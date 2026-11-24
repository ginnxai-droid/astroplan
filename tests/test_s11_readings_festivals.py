import re
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
from app.interpretation.readings import (
    generate_daily_area_readings,
    generate_daily_insight,
    generate_life_area_readings,
)
from app.interpretation.rules import load_rules

pytestmark = pytest.mark.s11

_TECHNICAL_TODAY = re.compile(
    r"\bnakshatras?\b|नक्षत्र|\bhouse\s+\d|\b\d{1,2}(?:st|nd|rd|th)?\s+houses?\b|"
    r"भाव\s*\d|\d+(?:\.\d+)?\s*°",
    re.IGNORECASE,
)


def _assert_human_today(text: str) -> None:
    assert _TECHNICAL_TODAY.search(text) is None
    assert re.fullmatch(r"[\d\s°.'\"+-]+", text.strip()) is None


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
    _assert_human_today(daily.simple_text)
    assert "झुक" in daily.simple_text

    yogas = detect_yogas_and_doshas(chart, cat, "mr", rules=rules)
    assert isinstance(yogas, list)

    seeded = load_festivals("data/festivals.yaml", allow_draft=True)
    assert len(seeded) >= 4
    vrats = compute_panchang_vrats_for_range(
        date(2026, 1, 1), 365, 18.5204, 73.8567, "Asia/Kolkata"
    )
    months = {v["date"][:7] for v in vrats}
    assert "2026-06" in months and "2026-12" in months


def test_personalized_today_and_chart_differ_by_kundali() -> None:
    cat = Catalog("i18n")
    rules = load_rules("rules/mvp_rules.yaml", allow_draft=True)
    target = date(2026, 11, 22)

    p1 = BirthDetailsInput(
        birth_date=date(1990, 1, 14),
        birth_time=time(6, 30),
        name="Aarav",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
        language="en",
    )
    p2 = BirthDetailsInput(
        birth_date=date(1995, 9, 25),
        birth_time=time(21, 15),
        name="Meera",
        place_name="Delhi",
        country="India",
        latitude=28.6139,
        longitude=77.2090,
        language="en",
    )
    c1 = calculate_chart(p1, 18.5204, 73.8567, "Asia/Kolkata")
    c2 = calculate_chart(p2, 28.6139, 77.2090, "Asia/Kolkata")
    m1 = next(p for p in c1.planets if p.planet == "Moon")
    m2 = next(p for p in c2.planets if p.planet == "Moon")
    d1 = calculate_vimshottari_dasha(p1.birth_date, m1.longitude, target)
    d2 = calculate_vimshottari_dasha(p2.birth_date, m2.longitude, target)
    t1 = evaluate_current_transits(c1, target)
    t2 = evaluate_current_transits(c2, target)
    pan1 = calculate_daily_panchang(target, 18.5204, 73.8567, "Asia/Kolkata")
    pan2 = calculate_daily_panchang(target, 28.6139, 77.2090, "Asia/Kolkata")

    day1 = generate_daily_insight(c1, pan1, t1, cat, "en", dasha=d1)
    day2 = generate_daily_insight(c2, pan2, t2, cat, "en", dasha=d2)
    assert day1.simple_text != day2.simple_text
    assert "Steady professional progress" not in day1.simple_text
    for day in (day1, day2):
        _assert_human_today(day.simple_text)
        assert "leaning toward" in day.simple_text
        assert "What can feel supportive" in day.simple_text
        assert "What needs care" in day.simple_text
        assert "A gentle next step" in day.simple_text

    areas1 = generate_life_area_readings(c1, d1, t1, rules, cat, "en")
    areas2 = generate_life_area_readings(c2, d2, t2, rules, cat, "en")
    assert areas1["career"][0].simple_text != areas2["career"][0].simple_text
    assert "Navamsa" in areas1["career"][0].simple_text
    assert "Steady professional progress" not in areas1["career"][0].simple_text

    d_areas1 = generate_daily_area_readings(c1, d1, t1, pan1, rules, "en")
    assert d_areas1["career"][0].simple_text != areas1["career"][0].simple_text
    assert "2026-11-22" in d_areas1["relationships"][0].time_window
    for area in d_areas1.values():
        _assert_human_today(area[0].simple_text)
        assert "What helps:" not in area[0].simple_text

    impact = areas1["career"][0].simple_text
    for planet in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"):
        assert planet in impact
    assert "What helps:" in impact
    assert "What needs care:" in impact
    assert "Takeaway:" in impact
    assert "Guru (Jupiter)" in impact
    assert "Shani (Saturn)" in impact
    for banned in (
        "guaranteed",
        "destined",
        "assured",
        "certainly will",
        "will definitely",
        "100%",
    ):
        assert banned not in impact.lower()
    sun = next(p for p in c1.planets if p.planet == "Sun")
    assert f"house {sun.house}" in impact
