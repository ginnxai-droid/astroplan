from datetime import date, time

import pytest
from pydantic import ValidationError

import app.core.chart as chart_module
from app.api.schemas import BirthDetailsInput, ChartResponse
from app.core.chart import calculate_chart

pytestmark = pytest.mark.s04


def _ref():
    inp = BirthDetailsInput(
        birth_date=date(1947, 8, 15),
        birth_time=time(0, 0),
        place_name="New Delhi",
        latitude=28.6139,
        longitude=77.2090,
        uncertainty_minutes=15,
        node_type="MEAN",
    )
    return calculate_chart(inp, 28.6139, 77.2090, "Asia/Kolkata")


def test_reference_1947_and_dasha_uncertainty_warning() -> None:
    c = _ref()
    assert c.ayanamsa_name == "Lahiri"
    assert 23.0 < c.ayanamsa_value < 23.25
    assert c.lagna_sign_name == "Taurus"
    assert c.moon_sign_name == "Cancer"
    assert c.moon_nakshatra == "Pushya"
    assert len(c.planets) == 9
    assert c.boundary_warning is not None
    assert "Dasha" in c.boundary_warning or "Lagna" in c.boundary_warning


def test_rahu_ketu_opposition() -> None:
    c = _ref()
    rahu = next(p for p in c.planets if p.planet == "Rahu")
    ketu = next(p for p in c.planets if p.planet == "Ketu")
    assert round((rahu.longitude + 180.0) % 360.0, 3) == round(ketu.longitude, 3)


def test_reference_1947_navamsa_ascendant() -> None:
    # Taurus 7°43' is the third navamsa of Taurus: Pisces, not D1 Taurus.
    payload = _ref().model_dump(mode="json")
    assert {"navamsa_lagna_sign_index", "navamsa_lagna_sign_name"} <= payload.keys()
    assert payload["navamsa_lagna_sign_index"] == 12
    assert payload["navamsa_lagna_sign_name"] == "Pisces"


@pytest.mark.parametrize(
    "lagna_lon,expected_index,expected_name",
    [
        (0.5, 1, "Aries"),
        (3.5, 2, "Taurus"),
        (30.0, 10, "Capricorn"),
        (39.99999, 12, "Pisces"),
        (90.0, 4, "Cancer"),
        (359.99999, 12, "Pisces"),
    ],
)
def test_navamsa_ascendant_uses_raw_lagna_longitude(
    monkeypatch, lagna_lon, expected_index, expected_name
) -> None:
    # Values just below boundaries must not cross them through display rounding.
    monkeypatch.setattr(chart_module, "sidereal_lagna", lambda *_: lagna_lon)
    inp = BirthDetailsInput(
        birth_date=date(1947, 8, 15), birth_time=time(0), place_name="New Delhi"
    )
    payload = calculate_chart(inp, 28.6139, 77.2090, "Asia/Kolkata").model_dump(mode="json")
    assert payload["navamsa_lagna_sign_index"] == expected_index
    assert payload["navamsa_lagna_sign_name"] == expected_name


@pytest.mark.parametrize("missing", ["navamsa_lagna_sign_index", "navamsa_lagna_sign_name"])
def test_chart_response_requires_navamsa_ascendant(missing) -> None:
    payload = _ref().model_dump()
    payload.pop(missing, None)
    with pytest.raises(ValidationError) as exc_info:
        ChartResponse.model_validate(payload)
    assert any(e["loc"] == (missing,) and e["type"] == "missing" for e in exc_info.value.errors())
