"""Optional LLM rewording. Off by default; hard-capped by llm_monthly_call_cap;
falls back on any guardrail error."""

from __future__ import annotations

from typing import Protocol

from app.config import Settings
from app.interpretation.audit import LLMAuditLog
from app.interpretation.guardrails import validate_rephrase


class LLMClientProtocol(Protocol):
    def complete(self, prompt: str) -> str: ...


class SafeRephraser:
    def __init__(self, settings: Settings, audit_log: LLMAuditLog) -> None:
        self._s = settings
        self._audit = audit_log
        self._calls_used = 0

    def rephrase(self, sentence: str, *, lang: str, client: LLMClientProtocol | None = None) -> str:
        if not self._s.llm_rephrase_enabled or client is None:
            return sentence
        if self._calls_used >= self._s.llm_monthly_call_cap:
            self._audit.record(
                lang,
                accepted=False,
                prompt=sentence,
                output="",
                fallback_reason="monthly_cap_reached",
            )
            return sentence
        self._calls_used += 1
        candidate = ""
        try:
            candidate = client.complete(sentence)
            validate_rephrase(sentence, candidate)
            self._audit.record(lang, accepted=True, prompt=sentence, output=candidate)
            return candidate
        except Exception as exc:
            self._audit.record(
                lang,
                accepted=False,
                prompt=sentence,
                output=candidate,
                fallback_reason=str(exc),
            )
            return sentence
