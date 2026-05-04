"""Signal handlers that persist audit log entries.

Auditable models are declared in :data:`AUDITABLE_MODELS` (label form
``"app_label.ModelName"``). For each one we connect:

* ``pre_save``  – capture the previous DB row so we can produce a per-field
  diff on update events.
* ``post_save`` – persist a CREATE or UPDATE log entry.
* ``post_delete`` – persist a DELETE log entry with the last known state.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save

from .middleware import get_current_actor, get_current_ip

logger = logging.getLogger(__name__)


# Business models that should emit an audit trail. Keep this list explicit so
# infrastructure tables (sessions, contenttypes, etc.) do not pollute the log.
AUDITABLE_MODELS: tuple[str, ...] = (
    "core.Procurador",
    "core.Setor",
    "core.Assunto",
    "core.TipoParecer",
    "geral.ProcessoGeral",
    "fazendaria.ProcessoFazendaria",
)


_PRE_SAVE_SNAPSHOT_ATTR = "_audit_previous_snapshot"


def _serialize_value(value: Any) -> Any:
    """Convert a model field value to something JSON friendly."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, models.Model):
        return value.pk
    return str(value)


def _auto_managed_fields(model: type[models.Model]) -> set[str]:
    """Return field names whose values are managed automatically by Django.

    These fields (``auto_now``, ``auto_now_add``) change on every save even
    when nothing meaningful changed, so we exclude them from the update diff.
    """

    auto: set[str] = set()
    for field in model._meta.concrete_fields:
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            auto.add(field.name)
    return auto


def _instance_snapshot(instance: models.Model) -> dict[str, Any]:
    """Snapshot the concrete (non-M2M) fields of ``instance`` as JSON-safe dict."""

    snapshot: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        try:
            value = getattr(instance, field.attname, None)
        except Exception:  # pragma: no cover - defensive
            value = None
        snapshot[field.name] = _serialize_value(value)
    return snapshot


def _diff(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    ignore: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Return ``(before_changed, after_changed, changed_fields)`` for two snapshots."""

    ignore = ignore or set()
    changed: list[str] = []
    before_changed: dict[str, Any] = {}
    after_changed: dict[str, Any] = {}
    keys = (set(before) | set(after)) - ignore
    for key in keys:
        if before.get(key) != after.get(key):
            changed.append(key)
            before_changed[key] = before.get(key)
            after_changed[key] = after.get(key)
    return before_changed, after_changed, sorted(changed)


def _build_audit_log_entry(
    *,
    instance: models.Model,
    action: str,
    before: dict[str, Any],
    after: dict[str, Any],
    changed_fields: list[str],
):
    from .models import AuditLog

    actor = get_current_actor()
    ip = get_current_ip()
    return AuditLog(
        action=action,
        actor=actor,
        actor_username=getattr(actor, "username", "") if actor else "",
        content_type=ContentType.objects.get_for_model(instance.__class__),
        object_id=str(instance.pk) if instance.pk is not None else "",
        object_repr=str(instance)[:255],
        before=before,
        after=after,
        changed_fields=changed_fields,
        ip_address=ip,
    )


def _on_pre_save(sender: type[models.Model], instance: models.Model, **kwargs: Any) -> None:
    if not instance.pk:
        setattr(instance, _PRE_SAVE_SNAPSHOT_ATTR, None)
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        setattr(instance, _PRE_SAVE_SNAPSHOT_ATTR, None)
        return
    setattr(instance, _PRE_SAVE_SNAPSHOT_ATTR, _instance_snapshot(previous))


def _on_post_save(
    sender: type[models.Model],
    instance: models.Model,
    created: bool,
    **kwargs: Any,
) -> None:
    after = _instance_snapshot(instance)
    if created:
        entry = _build_audit_log_entry(
            instance=instance,
            action="create",
            before={},
            after=after,
            changed_fields=sorted(after.keys()),
        )
        entry.save()
        return

    previous: dict[str, Any] | None = getattr(instance, _PRE_SAVE_SNAPSHOT_ATTR, None)
    if previous is None:
        return
    before_changed, after_changed, changed = _diff(
        previous, after, ignore=_auto_managed_fields(sender)
    )
    if not changed:
        return
    entry = _build_audit_log_entry(
        instance=instance,
        action="update",
        before=before_changed,
        after=after_changed,
        changed_fields=changed,
    )
    entry.save()


def _on_post_delete(sender: type[models.Model], instance: models.Model, **kwargs: Any) -> None:
    snapshot = _instance_snapshot(instance)
    entry = _build_audit_log_entry(
        instance=instance,
        action="delete",
        before=snapshot,
        after={},
        changed_fields=sorted(snapshot.keys()),
    )
    entry.save()


def connect_auditable_signals() -> None:
    """Connect pre/post save and post delete signals for every audited model."""

    for label in AUDITABLE_MODELS:
        try:
            model = apps.get_model(label)
        except LookupError:
            logger.warning("audit model not found", extra={"label": label})
            continue
        if model is None:
            continue
        dispatch_uid = f"auditoria-{label}"
        pre_save.connect(_on_pre_save, sender=model, dispatch_uid=f"{dispatch_uid}-pre")
        post_save.connect(_on_post_save, sender=model, dispatch_uid=f"{dispatch_uid}-post")
        post_delete.connect(
            _on_post_delete, sender=model, dispatch_uid=f"{dispatch_uid}-del"
        )
