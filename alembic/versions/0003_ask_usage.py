"""Add the per-user weekly Ask quota table."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ask_usage",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("week_start_utc", sa.Date(), primary_key=True),
        sa.Column("questions_used", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("ask_usage")
