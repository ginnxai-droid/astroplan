"""Safety, claim, and grounding guardrails for every user-visible sentence across EN/HI/MR."""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.interpretation.errors import GuardrailViolation

ABSOLUTE_CLAIM_PATTERNS: list[str] = [
    r"100\s*%\s*accurate",
    r"\d+\s*%\s*accurate",
    r"\bguarantee(?:d|s)?\b",
    r"\bwill definitely\b",
    r"\bcertain(?:ly)? (?:to|will)\b",
    r"\bnever fails?\b",
    r"\bproven\b",
    r"\bknow your future\b",
]

FEAR_TERMS: dict[str, list[str]] = {
    "en": [
        r"\bdeath\b",
        r"\bdie[sd]?\b",
        r"\bdying\b",
        r"\bfatal\w*",
        r"\bdoom\w*",
        r"\bcurse\w*",
        r"\bdisaster\w*",
        r"\baccident\w*",
        r"\billness\w*",
        r"\bdisease\w*",
        r"\bmiscarriage\w*",
        r"\bpregnan\w*",
        r"\bbankrupt(?:cy)?\b",
        r"\bruin\w*",
        r"\bblack\s*magic\b",
    ],
    "hi": [
        "मृत्यु",
        "मौत",
        "मरना",
        "घातक",
        "श्राप",
        "शाप",
        "दुर्घटना",
        "बीमारी",
        "रोग",
        "गर्भपात",
        "दिवालिया",
        "तबाही",
        "काला जादू",
        "गारंटी",
        "100% सटीक",
        "पक्का",
    ],
    "mr": [
        "मृत्यू",
        "मरणे",
        "घातक",
        "शाप",
        "अपघात",
        "आजार",
        "रोग",
        "गर्भपात",
        "दिवाळखोरी",
        "उद्ध्वस्त",
        "काळी जादू",
        "हमी",
        "100% अचूक",
        "नक्की",
    ],
}

UPSELL_PATTERNS: list[str] = [
    r"\bbuy\s+this\s+gemstone\b",
    r"\bpaid\s+remedy\b",
    r"\bpurchase\s+(?:a\s+)?(?:puja|pooja|yagna|gemstone)\b",
    r"\bwhatsapp\s+(?:me|us)\s+to\s+pay\b",
]

_PLACEMENT_ENTITIES: tuple[str, ...] = (
    "sun",
    "moon",
    "mars",
    "mercury",
    "jupiter",
    "venus",
    "saturn",
    "rahu",
    "ketu",
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
    "सूर्य",
    "रवी",
    "चंद्र",
    "चंद्रमा",
    "मंगल",
    "मंगळ",
    "बुध",
    "बृहस्पति",
    "गुरू",
    "शुक्र",
    "शनि",
    "शनी",
    "राहु",
    "राहू",
    "केतु",
    "केतू",
    "मेष",
    "वृषभ",
    "मिथुन",
    "कर्क",
    "सिंह",
    "कन्या",
    "तुला",
    "तूळ",
    "वृश्चिक",
    "धनु",
    "मकर",
    "कुंभ",
    "मीन",
)
_STRENGTH_WORDS: tuple[str, ...] = (
    "likely",
    "supported",
    "weak",
    "contested",
    "संभावित",
    "समर्थित",
    "कमजोर",
    "विवादित",
    "शक्य",
    "पूरक",
    "कमकुवत",
)
_CLASSICAL_SOURCES: tuple[str, ...] = (
    "bphs",
    "phaladeepika",
    "parashara",
    "brihat",
    "पाराशर",
    "फलदीपिका",
)


def _compile(pats: Iterable[str], *, latin: bool) -> list[re.Pattern[str]]:
    if latin:
        return [re.compile(p, re.IGNORECASE) for p in pats]
    # Devanagari terms must match whole words: "हमी" (guarantee) must not
    # fire inside "नेहमी" (always). Matras are not \w, so use explicit
    # Devanagari-range lookarounds instead of \b.
    return [re.compile(rf"(?<![ऀ-ॿ]){p}(?![ऀ-ॿ])") for p in pats]


_ABSOLUTE = _compile(ABSOLUTE_CLAIM_PATTERNS, latin=True)
_FEAR = {lang: _compile(terms, latin=(lang == "en")) for lang, terms in FEAR_TERMS.items()}
_UPSELL = _compile(UPSELL_PATTERNS, latin=True)


def verify_text(text: str, *, languages: Iterable[str] = ("en", "hi", "mr")) -> bool:
    for pat in _ABSOLUTE:
        if pat.search(text):
            raise GuardrailViolation(f"absolute-claim pattern: {pat.pattern!r}")
    for lang in languages:
        for pat in _FEAR.get(lang, []):
            if pat.search(text):
                raise GuardrailViolation(f"fear-term ({lang}): {pat.pattern!r}")
    for pat in _UPSELL:
        if pat.search(text):
            raise GuardrailViolation(f"upsell pattern: {pat.pattern!r}")
    return True


def _extract_tokens(text: str, vocab: Iterable[str]) -> set[str]:
    lower = text.lower()
    found: set[str] = set()
    for w in vocab:
        if w.isascii():
            if re.search(rf"\b{re.escape(w)}\b", lower):
                found.add(w)
        elif w in text:
            found.add(w)
    return found


def validate_rephrase(original: str, rephrased: str) -> bool:
    """Strict grounding check for LLM output across EN/HI/MR (Section 10 / Gap 10)."""
    verify_text(rephrased)
    if not set(re.findall(r"\d+", rephrased)).issubset(set(re.findall(r"\d+", original))):
        raise GuardrailViolation("LLM introduced new digits")
    if re.search(r"\brule[_\s-]?id\b", rephrased, flags=re.IGNORECASE):
        raise GuardrailViolation("LLM must not mention rule IDs")
    orig_entities = _extract_tokens(original, _PLACEMENT_ENTITIES)
    new_entities = _extract_tokens(rephrased, _PLACEMENT_ENTITIES)
    if not new_entities.issubset(orig_entities):
        raise GuardrailViolation(
            f"LLM introduced ungrounded placements: {sorted(new_entities - orig_entities)}"
        )
    orig_grades = _extract_tokens(original, _STRENGTH_WORDS)
    new_grades = _extract_tokens(rephrased, _STRENGTH_WORDS)
    if orig_grades != new_grades:
        raise GuardrailViolation("LLM altered or injected strength-grade terms")
    orig_sources = _extract_tokens(original, _CLASSICAL_SOURCES)
    new_sources = _extract_tokens(rephrased, _CLASSICAL_SOURCES)
    if not orig_sources.issubset(new_sources):
        raise GuardrailViolation("LLM dropped classical source reference")
    return True
