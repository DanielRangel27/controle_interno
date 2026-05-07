"""Tests for the core app: spreadsheet importers and backup command."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from .importers import (
    coerce_date,
    extract_apenso_numero,
    is_fazendaria_apenso_row,
    merge_apensos,
    parse_apensos,
    parse_data_nome,
    parse_destino_fazendaria,
    parse_fazendaria_row,
    parse_geral_row,
    parse_numero_processo,
    parse_responsaveis_geral,
    parse_saida_geral,
    parse_situacao_fazendaria,
    parse_situacao_geral,
    parse_tipos_parecer,
)


class ParseTiposParecerTests(SimpleTestCase):
    def test_handles_empty_values(self) -> None:
        self.assertEqual(parse_tipos_parecer(None), [])
        self.assertEqual(parse_tipos_parecer(""), [])
        self.assertEqual(parse_tipos_parecer("   "), [])

    def test_normalizes_full_words(self) -> None:
        self.assertEqual(parse_tipos_parecer("Despacho"), ["D"])
        self.assertEqual(parse_tipos_parecer("despacho"), ["D"])
        self.assertEqual(parse_tipos_parecer("Parecer"), ["P"])
        self.assertEqual(parse_tipos_parecer("Parecer deferindo"), ["Pd"])
        self.assertEqual(parse_tipos_parecer("Parecer indeferindo"), ["Pi"])
        self.assertEqual(parse_tipos_parecer("Remessa"), ["R"])

    def test_accepts_short_codes(self) -> None:
        self.assertEqual(parse_tipos_parecer("D"), ["D"])
        self.assertEqual(parse_tipos_parecer("Pd"), ["Pd"])
        self.assertEqual(parse_tipos_parecer("PD"), ["Pd"])
        self.assertEqual(parse_tipos_parecer("PI"), ["Pi"])
        self.assertEqual(parse_tipos_parecer("R"), ["R"])

    def test_splits_combined_codes(self) -> None:
        self.assertEqual(parse_tipos_parecer("R / Pd"), ["R", "Pd"])
        self.assertEqual(parse_tipos_parecer("R / Pd / D"), ["R", "Pd", "D"])
        self.assertEqual(parse_tipos_parecer("PD;R"), ["Pd", "R"])

    def test_ignores_unknown_tokens(self) -> None:
        self.assertEqual(parse_tipos_parecer("xyz"), [])
        self.assertEqual(parse_tipos_parecer("D / xyz"), ["D"])


class ParseNumeroProcessoTests(SimpleTestCase):
    def test_parses_two_digit_year(self) -> None:
        result = parse_numero_processo("547/25")
        assert result is not None
        self.assertEqual(result.numero, "547/25")
        self.assertEqual(result.ano, 2025)

    def test_parses_four_digit_year(self) -> None:
        result = parse_numero_processo("3712/2025")
        assert result is not None
        self.assertEqual(result.ano, 2025)

    def test_strips_whitespace(self) -> None:
        result = parse_numero_processo(" 6353/21 ")
        assert result is not None
        self.assertEqual(result.numero, "6353/21")
        self.assertEqual(result.ano, 2021)

    def test_returns_none_for_noise(self) -> None:
        self.assertIsNone(parse_numero_processo("apenso"))
        self.assertIsNone(parse_numero_processo("APENSO"))
        self.assertIsNone(parse_numero_processo("   "))
        self.assertIsNone(parse_numero_processo(None))
        self.assertIsNone(parse_numero_processo("II volumes"))


class ParseDataNomeTests(SimpleTestCase):
    def test_parses_date_and_name(self) -> None:
        result = parse_data_nome("05/01/2026 - Dra. Eduarda B")
        assert result is not None
        self.assertEqual(result.data, dt.date(2026, 1, 5))
        self.assertEqual(result.nome, "Dra. Eduarda B")

    def test_parses_two_digit_year(self) -> None:
        result = parse_data_nome("27/01/26 - Dra. Eduarda Barreto")
        assert result is not None
        self.assertEqual(result.data, dt.date(2026, 1, 27))
        self.assertEqual(result.nome, "Dra. Eduarda Barreto")

    def test_handles_only_name(self) -> None:
        result = parse_data_nome("Izabella")
        assert result is not None
        self.assertIsNone(result.data)
        self.assertEqual(result.nome, "Izabella")

    def test_returns_none_for_blank(self) -> None:
        self.assertIsNone(parse_data_nome(""))
        self.assertIsNone(parse_data_nome(None))


class ParseDestinoFazendariaTests(SimpleTestCase):
    def test_parses_setor_and_date(self) -> None:
        result = parse_destino_fazendaria("divativa - 30/03/26")
        assert result is not None
        self.assertEqual(result.setor, "divativa")
        self.assertEqual(result.data, dt.date(2026, 3, 30))

    def test_handles_no_space_around_dash(self) -> None:
        result = parse_destino_fazendaria("Secat-12/01/26")
        assert result is not None
        self.assertEqual(result.setor, "Secat")
        self.assertEqual(result.data, dt.date(2026, 1, 12))

    def test_handles_only_setor(self) -> None:
        result = parse_destino_fazendaria("Gabinete")
        assert result is not None
        self.assertEqual(result.setor, "Gabinete")
        self.assertIsNone(result.data)


class ParseSaidaGeralTests(SimpleTestCase):
    def test_parses_date_then_setor(self) -> None:
        result = parse_saida_geral("06/01/2026 - Procsefop")
        assert result is not None
        self.assertEqual(result.data, dt.date(2026, 1, 6))
        self.assertEqual(result.setor, "Procsefop")

    def test_handles_only_setor(self) -> None:
        result = parse_saida_geral("Segurança Pública")
        assert result is not None
        self.assertEqual(result.setor, "Segurança Pública")
        self.assertIsNone(result.data)


class ParseSituacaoTests(SimpleTestCase):
    def test_fazendaria_situacoes(self) -> None:
        self.assertEqual(parse_situacao_fazendaria("concluído"), "concluido")
        self.assertEqual(parse_situacao_fazendaria("CONCLUÍDO"), "concluido")
        self.assertEqual(parse_situacao_fazendaria("Andamento"), "andamento")
        self.assertEqual(parse_situacao_fazendaria("Remessa"), "remessa")
        self.assertEqual(parse_situacao_fazendaria("no armário"), "no_armario")
        self.assertIsNone(parse_situacao_fazendaria("xyz"))
        self.assertIsNone(parse_situacao_fazendaria(""))

    def test_geral_situacoes(self) -> None:
        self.assertEqual(parse_situacao_geral("ENTREGUE"), "entregue")
        self.assertEqual(parse_situacao_geral("Entregue no caderno"), "caderno")
        self.assertEqual(parse_situacao_geral("ANDAMENTO"), "andamento")
        self.assertEqual(parse_situacao_geral("Análise"), "analise")
        self.assertEqual(parse_situacao_geral("CONCLUÍDO"), "concluido")
        self.assertIsNone(parse_situacao_geral("xyz"))


class ParseApensosTests(SimpleTestCase):
    def test_dash_becomes_empty(self) -> None:
        self.assertEqual(parse_apensos("-"), "")
        self.assertEqual(parse_apensos("--"), "")
        self.assertEqual(parse_apensos(None), "")

    def test_real_value_preserved(self) -> None:
        self.assertEqual(parse_apensos("301/2014"), "301/2014")
        self.assertEqual(parse_apensos(" II volumes "), "II volumes")


class FazendariaApensoHelpersTests(SimpleTestCase):
    def test_is_fazendaria_apenso_row_detects_variations(self) -> None:
        self.assertTrue(is_fazendaria_apenso_row("apenso"))
        self.assertTrue(is_fazendaria_apenso_row("APENSO"))
        self.assertTrue(is_fazendaria_apenso_row(" Apenso "))
        self.assertTrue(is_fazendaria_apenso_row("apensos"))

    def test_is_fazendaria_apenso_row_rejects_other_values(self) -> None:
        self.assertFalse(is_fazendaria_apenso_row(""))
        self.assertFalse(is_fazendaria_apenso_row(None))
        self.assertFalse(is_fazendaria_apenso_row("547/25"))
        self.assertFalse(is_fazendaria_apenso_row("apenso de algo"))

    def test_extract_apenso_numero_normalizes_known_formats(self) -> None:
        self.assertEqual(extract_apenso_numero("3928/15"), "3928/15")
        self.assertEqual(extract_apenso_numero(" 7689/21 "), "7689/21")
        self.assertEqual(extract_apenso_numero("3712/2025"), "3712/2025")

    def test_extract_apenso_numero_falls_back_to_raw_text(self) -> None:
        self.assertEqual(extract_apenso_numero("II volumes"), "II volumes")

    def test_extract_apenso_numero_returns_empty_for_blank(self) -> None:
        self.assertEqual(extract_apenso_numero(None), "")
        self.assertEqual(extract_apenso_numero("   "), "")

    def test_merge_apensos_appends_unique_values(self) -> None:
        self.assertEqual(merge_apensos("", "3928/15"), "3928/15")
        self.assertEqual(merge_apensos("3928/15", "7689/21"), "3928/15; 7689/21")

    def test_merge_apensos_is_case_insensitive_and_idempotent(self) -> None:
        self.assertEqual(merge_apensos("3928/15", "3928/15"), "3928/15")
        self.assertEqual(merge_apensos("3928/15", " 3928/15 "), "3928/15")
        self.assertEqual(
            merge_apensos("3928/15; 7689/21", "7689/21"),
            "3928/15; 7689/21",
        )

    def test_merge_apensos_preserves_existing_when_new_is_blank(self) -> None:
        self.assertEqual(merge_apensos("3928/15", ""), "3928/15")
        self.assertEqual(merge_apensos("3928/15", None), "3928/15")  # type: ignore[arg-type]


class ParseResponsaveisGeralTests(SimpleTestCase):
    def test_single(self) -> None:
        result = parse_responsaveis_geral("Adolpho")
        assert result is not None
        self.assertEqual(result.principal, "Adolpho")
        self.assertIsNone(result.secundario)

    def test_two(self) -> None:
        result = parse_responsaveis_geral("Iely / Rodrigo")
        assert result is not None
        self.assertEqual(result.principal, "Iely")
        self.assertEqual(result.secundario, "Rodrigo")


class CoerceDateTests(SimpleTestCase):
    def test_passthrough_datetime(self) -> None:
        self.assertEqual(
            coerce_date(dt.datetime(2026, 1, 5, 9, 30)), dt.date(2026, 1, 5)
        )

    def test_string_with_date_prefix(self) -> None:
        self.assertEqual(coerce_date("05/01/2026"), dt.date(2026, 1, 5))

    def test_blank_returns_none(self) -> None:
        self.assertIsNone(coerce_date(""))
        self.assertIsNone(coerce_date(None))


class ParseFazendariaRowTests(SimpleTestCase):
    def test_typical_row(self) -> None:
        # 14 columns mirroring the 2026 fazendaria sheet (cols 3, 6-9, 11, 14 are noise).
        row = (
            "547/25", "05/01/2026 - Dra. Eduarda B", None, None, "Lançamento Predial",
            None, None, None, None, "concluído", None, "Secat-12/01/26", "Despacho",
            None,
        )
        record = parse_fazendaria_row(row)
        assert record is not None
        self.assertEqual(record.numero.numero, "547/25")
        self.assertEqual(record.numero.ano, 2025)
        self.assertEqual(record.procurador_nome, "Dra. Eduarda B")
        self.assertEqual(record.data_recebimento, dt.date(2026, 1, 5))
        self.assertEqual(record.assunto, "Lançamento Predial")
        self.assertEqual(record.situacao, "concluido")
        self.assertEqual(record.destino_nome, "Secat")
        self.assertEqual(record.data_remessa, dt.date(2026, 1, 12))
        self.assertEqual(record.tipos_parecer, ["D"])

    def test_apenso_row_returns_none(self) -> None:
        row = ("apenso", None, None, None, None, None, None, None, None,
               None, None, None, None, None)
        self.assertIsNone(parse_fazendaria_row(row))


class ParseGeralRowTests(SimpleTestCase):
    def test_typical_row(self) -> None:
        row = (
            "3712/2025",
            None,
            "-",
            dt.datetime(2026, 1, 5),
            "Procsefop",
            "Retirada de custas",
            "ENTREGUE",
            "06/01/2026 - Procsefop",
            "R",
        )
        record = parse_geral_row(row)
        assert record is not None
        self.assertEqual(record.numero.ano, 2025)
        self.assertIsNone(record.data_entrada)
        self.assertEqual(record.apensos, "")
        self.assertEqual(record.data_distribuicao, dt.date(2026, 1, 5))
        self.assertEqual(record.responsavel_nome, "Procsefop")
        self.assertIsNone(record.responsavel_secundario_nome)
        self.assertEqual(record.assunto, "Retirada de custas")
        self.assertEqual(record.situacao, "entregue")
        self.assertEqual(record.data_saida, dt.date(2026, 1, 6))
        self.assertEqual(record.destino_saida_nome, "Procsefop")
        self.assertEqual(record.tipos_parecer, ["R"])

    def test_co_responsavel_and_apenso(self) -> None:
        row = (
            "2478/2025",
            None,
            "301/2014",
            dt.datetime(2025, 12, 23),
            "Iely / Rodrigo",
            "Autonomia de táxi",
            "ENTREGUE",
            "16/01/2026 - Seg. Pública",
            "R / Pd",
        )
        record = parse_geral_row(row)
        assert record is not None
        self.assertEqual(record.responsavel_nome, "Iely")
        self.assertEqual(record.responsavel_secundario_nome, "Rodrigo")
        self.assertEqual(record.apensos, "301/2014")
        self.assertEqual(record.tipos_parecer, ["R", "Pd"])


class ImportarPlanilhasFazendariaApensoTests(TestCase):
    """End-to-end test for the fazendaria importer attaching apenso rows."""

    def _build_workbook(self, path: Path, rows: list[tuple]) -> None:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "2026"
        for row in rows:
            ws.append(row)
        wb.save(path)

    def test_apenso_row_is_attached_to_previous_main_row(self) -> None:
        from django.core.management import call_command

        from fazendaria.models import ProcessoFazendaria

        rows: list[tuple] = [
            (
                "547/25", "05/01/2026 - Dra. Eduarda B", None, None,
                "Lançamento Predial", None, None, None, None, "concluído",
                None, "Secat-12/01/26", "Despacho", None,
            ),
            (
                "apenso", "3928/15", None, None, None, None, None, None,
                None, None, None, None, None, None,
            ),
            (
                "apenso", "7689/21", None, None, None, None, None, None,
                None, None, None, None, None, None,
            ),
            (
                "548/25", "06/01/2026 - Dra. Eduarda B", None, None,
                "Outro assunto", None, None, None, None, "Andamento",
                None, None, None, None,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "fazendaria.xlsx"
            self._build_workbook(path, rows)

            call_command("importar_planilhas", fazendaria=str(path), aba="2026")

            principal = ProcessoFazendaria.objects.get(numero_processo="547/25")
            self.assertEqual(principal.apensos, "3928/15; 7689/21")

            sem_apenso = ProcessoFazendaria.objects.get(numero_processo="548/25")
            self.assertEqual(sem_apenso.apensos, "")

            # Apenso rows must NOT be persisted as separate processes.
            self.assertFalse(
                ProcessoFazendaria.objects.filter(numero_processo="3928/15").exists()
            )
            self.assertFalse(
                ProcessoFazendaria.objects.filter(numero_processo="7689/21").exists()
            )

    def test_reimport_is_idempotent_for_apensos(self) -> None:
        from django.core.management import call_command

        from fazendaria.models import ProcessoFazendaria

        rows: list[tuple] = [
            (
                "547/25", "05/01/2026 - Dra. Eduarda B", None, None,
                "Lançamento Predial", None, None, None, None, "concluído",
                None, "Secat-12/01/26", "Despacho", None,
            ),
            (
                "apenso", "3928/15", None, None, None, None, None, None,
                None, None, None, None, None, None,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "fazendaria.xlsx"
            self._build_workbook(path, rows)

            call_command("importar_planilhas", fazendaria=str(path), aba="2026")
            call_command("importar_planilhas", fazendaria=str(path), aba="2026")

            principal = ProcessoFazendaria.objects.get(numero_processo="547/25")
            self.assertEqual(principal.apensos, "3928/15")
            self.assertEqual(ProcessoFazendaria.objects.count(), 1)


def _git_env() -> dict[str, str]:
    """Return env vars that force a deterministic git author/committer.

    This sidesteps any missing ``user.name``/``user.email`` config on the
    machine running the tests.
    """

    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Backup Test",
            "GIT_AUTHOR_EMAIL": "backup-test@example.com",
            "GIT_COMMITTER_NAME": "Backup Test",
            "GIT_COMMITTER_EMAIL": "backup-test@example.com",
        }
    )
    return env


class BackupGitCommandTests(TestCase):
    """End-to-end tests for ``backup_git`` using a local bare repo as remote.

    A bare repository is a real git remote that lives on disk; it lets us push
    without any network access while exercising the full flow (clone, dump,
    copy sqlite, commit, push).
    """

    def setUp(self) -> None:
        # Each test gets a fresh remote so they don't see each other's commits.
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.remote_path = self.tmp_path / "remote.git"
        env = _git_env()
        subprocess.run(
            ["git", "init", "--bare", "-b", "main", str(self.remote_path)],
            check=True,
            capture_output=True,
            env=env,
        )
        seed = self.tmp_path / "seed"
        seed.mkdir()
        for cmd in (
            ["init", "-b", "main"],
            ["commit", "--allow-empty", "-m", "init"],
            ["remote", "add", "origin", str(self.remote_path)],
            ["push", "-u", "origin", "main"],
        ):
            subprocess.run(
                ["git", *cmd],
                cwd=str(seed),
                check=True,
                capture_output=True,
                env=env,
            )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build_config(self, repo_dir: Path):
        from .management.commands.backup_git import BackupConfig

        return BackupConfig(
            remote=str(self.remote_path),
            branch="main",
            repo_dir=repo_dir,
            db_path=Path(__file__).resolve().parent.parent / "db.sqlite3",
        )

    def _run_with_env(self, repo_dir: Path):
        """Run ``execute_backup`` with deterministic git author env vars."""

        from .management.commands import backup_git as backup_module

        original_run = subprocess.run

        def run_with_env(*args, **kwargs):
            env = kwargs.pop("env", None) or os.environ.copy()
            env.update(_git_env())
            return original_run(*args, env=env, **kwargs)

        config = self._build_config(repo_dir)
        with patch.object(backup_module.subprocess, "run", side_effect=run_with_env):
            return backup_module.execute_backup(config), config

    def test_first_run_clones_and_pushes(self) -> None:
        repo_dir = self.tmp_path / "first_run"
        result, _ = self._run_with_env(repo_dir)
        self.assertTrue(result.committed)
        self.assertTrue(result.pushed)
        self.assertTrue(result.dump_path.exists())
        self.assertEqual(result.dump_path.parent.parent.name, "procuradoria")
        self.assertEqual(result.dump_path.parent.name, "backups")
        # Remote must have received the new commit.
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(self.remote_path),
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("backup:", log.stdout)

    def test_second_run_with_no_changes_skips_commit(self) -> None:
        repo_dir = self.tmp_path / "second_run"
        first, _ = self._run_with_env(repo_dir)
        self.assertTrue(first.committed)

        second, _ = self._run_with_env(repo_dir)
        self.assertFalse(
            second.committed,
            "Backup criou commit vazio quando nada mudou.",
        )
        self.assertFalse(second.pushed)

    def test_offline_keeps_local_commit_and_marks_pending(self) -> None:
        from .management.commands import backup_git as backup_module

        repo_dir = self.tmp_path / "offline_run"
        # First run online so the local clone exists.
        first, config = self._run_with_env(repo_dir)
        self.assertTrue(first.pushed)

        # Simulate offline: redirect the local repo's origin to a host that
        # will fail DNS resolution. ``git fetch``/``push`` will then complain
        # with messages matching ``is_network_error``.
        env = _git_env()
        subprocess.run(
            ["git", "remote", "set-url", "origin",
             "https://invalid.invalid-host.example/repo.git"],
            cwd=str(repo_dir),
            check=True,
            capture_output=True,
            env=env,
        )

        # Touch the live SQLite file so there is something new to commit.
        if config.db_path.exists():
            mtime = config.db_path.stat().st_mtime + 1
            os.utime(config.db_path, (mtime, mtime))

        # Even when "offline", the backup must not raise. It must produce a
        # local commit and report ``network_offline=True``.
        original_run = subprocess.run

        def run_with_env(*args, **kwargs):
            env = kwargs.pop("env", None) or os.environ.copy()
            env.update(_git_env())
            return original_run(*args, env=env, **kwargs)

        with patch.object(backup_module.subprocess, "run", side_effect=run_with_env):
            result = backup_module.execute_backup(config)

        self.assertTrue(result.network_offline)
        self.assertFalse(result.pushed)


class IsNetworkErrorTests(SimpleTestCase):
    def test_detects_dns_failure(self) -> None:
        from core.management.commands.backup_git import is_network_error

        self.assertTrue(
            is_network_error("fatal: unable to access 'https://github.com/foo'")
        )
        self.assertTrue(is_network_error("Could not resolve host: github.com"))
        self.assertTrue(is_network_error("Failed to connect to github.com port 443"))

    def test_ignores_unrelated_messages(self) -> None:
        from core.management.commands.backup_git import is_network_error

        self.assertFalse(is_network_error("permission denied (publickey)"))
        self.assertFalse(is_network_error("merge conflict in foo.txt"))


def _make_backup_result(**overrides):
    """Build a fake ``BackupResult`` for tests that mock ``execute_backup``."""

    from core.management.commands.backup_git import BackupResult

    defaults = dict(
        dump_path=Path("/tmp/dump.json"),
        sqlite_path=None,
        committed=True,
        pushed=True,
        network_offline=False,
        pending_commits=0,
    )
    defaults.update(overrides)
    return BackupResult(**defaults)


@override_settings(
    BACKUP_GIT_AUTO_ON_PROCESS_CHANGE=True,
    BACKUP_GIT_AUTO_COOLDOWN_SECONDS=0,
)
class ProcessAutoBackupSignalTests(TestCase):
    """Signal tests for automatic backup on process CRUD changes."""

    def test_runs_backup_on_process_create_update_delete(self) -> None:
        from geral.models import ProcessoGeral

        with patch(
            "core.process_backup_signals.execute_backup",
            return_value=_make_backup_result(),
        ) as mocked_run:
            with patch(
                "core.process_backup_signals.BackupConfig.from_settings",
                return_value=object(),
            ):
                process = ProcessoGeral.objects.create(numero_processo="9001/26", ano=2026)
                process.observacoes = "Atualizado por teste"
                process.save(update_fields=["observacoes"])
                process.delete()

        self.assertEqual(mocked_run.call_count, 3)

    def test_status_is_ok_after_successful_backup(self) -> None:
        from core.process_backup_signals import get_last_backup_status, reset_status
        from geral.models import ProcessoGeral

        reset_status()
        with patch(
            "core.process_backup_signals.execute_backup",
            return_value=_make_backup_result(),
        ):
            with patch(
                "core.process_backup_signals.BackupConfig.from_settings",
                return_value=object(),
            ):
                ProcessoGeral.objects.create(numero_processo="9100/26", ano=2026)

        status = get_last_backup_status()
        self.assertIsNotNone(status)
        self.assertEqual(status.outcome, "ok")
        reset_status()

    def test_status_is_offline_when_network_unreachable(self) -> None:
        from core.process_backup_signals import get_last_backup_status, reset_status
        from geral.models import ProcessoGeral

        reset_status()
        with patch(
            "core.process_backup_signals.execute_backup",
            return_value=_make_backup_result(
                network_offline=True, pushed=False, pending_commits=2
            ),
        ):
            with patch(
                "core.process_backup_signals.BackupConfig.from_settings",
                return_value=object(),
            ):
                ProcessoGeral.objects.create(numero_processo="9101/26", ano=2026)

        status = get_last_backup_status()
        self.assertIsNotNone(status)
        self.assertEqual(status.outcome, "offline")
        self.assertEqual(status.pending_commits, 2)
        reset_status()

    def test_status_is_error_when_backup_raises(self) -> None:
        from core.process_backup_signals import get_last_backup_status, reset_status
        from geral.models import ProcessoGeral

        reset_status()
        with patch(
            "core.process_backup_signals.execute_backup",
            side_effect=RuntimeError("boom"),
        ):
            with patch(
                "core.process_backup_signals.BackupConfig.from_settings",
                return_value=object(),
            ):
                ProcessoGeral.objects.create(numero_processo="9102/26", ano=2026)

        status = get_last_backup_status()
        self.assertIsNotNone(status)
        self.assertEqual(status.outcome, "error")
        self.assertIn("boom", status.error_message or "")
        reset_status()

    def test_offline_does_not_update_cooldown_state_file(self) -> None:
        from geral.models import ProcessoGeral

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "last_run.txt"
            with override_settings(
                BACKUP_GIT_AUTO_ON_PROCESS_CHANGE=True,
                BACKUP_GIT_AUTO_COOLDOWN_SECONDS=120,
                BACKUP_GIT_AUTO_COOLDOWN_STATE_FILE=state_file,
            ):
                with patch(
                    "core.process_backup_signals.execute_backup",
                    return_value=_make_backup_result(
                        network_offline=True, pushed=False
                    ),
                ):
                    with patch(
                        "core.process_backup_signals.BackupConfig.from_settings",
                        return_value=object(),
                    ):
                        ProcessoGeral.objects.create(numero_processo="9103/26", ano=2026)

            self.assertFalse(state_file.exists())

    def test_respects_cooldown_window(self) -> None:
        from geral.models import ProcessoGeral

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "last_run.txt"
            state_file.write_text(str(time.time()), encoding="utf-8")
            with override_settings(
                BACKUP_GIT_AUTO_ON_PROCESS_CHANGE=True,
                BACKUP_GIT_AUTO_COOLDOWN_SECONDS=120,
                BACKUP_GIT_AUTO_COOLDOWN_STATE_FILE=state_file,
            ):
                with patch(
                    "core.process_backup_signals.execute_backup"
                ) as mocked_run:
                    ProcessoGeral.objects.create(numero_processo="9003/26", ano=2026)

        mocked_run.assert_not_called()

    def test_updates_cooldown_state_file_after_success(self) -> None:
        from geral.models import ProcessoGeral

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "last_run.txt"
            state_file.write_text("1.0", encoding="utf-8")
            with override_settings(
                BACKUP_GIT_AUTO_ON_PROCESS_CHANGE=True,
                BACKUP_GIT_AUTO_COOLDOWN_SECONDS=120,
                BACKUP_GIT_AUTO_COOLDOWN_STATE_FILE=state_file,
            ):
                with patch(
                    "core.process_backup_signals.execute_backup",
                    return_value=_make_backup_result(),
                ) as mocked_run:
                    with patch(
                        "core.process_backup_signals.BackupConfig.from_settings",
                        return_value=object(),
                    ):
                        with patch(
                            "core.process_backup_signals.time.time",
                            side_effect=[1000.0, 1000.0],
                        ):
                            ProcessoGeral.objects.create(numero_processo="9004/26", ano=2026)
                mocked_run.assert_called_once()
                self.assertEqual(state_file.read_text(encoding="utf-8").strip(), "1000.0")


@override_settings(BACKUP_GIT_AUTO_ON_PROCESS_CHANGE=False)
class ProcessAutoBackupDisabledTests(TestCase):
    def test_does_not_run_backup_when_flag_is_disabled(self) -> None:
        from geral.models import ProcessoGeral

        with patch(
            "core.process_backup_signals.execute_backup"
        ) as mocked_run:
            ProcessoGeral.objects.create(numero_processo="9002/26", ano=2026)

        mocked_run.assert_not_called()


class BackupStatusFlashMiddlewareTests(SimpleTestCase):
    """Verify that the middleware turns thread-local status into flash messages."""

    def _build_middleware(self):
        from core.middleware import BackupStatusFlashMiddleware
        from django.http import HttpResponse

        def get_response(_request):
            return HttpResponse("ok")

        return BackupStatusFlashMiddleware(get_response)

    def _build_request(self, *, authenticated: bool = True):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        request = RequestFactory().post("/geral/novo/")
        request.session = {}
        request._messages = FallbackStorage(request)

        class _User:
            def __init__(self, authed: bool) -> None:
                self.is_authenticated = authed

        request.user = _User(authenticated)
        return request

    def test_offline_status_adds_warning_message(self) -> None:
        from django.contrib import messages as message_module

        from core.process_backup_signals import BackupStatus, _set_status

        middleware = self._build_middleware()
        request = self._build_request()

        def get_response(_req):
            _set_status(BackupStatus(outcome="offline", pending_commits=3))
            from django.http import HttpResponse

            return HttpResponse("ok")

        middleware.get_response = get_response
        middleware(request)

        stored = list(request._messages)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].level, message_module.WARNING)
        self.assertIn("sem conexão", stored[0].message)
        self.assertIn("3 commit(s) pendente(s)", stored[0].message)

    def test_error_status_adds_error_message(self) -> None:
        from django.contrib import messages as message_module

        from core.process_backup_signals import BackupStatus, _set_status

        middleware = self._build_middleware()
        request = self._build_request()

        def get_response(_req):
            _set_status(BackupStatus(outcome="error", error_message="boom"))
            from django.http import HttpResponse

            return HttpResponse("ok")

        middleware.get_response = get_response
        middleware(request)

        stored = list(request._messages)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].level, message_module.ERROR)

    def test_anonymous_user_does_not_get_flash(self) -> None:
        from core.process_backup_signals import BackupStatus, _set_status

        middleware = self._build_middleware()
        request = self._build_request(authenticated=False)

        def get_response(_req):
            _set_status(BackupStatus(outcome="offline"))
            from django.http import HttpResponse

            return HttpResponse("ok")

        middleware.get_response = get_response
        middleware(request)

        self.assertEqual(list(request._messages), [])


class CoreServiceReportTests(TestCase):
    """Tests for the rich dashboard / relatorio service helpers."""

    @classmethod
    def setUpTestData(cls) -> None:
        from core.models import Assunto, Modulo, Procurador, Setor, TipoParecer
        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria
        from geral.models import ProcessoGeral, SituacaoGeral

        cls.proc = Procurador.objects.create(
            nome="Dra. Eduarda", modulo=Modulo.AMBOS
        )
        cls.setor = Setor.objects.create(nome="DIVATIVA")
        cls.assunto_faz = Assunto.objects.create(
            nome="Lançamento", modulo=Modulo.FAZENDARIA
        )
        cls.assunto_geral = Assunto.objects.create(
            nome="Permuta", modulo=Modulo.GERAL
        )
        cls.tp = TipoParecer.objects.create(codigo="P", nome="Parecer")

        today = dt.date.today()
        cls.faz = ProcessoFazendaria.objects.create(
            numero_processo="100/26",
            ano=today.year,
            procurador=cls.proc,
            data_recebimento=today,
            assunto=cls.assunto_faz,
            destino=cls.setor,
            situacao=SituacaoFazendaria.ANDAMENTO,
        )
        cls.faz.tipos_parecer.add(cls.tp)

        cls.ger = ProcessoGeral.objects.create(
            numero_processo="200/2026",
            ano=today.year,
            data_distribuicao=today,
            responsavel=cls.proc,
            assunto=cls.assunto_geral,
            destino_saida=cls.setor,
            situacao=SituacaoGeral.ANDAMENTO,
        )
        cls.ger.tipos_parecer.add(cls.tp)

    def test_dashboard_summaries_include_both_modules(self) -> None:
        from core.services import get_dashboard_summaries

        summaries = get_dashboard_summaries()
        slugs = {s.slug for s in summaries}
        self.assertEqual(slugs, {"fazendaria", "geral"})
        for s in summaries:
            self.assertGreaterEqual(s.total, 1)

    def test_recent_processes_returns_items_from_both_modules(self) -> None:
        from core.services import get_recent_processes

        recent = get_recent_processes(limit=5)
        modulos = {item.modulo for item in recent}
        self.assertEqual(modulos, {"Fazendária", "Geral"})

    def test_fazendaria_report_has_top_lists_and_monthly(self) -> None:
        from core.services import fazendaria_report

        report = fazendaria_report()
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report.total, 1)
        self.assertEqual(len(report.monthly), 12)
        self.assertEqual(report.monthly_max, 1)
        self.assertEqual(report.top_procuradores[0].count, 1)
        self.assertEqual(report.top_setores[0].count, 1)
        self.assertEqual(report.top_pareceres[0].count, 1)
        labels = [c.label for c in report.counters]
        self.assertIn("Em andamento", labels)

    def test_geral_report_has_top_lists_and_monthly(self) -> None:
        from core.services import geral_report

        report = geral_report()
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report.total, 1)
        self.assertEqual(len(report.monthly), 12)
        self.assertGreaterEqual(report.monthly_max, 1)
        self.assertEqual(report.top_procuradores[0].count, 1)

    def test_global_search_finds_in_both_modules(self) -> None:
        from core.services import global_search

        hits = global_search("100/26")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].modulo, "Fazendária")

        hits = global_search("200")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].modulo, "Geral")

        self.assertEqual(global_search(""), [])


class CoreSearchViewTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        from django.contrib.auth import get_user_model
        from core.models import Assunto, Modulo
        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria

        cls.user = get_user_model().objects.create_user(username="u", password="x")
        cls.assunto = Assunto.objects.create(nome="X", modulo=Modulo.FAZENDARIA)
        ProcessoFazendaria.objects.create(
            numero_processo="ABC123/26",
            ano=2026,
            assunto=cls.assunto,
            situacao=SituacaoFazendaria.ANDAMENTO,
        )

    def setUp(self) -> None:
        self.client.login(username="u", password="x")

    def test_search_view_renders_results(self) -> None:
        from django.urls import reverse

        resp = self.client.get(reverse("core:busca"), {"q": "ABC123"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ABC123/26")

    def test_search_view_without_query_renders_empty(self) -> None:
        from django.urls import reverse

        resp = self.client.get(reverse("core:busca"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "ABC123/26")


class DistribuirProcessosServiceTests(TestCase):
    """Tests for the ``distribuir_processos`` service helper."""

    @classmethod
    def setUpTestData(cls) -> None:
        from core.models import Modulo, Procurador
        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria
        from geral.models import ProcessoGeral, SituacaoGeral

        cls.procurador = Procurador.objects.create(
            nome="Dra. Distribuidora", modulo=Modulo.AMBOS
        )
        cls.faz1 = ProcessoFazendaria.objects.create(
            numero_processo="500/26",
            ano=2026,
            situacao=SituacaoFazendaria.DISTRIBUICAO,
        )
        cls.faz2 = ProcessoFazendaria.objects.create(
            numero_processo="501/26",
            ano=2026,
            situacao=SituacaoFazendaria.DISTRIBUICAO,
        )
        cls.ger1 = ProcessoGeral.objects.create(
            numero_processo="900/26",
            ano=2026,
            situacao=SituacaoGeral.DISTRIBUICAO,
        )
        cls.ger2 = ProcessoGeral.objects.create(
            numero_processo="901/26",
            ano=2026,
            situacao=SituacaoGeral.DISTRIBUICAO,
        )

    def test_updates_both_modules_with_today(self) -> None:
        from core.services import distribuir_processos
        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria
        from geral.models import ProcessoGeral, SituacaoGeral

        result = distribuir_processos(
            procurador_id=self.procurador.pk,
            fazendaria_ids=[self.faz1.pk, self.faz2.pk],
            geral_ids=[self.ger1.pk],
        )
        today = dt.date.today()

        self.assertEqual(result.fazendaria_atualizados, 2)
        self.assertEqual(result.geral_atualizados, 1)
        self.assertEqual(result.responsavel_nome, "Dra. Distribuidora")
        self.assertEqual(len(result.processos_pdf), 3)

        for faz in ProcessoFazendaria.objects.filter(pk__in=[self.faz1.pk, self.faz2.pk]):
            self.assertEqual(faz.procurador_id, self.procurador.pk)
            self.assertEqual(faz.situacao, SituacaoFazendaria.ANDAMENTO)
            self.assertEqual(faz.data_distribuicao, today)

        ger1 = ProcessoGeral.objects.get(pk=self.ger1.pk)
        self.assertEqual(ger1.responsavel_id, self.procurador.pk)
        self.assertEqual(ger1.situacao, SituacaoGeral.ANDAMENTO)
        self.assertEqual(ger1.data_distribuicao, today)

        ger2 = ProcessoGeral.objects.get(pk=self.ger2.pk)
        self.assertEqual(ger2.situacao, SituacaoGeral.DISTRIBUICAO)
        self.assertIsNone(ger2.responsavel_id)
        self.assertIsNone(ger2.data_distribuicao)

    def test_accepts_explicit_date(self) -> None:
        from core.services import distribuir_processos
        from geral.models import ProcessoGeral

        custom = dt.date(2026, 4, 1)
        distribuir_processos(
            procurador_id=self.procurador.pk,
            fazendaria_ids=[],
            geral_ids=[self.ger1.pk],
            data_distribuicao=custom,
        )
        ger1 = ProcessoGeral.objects.get(pk=self.ger1.pk)
        self.assertEqual(ger1.data_distribuicao, custom)


class DistribuicaoPDFViewTests(TestCase):
    """Integration tests for the ``DistribuicaoPDFView`` endpoint."""

    @classmethod
    def setUpTestData(cls) -> None:
        from django.contrib.auth import get_user_model

        from core.models import Modulo, Procurador
        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria
        from geral.models import ProcessoGeral, SituacaoGeral

        cls.user = get_user_model().objects.create_user(username="dist", password="x")
        cls.procurador = Procurador.objects.create(
            nome="Dr. Responsável", modulo=Modulo.AMBOS
        )
        cls.procurador_inativo = Procurador.objects.create(
            nome="Dra. Inativa", modulo=Modulo.AMBOS, ativo=False
        )
        cls.faz = ProcessoFazendaria.objects.create(
            numero_processo="700/26",
            ano=2026,
            situacao=SituacaoFazendaria.DISTRIBUICAO,
        )
        cls.ger = ProcessoGeral.objects.create(
            numero_processo="800/26",
            ano=2026,
            situacao=SituacaoGeral.DISTRIBUICAO,
        )

    def setUp(self) -> None:
        self.client.login(username="dist", password="x")

    def test_post_updates_processes_and_returns_pdf(self) -> None:
        from django.urls import reverse

        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria
        from geral.models import ProcessoGeral, SituacaoGeral

        resp = self.client.post(
            reverse("core:distribuicao_pdf"),
            data={
                "responsavel": str(self.procurador.pk),
                "faz": [str(self.faz.pk)],
                "ger": [str(self.ger.pk)],
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

        today = dt.date.today()
        faz = ProcessoFazendaria.objects.get(pk=self.faz.pk)
        self.assertEqual(faz.procurador_id, self.procurador.pk)
        self.assertEqual(faz.situacao, SituacaoFazendaria.ANDAMENTO)
        self.assertEqual(faz.data_distribuicao, today)

        ger = ProcessoGeral.objects.get(pk=self.ger.pk)
        self.assertEqual(ger.responsavel_id, self.procurador.pk)
        self.assertEqual(ger.situacao, SituacaoGeral.ANDAMENTO)
        self.assertEqual(ger.data_distribuicao, today)

    def test_post_without_responsavel_does_not_update(self) -> None:
        from django.urls import reverse

        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria

        resp = self.client.post(
            reverse("core:distribuicao_pdf"),
            data={"faz": [str(self.faz.pk)]},
        )

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:distribuicao"))

        faz = ProcessoFazendaria.objects.get(pk=self.faz.pk)
        self.assertEqual(faz.situacao, SituacaoFazendaria.DISTRIBUICAO)
        self.assertIsNone(faz.procurador_id)
        self.assertIsNone(faz.data_distribuicao)

    def test_post_without_processos_does_not_update(self) -> None:
        from django.urls import reverse

        from geral.models import ProcessoGeral, SituacaoGeral

        resp = self.client.post(
            reverse("core:distribuicao_pdf"),
            data={"responsavel": str(self.procurador.pk)},
        )

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:distribuicao"))

        ger = ProcessoGeral.objects.get(pk=self.ger.pk)
        self.assertEqual(ger.situacao, SituacaoGeral.DISTRIBUICAO)
        self.assertIsNone(ger.responsavel_id)
        self.assertIsNone(ger.data_distribuicao)

    def test_post_with_invalid_responsavel_does_not_update(self) -> None:
        from django.urls import reverse

        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria

        resp = self.client.post(
            reverse("core:distribuicao_pdf"),
            data={
                "responsavel": "999999",
                "faz": [str(self.faz.pk)],
            },
        )

        self.assertEqual(resp.status_code, 302)
        faz = ProcessoFazendaria.objects.get(pk=self.faz.pk)
        self.assertEqual(faz.situacao, SituacaoFazendaria.DISTRIBUICAO)
        self.assertIsNone(faz.procurador_id)

    def test_post_with_inactive_responsavel_does_not_update(self) -> None:
        from django.urls import reverse

        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria

        resp = self.client.post(
            reverse("core:distribuicao_pdf"),
            data={
                "responsavel": str(self.procurador_inativo.pk),
                "faz": [str(self.faz.pk)],
            },
        )

        self.assertEqual(resp.status_code, 302)
        faz = ProcessoFazendaria.objects.get(pk=self.faz.pk)
        self.assertEqual(faz.situacao, SituacaoFazendaria.DISTRIBUICAO)
        self.assertIsNone(faz.procurador_id)
