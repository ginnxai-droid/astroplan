"""Deterministic single-chart Yoga and Dosha detection driven by reviewed YAML rules."""

from __future__ import annotations

from app.api.schemas import (
    ChartResponse,
    ExplainedStatement,
    LanguageCode,
    WhyThisExplanation,
)
from app.interpretation.guardrails import verify_text
from app.interpretation.language import Catalog
from app.interpretation.phala import _g, _line, _matter
from app.interpretation.rules import Rule
from app.interpretation.terms import gloss


def detect_yogas_and_doshas(
    chart: ChartResponse,
    catalog: Catalog,
    lang: LanguageCode,
    rules: list[Rule] | None = None,
) -> list[ExplainedStatement]:
    rule_map: dict[str, Rule] = {r.id: r for r in (rules or [])}
    sun = next(p for p in chart.planets if p.planet == "Sun")
    moon = next(p for p in chart.planets if p.planet == "Moon")
    mars = next(p for p in chart.planets if p.planet == "Mars")
    mercury = next(p for p in chart.planets if p.planet == "Mercury")
    jupiter = next(p for p in chart.planets if p.planet == "Jupiter")

    results: list[ExplainedStatement] = []

    jup_from_moon = ((jupiter.sign_index - moon.sign_index) % 12) + 1
    if jup_from_moon in (1, 4, 7, 10):
        r_gk = rule_map.get("RULE_PARASHARI_YOGA_GAJAKESARI")
        source = r_gk.classical_source if r_gk else "Brihat Parashara Hora Shastra (BPHS), Ch. 36"
        simple = _line(
            "yoga_gajakesari_simple",
            lang,
            jup_sign=_g(jupiter.sign_name, lang),
            jup_h=jupiter.house,
            jup_nak=_g(jupiter.nakshatra_name, lang),
            jup_d9=_g(jupiter.navamsa_sign_name, lang),
            from_moon=jup_from_moon,
            moon_sign=_g(moon.sign_name, lang),
            moon_nak=_g(moon.nakshatra_name, lang),
            matter=_matter(jupiter.house, lang),
        )
        pro = _line(
            "yoga_gajakesari_pro",
            lang,
            jup_sign=_g(jupiter.sign_name, lang),
            jup_h=jupiter.house,
            jup_nak=_g(jupiter.nakshatra_name, lang),
            jup_pada=jupiter.pada,
            jup_d9=_g(jupiter.navamsa_sign_name, lang),
            from_moon=jup_from_moon,
            moon_sign=_g(moon.sign_name, lang),
            moon_h=moon.house,
            moon_nak=_g(moon.nakshatra_name, lang),
            moon_pada=moon.pada,
        )
        verify_text(simple, languages=(lang,))
        verify_text(pro, languages=(lang,))
        results.append(
            ExplainedStatement(
                statement_id=f"YOGA_GAJAKESARI_{chart.lagna_sign_index}_{moon.sign_index}",
                category="yoga",
                time_window="Natal Chart Pattern",
                simple_text=simple,
                pro_text=pro,
                why_this=WhyThisExplanation(
                    rule_id="RULE_PARASHARI_YOGA_GAJAKESARI",
                    placement_evidence=(
                        f"Jupiter in {gloss(jupiter.sign_name, lang)} "
                        f"({jup_from_moon}th from Moon in {gloss(moon.sign_name, lang)})"
                    ),
                    classical_source=source,
                    strength_grade="likely"
                    if jupiter.navamsa_sign_index in (4, 9, 12)
                    else "supported",
                ),
                safety_verified=True,
            )
        )

    if sun.sign_index == mercury.sign_index:
        r_ba = rule_map.get("RULE_PARASHARI_YOGA_BUDHADITYA")
        source = r_ba.classical_source if r_ba else "Phaladeepika, Ch. 6"
        simple = _line(
            "yoga_budhaditya_simple",
            lang,
            sun_nak=_g(sun.nakshatra_name, lang),
            merc_nak=_g(mercury.nakshatra_name, lang),
            merc_d9=_g(mercury.navamsa_sign_name, lang),
            sign=_g(sun.sign_name, lang),
            house=sun.house,
            matter=_matter(sun.house, lang),
        )
        pro = _line(
            "yoga_budhaditya_pro",
            lang,
            sun_nak=_g(sun.nakshatra_name, lang),
            sun_pada=sun.pada,
            sun_d9=_g(sun.navamsa_sign_name, lang),
            merc_nak=_g(mercury.nakshatra_name, lang),
            merc_pada=mercury.pada,
            merc_d9=_g(mercury.navamsa_sign_name, lang),
            sign=_g(sun.sign_name, lang),
            house=sun.house,
            lagna=_g(chart.lagna_sign_name, lang),
        )
        verify_text(simple, languages=(lang,))
        verify_text(pro, languages=(lang,))
        results.append(
            ExplainedStatement(
                statement_id=f"YOGA_BUDHADITYA_{sun.sign_index}",
                category="yoga",
                time_window="Natal Chart Pattern",
                simple_text=simple,
                pro_text=pro,
                why_this=WhyThisExplanation(
                    rule_id="RULE_PARASHARI_YOGA_BUDHADITYA",
                    placement_evidence=(
                        f"Sun and Mercury conjoined in {gloss(sun.sign_name, lang)} "
                        f"(House {sun.house})"
                    ),
                    classical_source=source,
                    strength_grade="supported",
                ),
                safety_verified=True,
            )
        )

    if jupiter.sign_index in (4, 9, 12) and jupiter.house in (1, 4, 7, 10):
        r_hm = rule_map.get("RULE_PARASHARI_YOGA_HAMSA")
        source = (
            r_hm.classical_source
            if r_hm
            else "Brihat Parashara Hora Shastra (BPHS), Ch. 75 (Pancha Mahapurusha)"
        )
        simple = _line(
            "yoga_hamsa_simple",
            lang,
            sign=_g(jupiter.sign_name, lang),
            house=jupiter.house,
            nak=_g(jupiter.nakshatra_name, lang),
            d9=_g(jupiter.navamsa_sign_name, lang),
            matter=_matter(jupiter.house, lang),
        )
        pro = _line(
            "yoga_hamsa_pro",
            lang,
            sign=_g(jupiter.sign_name, lang),
            lagna=_g(chart.lagna_sign_name, lang),
            house=jupiter.house,
            nak=_g(jupiter.nakshatra_name, lang),
            pada=jupiter.pada,
            d9=_g(jupiter.navamsa_sign_name, lang),
        )
        verify_text(simple, languages=(lang,))
        verify_text(pro, languages=(lang,))
        results.append(
            ExplainedStatement(
                statement_id=f"YOGA_HAMSA_{jupiter.sign_index}_{jupiter.house}",
                category="yoga",
                time_window="Natal Chart Pattern",
                simple_text=simple,
                pro_text=pro,
                why_this=WhyThisExplanation(
                    rule_id="RULE_PARASHARI_YOGA_HAMSA",
                    placement_evidence=(
                        f"Jupiter in {gloss(jupiter.sign_name, lang)} "
                        f"(House {jupiter.house} Kendra in own/exalted sign)"
                    ),
                    classical_source=source,
                    strength_grade="likely",
                ),
                safety_verified=True,
            )
        )

    mars_from_moon = ((mars.sign_index - moon.sign_index) % 12) + 1
    if mars.house in (1, 2, 4, 7, 8, 12) or mars_from_moon in (1, 2, 4, 7, 8, 12):
        r_mg = rule_map.get("RULE_PARASHARI_MANGAL_CONTEXT")
        text_key = r_mg.text_key if r_mg else "dosha.mangal_context"
        source = r_mg.classical_source if r_mg else "Brihat Parashara Hora Shastra (BPHS), Ch. 80"
        mitigated = mars.sign_index in (1, 8, 10)
        simple = _line(
            "dosha_mangal_mitigated" if mitigated else "dosha_mangal_active",
            lang,
            sign=_g(mars.sign_name, lang),
            house=mars.house,
            m_house=mars_from_moon,
            nak=_g(mars.nakshatra_name, lang),
            d9=_g(mars.navamsa_sign_name, lang),
            matter=_matter(mars.house, lang),
        )
        pro = catalog.format(
            f"{text_key}.pro",
            lang,
            mars_house=mars.house,
            mars_moon_house=mars_from_moon,
        )
        verify_text(simple, languages=(lang,))
        verify_text(pro, languages=(lang,))
        results.append(
            ExplainedStatement(
                statement_id=f"DOSHA_MANGAL_CONTEXT_{mars.house}",
                category="dosha_context",
                time_window="Natal Partnership Context",
                simple_text=simple,
                pro_text=pro,
                why_this=WhyThisExplanation(
                    rule_id="RULE_PARASHARI_MANGAL_CONTEXT",
                    placement_evidence=(
                        f"Mars in {gloss(mars.sign_name, lang)} (House {mars.house} from Lagna, "
                        f"House {mars_from_moon} from Moon)"
                    ),
                    classical_source=source,
                    strength_grade="weak" if mitigated else "contested",
                ),
                safety_verified=True,
            )
        )

    return results
