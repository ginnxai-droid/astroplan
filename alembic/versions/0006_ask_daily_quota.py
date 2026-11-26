"""Remember the day of the last answered Ask question."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ask_usage") as batch:
        batch.add_column(sa.Column("last_asked_on", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column("day_questions_used", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("ask_usage") as batch:
        batch.drop_column("day_questions_used")
        batch.drop_column("last_asked_on")
