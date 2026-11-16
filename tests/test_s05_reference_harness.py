import pytest

from tests.reference_harness import (
    AYANAMSA_TOL_DEG,
    LAGNA_LON_TOL_DEG,
    PLANET_LON_TOL_DEG,
    REFERENCE_SOFTWARE_STANDARD,
    load_reference_fixture,
    verify_reference_entry,
)

pytestmark = pytest.mark.s05


def test_harness_validates_seeded_reference_and_tolerances() -> None:
    assert "swetest v2.10.03" in REFERENCE_SOFTWARE_STANDARD
    assert PLANET_LON_TOL_DEG == 0.01 and LAGNA_LON_TOL_DEG == 0.05 and AYANAMSA_TOL_DEG == 0.005
    entries = load_reference_fixture()
    assert len(entries) >= 1
    for e in entries:
        assert verify_reference_entry(e) == []
