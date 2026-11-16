from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.config import Settings


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--gates", action="store_true", help="run release gates G1/G2")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--gates"):
        return
    skip = pytest.mark.skip(reason="release gate: run with --gates")
    for item in items:
        if "release_gate_g1" in item.keywords or "release_gate_g2" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _crypto() -> None:
    try:
        from app.db import crypto
    except ImportError:
        return
    crypto.configure("", "test")


@pytest.fixture(scope="session")
def catalog():
    from app.interpretation.language import Catalog

    return Catalog("i18n")


@pytest.fixture(scope="session")
def rules():
    from app.interpretation.rules import load_rules

    return load_rules("rules/mvp_rules.yaml", allow_draft=True)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        allow_draft_rules=True,
        geocode_provider="manual_only",
    )


@pytest.fixture
def client(settings: Settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(settings)
    snap = Path("openapi.json")
    if not snap.exists():
        snap.write_text(
            json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return TestClient(app)


@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()
