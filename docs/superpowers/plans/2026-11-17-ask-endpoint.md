# Ask Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an authenticated `POST /v1/readings/ask` endpoint that routes a user's question to one of the four advisor-approved life areas and returns the pre-computed, guarded statement for that area.

**Architecture:** A deterministic lexicon classifies the question before any chart math runs; unmatched questions return an `uncovered` response with zero model, ephemeris, or quota cost. Matched questions compute the chart once, select the area's existing `ExplainedStatement`, optionally reword it through `SafeRephraser` under a stricter answer validator, register the canonical text in the prediction ledger, and consume one quota unit. The model never sees the question and never produces astrology.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PyYAML, pytest, ruff, mypy strict.

**Spec:** `docs/superpowers/specs/2026-11-17-ask-endpoint-design.md`

## Global Constraints

- Four life areas only: `career`, `relationships`, `finances`, `home` (`LifeAreaCategory`).
- The LLM never receives the user's question; it receives one already-guarded sentence.
- `guardrails.validate_rephrase` behaviour is unchanged; no existing assertion may be edited.
- The registered ledger text is the canonical catalog sentence, never reworded prose.
- All user-visible prose lives in `i18n/{en,hi,mr}.json`; no prose literals in `app/**/*.py`.
- `make guardrails` must PASS (G3, G5, G6, G7), including i18n key parity.
- `openapi.json` must be regenerated in the same change that adds the route.
- `ask_enabled` defaults to `False`; the endpoint is dark until the owner turns it on.
- Rules stay `draft`; G2 semantics are untouched.

---

### Task 1: Answer validator on top of the unchanged rephrase gate

**Files:**
- Modify: `app/interpretation/guardrails.py:197-218`
- Test: `tests/test_validate_answer.py` (create)

**Interfaces:**
- Consumes: `verify_text`, `_extract_tokens`, existing vocab tuples in `guardrails.py`.
- Produces:
  - `_validate_grounding(original: str, rephrased: str, *, extra_digits: frozenset[str] = frozenset(), require_sources: bool = True, normalize_digits: bool = False) -> None`
  - `validate_answer(*, bundle: str, question: str, area: LifeAreaCategory, answer: str, lang: LanguageCode, lexicon: AreaLexicon, require_sources: bool = False) -> None` — `AreaLexicon` is imported for typing only; at runtime it must expose `.terms: dict[str, tuple[str, ...]]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validate_answer.py`:

```python
from types import SimpleNamespace

import pytest

from app.interpretation.errors import GuardrailViolation
from app.interpretation.guardrails import validate_answer, validate_rephrase

LEXICON = SimpleNamespace(
    terms={
        "career": ("job", "career", "work"),
        "relationships": ("marriage", "partner", "spouse"),
        "finances": ("money", "savings", "loan"),
        "home": ("home", "house", "property"),
    }
)

BUNDLE = "Steady professional progress is supported through structured planning and consistent effort."
QUESTION = "Will I change jobs before mid-2027?"


def test_validate_rephrase_digit_behaviour_is_unchanged() -> None:
    assert validate_rephrase("Progress in 2027.", "In 2027 progress continues.")
    with pytest.raises(GuardrailViolation, match="new digits"):
        validate_rephrase("Progress in 2027.", "Progress in 2028.")
    with pytest.raises(GuardrailViolation, match="new digits"):
        validate_rephrase("Progress in 2027.", "प्रगति २०२७ में है।")


def test_canonical_sentence_passes_answer_validation() -> None:
    validate_answer(
        bundle=BUNDLE,
        question=QUESTION,
        area="career",
        answer=BUNDLE,
        lang="en",
        lexicon=LEXICON,
    )


def test_answer_may_echo_the_question_year() -> None:
    validate_answer(
        bundle=BUNDLE,
        question=QUESTION,
        area="career",
        answer="Career progress is supported before 2027.",
        lang="en",
        lexicon=LEXICON,
    )


def test_devanagari_digits_normalize_against_latin_question() -> None:
    # The bundle is already in the answer's language (as in the API flow), so the
    # strength-grade vocabularies match; only the digit script differs.
    validate_answer(
        bundle="कार्यक्षेत्र में स्थिर प्रगति के संकेत हैं।",
        question=QUESTION,
        area="career",
        answer="२०२७ से पहले कार्यक्षेत्र में स्थिर प्रगति के संकेत हैं।",
        lang="hi",
        lexicon=LEXICON,
    )


def test_answer_drifting_to_another_area_is_rejected() -> None:
    with pytest.raises(GuardrailViolation, match="another life area"):
        validate_answer(
            bundle=BUNDLE,
            question=QUESTION,
            area="career",
            answer="Your savings and loan position is supported this year.",
            lang="en",
            lexicon=LEXICON,
        )


def test_soft_refusal_is_rejected() -> None:
    with pytest.raises(GuardrailViolation, match="refuses"):
        validate_answer(
            bundle=BUNDLE,
            question=QUESTION,
            area="career",
            answer="I cannot answer whether work progress is supported.",
            lang="en",
            lexicon=LEXICON,
        )


def test_invented_month_is_rejected() -> None:
    with pytest.raises(GuardrailViolation, match="unlisted month"):
        validate_answer(
            bundle="Steady progress until 2027-08-12 is supported.",
            question=QUESTION,
            area="career",
            answer="Career progress is supported in September 2027.",
            lang="en",
            lexicon=LEXICON,
        )


@pytest.mark.parametrize(
    ("answer", "match"),
    [
        ("Career progress is supported?", "shape"),
        ("As an AI, career progress is supported.", "echoes instruction text"),
        ("Supported.", "shape"),
        ("- career progress\n- supported effort", "shape"),
    ],
)
def test_bad_shape_and_meta_are_rejected(answer: str, match: str) -> None:
    with pytest.raises(GuardrailViolation, match=match):
        validate_answer(
            bundle=BUNDLE,
            question=QUESTION,
            area="career",
            answer=answer,
            lang="en",
            lexicon=LEXICON,
        )


def test_wrong_script_is_rejected() -> None:
    with pytest.raises(GuardrailViolation, match="script"):
        validate_answer(
            bundle="कार्यक्षेत्र में स्थिर प्रगति के संकेत हैं।",
            question=QUESTION,
            area="career",
            answer="करियर में स्थिर प्रगति के संकेत हैं और निरंतर प्रयास सहायक है।",
            lang="en",
            lexicon=LEXICON,
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_validate_answer.py -q`
Expected: FAIL with `ImportError: cannot import name 'validate_answer'`.

- [ ] **Step 3: Implement the refactor and the validator**

In `app/interpretation/guardrails.py`, add near the vocab block:

```python
_REFUSAL_PATTERNS: tuple[str, ...] = (
    r"\bcannot (?:answer|say|tell)\b",
    r"\bcan't (?:answer|say|tell)\b",
    r"\bunable to (?:answer|say|tell)\b",
    r"\bno information\b",
)
_REFUSAL_SUBSTRINGS: tuple[str, ...] = (
    "उत्तर नहीं दे सकते",
    "जानकारी नहीं है",
    "उत्तर देऊ शकत नाही",
    "माहिती नाही",
)
_MONTH_TOKENS: tuple[str, ...] = (
    "january",
    "february",
    "march",
    "april",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "जनवरी",
    "फरवरी",
    "मार्च",
    "अप्रैल",
    "जून",
    "जुलाई",
    "अगस्त",
    "सितंबर",
    "अक्टूबर",
    "नवंबर",
    "दिसंबर",
    "जानेवारी",
    "फेब्रुवारी",
    "एप्रिल",
    "जुलै",
    "ऑगस्ट",
    "सप्टेंबर",
    "ऑक्टोबर",
    "नोव्हेंबर",
    "डिसेंबर",
)  # "may" is excluded: it collides with the modal verb
_META_TOKENS: tuple[str, ...] = ("system", "prompt", "instruction", "language model", "as an ai")
_DIGIT_RUN = re.compile(r"\d+")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_REFUSAL = [re.compile(p, re.IGNORECASE) for p in _REFUSAL_PATTERNS]
```

