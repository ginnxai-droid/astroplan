from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    dpdp_consent_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    age_verified_18_plus: Mapped[bool] = mapped_column(Boolean, default=False)
    parental_consent_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    dpdp_consent_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    notification_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    notifications_muted: Mapped[bool] = mapped_column(Boolean, default=False)


class BirthChartRow(Base):
    __tablename__ = "birth_charts"

    chart_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE")
    )
    birth_date: Mapped[date] = mapped_column(Date)
    birth_time: Mapped[time] = mapped_column(Time)
    name_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    place_name_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    country_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    latitude_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    longitude_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    timezone_iana: Mapped[str] = mapped_column(String(64))
    uncertainty_minutes: Mapped[int] = mapped_column(Integer, default=0)
    node_type: Mapped[str] = mapped_column(String(8), default="MEAN")
    ayanamsa_mode: Mapped[str] = mapped_column(String(16), default="LAHIRI")
    third_party_permission_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class LedgerEntryRow(Base):
    __tablename__ = "prediction_ledger_entries"

    entry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    statement_id: Mapped[str] = mapped_column(String(128))
    rule_id: Mapped[str] = mapped_column(String(64))
    statement_text: Mapped[str] = mapped_column(Text)
    confidence_grade: Mapped[str] = mapped_column(String(16))
    assigned_probability: Mapped[float] = mapped_column(Numeric(4, 2))
    time_window: Mapped[str] = mapped_column(String(64))
    observable_outcome_criteria: Mapped[str] = mapped_column(Text)
    safety_category: Mapped[str] = mapped_column(String(32), default="general")
    registered_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    user_outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    outcome_logged_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AskUsageRow(Base):
    __tablename__ = "ask_usage"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    week_start_utc: Mapped[date] = mapped_column(Date, primary_key=True)
    questions_used: Mapped[int] = mapped_column(Integer, default=0)


class TelemetryEventRow(Base):
    __tablename__ = "telemetry_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="en")
    cohort_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recorded_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RevokedShareTokenRow(Base):
    __tablename__ = "revoked_share_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    revoked_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class LLMAuditRow(Base):
    __tablename__ = "llm_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    lang: Mapped[str] = mapped_column(String(5), default="en")
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    output_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bundle_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question_area: Mapped[str | None] = mapped_column(String(32), nullable=True)
