"""Admin registration for AuditLog (read-only)."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "action",
        "content_type",
        "object_repr",
        "actor_username",
        "ip_address",
    )
    list_filter = ("action", "content_type", "actor")
    search_fields = ("object_repr", "actor_username", "object_id")
    date_hierarchy = "timestamp"
    readonly_fields = (
        "timestamp",
        "action",
        "actor",
        "actor_username",
        "content_type",
        "object_id",
        "object_repr",
        "before",
        "after",
        "changed_fields",
        "ip_address",
    )
    ordering = ("-timestamp",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return request.user.is_superuser
