from datetime import date

import pytest

from app.core.dasha import calculate_vimshottari_dasha

pytestmark = pytest.mark.s06


def test_dasha_reference_boundaries_and_120_year_cycle() -> None:
    birth = date(2000, 1, 1)
    d = calculate_vimshottari_dasha(birth, 0.0, date(2000, 6, 1))
    timeline = d["timeline"]  # type: ignore[assignment]
    assert len(timeline) == 9  # type: ignore[arg-type]
    assert timeline[0]["mahadasha_lord"] == "Ketu"  # type: ignore[index]
    assert timeline[0]["start_date"] == "2000-01-01"  # type: ignore[index]
    assert timeline[0]["end_date"] == "2007-01-01"  # type: ignore[index]
    assert timeline[1]["mahadasha_lord"] == "Venus"  # type: ignore[index]
    assert timeline[1]["end_date"] == "2027-01-01"  # type: ignore[index]
    assert d["active_mahadasha"] == "Ketu"
    assert d["active_antardasha"] in {"Ketu", "Venus"}
