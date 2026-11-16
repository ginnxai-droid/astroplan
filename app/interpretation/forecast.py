from __future__ import annotations

from app.api.schemas import (
    AnnualForecastQuarter,
    AnnualForecastResponse,
    ChartResponse,
    ExplainedStatement,
    LanguageCode,
    WhyThisExplanation,
)
from app.interpretation.guardrails import verify_text
from app.interpretation.language import Catalog
from app.interpretation.readings import generate_life_area_readings
from app.interpretation.rules import Rule


def generate_annual_forecast_report(
    chart: ChartResponse,
    dasha: dict[str, object],
    transits: dict[str, object],
    rules: list[Rule],
    catalog: Catalog,
    year: int,
    lang: LanguageCode,
) -> AnnualForecastResponse:
    areas = generate_life_area_readings(chart, dasha, transits, rules, catalog, lang)

    simple = catalog.format(
        "annual_overview.simple",
        lang,
        year=year,
        md=str(dasha["active_mahadasha"]),
        jup_sign=str(transits["jupiter_transit_sign"]),
        sat_sign=str(transits["saturn_transit_sign"]),
    )
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
                f"Lagna {chart.lagna_sign_name}, Moon {chart.moon_sign_name}, "
                f"Dasha {dasha['active_mahadasha']}/{dasha['active_antardasha']}"
            ),
            classical_source="Phaladeepika Ch. 26 (Gochara) & BPHS Dasha Phala",
            strength_grade="supported",
        ),
        safety_verified=True,
    )

    sade_sati_info: dict[str, object] = transits["sade_sati"]  # type: ignore[assignment]
    quarters = [
        AnnualForecastQuarter(
            quarter=f"Q1 {year} (Jan-Mar)",
            theme_statement=areas["career"][0],
            active_dasha=f"{dasha['active_mahadasha']}-{dasha['active_antardasha']}",
            key_transit_note=(
                f"Jupiter in {transits['jupiter_transit_sign']} supports structured planning."
            ),
        ),
        AnnualForecastQuarter(
            quarter=f"Q2 {year} (Apr-Jun)",
            theme_statement=areas["finances"][0],
            active_dasha=f"{dasha['active_mahadasha']}-{dasha['active_antardasha']}",
            key_transit_note="Focus on savings allocation and budget review.",
        ),
        AnnualForecastQuarter(
            quarter=f"Q3 {year} (Jul-Sep)",
            theme_statement=areas["relationships"][0],
            active_dasha=f"{dasha['active_mahadasha']}-{dasha['active_antardasha']}",
            key_transit_note="Constructive communication in family and partnerships.",
        ),
        AnnualForecastQuarter(
            quarter=f"Q4 {year} (Oct-Dec)",
            theme_statement=areas["home"][0],
            active_dasha=f"{dasha['active_mahadasha']}-{dasha['active_antardasha']}",
            key_transit_note=str(sade_sati_info["phase_description"]),
        ),
    ]

    return AnnualForecastResponse(
        year=year,
        delivery_format="IN_APP_INTERACTIVE",
        pdf_export_available=False,
        overview=overview,
        quarters=quarters,
        life_area_highlights=areas,
    )
