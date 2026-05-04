"""Business services for the geral module."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

from django.db.models import Q, QuerySet

from .models import ProcessoGeral, SituacaoGeral

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessoFilters:
    busca: str = ""
    ano: int | None = None
    situacao: str = ""
    responsavel_id: int | None = None
    destino_id: int | None = None
    assunto_id: int | None = None
    tipo_parecer_id: int | None = None
    data_inicio: dt.date | None = None
    data_fim: dt.date | None = None

    @classmethod
    def from_querydict(cls, data: Any) -> "ProcessoFilters":
        def _int(name: str) -> int | None:
            value = (data.get(name) or "").strip()
            if not value:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def _date(name: str) -> dt.date | None:
            value = (data.get(name) or "").strip()
            if not value:
                return None
            try:
                return dt.date.fromisoformat(value)
            except ValueError:
                return None

        return cls(
            busca=(data.get("busca") or "").strip(),
            ano=_int("ano"),
            situacao=(data.get("situacao") or "").strip(),
            responsavel_id=_int("responsavel"),
            destino_id=_int("destino"),
            assunto_id=_int("assunto"),
            tipo_parecer_id=_int("tipo_parecer"),
            data_inicio=_date("data_inicio"),
            data_fim=_date("data_fim"),
        )


def base_queryset() -> QuerySet[ProcessoGeral]:
    return (
        ProcessoGeral.objects.all()
        .select_related(
            "responsavel",
            "responsavel_secundario",
            "assunto",
            "destino_saida",
            "criado_por",
        )
        .prefetch_related("tipos_parecer")
    )


def filter_processos(
    qs: QuerySet[ProcessoGeral], filters: ProcessoFilters
) -> QuerySet[ProcessoGeral]:
    if filters.busca:
        qs = qs.filter(
            Q(numero_processo__icontains=filters.busca)
            | Q(observacoes__icontains=filters.busca)
            | Q(apensos__icontains=filters.busca)
        )
    if filters.ano:
        qs = qs.filter(ano=filters.ano)
    if filters.situacao:
        qs = qs.filter(situacao=filters.situacao)
    if filters.responsavel_id:
        qs = qs.filter(
            Q(responsavel_id=filters.responsavel_id)
            | Q(responsavel_secundario_id=filters.responsavel_id)
        )
    if filters.destino_id:
        qs = qs.filter(destino_saida_id=filters.destino_id)
    if filters.assunto_id:
        qs = qs.filter(assunto_id=filters.assunto_id)
    if filters.tipo_parecer_id:
        qs = qs.filter(tipos_parecer__id=filters.tipo_parecer_id).distinct()
    if filters.data_inicio:
        qs = qs.filter(data_distribuicao__gte=filters.data_inicio)
    if filters.data_fim:
        qs = qs.filter(data_distribuicao__lte=filters.data_fim)
    return qs


def list_processos(filters: ProcessoFilters) -> QuerySet[ProcessoGeral]:
    return filter_processos(base_queryset(), filters)


def export_columns():
    """Columns used for CSV/XLSX exports of geral processes."""

    def _responsavel(p) -> str:
        if not p.responsavel and not p.responsavel_secundario:
            return ""
        if p.responsavel and p.responsavel_secundario:
            return f"{p.responsavel} / {p.responsavel_secundario}"
        return str(p.responsavel or p.responsavel_secundario)

    return [
        ("Número", lambda p: p.numero_processo),
        ("Ano", lambda p: p.ano),
        ("Data entrada", lambda p: p.data_entrada),
        ("Apensos", lambda p: p.apensos or ""),
        ("Distribuição", lambda p: p.data_distribuicao),
        ("Responsável", _responsavel),
        ("Assunto", lambda p: str(p.assunto) if p.assunto else ""),
        ("Observações", lambda p: p.observacoes or ""),
        ("Situação", lambda p: p.get_situacao_display()),
        ("Data saída", lambda p: p.data_saida),
        ("Destino saída", lambda p: str(p.destino_saida) if p.destino_saida else ""),
        ("Pareceres", lambda p: [tp.codigo for tp in p.tipos_parecer.all()]),
        ("Cadastrado por", lambda p: str(p.criado_por) if p.criado_por else ""),
        ("Cadastrado em", lambda p: p.criado_em),
    ]


def available_anos() -> list[int]:
    return list(
        ProcessoGeral.objects.values_list("ano", flat=True)
        .distinct()
        .order_by("-ano")
    )


def situacao_counters(qs: QuerySet[ProcessoGeral] | None = None) -> dict[str, int]:
    qs = qs if qs is not None else ProcessoGeral.objects.all()
    counts: dict[str, int] = {
        value: qs.filter(situacao=value).count() for value, _ in SituacaoGeral.choices
    }
    counts["total"] = qs.count()
    return counts
