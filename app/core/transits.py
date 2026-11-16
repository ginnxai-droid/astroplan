from __future__ import annotations

from datetime import date, time

import swisseph as swe

from app.api.schemas import ChartResponse
from app.core.constants import RASHI_NAMES
from app.core.ephemeris import sidereal_longitudes
from app.core.timeutil import local_to_utc
from app.core.zodiac import nakshatra_and_pada, sign_index_from_longitude

PHASE_DESCRIPTIONS: dict[int, str] = {
    12: "Rising Phase (12th from Natal Moon) — focus on steady routines and rest",
    1: "Peak Phase (1st over Natal Moon) — structured responsibility and maturity",
    2: "Setting Phase (2nd from Natal Moon) — consolidation of financial and family commitments",
}


def evaluate_current_transits(chart: ChartResponse, target_date: date) -> dict[str, object]:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    utc = local_to_utc(target_date, time(12, 0), "UTC")
    jd = float(swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60.0))
    planets = {p.planet: p.longitude_sidereal for p in sidereal_longitudes(jd)}
    sat = sign_index_from_longitude(planets["Saturn"])
    jup = sign_index_from_longitude(planets["Jupiter"])
    moon_transit = sign_index_from_longitude(planets["Moon"])
    _, moon_transit_nak, _ = nakshatra_and_pada(planets["Moon"])

    sat_house = ((sat - chart.moon_sign_index) % 12) + 1
    jup_house = ((jup - chart.moon_sign_index) % 12) + 1
    moon_house = ((moon_transit - chart.moon_sign_index) % 12) + 1

    return {
        "target_date": target_date.isoformat(),
        "saturn_transit_sign": RASHI_NAMES[sat - 1],
        "saturn_house_from_moon": sat_house,
        "jupiter_transit_sign": RASHI_NAMES[jup - 1],
        "jupiter_house_from_moon": jup_house,
        "moon_transit_sign": RASHI_NAMES[moon_transit - 1],
        "moon_transit_nakshatra": moon_transit_nak,
        "moon_house_from_natal_moon": moon_house,
        "sade_sati": {
            "is_active": sat_house in (12, 1, 2),
            "phase_key": f"sade_sati.house_{sat_house}"
            if sat_house in (12, 1, 2)
            else "sade_sati.inactive",
            "phase_description": PHASE_DESCRIPTIONS.get(
                sat_house,
                "Saturn is not in 12th/1st/2nd from Natal Moon (Sade Sati inactive).",
            ),
        },
    }
