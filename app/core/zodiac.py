from __future__ import annotations

from app.core.constants import NAKSHATRA_NAMES, RASHI_NAMES


def sign_index_from_longitude(lon: float) -> int:
    return int((lon % 360.0) / 30.0) + 1


def degree_in_sign(lon: float) -> float:
    return (lon % 360.0) % 30.0


def nakshatra_and_pada(lon: float) -> tuple[int, str, int]:
    lon = lon % 360.0
    quarter = int(lon / (360.0 / 108.0))
    zero, pada = divmod(quarter, 4)
    return zero + 1, NAKSHATRA_NAMES[zero], pada + 1


def navamsa_sign_index(lon: float) -> int:
    return (int((lon % 360.0) / (360.0 / 108.0)) % 12) + 1


def whole_sign_house(planet_sign: int, lagna_sign: int) -> int:
    return ((planet_sign - lagna_sign) % 12) + 1


def sign_name(idx: int) -> str:
    return RASHI_NAMES[idx - 1]
