"""Business services for the core app.

Holds the dashboard aggregations and the global cross-module search.
Imports of fazendaria/geral models are local to keep this module
importable even before those apps are migrated.
"""

from __future__ import annotations

import calendar
import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModuleSummary:
    label: str
    slug: str
    total: int
    em_andamento: int
    concluidos: int
    list_url_name: str
    create_url_name: str
    relatorio_url_name: str | None = None


@dataclass(frozen=True)
class TopItem:
    label: str
    count: int


@dataclass(frozen=True)
class MonthBucket:
    """A single bar of the 'processos por mês' chart."""

    label: str  # "jan/26"
    iso: str  # "2026-01"
    count: int


@dataclass(frozen=True)
class CounterItem:
    label: str
    value: int
    css_modifier: str = ""  # e.g. "info", "success", "warning"


@dataclass(frozen=True)
class ModuleReport:
    """Rich report rendered on the dashboard and on the /relatorios/ page."""

    label: str
    slug: str
    total: int
    counters: list[CounterItem]
    top_procuradores: list[TopItem]
    top_setores: list[TopItem]
    top_assuntos: list[TopItem]
    top_pareceres: list[TopItem]
    monthly: list[MonthBucket]
    monthly_max: int
    list_url_name: str
    create_url_name: str
    export_csv_url_name: str
    export_xlsx_url_name: str


def _safe_count(callable_):
    try:
        return callable_()
    except Exception:
        logger.warning("count failed", exc_info=True)
        return 0


# ---------------------------------------------------------------------------
# Dashboard summary cards (lightweight)
# ---------------------------------------------------------------------------


def get_dashboard_summaries() -> list[ModuleSummary]:
    summaries: list[ModuleSummary] = []

    try:
        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria
    except Exception:  # pragma: no cover - defensive during migrations
        ProcessoFazendaria = None
        SituacaoFazendaria = None

    try:
        from geral.models import ProcessoGeral, SituacaoGeral
    except Exception:  # pragma: no cover
        ProcessoGeral = None
        SituacaoGeral = None

    if ProcessoFazendaria is not None and SituacaoFazendaria is not None:
        qs = ProcessoFazendaria.objects.all()
        summaries.append(
            ModuleSummary(
                label="Procuradoria Fazendária",
                slug="fazendaria",
                total=_safe_count(qs.count),
                em_andamento=_safe_count(
                    qs.filter(situacao=SituacaoFazendaria.ANDAMENTO).count
                ),
                concluidos=_safe_count(
                    qs.filter(situacao=SituacaoFazendaria.CONCLUIDO).count
                ),
                list_url_name="fazendaria:lista",
                create_url_name="fazendaria:criar",
                relatorio_url_name="core:relatorio_fazendaria",
            )
        )
    else:
        summaries.append(
            ModuleSummary(
                label="Procuradoria Fazendária",
                slug="fazendaria",
                total=0,
                em_andamento=0,
                concluidos=0,
                list_url_name="fazendaria:lista",
                create_url_name="fazendaria:criar",
            )
        )

    if ProcessoGeral is not None and SituacaoGeral is not None:
        qs = ProcessoGeral.objects.all()
        summaries.append(
            ModuleSummary(
                label="Procuradoria Geral",
                slug="geral",
                total=_safe_count(qs.count),
                em_andamento=_safe_count(
                    qs.filter(situacao=SituacaoGeral.ANDAMENTO).count
                ),
                concluidos=_safe_count(
                    qs.filter(situacao=SituacaoGeral.ENTREGUE).count
                ),
                list_url_name="geral:lista",
                create_url_name="geral:criar",
                relatorio_url_name="core:relatorio_geral",
            )
        )
    else:
        summaries.append(
            ModuleSummary(
                label="Procuradoria Geral",
                slug="geral",
                total=0,
                em_andamento=0,
                concluidos=0,
                list_url_name="geral:lista",
                create_url_name="geral:criar",
            )
        )

    return summaries


# ---------------------------------------------------------------------------
# Generic top-N + monthly histogram helpers (work on any QuerySet)
# ---------------------------------------------------------------------------


PT_MONTH_ABBR = [
    "",  # 1-indexed
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]


def _top_items(qs, field_name: str, limit: int = 5) -> list[TopItem]:
    from django.db.models import Count

    rows = (
        qs.exclude(**{f"{field_name}__isnull": True})
        .values(field_name)
        .annotate(n=Count("id"))
        .order_by("-n")[:limit]
    )
    items: list[TopItem] = []
    for row in rows:
        # row[field_name] is the FK id; resolve to a display label below.
        items.append(TopItem(label=str(row[field_name]), count=row["n"]))
    return items


