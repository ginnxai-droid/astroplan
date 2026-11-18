import pytest

from app.config import DEFAULT_DEV_SHARE_SECRET, Settings

pytestmark = pytest.mark.s00

GOOD = {
    "env": "production",
    "database_url": "postgresql+psycopg://astro:pw@db:5432/astroplan",
    "legal_gate_approved": True,
    "legal_gate_reference": "OWNER-2026-11-18-AGPL3",
    "source_offer_url": "https://github.com/ginnxai-droid/astroplan",
    "require_swiss_files": True,
    "allow_draft_rules": False,
    "auth_mode": "firebase",
    "field_encryption_keys": "k",
    "share_token_secret": "prod-super-secret-hmac-signing-key-32chars!",
    "operator_api_key": "prod-operator-secret-key-123",
}


def test_production_accepts_fully_gated_config() -> None:
    assert Settings(**GOOD).env == "production"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"legal_gate_approved": False}, "G0"),
        ({"legal_gate_reference": " "}, "G0"),
        ({"source_offer_url": ""}, "G0"),
        ({"source_offer_url": "http://example.com/source"}, "G0"),
        ({"require_swiss_files": False}, "G1"),
        ({"allow_draft_rules": True}, "G2"),
        ({"auth_mode": "dev"}, "G5"),
        ({"field_encryption_keys": ""}, "G5"),
        ({"share_token_secret": DEFAULT_DEV_SHARE_SECRET}, "M3"),
        ({"share_token_secret": "short-secret"}, "M3"),
        ({"operator_api_key": "dev-operator-key"}, "M2"),
        ({"database_url": "sqlite+pysqlite:///:memory:"}, "G5"),
    ],
)
def test_production_refuses_missing_guardrail(override: dict[str, object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        Settings(**{**GOOD, **override})  # type: ignore[arg-type]


def test_dev_defaults_safe() -> None:
    s = Settings(env="dev")
    assert s.llm_rephrase_enabled is False
    assert s.legal_gate_approved is False
    assert s.source_offer_url == ""
