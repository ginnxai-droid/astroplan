import json
from pathlib import Path

import pytest
import yaml

from app.core.festivals import load_festivals
from app.interpretation.rules import load_rules

pytestmark = pytest.mark.release_gate_g2


def test_g2_advisor_signoff_complete() -> None:
    rules = load_rules("rules/mvp_rules.yaml", allow_draft=False)
    assert len(rules) >= 8
    festivals = load_festivals("data/festivals.yaml", allow_draft=False)
    assert len(festivals) >= 1
    tables = yaml.safe_load(Path("rules/ashtakoota_tables.yaml").read_text(encoding="utf-8"))
    assert tables.get("status") == "approved" and tables.get("reviewer")
    meta = json.loads(Path("i18n/_meta.json").read_text(encoding="utf-8"))
    for lang in ("en", "hi", "mr"):
        assert meta[lang]["status"] == "approved"
        assert meta[lang]["reviewer"] and meta[lang]["reviewed_at"]
