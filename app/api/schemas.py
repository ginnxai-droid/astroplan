from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

LanguageCode = Literal["en", "hi", "mr"]
StrengthGrade = Literal["likely", "supported", "weak", "contested"]
LifeAreaCategory = Literal["career", "relationships", "finances", "home"]
NodeType = Literal["MEAN", "TRUE"]
TelemetryEventType = Literal[
    "why_this_opened",
    "annual_forecast_opened",
    "annual_forecast_completed",
    "life_area_viewed",
    "daily_panchang_opened",
    "daily_insight_opened",
    "ask_answered",
    "ask_uncovered",
]


class BirthDetailsInput(BaseModel):
    name: str = "User"
    birth_date: date
    birth_time: time
    place_name: str = Field(..., min_length=2)
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    timezone_override: str | None = None
    uncertainty_minutes: int = Field(0, ge=0, le=120)
    node_type: NodeType = "MEAN"
    language: LanguageCode = "en"


class ConsentGrantRequest(BaseModel):
    user_id: str = Field(..., min_length=2)
    dpdp_consent_granted: bool = False
    age_verified_18_plus: bool = False
    parental_consent_verified: bool = False
    preferred_language: LanguageCode = "en"

    @model_validator(mode="after")
    def _validate_consent(self) -> ConsentGrantRequest:
        if not self.dpdp_consent_granted:
            raise ValueError("dpdp_consent_required")
        if not (self.age_verified_18_plus or self.parental_consent_verified):
            raise ValueError("age_gate_or_parental_consent_required")
        return self


class UserChartSaveRequest(BaseModel):
    user_id: str = Field(..., min_length=2)
    chart_id: str = Field(..., min_length=2)
    details: BirthDetailsInput
    dpdp_consent_granted: bool = False
    age_verified_18_plus: bool = False
    parental_consent_verified: bool = False
    is_third_party_chart: bool = False
    third_party_permission_confirmed: bool = False

    @model_validator(mode="after")
    def _verify_dpdp_and_age_gate(self) -> UserChartSaveRequest:
        if not self.dpdp_consent_granted:
            raise ValueError("dpdp_consent_required")
        if not (self.age_verified_18_plus or self.parental_consent_verified):
            raise ValueError("age_gate_or_parental_consent_required")
        if self.is_third_party_chart and not self.third_party_permission_confirmed:
            raise ValueError("third_party_permission_required")
        return self


class TelemetryEventInput(BaseModel):
    event_type: TelemetryEventType
    category: str | None = None
    rule_id: str | None = None
    language: LanguageCode = "en"
    cohort_hash: str | None = None


class PlanetPosition(BaseModel):
    planet: str
    longitude: float
    sign_index: int
    sign_name: str
    degree_in_sign: float
    house: int
    nakshatra_index: int
    nakshatra_name: str
    pada: int
    navamsa_sign_index: int
    navamsa_sign_name: str
    is_retrograde: bool


class WhyThisExplanation(BaseModel):
    rule_id: str
    placement_evidence: str
    classical_source: str
    tradition: str = "Parashari"
    strength_grade: StrengthGrade
    method_note: str = "Sidereal Lahiri, Whole-Sign Houses"


class ExplainedStatement(BaseModel):
    statement_id: str
    category: str
    time_window: str
    simple_text: str
    pro_text: str
    why_this: WhyThisExplanation
    safety_verified: bool  # Mandatory; no default


class ChartResponse(BaseModel):
    """Non-interpretive deterministic astronomical output (Steps 1-6)."""

    input_summary: BirthDetailsInput
    resolved_latitude: float
    resolved_longitude: float
    resolved_timezone: str
    utc_datetime: datetime
    ayanamsa_name: str
    ayanamsa_value: float
    lagna_sign_index: int
    lagna_sign_name: str
    lagna_degree: float
    navamsa_lagna_sign_index: int
    navamsa_lagna_sign_name: str
    moon_sign_index: int
    moon_sign_name: str
    moon_nakshatra: str
    moon_pada: int
    boundary_warning: str | None = None
    planets: list[PlanetPosition]
    disclaimer_key: str = "chart.disclaimer"
    disclaimer: str = ""


class AnnualForecastQuarter(BaseModel):
    quarter: str
    theme_statement: ExplainedStatement
    active_dasha: str
    key_transit_note: str


class AnnualForecastResponse(BaseModel):
    year: int
    delivery_format: Literal["IN_APP_INTERACTIVE"] = "IN_APP_INTERACTIVE"
    pdf_export_available: Literal[False] = False
    overview: ExplainedStatement
    quarters: list[AnnualForecastQuarter]
    life_area_highlights: dict[LifeAreaCategory, list[ExplainedStatement]]


class MatchingInput(BaseModel):
    profile_a: BirthDetailsInput
    profile_b: BirthDetailsInput
    partner_consent_confirmed: bool = False

    @model_validator(mode="after")
    def _require_partner_consent(self) -> MatchingInput:
        if not self.partner_consent_confirmed:
            raise ValueError("partner_consent_required")
        return self


class AskRequest(BaseModel):
    details: BirthDetailsInput
    question: str = Field(..., min_length=3, max_length=280)
    target_date: date | None = None


class AskCoverage(BaseModel):
    status: Literal["answered", "uncovered"]
    area: LifeAreaCategory | None
    matched_terms: list[str]
    available_areas: list[LifeAreaCategory]


class LLMProvenance(BaseModel):
    used: bool
    model: str | None = None
    fallback_reason: str | None = None


class AskResponse(BaseModel):
    request_id: str
    coverage: AskCoverage
    statement: ExplainedStatement | None
    context: list[ExplainedStatement] = Field(default_factory=list)
    ledger_entry_id: str | None = None
    llm: LLMProvenance
    disclaimer: str
