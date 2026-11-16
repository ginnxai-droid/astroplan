"""Static scanner. Checks printed as PASS/FAIL. Exit code 1 on any failure."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.interpretation.guardrails import verify_text  # noqa: E402

FORBIDDEN_MODULES = ["free_form_chat", "rectification", "pdf_export"]
FORBIDDEN_PERMISSIONS = ["READ_CONTACTS", "WRITE_CONTACTS"]
WEBSHARE_REQUIRED_TOKENS = (
    "ASTRO_API_URL",
    "/share/${encodeURIComponent(params.token)}",
    'cache: "no-store"',
)
WEBSHARE_FORBIDDEN_TOKENS = (
    "ASTRO_SHARE_TOKEN_SECRET",
    "field_encryption_keys",
    "X-Operator-Key",
)


def _g3_static() -> list[str]:
    problems: list[str] = []
    for path in (ROOT / "app").rglob("*.py"):
        if path.name == "guardrails.py":
            continue
        text = path.read_text(encoding="utf-8")
        for literal in re.findall(r'"([^"\n]{12,})"', text):
            try:
                verify_text(literal)
            except Exception as exc:
                problems.append(f"G3-static: {path.relative_to(ROOT)}: {exc}")
    return problems


def _g5_logging() -> list[str]:
    problems: list[str] = []
    for path in (ROOT / "app" / "api").rglob("*.py"):
        if re.search(
            r"logger\.(info|debug|warning)\([^)]*request\.json",
            path.read_text(encoding="utf-8"),
        ):
            problems.append(f"G5-logging: {path.relative_to(ROOT)} logs request body")
    return problems


def _g5_contacts() -> list[str]:
    manifest = ROOT / "mobile" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    if not manifest.exists():
        return []
    text = manifest.read_text(encoding="utf-8")
    return [f"G5-contacts: {p} present" for p in FORBIDDEN_PERMISSIONS if p in text]


def _g5_webshare() -> list[str]:
    page = ROOT / "web-share" / "app" / "share" / "[token]" / "page.tsx"
    if not page.exists():
        return ["G5-webshare: web-share/app/share/[token]/page.tsx is missing"]
    text = page.read_text(encoding="utf-8")
    problems: list[str] = []
    for required in WEBSHARE_REQUIRED_TOKENS:
        if required not in text:
            problems.append(f"G5-webshare: share page lost a server-fetch guard: {required}")
    for forbidden in WEBSHARE_FORBIDDEN_TOKENS:
        if forbidden in text:
            problems.append(f"G5-webshare: secret material in share page: {forbidden}")
    return problems


def _g6_i18n() -> list[str]:
    problems: list[str] = []
    keys: dict[str, set[str]] = {}
    for lang in ("en", "hi", "mr"):
        path = ROOT / "i18n" / f"{lang}.json"
        if not path.exists():
            problems.append(f"G6-i18n: missing {path.relative_to(ROOT)}")
            continue
        keys[lang] = set(json.loads(path.read_text(encoding="utf-8")).keys())
    if len(keys) == 3:
        for lang in ("hi", "mr"):
            missing = keys["en"] - keys[lang]
            extra = keys[lang] - keys["en"]
            if missing:
                problems.append(f"G6-i18n: {lang} missing {sorted(missing)[:5]}")
            if extra:
                problems.append(f"G6-i18n: {lang} extra {sorted(extra)[:5]}")
    return problems


def _g6_hardcoded() -> list[str]:
    problems: list[str] = []
    for path in (ROOT / "app").rglob("*.py"):
        for literal in re.findall(r'"([A-Z][a-z][^"\n]{25,})"', path.read_text(encoding="utf-8")):
            if any(w in literal.lower() for w in ("the ", "your ", "you ")):
                problems.append(f"G6-hardcoded: {path.relative_to(ROOT)}: {literal[:60]!r}")
    return problems


def _g7_scope() -> list[str]:
    return [
        f"G7-scope: forbidden module pattern {n}"
        for n in FORBIDDEN_MODULES
        if any((ROOT / "app").rglob(f"*{n}*"))
    ]


def main() -> int:
    failed = False
    for label, fn in [
        ("G3-static", _g3_static),
        ("G5-logging", _g5_logging),
        ("G5-contacts", _g5_contacts),
        ("G5-webshare", _g5_webshare),
        ("G6-i18n", _g6_i18n),
        ("G6-hardcoded", _g6_hardcoded),
        ("G7-scope", _g7_scope),
    ]:
        problems = fn()
        if problems:
            failed = True
            print(f"  FAIL  {label}")
            for p in problems[:10]:
                print(f"        {p}")
        else:
            print(f"  PASS  {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
