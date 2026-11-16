"""Backend daily notification dispatcher with configurable time-window matching (Gap 21)."""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import BirthChartRow, UserRow


def _minutes_since_midnight(t: time) -> int:
    return t.hour * 60 + t.minute


def collect_due_notification_users(
    sf: sessionmaker[Session],
    target_time: time,
    target_date: date,
    window_minutes: int = 15,
) -> list[dict[str, str]]:
    target_min = _minutes_since_midnight(target_time)
    with sf() as s:
        users = s.scalars(
            select(UserRow).where(
                UserRow.notifications_muted.is_(False),
                UserRow.dpdp_consent_granted.is_(True),
                UserRow.notification_time.is_not(None),
            )
        ).all()
        dispatched: list[dict[str, str]] = []
        for u in users:
            assert u.notification_time is not None
            diff = abs(_minutes_since_midnight(u.notification_time) - target_min)
            if min(diff, 1440 - diff) > window_minutes:
                continue
            chart = s.scalar(select(BirthChartRow).where(BirthChartRow.user_id == u.user_id))
            if chart is not None:
                dispatched.append(
                    {
                        "user_id": u.user_id,
                        "chart_id": chart.chart_id,
                        "language": u.preferred_language,
                        "target_date": target_date.isoformat(),
                    }
                )
        return dispatched
