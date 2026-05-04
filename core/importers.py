"""Pure parsing helpers used by the spreadsheet importers.

Functions here MUST NOT touch the database directly. They convert raw cell
values from the spreadsheets into normalized Python primitives, so that they
can be unit-tested without any Django setup overhead.

The patterns below were derived from real samples of the 2026 tabs of:
    - CONTROLE DE PA - PROCSEFOP 2021-22 (Recuperado) - Copia.xlsx (fazendaria)
    - 001 - Controle Interno de Processos copia.xlsm                (geral)
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Tipos de parecer (Despacho/Parecer/Parecer deferindo/Parecer indeferindo/Remessa)
# ---------------------------------------------------------------------------

TIPO_PARECER_CANONICOS: dict[str, str] = {
    "D": "Despacho",
    "P": "Parecer",
    "Pd": "Parecer deferindo",
    "Pi": "Parecer indeferindo",
    "R": "Remessa",
}

# Maps any free-form text to a canonical code. Matching is case-insensitive.
_PARECER_ALIASES: dict[str, str] = {
    "d": "D",
    "despacho": "D",
    "p": "P",
    "parecer": "P",
    "pd": "Pd",
    "parecer deferindo": "Pd",
    "parecer deferido": "Pd",
    "pi": "Pi",
    "parecer indeferindo": "Pi",
    "parecer indeferido": "Pi",
    "r": "R",
    "remessa": "R",
}


def parse_tipos_parecer(value: object) -> list[str]:
    """Parse a parecer cell into a list of canonical codes.

    Examples (real cells from the 2026 tabs)::

        "Despacho"            -> ["D"]
        "parecer"             -> ["P"]
        "Parecer deferindo"   -> ["Pd"]
        "Pd"                  -> ["Pd"]
        "PD"                  -> ["Pd"]
        "R / Pd"              -> ["R", "Pd"]
        "  "                  -> []
        None                  -> []
    """

    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []

    # Split on "/", ";" or "," to support combos like "R / Pd" or "R; Pd".
    parts = re.split(r"[/;,]", text)
    codes: list[str] = []
    for part in parts:
        key = part.strip().lower()
        if not key:
            continue
        canonical = _PARECER_ALIASES.get(key)
        if canonical and canonical not in codes:
            codes.append(canonical)
    return codes


# ---------------------------------------------------------------------------
# Numero do processo (e.g. "547/25", "3712/2025")
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumeroProcesso:
    numero: str
    ano: int


_NUMERO_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d{2,4})\s*$")


def parse_numero_processo(value: object) -> NumeroProcesso | None:
    """Parse a process number cell into number+ano.

    Examples::

        "547/25"      -> NumeroProcesso("547/25",  2025)
        "3712/2025"   -> NumeroProcesso("3712/2025", 2025)
        " 6353/21 "   -> NumeroProcesso("6353/21", 2021)
        "apenso"      -> None  (skip noise)
        "   "         -> None
    """

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    m = _NUMERO_RE.match(text)
    if not m:
        return None
    numero_raw = m.group(1)
    ano_raw = m.group(2)
    if len(ano_raw) == 2:
        # Assume 20XX for two-digit years (sheets cover 2017-2026).
        ano = 2000 + int(ano_raw)
    else:
        ano = int(ano_raw)
    if not (1900 <= ano <= 2100):
        return None
    return NumeroProcesso(numero=f"{numero_raw}/{ano_raw}", ano=ano)


# ---------------------------------------------------------------------------
# "DD/MM/YY[YY] - Nome"  (used in the Fazendaria sheet "Procurador" column)
# ---------------------------------------------------------------------------


_DATE_PREFIX_RE = re.compile(
    r"""^\s*
        (?P<day>\d{1,2})\s*/\s*(?P<month>\d{1,2})\s*/\s*(?P<year>\d{2,4})
        \s*[-\u2013\u2014:]?\s*    # optional separator (hyphen, en/em dash, colon)
        (?P<rest>.*)$
    """,
    re.VERBOSE,
)


def _to_date(day: int, month: int, year: int) -> dt.date | None:
    if year < 100:
        year += 2000
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


@dataclass(frozen=True)
class DataNome:
    data: dt.date | None
    nome: str


def parse_data_nome(value: object) -> DataNome | None:
    """Parse cells like ``"05/01/2026 - Dra. Eduarda B"`` into (date, name).

    Variations supported::

        "05/01/2026 - Dra. Eduarda B"  -> (2026-01-05, "Dra. Eduarda B")
        "27/01/26 - Dra. Eduarda B"    -> (2026-01-27, "Dra. Eduarda B")
        "Izabella"                     -> (None, "Izabella")
        ""                             -> None
        None                           -> None
    """

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    m = _DATE_PREFIX_RE.match(text)
    if not m:
        return DataNome(data=None, nome=text)
    data = _to_date(int(m.group("day")), int(m.group("month")), int(m.group("year")))
    nome = m.group("rest").strip(" -:\u2013\u2014\t")
    if not nome:
        return DataNome(data=data, nome="")
    return DataNome(data=data, nome=nome)


# ---------------------------------------------------------------------------
# Setor / data — two formats observed
# ---------------------------------------------------------------------------


_SETOR_DATA_FAZ_RE = re.compile(
    r"""^\s*
        (?P<setor>.+?)
        \s*[-\u2013\u2014]\s*
        (?P<day>\d{1,2})\s*/\s*(?P<month>\d{1,2})\s*/\s*(?P<year>\d{2,4})
        \s*$
    """,
    re.VERBOSE,
)

_DATA_SETOR_GERAL_RE = re.compile(
    r"""^\s*
        (?P<day>\d{1,2})\s*/\s*(?P<month>\d{1,2})\s*/\s*(?P<year>\d{2,4})
        \s*[-\u2013\u2014]\s*
        (?P<setor>.+?)
        \s*$
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class SetorData:
    setor: str
    data: dt.date | None


