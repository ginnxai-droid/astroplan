"""Deterministic OpenAPI snapshot generator for Gap 24 contract freeze."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def generate_openapi_dict() -> dict[str, object]:
    s = Settings(
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        allow_draft_rules=True,
        geocode_provider="manual_only",
    )
    return create_app(s).openapi()


def main() -> int:
    out = ROOT / "openapi.json"
    out.write_text(
        json.dumps(generate_openapi_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
