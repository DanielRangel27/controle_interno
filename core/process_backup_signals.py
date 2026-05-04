"""Automatic backup hooks for process model changes.

When enabled via ``BACKUP_GIT_AUTO_ON_PROCESS_CHANGE``, any create/update/delete
on ``ProcessoGeral`` or ``ProcessoFazendaria`` triggers ``manage.py backup_git``.
"""

from __future__ import annotations

import logging
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


def _run_backup(*, reason: str) -> None:
    if not _auto_backup_enabled():
        return
    try:
        call_command("backup_git")
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
