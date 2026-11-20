from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
ENTRYPOINT = ROOT / "docker-entrypoint.sh"

EPHEMERIS = {
    "sepl_18.se1": "ca1393ceab3a44fbc895887cf789c68819ae6a1cbc9b22225872dbe4ccd99a66",
    "semo_18.se1": "1ca07bd67c24374d77226180c20a4f9996cba013697894810518e7eb582ca4f7",
    "seas_18.se1": "a2cd8fc33807c78ca9a700c91c2e042258b12fc4796519e00781440b5ad8b2e2",
}


def test_image_bakes_checksum_pinned_ephemeris_files() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "ASTRO_EPHE_PATH=/ephe" in text
    assert "sha256sum -c" in text, "ephemeris downloads must be checksum verified"
    for name, digest in EPHEMERIS.items():
        assert name in text, f"{name} must be baked into the image (ephemeral disks wipe it)"
        assert digest in text, f"{name} must be pinned to its known digest"


def test_entrypoint_migrates_before_serving() -> None:
    script = ENTRYPOINT.read_text(encoding="utf-8")
    assert script.startswith("#!/bin/sh")
    assert "set -eu" in script, "entrypoint must fail closed"
    migrate = script.index("alembic upgrade head")
    serve = script.index("exec uvicorn")
    assert migrate < serve, "migrations must run before the app starts"
    assert "${PORT:-8000}" in script, "container must honour the host-assigned port"


def test_dockerfile_runs_the_entrypoint() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "docker-entrypoint.sh" in text
    assert 'ENTRYPOINT ["/srv/docker-entrypoint.sh"]' in text
