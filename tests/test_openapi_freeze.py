"""Gap 24: committed OpenAPI snapshot freeze.

`openapi.json` is generated via `make openapi` (`python scripts/generate_openapi.py`)
and committed to the repository. This test (marker s17, so it runs inside
`validate_step.py S17` and `--all`) fails whenever the live schema drifts
from the committed snapshot, so breaking API changes can never land silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.s17

SNAPSHOT = Path("openapi.json")


def _flat_paths(schema: dict[str, object]) -> set[str]:
    paths = schema.get("paths", {})
    assert isinstance(paths, dict)
    return {
        f"{method.upper()} {path}"
        for path, ops in paths.items()
        if isinstance(ops, dict)
        for method in ops
    }


def test_openapi_schema_matches_committed_snapshot(client) -> None:
    assert SNAPSHOT.exists(), (
        "openapi.json snapshot is missing - run `make openapi` and commit the file"
    )
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    live = client.app.openapi()
    if live != committed:
        drifted = sorted(_flat_paths(live) ^ _flat_paths(committed))
        hint = ", ".join(drifted[:10]) if drifted else "component schemas changed"
        raise AssertionError(
            f"OpenAPI schema drift detected ({hint}). If the change is "
            "intentional, regenerate the snapshot with `make openapi` and "
            "commit it in the same change."
        )
