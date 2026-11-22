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
        name="Partner A",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
    )
    p2 = BirthDetailsInput(
        birth_date=date(1996, 8, 12),
        birth_time=time(18, 45),
        name="Partner B",
        place_name="Mumbai",
        country="India",
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


def test_partnership_reading_uses_both_charts_and_both_dashas() -> None:
    from app.core.dasha import calculate_vimshottari_dasha
    from app.interpretation.match_reading import describe_partnership

    p1 = BirthDetailsInput(
        birth_date=date(1994, 3, 21),
        birth_time=time(9, 15),
        name="Asha",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
        language="mr",
    )
    p2 = BirthDetailsInput(
        birth_date=date(1996, 8, 12),
        birth_time=time(18, 45),
        name="Nutan",
        place_name="Mumbai",
        country="India",
        latitude=19.0760,
        longitude=72.8777,
        language="mr",
    )
    c1 = calculate_chart(p1, 18.5204, 73.8567, "Asia/Kolkata")
    c2 = calculate_chart(p2, 19.0760, 72.8777, "Asia/Kolkata")
    today = date(2026, 11, 22)
    moon1 = next(p for p in c1.planets if p.planet == "Moon")
    moon2 = next(p for p in c2.planets if p.planet == "Moon")
    report = describe_partnership(
        c1,
        c2,
        calculate_vimshottari_dasha(p1.birth_date, moon1.longitude, today),
        calculate_vimshottari_dasha(p2.birth_date, moon2.longitude, today),
        calculate_ashtakoota_match(c1, c2),
        name_a="Asha",
        name_b="Nutan",
        place_a="Pune",
        place_b="Mumbai",
        when_a="1994-03-21 09:15",
        when_b="1996-08-12 18:45",
        lang="mr",
        already_married=True,
        on_date=today,
    )
    sections = report["sections"]
    assert isinstance(sections, list) and len(sections) == 6
    titles = [str(section["title"]) for section in sections]  # type: ignore[index]
    assert titles == [
        "स्वभाव",
        "नाते",
        "विवाहाची सध्याची स्थिती",
        "ताण आणि काय करावे",
        "सध्याची ग्रहगती",
        "दशा आणि आचरण",
    ]
    joined = " ".join(str(section["text"]) for section in sections)  # type: ignore[index]
    assert "Asha" in joined and "Nutan" in joined
    assert c1.lagna_sign_name in joined and c2.lagna_sign_name in joined
    assert "सप्तम" in joined and "गोचर" in joined and "आधीच विवाहित" in joined
    assert report["already_married"] is True
    people = report["people"]
    assert isinstance(people, list) and len(people) == 2
    assert "Pune" in str(people[0]["birth"])  # type: ignore[index]
    assert "Mumbai" in str(people[1]["birth"])  # type: ignore[index]
