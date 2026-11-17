from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.crypto import decrypt_str, encrypt_str


@dataclass(frozen=True)
class LLMAuditEvent:
    timestamp_utc: datetime
    lang: str
    accepted: bool
    prompt_ciphertext: bytes
    output_ciphertext: bytes
    fallback_reason: str | None
    prompt_version: str | None = None
    model: str | None = None
    bundle_hash: str | None = None
    question_area: str | None = None

    def decrypted_prompt_and_output(self) -> tuple[str, str]:
        return decrypt_str(self.prompt_ciphertext), decrypt_str(self.output_ciphertext)


class LLMAuditLog:
    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self._sf = session_factory
        self.events: list[LLMAuditEvent] = []

    def record(
        self,
        lang: str,
        accepted: bool,
        prompt: str,
        output: str,
        fallback_reason: str | None = None,
        prompt_version: str | None = None,
        model: str | None = None,
        bundle_hash: str | None = None,
        question_area: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        p_enc = encrypt_str(prompt)
        o_enc = encrypt_str(output)
        ev = LLMAuditEvent(
            timestamp_utc=now,
            lang=lang,
            accepted=accepted,
            prompt_ciphertext=p_enc,
            output_ciphertext=o_enc,
            fallback_reason=fallback_reason,
            prompt_version=prompt_version,
            model=model,
            bundle_hash=bundle_hash,
            question_area=question_area,
        )
        self.events.append(ev)
        if self._sf is not None:
            from app.db.models import LLMAuditRow

            with self._sf() as s, s.begin():
                s.add(
                    LLMAuditRow(
                        timestamp_utc=now,
                        lang=lang,
                        accepted=accepted,
                        prompt_ciphertext=p_enc,
                        output_ciphertext=o_enc,
                        fallback_reason=fallback_reason,
                        prompt_version=prompt_version,
                        model=model,
                        bundle_hash=bundle_hash,
                        question_area=question_area,
                    )
                )

    def total_persisted_calls(self) -> int:
        if self._sf is not None:
            from app.db.models import LLMAuditRow

            with self._sf() as s:
                count = s.scalar(select(func.count(LLMAuditRow.id)))
                return int(count or 0)
        return len(self.events)
