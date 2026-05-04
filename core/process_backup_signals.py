"""Automatic backup hooks for process model changes.

When enabled via ``BACKUP_GIT_AUTO_ON_PROCESS_CHANGE``, any create/update/delete
on ``ProcessoGeral`` or ``ProcessoFazendaria`` triggers ``manage.py backup_git``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db.models import Model
from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)

PROCESS_MODELS: tuple[str, ...] = (
    "geral.ProcessoGeral",
    "fazendaria.ProcessoFazendaria",
)


def _auto_backup_enabled() -> bool:
    return bool(getattr(settings, "BACKUP_GIT_AUTO_ON_PROCESS_CHANGE", False))


def _cooldown_seconds() -> int:
    raw = getattr(settings, "BACKUP_GIT_AUTO_COOLDOWN_SECONDS", 120)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 120


def _cooldown_state_file() -> Path:
    default_path = Path(settings.BASE_DIR) / ".backup_auto_last_run"
    raw = getattr(settings, "BACKUP_GIT_AUTO_COOLDOWN_STATE_FILE", default_path)
    return Path(raw)


def _last_run_timestamp(path: Path) -> float | None:
    try:
        content = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError:
        return None
    if not content:
        return None
    try:
        return float(content)
    except ValueError:
        return None


def _update_last_run_timestamp(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(time.time()), encoding="utf-8")


def _should_skip_by_cooldown() -> bool:
    cooldown = _cooldown_seconds()
    if cooldown <= 0:
        return False
    state_file = _cooldown_state_file()
    last = _last_run_timestamp(state_file)
    if last is None:
        return False
    return (time.time() - last) < cooldown


def _run_backup(*, reason: str) -> None:
    if not _auto_backup_enabled():
        return
    if _should_skip_by_cooldown():
        logger.info("auto backup skipped by cooldown", extra={"reason": reason})
        return
    try:
        call_command("backup_git")
        _update_last_run_timestamp(_cooldown_state_file())
    except Exception:
        logger.exception("auto backup failed", extra={"reason": reason})


def _on_process_saved(
    sender: type[Model],
    instance: Model,
    created: bool,
    raw: bool = False,
    **kwargs: Any,
) -> None:
    if raw:
        return
    action = "create" if created else "update"
    reason = f"{sender._meta.label_lower}:{action}:{instance.pk}"
    _run_backup(reason=reason)


def _on_process_deleted(
    sender: type[Model],
    instance: Model,
    **kwargs: Any,
) -> None:
    reason = f"{sender._meta.label_lower}:delete:{instance.pk}"
    _run_backup(reason=reason)


def connect_process_backup_signals() -> None:
    for label in PROCESS_MODELS:
        try:
            model = apps.get_model(label)
        except LookupError:
            logger.warning("process model not found", extra={"label": label})
            continue
        if model is None:
            continue
        post_save.connect(
            _on_process_saved,
            sender=model,
            dispatch_uid=f"auto-backup-{label}-post-save",
        )
        post_delete.connect(
            _on_process_deleted,
            sender=model,
            dispatch_uid=f"auto-backup-{label}-post-delete",
        )
