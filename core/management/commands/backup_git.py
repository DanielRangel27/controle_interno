"""Push a database backup to a private Git repository.

Run::

    python manage.py backup_git

What the command does:

1. Clones the configured remote (``BACKUP_GIT_REMOTE``) into ``BACKUP_GIT_DIR``
   on the first run, or runs ``git pull`` on subsequent runs.
2. Writes ``backups/db-YYYY-MM-DD.json`` with ``manage.py dumpdata`` and replaces
   ``db.sqlite3`` with a binary copy of the live database.
3. If nothing changed since the last run, exits cleanly without creating an
   empty commit. Otherwise commits and pushes to the configured branch.

When the network is unreachable (DNS failure, no route to host), the command
falls back to "offline mode": it still creates the local commit so nothing is
lost, marks the result as ``network_offline=True`` and skips the push. The
next successful run will push any backlog of pending commits automatically.

Authentication is delegated to the system git installation (use the Windows
Credential Manager with a Personal Access Token, or an SSH remote).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


_NETWORK_ERROR_HINTS: tuple[str, ...] = (
    "could not resolve host",
    "could not resolve",
    "failed to connect",
    "unable to access",
    "operation timed out",
    "connection timed out",
    "no route to host",
    "network is unreachable",
    "temporary failure in name resolution",
    "ssl_connect",
    "could not read from remote",
    "the remote end hung up",
)


class GitError(RuntimeError):
    """Raised when a git subprocess returns a non-zero status."""


def is_network_error(exc: GitError | str) -> bool:
    """Detect if a git failure looks like a transient network issue."""

    text = str(exc).lower()
    return any(hint in text for hint in _NETWORK_ERROR_HINTS)


@dataclass(frozen=True)
class BackupConfig:
    remote: str
    branch: str
    repo_dir: Path
    db_path: Path
    target_subdir: str = "procuradoria"

    @classmethod
    def from_settings(cls) -> "BackupConfig":
        remote = str(getattr(settings, "BACKUP_GIT_REMOTE", "")).strip()
        if not remote:
            raise CommandError(
                "BACKUP_GIT_REMOTE não configurado. Defina no .env."
            )
        branch = str(getattr(settings, "BACKUP_GIT_BRANCH", "main")).strip() or "main"
        repo_dir = Path(getattr(settings, "BACKUP_GIT_DIR", settings.BASE_DIR / "_backup_repo"))
        db_path = Path(settings.DATABASES["default"]["NAME"])
        target_subdir = str(
            getattr(settings, "BACKUP_GIT_TARGET_SUBDIR", "procuradoria")
        ).strip() or "procuradoria"
        return cls(
            remote=remote,
            branch=branch,
            repo_dir=repo_dir,
            db_path=db_path,
            target_subdir=target_subdir,
        )


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` in ``cwd`` and raise :class:`GitError` on failure."""

    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} (rc={result.returncode})\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result


def _local_repo_exists(config: BackupConfig) -> bool:
    return (config.repo_dir / ".git").is_dir()


def ensure_repo(config: BackupConfig) -> bool:
    """Make sure the backup repository exists locally and is up to date.

    Returns ``True`` when the network sync succeeded, ``False`` when we had to
    fall back to the local repository because the remote was unreachable.
    """

    config.repo_dir.parent.mkdir(parents=True, exist_ok=True)
    if _local_repo_exists(config):
        try:
            run_git(["fetch", "origin"], cwd=config.repo_dir)
        except GitError as exc:
            if is_network_error(exc):
                logger.warning(
                    "backup offline: cannot reach remote, using local repo only",
                    extra={"error": str(exc)},
                )
                # Best effort: ensure the right branch is checked out locally.
                try:
                    run_git(["checkout", config.branch], cwd=config.repo_dir)
                except GitError:
                    run_git(["checkout", "-B", config.branch], cwd=config.repo_dir)
                return False
            raise
        try:
            run_git(["checkout", config.branch], cwd=config.repo_dir)
            run_git(["pull", "--ff-only", "origin", config.branch], cwd=config.repo_dir)
        except GitError:
            run_git(["checkout", "-B", config.branch], cwd=config.repo_dir)
        return True

    if config.repo_dir.exists() and any(config.repo_dir.iterdir()):
        raise CommandError(
            f"Diretório {config.repo_dir} existe mas não é um repositório Git. "
            "Remova-o ou aponte BACKUP_GIT_DIR para outro lugar."
        )
    config.repo_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_git(
            ["clone", "--branch", config.branch, config.remote, str(config.repo_dir)],
            cwd=config.repo_dir.parent,
        )
        return True
    except GitError as exc:
        if is_network_error(exc):
            raise CommandError(
                "Não foi possível clonar o repositório de backup (sem conexão). "
                "Conecte a máquina à internet ao menos uma vez para o primeiro backup."
            ) from exc
        run_git(["init"], cwd=config.repo_dir)
        run_git(["remote", "add", "origin", config.remote], cwd=config.repo_dir)
        run_git(["checkout", "-B", config.branch], cwd=config.repo_dir)
        return True


