import pytest

from app.interpretation.errors import GuardrailViolation
from app.interpretation.guardrails import validate_rephrase, verify_text

pytestmark = pytest.mark.s01


@pytest.mark.parametrize(
    "text",
    [
        "This is 100% accurate.",
        "Guaranteed results.",
        "You will definitely succeed.",
        "You will face death soon.",
        "Bankruptcy is coming.",
        "Black magic is affecting you.",
        "Buy this gemstone for a paid remedy.",
    ],
)
def test_english_fear_claims_blocked(text: str) -> None:
    with pytest.raises(GuardrailViolation):
        verify_text(text)


@pytest.mark.parametrize(
    "text",
    [
        "आपकी मृत्यु निकट है।",
        "यह भविष्यवाणी 100% सटीक है।",
        "आपको दिवालिया होने का श्राप है।",
    ],
)
def test_hindi_fear_blocked(text: str) -> None:
    with pytest.raises(GuardrailViolation):
        verify_text(text, languages=("hi",))


@pytest.mark.parametrize("text", ["तुमचा मृत्यू जवळ आहे.", "हे 100% अचूक आहे."])
def test_marathi_fear_blocked(text: str) -> None:
    with pytest.raises(GuardrailViolation):
        verify_text(text, languages=("mr",))


def test_marathi_standalone_hami_blocked_but_nehami_allowed() -> None:
    with pytest.raises(GuardrailViolation):
        verify_text("आम्ही हमी देतो.", languages=("mr",))
    assert verify_text("महत्त्वाच्या निर्णयांसाठी नेहमी तज्ज्ञांचा सल्ला घ्यावा.", languages=("mr",))


def test_hindi_standalone_fear_blocked_but_substring_word_allowed() -> None:
    with pytest.raises(GuardrailViolation):
        verify_text("यह गारंटी है।", languages=("hi",))
    with pytest.raises(GuardrailViolation):
        verify_text("रोग की आशंका है।", languages=("hi",))
    assert verify_text("आरोग्य उत्तम राहावे.", languages=("hi",))


def test_validate_rephrase_blocks_new_digits_rule_id_placements_and_grade_drift() -> None:
    with pytest.raises(GuardrailViolation, match="new digits"):
        validate_rephrase("Progress in 2026.", "Progress in 2026 and 2027.")
    with pytest.raises(GuardrailViolation, match="rule IDs"):
        validate_rephrase("Progress is supported.", "Per rule_id X, progress is supported.")
    with pytest.raises(GuardrailViolation, match="ungrounded placements"):
        validate_rephrase(
            "Jupiter in Cancer is supported.", "Jupiter and Mars in Aries is supported."
        )
    with pytest.raises(GuardrailViolation, match="ungrounded placements"):
        validate_rephrase("बृहस्पति कर्क में है।", "बृहस्पति और शनि मेष में हैं।")
    with pytest.raises(GuardrailViolation, match="strength-grade"):
        validate_rephrase("Jupiter in Cancer is supported.", "Jupiter in Cancer is likely.")
    with pytest.raises(GuardrailViolation, match="strength-grade"):
        validate_rephrase("Jupiter in Cancer brings calm.", "Jupiter in Cancer is likely.")
    with pytest.raises(GuardrailViolation, match="classical source"):
        validate_rephrase("Supported per BPHS.", "Supported generally.")
