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
