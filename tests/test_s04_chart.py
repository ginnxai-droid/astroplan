from datetime import date, time

import pytest

from app.api.schemas import BirthDetailsInput
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