def _top_related(
    qs, fk_field: str, attr_for_label: str = "nome", limit: int = 5
) -> list[TopItem]:
    """Top-N rows grouped by a foreign key, materializing the label."""

    from django.db.models import Count

    rows = (
        qs.exclude(**{f"{fk_field}__isnull": True})
        .values(f"{fk_field}__{attr_for_label}")
        .annotate(n=Count("id"))
        .order_by("-n")[:limit]
    )
    return [
        TopItem(label=str(row[f"{fk_field}__{attr_for_label}"]), count=row["n"])
        for row in rows
    ]


def _top_pareceres(qs, limit: int = 5) -> list[TopItem]:
    from django.db.models import Count

    rows = (
        qs.exclude(tipos_parecer__isnull=True)
        .values("tipos_parecer__nome", "tipos_parecer__codigo")
        .annotate(n=Count("id"))
        .order_by("-n")[:limit]
    )
    return [
        TopItem(
            label=f"{row['tipos_parecer__codigo']} - {row['tipos_parecer__nome']}",
            count=row["n"],
        )
        for row in rows
    ]


def _monthly_histogram(qs, date_field: str, months: int = 12) -> list[MonthBucket]:
    """Bucketize ``qs`` by ``date_field`` over the last ``months`` months."""

    today = dt.date.today()
    # Align to the first day of the current month, walk backwards.
    cursor = dt.date(today.year, today.month, 1)
    buckets: list[MonthBucket] = []
    pairs: list[tuple[int, int]] = []
    for _ in range(months):
        pairs.append((cursor.year, cursor.month))
        # walk to first day of previous month
        prev_year = cursor.year - 1 if cursor.month == 1 else cursor.year
        prev_month = 12 if cursor.month == 1 else cursor.month - 1
        cursor = dt.date(prev_year, prev_month, 1)
    pairs.reverse()  # oldest first

    for year, month in pairs:
        last_day = calendar.monthrange(year, month)[1]
        start = dt.date(year, month, 1)
        end = dt.date(year, month, last_day)
        count = qs.filter(
            **{f"{date_field}__gte": start, f"{date_field}__lte": end}
        ).count()
        buckets.append(
            MonthBucket(
                label=f"{PT_MONTH_ABBR[month]}/{str(year)[-2:]}",
                iso=f"{year:04d}-{month:02d}",
                count=count,
            )
        )
    return buckets


# ---------------------------------------------------------------------------
# Per-module rich reports
# ---------------------------------------------------------------------------


_FAZ_MODIFIERS = {
    "andamento": "info",
    "concluido": "success",
    "aguardando": "warning",
    "pendente": "warning",
}

_GERAL_MODIFIERS = {
    "andamento": "info",
    "entregue": "success",
    "aguardando": "warning",
    "devolvido": "danger",
}


def _build_counters(qs, choices, modifiers: dict[str, str]) -> list[CounterItem]:
    out: list[CounterItem] = []
    for value, label in choices:
        out.append(
            CounterItem(
                label=label,
                value=qs.filter(situacao=value).count(),
                css_modifier=modifiers.get(value, ""),
            )
        )
    return out


def fazendaria_report() -> ModuleReport | None:
    try:
        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria
    except Exception:  # pragma: no cover
        return None

    qs = ProcessoFazendaria.objects.all()
    monthly = _monthly_histogram(qs, "data_recebimento")
    return ModuleReport(
        label="Procuradoria Fazendária",
        slug="fazendaria",
        total=qs.count(),
        counters=_build_counters(qs, SituacaoFazendaria.choices, _FAZ_MODIFIERS),
        top_procuradores=_top_related(qs, "procurador"),
        top_setores=_top_related(qs, "destino"),
        top_assuntos=_top_related(qs, "assunto"),
        top_pareceres=_top_pareceres(qs),
        monthly=monthly,
        monthly_max=max((b.count for b in monthly), default=0),
        list_url_name="fazendaria:lista",
        create_url_name="fazendaria:criar",
        export_csv_url_name="fazendaria:exportar",
        export_xlsx_url_name="fazendaria:exportar",
    )


