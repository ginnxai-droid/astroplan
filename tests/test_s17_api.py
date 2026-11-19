import logging

import pytest

pytestmark = pytest.mark.s17


def test_chart_dasha_transits_daily_insight_yogas_304_etag_and_observability(
    client, caplog
) -> None:
    payload = {
        "name": "Aarav",
        "birth_date": "1993-11-14",
        "birth_time": "10:15:00",
        "place_name": "Pune",
        "country": "India",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "uncertainty_minutes": 10,
        "node_type": "MEAN",
        "language": "hi",
    }
    with caplog.at_level(logging.INFO, logger="astroplan.observability"):
        r = client.post("/v1/chart", json=payload)
    assert r.status_code == 200
    assert r.json()["ayanamsa_name"] == "Lahiri"
    assert r.json()["disclaimer"] != ""
    assert {"navamsa_lagna_sign_index", "navamsa_lagna_sign_name"} <= r.json().keys()
    assert any('"event": "http_request"' in rec.message for rec in caplog.records)

    assert client.post("/v1/dasha", json=payload).status_code == 200
    assert client.post("/v1/transits", json=payload).status_code == 200
    assert client.post("/v1/insights/daily", json=payload).status_code == 200
    assert client.post("/v1/readings/yogas-doshas", json=payload).status_code == 200

    r_panchang = client.get("/v1/panchang?target_date=2026-11-16&lat=18.5204&lon=73.8567")
    assert r_panchang.status_code == 200
    assert {
        "moon_longitude",
        "moon_sign_name",
        "moon_degree_in_sign",
        "moon_nakshatra_pada",
        "reference_datetime",
        "reference_kind",
        "phase_illumination",
    } <= r_panchang.json().keys()
    assert "max-age=86400" in r_panchang.headers.get("Cache-Control", "")
    etag = r_panchang.headers["ETag"]
    r_304 = client.get(
        "/v1/panchang?target_date=2026-11-16&lat=18.5204&lon=73.8567",
        headers={"If-None-Match": etag},
    )
    assert r_304.status_code == 304

    r_life = client.post("/v1/readings/life-areas", json=payload)
    assert r_life.status_code == 200
    assert set(r_life.json()["life_areas"].keys()) == {
        "career",
        "relationships",
        "finances",
        "home",
    }


def test_trust_about_predictions_exposes_agpl_source_offer() -> None:
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        allow_draft_rules=True,
        geocode_provider="manual_only",
        source_offer_url="https://example.org/astroplan-source",
    )
    body = TestClient(create_app(settings)).get("/v1/trust/about-predictions?lang=en").json()
    assert body["source_offer_url"] == "https://example.org/astroplan-source"
    assert body["license"] == "AGPL-3.0"


def test_m1_cross_user_idor_blocked_m2_operator_gate_and_share_revocation(client) -> None:
    headers_u999 = {"X-User-Id": "U999"}
    headers_attacker = {"X-User-Id": "U_ATTACKER"}

    consent_res = client.post(
        "/v1/privacy/consent",
        json={"user_id": "U999", "dpdp_consent_granted": True, "age_verified_18_plus": True},
        headers=headers_u999,
    )
    assert consent_res.status_code == 200

    save_req = {
        "user_id": "U999",
        "chart_id": "C999",
        "details": {
            "name": "Aarav",
            "birth_date": "1992-05-10",
            "birth_time": "14:30:00",
            "place_name": "Pune",
            "country": "India",
            "latitude": 18.5204,
            "longitude": 73.8567,
        },
        "dpdp_consent_granted": True,
        "age_verified_18_plus": True,
    }
    assert client.post("/v1/user/chart", json=save_req, headers=headers_u999).status_code == 200

    assert client.get("/v1/user/U999/export", headers=headers_attacker).status_code == 403
    assert client.delete("/v1/user/U999", headers=headers_attacker).status_code == 403
    assert (
        client.post(
            "/v1/user/chart/C999/share-token?consent_to_share=true",
            headers=headers_attacker,
        ).status_code
        == 403
    )

    assert client.post("/v1/user/chart/C999/share-token", headers=headers_u999).status_code == 400
    tok_res = client.post(
        "/v1/user/chart/C999/share-token?consent_to_share=true", headers=headers_u999
    )
    assert tok_res.status_code == 200
    tok = tok_res.json()["share_token"]
    assert client.get(f"/v1/share/{tok}").status_code == 200
    assert client.post(f"/v1/share/{tok}/revoke", headers=headers_u999).status_code == 200
    assert client.get(f"/v1/share/{tok}").status_code == 403

    pref_res = client.post(
        "/v1/user/notifications/preferences",
        json={"notifications_muted": True},
        headers=headers_u999,
    )
    assert pref_res.status_code == 200 and pref_res.json()["notifications_muted"] is True

    assert client.post("/v1/notifications/dispatch-due").status_code == 403
    assert (
        client.post(
            "/v1/notifications/dispatch-due",
            headers={"X-Operator-Key": "dev-operator-key"},
        ).status_code
        == 200
    )
    assert client.post("/v1/metrics/purge-expired").status_code == 403
    assert (
        client.post(
            "/v1/metrics/purge-expired",
            headers={"X-Operator-Key": "dev-operator-key"},
        ).status_code
        == 200
    )

    exp = client.get("/v1/privacy/export", headers=headers_u999)
    assert exp.status_code == 200 and exp.json()["charts"][0]["name"] == "Aarav"
    assert exp.json()["charts"][0]["country"] == "India"
    assert client.delete("/v1/privacy/delete", headers=headers_u999).status_code == 200


