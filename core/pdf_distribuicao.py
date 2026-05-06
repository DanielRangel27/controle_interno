"""PDF generation for the 'Distribuição de Processos' document.

Uses ReportLab to build a formal PDF containing:
- List of selected processes (number and year)
- Date when the document was generated
- Name of the responsible person (procurador)
- Signature and date lines
"""

from __future__ import annotations

import io
from datetime import date
from typing import Sequence

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas


# ── Portuguese month names ──────────────────────────────────────────────
_MESES = [
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _data_por_extenso(d: date) -> str:
    """Return the date in long-form Portuguese, e.g. '06 de maio de 2026'."""
    return f"{d.day:02d} de {_MESES[d.month]} de {d.year}"


def gerar_pdf_distribuicao(
    processos: Sequence[dict],
    responsavel: str,
    data_geracao: date | None = None,
) -> io.BytesIO:
    """Build a PDF for process distribution and return it as a BytesIO buffer.

    Parameters
    ----------
    processos:
        List of dicts, each with keys ``numero_processo``, ``ano``, and
        ``modulo`` (e.g. "Fazendária" or "Geral").
    responsavel:
        Full name of the person responsible (procurador).
    data_geracao:
        Date shown on the document; defaults to today.
    """
    if data_geracao is None:
        data_geracao = date.today()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # ── margins ──────────────────────────────────────────────────────
    left = 3 * cm
    right = width - 3 * cm
    usable = right - left
    center_x = width / 2

    y = height - 4 * cm  # starting Y

    # ── Header / Title ───────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(center_x, y, "PROCURADORIA-GERAL DO MUNICÍPIO")
    y -= 0.8 * cm

    c.setFont("Helvetica", 12)
    c.drawCentredString(center_x, y, "Controle Interno de Processos")
    y -= 1.5 * cm

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(center_x, y, "DISTRIBUIÇÃO DE PROCESSOS")
    y -= 2 * cm

    # ── Horizontal rule ──────────────────────────────────────────────
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.setLineWidth(0.8)
    c.line(left, y, right, y)
    y -= 1.2 * cm

    # ── Date & Responsible ───────────────────────────────────────────
    c.setFont("Helvetica", 12)
    c.drawString(left, y, f"Data de emissão:  {_data_por_extenso(data_geracao)}")
    y -= 0.7 * cm

    c.drawString(left, y, f"Responsável:  {responsavel}")
    y -= 1.2 * cm

    # ── Table header ─────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 11)
    col_num_x = left
    col_ano_x = left + 8 * cm
    col_mod_x = left + 11 * cm

    c.drawString(col_num_x, y, "Nº Processo")
    c.drawString(col_ano_x, y, "Ano")
    c.drawString(col_mod_x, y, "Módulo")
    y -= 0.15 * cm
    c.setLineWidth(0.5)
    c.line(left, y, right, y)
    y -= 0.5 * cm

    # ── Process rows ─────────────────────────────────────────────────
    c.setFont("Helvetica", 11)
    for proc in processos:
        if y < 6 * cm:
            c.showPage()
            y = height - 3 * cm
            c.setFont("Helvetica", 11)

        c.drawString(col_num_x, y, str(proc["numero_processo"]))
        c.drawString(col_ano_x, y, str(proc["ano"]))
        c.drawString(col_mod_x, y, str(proc.get("modulo", "")))
        y -= 0.55 * cm

    y -= 0.5 * cm
    c.setLineWidth(0.5)
    c.line(left, y, right, y)
    y -= 1.5 * cm

    # ── Body text ────────────────────────────────────────────────────
    c.setFont("Helvetica", 11)
    qtd = len(processos)
    plural = "s" if qtd > 1 else ""
    body = (
        f"Certifico que o{plural} {qtd} processo{plural} administrativo{plural} "
        f"listado{plural} acima {'foram distribuídos' if qtd > 1 else 'foi distribuído'} "
        f"ao(à) procurador(a) {responsavel}, "
        f"na data de {_data_por_extenso(data_geracao)}, para análise e "
        "emissão de parecer/despacho."
    )

    lines = simpleSplit(body, "Helvetica", 11, usable)
    for line in lines:
        c.drawString(left, y, line)
        y -= 0.5 * cm

    y -= 2 * cm

    # ── Signature block ──────────────────────────────────────────────
    sig_line_width = 10 * cm
    sig_x = center_x - sig_line_width / 2

    # Ensure signature blocks fit on the page
    if y < 7 * cm:
        c.showPage()
        y = height - 5 * cm

    # Date line
    c.setFont("Helvetica", 11)
    c.drawCentredString(center_x, y, "_______ , _____ de _______________ de ________")
    y -= 0.4 * cm
    c.setFont("Helvetica", 9)
    c.drawCentredString(center_x, y, "(Local e Data)")
    y -= 2.5 * cm

    # Signature line – responsável
    c.setLineWidth(0.5)
    c.line(sig_x, y, sig_x + sig_line_width, y)
    y -= 0.4 * cm
    c.setFont("Helvetica", 10)
    c.drawCentredString(center_x, y, responsavel)
    y -= 0.4 * cm
    c.setFont("Helvetica", 9)
    c.drawCentredString(center_x, y, "Assinatura do(a) Responsável")

    y -= 3 * cm

    # Signature line – quem distribui
    c.setLineWidth(0.5)
    c.line(sig_x, y, sig_x + sig_line_width, y)
    y -= 0.4 * cm
    c.setFont("Helvetica", 10)
    c.drawCentredString(center_x, y, "____________________________________")
    y -= 0.4 * cm
    c.setFont("Helvetica", 9)
    c.drawCentredString(center_x, y, "Assinatura de quem distribuiu")

    # ── Footer ───────────────────────────────────────────────────────
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(
        center_x,
        2 * cm,
        f"Documento gerado em {data_geracao:%d/%m/%Y} — Controle Interno",
    )

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
