from __future__ import annotations

import os

from sqlalchemy import create_engine

from alembic import context
from app.db.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = os.environ.get("ASTRO_DATABASE_URL", "sqlite+pysqlite:///./astroplan_dev.db")
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