def parse_destino_fazendaria(value: object) -> SetorData | None:
    """Parse the fazendaria 'Destino' column: ``"divativa - 30/03/26"``.

    Tolerates Excel formats like ``"Secat-12/01/26"`` (no spaces around dash)
    and falls back to "no date" when only a sector name is present.
    """

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    m = _SETOR_DATA_FAZ_RE.match(text)
    if m:
        data = _to_date(
            int(m.group("day")), int(m.group("month")), int(m.group("year"))
        )
        setor = m.group("setor").strip()
        return SetorData(setor=setor, data=data)
    return SetorData(setor=text, data=None)


def parse_saida_geral(value: object) -> SetorData | None:
    """Parse the geral 'SAIDA' column: ``"06/01/2026 - Procsefop"``.

    Falls back to "no date" when only a sector name is present
    (e.g. ``"Segurança Pública"``).
    """

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    m = _DATA_SETOR_GERAL_RE.match(text)
    if m:
        data = _to_date(
            int(m.group("day")), int(m.group("month")), int(m.group("year"))
        )
        setor = m.group("setor").strip()
        return SetorData(setor=setor, data=data)
    return SetorData(setor=text, data=None)


# ---------------------------------------------------------------------------
# Situacao - normalize to choice values
# ---------------------------------------------------------------------------


_SITUACAO_FAZ: dict[str, str] = {
    "concluido": "concluido",
    "concluído": "concluido",
    "andamento": "andamento",
    "em andamento": "andamento",
    "remessa": "remessa",
    "no armario": "no_armario",
    "no armário": "no_armario",
    "no armarrio": "no_armario",
}


def parse_situacao_fazendaria(value: object) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    return _SITUACAO_FAZ.get(key)


_SITUACAO_GERAL: dict[str, str] = {
    "entregue": "entregue",
    "entregue no caderno": "caderno",
    "caderno": "caderno",
    "andamento": "andamento",
    "em andamento": "andamento",
    "analise": "analise",
    "análise": "analise",
    "em analise": "analise",
    "em análise": "analise",
    "concluido": "concluido",
    "concluído": "concluido",
}


def parse_situacao_geral(value: object) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    return _SITUACAO_GERAL.get(key)


# ---------------------------------------------------------------------------
# Apensos (geral)
# ---------------------------------------------------------------------------


def parse_apensos(value: object) -> str:
    """Normalize the 'APENSOS' cell. ``"-"`` becomes empty; otherwise trim."""

    if value is None:
        return ""
    text = str(value).strip()
    if text in {"-", "--", "—", "–"}:
        return ""
    return text


