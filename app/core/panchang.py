"""Sunrise-accurate Panchang (anchors Rahu Kaal and Abhijit Muhurat to true local sunrise)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from math import cos, radians

import swisseph as swe

from app.core.constants import (
    KARANA_REPEATING,
    RAHU_KAAL_SLOT_BY_WEEKDAY,
    TITHI_NAMES,
    VARA_NAMES,
    YOGA_NAMES,
)
from app.core.ephemeris import sunrise_sunset_jd_ut
from app.core.timeutil import jd_ut_to_local_datetime, local_to_utc
from app.core.zodiac import degree_in_sign, nakshatra_and_pada, sign_index_from_longitude, sign_name


def _karana(idx: int) -> str:
    if idx == 0:
        return "Kimstughna"
    if idx >= 57:
        return {57: "Shakuni", 58: "Chatushpada", 59: "Naga"}.get(idx, "Bava")
    return KARANA_REPEATING[(idx - 1) % 7]


def calculate_daily_panchang(
    target_date: date, lat: float, lon: float, tz_name: str
) -> dict[str, object]:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ref = local_to_utc(target_date, time(6, 0), tz_name)
    jd_ref = float(swe.julday(ref.year, ref.month, ref.day, ref.hour + ref.minute / 60.0))
    rise_jd, set_jd = sunrise_sunset_jd_ut(jd_ref, lat, lon)

    if rise_jd is None or set_jd is None:
        sunrise_dt = datetime.combine(target_date, time(6, 0))
        sunset_dt = datetime.combine(target_date, time(18, 0))
        fallback = True
    else:
        sunrise_dt = jd_ut_to_local_datetime(rise_jd, tz_name).replace(tzinfo=None)
        sunset_dt = jd_ut_to_local_datetime(set_jd, tz_name).replace(tzinfo=None)
        fallback = False

    ref_jd = rise_jd if rise_jd is not None else jd_ref
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    sun_lon = float(swe.calc_ut(ref_jd, swe.SUN, flags)[0][0]) % 360.0
    moon_lon = float(swe.calc_ut(ref_jd, swe.MOON, flags)[0][0]) % 360.0

    diff = (moon_lon - sun_lon) % 360.0
    tithi_idx = int(diff / 12.0)
    tithi = TITHI_NAMES[tithi_idx]
    weekday = target_date.weekday()
    vara = VARA_NAMES[weekday]
    _, nak, moon_pada = nakshatra_and_pada(moon_lon)
    yoga = YOGA_NAMES[int(((sun_lon + moon_lon) % 360.0) / (360.0 / 27.0))]
    karana = _karana(int(diff / 6.0))

    day = max((sunset_dt - sunrise_dt).total_seconds() / 3600.0, 1.0)
    slot = day / 8.0
    rk_slot = RAHU_KAAL_SLOT_BY_WEEKDAY[weekday]
    rk_start = sunrise_dt + timedelta(hours=(rk_slot - 1) * slot)
    rk_end = rk_start + timedelta(hours=slot)
    muh = day / 15.0
    abh_start = sunrise_dt + timedelta(hours=7 * muh)
    abh_end = abh_start + timedelta(hours=muh)

    return {
        "date": target_date.isoformat(),
        "location": {"latitude": lat, "longitude": lon, "timezone": tz_name},
        "tithi": tithi,
        "tithi_index": tithi_idx + 1,
        "sun_longitude": round(sun_lon, 4),
        "moon_longitude": moon_lon,
        "moon_sign_name": sign_name(sign_index_from_longitude(moon_lon)),
        "moon_degree_in_sign": degree_in_sign(moon_lon),
        "moon_nakshatra_pada": moon_pada,
        "reference_datetime": jd_ut_to_local_datetime(ref_jd, tz_name).isoformat(),
        "reference_kind": "sunrise" if rise_jd is not None else "fallback_06:00",
        "phase_illumination": (1.0 - cos(radians(diff))) / 2.0,
        "vara": vara,
        "nakshatra": nak,
        "yoga": yoga,
        "karana": karana,
        "sunrise_local": sunrise_dt.strftime("%H:%M"),
        "sunset_local": sunset_dt.strftime("%H:%M"),
        "rahu_kaal": f"{rk_start.strftime('%H:%M')} - {rk_end.strftime('%H:%M')}",
        "abhijit_muhurat": f"{abh_start.strftime('%H:%M')} - {abh_end.strftime('%H:%M')}",
        "slot_math_fallback": fallback,
        "offline_cacheable": True,
        "cache_ttl_seconds": 86400,
    }
