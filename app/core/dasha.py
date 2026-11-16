from __future__ import annotations

from datetime import date, timedelta
from typing import TypedDict

from app.core.constants import DAYS_PER_YEAR, TOTAL_VIMSHOTTARI_YEARS, VIMSHOTTARI_SEQUENCE


class _MD(TypedDict):
    mahadasha_lord: str
    start_date: str
    end_date: str
    full_years: int
    seq_idx: int


class _AD(TypedDict):
    antardasha_lord: str
    start_date: str
    end_date: str
    ad_seq_idx: int
    sub_days: int
    raw_start: date


def _seq(moon_lon: float) -> tuple[int, float]:
    span = 360.0 / 27.0
    lon = moon_lon % 360.0
    idx = int(lon / span)
    return idx % 9, 1.0 - ((lon - idx * span) / span)


def calculate_vimshottari_dasha(
    birth_date: date, moon_lon: float, target_date: date
) -> dict[str, object]:
    start, remaining = _seq(moon_lon)
    mds: list[_MD] = []
    cursor = birth_date
    for offset in range(9):
        seq_idx = (start + offset) % 9
        lord, years = VIMSHOTTARI_SEQUENCE[seq_idx]
        run = years * remaining if offset == 0 else float(years)
        end = cursor + timedelta(days=round(run * DAYS_PER_YEAR))
        mds.append(
            {
                "mahadasha_lord": lord,
                "start_date": cursor.isoformat(),
                "end_date": end.isoformat(),
                "full_years": years,
                "seq_idx": seq_idx,
            }
        )
        cursor = end

    active_md = next(
        (
            m
            for m in mds
            if date.fromisoformat(m["start_date"])
            <= target_date
            <= date.fromisoformat(m["end_date"])
        ),
        mds[0],
    )
    md_years = active_md["full_years"]
    md_start = date.fromisoformat(active_md["end_date"]) - timedelta(
        days=round(md_years * DAYS_PER_YEAR)
    )

    ad_cursor = md_start
    active_ad: _AD | None = None
    for off in range(9):
        ad_idx = (active_md["seq_idx"] + off) % 9
        ad_lord, ad_years = VIMSHOTTARI_SEQUENCE[ad_idx]
        sub_days = round(md_years * ad_years / TOTAL_VIMSHOTTARI_YEARS * DAYS_PER_YEAR)
        ad_end = ad_cursor + timedelta(days=sub_days)
        entry: _AD = {
            "antardasha_lord": ad_lord,
            "start_date": max(ad_cursor, birth_date).isoformat(),
            "end_date": ad_end.isoformat(),
            "ad_seq_idx": ad_idx,
            "sub_days": sub_days,
            "raw_start": ad_cursor,
        }
        if active_ad is None and ad_cursor <= target_date <= ad_end:
            active_ad = entry
        ad_cursor = ad_end
    if active_ad is None:
        active_ad = entry

    pd_cursor = active_ad["raw_start"]
    active_pd = active_ad["antardasha_lord"]
    for off in range(9):
        pd_idx = (active_ad["ad_seq_idx"] + off) % 9
        pd_lord, pd_years = VIMSHOTTARI_SEQUENCE[pd_idx]
        pd_days = max(round(active_ad["sub_days"] * pd_years / TOTAL_VIMSHOTTARI_YEARS), 1)
        pd_end = pd_cursor + timedelta(days=pd_days)
        if pd_cursor <= target_date <= pd_end:
            active_pd = pd_lord
            break
        pd_cursor = pd_end

    return {
        "active_mahadasha": active_md["mahadasha_lord"],
        "active_antardasha": active_ad["antardasha_lord"],
        "active_pratyantardasha": active_pd,
        "mahadasha_end_date": active_md["end_date"],
        "antardasha_end_date": active_ad["end_date"],
        "timeline": [
            {
                "mahadasha_lord": m["mahadasha_lord"],
                "start_date": m["start_date"],
                "end_date": m["end_date"],
            }
            for m in mds
        ],
    }
