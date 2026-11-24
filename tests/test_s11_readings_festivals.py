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
from app.interpretation.voice import (
    compose_today,
    max_area_words,
    max_today_words,
    sentence_count,
    spoken_lines,
    today_voice_problem,
)

pytestmark = pytest.mark.s11

_TECHNICAL_TODAY = re.compile(
    r"\bnakshatras?\b|नक्षत्र|\bgochars?\b|गोचर|\bD9\b|नवांश|"
    r"\blagnas?\b|लग्न|\bkundalis?\b|कुंडली|"
    r"\bhouse\s+\d|\b\d{1,2}(?:st|nd|rd|th)?\s+houses?\b|"
    r"भाव\s*\d|\d+(?:\.\d+)?\s*°|"
    r"\b(?:aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|"
    r"capricorn|aquarius|pisces)\b|"
    r"मेष|वृषभ|मिथुन|कर्क|सिंह|कन्या|तुला|वृश्चिक|धनु|मकर|कुंभ|मीन",
    re.IGNORECASE,
)


def _assert_human_today(text: str) -> None:
    assert _TECHNICAL_TODAY.search(text) is None
    assert re.fullmatch(r"[\d\s°.'\"+-]+", text.strip()) is None


def _assert_spoken_today(text: str, *, lang: str) -> None:
    assert sentence_count(text) >= 2
    assert today_voice_problem(text) is None
    assert len(text.split()) <= 120
    assert "धीर मागतो" not in text
    assert "बाबतीत" not in text
    assert "today asks" not in text.lower()
    assert "asks for patience" not in text.lower()
    if lang == "en":
        assert re.search(r"\byou\b", text, re.IGNORECASE)
    elif lang == "mr":
        assert re.search(r"तुम्ह|तुमच", text)
    else:
        assert "आप" in text


def test_today_voice_sits_with_the_person_and_changes_with_the_day() -> None:
    for line in spoken_lines():
        assert "धीर मागतो" not in line
        assert "बाबतीत" not in line
        assert "today asks" not in line.lower()
        assert "asks for patience" not in line.lower()
        assert _TECHNICAL_TODAY.search(line) is None
    for lang in ("en", "hi", "mr"):
        assert max_today_words(lang) <= 120
        assert max_area_words(lang) <= 120
    shared = dict(
        pressured=True,
        money_easy=False,
        saturn_easy=False,
        work_house=5,
        money_house=2,
        home_house=4,
        talk_house=7,
        step_planet="Jupiter",
    )
    open_day = {**shared, "pressured": False, "money_easy": True, "saturn_easy": True}
    mars = compose_today(lang="mr", weekday_lord="Mars", **open_day)
    sun = compose_today(lang="mr", weekday_lord="Sun", **open_day)
    easy = compose_today(lang="en", weekday_lord="Mars", **open_day)
    tight = compose_today(lang="en", weekday_lord="Mars", **shared)
    assert mars != sun
    assert easy != tight
    _assert_spoken_today(mars, lang="mr")
    _assert_spoken_today(sun, lang="mr")
    _assert_spoken_today(easy, lang="en")
    _assert_spoken_today(tight, lang="en")
    assert mars.startswith("आज मंगळवार")
    assert "तुमच्या बोलण्यात" in mars
    assert easy.startswith("Tuesday carries Mars")
    assert "the way you speak" in easy


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

    daily = generate_daily_insight(chart, panchang, transits, cat, "mr", dasha=dasha)
    hindi = generate_daily_insight(chart, panchang, transits, cat, "hi", dasha=dasha)
    assert daily.why_this.rule_id == "RULE_GOCHARA_CHANDRA_DAILY"
    assert daily.safety_verified is True
    _assert_human_today(daily.simple_text)
    _assert_spoken_today(daily.simple_text, lang="mr")
    _assert_human_today(hindi.simple_text)
    _assert_spoken_today(hindi.simple_text, lang="hi")
    assert "कामात" in daily.simple_text
    assert "धनात" in daily.simple_text
    assert "घरी" in daily.simple_text
    assert "बोलताना" in daily.simple_text
    assert "Test Person" not in daily.simple_text
    assert "नवांश" in daily.pro_text

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
        _assert_spoken_today(day.simple_text, lang="en")
        assert "At work" in day.simple_text
        assert "With money" in day.simple_text
        assert "At home" in day.simple_text
        assert "In conversation" in day.simple_text
        assert "Your energy" in day.simple_text
        assert "Aarav" not in day.simple_text
        assert "Meera" not in day.simple_text
        assert "D9" in day.pro_text

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
        _assert_spoken_today(area[0].simple_text, lang="en")
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
