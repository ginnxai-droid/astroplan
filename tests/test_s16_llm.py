import pytest

from app.config import Settings
from app.db.session import make_engine_and_session
from app.interpretation.audit import LLMAuditLog
from app.interpretation.llm import SafeRephraser

pytestmark = pytest.mark.s16


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def complete(self, prompt: str) -> str:
        return self._reply


def test_llm_disabled_by_default_returns_template() -> None:
    audit = LLMAuditLog()
    r = SafeRephraser(Settings(env="test", llm_rephrase_enabled=False), audit)
    orig = "Steady professional progress is supported."
    assert r.rephrase(orig, lang="en", client=_FakeLLM("Guaranteed 100% accurate!")) == orig
    assert len(audit.events) == 0


def test_llm_audit_stores_encrypted_prompt_and_output_in_sql() -> None:
    _, sf = make_engine_and_session("sqlite+pysqlite:///:memory:")
    audit = LLMAuditLog(session_factory=sf)
    r = SafeRephraser(
        Settings(env="test", llm_rephrase_enabled=True, llm_monthly_call_cap=2), audit
    )
    orig = "Progress in 2027 is supported."
    bad = "Progress in 2028 is guaranteed."
    assert r.rephrase(orig, lang="en", client=_FakeLLM(bad)) == orig
    ev = audit.events[-1]
    assert ev.accepted is False
    assert b"2027" not in ev.prompt_ciphertext
    assert ev.decrypted_prompt_and_output() == (orig, bad)

    # Verify SQL persistence across a fresh LLMAuditLog instance
    reader_audit = LLMAuditLog(session_factory=sf)
    assert reader_audit.total_persisted_calls() == 1
