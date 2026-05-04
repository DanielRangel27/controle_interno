"""Admin customizations for the accounts module.

Adds a bulk action to approve pending users (sets ``is_active=True``) on the
default ``UserAdmin`` from ``django.contrib.auth``.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db.models import QuerySet
from django.http import HttpRequest

logger = logging.getLogger(__name__)

User = get_user_model()


@admin.action(description="Aprovar cadastros selecionados (ativar usuários)")
def approve_pending_users(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet[Any],
) -> None:
    pending = queryset.filter(is_active=False)
    count = pending.update(is_active=True)
    for user in pending:
        logger.info(
            "user approved",
            extra={
                "user_id": user.pk,
                "username": user.get_username(),
                "approved_by_id": request.user.pk,
            },
        )
    messages.success(request, f"{count} usuário(s) aprovado(s) e ativado(s).")


class PendingUserFilter(admin.SimpleListFilter):
    title = "aprovação"
    parameter_name = "aprovacao"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin):
        return (
            ("pendentes", "Pendentes (inativos)"),
            ("ativos", "Ativos"),
        )

    def queryset(self, request: HttpRequest, queryset: QuerySet[Any]):
        if self.value() == "pendentes":
            return queryset.filter(is_active=False)
        if self.value() == "ativos":
            return queryset.filter(is_active=True)
        return queryset


class CustomUserAdmin(UserAdmin):
    actions = (*UserAdmin.actions, approve_pending_users)
    list_filter = (PendingUserFilter, *UserAdmin.list_filter)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "date_joined",
    )


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