def test_ledger_calibration_is_scoped_to_the_authenticated_user(client) -> None:
    headers = {"X-User-Id": "U_CAL"}

    own = client.get("/v1/ledger/calibration", headers=headers)
    assert own.status_code == 200
    assert own.json()["scope_user_id"] == "U_CAL"

    assert client.get("/v1/ledger/calibration?user_id=U_CAL", headers=headers).status_code == 200

    cross_user = client.get("/v1/ledger/calibration?user_id=U_OTHER", headers=headers)
    assert cross_user.status_code == 403
    assert cross_user.json()["detail"]["error"] == "forbidden_cross_user_access"


def test_ledger_marks_require_a_closed_window(client) -> None:
    headers = {"X-User-Id": "U_WINDOW"}
    base = {
        "user_id": "U_WINDOW",
        "statement_id": "S_WINDOW",
        "rule_id": "RULE_PARASHARI_CAREER_10H",
        "statement_text": "Steady professional progress is supported through planning.",
        "confidence_grade": "supported",
        "observable_outcome_criteria": "Role changed by window end.",
    }

    future = client.post(
        "/v1/ledger/register",
        headers=headers,
        json={**base, "entry_id": "E_FUTURE", "time_window": "Q1 2027"},
    )
    assert future.status_code == 200
    blocked = client.post("/v1/ledger/E_FUTURE/mark", headers=headers, json={"outcome": "miss"})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["error"] == "window_not_closed"

    undated = client.post(
        "/v1/ledger/register",
        headers=headers,
        json={**base, "entry_id": "E_UNDATED", "time_window": "when it happens"},
    )
    assert undated.status_code == 422
    assert undated.json()["detail"]["error"] == "unresolvable_time_window"

    closed = client.post(
        "/v1/ledger/register",
        headers=headers,
        json={**base, "entry_id": "E_CLOSED", "time_window": "Q1 2020"},
    )
    assert closed.status_code == 200
    marked = client.post("/v1/ledger/E_CLOSED/mark", headers=headers, json={"outcome": "hit"})
    assert marked.status_code == 200


def test_m6_firebase_mode_rejects_unauthenticated_requests(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    monkeypatch.setattr("app.main.configure_firebase", lambda settings: None)
    fb_client = TestClient(
        create_app(
            Settings(
                env="test",
                auth_mode="firebase",
                database_url="sqlite+pysqlite:///:memory:",
                allow_draft_rules=True,
                geocode_provider="manual_only",
            )
        )
    )
    assert fb_client.get("/v1/privacy/export").status_code == 401
    assert fb_client.delete("/v1/privacy/delete").status_code == 401
    assert fb_client.get("/v1/ledger/calibration").status_code == 401
    assert (
        fb_client.post(
            "/v1/privacy/consent",
            json={"user_id": "U1", "dpdp_consent_granted": True, "age_verified_18_plus": True},
        ).status_code
        == 401
    )


def test_m4_festivals_full_year_and_gap24_openapi_schema_contract(client) -> None:
    res = client.get("/v1/festivals?year=2026&include_computed_vrats=true")
    assert res.status_code == 200
    months = {item["date"][:7] for item in res.json()}
    assert "2026-06" in months and "2026-12" in months

    schema = client.app.openapi()
    required_paths = {
        "/v1/chart": {"post"},
        "/v1/dasha": {"post"},
        "/v1/transits": {"post"},
        "/v1/panchang": {"get"},
        "/v1/insights/daily": {"post"},
        "/v1/readings/yogas-doshas": {"post"},
        "/v1/readings/life-areas": {"post"},
        "/v1/reports/annual-forecast": {"post"},
        "/v1/matching/ashtakoota": {"post"},
        "/v1/privacy/consent": {"post"},
        "/v1/privacy/export": {"get"},
        "/v1/privacy/delete": {"delete"},
        "/v1/user/notifications/preferences": {"post"},
        "/v1/metrics/purge-expired": {"post"},
        "/v1/ledger/register": {"post"},
        "/v1/ledger/calibration": {"get"},
    }
    for path, methods in required_paths.items():
        assert path in schema["paths"], f"Missing OpenAPI path: {path}"
        assert methods.issubset(set(schema["paths"][path].keys()))

    schemas = schema["components"]["schemas"]
    assert {"navamsa_lagna_sign_index", "navamsa_lagna_sign_name"} <= set(
        schemas["ChartResponse"]["required"]
    )
    assert {"lagna_sign_name", "moon_nakshatra", "planets", "disclaimer"}.issubset(
        set(schemas["ChartResponse"]["properties"].keys())
    )
    assert {"simple_text", "pro_text", "why_this", "safety_verified"}.issubset(
        set(schemas["ExplainedStatement"]["properties"].keys())
    )
