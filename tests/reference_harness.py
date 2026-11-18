"""Reference chart verification harness for Release Gate G1 (Gaps 6, 7, 8)."""

from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path
from typing import Any

from app.api.schemas import BirthDetailsInput
from app.core.chart import calculate_chart

REFERENCE_SOFTWARE_STANDARD = (
    "Swiss Ephemeris swetest v2.10.03 / Jagannatha Hora v8.0 "
    "(SE_SIDM_LAHIRI, Whole-Sign Houses, Geocentric)"
)
PLANET_LON_TOL_DEG: float = 0.01
LAGNA_LON_TOL_DEG: float = 0.05
AYANAMSA_TOL_DEG: float = 0.005


def load_reference_fixture(
    path: str | Path = "tests/fixtures/reference_charts.json",
) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_reference_entry(entry: dict[str, Any]) -> list[str]:
    b = entry["birth"]
    exp = entry["expected"]
    inp = BirthDetailsInput(
        name="Reference",
        birth_date=date.fromisoformat(b["date"]),
        birth_time=time.fromisoformat(b["time"]),
        place_name=b["place"],
        country=b["country"],
        latitude=float(b["lat"]),
        longitude=float(b["lon"]),
        node_type=b.get("node_type", "MEAN"),
    )
    chart = calculate_chart(inp, float(b["lat"]), float(b["lon"]), b["tz"])
    errors: list[str] = []
    if chart.lagna_sign_name != exp["lagna_sign"]:
        errors.append(f"Lagna mismatch: got {chart.lagna_sign_name}, expected {exp['lagna_sign']}")
    if (
        "lagna_degree" in exp
        and abs(chart.lagna_degree - float(exp["lagna_degree"])) > LAGNA_LON_TOL_DEG
    ):
        errors.append(
            f"Lagna degree diff {abs(chart.lagna_degree - float(exp['lagna_degree'])):.4f} "
            f"> {LAGNA_LON_TOL_DEG}"
        )
    if (
        "ayanamsa_value" in exp
        and abs(chart.ayanamsa_value - float(exp["ayanamsa_value"])) > AYANAMSA_TOL_DEG
    ):
        errors.append(
            f"Ayanamsa diff {abs(chart.ayanamsa_value - float(exp['ayanamsa_value'])):.4f} "
            f"> {AYANAMSA_TOL_DEG}"
        )
    if "moon_nakshatra" in exp and chart.moon_nakshatra != exp["moon_nakshatra"]:
        errors.append(f"Moon Nakshatra mismatch: {chart.moon_nakshatra} != {exp['moon_nakshatra']}")
    if "moon_pada" in exp and chart.moon_pada != int(exp["moon_pada"]):
        errors.append(f"Moon Pada mismatch: {chart.moon_pada} != {exp['moon_pada']}")
    for p_name, exp_lon in exp.get("planet_longitudes", {}).items():
        actual = next(p.longitude for p in chart.planets if p.planet == p_name)
        diff = min((actual - float(exp_lon)) % 360.0, (float(exp_lon) - actual) % 360.0)
        if diff > PLANET_LON_TOL_DEG:
            errors.append(f"{p_name} lon diff {diff:.4f} > {PLANET_LON_TOL_DEG} deg")
    return errors
