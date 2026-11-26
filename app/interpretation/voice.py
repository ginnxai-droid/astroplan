"""How a jyotish speaks to the person sitting with them.

Simple Today is two short paragraphs: the weekday, then one supportive
planet when the engine names one. The model prompt and the fallback
both follow this guide. A planet is named only inside a life sentence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_DATA: dict[str, Any] = json.loads(
    Path(__file__).with_name("voice.json").read_text(encoding="utf-8")
)
_SENTENCE_END = re.compile(r"[.!?।॥]+")
_ROBOTIC = (
    "धीर मागतो",
    "बाबतीत",
    "तापू शकते",
    "नक्की",
    "निश्चित",
    "अहंकारापेक्षा छोटे",
    "आरोपेक्षा छोटे",
    "आशेपेक्षा छोटे",
    "गर्दी करू नका",
    "स्तुती मागू नका",
    "ताबा मिळवण्यासाठी",
    "भाषण नको",
    "मतभेद लपवू नका",
    "asks for patience",
    "today asks",
    "ordinary task",
    "heat up",
    "carries mars",
    "supportive_today",
    "smaller than your pride",
    "smaller than the hope",
    "smaller than the accusation",
    "smaller than ego",
)
_LORDS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
_STEPS = (*_LORDS, "Rahu", "Ketu")
_AREAS = ("career", "relationships", "finances", "home")
_DOMAIN = {
    "career": "work",
    "finances": "money",
    "home": "home",
    "relationships": "talk",
}


def today_instruction(lang: str) -> str:
    """Model skill text explaining Today."""
    guide: dict[str, str] = _DATA["guide"]
    return str(guide.get(lang) or guide["en"])


def period_instruction(lang: str) -> str:
    """Same sitting voice for a life area, a day, or a year."""
    guide: dict[str, str] = _DATA["period_guide"]
    return str(guide.get(lang) or guide["en"])


def sentence_count(text: str) -> int:
    return len([part for part in _SENTENCE_END.split(text) if part.strip()])


def today_voice_problem(text: str) -> str | None:
    """Reject a slogan or stiff calque, then use fallback text."""
    stripped = text.strip()
    lowered = stripped.lower()
    for phrase in _ROBOTIC:
        if phrase.isascii():
            if phrase in lowered:
                return "robotic-voice"
        elif phrase in stripped:
            return "robotic-voice"
    paragraphs = [part for part in stripped.splitlines() if part.strip()]
    if len(paragraphs) < 2 or sentence_count(stripped) < 2:
        return "one-line-slogan"
    return None


def spoken_lines() -> list[str]:
    """Fallback sentences only. Guide text is an instruction, not speech."""
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            found.append(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in {"guide", "period_guide"}:
                    continue
                walk(value)

    walk(_DATA)
    return found


def _lang(block: Any, lang: str) -> str:
    if not isinstance(block, dict):
        raise KeyError(lang)
    value = block.get(lang) or block.get("en")
    return str(value).strip()


def _house(section: str, house: int, lang: str) -> str:
    houses: dict[str, Any] = _DATA[section]
    key = str(house if 1 <= house <= 12 else 1)
    return _lang(houses[key], lang)


def _named(section: str, name: str, lang: str, *, default: str) -> str:
    table: dict[str, Any] = _DATA[section]
    return _lang(table.get(name) or table[default], lang)


def _join(parts: list[str]) -> str:
    return " ".join(part for part in parts if part)


def compose_today(*, lang: str, weekday_lord: str, supportive: str | None) -> str:
    """Weekday paragraph, then one supportive planet when named."""
    lord = weekday_lord if weekday_lord in _LORDS else "Sun"
    first = _lang(_DATA["weekday"][lord], lang)
    block = _DATA["support"].get(supportive) if supportive else None
    second = _lang(block, lang) if isinstance(block, dict) else _lang(_DATA["careful"], lang)
    return f"{first}\n\n{second}"


def compose_period_area(
    *,
    lang: str,
    area: str,
    easy: bool,
    care: str,
    house: int,
    step_planet: str,
) -> str:
    """Kundali life-area note for this period, without a placement catalog."""
    mood = "easy" if easy else "narrow"
    domain = _DOMAIN[area]
    care_key = care if care in ("strain", "slow", "hurry") else "hurry"
    step = step_planet if step_planet in _STEPS else "Sun"
    head = _lang(_DATA["period_open"][area][mood], lang)
    tail = _join(
        [
            _house(domain, house, lang),
            _named("care_line", care_key, lang, default="hurry"),
            _named("step", step, lang, default="Sun"),
        ]
    )
    return f"{head}\n\n{tail}"


def compose_year(*, lang: str, year: int, stance: str, planet: str) -> str:
    """Spoken year. Stance is moving, careful, or waiting."""
    key = stance if stance in ("moving", "careful", "waiting") else "waiting"
    step = planet if planet in _STEPS else "Sun"
    head = _lang(_DATA["year_open"][key], lang).format(year=year)
    close = _lang(_DATA["year_close"][key], lang).format(
        step=_named("step", step, lang, default="Sun")
    )
    return f"{head}\n\n{close}"


def compose_span(
    *,
    lang: str,
    year: int,
    start: str,
    end: str,
    area: str,
    stance: str,
    planet: str,
) -> str:
    """Spoken quarter. Month names only, no sign catalog."""
    key = stance if stance in ("moving", "careful", "waiting") else "waiting"
    step = planet if planet in _STEPS else "Sun"
    head = _lang(_DATA["span_open"][area][key], lang).format(start=start, end=end, year=year)
    close = _named("step", step, lang, default="Sun")
    return f"{head}\n\n{close}"


def compose_area(
    *,
    lang: str,
    area: str,
    easy: bool,
    care: str,
    house: int,
    step_planet: str,
) -> str:
    """One life-area part, same sitting voice."""
    mood = "easy" if easy else "narrow"
    domain = _DOMAIN[area]
    care_key = care if care in ("strain", "slow", "hurry") else "hurry"
    step = step_planet if step_planet in _STEPS else "Sun"
    head = _lang(_DATA["area_open"][area][mood], lang)
    tail = _join(
        [
            _house(domain, house, lang),
            _named("care_line", care_key, lang, default="hurry"),
            _named("step", step, lang, default="Sun"),
        ]
    )
    return f"{head}\n\n{tail}"


def _words(text: str) -> int:
    return len(text.split())


def max_today_words(lang: str) -> int:
    weekdays = max(_words(_lang(_DATA["weekday"][lord], lang)) for lord in _LORDS)
    supports = max(_words(_lang(block, lang)) for block in _DATA["support"].values())
    careful = _words(_lang(_DATA["careful"], lang))
    return weekdays + max(supports, careful)


def max_area_words(lang: str) -> int:
    openings = [
        _words(_lang(_DATA["area_open"][area][mood], lang))
        for area in _AREAS
        for mood in ("easy", "narrow")
    ]
    domains = max(
        max(_words(_house(name, house, lang)) for house in range(1, 13))
        for name in ("work", "money", "home", "talk")
    )
    cares = max(
        _words(_named("care_line", key, lang, default="hurry"))
        for key in ("strain", "slow", "hurry")
    )
    steps = max(_words(_named("step", name, lang, default="Sun")) for name in _STEPS)
    return max(openings) + domains + cares + steps
