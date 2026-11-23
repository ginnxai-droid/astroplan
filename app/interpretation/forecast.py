from __future__ import annotations

import calendar
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import swisseph as swe

from app.api.schemas import (
    AnnualForecastQuarter,
    AnnualForecastResponse,
    ChartResponse,
    ExplainedStatement,
    LanguageCode,
    LifeAreaCategory,
    WhyThisExplanation,
)
from app.core.constants import RASHI_NAMES
from app.core.dasha import calculate_vimshottari_dasha
from app.core.ephemeris import sidereal_longitudes, sidereal_nodes
from app.core.zodiac import sign_index_from_longitude
from app.interpretation.guardrails import verify_text
from app.interpretation.language import Catalog
from app.interpretation.phala import quarter_reading, transit_note, year_reading
from app.interpretation.readings import generate_life_area_readings
from app.interpretation.rules import Rule
from app.interpretation.terms import gloss

_MONTH_TEXT: dict[str, object] = json.loads(
    Path(__file__).with_name("month_text.json").read_text(encoding="utf-8")
)
_LANG_IDX = {"en": 0, "hi": 1, "mr": 2}
_MOVING = ("Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu")

Snapshot = tuple[dict[str, object], dict[str, object]]
_Period = tuple[str, str, str]


def _mt(key: str, lang: str, **kwargs: object) -> str:
    raw = _MONTH_TEXT[key]
    if not isinstance(raw, list):
        raise TypeError(key)
    text = str(raw[_LANG_IDX[lang]])
    return text.format(**kwargs) if kwargs else text


def _local_month(name: str, lang: str) -> str:
    months = _MONTH_TEXT["months"]
    if not isinstance(months, dict):
        raise TypeError("months")
    row = months[name]
    if not isinstance(row, list):
        raise TypeError(name)
    return str(row[_LANG_IDX[lang]])


def _focus(index: int, lang: str) -> str:
    focuses = _MONTH_TEXT["focus"]
    if not isinstance(focuses, list):
        raise TypeError("focus")
    row = focuses[index]
    if not isinstance(row, list):
        raise TypeError("focus row")
    return str(row[_LANG_IDX[lang]])


def _signs_on(day: date, true_node: bool) -> dict[str, int]:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    jd = float(swe.julday(day.year, day.month, day.day, 12.0))
    found = {
        raw.planet: sign_index_from_longitude(raw.longitude_sidereal)
        for raw in sidereal_longitudes(jd)
    }
    rahu, ketu = sidereal_nodes(jd, true_node=true_node)
    found["Rahu"] = sign_index_from_longitude(rahu)
    found["Ketu"] = sign_index_from_longitude(ketu)
    return found


def _month_paragraph(chart: ChartResponse, year: int, month: int, focus: str, lang: str) -> str:
    birth = chart.input_summary.birth_date
    moon_lon = next(item.longitude for item in chart.planets if item.planet == "Moon")
    true_node = chart.input_summary.node_type == "TRUE"
    last_day = calendar.monthrange(year, month)[1]
    sign_cache: dict[date, dict[str, int]] = {}
    period_cache: dict[date, _Period] = {}

    def signs(day: date) -> dict[str, int]:
        cached = sign_cache.get(day)
        if cached is None:
            cached = _signs_on(day, true_node)
            sign_cache[day] = cached
        return cached

    def period(day: date) -> _Period:
        cached = period_cache.get(day)
        if cached is None:
            row = calculate_vimshottari_dasha(birth, moon_lon, day)
            cached = (
                str(row["active_mahadasha"]),
                str(row["active_antardasha"]),
                str(row["active_pratyantardasha"]),
            )
            period_cache[day] = cached
        return cached

    shifts: list[str] = []
    previous_signs = signs(date(year, month, 1))
    previous_period = period(date(year, month, 1))
    for day_number in range(2, last_day + 1):
        current_day = date(year, month, day_number)
        current_signs = signs(current_day)
        for name in _MOVING:
            old_i, new_i = previous_signs[name], current_signs[name]
            if old_i != new_i:
                shifts.append(
                    _mt(
                        "shift_sign",
                        lang,
                        planet=gloss(name, lang),
                        old=gloss(RASHI_NAMES[old_i - 1], lang),
                        new=gloss(RASHI_NAMES[new_i - 1], lang),
                        when=current_day.isoformat(),
                    )
                )
        current_period = period(current_day)
        old_md, old_ad, old_pd = previous_period
        new_md, new_ad, new_pd = current_period
        if (old_md, old_ad) != (new_md, new_ad):
            shifts.append(
                _mt(
                    "shift_dasha",
                    lang,
                    when=current_day.isoformat(),
                    old_md=gloss(old_md, lang),
                    old_ad=gloss(old_ad, lang),
                    new_md=gloss(new_md, lang),
                    new_ad=gloss(new_ad, lang),
                )
            )
        elif old_pd != new_pd:
            shifts.append(
                _mt(
                    "shift_pd",
                    lang,
                    when=current_day.isoformat(),
                    old_pd=gloss(old_pd, lang),
                    new_pd=gloss(new_pd, lang),
                    md=gloss(new_md, lang),
                    ad=gloss(new_ad, lang),
                )
            )
        previous_signs = current_signs
        previous_period = current_period

    mid = date(year, month, 15)
    mid_signs = signs(mid)
    mid_period = period(mid)
    dasha = calculate_vimshottari_dasha(birth, moon_lon, mid)
    if not shifts:
        shifts.append(_mt("shift_none", lang))
    month_name = calendar.month_name[month]
    return _mt(
        "month_specific",
        lang,
        month=_local_month(month_name, lang),
        sun=gloss(RASHI_NAMES[mid_signs["Sun"] - 1], lang),
        mercury=gloss(RASHI_NAMES[mid_signs["Mercury"] - 1], lang),
        venus=gloss(RASHI_NAMES[mid_signs["Venus"] - 1], lang),
        mars=gloss(RASHI_NAMES[mid_signs["Mars"] - 1], lang),
        jup=gloss(RASHI_NAMES[mid_signs["Jupiter"] - 1], lang),
        jup_h=((mid_signs["Jupiter"] - chart.moon_sign_index) % 12) + 1,
        sat=gloss(RASHI_NAMES[mid_signs["Saturn"] - 1], lang),
        sat_h=((mid_signs["Saturn"] - chart.moon_sign_index) % 12) + 1,
        md=gloss(mid_period[0], lang),
        ad=gloss(mid_period[1], lang),
        ad_end=dasha["antardasha_end_date"],
        shifts=" ".join(shifts),
        focus=focus,
    )


