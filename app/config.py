"""Application settings. Production guardrails (G0, G1, G2, G5, M2, M3) enforced here in code."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_SHARE_SECRET = "dev-share-secret-change-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASTRO_", extra="ignore")

    env: Literal["dev", "test", "staging", "production"] = "dev"
    database_url: str = "sqlite+pysqlite:///./astroplan_dev.db"

    # Ephemeris. Empty path -> built-in Moshier fallback (dev/test only).
    ephe_path: str = ""
    require_swiss_files: bool = False

    # G0: Legal & Swiss Ephemeris AGPL/Commercial licensing gate
    legal_gate_approved: bool = False
    legal_gate_reference: str = ""

    # G2: Advisor rule-library approval gate
    allow_draft_rules: bool = False
    rules_path: str = "rules/mvp_rules.yaml"
    i18n_dir: str = "i18n"
    tables_path: str = "rules/ashtakoota_tables.yaml"
    festivals_path: str = "data/festivals.yaml"

    # Optional LLM rephrasing (off by default; hard-capped for cost control)
    llm_rephrase_enabled: bool = False
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"
    llm_monthly_call_cap: int = 1000

    # Ask endpoint (routing over approved statements; off until the owner enables it)
    ask_enabled: bool = False
    ask_weekly_free_quota: int = 3
    ask_lexicon_path: str = "rules/ask_lexicon.yaml"

    # Geocoding
    geocode_provider: Literal["nominatim", "manual_only"] = "nominatim"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    geocode_user_agent: str = "astroplan-beta/3.6 (contact: set-in-env)"

    # G5, M2 & M3: Auth + Fernet field encryption + Signed Share Tokens + Operator Key
    # + DPDP Grievance Officer
    auth_mode: Literal["dev", "firebase"] = "dev"
    field_encryption_keys: str = ""  # comma-separated Fernet keys; first key encrypts
    share_token_secret: str = DEFAULT_DEV_SHARE_SECRET
    operator_api_key: str = "dev-operator-key"
    grievance_officer_name: str = "Meera Deshmukh"
    grievance_officer_email: str = "grievance@astroplan.in"
    grievance_response_sla_hours: int = 72

    @model_validator(mode="after")
    def _enforce_production_guardrails(self) -> Settings:
        if self.env != "production":
            return self
        problems: list[str] = []
        if not (self.legal_gate_approved and self.legal_gate_reference.strip()):
            problems.append("G0: legal_gate_approved and legal_gate_reference required")
        if not self.require_swiss_files:
            problems.append("G1: require_swiss_files must be true")
        if self.allow_draft_rules:
            problems.append("G2: allow_draft_rules must be false")
        if self.auth_mode != "firebase":
            problems.append("G5: auth_mode must be 'firebase'")
        if not self.field_encryption_keys.strip():
            problems.append("G5: field_encryption_keys required")
        if (
            self.share_token_secret == DEFAULT_DEV_SHARE_SECRET
            or len(self.share_token_secret.strip()) < 32
        ):
            problems.append("M3: share_token_secret must be changed and >= 32 chars in production")
        if self.operator_api_key == "dev-operator-key" or len(self.operator_api_key.strip()) < 16:
            problems.append("M2: operator_api_key must be changed in production")
        if not self.database_url.startswith("postgresql"):
            problems.append("G5: production database_url must be postgresql")
        if problems:
            raise ValueError("Production guardrail failure: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
