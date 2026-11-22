from __future__ import annotations

from dataclasses import dataclass

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
from app.interpretation.phala import area_reading, daily_reading
from app.interpretation.rules import Rule
from app.interpretation.terms import gloss


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
    ctx = _ctx(chart, dasha, transits)
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
        simple = area_reading(chart, dasha, transits, lang, rule.category)
        pro = catalog.get(f"{rule.text_key}.pro", lang)
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


def generate_daily_insight(
    chart: ChartResponse,
    panchang: dict[str, object],
    transits: dict[str, object],
    catalog: Catalog,
    lang: LanguageCode,
) -> ExplainedStatement:
    moon_house = int(str(transits["moon_house_from_natal_moon"]))
    transit_moon_sign = str(transits["moon_transit_sign"])
    tithi = str(panchang["tithi"])
    yoga = str(panchang["yoga"])
    date_str = str(panchang["date"])

    simple = daily_reading(chart, panchang, transits, lang)
    pro = catalog.format(
        "daily_insight.pro",
        lang,
        transit_moon_sign=transit_moon_sign,
        moon_house=moon_house,
        natal_moon=chart.moon_sign_name,
        tithi=tithi,
        yoga=yoga,
    )
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
