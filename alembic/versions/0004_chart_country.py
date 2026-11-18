"""Add encrypted country to saved birth charts."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("birth_charts") as batch:
        batch.add_column(sa.Column("country_encrypted", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("birth_charts") as batch:
        batch.drop_column("country_encrypted")
