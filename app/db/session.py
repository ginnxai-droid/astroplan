"""SQLAlchemy engine and sessionmaker factory (Gap 22 / Gap 25).

Reconciles create_all with Alembic: in-memory/dev SQLite auto-creates tables for fast unit
tests, while PostgreSQL staging/production relies strictly on `alembic upgrade head` unless
auto_create_tables=True.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base


def make_engine_and_session(
    database_url: str, *, auto_create_tables: bool | None = None
) -> tuple[Engine, sessionmaker[Session]]:
    if database_url.endswith(":memory:"):
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        should_create = True if auto_create_tables is None else auto_create_tables
    else:
        engine = create_engine(database_url)
        should_create = (
            database_url.startswith("sqlite") if auto_create_tables is None else auto_create_tables
        )
    if should_create:
        Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)
