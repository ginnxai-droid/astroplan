"""Astronomical Panchang-based Festival and Vrat computation engine + regional rules (Gap 2, M4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

from app.core.panchang import calculate_daily_panchang
from app.interpretation.errors import RuleSchemaError


@dataclass(frozen=True)
class Festival:
    name: str
    date: date
    tradition: str
    category: str
    tithi_rule: str
    status: str
    reviewer: str | None
    reviewed_at: str | None


def load_festivals(path: str | Path, *, allow_draft: bool) -> list[Festival]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    out: list[Festival] = []
    for entry in raw:
        f = Festival(
            name=entry["name"],
            date=date.fromisoformat(entry["date"]),
            tradition=entry.get("tradition", "smarta_maharashtra_north"),
            category=entry.get("category", "festival"),
            tithi_rule=entry.get("tithi_rule", "sunrise_tithi"),
            status=entry.get("status", "draft"),
            reviewer=entry.get("reviewer"),
            reviewed_at=entry.get("reviewed_at"),
        )
        if f.status == "draft" and not allow_draft:
            raise RuleSchemaError(f"G2: festival {f.name} draft in production")
        out.append(f)
    return out


def compute_panchang_vrats_for_range(
    start_date: date,
    days: int,
    lat: float,
    lon: float,
    tz_name: str,
) -> list[dict[str, str]]:
    """Computes location-accurate Ekadashi, Pradosh, Purnima, Amavasya, and Sankranti vrats."""
    events: list[dict[str, str]] = []
    prev_sun_sign: int | None = None
    for offset in range(days):
        cur = start_date + timedelta(days=offset)
        p = calculate_daily_panchang(cur, lat, lon, tz_name)
        t_idx = int(str(p["tithi_index"]))
        t_name = str(p["tithi"])
        sun_lon = float(str(p["sun_longitude"]))
        sun_sign = int(sun_lon / 30.0) + 1

        if t_idx in (11, 26):
            events.append(
                {
                    "name": f"{t_name} Ekadashi Vrat",
                    "date": cur.isoformat(),
                    "type": "vrat",
                    "tithi": t_name,
                }
            )
        elif t_idx in (13, 28):
            events.append(
                {
                    "name": f"{t_name} Pradosh Vrat",
                    "date": cur.isoformat(),
                    "type": "vrat",
                    "tithi": t_name,
                }
            )
        elif t_idx == 15:
            events.append(
                {"name": "Purnima", "date": cur.isoformat(), "type": "purnima", "tithi": t_name}
            )
        elif t_idx == 30:
            events.append(
                {"name": "Amavasya", "date": cur.isoformat(), "type": "amavasya", "tithi": t_name}
            )
        if prev_sun_sign is not None and sun_sign != prev_sun_sign:
            events.append(
                {
                    "name": "Makar Sankranti"
                    if sun_sign == 10
                    else f"Solar Sankranti (Sign {sun_sign})",
                    "date": cur.isoformat(),
                    "type": "sankranti",
                    "tithi": t_name,
                }
            )
        prev_sun_sign = sun_sign
    return events
