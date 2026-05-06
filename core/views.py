"""Views for the core app."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import TemplateView, View

from core.models import Procurador, Modulo
from fazendaria.models import ProcessoFazendaria
from geral.models import ProcessoGeral

from .context_processors import THEME_COOKIE, VALID_THEMES
from .pdf_distribuicao import gerar_pdf_distribuicao
from .services import (
    fazendaria_report,
    geral_report,
    get_dashboard_summaries,
    get_recent_processes,
    global_search,
)

logger = logging.getLogger(__name__)


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


class DistribuicaoView(LoginRequiredMixin, TemplateView):
    """Page where the user selects processes and a responsible person to generate a PDF."""

    template_name = "core/distribuicao.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)

        # Processos fazendários
        ctx["processos_fazendaria"] = (
            ProcessoFazendaria.objects.select_related("procurador")
            .filter(situacao="distribuicao")
            .order_by("-ano", "numero_processo")
        )

        # Processos gerais
        ctx["processos_geral"] = (
            ProcessoGeral.objects.select_related("responsavel")
            .filter(situacao="distribuicao")
            .order_by("-ano", "numero_processo")
        )

        # Procuradores ativos (ambos os módulos)
        ctx["procuradores"] = Procurador.objects.filter(ativo=True).order_by("nome")

        return ctx


class DistribuicaoPDFView(LoginRequiredMixin, View):
    """Generate a PDF for the selected processes and responsible person."""

    def post(self, request: HttpRequest) -> HttpResponse:
        responsavel = request.POST.get("responsavel", "").strip()
        if not responsavel:
            from django.contrib import messages
            messages.error(request, "Selecione um responsável.")
            return HttpResponseRedirect(reverse("core:distribuicao"))

        # Collect selected fazendaria process IDs
        faz_ids = request.POST.getlist("faz")
        # Collect selected geral process IDs
        ger_ids = request.POST.getlist("ger")

        if not faz_ids and not ger_ids:
            from django.contrib import messages
            messages.error(request, "Selecione pelo menos um processo.")
            return HttpResponseRedirect(reverse("core:distribuicao"))

        processos_data = []

        if faz_ids:
            faz_qs = ProcessoFazendaria.objects.filter(pk__in=faz_ids)
            for p in faz_qs:
                processos_data.append({
                    "numero_processo": p.numero_processo,
                    "ano": p.ano,
                    "modulo": "Fazendária",
                })

        if ger_ids:
            ger_qs = ProcessoGeral.objects.filter(pk__in=ger_ids)
            for p in ger_qs:
                processos_data.append({
                    "numero_processo": p.numero_processo,
                    "ano": p.ano,
                    "modulo": "Geral",
                })

        buf = gerar_pdf_distribuicao(
            processos=processos_data,
            responsavel=responsavel,
        )

        filename = "distribuicao_processos.pdf"
        response = HttpResponse(buf.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        logger.info(
            "distribuicao PDF generated",
            extra={
                "user_id": request.user.pk,
                "responsavel": responsavel,
                "faz_count": len(faz_ids),
                "ger_count": len(ger_ids),
            },
        )
        return response
