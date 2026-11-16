from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import yaml

from app.api.schemas import ChartResponse


class KootaRow(TypedDict):
    koota: str
    max_points: float
    scored: float
    meaning: str


def _mangal(chart: ChartResponse) -> dict[str, object]:
    mars = next(p for p in chart.planets if p.planet == "Mars")
    from_lagna = mars.house
    from_moon = ((mars.sign_index - chart.moon_sign_index) % 12) + 1
    present = (from_lagna in {1, 2, 4, 7, 8, 12}) or (from_moon in {1, 2, 4, 7, 8, 12})
    cancellation = mars.sign_index in {1, 8, 10}
    return {
        "mars_house_from_lagna": from_lagna,
        "mars_house_from_moon": from_moon,
        "raw_mangal_indicator": present,
        "traditional_mitigation_present": cancellation,
        "contextual_note": (
            "Mars placement indicates high energy in partnerships. Traditional texts note "
            "multiple mitigations (own-sign placement, balanced partner charts). "
            "Treat as a conversation input, not a cause for alarm."
        ),
    }


def calculate_ashtakoota_match(
    a: ChartResponse,
    b: ChartResponse,
    tables_path: str | Path = "rules/ashtakoota_tables.yaml",
) -> dict[str, object]:
    tables = yaml.safe_load(Path(tables_path).read_text(encoding="utf-8"))
    sign_lord = {int(k): str(v) for k, v in tables["sign_lords"].items()}
    varna = {int(k): int(v) for k, v in tables["varna_by_sign"].items()}
    nak_gana = [int(x) for x in tables["nakshatra_gana"]]
    nak_nadi = [int(x) for x in tables["nakshatra_nadi"]]
    bhakoot_bad = {int(x) for x in tables["bhakoot_dosha_distances"]}

    ma = next(p for p in a.planets if p.planet == "Moon")
    mb = next(p for p in b.planets if p.planet == "Moon")
    sa, sb = ma.sign_index, mb.sign_index
    na, nb = ma.nakshatra_index - 1, mb.nakshatra_index - 1

    varna_score = 1.0 if varna[sa] >= varna[sb] else 0.5
    vashya = 2.0 if sa == sb or abs(sa - sb) in (2, 4, 6) else 1.0
    tara = 3.0 if (((nb - na) % 27) % 9) in (0, 1, 3, 5, 7, 8) else 1.5
    yoni = 4.0 if (na % 14) == (nb % 14) else (2.5 if abs((na % 14) - (nb % 14)) <= 4 else 1.0)
    maitri = 5.0 if sign_lord[sa] == sign_lord[sb] else 3.5
    ga, gb = nak_gana[na], nak_gana[nb]
    gana = 6.0 if ga == gb else (5.0 if {ga, gb} == {0, 1} else 1.0)
    bhakoot = 0.0 if (((sb - sa) % 12) + 1) in bhakoot_bad else 7.0
    nadi = 0.0 if nak_nadi[na] == nak_nadi[nb] else 8.0

    kootas: list[KootaRow] = [
        {
            "koota": "Varna",
            "max_points": 1.0,
            "scored": varna_score,
            "meaning": "Work ethic compatibility",
        },
        {"koota": "Vashya", "max_points": 2.0, "scored": vashya, "meaning": "Mutual support"},
        {"koota": "Tara", "max_points": 3.0, "scored": tara, "meaning": "Shared fortune"},
        {
            "koota": "Yoni",
            "max_points": 4.0,
            "scored": yoni,
            "meaning": "Instinctive responsiveness",
        },
        {
            "koota": "Graha Maitri",
            "max_points": 5.0,
            "scored": maitri,
            "meaning": "Mental friendship",
        },
        {"koota": "Gana", "max_points": 6.0, "scored": gana, "meaning": "Lifestyle style"},
        {"koota": "Bhakoot", "max_points": 7.0, "scored": bhakoot, "meaning": "Family growth"},
        {"koota": "Nadi", "max_points": 8.0, "scored": nadi, "meaning": "Vitality balance"},
    ]
    return {
        "total_score": round(sum(k["scored"] for k in kootas), 1),
        "max_score": 36.0,
        "koota_breakdown": kootas,
        "mangal_dosha_check": {"profile_a": _mangal(a), "profile_b": _mangal(b)},
        "method_limitations_note": (
            "Ashtakoota evaluates Moon Nakshatra and Rashi only. Traditional Jyotish also "
            "considers Lagna, D9, and mutual communication; treat scores as discussion inputs, "
            "not deterministic verdicts."
        ),
    }
