"""Yearly and quarterly forecast as a PDF.

The face is Noto Sans Devanagari (SIL Open Font License), which covers
English, Hindi, and Marathi in one file.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from app.api.schemas import AnnualForecastResponse

_FONT = Path(__file__).resolve().parent / "fonts" / "NotoSansDevanagari-Regular.ttf"


def _write(pdf: FPDF, size: int, line_height: float, text: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Astro", size=size)
    pdf.multi_cell(pdf.epw, line_height, text)


def render_annual_pdf(report: AnnualForecastResponse, *, name: str, disclaimer: str) -> bytes:
    if not _FONT.is_file():
        raise FileNotFoundError(_FONT)
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_text_shaping(True)
    pdf.add_font("Astro", fname=str(_FONT))
    pdf.add_page()
    _write(pdf, 18, 10, f"{name} — {report.year}")
    pdf.ln(2)
    _write(pdf, 11, 6, disclaimer)
    pdf.ln(3)
    _write(pdf, 12, 7, report.overview.simple_text)
    for quarter in report.quarters:
        pdf.add_page()
        _write(pdf, 16, 9, quarter.quarter)
        pdf.ln(1)
        _write(pdf, 11, 6, quarter.active_dasha)
        _write(pdf, 11, 6, quarter.key_transit_note)
        pdf.ln(2)
        _write(pdf, 12, 7, quarter.theme_statement.simple_text)
    return bytes(pdf.output())
