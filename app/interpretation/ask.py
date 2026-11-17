"""Deterministic question routing, no model involvement."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

from app.api.schemas import LifeAreaCategory

AREA_ORDER: tuple[LifeAreaCategory, ...] = ("career", "relationships", "finances", "home")


class AskLexiconError(ValueError):
    pass


@dataclass(frozen=True)
class AreaLexicon:
    terms: dict[LifeAreaCategory, tuple[str, ...]]
    present_cues: tuple[str, ...]


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
    unknown = set(data) - set(AREA_ORDER) - {"present_cues"}
    if unknown:
        raise AskLexiconError(f"lexicon has unknown keys: {sorted(unknown)}")
    return AreaLexicon(terms=terms, present_cues=tuple(str(cue) for cue in cues))


def classify_question(
    question: str, lexicon: AreaLexicon
) -> tuple[LifeAreaCategory | None, list[str]]:
    lowered = question.lower()
    scores: dict[LifeAreaCategory, list[str]] = {}
    for area in AREA_ORDER:
        hits = [term for term in lexicon.terms[area] if _matches(lowered, term)]
        if hits:
            scores[area] = hits
    if not scores:
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
