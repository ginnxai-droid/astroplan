"""S20 static contract: the share page is server-fetched, token-protected and secret-free."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.s20

PAGE = Path("web-share/app/share/[token]/page.tsx")
PKG = Path("web-share/package.json")


def test_share_page_is_a_server_component_that_fetches_the_share_api() -> None:
    src = PAGE.read_text(encoding="utf-8")
    assert "export default async function" in src, "must remain a React server component"
    assert "/share/${encodeURIComponent(params.token)}" in src, (
        "must server-fetch GET /v1/share/{token} (Gap 20 / C6)"
    )
    assert 'cache: "no-store"' in src, "share responses must never be cached"


def test_share_page_embeds_no_secrets_and_no_client_side_token_logic() -> None:
    src = PAGE.read_text(encoding="utf-8")
    for banned in (
        "ASTRO_SHARE_TOKEN_SECRET",
        "ASTRO_OPERATOR_API_KEY",
        "X-Operator-Key",
        "field_encryption_keys",
        "atob(",
    ):
        assert banned not in src, f"forbidden material in share page: {banned}"


def test_share_page_conveys_the_agpl_source_offer() -> None:
    src = PAGE.read_text(encoding="utf-8")
    assert "AGPL-3.0" in src, "network use must convey the ephemeris license"
    assert "github.com/ginnxai-droid/astroplan" in src, "source offer must link to the code"


def test_web_share_package_pins_next_14() -> None:
    pkg = json.loads(PKG.read_text(encoding="utf-8"))
    assert pkg["dependencies"]["next"].startswith("14.2.")
    assert "react" in pkg["dependencies"] and "react-dom" in pkg["dependencies"]
