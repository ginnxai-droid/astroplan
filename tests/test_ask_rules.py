import pytest

from app.interpretation.errors import RuleSchemaError
from app.interpretation.rules import load_rules


def test_area_rules_carry_outcome_criteria() -> None:
    rules = load_rules("rules/mvp_rules.yaml", allow_draft=True)
    areas = {"career", "relationships", "finances", "home"}
    for rule in rules:
        if rule.category in areas:
            assert rule.observable_outcome_criteria.strip(), rule.id


def test_approved_rule_without_criteria_fails(tmp_path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        "\n".join(
            [
                "- id: RULE_X",
                "  category: career",
                "  text_key: career_10h_discipline",
                "  evidence_template: Sun in {sun_sign}",
                "  classical_source: BPHS",
                "  tradition: Parashari",
                "  strength_grade: supported",
                "  reviewer: advisor",
                "  reviewed_at: 2026-11-17",
                "  status: approved",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuleSchemaError, match="observable_outcome_criteria"):
        load_rules(path, allow_draft=False)
