"""Business services for the fazendaria module.

Keeps query/filter logic out of views so it can be reused and tested.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

from django.db.models import Q, QuerySet

from .models import ProcessoFazendaria, SituacaoFazendaria

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessoFilters:
    """Strongly typed filter input for the listing screen."""

    busca: str = ""
    ano: int | None = None
    situacao: str = ""
    procurador_id: int | None = None
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
            procurador_id=_int("procurador"),
            destino_id=_int("destino"),
            assunto_id=_int("assunto"),
            tipo_parecer_id=_int("tipo_parecer"),
            data_inicio=_date("data_inicio"),
            data_fim=_date("data_fim"),
        )


def base_queryset() -> QuerySet[ProcessoFazendaria]:
    return (
        ProcessoFazendaria.objects.all()
        .select_related("procurador", "assunto", "destino", "criado_por")
        .prefetch_related("tipos_parecer")
    )


def filter_processos(
    qs: QuerySet[ProcessoFazendaria], filters: ProcessoFilters
) -> QuerySet[ProcessoFazendaria]:
    if filters.busca:
        qs = qs.filter(
            Q(numero_processo__icontains=filters.busca)
            | Q(observacoes__icontains=filters.busca)
        )
    if filters.ano:
        qs = qs.filter(ano=filters.ano)
    if filters.situacao:
        qs = qs.filter(situacao=filters.situacao)
    if filters.procurador_id:
        qs = qs.filter(procurador_id=filters.procurador_id)
    if filters.destino_id:
        qs = qs.filter(destino_id=filters.destino_id)
    if filters.assunto_id:
        qs = qs.filter(assunto_id=filters.assunto_id)
    if filters.tipo_parecer_id:
        qs = qs.filter(tipos_parecer__id=filters.tipo_parecer_id).distinct()
    if filters.data_inicio:
        qs = qs.filter(data_recebimento__gte=filters.data_inicio)
    if filters.data_fim:
        qs = qs.filter(data_recebimento__lte=filters.data_fim)
    return qs


def list_processos(filters: ProcessoFilters) -> QuerySet[ProcessoFazendaria]:
    return filter_processos(base_queryset(), filters)


def export_columns():
    """Columns used for CSV/XLSX exports of fazendaria processes."""

    return [
        ("Número", lambda p: p.numero_processo),
        ("Ano", lambda p: p.ano),
        ("Procurador", lambda p: str(p.procurador) if p.procurador else ""),
        ("Recebimento", lambda p: p.data_recebimento),
        ("Assunto", lambda p: str(p.assunto) if p.assunto else ""),
        ("Observações", lambda p: p.observacoes or ""),
        ("Situação", lambda p: p.get_situacao_display()),
        ("Destino", lambda p: str(p.destino) if p.destino else ""),
        ("Data remessa", lambda p: p.data_remessa),
        (
            "Pareceres",
            lambda p: [tp.codigo for tp in p.tipos_parecer.all()],
        ),
        ("Cadastrado por", lambda p: str(p.criado_por) if p.criado_por else ""),
        ("Cadastrado em", lambda p: p.criado_em),
    ]


def available_anos() -> list[int]:
    """Anos com processos cadastrados, ordenados do mais recente ao mais antigo."""

    return list(
        ProcessoFazendaria.objects.values_list("ano", flat=True)
        .distinct()
        .order_by("-ano")
    )


def situacao_counters(
    qs: QuerySet[ProcessoFazendaria] | None = None,
) -> dict[str, int]:
    """Return a mapping {situacao: count} plus a 'total' key for the listing."""

    qs = qs if qs is not None else ProcessoFazendaria.objects.all()
    counts: dict[str, int] = {
        value: qs.filter(situacao=value).count() for value, _ in SituacaoFazendaria.choices
    }
    counts["total"] = qs.count()
    return counts
