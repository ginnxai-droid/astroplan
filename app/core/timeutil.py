from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.errors import UnknownTimezoneError


def load_zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise UnknownTimezoneError(tz_name) from exc


def local_to_utc(birth_date: date, birth_time: time, tz_name: str) -> datetime:
    zone = load_zone(tz_name)
    return datetime.combine(birth_date, birth_time, tzinfo=zone).astimezone(UTC)


def jd_ut_to_local_datetime(jd_ut: float, tz_name: str) -> datetime:
    import swisseph as swe

    y, m, d, h = swe.revjul(jd_ut)
    utc = datetime(y, m, d, tzinfo=UTC) + timedelta(hours=h)
    return utc.astimezone(load_zone(tz_name))
