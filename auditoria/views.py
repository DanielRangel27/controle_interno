"""Read-only views to inspect the audit trail from inside the app."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.views.generic import ListView

from .models import AuditAction, AuditLog


class StaffRequiredMixin(UserPassesTestMixin):
    """Restrict access to staff users (admins) only."""

    raise_exception = False

    def test_func(self) -> bool:
        user = self.request.user  # type: ignore[attr-defined]
        return bool(user and user.is_authenticated and user.is_staff)


class AuditLogListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    template_name = "auditoria/auditlog_list.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self) -> QuerySet[AuditLog]:
        qs = AuditLog.objects.select_related("actor", "content_type").order_by(
            "-timestamp"
        )
        params = self.request.GET
        action = (params.get("acao") or "").strip()
        if action in {choice for choice, _ in AuditAction.choices}:
            qs = qs.filter(action=action)

        ctype_id = (params.get("modelo") or "").strip()
        if ctype_id.isdigit():
            qs = qs.filter(content_type_id=int(ctype_id))

        actor_id = (params.get("usuario") or "").strip()
        if actor_id.isdigit():
            qs = qs.filter(actor_id=int(actor_id))

        termo = (params.get("q") or "").strip()
        if termo:
            qs = qs.filter(object_repr__icontains=termo)
        return qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["acao_atual"] = self.request.GET.get("acao", "")
        ctx["modelo_atual"] = self.request.GET.get("modelo", "")
        ctx["usuario_atual"] = self.request.GET.get("usuario", "")
        ctx["termo_atual"] = self.request.GET.get("q", "")
        ctx["acoes"] = AuditAction.choices
        ctx["content_types"] = ContentType.objects.filter(
            audit_logs__isnull=False
        ).distinct().order_by("app_label", "model")
        return ctx
