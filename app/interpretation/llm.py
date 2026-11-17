"""Optional LLM rewording. Off by default; hard-capped by llm_monthly_call_cap;
falls back on any guardrail error. rephrase_detailed reports whether a call was
attempted and accepted, plus an optional fallback reason; rephrase returns its text."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings
from app.interpretation.audit import LLMAuditLog
from app.interpretation.guardrails import validate_rephrase


class LLMClientProtocol(Protocol):
    def complete(self, prompt: str) -> str: ...


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
