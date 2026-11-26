"""Question routing and spoken answers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import yaml

from app.api.schemas import (
    ChartResponse,
    ExplainedStatement,
    LanguageCode,
    LifeAreaCategory,
    WhyThisExplanation,
)
from app.interpretation.llm import LLMClientProtocol, SafeRephraser
from app.interpretation.question import answer_question
from app.interpretation.rules import Rule

AREA_ORDER: tuple[LifeAreaCategory, ...] = ("career", "relationships", "finances", "home")


class AskLexiconError(ValueError):
    pass


@dataclass(frozen=True)
class AreaLexicon:
    terms: dict[LifeAreaCategory, tuple[str, ...]]
    present_cues: tuple[str, ...]
    others: tuple[str, ...] = ()


def _matches(lowered: str, term: str) -> bool:
    if term.isascii():
        return re.search(rf"(?<![a-z]){re.escape(term.lower())}", lowered) is not None
    return term in lowered


def load_area_lexicon(path: str | Path) -> AreaLexicon:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AskLexiconError("lexicon must be a mapping")
    terms: dict[LifeAreaCategory, tuple[str, ...]] = {}
    for area in AREA_ORDER:
        raw = data.get(area)
        if not isinstance(raw, list) or not raw:
            raise AskLexiconError(f"lexicon missing terms for {area}")
        terms[area] = tuple(str(item) for item in raw)
    cues = data.get("present_cues")
    if not isinstance(cues, list) or not cues:
        raise AskLexiconError("lexicon missing present_cues")
    raw_others = data.get("others", [])
    if not isinstance(raw_others, list):
        raise AskLexiconError("lexicon others must be a list")
    unknown = set(data) - set(AREA_ORDER) - {"present_cues", "others"}
    if unknown:
        raise AskLexiconError(f"lexicon has unknown keys: {sorted(unknown)}")
    return AreaLexicon(
        terms=terms,
        present_cues=tuple(str(cue) for cue in cues),
        others=tuple(str(item) for item in raw_others),
    )


def classify_question(
    question: str, lexicon: AreaLexicon
) -> tuple[str | None, list[str]]:
    lowered = question.lower()
    scores: dict[LifeAreaCategory, list[str]] = {}
    for area in AREA_ORDER:
        hits = [term for term in lexicon.terms[area] if _matches(lowered, term)]
        if hits:
            scores[area] = hits
    if not scores:
        other_hits = [term for term in lexicon.others if _matches(lowered, term)]
        if other_hits:
            return "others", other_hits
        return None, []
    best = max(len(hits) for hits in scores.values())
    winners = [area for area, hits in scores.items() if len(hits) == best]
    if len(winners) != 1:
        return None, []
    area = winners[0]
    return area, scores[area]


def is_present_time_question(question: str, lexicon: AreaLexicon) -> bool:
    lowered = question.lower()
    return any(_matches(lowered, cue) for cue in lexicon.present_cues)


def infer_target_date(question: str, *, today: date) -> date | None:
    years = sorted({int(year) for year in re.findall(r"(?<!\d)(20\d{2})(?!\d)", question)})
    if len(years) != 1:
        return None
    candidate = date(years[0], 1, 15)
    try:
        upper = date(today.year + 3, today.month, today.day)
    except ValueError:  # 29 February has no counterpart three years on
        upper = date(today.year + 3, today.month, 28)
    return min(max(candidate, today), upper)


def iso_week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


@dataclass(frozen=True)
class AskResolution:
    area: str | None
    matched_terms: tuple[str, ...]
    canonical: ExplainedStatement | None
    display: ExplainedStatement | None
    context: tuple[ExplainedStatement, ...]
    llm_used: bool
    fallback_reason: str | None
    model: str | None = None


def bundle_hash_for(statement: ExplainedStatement) -> str:
    payload = "|".join(
        (
            statement.statement_id,
            statement.why_this.rule_id,
            statement.why_this.strength_grade,
            statement.time_window,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _compose_others(
    *,
    question: str,
    lang: LanguageCode,
    matched: list[str],
    rephraser: SafeRephraser | None,
    llm_client: LLMClientProtocol | None,
    chart: ChartResponse | None,
    dasha: Mapping[str, object] | None,
    transits: Mapping[str, object] | None,
) -> AskResolution:
    if chart is None:
        return AskResolution("others", tuple(matched), None, None, (), False, None)
    spoken, facts = answer_question(
        question=question,
        lang=lang,
        area="others",
        chart=chart,
        dasha=dasha,
        transits=transits,
    )
    end = str((dasha or {}).get("antardasha_end_date") or "")
    window = end[:10] if end else "current period"
    canonical = ExplainedStatement(
        statement_id=f"OTHERS_VEHICLE_{chart.lagna_sign_index}_{chart.moon_sign_index}",
        category="others",
        time_window=window,
        simple_text=spoken,
        pro_text=spoken,
        why_this=WhyThisExplanation(
            rule_id="RULE_TOPIC_VEHICLE",
            placement_evidence="Fourth-house and Venus vehicle signification",
            classical_source="BPHS Sukha-bhava vehicle signification",
            strength_grade="supported",
        ),
        safety_verified=True,
    )
    display = canonical
    llm_used = False
    fallback_reason: str | None = None
    model: str | None = None
    if rephraser is not None and llm_client is not None:
        outcome = rephraser.interpret_detailed(
            spoken,
            facts=facts,
            lang=lang,
            client=llm_client,
            voice="question",
        )
        llm_used = outcome.accepted
        fallback_reason = outcome.fallback_reason
        if outcome.accepted:
            display = canonical.model_copy(update={"simple_text": outcome.text})
            name = getattr(llm_client, "model_name", None)
            model = name if isinstance(name, str) and name.strip() else None
    return AskResolution(
        area="others",
        matched_terms=tuple(matched),
        canonical=canonical,
        display=display,
        context=(),
        llm_used=llm_used,
        fallback_reason=fallback_reason,
        model=model,
    )


def compose_answer(
    *,
    question: str,
    lang: LanguageCode,
    lexicon: AreaLexicon,
    statements_by_area: Mapping[LifeAreaCategory, list[ExplainedStatement]],
    daily_insight: ExplainedStatement | None,
    rephraser: SafeRephraser | None = None,
    llm_client: LLMClientProtocol | None = None,
    chart: ChartResponse | None = None,
    dasha: Mapping[str, object] | None = None,
    transits: Mapping[str, object] | None = None,
) -> AskResolution:
    area, matched = classify_question(question, lexicon)
    if area is None:
        return AskResolution(None, (), None, None, (), False, None)
    if area == "others":
        return _compose_others(
            question=question,
            lang=lang,
            matched=matched,
            rephraser=rephraser,
            llm_client=llm_client,
            chart=chart,
            dasha=dasha,
            transits=transits,
        )
    life_area = cast(LifeAreaCategory, area)
    candidates = statements_by_area.get(life_area) or []
    if not candidates:
        return AskResolution(area, tuple(matched), None, None, (), False, None)
    canonical = candidates[0]
    context: tuple[ExplainedStatement, ...] = (
        (daily_insight,) if daily_insight and is_present_time_question(question, lexicon) else ()
    )
    spoken, facts = answer_question(
        question=question,
        lang=lang,
        area=area,
        time_window=canonical.time_window,
        strength=canonical.why_this.strength_grade,
        chart=chart,
        dasha=dasha,
        transits=transits,
    )
    display = canonical.model_copy(update={"simple_text": spoken})
    llm_used = False
    fallback_reason: str | None = None
    model: str | None = None
    if rephraser is not None and llm_client is not None:
        outcome = rephraser.interpret_detailed(
            spoken,
            facts=facts,
            lang=lang,
            client=llm_client,
            voice="question",
        )
        llm_used = outcome.accepted
        fallback_reason = outcome.fallback_reason
        if outcome.accepted:
            display = canonical.model_copy(update={"simple_text": outcome.text})
            name = getattr(llm_client, "model_name", None)
            model = name if isinstance(name, str) and name.strip() else None
    return AskResolution(
        area=area,
        matched_terms=tuple(matched),
        canonical=canonical,
        display=display,
        context=context,
        llm_used=llm_used,
        fallback_reason=fallback_reason,
        model=model,
    )


def ask_ledger_entry_id(user_id: str, statement: ExplainedStatement) -> str:
    payload = f"{user_id}|{statement.statement_id}|{statement.time_window}"
    return "ASK-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def outcome_criteria_for(statement: ExplainedStatement, rules: list[Rule]) -> str:
    return next(
        (
            rule.observable_outcome_criteria
            for rule in rules
            if rule.id == statement.why_this.rule_id
        ),
        "",
    )
