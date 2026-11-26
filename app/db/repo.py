from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.crypto import decrypt_str, encrypt_str
from app.db.models import (
    AskUsageRow,
    BirthChartRow,
    LedgerEntryRow,
    TelemetryEventRow,
    UserRow,
)
from app.db.session import make_engine_and_session

# Free tier stays 7/week and 1/day after monetization.
# A future paid plan may raise these two numbers.
FREE_ASK_WEEKLY_QUOTA = 7
FREE_ASK_DAILY_QUOTA = 1


class AskQuotaStatus(StrEnum):
    ALLOWED = "allowed"
    DAILY_EXHAUSTED = "ask_daily_quota_exhausted"
    WEEKLY_EXHAUSTED = "ask_quota_exhausted"


class PrivacyRepo:
    def __init__(self, database_url: str) -> None:
        self._engine, self._session_factory = make_engine_and_session(database_url)

    @property
    def session_factory(self) -> sessionmaker[Session]:
        return self._session_factory

    def record_consent(
        self,
        *,
        user_id: str,
        dpdp_consent_granted: bool,
        age_verified_18_plus: bool,
        parental_consent_verified: bool,
        preferred_language: str = "en",
    ) -> dict[str, object]:
        if not dpdp_consent_granted:
            raise ValueError("dpdp_consent_required")
        if not (age_verified_18_plus or parental_consent_verified):
            raise ValueError("age_gate_or_parental_consent_required")
        now = datetime.now(UTC)
        with self._session_factory() as s, s.begin():
            existing = s.scalar(select(UserRow).where(UserRow.user_id == user_id))
            if existing is None:
                s.add(
                    UserRow(
                        user_id=user_id,
                        preferred_language=preferred_language,
                        dpdp_consent_granted=True,
                        age_verified_18_plus=age_verified_18_plus,
                        parental_consent_verified=parental_consent_verified,
                        dpdp_consent_timestamp=now,
                    )
                )
            else:
                existing.preferred_language = preferred_language
                existing.dpdp_consent_granted = True
                existing.age_verified_18_plus = age_verified_18_plus
                existing.parental_consent_verified = parental_consent_verified
                existing.dpdp_consent_timestamp = now
        return {
            "user_id": user_id,
            "dpdp_consent_granted": True,
            "timestamp_utc": now.isoformat(),
        }

    def update_notification_preferences(
        self,
        *,
        user_id: str,
        notifications_muted: bool,
        notification_time: time | None = None,
    ) -> dict[str, object]:
        with self._session_factory() as s, s.begin():
            user = s.scalar(select(UserRow).where(UserRow.user_id == user_id))
            if user is None:
                raise KeyError(user_id)
            user.notifications_muted = notifications_muted
            if notification_time is not None:
                user.notification_time = notification_time
        return {
            "user_id": user_id,
            "notifications_muted": notifications_muted,
            "notification_time": notification_time.isoformat() if notification_time else None,
        }

    def create_user_and_chart(
        self,
        *,
        user_id: str,
        chart_id: str,
        name: str,
        birth_date: date,
        birth_time: time,
        place_name: str,
        country: str,
        lat: float,
        lon: float,
        tz_iana: str,
        dpdp_consent_granted: bool = False,
        age_verified_18_plus: bool = False,
        parental_consent_verified: bool = False,
        is_third_party_chart: bool = False,
        third_party_permission_confirmed: bool = False,
        notification_time: time | None = None,
        uncertainty_minutes: int = 0,
        node_type: str = "MEAN",
        preferred_language: str = "en",
        already_married: bool = False,
        gender: str | None = None,
        marital_status: str | None = None,
        occupation: str | None = None,
    ) -> None:
        if not dpdp_consent_granted:
            raise ValueError("dpdp_consent_required")
        if not (age_verified_18_plus or parental_consent_verified):
            raise ValueError("age_gate_or_parental_consent_required")
        if is_third_party_chart and not third_party_permission_confirmed:
            raise ValueError("third_party_permission_required")
        with self._session_factory() as s, s.begin():
            existing = s.scalar(select(UserRow).where(UserRow.user_id == user_id))
            if existing is None:
                s.add(
                    UserRow(
                        user_id=user_id,
                        preferred_language=preferred_language,
                        dpdp_consent_granted=dpdp_consent_granted,
                        age_verified_18_plus=age_verified_18_plus,
                        parental_consent_verified=parental_consent_verified,
                        notification_time=notification_time,
                        gender=gender,
                        marital_status=marital_status,
                        occupation=occupation,
                    )
                )
            else:
                existing.preferred_language = preferred_language
                existing.dpdp_consent_granted = dpdp_consent_granted
                existing.age_verified_18_plus = age_verified_18_plus
                existing.parental_consent_verified = parental_consent_verified
                if gender is not None:
                    existing.gender = gender
                if marital_status is not None:
                    existing.marital_status = marital_status
                if occupation is not None:
                    existing.occupation = occupation
            s.merge(
                BirthChartRow(
                    chart_id=chart_id,
                    user_id=user_id,
                    birth_date=birth_date,
                    birth_time=birth_time,
                    name_encrypted=encrypt_str(name),
                    place_name_encrypted=encrypt_str(place_name),
                    country_encrypted=encrypt_str(country),
                    latitude_encrypted=encrypt_str(str(lat)),
                    longitude_encrypted=encrypt_str(str(lon)),
                    timezone_iana=tz_iana,
                    uncertainty_minutes=uncertainty_minutes,
                    node_type=node_type,
                    ayanamsa_mode="MARRIED" if already_married else "LAHIRI",
                    third_party_permission_confirmed=third_party_permission_confirmed,
                )
            )

    def _decrypt_chart_row(self, c: BirthChartRow, lang: str = "en") -> dict[str, object]:
        return {
            "chart_id": c.chart_id,
            "name": decrypt_str(c.name_encrypted),
            "birth_date": c.birth_date.isoformat(),
            "birth_time": c.birth_time.strftime("%H:%M:%S"),
            "place_name": decrypt_str(c.place_name_encrypted),
            "country": decrypt_str(c.country_encrypted) if c.country_encrypted else "India",
            "latitude": float(decrypt_str(c.latitude_encrypted)),
            "longitude": float(decrypt_str(c.longitude_encrypted)),
            "timezone_override": c.timezone_iana,
            "uncertainty_minutes": c.uncertainty_minutes,
            "node_type": c.node_type,
            "language": lang,
            "already_married": c.ayanamsa_mode == "MARRIED",
            "third_party_permission_confirmed": c.third_party_permission_confirmed,
        }

    def get_user_profile(self, user_id: str) -> dict[str, object]:
        with self._session_factory() as s:
            user = s.scalar(select(UserRow).where(UserRow.user_id == user_id))
            if user is None:
                return {"saved": False, "user_id": user_id}
            charts = s.scalars(select(BirthChartRow).where(BirthChartRow.user_id == user_id)).all()
            if not charts:
                return {
                    "saved": False,
                    "user_id": user_id,
                    "preferred_language": user.preferred_language,
                    "dpdp_consent_granted": user.dpdp_consent_granted,
                    "age_verified_18_plus": user.age_verified_18_plus,
                    "parental_consent_verified": user.parental_consent_verified,
                    "gender": user.gender,
                    "marital_status": user.marital_status,
                    "occupation": user.occupation,
                }
            self_row: BirthChartRow | None = None
            partner_row: BirthChartRow | None = None
            for row in charts:
                if row.chart_id.endswith(":partner") or row.third_party_permission_confirmed:
                    partner_row = row
                else:
                    self_row = row
            lang = user.preferred_language or "en"
            return {
                "saved": self_row is not None,
                "user_id": user.user_id,
                "preferred_language": lang,
                "dpdp_consent_granted": user.dpdp_consent_granted,
                "age_verified_18_plus": user.age_verified_18_plus,
                "parental_consent_verified": user.parental_consent_verified,
                "gender": user.gender,
                "marital_status": user.marital_status,
                "occupation": user.occupation,
                "self_chart": self._decrypt_chart_row(self_row, lang) if self_row else None,
                "partner_chart": (
                    self._decrypt_chart_row(partner_row, lang) if partner_row else None
                ),
            }

    def get_raw_ciphertext(self, chart_id: str) -> tuple[bytes, bytes]:
        with self._session_factory() as s:
            row = s.scalar(select(BirthChartRow).where(BirthChartRow.chart_id == chart_id))
            assert row is not None
            return row.name_encrypted, row.place_name_encrypted

    def get_chart_by_id(self, chart_id: str) -> dict[str, object] | None:
        with self._session_factory() as s:
            c = s.scalar(select(BirthChartRow).where(BirthChartRow.chart_id == chart_id))
            if c is None:
                return None
            return {
                "chart_id": c.chart_id,
                "user_id": c.user_id,
                "name": decrypt_str(c.name_encrypted),
                "birth_date": c.birth_date.isoformat(),
                "birth_time": c.birth_time.isoformat(),
                "place_name": decrypt_str(c.place_name_encrypted),
                "country": decrypt_str(c.country_encrypted) if c.country_encrypted else "",
                "latitude": float(decrypt_str(c.latitude_encrypted)),
                "longitude": float(decrypt_str(c.longitude_encrypted)),
                "timezone_iana": c.timezone_iana,
            }

    def export_user_data(self, user_id: str) -> dict[str, object]:
        with self._session_factory() as s:
            user = s.scalar(select(UserRow).where(UserRow.user_id == user_id))
            if user is None:
                return {}
            charts = s.scalars(select(BirthChartRow).where(BirthChartRow.user_id == user_id)).all()
            return {
                "user_id": user.user_id,
                "dpdp_consent_granted": user.dpdp_consent_granted,
                "age_verified_18_plus": user.age_verified_18_plus,
                "parental_consent_verified": user.parental_consent_verified,
                "notifications_muted": user.notifications_muted,
                "charts": [
                    {
                        "chart_id": c.chart_id,
                        "name": decrypt_str(c.name_encrypted),
                        "birth_date": c.birth_date.isoformat(),
                        "birth_time": c.birth_time.isoformat(),
                        "place_name": decrypt_str(c.place_name_encrypted),
                        "country": decrypt_str(c.country_encrypted) if c.country_encrypted else "",
                        "latitude": float(decrypt_str(c.latitude_encrypted)),
                        "longitude": float(decrypt_str(c.longitude_encrypted)),
                        "timezone_iana": c.timezone_iana,
                    }
                    for c in charts
                ],
            }

    def delete_user(self, user_id: str) -> None:
        with self._session_factory() as s, s.begin():
            s.execute(delete(LedgerEntryRow).where(LedgerEntryRow.user_id == user_id))
            s.execute(delete(AskUsageRow).where(AskUsageRow.user_id == user_id))
            s.execute(delete(BirthChartRow).where(BirthChartRow.user_id == user_id))
            s.execute(delete(UserRow).where(UserRow.user_id == user_id))

    def record_telemetry(
        self,
        *,
        event_type: str,
        category: str | None = None,
        rule_id: str | None = None,
        language: str = "en",
        cohort_hash: str | None = None,
    ) -> None:
        with self._session_factory() as s, s.begin():
            s.add(
                TelemetryEventRow(
                    event_type=event_type,
                    category=category,
                    rule_id=rule_id,
                    language=language,
                    cohort_hash=cohort_hash,
                )
            )

    def telemetry_summary(self) -> dict[str, object]:
        with self._session_factory() as s:
            rows = s.execute(
                select(TelemetryEventRow.event_type, func.count(TelemetryEventRow.id)).group_by(
                    TelemetryEventRow.event_type
                )
            ).all()
            distinct_cohorts = s.scalar(
                select(func.count(func.distinct(TelemetryEventRow.cohort_hash))).where(
                    TelemetryEventRow.cohort_hash.is_not(None)
                )
            )
            counts = {str(k): int(v) for k, v in rows}
            return {
                **counts,
                "distinct_active_cohorts": int(distinct_cohorts or 0),
            }

    def purge_telemetry_older_than(self, *, retention_days: int = 90) -> int:
        """Gap 26: enforce 90-day DPDP telemetry retention purge."""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        with self._session_factory() as s, s.begin():
            result = cast(
                CursorResult[Any],
                s.execute(
                    delete(TelemetryEventRow).where(TelemetryEventRow.recorded_at_utc < cutoff)
                ),
            )
        return int(result.rowcount or 0)

    def consume_ask_quota(
        self,
        *,
        user_id: str,
        week_start: date,
        asked_on: date,
        weekly_limit: int,
        daily_limit: int,
    ) -> AskQuotaStatus:
        """Count one answered question. A limit of 0 or below is unlimited.

        Both limits unlimited writes nothing. ``asked_on`` is the same date
        that produced ``week_start``.
        """
        weekly_open = weekly_limit <= 0
        daily_open = daily_limit <= 0
        if weekly_open and daily_open:
            return AskQuotaStatus.ALLOWED
        with self._session_factory() as s, s.begin():
            row = s.get(AskUsageRow, (user_id, week_start))
            if row is None:
                s.add(
                    AskUsageRow(
                        user_id=user_id,
                        week_start_utc=week_start,
                        questions_used=1,
                        last_asked_on=asked_on,
                        day_questions_used=1,
                    )
                )
                return AskQuotaStatus.ALLOWED
            if not weekly_open and row.questions_used >= weekly_limit:
                return AskQuotaStatus.WEEKLY_EXHAUSTED
            same_day = row.last_asked_on == asked_on
            if not daily_open and same_day and row.day_questions_used >= daily_limit:
                return AskQuotaStatus.DAILY_EXHAUSTED
            row.questions_used += 1
            if same_day:
                row.day_questions_used += 1
            else:
                row.last_asked_on = asked_on
                row.day_questions_used = 1
            return AskQuotaStatus.ALLOWED
