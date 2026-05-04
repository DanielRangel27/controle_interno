"""Views for the core app."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import TemplateView, View

from .context_processors import THEME_COOKIE, VALID_THEMES
from .services import (
    fazendaria_report,
    geral_report,
    get_dashboard_summaries,
    get_recent_processes,
    global_search,
)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["summaries"] = get_dashboard_summaries()
        ctx["recent"] = get_recent_processes(limit=8)
        return ctx


class RelatorioFazendariaView(LoginRequiredMixin, TemplateView):
    template_name = "core/relatorio.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["report"] = fazendaria_report()
        return ctx


class RelatorioGeralView(LoginRequiredMixin, TemplateView):
    template_name = "core/relatorio.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["report"] = geral_report()
        return ctx


class BuscaGlobalView(LoginRequiredMixin, TemplateView):
    template_name = "core/busca.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        termo = (self.request.GET.get("q") or "").strip()
        ctx["termo"] = termo
        ctx["resultados"] = global_search(termo) if termo else []
        return ctx


class ToggleThemeView(View):
    """Persist the theme choice in a cookie and redirect back."""

    def post(self, request: HttpRequest) -> HttpResponse:
        choice = request.POST.get("theme", "auto")
        if choice not in VALID_THEMES:
            choice = "auto"

        next_url = request.POST.get("next") or request.headers.get("Referer") or reverse(
            "core:dashboard"
        )
        response = HttpResponseRedirect(next_url)
        response.set_cookie(
            THEME_COOKIE,
            choice,
            max_age=60 * 60 * 24 * 365,
            samesite="Lax",
        )
        return response
