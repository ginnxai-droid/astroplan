"""Question skill and spoken Ask fallback."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from app.api.schemas import ChartResponse
from app.core.constants import RASHI_NAMES
from app.interpretation.guardrails import verify_text
from app.interpretation.voice import sentence_count

_DATA: dict[str, Any] = json.loads(
    Path(__file__).with_name("question.json").read_text(encoding="utf-8")
)
_WINDOW = re.compile(
    r"\b([A-Za-z]+)-([A-Za-z]+)\s+Dasha\s+\(until\s+(\d{4}-\d{2}-\d{2})\)",
    re.IGNORECASE,
)
_NAMED_WORK = re.compile(
    r"\b(?:as an?|become(?: an?)?|job as|work as|career as|career in)\s+[a-z]",
    re.IGNORECASE,
)
_CHANGE = ("change", "switch", "quit", "resign", "desperate", "बदल", "छोड़", "सोड")
_BUY = ("buy", "purchase", "new house", "new home", "second home", "खरेदी", "खरीद")
_MARRY = ("marry", "marriage", "wedding", "विवाह", "शादी", "लग्न")
_PRESSURE = {6, 8, 12}
_JUPITER_EASY = {2, 5, 7, 9, 11}
_SATURN_EASY = {3, 6, 11}
_NEW_HOME = {2, 4, 5, 9, 11}
_PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
_LORDS = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}
_AREA_HOUSE = {"career": 10, "relationships": 7, "finances": 2, "home": 4, "others": 4}
_GLOSSES = (
    "अहंकारापेक्षा छोटे",
    "आरोपेक्षा छोटे",
    "आशेपेक्षा छोटे",
    "गर्दी करू नका",
    "स्तुती मागू नका",
    "ताबा मिळवण्यासाठी",
    "भाषण नको",
    "मतभेद लपवू नका",
    "smaller than your pride",
    "smaller than the hope",
    "smaller than the accusation",
    "smaller than ego",
    "be cautious here",
    "take protective measures",
)
_TOPIC = {
    "career": (r"\b(?:work|job|career)\b", ("काम", "नोकरी", "नौकरी", "करियर", "करिअर")),
    "home": (r"\b(?:home|house)\b", ("घर", "मकान")),
    "finances": (r"\b(?:money|loan)\b", ("धन", "पैसे", "पैसा", "कर्ज")),
    "relationships": (
        r"\b(?:partner|bond|marriage|marry)\b",
        ("जोडीदार", "जोड़ीदार", "रिश्ता", "नाते", "लग्न", "शादी", "विवाह"),
    ),
    "others": (r"\b(?:car|vehicle)\b", ("गाड़ी", "गाडी", "कार", "वाहन")),
}


def question_instruction(lang: str) -> str:
    return _piece(_DATA["skill"], lang)


def question_voice_problem(text: str, facts: str) -> str | None:
    """Reject a catalog dump, a slogan, or a missed decision."""
    stripped = text.strip()
    lowered = stripped.lower()
    for phrase in _GLOSSES:
        if phrase.isascii():
            if phrase in lowered:
                return "slogan-gloss"
        elif phrase in stripped:
            return "slogan-gloss"
    if "?" in stripped:
        return "questionnaire"
    paragraphs = [part for part in stripped.splitlines() if part.strip()]
    if not 2 <= len(paragraphs) <= 3 or sentence_count(stripped) < 2:
        return "question-shape"
    if len(stripped.split()) > 180:
        return "question-shape"
    lang = _fact(facts, "lang") or "en"
    if lang == "en" and re.search(r"\byou\b", stripped, re.IGNORECASE) is None:
        return "question-voice"
    if lang == "hi" and "आप" not in stripped:
        return "question-voice"
    if lang == "mr" and re.search(r"तुम्ह|तुमच", stripped) is None:
        return "question-voice"
    area = _fact(facts, "area")
    rule = _TOPIC.get(area)
    if rule is None:
        return None
    latin, local = rule
    if lang == "en":
        if re.search(latin, lowered) is None:
            return "missed-decision"
    elif not any(token in stripped for token in local):
        return "missed-decision"
    return None


def answer_question(
    *,
    question: str,
    lang: str,
    area: str,
    time_window: str = "",
    strength: str = "",
    chart: ChartResponse | None = None,
    dasha: Mapping[str, object] | None = None,
    transits: Mapping[str, object] | None = None,
) -> tuple[str, str]:
    """Spoken answer plus fact packet."""
    decision = _decision(question, area)
    md, ad, end = _period_parts(time_window, dasha)
    lord_house, jupiter_house, saturn_house = _houses(chart, transits, area)
    if lord_house is not None and jupiter_house is not None and saturn_house is not None:
        stance = _stance(lord_house, jupiter_house, saturn_house)
        jupiter = "supportive" if jupiter_house in _JUPITER_EASY else "quiet"
        saturn = "careful" if saturn_house not in _SATURN_EASY else "steady"
    else:
        stance = "moving" if strength in {"supported", "likely"} else "waiting"
        jupiter = ""
        saturn = ""
    already, fresh = _home_flags(chart, jupiter_house)
    place = _seventh_placed(chart) if decision == "marriage" else already
    named = _NAMED_WORK.search(question) is not None
    fit = ""
    if area == "career" and chart is not None and not named:
        fit = _piece(_DATA["fit"][str(_lord_house(chart, 10))], lang)
    period = _period_phrase(md, ad, lang)
    until = _until_phrase(end, lang)
    text = _render(
        lang=lang,
        area=area,
        decision=decision,
        stance=stance,
        already=place,
        fresh=fresh,
        fit=fit,
        named=named,
        period=period,
        until=until,
        jupiter=jupiter,
        saturn=saturn,
    )
    facts = _facts(
        question=question,
        lang=lang,
        area=area,
        decision=decision,
        period=period,
        end=end,
        stance=stance,
        already=already,
        fresh=fresh,
        place=place,
        fit=fit,
        named=named,
        jupiter=jupiter,
        saturn=saturn,
        md=md,
        ad=ad,
    )
    verify_text(text, languages=(lang,))
    problem = question_voice_problem(text, facts)
    if problem is not None:
        raise ValueError(problem)
    return text, facts


def _render(
    *,
    lang: str,
    area: str,
    decision: str,
    stance: str,
    already: bool | None,
    fresh: bool | None,
    fit: str,
    named: bool,
    period: str,
    until: str,
    jupiter: str,
    saturn: str,
) -> str:
    head = [_piece(_DATA["open"][_open_key(decision, stance, already, fresh)], lang)]
    if fit and not named:
        head.append(_piece(_DATA["career_fit"], lang).format(fit=fit))
    if area == "career":
        head.append(_piece(_DATA["career_exact"], lang))
    if decision == "buy_house" and stance != "waiting":
        head.append(_piece(_DATA["house_exact"], lang))
    if decision == "vehicle" and stance != "waiting":
        head.append(_piece(_DATA["vehicle_exact"], lang))
    if period:
        period_line = _piece(_DATA["period_line"], lang).format(period=period, until=until)
    else:
        period_line = _piece(_DATA["period_unknown"], lang)
    if decision == "marriage":
        tail_group = "relationships"
    elif decision in {"buy_house", "vehicle"}:
        tail_group = "buy"
    else:
        tail_group = area
    tail = [
        period_line,
        _transit(jupiter, saturn, lang),
        _piece(_DATA["tail"][tail_group][stance], lang),
    ]
    return f"{_join(head)}\n\n{_join(tail)}"


def _facts(
    *,
    question: str,
    lang: str,
    area: str,
    decision: str,
    period: str,
    end: str,
    stance: str,
    already: bool | None,
    fresh: bool | None,
    place: bool | None,
    fit: str,
    named: bool,
    jupiter: str,
    saturn: str,
    md: str,
    ad: str,
) -> str:
    lines = [
        f"question: {question}",
        f"lang: {lang}",
        f"area: {area}",
        f"decision: {decision}",
        f"period_spoken: {period or 'unknown'}",
        f"period_end: {end or 'unknown'}",
        f"stance: {stance}",
        f"planets: {', '.join(_allowed_planets(md, ad, jupiter, saturn))}",
    ]
    if area == "career":
        lines.append(f"named_work: {'yes' if named else 'no'}")
        lines.append(f"work_fit: {fit or 'unknown'}")
    if area == "home":
        lines.append(f"already_home: {_flag(already)}")
        lines.append(f"new_home: {_flag(fresh)}")
    if decision == "vehicle":
        lines.append(f"vehicle_place: {_place_word(place)}")
    if decision == "marriage":
        lines.append(f"marriage_place: {_place_word(place)}")
    if jupiter:
        lines.append(f"jupiter: {jupiter}")
    if saturn:
        lines.append(f"saturn: {saturn}")
    return "\n".join(lines)


def _decision(question: str, area: str) -> str:
    lowered = question.lower()
    if area == "others":
        return "vehicle"
    if area == "career":
        if any(token in lowered for token in _CHANGE):
            return "job_change"
        return "career"
    if area == "home":
        if any(token in lowered for token in _BUY):
            return "buy_house"
        return "home"
    if area == "finances":
        return "money"
    if any(token in lowered for token in _MARRY):
        return "marriage"
    return "partner"


def _open_key(
    decision: str,
    stance: str,
    already: bool | None,
    fresh: bool | None,
) -> str:
    if decision == "job_change":
        return f"change_{stance}"
    if decision == "career":
        return f"work_{stance}"
    if decision == "money":
        return f"money_{stance}"
    if decision == "partner":
        return f"bond_{stance}"
    if decision == "vehicle":
        return _place_key("vehicle", stance, already)
    if decision == "marriage":
        return _place_key("marriage", stance, already)
    if decision == "home":
        if already is None:
            return "home_waiting" if stance == "waiting" else "home_moving"
        return "home_ok" if already else "home_strain"
    if already is None:
        return "buy_wait_unknown" if stance == "waiting" else "buy_move_unknown"
    if not already:
        return "buy_no"
    if stance == "waiting":
        return "buy_later" if fresh else "buy_hold"
    return "buy_now"


def _period_parts(
    time_window: str,
    dasha: Mapping[str, object] | None,
) -> tuple[str, str, str]:
    if dasha is not None:
        md = str(dasha.get("active_mahadasha") or "")
        ad = str(dasha.get("active_antardasha") or "")
        end = str(dasha.get("antardasha_end_date") or "")
        if md in _PLANETS and ad in _PLANETS:
            return md, ad, end[:10]
    match = _WINDOW.search(time_window)
    if match is None:
        return "", "", ""
    md, ad, end = match.group(1), match.group(2), match.group(3)
    md = md[:1].upper() + md[1:].lower()
    ad = ad[:1].upper() + ad[1:].lower()
    if md not in _PLANETS or ad not in _PLANETS:
        return "", "", ""
    return md, ad, end


def _houses(
    chart: ChartResponse | None,
    transits: Mapping[str, object] | None,
    area: str,
) -> tuple[int | None, int | None, int | None]:
    if chart is None or transits is None:
        return None, None, None
    return (
        _lord_house(chart, _AREA_HOUSE[area]),
        _optional_int(transits, "jupiter_house_from_moon"),
        _optional_int(transits, "saturn_house_from_moon"),
    )


def _optional_int(transits: Mapping[str, object], key: str) -> int | None:
    if key not in transits:
        return None
    return int(str(transits[key]))


def _stance(lord_house: int, jupiter_house: int, saturn_house: int) -> str:
    lord_ok = lord_house not in _PRESSURE
    jupiter_easy = jupiter_house in _JUPITER_EASY
    saturn_hard = saturn_house not in _SATURN_EASY
    if lord_ok and jupiter_easy and not saturn_hard:
        return "moving"
    if lord_ok and jupiter_easy and saturn_hard:
        return "careful"
    return "waiting"


def _home_flags(
    chart: ChartResponse | None,
    jupiter_house: int | None,
) -> tuple[bool | None, bool | None]:
    if chart is None:
        return None, None
    fourth = _lord_house(chart, 4)
    already = fourth not in _PRESSURE
    helped = jupiter_house is not None and jupiter_house in _JUPITER_EASY
    return already, already and (fourth in _NEW_HOME or helped)


def _lord_house(chart: ChartResponse, house: int) -> int:
    sign = RASHI_NAMES[(chart.lagna_sign_index - 1 + house - 1) % 12]
    name = _LORDS[sign]
    planet = next(item for item in chart.planets if item.planet == name)
    return planet.house


def _period_phrase(md: str, ad: str, lang: str) -> str:
    if not md or not ad:
        return ""
    return _piece(_DATA["period"], lang).format(
        md=_piece(_DATA["planets"][md], lang),
        ad=_piece(_DATA["planets"][ad], lang),
    )


def _until_phrase(iso: str, lang: str) -> str:
    if not iso:
        return ""
    try:
        day = date.fromisoformat(iso[:10])
    except ValueError:
        return ""
    month = _piece(_DATA["months"][str(day.month)], lang)
    return _piece(_DATA["until"], lang).format(month=month, year=day.year)


def _transit(jupiter: str, saturn: str, lang: str) -> str:
    if jupiter == "supportive" and saturn == "careful":
        key = "both"
    elif jupiter == "supportive":
        key = "jupiter"
    elif saturn == "careful":
        key = "saturn"
    else:
        return ""
    return _piece(_DATA["transit"][key], lang)


def _allowed_planets(md: str, ad: str, jupiter: str, saturn: str) -> list[str]:
    names: list[str] = []
    for name in (md, ad, "Jupiter" if jupiter else "", "Saturn" if saturn else ""):
        if name and name not in names:
            names.append(name)
    return names


def _seventh_placed(chart: ChartResponse | None) -> bool | None:
    if chart is None:
        return None
    return _lord_house(chart, 7) not in _PRESSURE


def _place_word(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "placed" if value else "ahead"


def _place_key(prefix: str, stance: str, placed: bool | None) -> str:
    if placed is None:
        return f"{prefix}_unknown_wait" if stance == "waiting" else f"{prefix}_unknown_move"
    if not placed:
        return f"{prefix}_ahead_wait" if stance == "waiting" else f"{prefix}_ahead_move"
    if stance == "waiting":
        return f"{prefix}_placed_wait"
    if stance == "moving":
        return f"{prefix}_placed_move"
    return f"{prefix}_placed_careful"


def _flag(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


def _fact(facts: str, key: str) -> str:
    prefix = f"{key}:"
    for line in facts.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def _piece(block: object, lang: str) -> str:
    if not isinstance(block, dict):
        raise KeyError(lang)
    value = block.get(lang) or block.get("en")
    if not isinstance(value, str) or not value.strip():
        raise KeyError(lang)
    return value


def _join(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())
