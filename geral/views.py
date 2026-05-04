"""Class-based views for the geral module."""

from __future__ import annotations

import logging
from typing import Any

from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from core.exporters import export_csv, export_xlsx

from .forms import FiltroProcessoForm, ProcessoGeralForm
from .models import ProcessoGeral, SituacaoGeral
from .services import (
    ProcessoFilters,
    available_anos,
    export_columns,
    list_processos,
    situacao_counters,
)

logger = logging.getLogger(__name__)


class ProcessoListView(LoginRequiredMixin, ListView):
    template_name = "geral/processo_list.html"
    context_object_name = "processos"
    paginate_by = 25

    def get_queryset(self):
        filters = ProcessoFilters.from_querydict(self.request.GET)
        return list_processos(filters)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["filtro_form"] = FiltroProcessoForm(self.request.GET or None)
        counters = situacao_counters(self.get_queryset())
        ctx["counters_total"] = counters.get("total", 0)
        ctx["counters_list"] = [
            {"value": value, "label": label, "count": counters.get(value, 0)}
            for value, label in SituacaoGeral.choices
        ]
        ctx["situacoes"] = SituacaoGeral.choices
        ctx["anos"] = available_anos()
        ctx["query_string"] = self._query_string_without_page(prefix="&")
        ctx["export_query"] = self._query_string_without_page(prefix="?")
        return ctx

    def _query_string_without_page(self, prefix: str = "&") -> str:
        params = self.request.GET.copy()
        params.pop("page", None)
        encoded = params.urlencode()
        return f"{prefix}{encoded}" if encoded else ""


class ProcessoDetailView(LoginRequiredMixin, DetailView):
    model = ProcessoGeral
    template_name = "geral/processo_detail.html"
    context_object_name = "processo"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "responsavel",
                "responsavel_secundario",
                "assunto",
                "destino_saida",
                "criado_por",
            )
            .prefetch_related("tipos_parecer")
        )


class ProcessoCreateView(LoginRequiredMixin, CreateView):
    model = ProcessoGeral
    form_class = ProcessoGeralForm
    template_name = "geral/processo_form.html"
    success_url = reverse_lazy("geral:lista")

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        response = super().form_valid(form)
        logger.info(
            "geral process created",
            extra={
                "process_id": self.object.pk,
                "numero": self.object.numero_processo,
                "user_id": self.request.user.pk,
            },
        )
        messages.success(self.request, "Processo cadastrado com sucesso.")
        return response

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Novo processo"
        ctx["submit_label"] = "Cadastrar"
        return ctx


class ProcessoUpdateView(LoginRequiredMixin, UpdateView):
    model = ProcessoGeral
    form_class = ProcessoGeralForm
    template_name = "geral/processo_form.html"

    def get_success_url(self) -> str:
        return reverse_lazy("geral:detalhe", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info(
            "geral process updated",
            extra={"process_id": self.object.pk, "user_id": self.request.user.pk},
        )
        messages.success(self.request, "Processo atualizado.")
        return response

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = f"Editar {self.object.numero_processo}"
        ctx["submit_label"] = "Salvar alterações"
        return ctx


class ProcessoExportView(LoginRequiredMixin, View):
    """Stream the filtered queryset as CSV or XLSX."""

    def get(self, request: HttpRequest, formato: str) -> HttpResponse:
        filters = ProcessoFilters.from_querydict(request.GET)
        qs = list_processos(filters)
        filename = f"processos-geral-{date.today():%Y-%m-%d}"
        if formato == "csv":
            return export_csv(qs, export_columns(), filename)
        if formato == "xlsx":
            return export_xlsx(qs, export_columns(), filename, sheet_title="Geral")
        return HttpResponse(status=404)
