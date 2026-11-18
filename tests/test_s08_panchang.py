from datetime import date, datetime, time, timedelta
from math import cos, radians
from zoneinfo import ZoneInfo

import pytest
import swisseph as swe

import app.core.panchang as panchang
from app.core.panchang import calculate_daily_panchang
from app.core.timeutil import jd_ut_to_local_datetime, local_to_utc

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


def test_sunrise_dial_uses_same_reference_as_panchang() -> None:
    p = calculate_daily_panchang(date(2026, 11, 15), 18.5204, 73.8567, "Asia/Kolkata")
    required = {
        "moon_longitude",
        "moon_sign_name",
        "moon_degree_in_sign",
        "moon_nakshatra_pada",
        "reference_datetime",
        "reference_kind",
        "phase_illumination",
    }
    assert required <= p.keys()

    # Independently obtain sunrise and positions from Swiss Ephemeris.
    rise = swe.rise_trans(
        swe.julday(2026, 11, 15, 0.5) - 0.25,
        swe.SUN,
        swe.CALC_RISE | swe.BIT_DISC_CENTER,
        (73.8567, 18.5204, 0.0),
    )[1][0]
    reference = datetime.fromisoformat(str(p["reference_datetime"]))
    assert reference == jd_ut_to_local_datetime(rise, "Asia/Kolkata")
    assert reference.utcoffset() == timedelta(hours=5, minutes=30)
    assert reference.strftime("%H:%M") == p["sunrise_local"]
    assert p["reference_kind"] == "sunrise"
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    sun = float(swe.calc_ut(rise, swe.SUN, flags)[0][0]) % 360.0
    moon = float(swe.calc_ut(rise, swe.MOON, flags)[0][0]) % 360.0
    assert p["moon_longitude"] == moon
    assert p["sun_longitude"] == round(sun, 4)
    assert p["moon_degree_in_sign"] == moon % 30.0
    assert p["moon_sign_name"] == "Capricorn"
    assert p["nakshatra"] == "Uttara Ashadha"
    assert p["moon_nakshatra_pada"] == 2
    assert p["tithi_index"] == 6
    assert p["phase_illumination"] == pytest.approx((1 - cos(radians(moon - sun))) / 2)


@pytest.mark.parametrize("tz_name", ["Asia/Kolkata", "America/New_York", "Pacific/Auckland"])
@pytest.mark.parametrize("has_sunset", [False, True])
def test_missing_sunrise_labels_six_am_reference(monkeypatch, tz_name, has_sunset) -> None:
    target = date(2026, 11, 15)
    utc = local_to_utc(target, time(6), tz_name)
    jd = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60.0)
    monkeypatch.setattr(
        panchang, "sunrise_sunset_jd_ut", lambda *_: (None, jd + 0.5 if has_sunset else None)
    )
    p = calculate_daily_panchang(target, 18.5204, 73.8567, tz_name)
    assert p["reference_kind"] == "fallback_06:00"
    reference = datetime.fromisoformat(str(p["reference_datetime"]))
    assert reference == jd_ut_to_local_datetime(jd, tz_name)
    local_six = datetime.combine(target, time(6), tzinfo=ZoneInfo(tz_name))
    assert abs((reference - local_six).total_seconds()) < 0.0001
    assert reference.utcoffset() == local_six.utcoffset()
    moon = float(swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL | swe.FLG_SPEED)[0][0]) % 360.0
    assert p["moon_longitude"] == moon
    assert p["slot_math_fallback"] is True
    assert p["sunrise_local"] == "06:00"


def test_missing_sunset_does_not_relabel_actual_sunrise(monkeypatch) -> None:
    rise = swe.julday(2026, 11, 15, 1.5)
    monkeypatch.setattr(panchang, "sunrise_sunset_jd_ut", lambda *_: (rise, None))
    p = calculate_daily_panchang(date(2026, 11, 15), 18.5204, 73.8567, "Asia/Kolkata")
    assert p["reference_kind"] == "sunrise"
    assert p["reference_datetime"] == "2026-11-15T07:00:00+05:30"
    assert p["slot_math_fallback"] is True
    moon = float(swe.calc_ut(rise, swe.MOON, swe.FLG_SIDEREAL | swe.FLG_SPEED)[0][0]) % 360.0
    assert p["moon_longitude"] == moon


@pytest.mark.parametrize(
    "sun,moon,sign,degree,nakshatra,pada,illumination",
    [
        (0.0, 0.0, "Aries", 0.0, "Ashwini", 1, 0.0),
        (1.0, 91.0, "Cancer", 1.0, "Punarvasu", 4, 0.5),
        (1.0, 181.0, "Libra", 1.0, "Chitra", 3, 1.0),
        (1.0, 271.0, "Capricorn", 1.0, "Uttara Ashadha", 2, 0.5),
        (30.0, 29.999999, "Aries", 29.999999, "Krittika", 1, 0.0),
        (0.0, 359.999999, "Pisces", 29.999999, "Revati", 4, 0.0),
    ],
)
def test_dial_phase_and_boundaries(
    monkeypatch, sun, moon, sign, degree, nakshatra, pada, illumination
) -> None:
    rise = swe.julday(2026, 11, 15, 1.5)
    monkeypatch.setattr(panchang, "sunrise_sunset_jd_ut", lambda *_: (rise, rise + 0.5))

    def positions(jd, planet, flags):
        assert jd == rise
        assert flags == swe.FLG_SIDEREAL | swe.FLG_SPEED
        return (({swe.SUN: sun, swe.MOON: moon}[planet], 0, 0, 0, 0, 0), flags)

    monkeypatch.setattr(panchang.swe, "calc_ut", positions)
    p = calculate_daily_panchang(date(2026, 11, 15), 18.5204, 73.8567, "Asia/Kolkata")
    assert p["moon_longitude"] == moon
    assert p["moon_sign_name"] == sign
    assert p["moon_degree_in_sign"] == pytest.approx(degree)
    assert p["nakshatra"] == nakshatra
    assert p["moon_nakshatra_pada"] == pada
    assert p["phase_illumination"] == pytest.approx(illumination, abs=1e-12)
    assert 0.0 <= p["phase_illumination"] <= 1.0
