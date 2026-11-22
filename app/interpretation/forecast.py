from __future__ import annotations

from collections.abc import Sequence

from app.api.schemas import (
    AnnualForecastQuarter,
    AnnualForecastResponse,
    ChartResponse,
    ExplainedStatement,
    LanguageCode,
    LifeAreaCategory,
    WhyThisExplanation,
)
from app.interpretation.guardrails import verify_text
from app.interpretation.language import Catalog
from app.interpretation.phala import quarter_reading, transit_note, year_reading
from app.interpretation.readings import generate_life_area_readings
from app.interpretation.rules import Rule
from app.interpretation.terms import gloss

Snapshot = tuple[dict[str, object], dict[str, object]]

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
        reading = quarter_reading(chart, q_dasha, q_transits, lang, months)
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
