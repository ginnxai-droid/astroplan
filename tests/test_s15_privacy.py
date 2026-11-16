import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.core.notifications import collect_due_notification_users
from app.core.share_token import ShareTokenManager
from app.db import crypto
from app.db.models import TelemetryEventRow
from app.db.repo import PrivacyRepo

pytestmark = pytest.mark.s15


def test_fernet_encryption_name_place_consent_sql_revocation_and_window_dispatch(
    fernet_key: str,
) -> None:
    crypto.configure(fernet_key, "test")
    repo = PrivacyRepo("sqlite+pysqlite:///:memory:")

    with pytest.raises(ValueError, match="dpdp_consent_required"):
        repo.create_user_and_chart(
            user_id="U_NO_CONSENT",
            chart_id="C_NO",
            birth_date=date(1993, 11, 14),
            birth_time=time(10, 15),
            place_name="Pune",
            lat=18.5204,
            lon=73.8567,
            tz_iana="Asia/Kolkata",
        )

    repo.create_user_and_chart(
        user_id="U100",
        chart_id="C100",
        name="Aarav Sharma",
        birth_date=date(1993, 11, 14),
        birth_time=time(10, 15),
        place_name="Pune",
        lat=18.5204,
        lon=73.8567,
        tz_iana="Asia/Kolkata",
        dpdp_consent_granted=True,
        age_verified_18_plus=True,
        notification_time=time(7, 30),
    )
    raw_name, raw_place = repo.get_raw_ciphertext("C100")
    assert b"Aarav" not in raw_name and b"Pune" not in raw_place

    due = collect_due_notification_users(
        repo.session_factory, time(7, 40), date(2026, 11, 16), window_minutes=15
    )
    assert len(due) == 1 and due[0]["user_id"] == "U100"

    mgr_writer = ShareTokenManager("secret-key", session_factory=repo.session_factory)
    tok = mgr_writer.create_token("C100", "U100", ttl_seconds=600)
    assert mgr_writer.verify_token(tok)["chart_id"] == "C100"
    mgr_writer.revoke_token(tok)

    mgr_reader = ShareTokenManager("secret-key", session_factory=repo.session_factory)
    with pytest.raises(ValueError, match="invalid_or_revoked"):
        mgr_reader.verify_token(tok)

    repo.delete_user("U100")
    assert repo.export_user_data("U100") == {}


def test_telemetry_90_day_retention_purge_enforced() -> None:
    """Gap 26: the documented 90-day retention policy is executable code."""
    crypto.configure(Fernet.generate_key().decode(), "test")
    repo = PrivacyRepo("sqlite+pysqlite:///:memory:")

    repo.record_telemetry(event_type="daily_panchang_opened", cohort_hash="CH_RET")
    with repo.session_factory() as s, s.begin():
        s.add(
            TelemetryEventRow(
                event_type="life_area_viewed",
                cohort_hash="CH_RET",
                recorded_at_utc=datetime.now(UTC) - timedelta(days=91),
            )
        )

    purged = repo.purge_telemetry_older_than(retention_days=90)
    assert purged == 1

    summary = repo.telemetry_summary()
    assert summary["daily_panchang_opened"] == 1  # type: ignore[index]
    assert "life_area_viewed" not in summary  # type: ignore[operator]


def test_create_app_wires_configured_field_encryption_keys(tmp_path: Path) -> None:
    """G5: configured Fernet keys must encrypt PII at rest and survive restarts."""
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    key = Fernet.generate_key().decode()
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'keys.db').as_posix()}"
    settings = Settings(
        env="test",
        database_url=db_url,
        allow_draft_rules=True,
        geocode_provider="manual_only",
        field_encryption_keys=key,
    )
    client = TestClient(create_app(settings))
    res = client.post(
        "/v1/user/chart",
        headers={"X-User-Id": "U_KEYS"},
        json={
            "user_id": "U_KEYS",
            "chart_id": "C_KEYS",
            "details": {
                "name": "Asha Keys",
                "birth_date": "1990-05-15",
                "birth_time": "08:45:00",
                "place_name": "Pune",
                "latitude": 18.5204,
                "longitude": 73.8567,
                "timezone_override": "Asia/Kolkata",
            },
            "dpdp_consent_granted": True,
            "age_verified_18_plus": True,
        },
    )
    assert res.status_code == 200, res.text

    raw_name, _ = PrivacyRepo(db_url).get_raw_ciphertext("C_KEYS")
    assert Fernet(key.encode()).decrypt(raw_name).decode() == "Asha Keys"

    restarted = TestClient(create_app(settings))
    export = restarted.get("/v1/privacy/export", headers={"X-User-Id": "U_KEYS"})
    assert export.status_code == 200
    assert "Asha Keys" in json.dumps(export.json())
