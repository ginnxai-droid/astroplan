"""Add gender, marital_status, and occupation to users."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("gender", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("marital_status", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("occupation", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("occupation")
        batch.drop_column("marital_status")
        batch.drop_column("gender")