def write_dump(config: BackupConfig, timestamp: datetime) -> Path:
    """Run ``dumpdata`` into the backup repository and return the file path."""

    backups_dir = config.repo_dir / config.target_subdir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    target = backups_dir / f"db-{timestamp:%Y-%m-%d}.json"
    with open(target, "w", encoding="utf-8") as fh:
        call_command(
            "dumpdata",
            "--indent",
            "2",
            "--natural-foreign",
            "--natural-primary",
            "--exclude",
            "contenttypes",
            "--exclude",
            "auth.permission",
            "--exclude",
            "admin.logentry",
            "--exclude",
            "sessions.session",
            stdout=fh,
        )
    return target


def copy_sqlite(config: BackupConfig) -> Path | None:
    """Copy the live SQLite file into the backup repo (skip if not SQLite)."""

    if not config.db_path.exists():
        return None
    if config.db_path.suffix not in {".sqlite", ".sqlite3", ".db"}:
        return None
    target_dir = config.repo_dir / config.target_subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "db.sqlite3"
    shutil.copy2(config.db_path, target)
    return target


def _count_unpushed_commits(config: BackupConfig) -> int:
    """Return how many local commits are ahead of ``origin/<branch>``."""

    try:
        result = run_git(
            ["rev-list", "--count", f"origin/{config.branch}..HEAD"],
            cwd=config.repo_dir,
        )
    except GitError:
        return 0
    try:
        return int(result.stdout.strip() or "0")
    except ValueError:
        return 0


@dataclass(frozen=True)
class BackupResult:
    dump_path: Path
    sqlite_path: Path | None
    committed: bool
    pushed: bool
    network_offline: bool = False
    pending_commits: int = 0


def execute_backup(config: BackupConfig, *, no_push: bool = False) -> BackupResult:
    """Programmatic entry point used by the management command and tests."""

    timestamp = datetime.now()
    network_ok = ensure_repo(config)
    dump_path = write_dump(config, timestamp)
    sqlite_path = copy_sqlite(config)

    run_git(["add", "-A"], cwd=config.repo_dir)
    status = run_git(["status", "--porcelain"], cwd=config.repo_dir)
    has_staged_changes = bool(status.stdout.strip())

    committed = False
    if has_staged_changes:
        run_git(
            ["commit", "-m", f"backup: {timestamp:%Y-%m-%d %H:%M}"],
            cwd=config.repo_dir,
        )
        committed = True

    pushed = False
    network_offline = not network_ok
    unpushed_before = _count_unpushed_commits(config) if network_ok else 0
    if not no_push and network_ok and unpushed_before > 0:
        try:
            run_git(["push", "-u", "origin", config.branch], cwd=config.repo_dir)
            pushed = True
        except GitError as exc:
            if is_network_error(exc):
                logger.warning(
                    "backup offline during push: keeping commit local",
                    extra={"error": str(exc)},
                )
                network_offline = True
            else:
                raise

    pending = 0
    if network_offline or (committed and not pushed and not no_push):
        pending = _count_unpushed_commits(config)

    return BackupResult(
        dump_path=dump_path,
        sqlite_path=sqlite_path,
        committed=committed,
        pushed=pushed,
        network_offline=network_offline,
        pending_commits=pending,
    )


class Command(BaseCommand):
    help = "Faz dump do banco e envia para o repositório Git privado configurado."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--no-push",
            action="store_true",
            help="Faz commit local mas não envia para o remoto (útil para testes).",
        )

    def handle(self, *args, **options) -> None:
        config = BackupConfig.from_settings()
        no_push = options["no_push"]
        try:
            result = execute_backup(config, no_push=no_push)
        except GitError as exc:
            logger.error("git command failed: %s", exc)
            raise CommandError(str(exc)) from exc

        if not result.committed and not result.network_offline:
            self.stdout.write(self.style.WARNING(
                "Nada mudou desde o último backup; nada a commitar."
            ))
            logger.info("backup skipped (no changes)")
            return

        if result.network_offline:
            details = f"dump={result.dump_path.name}"
            if result.sqlite_path:
                details += f", sqlite={result.sqlite_path.name}"
            self.stdout.write(self.style.WARNING(
                f"Backup local registrado sem conexão: {details}. "
                f"{result.pending_commits} commit(s) pendente(s) para envio."
            ))
            logger.warning(
                "backup offline (commit kept locally)",
                extra={
                    "dump": str(result.dump_path),
                    "sqlite": str(result.sqlite_path) if result.sqlite_path else None,
                    "pending_commits": result.pending_commits,
                },
            )
            return

        suffix = (
            " (enviado para o remoto)" if result.pushed else " (não enviado)"
        )
        details = f"dump={result.dump_path.name}"
        if result.sqlite_path:
            details += f", sqlite={result.sqlite_path.name}"
        self.stdout.write(self.style.SUCCESS(f"Backup criado: {details}{suffix}"))
        logger.info(
            "backup completed",
            extra={
                "dump": str(result.dump_path),
                "sqlite": str(result.sqlite_path) if result.sqlite_path else None,
                "pushed": result.pushed,
            },
        )