Also add the typing-only imports at the top of the module:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.api.schemas import LanguageCode, LifeAreaCategory
    from app.interpretation.ask import AreaLexicon
```

Replace the body of `validate_rephrase` with a call into a new private function, then append the answer validator:

```python
def _digit_set(text: str, *, normalize: bool) -> set[str]:
    runs = _DIGIT_RUN.findall(text)
    return {str(int(run)) for run in runs} if normalize else set(runs)


def _validate_grounding(
    original: str,
    rephrased: str,
    *,
    extra_digits: frozenset[str] = frozenset(),
    require_sources: bool = True,
    normalize_digits: bool = False,
) -> None:
    verify_text(rephrased)
    allowed = _digit_set(original, normalize=normalize_digits) | set(extra_digits)
    if not _digit_set(rephrased, normalize=normalize_digits).issubset(allowed):
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
    if require_sources:
        orig_sources = _extract_tokens(original, _CLASSICAL_SOURCES)
        new_sources = _extract_tokens(rephrased, _CLASSICAL_SOURCES)
        if not orig_sources.issubset(new_sources):
            raise GuardrailViolation("LLM dropped classical source reference")


def validate_rephrase(original: str, rephrased: str) -> bool:
    """Strict grounding check for LLM output across EN/HI/MR (Section 10 / Gap 10)."""
    _validate_grounding(original, rephrased)
    return True


def validate_answer(
    *,
    bundle: str,
    question: str,
    area: LifeAreaCategory,
    answer: str,
    lang: LanguageCode,
    lexicon: AreaLexicon,
    require_sources: bool = False,
) -> None:
    _validate_grounding(
        bundle,
        answer,
        extra_digits=frozenset(_digit_set(question, normalize=True)),
        require_sources=require_sources,
        normalize_digits=True,
    )
    other_terms: list[str] = []
    for name, terms in lexicon.terms.items():
        if name != area:
            other_terms.extend(terms)
    if _extract_tokens(answer, other_terms):
        raise GuardrailViolation("answer drifted to another life area")
    if any(pattern.search(answer) for pattern in _REFUSAL) or any(
        marker in answer for marker in _REFUSAL_SUBSTRINGS
    ):
        raise GuardrailViolation("answer refuses a covered life area")
    allowed_months = _extract_tokens(bundle, _MONTH_TOKENS) | _extract_tokens(
        question, _MONTH_TOKENS
    )
    if _extract_tokens(answer, _MONTH_TOKENS) - allowed_months:
        raise GuardrailViolation("answer introduced an unlisted month")
    if not 15 <= len(answer) <= 420 or "\n" in answer or "?" in answer:
        raise GuardrailViolation("answer shape is not a single statement")
    if re.search(r"(^|\s)[-*•]\s", answer):
        raise GuardrailViolation("answer shape is not a single statement")
    if _extract_tokens(answer, _META_TOKENS):
        raise GuardrailViolation("answer echoes instruction text")
    has_devanagari = _DEVANAGARI_RE.search(answer) is not None
    has_latin = _LATIN_RE.search(answer) is not None
    if lang == "en" and (has_devanagari or not has_latin):
        raise GuardrailViolation("answer script does not match the requested language")
    if lang in ("hi", "mr") and not has_devanagari:
        raise GuardrailViolation("answer script does not match the requested language")
```

- [ ] **Step 4: Run both test files**

Run: `python -m pytest tests/test_validate_answer.py tests/test_s01_guardrails.py -q`
Expected: both PASS; no edits were made to `tests/test_s01_guardrails.py`.

- [ ] **Step 5: Run the static scanners**

Run: `python scripts/check_guardrails.py`
Expected: PASS for G3-static and G6-hardcoded (the new literals are lowercase messages and month tokens).

- [ ] **Step 6: Commit**

```bash
git add app/interpretation/guardrails.py tests/test_validate_answer.py
git commit -m "feat(ask): add question-aware answer validator over unchanged rephrase gate"
```

---

### Task 2: Deterministic lexicon and question routing

**Files:**
- Create: `rules/ask_lexicon.yaml`
- Create: `app/interpretation/ask.py`
- Test: `tests/test_ask_classification.py` (create)

**Interfaces:**
- Consumes: `LifeAreaCategory` from `app.api.schemas`.
- Produces:
  - `AREA_ORDER: tuple[LifeAreaCategory, ...]`
  - `class AskLexiconError(ValueError)`
  - `@dataclass(frozen=True) AreaLexicon(terms: dict[LifeAreaCategory, tuple[str, ...]], present_cues: tuple[str, ...])`
  - `load_area_lexicon(path: str | Path) -> AreaLexicon`
  - `classify_question(question: str, lexicon: AreaLexicon) -> tuple[LifeAreaCategory | None, list[str]]`
  - `is_present_time_question(question: str, lexicon: AreaLexicon) -> bool`
  - `infer_target_date(question: str, *, today: date) -> date | None`
  - `iso_week_start(day: date) -> date`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ask_classification.py`:

```python
from datetime import date

import pytest

from app.interpretation.ask import (
    AskLexiconError,
    classify_question,
    infer_target_date,
    is_present_time_question,
    iso_week_start,
    load_area_lexicon,
)


@pytest.fixture(scope="module")
def lexicon():
    return load_area_lexicon("rules/ask_lexicon.yaml")


@pytest.mark.parametrize(
    ("question", "area", "term"),
    [
        ("Will I change jobs before mid-2027?", "career", "job"),
        ("Should I ask for a promotion this year?", "career", "promotion"),
        ("Will I marry in the next two years?", "relationships", "marry"),
        ("Should I take a loan this year?", "finances", "loan"),
        ("Is this a good year to move home?", "home", "home"),
    ],
)
def test_routes_english_questions(lexicon, question, area, term) -> None:
    routed, matched = classify_question(question, lexicon)
    assert routed == area
    assert term in matched


def test_routes_hindi_and_marathi(lexicon) -> None:
    assert classify_question("क्या मेरी नौकरी बदलेगी?", lexicon)[0] == "career"
    assert classify_question("माझं घर कधी बदलेल?", lexicon)[0] == "home"


def test_unmapped_area_abstains(lexicon) -> None:
    assert classify_question("How is my health in 2027?", lexicon) == (None, [])


def test_negation_is_not_understood_and_routes_to_the_named_area(lexicon) -> None:
    # Documented v1 limitation: the router sees the noun, not the negation.
    assert classify_question("I am not worried about money, will my loan clear?", lexicon)[0] == (
        "finances"
    )


def test_compound_tie_abstains(lexicon) -> None:
    assert classify_question("Should I move for a new job?", lexicon) == (None, [])


def test_present_cue_detection(lexicon) -> None:
    assert is_present_time_question("What should I focus on today?", lexicon)
    assert not is_present_time_question("Will I change jobs in 2028?", lexicon)


def test_target_year_inference_and_clamping() -> None:
    today = date(2026, 11, 17)
    assert infer_target_date("Will I change jobs before mid-2027?", today=today) == date(2027, 1, 15)
    assert infer_target_date("Anything for 2026 or 2027?", today=today) is None
    assert infer_target_date("What about 2035?", today=today) == date(2029, 11, 17)
    assert infer_target_date("Will I change jobs?", today=today) is None


def test_target_year_inference_survives_leap_day() -> None:
    assert infer_target_date("2027", today=date(2028, 2, 29)) == date(2028, 2, 29)


def test_iso_week_start_is_monday() -> None:
    assert iso_week_start(date(2026, 11, 17)) == date(2026, 11, 16)


def test_loader_rejects_incomplete_lexicon(tmp_path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("career: [job]\npresent_cues: [today]\n", encoding="utf-8")
    with pytest.raises(AskLexiconError):
        load_area_lexicon(bad)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ask_classification.py -q`
Expected: FAIL with `ModuleNotFoundError: app.interpretation.ask`.

- [ ] **Step 3: Create the lexicon data**

