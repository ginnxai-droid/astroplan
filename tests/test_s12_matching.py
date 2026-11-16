from datetime import date, time

import pytest

from app.api.schemas import BirthDetailsInput, MatchingInput
from app.core.chart import calculate_chart
from app.core.matching import calculate_ashtakoota_match

pytestmark = pytest.mark.s12


def test_matching_score_breakdown_and_partner_consent_gate() -> None:
    p1 = BirthDetailsInput(
        birth_date=date(1994, 3, 21),
        birth_time=time(9, 15),
        place_name="Pune",
        latitude=18.5204,
        longitude=73.8567,
    )
    p2 = BirthDetailsInput(
        birth_date=date(1996, 8, 12),
        birth_time=time(18, 45),
        place_name="Mumbai",
        latitude=19.0760,
        longitude=72.8777,
    )
    with pytest.raises(ValueError, match="partner_consent_required"):
        MatchingInput(profile_a=p1, profile_b=p2, partner_consent_confirmed=False)

    c1 = calculate_chart(p1, 18.5204, 73.8567, "Asia/Kolkata")
    c2 = calculate_chart(p2, 19.0760, 72.8777, "Asia/Kolkata")
    m = calculate_ashtakoota_match(c1, c2)
    assert 0.0 <= float(str(m["total_score"])) <= 36.0
    assert m["max_score"] == 36.0
    assert len(m["koota_breakdown"]) == 8  # type: ignore[arg-type]
