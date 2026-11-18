from datetime import date, time

import pytest

from app.api.schemas import BirthDetailsInput
from app.core.chart import calculate_chart
from app.core.transits import evaluate_current_transits

pytestmark = pytest.mark.s07


def test_shape() -> None:
    inp = BirthDetailsInput(
        birth_date=date(1990, 1, 1),
        birth_time=time(12, 0),
        name="Test Person",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
    )
    c = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    r = evaluate_current_transits(c, date(2026, 11, 15))
    assert "sade_sati" in r and isinstance(r["sade_sati"]["is_active"], bool)  # type: ignore[index]
    assert "moon_transit_sign" in r
