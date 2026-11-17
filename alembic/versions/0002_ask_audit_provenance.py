"""Add LLM provenance columns used by the Ask endpoint."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_audit_events", sa.Column("prompt_version", sa.String(32), nullable=True))
    op.add_column("llm_audit_events", sa.Column("model", sa.String(64), nullable=True))
    op.add_column("llm_audit_events", sa.Column("bundle_hash", sa.String(64), nullable=True))
    op.add_column("llm_audit_events", sa.Column("question_area", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_audit_events", "question_area")
    op.drop_column("llm_audit_events", "bundle_hash")
    op.drop_column("llm_audit_events", "model")
    op.drop_column("llm_audit_events", "prompt_version")
