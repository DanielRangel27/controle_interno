"""Persistence layer for the audit trail.

We use a single ``AuditLog`` table generic over ``ContentType`` so the same
model serves every auditable business model without duplication. Field-level
``before``/``after`` snapshots are stored as JSON to enable diffs.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditAction(models.TextChoices):
    CREATE = "create", "Criação"
    UPDATE = "update", "Atualização"
    DELETE = "delete", "Exclusão"


class AuditLog(models.Model):
    """A single audited change on a business model instance."""

    action = models.CharField(
        "ação",
        max_length=16,
        choices=AuditAction.choices,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    actor_username = models.CharField(
        "usuário (snapshot)",
        max_length=150,
        blank=True,
        help_text=(
            "Username preservado mesmo quando o usuário é excluído ou anônimo."
        ),
    )

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="tipo do objeto",
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    object_id = models.CharField("ID do objeto", max_length=64)
    object_repr = models.CharField(
        "representação do objeto",
        max_length=255,
        blank=True,
    )
    content_object = GenericForeignKey("content_type", "object_id")

    before = models.JSONField("antes", default=dict, blank=True)
    after = models.JSONField("depois", default=dict, blank=True)
    changed_fields = models.JSONField("campos alterados", default=list, blank=True)

    timestamp = models.DateTimeField("data/hora", auto_now_add=True)
    ip_address = models.GenericIPAddressField("ip", null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["actor"]),
            models.Index(fields=["action"]),
            models.Index(fields=["-timestamp"]),
        ]

    def __str__(self) -> str:
        actor = self.actor_username or "system"
        label = self.get_action_display()
        return f"{label} de {self.content_type} #{self.object_id} por {actor}"
