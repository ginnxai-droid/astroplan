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
    assert validate_rephrase("Progress in 2027.", "Progress in 2027 is supported.")
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
    "answer",
    [
        "Career progress is supported?",
        "As an AI, career progress is supported.",
        "Supported.",
        "- career progress\n- supported effort",
    ],
)
def test_bad_shape_and_meta_are_rejected(answer: str) -> None:
    with pytest.raises(GuardrailViolation):
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
