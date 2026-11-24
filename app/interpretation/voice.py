"""How a jyotish explains today to the person sitting with them.

The model prompt and the deterministic fallback both follow this guide.
A planet is named only inside a life sentence. The simple text stays in
ordinary life: work, money, home, conversation, and energy.
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
    "asks for patience",
    "today asks",
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
    """Skill text for the model: sit with the person and explain the day."""
    guide: dict[str, str] = _DATA["guide"]
    return str(guide.get(lang) or guide["en"])


def sentence_count(text: str) -> int:
    return len([part for part in _SENTENCE_END.split(text) if part.strip()])


def today_voice_problem(text: str) -> str | None:
    """Reject a slogan or a stiff calque so the human fallback is used."""
    stripped = text.strip()
    lowered = stripped.lower()
    for phrase in _ROBOTIC:
        if phrase.isascii():
            if phrase in lowered:
                return "robotic-voice"
        elif phrase in stripped:
            return "robotic-voice"
    if sentence_count(stripped) < 2:
        return "one-line-slogan"
    return None


def spoken_lines() -> list[str]:
    """Every fallback sentence. The guide itself is an instruction, not speech."""
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            found.append(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key == "guide":
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


def compose_today(
    *,
    lang: str,
    weekday_lord: str,
    pressured: bool,
    money_easy: bool,
    saturn_easy: bool,
    work_house: int,
    money_house: int,
    home_house: int,
    talk_house: int,
    step_planet: str,
) -> str:
    """Several connected sentences for this weekday lord and these life themes."""
    mood = "care" if pressured else "support"
    lord = weekday_lord if weekday_lord in _LORDS else "Sun"
    step = step_planet if step_planet in _STEPS else lord
    tone = "easy" if money_easy else "tight"
    energy = "easy" if saturn_easy else "quiet"
    return _join(
        [
            _lang(_DATA["opening"][lord][mood], lang),
            _house("work", work_house, lang),
            _house("money", money_house, lang),
            _named("money_tone", tone, lang, default="tight"),
            _house("home", home_house, lang),
            _house("talk", talk_house, lang),
            _named("energy", energy, lang, default="quiet"),
            _named("step", step, lang, default="Sun"),
        ]
    )


def compose_area(
    *,
    lang: str,
    area: str,
    easy: bool,
    care: str,
    house: int,
    step_planet: str,
) -> str:
    """One part of the day, in the same sitting voice."""
    mood = "easy" if easy else "narrow"
    domain = _DOMAIN[area]
    care_key = care if care in ("strain", "slow", "hurry") else "hurry"
    step = step_planet if step_planet in _STEPS else "Sun"
    return _join(
        [
            _lang(_DATA["area_open"][area][mood], lang),
            _house(domain, house, lang),
            _named("care_line", care_key, lang, default="hurry"),
            _named("step", step, lang, default="Sun"),
        ]
    )


def _words(text: str) -> int:
    return len(text.split())


def max_today_words(lang: str) -> int:
    openings = [
        _words(_lang(_DATA["opening"][lord][mood], lang))
        for lord in _LORDS
        for mood in ("support", "care")
    ]

    def section_max(name: str) -> int:
        return max(_words(_house(name, house, lang)) for house in range(1, 13))

    tones = max(
        _words(_named("money_tone", key, lang, default="tight")) for key in ("easy", "tight")
    )
    energies = max(
        _words(_named("energy", key, lang, default="quiet")) for key in ("easy", "quiet")
    )
    steps = max(_words(_named("step", name, lang, default="Sun")) for name in _STEPS)
    return (
        max(openings)
        + section_max("work")
        + section_max("money")
        + tones
        + section_max("home")
        + section_max("talk")
        + energies
        + steps
    )


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
