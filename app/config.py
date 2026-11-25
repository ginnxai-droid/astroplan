"""Application settings. Production guardrails (G0, G1, G2, G5, M2, M3) enforced here in code."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_SHARE_SECRET = "dev-share-secret-change-in-production"
# OpenRouter chat models. Paid ids go first so a question can be followed;
# the free ids stay as fallback. :free only where that catalog entry exists.
# Replace a retired id with ASTRO_OPENROUTER_MODELS.
DEFAULT_OPENROUTER_MODELS = ",".join(
    (
        "google/gemini-4-hydrogen",
        "openai/gpt-6.2-sol",
        "anthropic/claude-sonnet-5.5",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "google/gemma-4-31b-it:free",
        "openai/gpt-oss-120b:free",
    )
)


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
    # AGPL-3.0 network-use obligation: where users can obtain the corresponding source.
    source_offer_url: str = ""

    # G2: Advisor rule-library approval gate
    allow_draft_rules: bool = False
    rules_path: str = "rules/mvp_rules.yaml"
    i18n_dir: str = "i18n"
    tables_path: str = "rules/ashtakoota_tables.yaml"
    festivals_path: str = "data/festivals.yaml"

    # Optional LLM rephrasing (off by default; hard-capped for cost control)
    llm_rephrase_enabled: bool = False
    # Plain-language reading of structured facts. ASTRO_LLM_ENABLED=true.
    # ASTRO_LLM_PROVIDERS locks the order when set. Otherwise an OpenRouter key
    # tries ASTRO_OPENROUTER_MODELS first, then Gemini, Gemma, and Anthropic.
    llm_enabled: bool = False
    llm_providers: str = "gemini,gemma,anthropic"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemma_model: str = "gemma-4-31b-it"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"
    anthropic_base_url: str = "https://api.anthropic.com"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_api_key: SecretStr | None = None
    # Used only when ASTRO_OPENROUTER_MODELS is empty.
    openrouter_model: str = "google/gemma-3-27b-it:free"
    openrouter_models: str = DEFAULT_OPENROUTER_MODELS
    llm_monthly_call_cap: int = 1000

    # Ask endpoint (routing over approved statements; off until the owner enables it)
    ask_enabled: bool = False
    ask_weekly_free_quota: int = 3
    ask_lexicon_path: str = "rules/ask_lexicon.yaml"

    # Geocoding
    geocode_provider: Literal["nominatim", "manual_only"] = "nominatim"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    geocode_user_agent: str = "astroplan-beta/3.6 (contact: set-in-env)"
    places_db: str = ""

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
        source_offer = self.source_offer_url.strip()
        if not source_offer.startswith("https://") or source_offer == "https://":
            problems.append("G0: source_offer_url must be an https source offer")
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
