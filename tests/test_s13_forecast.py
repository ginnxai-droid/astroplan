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

QUARTER_MONTHS = (1, 4, 7, 10)


def _person() -> BirthDetailsInput:
    return BirthDetailsInput(
        birth_date=date(1992, 5, 10),
        birth_time=time(14, 30),
        name="Test Person",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
    )


def _snapshots(chart, inp: BirthDetailsInput, year: int):
    moon = next(p for p in chart.planets if p.planet == "Moon")
    out = []
    for month in QUARTER_MONTHS:
        ref = date(year, month, 15)
        out.append(
            (
                calculate_vimshottari_dasha(inp.birth_date, moon.longitude, ref),
                evaluate_current_transits(chart, ref),
            )
        )
    return out


def test_annual_forecast_offers_a_pdf() -> None:
    inp = _person()
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    annual = generate_annual_forecast_report(
        chart,
        _snapshots(chart, inp, 2027),
        load_rules("rules/mvp_rules.yaml", allow_draft=True),
        Catalog("i18n"),
        2027,
        "en",
    )
    assert annual.delivery_format == "IN_APP_INTERACTIVE"
    assert annual.pdf_export_available is True
    assert len(annual.quarters) == 4
    quarter = annual.quarters[0].theme_statement.pro_text
    assert "Career." in quarter
    assert "Relationships, marriage, and children." in quarter
    assert "Money." in quarter
    assert "Observance." in quarter
    assert "January." in quarter
    assert len(quarter) > 1500
    spoken = annual.quarters[0].theme_statement.simple_text
    assert "On the 15th the Sun is in" not in spoken
    assert "you" in spoken.lower()
    assert chart.lagna_sign_name not in annual.overview.simple_text
    assert "you" in annual.overview.simple_text.lower()
    assert chart.lagna_sign_name in annual.overview.pro_text


def test_annual_pdf_is_a_real_document(client) -> None:
    response = client.post(
        "/v1/reports/annual-forecast/pdf",
        json={
            "name": "Test Person",
            "birth_date": "1992-05-10",
            "birth_time": "14:30:00",
            "place_name": "Pune",
            "country": "India",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "language": "mr",
        },
        params={"forecast_year": 2026},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    assert "astroplan-2026.pdf" in response.headers["content-disposition"]
    assert len(response.content) > 2000


def test_quarters_use_their_own_dasha_and_transit_snapshots() -> None:
    inp = _person()
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    snapshots = _snapshots(chart, inp, 2028)
    annual = generate_annual_forecast_report(
        chart,
        snapshots,
        load_rules("rules/mvp_rules.yaml", allow_draft=True),
        Catalog("i18n"),
        2028,
        "en",
    )

    expected = [f"{d['active_mahadasha']}-{d['active_antardasha']}" for d, _ in snapshots]
    assert expected[0] != expected[1], "fixture year must contain a dasha change"
    assert [q.active_dasha for q in annual.quarters] == expected
    for quarter, (_, transits) in zip(annual.quarters, snapshots, strict=True):
        assert str(transits["jupiter_transit_sign"]) in quarter.key_transit_note


def test_quarters_name_distinct_months_and_changes() -> None:
    inp = _person()
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    annual = generate_annual_forecast_report(
        chart,
        _snapshots(chart, inp, 2027),
        load_rules("rules/mvp_rules.yaml", allow_draft=True),
        Catalog("i18n"),
        2027,
        "en",
    )
    named = (
        ("January", "February", "March"),
        ("April", "May", "June"),
        ("July", "August", "September"),
        ("October", "November", "December"),
    )
    texts = [quarter.theme_statement.pro_text for quarter in annual.quarters]
    spoken = [quarter.theme_statement.simple_text for quarter in annual.quarters]
    assert len(set(texts)) == 4
    assert len(set(spoken)) == 4
    for text, months in zip(spoken, named, strict=True):
        assert months[0] in text and months[2] in text
        assert "On the 15th the Sun is in" not in text
    sun_signs: list[str] = []
    for text, months in zip(texts, named, strict=True):
        for month in months:
            assert f"{month}." in text
        parts = text.split("On the 15th the Sun is in ")
        assert len(parts) == 4
        quarter_suns = [part.split(",")[0].strip() for part in parts[1:]]
        assert len(set(quarter_suns)) >= 2
        sun_signs.extend(quarter_suns)
        assert "changes sign" in text or "shifts on" in text
    assert len(set(sun_signs)) >= 8
