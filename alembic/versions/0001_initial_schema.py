"""Initial DPDP schema: encrypted name, opt-in consent defaults, cohort_hash,
revoked_share_tokens, and llm_audit_events."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("preferred_language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("dpdp_consent_granted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("age_verified_18_plus", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "parental_consent_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("dpdp_consent_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notification_time", sa.Time(), nullable=True),
        sa.Column("notifications_muted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "birth_charts",
        sa.Column("chart_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.user_id", ondelete="CASCADE")),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("birth_time", sa.Time(), nullable=False),
        sa.Column("name_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("place_name_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("latitude_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("longitude_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("timezone_iana", sa.String(64), nullable=False),
        sa.Column("uncertainty_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("node_type", sa.String(8), nullable=False, server_default="MEAN"),
        sa.Column("ayanamsa_mode", sa.String(16), nullable=False, server_default="LAHIRI"),
        sa.Column(
            "third_party_permission_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        "prediction_ledger_entries",
        sa.Column("entry_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("statement_id", sa.String(128), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("statement_text", sa.Text(), nullable=False),
        sa.Column("confidence_grade", sa.String(16), nullable=False),
        sa.Column("assigned_probability", sa.Numeric(4, 2), nullable=False),
        sa.Column("time_window", sa.String(64), nullable=False),
        sa.Column("observable_outcome_criteria", sa.Text(), nullable=False),
        sa.Column("safety_category", sa.String(32), nullable=False, server_default="general"),
        sa.Column("registered_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_outcome", sa.String(16), nullable=True),
        sa.Column("outcome_logged_at_utc", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("rule_id", sa.String(64), nullable=True),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("cohort_hash", sa.String(64), nullable=True),
        sa.Column("recorded_at_utc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "revoked_share_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("revoked_at_utc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "llm_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lang", sa.String(5), nullable=False, server_default="en"),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("prompt_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("output_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("llm_audit_events")
    op.drop_table("revoked_share_tokens")
    op.drop_table("telemetry_events")
    op.drop_table("prediction_ledger_entries")
    op.drop_table("birth_charts")
    op.drop_table("users")
