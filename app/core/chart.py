from __future__ import annotations

from datetime import date, datetime, time, timedelta

import swisseph as swe

from app.api.schemas import BirthDetailsInput, ChartResponse, PlanetPosition
from app.core.constants import (
    DAYS_PER_YEAR,
    NAKSHATRA_NAMES,
    RASHI_NAMES,
    VIMSHOTTARI_SEQUENCE,
)
from app.core.ephemeris import (
    ayanamsa_ut,
    sidereal_lagna,
    sidereal_longitudes,
    sidereal_nodes,
)
from app.core.timeutil import local_to_utc
from app.core.zodiac import (
    degree_in_sign,
    nakshatra_and_pada,
    navamsa_sign_index,
    sign_index_from_longitude,
    sign_name,
    whole_sign_house,
)


def _jd_ut(birth_date: date, birth_time: time, tz_name: str) -> tuple[float, datetime]:
    utc = local_to_utc(birth_date, birth_time, tz_name)
    jd = float(
        swe.julday(
            utc.year,
            utc.month,
            utc.day,
            utc.hour + utc.minute / 60.0 + utc.second / 3600.0,
        )
    )
    return jd, utc


def _build(name: str, lon: float, speed: float, lagna_idx: int) -> PlanetPosition:
    sign_idx = sign_index_from_longitude(lon)
    nk_idx, nk_name, pada = nakshatra_and_pada(lon)
    d9 = navamsa_sign_index(lon)
    return PlanetPosition(
        planet=name,
        longitude=round(lon, 4),
        sign_index=sign_idx,
        sign_name=sign_name(sign_idx),
        degree_in_sign=round(degree_in_sign(lon), 4),
        house=whole_sign_house(sign_idx, lagna_idx),
        nakshatra_index=nk_idx,
        nakshatra_name=nk_name,
        pada=pada,
        navamsa_sign_index=d9,
        navamsa_sign_name=sign_name(d9),
        is_retrograde=(speed < 0),
    )


def _starting_dasha_balance_days(moon_lon: float) -> tuple[str, int]:
    span = 360.0 / 27.0
    lon = moon_lon % 360.0
    nak_idx = int(lon / span)
    rem = 1.0 - ((lon - nak_idx * span) / span)
    lord, years = VIMSHOTTARI_SEQUENCE[nak_idx % 9]
    return lord, round(years * rem * DAYS_PER_YEAR)


def _uncertainty_warning(
    details: BirthDetailsInput,
    lat: float,
    lon: float,
    tz_name: str,
    base_lagna: int,
    base_nak: int,
    base_moon_lon: float,
) -> str | None:
    if details.uncertainty_minutes <= 0:
        return None
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    base = local_to_utc(details.birth_date, details.birth_time, tz_name)
    base_lord, base_days = _starting_dasha_balance_days(base_moon_lon)
    warnings: list[str] = []
    for delta in (-details.uncertainty_minutes, details.uncertainty_minutes):
        s = base + timedelta(minutes=delta)
        jd = float(swe.julday(s.year, s.month, s.day, s.hour + s.minute / 60.0 + s.second / 3600.0))
        lag = sign_index_from_longitude(sidereal_lagna(jd, lat, lon))
        moon, _ = swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL | swe.FLG_SPEED)
        m_lon = float(moon[0]) % 360.0
        nak, _, _ = nakshatra_and_pada(m_lon)
        shift_lord, shift_days = _starting_dasha_balance_days(m_lon)
        if lag != base_lagna:
            warnings.append(
                f"Lagna changes to {RASHI_NAMES[lag - 1]} within "
                f"±{details.uncertainty_minutes} min window."
            )
        if nak != base_nak:
            warnings.append(
                f"Moon Nakshatra shifts to {NAKSHATRA_NAMES[nak - 1]} (Dasha lord {shift_lord}) "
                f"within ±{details.uncertainty_minutes} min window."
            )
        elif abs(shift_days - base_days) >= 15:
            warnings.append(
                f"Vimshottari {base_lord} Dasha balance shifts by "
                f"±{abs(shift_days - base_days)} days "
                f"within ±{details.uncertainty_minutes} min window."
            )
    return " ".join(sorted(set(warnings))) or None


def calculate_chart(
    details: BirthDetailsInput, lat: float, lon: float, tz_name: str
) -> ChartResponse:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    jd, utc = _jd_ut(details.birth_date, details.birth_time, tz_name)
    ayan = ayanamsa_ut(jd)
    lagna_lon = sidereal_lagna(jd, lat, lon)
    lagna_idx = sign_index_from_longitude(lagna_lon)

    planets = [
        _build(r.planet, r.longitude_sidereal, r.speed_longitude, lagna_idx)
        for r in sidereal_longitudes(jd)
    ]
    rahu_lon, ketu_lon = sidereal_nodes(jd, true_node=(details.node_type == "TRUE"))
    planets.append(_build("Rahu", rahu_lon, -0.05, lagna_idx))
    planets.append(_build("Ketu", ketu_lon, -0.05, lagna_idx))

    moon = next(p for p in planets if p.planet == "Moon")
    warning = _uncertainty_warning(
        details, lat, lon, tz_name, lagna_idx, moon.nakshatra_index, moon.longitude
    )

    return ChartResponse(
        input_summary=details,
        resolved_latitude=lat,
        resolved_longitude=lon,
        resolved_timezone=tz_name,
        utc_datetime=utc,
        ayanamsa_name="Lahiri",
        ayanamsa_value=round(ayan, 4),
        lagna_sign_index=lagna_idx,
        lagna_sign_name=sign_name(lagna_idx),
        lagna_degree=round(degree_in_sign(lagna_lon), 4),
        moon_sign_index=moon.sign_index,
        moon_sign_name=moon.sign_name,
        moon_nakshatra=moon.nakshatra_name,
        moon_pada=moon.pada,
        boundary_warning=warning,
        planets=planets,
    )
