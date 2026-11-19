import pytest

from app.interpretation.errors import RuleSchemaError
from app.interpretation.rules import load_rules

pytestmark = pytest.mark.s09


def test_all_rules_load_in_dev() -> None:
    rules = load_rules("rules/mvp_rules.yaml", allow_draft=True)
    assert len(rules) == 8
    assert {"career", "relationships", "finances", "home", "yoga", "dosha_context"}.issubset(
        {r.category for r in rules}
    )


def test_drafts_refused_in_production(tmp_path) -> None:
    draft = tmp_path / "draft_rules.yaml"
    draft.write_text(
        "- id: RULE_TEST_DRAFT\n"
        "  category: career\n"
        "  text_key: career_10h_discipline\n"
        '  evidence_template: "Sun in {sun_sign}"\n'
        '  classical_source: "BPHS, Ch. 21"\n'
        "  strength_grade: supported\n"
        "  status: draft\n",
        encoding="utf-8",
    )
    with pytest.raises(RuleSchemaError, match="G2"):
        load_rules(draft, allow_draft=False)