def quarter_month_text(
    chart: ChartResponse, year: int, months: tuple[str, str, str], lang: str
) -> str:
    number = {name: index for index, name in enumerate(calendar.month_name) if name}
    paragraphs = [
        _month_paragraph(chart, year, number[name], _focus(index, lang), lang)
        for index, name in enumerate(months)
    ]
    return " ".join(paragraphs)


_QUARTERS: tuple[tuple[str, LifeAreaCategory, tuple[str, str, str]], ...] = (
    ("Q1 {year} (Jan-Mar)", "career", ("January", "February", "March")),
    ("Q2 {year} (Apr-Jun)", "finances", ("April", "May", "June")),
    ("Q3 {year} (Jul-Sep)", "relationships", ("July", "August", "September")),
    ("Q4 {year} (Oct-Dec)", "home", ("October", "November", "December")),
)


def generate_annual_forecast_report(
    chart: ChartResponse,
    snapshots: Sequence[Snapshot],
    rules: list[Rule],
    catalog: Catalog,
    year: int,
    lang: LanguageCode,
    month_facts: list[str] | None = None,
) -> AnnualForecastResponse:
    dasha, transits = snapshots[0]
    areas = generate_life_area_readings(chart, dasha, transits, rules, catalog, lang)

    simple = year_reading(chart, dasha, transits, lang)
    pro = catalog.format(
        "annual_overview.pro",
        lang,
        lagna=chart.lagna_sign_name,
        moon=chart.moon_sign_name,
        md=str(dasha["active_mahadasha"]),
        ad=str(dasha["active_antardasha"]),
        sat_house=str(transits["saturn_house_from_moon"]),
    )
    verify_text(simple, languages=(lang,))
    verify_text(pro, languages=(lang,))

    overview = ExplainedStatement(
        statement_id=f"ANNUAL_OVERVIEW_{year}_{chart.lagna_sign_index}",
        category="annual_overview",
        time_window=f"Calendar Year {year}",
        simple_text=simple,
        pro_text=pro,
        why_this=WhyThisExplanation(
            rule_id="RULE_ANNUAL_DASHA_GOCHARA_SYNTHESIS",
            placement_evidence=(
                f"Lagna {gloss(chart.lagna_sign_name, lang)}, "
                f"Moon {gloss(chart.moon_sign_name, lang)}, "
                f"Dasha {gloss(dasha['active_mahadasha'], lang)}/"
                f"{gloss(dasha['active_antardasha'], lang)}"
            ),
            classical_source="Phaladeepika Ch. 26 (Gochara) & BPHS Dasha Phala",
            strength_grade="supported",
        ),
        safety_verified=True,
    )

    quarters: list[AnnualForecastQuarter] = []
    for (q_dasha, q_transits), (label, category, months) in zip(snapshots, _QUARTERS, strict=True):
        q_areas = generate_life_area_readings(chart, q_dasha, q_transits, rules, catalog, lang)
        base = q_areas[category][0]
        month_text = quarter_month_text(chart, year, months, lang)
        if month_facts is not None:
            month_facts.append(month_text)
        reading = quarter_reading(
            chart,
            q_dasha,
            q_transits,
            lang,
            months,
            month_text=month_text,
        )
        quarters.append(
            AnnualForecastQuarter(
                quarter=label.format(year=year),
                theme_statement=base.model_copy(
                    update={"simple_text": reading, "time_window": label.format(year=year)}
                ),
                active_dasha=(
                    f"{gloss(q_dasha['active_mahadasha'], lang)}-"
                    f"{gloss(q_dasha['active_antardasha'], lang)}"
                ),
                key_transit_note=transit_note(q_transits, lang),
            )
        )

    return AnnualForecastResponse(
        year=year,
        delivery_format="IN_APP_INTERACTIVE",
        pdf_export_available=True,
        overview=overview,
        quarters=quarters,
        life_area_highlights=areas,
    )