Create `rules/ask_lexicon.yaml` (terms match at a left word boundary, so "job" also matches "jobs"):

```yaml
career:
  - job
  - career
  - promotion
  - appraisal
  - work
  - role
  - interview
  - business
  - नौकरी
  - करियर
  - नोकरी
  - करिअर
relationships:
  - marriage
  - marry
  - married
  - partner
  - spouse
  - relationship
  - commit
  - विवाह
  - शादी
  - रिश्ते
  - नाते
finances:
  - money
  - finance
  - loan
  - debt
  - saving
  - invest
  - salary
  - income
  - पैसा
  - कर्ज
  - पैसे
home:
  - home
  - house
  - property
  - rent
  - move
  - renovate
  - family
  - घर
  - मकान
  - जमीन
  - घरबदल
present_cues:
  - today
  - now
  - this week
  - currently
  - आज
  - अभी
  - आता
  - या आठवड्यात
```

- [ ] **Step 4: Implement `app/interpretation/ask.py`**

```python
"""Deterministic question routing. The model never reads the user's question."""

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
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_ask_classification.py -q`
Expected: PASS. If the compound-tie test fails, check that "move" (home) and "job" (career) each score exactly 1.

- [ ] **Step 6: Commit**

```bash
git add rules/ask_lexicon.yaml app/interpretation/ask.py tests/test_ask_classification.py
git commit -m "feat(ask): add deterministic area lexicon and question routing"
```

---

### Task 3: Outcome criteria on rules

**Files:**
- Modify: `app/interpretation/rules.py:16-56`
- Modify: `rules/mvp_rules.yaml` (four area rules)
- Test: `tests/test_ask_rules.py` (create)

**Interfaces:**
- Produces: `Rule.observable_outcome_criteria: str` (default `""`), enforced non-empty for `status: approved`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ask_rules.py`:

```python
import pytest

from app.interpretation.errors import RuleSchemaError
from app.interpretation.rules import load_rules


def test_area_rules_carry_outcome_criteria() -> None:
    rules = load_rules("rules/mvp_rules.yaml", allow_draft=True)
    areas = {"career", "relationships", "finances", "home"}
    for rule in rules:
        if rule.category in areas:
            assert rule.observable_outcome_criteria.strip(), rule.id


