from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.schemas import StrengthGrade
from app.interpretation.guardrails import verify_text

OutcomeMark = Literal["hit", "miss", "ambiguous"]

GRADE_PROBABILITY: dict[StrengthGrade, float] = {
    "likely": 0.75,
    "supported": 0.65,
    "weak": 0.45,
    "contested": 0.35,
}


class PreRegisteredLedgerEntry(BaseModel):
    entry_id: str
    user_id: str
    statement_id: str
    rule_id: str
    statement_text: str
    confidence_grade: StrengthGrade
    assigned_probability: float
    time_window: str
    observable_outcome_criteria: str
    safety_category: str
    registered_at_utc: datetime
    user_outcome: OutcomeMark | None = None
    outcome_logged_at_utc: datetime | None = None


class PredictionLedgerService:
    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self._sf = session_factory
        self._entries: dict[str, PreRegisteredLedgerEntry] = {}

    def register(
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
        verify_text(statement_text)
        now = datetime.now(UTC)
        prob = GRADE_PROBABILITY[confidence_grade]
        entry = PreRegisteredLedgerEntry(
            entry_id=entry_id,
            user_id=user_id,
            statement_id=statement_id,
            rule_id=rule_id,
            statement_text=statement_text,
            confidence_grade=confidence_grade,
            assigned_probability=prob,
            time_window=time_window,
            observable_outcome_criteria=observable_outcome_criteria,
            safety_category=safety_category,
            registered_at_utc=now,
        )
        self._entries[entry_id] = entry
        if self._sf is not None:
            from app.db.models import LedgerEntryRow

            with self._sf() as s, s.begin():
                s.merge(
                    LedgerEntryRow(
                        entry_id=entry_id,
                        user_id=user_id,
                        statement_id=statement_id,
                        rule_id=rule_id,
                        statement_text=statement_text,
                        confidence_grade=confidence_grade,
                        assigned_probability=prob,
                        time_window=time_window,
                        observable_outcome_criteria=observable_outcome_criteria,
                        safety_category=safety_category,
                        registered_at_utc=now,
                    )
                )
        return entry

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
        for existing in self._all_entries():
            if existing.entry_id == entry_id:
                if existing.user_id == user_id:
                    return existing
                raise ValueError("entry id belongs to another user")
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

    def mark_outcome(self, entry_id: str, outcome: OutcomeMark) -> PreRegisteredLedgerEntry:
        now = datetime.now(UTC)
        if self._sf is not None:
            from app.db.models import LedgerEntryRow

            with self._sf() as s, s.begin():
                row = s.scalar(select(LedgerEntryRow).where(LedgerEntryRow.entry_id == entry_id))
                if row is None:
                    raise KeyError(entry_id)
                row.user_outcome = outcome
                row.outcome_logged_at_utc = now
                entry = PreRegisteredLedgerEntry(
                    entry_id=row.entry_id,
                    user_id=row.user_id,
                    statement_id=row.statement_id,
                    rule_id=row.rule_id,
                    statement_text=row.statement_text,
                    confidence_grade=row.confidence_grade,
                    assigned_probability=float(row.assigned_probability),
                    time_window=row.time_window,
                    observable_outcome_criteria=row.observable_outcome_criteria,
                    safety_category=row.safety_category,
                    registered_at_utc=row.registered_at_utc,
                    user_outcome=outcome,
                    outcome_logged_at_utc=now,
                )
                self._entries[entry_id] = entry
                return entry
        if entry_id not in self._entries:
            raise KeyError(entry_id)
        e = self._entries[entry_id]
        e.user_outcome = outcome
        e.outcome_logged_at_utc = now
        return e

    def _all_entries(self, user_id: str | None = None) -> list[PreRegisteredLedgerEntry]:
        if self._sf is not None:
            from app.db.models import LedgerEntryRow

            with self._sf() as s:
                stmt = select(LedgerEntryRow)
                if user_id is not None:
                    stmt = stmt.where(LedgerEntryRow.user_id == user_id)
                rows = s.scalars(stmt).all()
                return [
                    PreRegisteredLedgerEntry(
                        entry_id=r.entry_id,
                        user_id=r.user_id,
                        statement_id=r.statement_id,
                        rule_id=r.rule_id,
                        statement_text=r.statement_text,
                        confidence_grade=r.confidence_grade,
                        assigned_probability=float(r.assigned_probability),
                        time_window=r.time_window,
                        observable_outcome_criteria=r.observable_outcome_criteria,
                        safety_category=r.safety_category,
                        registered_at_utc=r.registered_at_utc,
                        user_outcome=r.user_outcome,
                        outcome_logged_at_utc=r.outcome_logged_at_utc,
                    )
                    for r in rows
                ]
        vals = list(self._entries.values())
        return [e for e in vals if user_id is None or e.user_id == user_id]

    def calibration_summary(self, user_id: str | None = None) -> dict[str, object]:
        entries = self._all_entries(user_id=user_id)
        resolved = [e for e in entries if e.user_outcome is not None]
        binary = [e for e in resolved if e.user_outcome in ("hit", "miss")]
        brier = None
        if binary:
            se = [
                (e.assigned_probability - (1.0 if e.user_outcome == "hit" else 0.0)) ** 2
                for e in binary
            ]
            brier = round(sum(se) / len(se), 4)
        return {
            "scope_user_id": user_id or "global",
            "total_pre_registered": len(entries),
            "total_outcomes_logged": len(resolved),
            "counts": {
                "hit": sum(1 for e in resolved if e.user_outcome == "hit"),
                "miss": sum(1 for e in resolved if e.user_outcome == "miss"),
                "ambiguous": sum(1 for e in resolved if e.user_outcome == "ambiguous"),
            },
            "brier_calibration_score": brier,
            "methodology_statement": (
                "This log summarizes how often users reported each pre-registered outcome. "
                "It is a calibration log, not a scientific or validated accuracy claim."
            ),
        }
