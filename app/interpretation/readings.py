from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.api.schemas import (
    ChartResponse,
    ExplainedStatement,
    LanguageCode,
    LifeAreaCategory,
    PlanetPosition,
    WhyThisExplanation,
)
from app.interpretation.guardrails import verify_text
from app.interpretation.language import Catalog
from app.interpretation.phala import (
    area_pro_reading,
    daily_area_human,
    daily_area_reading,
    daily_human_reading,
    daily_pro_reading,
    house_matter,
    period_area_human,
)
from app.interpretation.rules import Rule
from app.interpretation.terms import gloss

_IMPACT: dict[str, dict[str, list[str]]] = json.loads(
    Path(__file__).with_name("life_impact.json").read_text(encoding="utf-8")
)
_IMPACT_PLANETS = (
    "Sun",
    "Moon",
    "Mars",
    "Mercury",
    "Jupiter",
    "Venus",
    "Saturn",
    "Rahu",
    "Ketu",
)
_LANG_IDX = {"en": 0, "hi": 1, "mr": 2}


def life_impact_text(chart: ChartResponse, lang: LanguageCode) -> str:
    """Everyday house impact: what helps, what needs care, and a takeaway."""
    idx = _LANG_IDX[lang]
    parts: list[str] = []
    for name in _IMPACT_PLANETS:
        planet = next(item for item in chart.planets if item.planet == name)
        matter = house_matter(planet.house, lang)
        block = _IMPACT[name]
        for key in ("helps", "care", "take"):
            parts.append(block[key][idx].format(house=planet.house, matter=matter))
    text = " ".join(parts)
    verify_text(text, languages=(lang,))
    return text


@dataclass(frozen=True)
class _Ctx:
    sun_sign: str
    sun_house: int
    sun_navamsa: str
    venus_sign: str
    venus_house: int
    venus_navamsa: str
    jup_sign: str
    jup_house: int
    jup_transit: int
    moon_sign: str
    moon_house: int
    moon_nak: str
    moon_pada: int
    md: str
    ad: str
    ad_end_date: str


def _ctx(chart: ChartResponse, dasha: dict[str, object], transits: dict[str, object]) -> _Ctx:
    def by(n: str) -> PlanetPosition:
        return next(p for p in chart.planets if p.planet == n)

    s, v, j, m = by("Sun"), by("Venus"), by("Jupiter"), by("Moon")
    return _Ctx(
        sun_sign=s.sign_name,
        sun_house=s.house,
        sun_navamsa=s.navamsa_sign_name,
        venus_sign=v.sign_name,
        venus_house=v.house,
        venus_navamsa=v.navamsa_sign_name,
        jup_sign=j.sign_name,
        jup_house=j.house,
        jup_transit=int(str(transits["jupiter_house_from_moon"])),
        moon_sign=m.sign_name,
        moon_house=m.house,
        moon_nak=m.nakshatra_name,
        moon_pada=m.pada,
        md=str(dasha["active_mahadasha"]),
        ad=str(dasha["active_antardasha"]),
        ad_end_date=str(dasha["antardasha_end_date"]),
    )


def generate_life_area_readings(
    chart: ChartResponse,
    dasha: dict[str, object],
    transits: dict[str, object],
    rules: list[Rule],
    catalog: Catalog,
    lang: LanguageCode,
) -> dict[LifeAreaCategory, list[ExplainedStatement]]:
    del catalog
    ctx = _ctx(chart, dasha, transits)
    impact = life_impact_text(chart, lang)
    window = f"Active {ctx.md}-{ctx.ad} Dasha (until {ctx.ad_end_date})"
    out: dict[LifeAreaCategory, list[ExplainedStatement]] = {
        "career": [],
        "relationships": [],
        "finances": [],
        "home": [],
    }
    for rule in rules:
        if rule.category not in out:
            continue
        simple = period_area_human(chart, dasha, transits, lang, rule.category)
        pro = f"{area_pro_reading(chart, dasha, transits, lang, rule.category)} {impact}"
        verify_text(simple, languages=(lang,))
        verify_text(pro, languages=(lang,))
        evidence = rule.evidence_template.format(
            **{name: gloss(value, lang) for name, value in vars(ctx).items()}
        )
        out[rule.category].append(
            ExplainedStatement(
                statement_id=f"{rule.id}_{chart.lagna_sign_index}_{chart.moon_sign_index}",
                category=rule.category,
                time_window=window,
                simple_text=simple,
                pro_text=pro,
                why_this=WhyThisExplanation(
                    rule_id=rule.id,
                    placement_evidence=evidence,
                    classical_source=rule.classical_source,
                    strength_grade=rule.strength_grade,
                ),
                safety_verified=True,
            )
        )
    return out


