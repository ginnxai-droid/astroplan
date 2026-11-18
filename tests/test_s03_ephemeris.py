from math import nextafter

import pytest

from app.config import Settings
from app.core.ephemeris import configure
from app.core.zodiac import nakshatra_and_pada, navamsa_sign_index, whole_sign_house

pytestmark = pytest.mark.s03


def test_production_refuses_moshier() -> None:
    with pytest.raises(RuntimeError, match="G1"):
        configure(Settings(env="dev", require_swiss_files=True, ephe_path=""))


def test_dev_accepts_moshier() -> None:
    configure(Settings(env="dev"))


def test_navamsa_boundaries() -> None:
    assert navamsa_sign_index(0.5) == 1
    assert navamsa_sign_index(3.5) == 2


def test_nakshatra_pada() -> None:
    _idx, name, pada = nakshatra_and_pada(100.0)
    assert name == "Pushya" and 1 <= pada <= 4


@pytest.mark.parametrize(
    "longitude,expected",
    [
        (nextafter(180.0, 0.0), (14, "Chitra", 2)),
        (180.0, (14, "Chitra", 3)),
        (nextafter(270.0, 0.0), (21, "Uttara Ashadha", 1)),
        (270.0, (21, "Uttara Ashadha", 2)),
        (-180.0, (14, "Chitra", 3)),
        (360.0, (1, "Ashwini", 1)),
    ],
)
def test_exact_pada_boundary_is_not_rounded_into_previous_quarter(longitude, expected) -> None:
    assert nakshatra_and_pada(longitude) == expected


def test_whole_sign_wraps() -> None:
    assert whole_sign_house(1, 4) == 10
    assert whole_sign_house(4, 4) == 1
