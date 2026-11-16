"""Run validation for one build step and record the result in validation/step_log.jsonl."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "validation" / "step_log.jsonl"
PY = sys.executable

BACKEND_STEPS = [f"S{n:02d}" for n in range(0, 18)]
MOBILE_STEPS = {
    "S18": [
        ("flutter analyze", ["flutter", "analyze"], "mobile"),
        ("flutter test", ["flutter", "test"], "mobile"),
        ("guardrail scan", [PY, "scripts/check_guardrails.py"], "."),
    ],
    "S19": [
        ("flutter analyze", ["flutter", "analyze"], "mobile"),
        ("flutter test", ["flutter", "test"], "mobile"),
        ("flutter integration", ["flutter", "test", "integration_test"], "mobile"),
    ],
}
EXTRA_STEP_CHECKS: dict[str, list[tuple[str, list[str]]]] = {
    "S20": [
        ("pytest -m s20", [PY, "-m", "pytest", "-m", "s20"]),
        ("guardrail scan", [PY, "scripts/check_guardrails.py"]),
        ("ruff lint", [PY, "-m", "ruff", "check", "app", "scripts", "tests"]),
        ("ruff format", [PY, "-m", "ruff", "format", "--check", "app", "scripts", "tests"]),
        ("mypy strict", [PY, "-m", "mypy", "app"]),
    ],
}
GATES = {
    "G1": [("reference charts", [PY, "-m", "pytest", "--gates", "-m", "release_gate_g1"])],
    "G2": [("advisor sign-off", [PY, "-m", "pytest", "--gates", "-m", "release_gate_g2"])],
}


def _static(step: str) -> list[tuple[str, list[str]]]:
    paths = [p for p in ("app", "scripts", "tests") if (ROOT / p).exists()]
    checks = [
        ("ruff lint", [PY, "-m", "ruff", "check", *paths]),
        ("ruff format", [PY, "-m", "ruff", "format", "--check", *paths]),
        ("mypy strict", [PY, "-m", "mypy", "app"]),
    ]
    if step != "S00":
        checks.append(("guardrail scan", [PY, "scripts/check_guardrails.py"]))
    return checks


def _run(
    label: str, cmd: list[str], cwd: str = ".", env: dict[str, str] | None = None
) -> dict[str, object]:
    if shutil.which(cmd[0]) is None and cmd[0] != PY:
        return {"check": label, "status": "FAIL", "detail": f"tool not found: {cmd[0]}"}
    proc = subprocess.run(
        cmd,
        cwd=ROOT / cwd,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )
    status = "PASS" if proc.returncode == 0 else "FAIL"
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-8:]
    return {"check": label, "status": status, "detail": "\n".join(tail) if status == "FAIL" else ""}


def validate(step: str) -> bool:
    results: list[dict[str, object]] = []
    if step in MOBILE_STEPS:
        for label, cmd, cwd in MOBILE_STEPS[step]:
            results.append(_run(label, cmd, cwd))
    elif step in BACKEND_STEPS:
        results.append(_run(f"pytest -m {step.lower()}", [PY, "-m", "pytest", "-m", step.lower()]))
        for label, cmd in _static(step):
            results.append(_run(label, cmd))
        if step == "S15" and (ROOT / "alembic.ini").exists():
            db = f"sqlite+pysqlite:///{tempfile.mkdtemp()}/migration_check.db"
            env = {"ASTRO_DATABASE_URL": db}
            results.append(
                _run("alembic upgrade head", [PY, "-m", "alembic", "upgrade", "head"], env=env)
            )
    elif step in EXTRA_STEP_CHECKS:
        for label, cmd in EXTRA_STEP_CHECKS[step]:
            results.append(_run(label, cmd))
    elif step in GATES:
        for label, cmd in GATES[step]:
            results.append(_run(label, cmd))
    else:
        print(f"unknown step {step}")
        return False

    ok = all(r["status"] == "PASS" for r in results)
    for r in results:
        print(f"  {r['status']}  {r['check']}")
        if r["detail"]:
            print("      " + str(r["detail"]).replace("\n", "\n      "))
    print(f"{step}: {'PASS - step may be marked complete' if ok else 'FAIL - do not proceed'}")
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {"step": step, "at": datetime.now(UTC).isoformat(), "ok": ok, "results": results}
            )
            + "\n"
        )
    return ok


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--all":
        return 0 if all([validate(s) for s in [*BACKEND_STEPS, *EXTRA_STEP_CHECKS]]) else 1
    if argv[0] == "--gate":
        return 0 if validate(argv[1]) else 1
    return 0 if validate(argv[0].upper()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