def geral_report() -> ModuleReport | None:
    try:
        from geral.models import ProcessoGeral, SituacaoGeral
    except Exception:  # pragma: no cover
        return None

    qs = ProcessoGeral.objects.all()
    monthly = _monthly_histogram(qs, "data_distribuicao")
    return ModuleReport(
        label="Procuradoria Geral",
        slug="geral",
        total=qs.count(),
        counters=_build_counters(qs, SituacaoGeral.choices, _GERAL_MODIFIERS),
        top_procuradores=_top_related(qs, "responsavel"),
        top_setores=_top_related(qs, "destino_saida"),
        top_assuntos=_top_related(qs, "assunto"),
        top_pareceres=_top_pareceres(qs),
        monthly=monthly,
        monthly_max=max((b.count for b in monthly), default=0),
        list_url_name="geral:lista",
        create_url_name="geral:criar",
        export_csv_url_name="geral:exportar",
        export_xlsx_url_name="geral:exportar",
    )


# ---------------------------------------------------------------------------
# Recent activity (for the dashboard)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecentProcess:
    modulo: str
    label: str
    numero: str
    ano: int
    data: dt.date | None
    detail_url_name: str
    pk: int


def get_recent_processes(limit: int = 8) -> list[RecentProcess]:
    """Return the latest processes from both modules, sorted by creation time."""

    items: list[RecentProcess] = []
    try:
        from fazendaria.models import ProcessoFazendaria

        for p in (
            ProcessoFazendaria.objects.all()
            .order_by("-criado_em")[:limit]
        ):
            items.append(
                RecentProcess(
                    modulo="Fazendária",
                    label=str(p.assunto) if p.assunto else "—",
                    numero=p.numero_processo,
                    ano=p.ano,
                    data=p.data_recebimento or p.criado_em.date(),
                    detail_url_name="fazendaria:detalhe",
                    pk=p.pk,
                )
            )
    except Exception:  # pragma: no cover
        pass

    try:
        from geral.models import ProcessoGeral

        for p in (
            ProcessoGeral.objects.all()
            .order_by("-criado_em")[:limit]
        ):
            items.append(
                RecentProcess(
                    modulo="Geral",
                    label=str(p.assunto) if p.assunto else "—",
                    numero=p.numero_processo,
                    ano=p.ano,
                    data=p.data_distribuicao or p.criado_em.date(),
                    detail_url_name="geral:detalhe",
                    pk=p.pk,
                )
            )
    except Exception:  # pragma: no cover
        pass

    items.sort(key=lambda i: i.data or dt.date.min, reverse=True)
    return items[:limit]


# ---------------------------------------------------------------------------
# Global search (cross-module)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchHit:
    modulo: str
    numero: str
    ano: int
    assunto: str
    situacao_display: str
    detail_url_name: str
    pk: int


def global_search(termo: str, limit_per_module: int = 25) -> list[SearchHit]:
    """Search by process number / observação across both modules."""

    termo = (termo or "").strip()
    hits: list[SearchHit] = []
    if not termo:
        return hits

    try:
        from fazendaria.models import ProcessoFazendaria
        from django.db.models import Q

        qs = (
            ProcessoFazendaria.objects.filter(
                Q(numero_processo__icontains=termo)
                | Q(observacoes__icontains=termo)
            )
            .select_related("assunto")[:limit_per_module]
        )
        for p in qs:
            hits.append(
                SearchHit(
                    modulo="Fazendária",
                    numero=p.numero_processo,
                    ano=p.ano,
                    assunto=str(p.assunto) if p.assunto else "—",
                    situacao_display=p.get_situacao_display(),
                    detail_url_name="fazendaria:detalhe",
                    pk=p.pk,
                )
            )
    except Exception:  # pragma: no cover
        pass

    try:
        from geral.models import ProcessoGeral
        from django.db.models import Q

        qs = (
            ProcessoGeral.objects.filter(
                Q(numero_processo__icontains=termo)
                | Q(observacoes__icontains=termo)
                | Q(apensos__icontains=termo)
            )
            .select_related("assunto")[:limit_per_module]
        )
        for p in qs:
            hits.append(
                SearchHit(
                    modulo="Geral",
                    numero=p.numero_processo,
                    ano=p.ano,
                    assunto=str(p.assunto) if p.assunto else "—",
                    situacao_display=p.get_situacao_display(),
                    detail_url_name="geral:detalhe",
                    pk=p.pk,
                )
            )
    except Exception:  # pragma: no cover
        pass

    return hits
