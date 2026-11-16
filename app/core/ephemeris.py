"""Thin Swiss Ephemeris wrapper. Production refuses Moshier fallback (G1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import swisseph as swe

from app.config import Settings

PLANET_CODES: dict[str, int] = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
}


@dataclass(frozen=True)
class RawPlanet:
    planet: str
    longitude_sidereal: float
    speed_longitude: float


def configure(settings: Settings) -> None:
    if settings.ephe_path:
        swe.set_ephe_path(str(Path(settings.ephe_path).resolve()))
    if settings.require_swiss_files:
        if not settings.ephe_path:
            raise RuntimeError("G1: require_swiss_files true but ephe_path empty")
        if not any(Path(settings.ephe_path).glob("se*.se1")):
            raise RuntimeError(f"G1: no se*.se1 in {settings.ephe_path}; refusing Moshier")
    swe.set_sid_mode(swe.SIDM_LAHIRI)


def ayanamsa_ut(jd_ut: float) -> float:
    return float(swe.get_ayanamsa_ut(jd_ut))


def sidereal_longitudes(jd_ut: float) -> list[RawPlanet]:
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    out: list[RawPlanet] = []
    for name, code in PLANET_CODES.items():
        values, _ = swe.calc_ut(jd_ut, code, flags)
        out.append(RawPlanet(name, float(values[0]) % 360.0, float(values[3])))
    return out


def sidereal_nodes(jd_ut: float, *, true_node: bool) -> tuple[float, float]:
    code = swe.TRUE_NODE if true_node else swe.MEAN_NODE
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    values, _ = swe.calc_ut(jd_ut, code, flags)
    rahu = float(values[0]) % 360.0
    return rahu, (rahu + 180.0) % 360.0


def sidereal_lagna(jd_ut: float, lat: float, lon: float) -> float:
    _, ascmc = swe.houses_ex(jd_ut, lat, lon, b"W", swe.FLG_SIDEREAL)
    return float(ascmc[0]) % 360.0


def sunrise_sunset_jd_ut(
    jd_ref: float, lat: float, lon: float
) -> tuple[float | None, float | None]:
    geo = (lon, lat, 0.0)
    try:
        rise = swe.rise_trans(jd_ref - 0.25, swe.SUN, swe.CALC_RISE | swe.BIT_DISC_CENTER, geo)
        setr = swe.rise_trans(jd_ref, swe.SUN, swe.CALC_SET | swe.BIT_DISC_CENTER, geo)
        return (
            float(rise[1][0]) if rise[0] == 0 else None,
            float(setr[1][0]) if setr[0] == 0 else None,
        )
    except Exception:
        return None, None