def generate_daily_area_readings(
    chart: ChartResponse,
    dasha: dict[str, object],
    transits: dict[str, object],
    panchang: dict[str, object],
    rules: list[Rule],
    lang: LanguageCode,
) -> dict[LifeAreaCategory, list[ExplainedStatement]]:
    ctx = _ctx(chart, dasha, transits)
    date_str = str(panchang["date"])
    window = f"{date_str} · {ctx.md}-{ctx.ad} Dasha"
    out: dict[LifeAreaCategory, list[ExplainedStatement]] = {
        "career": [],
        "relationships": [],
        "finances": [],
        "home": [],
    }
    for rule in rules:
        if rule.category not in out:
            continue
        simple = daily_area_human(chart, dasha, transits, panchang, lang, rule.category)
        _, pro = daily_area_reading(chart, dasha, transits, panchang, lang, rule.category)
        verify_text(simple, languages=(lang,))
        evidence = rule.evidence_template.format(
            **{name: gloss(value, lang) for name, value in vars(ctx).items()}
        )
        out[rule.category].append(
            ExplainedStatement(
                statement_id=(
                    f"DAILY_{rule.id}_{date_str}_{chart.lagna_sign_index}_{chart.moon_sign_index}"
                ),
                category=rule.category,
                time_window=window,
                simple_text=simple,
                pro_text=pro,
                why_this=WhyThisExplanation(
                    rule_id=rule.id,
                    placement_evidence=evidence,
                    classical_source=rule.classical_source,
                    strength_grade=rule.strength_grade,
                ),
                safety_verified=True,
            )
        )
    return out


def generate_daily_insight(
    chart: ChartResponse,
    panchang: dict[str, object],
    transits: dict[str, object],
    catalog: Catalog,
    lang: LanguageCode,
    dasha: dict[str, object] | None = None,
) -> ExplainedStatement:
    del catalog
    moon_house = int(str(transits["moon_house_from_natal_moon"]))
    transit_moon_sign = str(transits["moon_transit_sign"])
    tithi = str(panchang["tithi"])
    date_str = str(panchang["date"])

    simple = daily_human_reading(chart, panchang, transits, lang, dasha=dasha)
    pro = daily_pro_reading(chart, panchang, transits, lang, dasha=dasha)
    verify_text(simple, languages=(lang,))
    verify_text(pro, languages=(lang,))

    grade = "likely" if moon_house in (1, 3, 6, 10, 11) else "supported"
    return ExplainedStatement(
        statement_id=f"DAILY_INSIGHT_{date_str}_{chart.moon_sign_index}_{moon_house}",
        category="daily_insight",
        time_window=date_str,
        simple_text=simple,
        pro_text=pro,
        why_this=WhyThisExplanation(
            rule_id="RULE_GOCHARA_CHANDRA_DAILY",
            placement_evidence=(
                f"Transit Moon in {gloss(transit_moon_sign, lang)} "
                f"(House {moon_house} from Natal Moon in {gloss(chart.moon_sign_name, lang)}); "
                f"Tithi: {gloss(tithi, lang)}"
            ),
            classical_source="Phaladeepika, Ch. 26 (Chandra Gochara)",
            strength_grade=grade,
        ),
        safety_verified=True,
    )
