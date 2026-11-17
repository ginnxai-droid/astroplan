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
    return SafeRephraser(Settings(env="test", llm_rephrase_enabled=enabled), LLMAuditLog())


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
