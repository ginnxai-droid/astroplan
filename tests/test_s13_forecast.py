from datetime import date, time

import pytest

from app.api.schemas import BirthDetailsInput
from app.core.chart import calculate_chart
from app.core.dasha import calculate_vimshottari_dasha
from app.core.transits import evaluate_current_transits
from app.interpretation.forecast import generate_annual_forecast_report
from app.interpretation.language import Catalog
from app.interpretation.rules import load_rules

pytestmark = pytest.mark.s13


def test_annual_forecast_is_interactive_and_pdf_disabled() -> None:
    inp = BirthDetailsInput(
        birth_date=date(1992, 5, 10),
        birth_time=time(14, 30),
        name="Test Person",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
    )
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    moon = next(p for p in chart.planets if p.planet == "Moon")
    dasha = calculate_vimshottari_dasha(inp.birth_date, moon.longitude, date(2027, 1, 15))
    transits = evaluate_current_transits(chart, date(2027, 1, 15))
    rules = load_rules("rules/mvp_rules.yaml", allow_draft=True)
    annual = generate_annual_forecast_report(
        chart, dasha, transits, rules, Catalog("i18n"), 2027, "en"
    )
    assert annual.delivery_format == "IN_APP_INTERACTIVE"
    assert annual.pdf_export_available is False
    assert len(annual.quarters) == 4
