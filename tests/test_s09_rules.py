import pytest

from app.interpretation.errors import RuleSchemaError
from app.interpretation.rules import load_rules

pytestmark = pytest.mark.s09


def test_drafts_load_in_dev_including_yogas_and_doshas() -> None:
    rules = load_rules("rules/mvp_rules.yaml", allow_draft=True)
    assert len(rules) == 8
    assert {"career", "relationships", "finances", "home", "yoga", "dosha_context"}.issubset(
        {r.category for r in rules}
    )


def test_drafts_refused_in_production() -> None:
    with pytest.raises(RuleSchemaError, match="G2"):
        load_rules("rules/mvp_rules.yaml", allow_draft=False)
