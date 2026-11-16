from datetime import date

import pytest

from app.core.panchang import calculate_daily_panchang

pytestmark = pytest.mark.s08


def test_shape() -> None:
    p = calculate_daily_panchang(date(2026, 11, 15), 18.5204, 73.8567, "Asia/Kolkata")
    assert p["vara"] == "Sunday" and p["tithi"] and p["nakshatra"]
    assert "-" in str(p["rahu_kaal"]) and p["offline_cacheable"] is True


def test_rahu_kaal_inside_daytime() -> None:
    p = calculate_daily_panchang(date(2026, 11, 15), 18.5204, 73.8567, "Asia/Kolkata")

    def _min(s: str) -> int:
        h, m = map(int, s.split(":"))
        return h * 60 + m

    sunrise = _min(str(p["sunrise_local"]))
    sunset = _min(str(p["sunset_local"]))
    rk_s, rk_e = str(p["rahu_kaal"]).split(" - ")
    assert sunrise <= _min(rk_s) < _min(rk_e) <= sunset
