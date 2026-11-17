from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from app.api.schemas import StrengthGrade
from app.interpretation.errors import RuleSchemaError
from app.interpretation.guardrails import verify_text

Status = Literal["draft", "approved"]


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    text_key: str
    evidence_template: str
    classical_source: str
    tradition: str
    strength_grade: StrengthGrade
    reviewer: str | None
    reviewed_at: str | None
    status: Status
    observable_outcome_criteria: str = ""


def load_rules(path: str | Path, *, allow_draft: bool) -> list[Rule]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    out: list[Rule] = []
    for entry in raw:
        try:
            rule = Rule(
                id=entry["id"],
                category=entry["category"],
                text_key=entry["text_key"],
                evidence_template=entry["evidence_template"],
                classical_source=entry["classical_source"],
                tradition=entry.get("tradition", "Parashari"),
                strength_grade=entry["strength_grade"],
                reviewer=entry.get("reviewer"),
                reviewed_at=entry.get("reviewed_at"),
                status=entry.get("status", "draft"),
                observable_outcome_criteria=str(
                    entry.get("observable_outcome_criteria") or ""
                ).strip(),
            )
        except KeyError as exc:
            raise RuleSchemaError(f"rule {entry.get('id', '?')}: missing {exc}") from exc
        verify_text(rule.classical_source)
        verify_text(rule.evidence_template)
        if rule.observable_outcome_criteria:
            verify_text(rule.observable_outcome_criteria)
        if rule.status == "draft" and not allow_draft:
            raise RuleSchemaError(f"G2: rule {rule.id} draft but allow_draft false")
        if rule.status == "approved" and not (rule.reviewer and rule.reviewed_at):
            raise RuleSchemaError(f"G2: approved rule {rule.id} missing reviewer/reviewed_at")
        if rule.status == "approved" and not rule.observable_outcome_criteria:
            raise RuleSchemaError(
                f"G2: approved rule {rule.id} missing observable_outcome_criteria"
            )
        out.append(rule)
    return out