def test_approved_rule_without_criteria_fails(tmp_path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        "\n".join(
            [
                "- id: RULE_X",
                "  category: career",
                "  text_key: career_10h_discipline",
                "  evidence_template: Sun in {sun_sign}",
                "  classical_source: BPHS",
                "  tradition: Parashari",
                "  strength_grade: supported",
                "  reviewer: advisor",
                "  reviewed_at: 2026-11-17",
                "  status: approved",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuleSchemaError, match="observable_outcome_criteria"):
        load_rules(path, allow_draft=False)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ask_rules.py -q`
Expected: FAIL with `AttributeError: 'Rule' object has no attribute 'observable_outcome_criteria'`.

- [ ] **Step 3: Extend the dataclass and loader**

In `app/interpretation/rules.py`, append to `Rule` after `status`:

```python
    observable_outcome_criteria: str = ""
```

In `load_rules`, pass the new field in the constructor:

```python
                status=entry.get("status", "draft"),
                observable_outcome_criteria=str(
                    entry.get("observable_outcome_criteria") or ""
                ).strip(),
```

and add after the reviewer check:

```python
        if rule.status == "approved" and not rule.observable_outcome_criteria:
            raise RuleSchemaError(
                f"G2: approved rule {rule.id} missing observable_outcome_criteria"
            )
```

- [ ] **Step 4: Add criteria to the four area rules**

In `rules/mvp_rules.yaml`, add one line under `status: draft` for each of `RULE_PARASHARI_CAREER_10H`, `RULE_PARASHARI_REL_7H`, `RULE_PARASHARI_FIN_2H_11H`, `RULE_PARASHARI_HOME_4H`:

```yaml
  observable_outcome_criteria: "Job role, title, or workplace changed by the stated window end."
```

```yaml
  observable_outcome_criteria: "Partnership status or a joint commitment changed by the stated window end."
```

```yaml
  observable_outcome_criteria: "Household savings or monthly income moved by the stated window end."
```

```yaml
  observable_outcome_criteria: "Residence or living arrangement changed by the stated window end."
```

- [ ] **Step 5: Run the rules tests**

Run: `python -m pytest tests/test_ask_rules.py tests/test_s09_rules.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/interpretation/rules.py rules/mvp_rules.yaml tests/test_ask_rules.py
git commit -m "feat(ask): require observable outcome criteria for approved rules"
```

---

### Task 4: Client copy for coverage and errors

**Files:**
- Modify: `i18n/en.json`, `i18n/hi.json`, `i18n/mr.json`
- Test: `tests/test_ask_i18n.py` (create)

**Interfaces:**
- Produces keys in all three catalogs: `area.career`, `area.relationships`, `area.finances`, `area.home`, `ask.coverage.uncovered_title`, `ask.coverage.uncovered_body`, `ask.coverage.suggestion`, `error.ask_question_invalid`, `error.ask_quota_exhausted`, `error.ask_disabled`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ask_i18n.py`:

```python
import pytest

from app.interpretation.language import Catalog

KEYS = (
    "area.career",
    "area.relationships",
    "area.finances",
    "area.home",
    "ask.coverage.uncovered_title",
    "ask.coverage.uncovered_body",
    "ask.coverage.suggestion",
    "error.ask_question_invalid",
    "error.ask_quota_exhausted",
    "error.ask_disabled",
)


@pytest.mark.parametrize("lang", ["en", "hi", "mr"])
def test_ask_keys_exist_in_every_language(lang) -> None:
    catalog = Catalog("i18n")
    for key in KEYS:
        assert catalog.get(key, lang).strip()


def test_uncovered_body_formats_area_list() -> None:
    catalog = Catalog("i18n")
    text = catalog.format("ask.coverage.uncovered_body", "en", areas="Career, Finances")
    assert "Career, Finances" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ask_i18n.py -q`
Expected: FAIL with `MissingI18nKeyError`.

- [ ] **Step 3: Add keys to `i18n/en.json`**

```json
  "area.career": "Career",
  "area.relationships": "Relationships",
  "area.finances": "Finances",
  "area.home": "Home",
  "ask.coverage.uncovered_title": "No reviewed answer for this area yet.",
  "ask.coverage.uncovered_body": "Astroplan currently interprets four life areas from advisor-reviewed rules: {areas}. This question falls outside them, so we will not improvise an answer.",
  "ask.coverage.suggestion": "Try asking about career, money, home, or relationships.",
  "error.ask_question_invalid": "Please enter a question between 3 and 280 characters.",
  "error.ask_quota_exhausted": "Your three free questions for this week are used. They reset on Monday.",
  "error.ask_disabled": "Ask is not available right now.",
```

- [ ] **Step 4: Add the same keys to `i18n/hi.json`**

```json
  "area.career": "करियर",
  "area.relationships": "रिश्ते",
  "area.finances": "धन",
  "area.home": "घर",
  "ask.coverage.uncovered_title": "इस विषय के लिए अभी समीक्षित उत्तर नहीं है।",
  "ask.coverage.uncovered_body": "एस्ट्रोप्लान फिलहाल सलाहकार-समीक्षित नियमों से चार जीवन-क्षेत्रों की व्याख्या करता है: {areas}. यह प्रश्न इनसे बाहर है, इसलिए हम अपनी ओर से उत्तर नहीं गढ़ेंगे।",
  "ask.coverage.suggestion": "करियर, धन, घर या रिश्तों के बारे में पूछकर देखें।",
  "error.ask_question_invalid": "कृपया 3 से 280 अक्षरों के बीच प्रश्न लिखें।",
  "error.ask_quota_exhausted": "इस सप्ताह के तीन नि:शुल्क प्रश्न पूरे हो गए हैं। सोमवार को रीसेट होंगे।",
  "error.ask_disabled": "अभी पूछें सुविधा उपलब्ध नहीं है।",
```

- [ ] **Step 5: Add the same keys to `i18n/mr.json`**

```json
  "area.career": "करिअर",
  "area.relationships": "नाती",
  "area.finances": "पैसा",
  "area.home": "घर",
  "ask.coverage.uncovered_title": "या विषयासाठी सध्या तपासलेले उत्तर नाही.",
  "ask.coverage.uncovered_body": "अ‍ॅस्ट्रोप्लॅन सध्या सल्लागार-तपासलेल्या नियमांवरून चार जीवनक्षेत्रांचा अर्थ लावते: {areas}. हा प्रश्न त्याबाहेर आहे, म्हणून आम्ही स्वतःहून उत्तर तयार करणार नाही.",
  "ask.coverage.suggestion": "करिअर, पैसा, घर किंवा नात्यांबद्दल विचारून पाहा.",
  "error.ask_question_invalid": "कृपया 3 ते 280 अक्षरांमधील प्रश्न लिहा.",
  "error.ask_quota_exhausted": "या आठवड्याचे तीन मोफत प्रश्न संपले आहेत. सोमवारी पुन्हा सुरू होतील.",
  "error.ask_disabled": "सध्या विचारा सुविधा उपलब्ध नाही.",
```

- [ ] **Step 6: Run the parity scanner and tests**

Run: `python scripts/check_guardrails.py && python -m pytest tests/test_ask_i18n.py tests/test_s10_language.py -q`
Expected: `G6-i18n` PASS and all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add i18n/en.json i18n/hi.json i18n/mr.json tests/test_ask_i18n.py
git commit -m "feat(ask): add coverage and error copy in en/hi/mr"
```

---

### Task 5: Idempotent ledger registration

**Files:**
- Modify: `app/ledger/service.py:93` (add method after `register`)
- Test: `tests/test_ask_ledger.py` (create)

**Interfaces:**
- Produces: `PredictionLedgerService.register_or_get(*, entry_id, user_id, statement_id, rule_id, statement_text, confidence_grade, time_window, observable_outcome_criteria, safety_category="general") -> PreRegisteredLedgerEntry` — returns the existing entry without rewriting it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ask_ledger.py`:

```python
from app.db.session import make_engine_and_session
from app.ledger.service import PredictionLedgerService

FIELDS = {
    "entry_id": "ASK-DEDUPE",
    "user_id": "U1",
    "statement_id": "RULE_PARASHARI_CAREER_10H_4_7",
    "rule_id": "RULE_PARASHARI_CAREER_10H",
    "statement_text": "Steady professional progress is supported through planning.",
    "confidence_grade": "supported",
    "time_window": "Active Moon-Ketu Dasha (until 2027-08-12)",
    "observable_outcome_criteria": "Role changed by window end.",
    "safety_category": "life_area",
}


def test_register_or_get_dedupes_in_memory() -> None:
    svc = PredictionLedgerService()
    first = svc.register_or_get(**FIELDS)
    assert svc.register_or_get(**FIELDS).registered_at_utc == first.registered_at_utc
    assert len(svc._all_entries(user_id="U1")) == 1


def test_register_or_get_preserves_a_logged_outcome() -> None:
    _, sf = make_engine_and_session("sqlite+pysqlite:///:memory:")
    svc = PredictionLedgerService(session_factory=sf)
    svc.register_or_get(**FIELDS)
    svc.mark_outcome("ASK-DEDUPE", "hit")
    again = svc.register_or_get(**FIELDS)
    assert again.user_outcome == "hit"
    assert len(svc._all_entries(user_id="U1")) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ask_ledger.py -q`
Expected: FAIL with `AttributeError: 'PredictionLedgerService' object has no attribute 'register_or_get'`.

- [ ] **Step 3: Implement the method**

Insert in `app/ledger/service.py` after `register`:

```python
    def register_or_get(
        self,
        *,
        entry_id: str,
        user_id: str,
        statement_id: str,
        rule_id: str,
        statement_text: str,
        confidence_grade: StrengthGrade,
        time_window: str,
        observable_outcome_criteria: str,
        safety_category: str = "general",
    ) -> PreRegisteredLedgerEntry:
        for existing in self._all_entries(user_id=user_id):
            if existing.entry_id == entry_id:
                return existing
        return self.register(
            entry_id=entry_id,
            user_id=user_id,
            statement_id=statement_id,
            rule_id=rule_id,
            statement_text=statement_text,
            confidence_grade=confidence_grade,
            time_window=time_window,
            observable_outcome_criteria=observable_outcome_criteria,
            safety_category=safety_category,
        )
```

- [ ] **Step 4: Run the ledger tests**

Run: `python -m pytest tests/test_ask_ledger.py tests/test_s14_ledger.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ledger/service.py tests/test_ask_ledger.py
git commit -m "feat(ask): add idempotent ledger registration"
```

---

### Task 6: LLM provenance fields and detailed rephrase result

**Files:**
- Modify: `app/db/models.py:104-115`
- Modify: `app/interpretation/audit.py:12-63`
- Modify: `app/interpretation/llm.py:13-50`
- Test: `tests/test_ask_audit.py` (create)

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) RephraseResult(text: str, attempted: bool, accepted: bool, fallback_reason: str | None)`
  - `SafeRephraser.enabled -> bool`
  - `SafeRephraser.rephrase_detailed(sentence, *, lang, client=None, validator: Callable[[str, str], None] | None = None, prompt_version: str | None = None, bundle_hash: str | None = None, question_area: str | None = None) -> RephraseResult`
  - `SafeRephraser.rephrase(...) -> str` keeps its current signature and returns `.text`.
  - `LLMAuditRow` gains nullable `prompt_version`, `model`, `bundle_hash`, `question_area`.
  - `LLMAuditLog.record(..., prompt_version=None, model=None, bundle_hash=None, question_area=None)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ask_audit.py`:

```python
from app.config import Settings
from app.db.session import make_engine_and_session
from app.interpretation.audit import LLMAuditLog
from app.interpretation.errors import GuardrailViolation
from app.interpretation.llm import SafeRephraser


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def complete(self, prompt: str) -> str:
        return self._reply


def _rephraser(enabled: bool = True) -> tuple[SafeRephraser, LLMAuditLog]:
    _, sf = make_engine_and_session("sqlite+pysqlite:///:memory:")
    audit = LLMAuditLog(session_factory=sf)
    settings = Settings(env="test", llm_rephrase_enabled=enabled, llm_monthly_call_cap=5)
    return SafeRephraser(settings, audit), audit


def test_detailed_result_reports_acceptance_and_metadata() -> None:
    rephraser, audit = _rephraser()
    result = rephraser.rephrase_detailed(
        "Steady progress is supported.",
        lang="en",
        client=_FakeLLM("Steady progress remains supported."),
        prompt_version="ask-answer-v1",
        bundle_hash="abc123",
        question_area="career",
    )
    assert result.accepted is True
    assert result.text == "Steady progress remains supported."
    event = audit.events[-1]
    assert event.question_area == "career"
    assert event.bundle_hash == "abc123"
    assert event.prompt_version == "ask-answer-v1"
    assert event.model == "claude-3-5-haiku-latest"


def test_custom_validator_rejection_falls_back() -> None:
    rephraser, _ = _rephraser()

    def reject(original: str, candidate: str) -> None:
        raise GuardrailViolation("blocked by answer validator")

    result = rephraser.rephrase_detailed(
        "Steady progress is supported.",
        lang="en",
        client=_FakeLLM("Steady progress is certain."),
        validator=reject,
    )
    assert result.accepted is False
    assert result.text == "Steady progress is supported."
    assert result.fallback_reason == "blocked by answer validator"


def test_disabled_rephraser_attempts_nothing() -> None:
    rephraser, audit = _rephraser(enabled=False)
    result = rephraser.rephrase_detailed(
        "Steady progress is supported.", lang="en", client=_FakeLLM("x")
    )
    assert result.attempted is False
    assert result.text == "Steady progress is supported."
    assert audit.events == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ask_audit.py -q`
Expected: FAIL with `AttributeError: 'SafeRephraser' object has no attribute 'rephrase_detailed'`.

- [ ] **Step 3: Extend the row and the audit log**

In `app/db/models.py`, add to `LLMAuditRow`:

```python
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bundle_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question_area: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

In `app/interpretation/audit.py`, extend `LLMAuditEvent` with four defaulted fields (`prompt_version`, `model`, `bundle_hash`, `question_area`, all `str | None = None`), extend `record` with the same keyword arguments defaulting to `None`, pass them into the event and the `LLMAuditRow`.

- [ ] **Step 4: Rework `app/interpretation/llm.py`**

Replace the class body with:

```python
@dataclass(frozen=True)
class RephraseResult:
    text: str
    attempted: bool
    accepted: bool
    fallback_reason: str | None


class SafeRephraser:
    def __init__(self, settings: Settings, audit_log: LLMAuditLog) -> None:
        self._s = settings
        self._audit = audit_log
        self._calls_used = 0

    @property
    def enabled(self) -> bool:
        return self._s.llm_rephrase_enabled

    def rephrase(self, sentence: str, *, lang: str, client: LLMClientProtocol | None = None) -> str:
        return self.rephrase_detailed(sentence, lang=lang, client=client).text

    def rephrase_detailed(
        self,
        sentence: str,
        *,
        lang: str,
        client: LLMClientProtocol | None = None,
        validator: Callable[[str, str], None] | None = None,
        prompt_version: str | None = None,
        bundle_hash: str | None = None,
        question_area: str | None = None,
    ) -> RephraseResult:
        check = validator or validate_rephrase
        meta = {
            "prompt_version": prompt_version,
            "model": self._s.anthropic_model if client is not None else None,
            "bundle_hash": bundle_hash,
            "question_area": question_area,
        }
        if not self._s.llm_rephrase_enabled or client is None:
            return RephraseResult(sentence, attempted=False, accepted=False, fallback_reason=None)
        if self._calls_used >= self._s.llm_monthly_call_cap:
            self._audit.record(
                lang,
                accepted=False,
                prompt=sentence,
                output="",
                fallback_reason="monthly_cap_reached",
                **meta,
            )
            return RephraseResult(
                sentence, attempted=False, accepted=False, fallback_reason="monthly_cap_reached"
            )
        self._calls_used += 1
        candidate = ""
        try:
            candidate = client.complete(sentence)
            check(sentence, candidate)
            self._audit.record(lang, accepted=True, prompt=sentence, output=candidate, **meta)
            return RephraseResult(candidate, attempted=True, accepted=True, fallback_reason=None)
        except Exception as exc:
            self._audit.record(
                lang,
                accepted=False,
                prompt=sentence,
                output=candidate,
                fallback_reason=str(exc),
                **meta,
            )
            return RephraseResult(
                sentence, attempted=True, accepted=False, fallback_reason=str(exc)
            )
```

Add `from collections.abc import Callable` and `from dataclasses import dataclass` imports.

- [ ] **Step 5: Run the LLM tests**

Run: `python -m pytest tests/test_ask_audit.py tests/test_s16_llm.py -q`
Expected: PASS; the existing S16 assertions are unchanged.

- [ ] **Step 6: Add the migration**

Create `alembic/versions/0002_ask_audit_provenance.py`:

```python
"""Add LLM provenance columns used by the Ask endpoint."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_audit_events", sa.Column("prompt_version", sa.String(32), nullable=True))
    op.add_column("llm_audit_events", sa.Column("model", sa.String(64), nullable=True))
    op.add_column("llm_audit_events", sa.Column("bundle_hash", sa.String(64), nullable=True))
    op.add_column("llm_audit_events", sa.Column("question_area", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_audit_events", "question_area")
    op.drop_column("llm_audit_events", "bundle_hash")
    op.drop_column("llm_audit_events", "model")
    op.drop_column("llm_audit_events", "prompt_version")
```

- [ ] **Step 7: Verify the migration runs on a scratch database**

```bash
ASTRO_DATABASE_URL="sqlite+pysqlite:///./tmp_migration_check.db" alembic upgrade head
rm -f tmp_migration_check.db
```

Expected: no errors, `0001 -> 0002` applied.

- [ ] **Step 8: Commit**

```bash
git add app/db/models.py app/interpretation/audit.py app/interpretation/llm.py \
  alembic/versions/0002_ask_audit_provenance.py tests/test_ask_audit.py
git commit -m "feat(ask): record LLM provenance and expose detailed rephrase results"
```

---

### Task 7: Weekly quota persistence

**Files:**
- Modify: `app/db/models.py` (add `AskUsageRow`)
- Modify: `app/db/repo.py` (add `consume_ask_quota`)
- Create: `alembic/versions/0003_ask_usage.py`
- Test: `tests/test_ask_quota.py` (create)

**Interfaces:**
- Produces: `PrivacyRepo.consume_ask_quota(*, user_id: str, week_start: date, limit: int) -> bool` — `True` when the question is allowed (and counted), `False` when the limit is reached. `limit <= 0` means unlimited and writes nothing.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ask_quota.py`:

```python
from datetime import date

from app.db.repo import PrivacyRepo


def _repo() -> PrivacyRepo:
    return PrivacyRepo("sqlite+pysqlite:///:memory:")


def test_quota_allows_three_then_blocks() -> None:
    repo = _repo()
    week = date(2026, 11, 16)
    results = [repo.consume_ask_quota(user_id="U1", week_start=week, limit=3) for _ in range(4)]
    assert results == [True, True, True, False]


def test_quota_is_per_user_and_per_week() -> None:
    repo = _repo()
    assert repo.consume_ask_quota(user_id="U1", week_start=date(2026, 11, 16), limit=1)
    assert not repo.consume_ask_quota(user_id="U1", week_start=date(2026, 11, 16), limit=1)
    assert repo.consume_ask_quota(user_id="U2", week_start=date(2026, 11, 16), limit=1)
    assert repo.consume_ask_quota(user_id="U1", week_start=date(2026, 11, 23), limit=1)


def test_zero_limit_is_unlimited_and_writes_nothing() -> None:
    repo = _repo()
    week = date(2026, 11, 16)
    for _ in range(5):
        assert repo.consume_ask_quota(user_id="U1", week_start=week, limit=0)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ask_quota.py -q`
Expected: FAIL with `AttributeError: 'PrivacyRepo' object has no attribute 'consume_ask_quota'`.

- [ ] **Step 3: Add the table model**

In `app/db/models.py` after `LedgerEntryRow`:

```python
class AskUsageRow(Base):
    __tablename__ = "ask_usage"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    week_start_utc: Mapped[date] = mapped_column(Date, primary_key=True)
    questions_used: Mapped[int] = mapped_column(Integer, default=0)
```

Ensure `Date` is imported (it already is for `birth_date`).

- [ ] **Step 4: Add the repo method**

In `app/db/repo.py`, inside `PrivacyRepo`:

```python
    def consume_ask_quota(self, *, user_id: str, week_start: date, limit: int) -> bool:
        if limit <= 0:
            return True
        with self._session_factory() as s, s.begin():
            row = s.get(AskUsageRow, (user_id, week_start))
            if row is None:
                s.add(
                    AskUsageRow(user_id=user_id, week_start_utc=week_start, questions_used=1)
                )
                return True
            if row.questions_used >= limit:
                return False
            row.questions_used += 1
            return True
```

Import `AskUsageRow` next to the other model imports at the top of `app/db/repo.py`, and `date` from `datetime` if not already imported.

- [ ] **Step 5: Add the migration**

Create `alembic/versions/0003_ask_usage.py`:

```python
"""Add the per-user weekly Ask quota table."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ask_usage",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("week_start_utc", sa.Date(), primary_key=True),
        sa.Column("questions_used", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("ask_usage")
```

- [ ] **Step 6: Run the tests and the migration**

```bash
python -m pytest tests/test_ask_quota.py -q
ASTRO_DATABASE_URL="sqlite+pysqlite:///./tmp_migration_check.db" alembic upgrade head
rm -f tmp_migration_check.db
```

Expected: tests PASS; migration applies `0002 -> 0003`.

- [ ] **Step 7: Commit**

```bash
git add app/db/models.py app/db/repo.py alembic/versions/0003_ask_usage.py tests/test_ask_quota.py
git commit -m "feat(ask): enforce a per-user weekly question quota"
```

---

### Task 8: Settings flags

**Files:**
- Modify: `app/config.py:35-39`
- Test: `tests/test_ask_settings.py` (create)

**Interfaces:**
- Produces: `Settings.ask_enabled: bool = False`, `Settings.ask_weekly_free_quota: int = 3`, `Settings.ask_lexicon_path: str = "rules/ask_lexicon.yaml"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ask_settings.py`:

```python
from app.config import Settings


def test_ask_is_dark_by_default() -> None:
    settings = Settings(env="test")
    assert settings.ask_enabled is False
    assert settings.ask_weekly_free_quota == 3
    assert settings.ask_lexicon_path == "rules/ask_lexicon.yaml"


def test_ask_can_be_enabled_for_tests() -> None:
    settings = Settings(env="test", ask_enabled=True, ask_weekly_free_quota=1)
    assert settings.ask_enabled is True
    assert settings.ask_weekly_free_quota == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ask_settings.py -q`
Expected: FAIL with `ValidationError` for the unknown `ask_enabled` field (or assertion failure).

- [ ] **Step 3: Add the fields**

In `app/config.py`, inside the LLM block:

```python
    # Ask endpoint (routing over approved statements; off until the owner enables it)
    ask_enabled: bool = False
    ask_weekly_free_quota: int = 3
    ask_lexicon_path: str = "rules/ask_lexicon.yaml"
```

- [ ] **Step 4: Run the config tests**

Run: `python -m pytest tests/test_ask_settings.py tests/test_s00_config.py -q`
Expected: PASS; production-validator expectations unchanged.

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_ask_settings.py
git commit -m "feat(ask): add dark-launch settings for the ask endpoint"
```

---

### Task 9: Answer composition

**Files:**
- Modify: `app/interpretation/ask.py` (append)
- Test: `tests/test_ask_compose.py` (create)

**Interfaces:**
- Consumes: `classify_question`, `is_present_time_question`, `validate_answer`, `SafeRephraser.rephrase_detailed`, `RephraseResult`, `ExplainedStatement`, `WhyThisExplanation`, `Rule`.
- Produces:
  - `@dataclass(frozen=True) AskResolution(area: LifeAreaCategory | None, matched_terms: tuple[str, ...], canonical: ExplainedStatement | None, display: ExplainedStatement | None, context: tuple[ExplainedStatement, ...], llm_used: bool, fallback_reason: str | None)`
  - `compose_answer(*, question, lang, lexicon, statements_by_area, daily_insight, rephraser=None, llm_client=None) -> AskResolution`
  - `ask_ledger_entry_id(user_id: str, statement: ExplainedStatement) -> str`
  - `outcome_criteria_for(statement: ExplainedStatement, rules: list[Rule]) -> str`
  - `bundle_hash_for(statement: ExplainedStatement) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ask_compose.py`:

```python
import pytest

from app.api.schemas import ExplainedStatement, WhyThisExplanation
from app.config import Settings
from app.interpretation.ask import (
    ask_ledger_entry_id,
    bundle_hash_for,
    compose_answer,
    load_area_lexicon,
    outcome_criteria_for,
)
from app.interpretation.audit import LLMAuditLog
from app.interpretation.llm import SafeRephraser
from app.interpretation.rules import Rule


@pytest.fixture(scope="module")
def lexicon():
    return load_area_lexicon("rules/ask_lexicon.yaml")


def _statement(rule_id: str, text: str, category: str = "career") -> ExplainedStatement:
    return ExplainedStatement(
        statement_id=f"{rule_id}_4_7",
        category=category,
        time_window="Active Moon-Ketu Dasha (until 2027-08-12)",
        simple_text=text,
        pro_text=text,
        why_this=WhyThisExplanation(
            rule_id=rule_id,
            placement_evidence="Sun in Leo (House 10, D9 Aries)",
            classical_source="BPHS",
            strength_grade="supported",
        ),
        safety_verified=True,
    )


CAREER_TEXT = "Steady professional progress is supported through structured planning."
CAREER = _statement("RULE_PARASHARI_CAREER_10H", CAREER_TEXT)
DAILY = _statement(
    "RULE_GOCHARA_CHANDRA_DAILY",
    "Today's Panchang favors steady pacing and mindful effort.",
    category="daily_insight",
)


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def complete(self, prompt: str) -> str:
        return self._reply


def _rephraser(enabled: bool = True) -> SafeRephraser:
    return SafeRephraser(
        Settings(env="test", llm_rephrase_enabled=enabled), LLMAuditLog()
    )


def test_unmapped_question_returns_no_statement(lexicon) -> None:
    result = compose_answer(
        question="How is my health in 2027?",
        lang="en",
        lexicon=lexicon,
        statements_by_area={"career": [CAREER]},
        daily_insight=None,
    )
    assert result.area is None
    assert result.canonical is None


def test_mapped_question_returns_area_statement(lexicon) -> None:
    result = compose_answer(
        question="Will I change jobs in 2027?",
        lang="en",
        lexicon=lexicon,
        statements_by_area={"career": [CAREER]},
        daily_insight=None,
    )
    assert result.area == "career"
    assert result.canonical is CAREER
    assert result.display is CAREER
    assert result.llm_used is False


def test_context_only_with_present_cue(lexicon) -> None:
    today_result = compose_answer(
        question="What should I focus on today at work?",
        lang="en",
        lexicon=lexicon,
        statements_by_area={"career": [CAREER]},
        daily_insight=DAILY,
    )
    later_result = compose_answer(
        question="Will I change jobs in 2027?",
        lang="en",
        lexicon=lexicon,
        statements_by_area={"career": [CAREER]},
        daily_insight=DAILY,
    )
    assert today_result.context == (DAILY,)
    assert later_result.context == ()


def test_accepted_reword_replaces_display_text(lexicon) -> None:
    result = compose_answer(
        question="Will I change jobs in 2027?",
        lang="en",
        lexicon=lexicon,
        statements_by_area={"career": [CAREER]},
        daily_insight=None,
        rephraser=_rephraser(),
        llm_client=_FakeLLM("Professional progress is supported through steady effort."),
    )
    assert result.llm_used is True
    assert result.canonical is CAREER
    assert result.display is not None
    assert result.display.simple_text == "Professional progress is supported through steady effort."
    assert result.display.pro_text == CAREER.pro_text


def test_reword_drifting_to_another_area_falls_back(lexicon) -> None:
    result = compose_answer(
        question="Will I change jobs in 2027?",
        lang="en",
        lexicon=lexicon,
        statements_by_area={"career": [CAREER]},
        daily_insight=None,
        rephraser=_rephraser(),
        llm_client=_FakeLLM("Your savings and loan position is supported."),
    )
    assert result.llm_used is False
    assert result.display is CAREER
    assert result.fallback_reason is not None
    assert "another life area" in result.fallback_reason


def test_short_question_still_routes(lexicon) -> None:
    result = compose_answer(
        question="Job?",
        lang="en",
        lexicon=lexicon,
        statements_by_area={"career": [CAREER]},
        daily_insight=None,
    )
    assert result.area == "career"


def test_entry_id_is_stable_and_criteria_lookup_works(lexicon) -> None:
    assert ask_ledger_entry_id("U1", CAREER) == ask_ledger_entry_id("U1", CAREER)
    assert ask_ledger_entry_id("U1", CAREER) != ask_ledger_entry_id("U2", CAREER)
    rules = [
        Rule(
            id="RULE_PARASHARI_CAREER_10H",
            category="career",
            text_key="career_10h_discipline",
            evidence_template="Sun in {sun_sign}",
            classical_source="BPHS",
            tradition="Parashari",
            strength_grade="supported",
            reviewer=None,
            reviewed_at=None,
            status="draft",
            observable_outcome_criteria="Role changed by window end.",
        )
    ]
    assert outcome_criteria_for(CAREER, rules) == "Role changed by window end."
    assert outcome_criteria_for(_statement("RULE_UNKNOWN", CAREER_TEXT), rules) == ""
    assert len(bundle_hash_for(CAREER)) == 32
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ask_compose.py -q`
Expected: FAIL with `ImportError: cannot import name 'compose_answer'`.

- [ ] **Step 3: Implement composition in `app/interpretation/ask.py`**

Append (plus the imports it needs: `hashlib`, `ExplainedStatement`, `Rule`, `SafeRephraser`, `LLMClientProtocol`, `validate_answer`):

```python
@dataclass(frozen=True)
class AskResolution:
    area: LifeAreaCategory | None
    matched_terms: tuple[str, ...]
    canonical: ExplainedStatement | None
    display: ExplainedStatement | None
    context: tuple[ExplainedStatement, ...]
    llm_used: bool
    fallback_reason: str | None


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


def compose_answer(
    *,
    question: str,
    lang: LanguageCode,
    lexicon: AreaLexicon,
    statements_by_area: Mapping[str, list[ExplainedStatement]],
    daily_insight: ExplainedStatement | None,
    rephraser: SafeRephraser | None = None,
    llm_client: LLMClientProtocol | None = None,
) -> AskResolution:
    area, matched = classify_question(question, lexicon)
    if area is None:
        return AskResolution(None, (), None, None, (), False, None)
    candidates = statements_by_area.get(area) or []
    if not candidates:
        return AskResolution(area, tuple(matched), None, None, (), False, None)
    canonical = candidates[0]
    context: tuple[ExplainedStatement, ...] = (
        (daily_insight,) if daily_insight and is_present_time_question(question, lexicon) else ()
    )
    display = canonical
    llm_used = False
    fallback_reason: str | None = None
    if rephraser is not None and llm_client is not None:

        def check(reference: str, candidate: str) -> None:
            validate_answer(
                bundle=reference,
                question=question,
                area=area,
                answer=candidate,
                lang=lang,
                lexicon=lexicon,
            )

        outcome = rephraser.rephrase_detailed(
            canonical.simple_text,
            lang=lang,
            client=llm_client,
            validator=check,
            prompt_version="ask-answer-v1",
            bundle_hash=bundle_hash_for(canonical),
            question_area=area,
        )
        llm_used = outcome.accepted
        fallback_reason = outcome.fallback_reason
        if outcome.accepted:
            display = canonical.model_copy(update={"simple_text": outcome.text})
    return AskResolution(
        area=area,
        matched_terms=tuple(matched),
        canonical=canonical,
        display=display,
        context=context,
        llm_used=llm_used,
        fallback_reason=fallback_reason,
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
```

Use `from collections.abc import Mapping` and add `from app.api.schemas import ExplainedStatement, LanguageCode`. Import `SafeRephraser` and `LLMClientProtocol` from `app.interpretation.llm`, `validate_answer` from `app.interpretation.guardrails`, `Rule` from `app.interpretation.rules`. All four modules already import `guardrails`/`schemas`, so no cycle is introduced (`llm.py` imports `guardrails`, not `ask.py`).

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_ask_compose.py tests/test_validate_answer.py -q`
Expected: PASS.

- [ ] **Step 5: Run ruff and mypy on the touched module**

Run: `python -m ruff check app/interpretation/ask.py && python -m mypy app/interpretation/ask.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/interpretation/ask.py tests/test_ask_compose.py
git commit -m "feat(ask): compose guarded answers with optional rewording"
```

---

### Task 10: Schemas, route, telemetry and OpenAPI

**Files:**
- Modify: `app/api/schemas.py` (models + telemetry literal)
- Modify: `app/api/routes.py` (imports, router wiring, route)
- Modify: `openapi.json` (regenerated)
- Test: `tests/test_ask_api.py` (create)

**Interfaces:**
- Consumes: everything from Tasks 1–9.
- Produces: `POST /v1/readings/ask` accepting `AskRequest`, returning `AskResponse`; telemetry event types `ask_answered`, `ask_uncovered`.

- [ ] **Step 1: Write the failing API tests**

Create `tests/test_ask_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

DETAILS = {
    "name": "Aarav",
    "birth_date": "1993-11-14",
    "birth_time": "10:15:00",
    "place_name": "Pune",
    "latitude": 18.5204,
    "longitude": 73.8567,
    "uncertainty_minutes": 10,
    "node_type": "MEAN",
    "language": "en",
}
HEADERS = {"X-User-Id": "U_ASK"}


@pytest.fixture
def ask_client():
    settings = Settings(
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        allow_draft_rules=True,
        geocode_provider="manual_only",
        ask_enabled=True,
        ask_weekly_free_quota=3,
    )
    return TestClient(create_app(settings))


@pytest.fixture
def dark_client():
    settings = Settings(
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        allow_draft_rules=True,
        geocode_provider="manual_only",
    )
    return TestClient(create_app(settings))


def test_ask_is_503_when_disabled(dark_client) -> None:
    r = dark_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "Will I change jobs?"},
        headers=HEADERS,
    )
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "ask_disabled"


def test_answered_career_question(ask_client) -> None:
    r = ask_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "Will I change jobs before mid-2027?"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["coverage"]["status"] == "answered"
    assert body["coverage"]["area"] == "career"
    assert body["coverage"]["available_areas"] == ["career", "relationships", "finances", "home"]
    assert body["statement"]["why_this"]["rule_id"] == "RULE_PARASHARI_CAREER_10H"
    assert body["statement"]["safety_verified"] is True
    assert body["llm"]["used"] is False
    assert body["ledger_entry_id"].startswith("ASK-")
    assert body["disclaimer"]


def test_answered_is_idempotent_in_the_ledger(ask_client) -> None:
    payload = {"details": DETAILS, "question": "Will I change jobs before mid-2027?"}
    first = ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS).json()
    second = ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS).json()
    assert first["ledger_entry_id"] == second["ledger_entry_id"]


def test_uncovered_question_costs_nothing(ask_client) -> None:
    payload = {"details": DETAILS, "question": "How is my health in 2027?"}
    r = ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["coverage"] == {
        "status": "uncovered",
        "area": None,
        "matched_terms": [],
        "available_areas": ["career", "relationships", "finances", "home"],
    }
    assert body["statement"] is None
    assert body["ledger_entry_id"] is None
    # Two more uncovered questions must not consume the 3-answer quota.
    for _ in range(2):
        assert ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS).status_code == 200
    answered = ask_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "Should I take a loan this year?"},
        headers=HEADERS,
    )
    assert answered.status_code == 200
    assert answered.json()["coverage"]["area"] == "finances"


def test_short_question_is_422(ask_client) -> None:
    r = ask_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "hi"},
        headers=HEADERS,
    )
    assert r.status_code == 422


def test_quota_blocks_the_fourth_answer(ask_client) -> None:
    payload = {"details": DETAILS, "question": "Should I take a loan this year?"}
    codes = [
        ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ask_api.py -q`
Expected: FAIL with 404 for the route.

- [ ] **Step 3: Add the schemas**

In `app/api/schemas.py`, extend `TelemetryEventType` with `"ask_answered"` and `"ask_uncovered"`, and append:

```python
class AskRequest(BaseModel):
    details: BirthDetailsInput
    question: str = Field(..., min_length=3, max_length=280)
    target_date: date | None = None


class AskCoverage(BaseModel):
    status: Literal["answered", "uncovered"]
    area: LifeAreaCategory | None
    matched_terms: list[str]
    available_areas: list[LifeAreaCategory]


class LLMProvenance(BaseModel):
    used: bool
    model: str | None = None
    fallback_reason: str | None = None


class AskResponse(BaseModel):
    request_id: str
    coverage: AskCoverage
    statement: ExplainedStatement | None
    context: list[ExplainedStatement] = Field(default_factory=list)
    ledger_entry_id: str | None = None
    llm: LLMProvenance
    disclaimer: str
```

- [ ] **Step 4: Wire the route**

In `app/api/routes.py`:

Add imports: `from uuid import uuid4`; `AskCoverage`, `AskRequest`, `AskResponse`, `LLMProvenance` to the schemas import; `from app.interpretation.ask import AREA_ORDER, ask_ledger_entry_id, classify_question, compose_answer, infer_target_date, is_present_time_question, iso_week_start, load_area_lexicon, outcome_criteria_for`; `from app.interpretation.audit import LLMAuditLog`; `from app.interpretation.llm import SafeRephraser`.

In `build_router`, next to `rules = load_rules(...)`:

```python
    ask_lexicon = load_area_lexicon(settings.ask_lexicon_path)
    rephraser = SafeRephraser(settings, LLMAuditLog(session_factory=repo.session_factory))
```

Add the route after `/readings/life-areas`:

```python
    @router.post("/readings/ask", response_model=AskResponse)
    async def ask(
        req: AskRequest,
        auth_user: str = Depends(current_user_dep),
    ) -> AskResponse:
        lang = req.details.language
        if not settings.ask_enabled:
            raise HTTPException(
                503,
                {
                    "error": "ask_disabled",
                    "message": catalog.get("error.ask_disabled", lang),
                },
            )
        question = req.question.strip()
        if len(question) < 3 or "\x00" in question:
            raise HTTPException(
                422,
                {
                    "error": "ask_question_invalid",
                    "message": catalog.get("error.ask_question_invalid", lang),
                },
            )

        def uncovered(area: LifeAreaCategory | None, matched: list[str]) -> AskResponse:
            return AskResponse(
                request_id=str(uuid4()),
                coverage=AskCoverage(
                    status="uncovered",
                    area=area,
                    matched_terms=matched,
                    available_areas=list(AREA_ORDER),
                ),
                statement=None,
                context=[],
                ledger_entry_id=None,
                llm=LLMProvenance(used=False),
                disclaimer=catalog.get("trust.professional_advice_disclaimer", lang),
            )

        area, matched = classify_question(question, ask_lexicon)
        if area is None:
            repo.record_telemetry(
                event_type="ask_uncovered",
                category=None,
                rule_id=None,
                language=lang,
                cohort_hash=None,
            )
            return uncovered(None, [])

        try:
            lat, lon, tz = await _resolve(req.details, settings)
            today = _today_in_tz(tz)
            eff_date = req.target_date or infer_target_date(question, today=today) or today
            c = calculate_chart(req.details, lat, lon, tz)
            moon = next(p for p in c.planets if p.planet == "Moon")
            d = calculate_vimshottari_dasha(req.details.birth_date, moon.longitude, eff_date)
            t = evaluate_current_transits(c, eff_date)
            areas = generate_life_area_readings(c, d, t, rules, catalog, lang)
            daily = None
            if is_present_time_question(question, ask_lexicon):
                p = calculate_daily_panchang(eff_date, lat, lon, tz)
                daily = generate_daily_insight(c, p, t, catalog, lang)
        except Exception as exc:
            # G5: never echo exception text (it can contain birth details) to the caller.
            raise HTTPException(502, {"error": "chart_unavailable"}) from exc

        resolution = compose_answer(
            question=question,
            lang=lang,
            lexicon=ask_lexicon,
            statements_by_area=areas,
            daily_insight=daily,
            rephraser=rephraser,
            llm_client=None,
        )
        if resolution.canonical is None or resolution.display is None:
            return uncovered(area, list(resolution.matched_terms))

        if not repo.consume_ask_quota(
            user_id=auth_user,
            week_start=iso_week_start(today),
            limit=settings.ask_weekly_free_quota,
        ):
            raise HTTPException(
                429,
                {
                    "error": "ask_quota_exhausted",
                    "message": catalog.get("error.ask_quota_exhausted", lang),
                },
            )

        statement = resolution.canonical
        entry_id: str | None = None
        criteria = outcome_criteria_for(statement, rules)
        if criteria:
            entry = ledger.register_or_get(
                entry_id=ask_ledger_entry_id(auth_user, statement),
                user_id=auth_user,
                statement_id=statement.statement_id,
                rule_id=statement.why_this.rule_id,
                statement_text=statement.simple_text,
                confidence_grade=statement.why_this.strength_grade,
                time_window=statement.time_window,
                observable_outcome_criteria=criteria,
                safety_category="life_area",
            )
            entry_id = entry.entry_id

        repo.record_telemetry(
            event_type="ask_answered",
            category=area,
            rule_id=statement.why_this.rule_id,
            language=lang,
            cohort_hash=None,
        )
        return AskResponse(
            request_id=str(uuid4()),
            coverage=AskCoverage(
                status="answered",
                area=area,
                matched_terms=list(resolution.matched_terms),
                available_areas=list(AREA_ORDER),
            ),
            statement=resolution.display,
            context=list(resolution.context),
            ledger_entry_id=entry_id,
            llm=LLMProvenance(
                used=resolution.llm_used,
                model=settings.anthropic_model if resolution.llm_used else None,
                fallback_reason=resolution.fallback_reason,
            ),
            disclaimer=catalog.get("trust.professional_advice_disclaimer", lang),
        )
```

Add `LifeAreaCategory` to the schemas import if it is not already imported.

**Rewording stays inert on purpose.** `llm_client=None` is not a placeholder: no provider adapter exists in this repo (see Task 6 Interfaces), so `SafeRephraser` returns the canonical sentence with `used=False`. Do not invent a client here. Reword acceptance and rejection are already covered by the fake-client tests in Task 9; a real adapter is separate work that needs its own review.

- [ ] **Step 5: Run the API tests**

Run: `python -m pytest tests/test_ask_api.py -q`
Expected: PASS. If `test_quota_blocks_the_fourth_answer` returns 422, check that `AskRequest.question` max length is 280 and the quota fixture limit is 3.

- [ ] **Step 6: Regenerate the OpenAPI snapshot**

```bash
make openapi
git diff --stat openapi.json
```

Expected: the diff adds `/v1/readings/ask` and the new schemas only.

- [ ] **Step 7: Run the API regression suite**

Run: `python -m pytest tests/test_s17_api.py tests/test_openapi_freeze.py tests/test_s11_readings_festivals.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app/api/schemas.py app/api/routes.py openapi.json tests/test_ask_api.py
git commit -m "feat(ask): add POST /v1/readings/ask with ledger and quota enforcement"
```

---

### Task 11: Full acceptance

**Files:** none (verification only).

- [ ] **Step 1: Run the full suite**

Run: `make test`
Expected: PASS, including all new `tests/test_ask_*.py` files.

- [ ] **Step 2: Run lint, types and guardrails**

Run: `make lint types guardrails`
Expected: PASS. `G7-scope` must not report a `free_form_chat` module; `G6-i18n` must report parity.

- [ ] **Step 3: Verify the OpenAPI snapshot is committed**

Run: `make openapi-check`
Expected: exit 0 (no diff).

- [ ] **Step 4: Run the blueprint validator and release gates**

```bash
python scripts/validate_step.py --all
make gate-g1
make gate-g2
```

Expected: PASS, unchanged from before this feature. If G2 changes status, stop: this plan must not affect it.

- [ ] **Step 5: Manual smoke (optional, dev)**

```bash
make run
curl -s -X POST localhost:8000/v1/readings/ask \
  -H 'Content-Type: application/json' -H 'X-User-Id: U1' \
  -d '{"details":{"name":"Aarav","birth_date":"1993-11-14","birth_time":"10:15:00","place_name":"Pune","latitude":18.5204,"longitude":73.8567,"language":"en"},"question":"Will I change jobs before mid-2027?"}'
```

Expected with default settings: HTTP 503 `ask_disabled`. With `ASTRO_ASK_ENABLED=true`, the answered payload above.

- [ ] **Step 6: Report**

Summarise: tests added, files touched, migration ids, and the fact that the endpoint ships dark (`ask_enabled=false`) and LLM rewording remains inert until a provider adapter is wired.