# ---------------------------------------------------------------------------
# Responsavel (geral): "Iely / Rodrigo" -> (primary, secondary)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResponsaveisGeral:
    principal: str
    secundario: str | None


def parse_responsaveis_geral(value: object) -> ResponsaveisGeral | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = [p.strip() for p in re.split(r"\s*/\s*", text) if p.strip()]
    if not parts:
        return None
    if len(parts) == 1:
        return ResponsaveisGeral(principal=parts[0], secundario=None)
    return ResponsaveisGeral(principal=parts[0], secundario=parts[1])


# ---------------------------------------------------------------------------
# Datas vindas do Excel (datetime, str, etc.)
# ---------------------------------------------------------------------------


def coerce_date(value: object) -> dt.date | None:
    """Normalize an Excel cell value to a ``date`` (or None)."""

    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    m = _DATE_PREFIX_RE.match(text)
    if m:
        return _to_date(
            int(m.group("day")), int(m.group("month")), int(m.group("year"))
        )
    # Try "YYYY-MM-DD"
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Row-level normalizers (one per spreadsheet)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FazendariaRow:
    numero: NumeroProcesso
    procurador_nome: str | None
    data_recebimento: dt.date | None
    assunto: str | None
    situacao: str | None
    destino_nome: str | None
    data_remessa: dt.date | None
    tipos_parecer: list[str] = field(default_factory=list)


def parse_fazendaria_row(row: tuple) -> FazendariaRow | None:
    """Convert a raw Fazendaria row (list of cell values) to a typed record.

    The 2026 tab has 14 raw columns due to merged cells; only 6 carry data:
        col1=numero, col2=proc+date, col5=assunto, col10=situacao,
        col12=destino+date, col13=parecer.
    """

    def col(idx: int) -> object:
        return row[idx] if idx < len(row) else None

    numero = parse_numero_processo(col(0))
    if numero is None:
        return None  # row is noise (apenso markers, blanks, etc.)

    proc = parse_data_nome(col(1))
    procurador_nome = proc.nome if proc and proc.nome else None
    data_recebimento = proc.data if proc else None

    assunto_raw = col(4)
    assunto = str(assunto_raw).strip() if assunto_raw else None

    destino = parse_destino_fazendaria(col(11))
    destino_nome = destino.setor if destino else None
    data_remessa = destino.data if destino else None

    return FazendariaRow(
        numero=numero,
        procurador_nome=procurador_nome,
        data_recebimento=data_recebimento,
        assunto=assunto if assunto else None,
        situacao=parse_situacao_fazendaria(col(9)),
        destino_nome=destino_nome,
        data_remessa=data_remessa,
        tipos_parecer=parse_tipos_parecer(col(12)),
    )


@dataclass(frozen=True)
class GeralRow:
    numero: NumeroProcesso
    data_entrada: dt.date | None
    apensos: str
    data_distribuicao: dt.date | None
    responsavel_nome: str | None
    responsavel_secundario_nome: str | None
    assunto: str | None
    situacao: str | None
    data_saida: dt.date | None
    destino_saida_nome: str | None
    tipos_parecer: list[str] = field(default_factory=list)


def parse_geral_row(row: tuple) -> GeralRow | None:
    """Convert a raw Geral row (9 columns, no merged cells) to a typed record."""

    def col(idx: int) -> object:
        return row[idx] if idx < len(row) else None

    numero = parse_numero_processo(col(0))
    if numero is None:
        return None

    responsaveis = parse_responsaveis_geral(col(4))
    saida = parse_saida_geral(col(7))
    assunto_raw = col(5)
    assunto = str(assunto_raw).strip() if assunto_raw else None

    return GeralRow(
        numero=numero,
        data_entrada=coerce_date(col(1)),
        apensos=parse_apensos(col(2)),
        data_distribuicao=coerce_date(col(3)),
        responsavel_nome=responsaveis.principal if responsaveis else None,
        responsavel_secundario_nome=responsaveis.secundario if responsaveis else None,
        assunto=assunto if assunto else None,
        situacao=parse_situacao_geral(col(6)),
        data_saida=saida.data if saida else None,
        destino_saida_nome=saida.setor if saida else None,
        tipos_parecer=parse_tipos_parecer(col(8)),
    )
