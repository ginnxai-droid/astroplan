"""Deterministic single-chart Yoga and Dosha detection driven by reviewed YAML rules (Gap 3, N7)."""

from __future__ import annotations

from app.api.schemas import (
    ChartResponse,
    ExplainedStatement,
    LanguageCode,
    WhyThisExplanation,
)
from app.interpretation.guardrails import verify_text
from app.interpretation.language import Catalog
from app.interpretation.rules import Rule


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
        text_key = r_gk.text_key if r_gk else "yoga.gajakesari"
        source = r_gk.classical_source if r_gk else "Brihat Parashara Hora Shastra (BPHS), Ch. 36"
        simple = catalog.get(f"{text_key}.simple", lang)
        pro = catalog.get(f"{text_key}.pro", lang)
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
                        f"Jupiter in {jupiter.sign_name} "
                        f"({jup_from_moon}th from Moon in {moon.sign_name})"
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
        text_key = r_ba.text_key if r_ba else "yoga.budhaditya"
        source = r_ba.classical_source if r_ba else "Phaladeepika, Ch. 6"
        simple = catalog.get(f"{text_key}.simple", lang)
        pro = catalog.get(f"{text_key}.pro", lang)
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
                        f"Sun and Mercury conjoined in {sun.sign_name} (House {sun.house})"
                    ),
                    classical_source=source,
                    strength_grade="supported",
                ),
                safety_verified=True,
            )
        )

    if jupiter.sign_index in (4, 9, 12) and jupiter.house in (1, 4, 7, 10):
        r_hm = rule_map.get("RULE_PARASHARI_YOGA_HAMSA")
        text_key = r_hm.text_key if r_hm else "yoga.hamsa"
        source = (
            r_hm.classical_source
            if r_hm
            else "Brihat Parashara Hora Shastra (BPHS), Ch. 75 (Pancha Mahapurusha)"
        )
        simple = catalog.get(f"{text_key}.simple", lang)
        pro = catalog.get(f"{text_key}.pro", lang)
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
                        f"Jupiter in {jupiter.sign_name} "
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
        simple = catalog.get(f"{text_key}.simple", lang)
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
                        f"Mars in {mars.sign_name} (House {mars.house} from Lagna, "
                        f"House {mars_from_moon} from Moon)"
                    ),
                    classical_source=source,
                    strength_grade="weak" if mitigated else "contested",
                ),
                safety_verified=True,
            )
        )

    return results
