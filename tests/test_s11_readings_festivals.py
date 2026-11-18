from datetime import date, time

import pytest

from app.api.schemas import BirthDetailsInput
from app.core.chart import calculate_chart
from app.core.dasha import calculate_vimshottari_dasha
from app.core.festivals import compute_panchang_vrats_for_range, load_festivals
from app.core.panchang import calculate_daily_panchang
from app.core.transits import evaluate_current_transits
from app.core.yogas import detect_yogas_and_doshas
from app.interpretation.language import Catalog
from app.interpretation.readings import generate_daily_insight, generate_life_area_readings
from app.interpretation.rules import load_rules

pytestmark = pytest.mark.s11


def test_all_four_life_areas_daily_insight_yogas_and_astronomical_vrats() -> None:
    inp = BirthDetailsInput(
        birth_date=date(1992, 5, 10),
        birth_time=time(14, 30),
        name="Test Person",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
        language="mr",
    )
    cat = Catalog("i18n")
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    moon = next(p for p in chart.planets if p.planet == "Moon")
    target = date(2026, 11, 15)
    dasha = calculate_vimshottari_dasha(inp.birth_date, moon.longitude, target)
    transits = evaluate_current_transits(chart, target)
    panchang = calculate_daily_panchang(target, 18.5204, 73.8567, "Asia/Kolkata")
    rules = load_rules("rules/mvp_rules.yaml", allow_draft=True)

    out = generate_life_area_readings(chart, dasha, transits, rules, cat, "mr")
    assert set(out.keys()) == {"career", "relationships", "finances", "home"}

    daily = generate_daily_insight(chart, panchang, transits, cat, "mr")
    assert daily.why_this.rule_id == "RULE_GOCHARA_CHANDRA_DAILY"
    assert daily.safety_verified is True

    yogas = detect_yogas_and_doshas(chart, cat, "mr", rules=rules)
    assert isinstance(yogas, list)

    seeded = load_festivals("data/festivals.yaml", allow_draft=True)
    assert len(seeded) >= 4
    vrats = compute_panchang_vrats_for_range(
        date(2026, 1, 1), 365, 18.5204, 73.8567, "Asia/Kolkata"
    )
    months = {v["date"][:7] for v in vrats}
    assert "2026-06" in months and "2026-12" in months
