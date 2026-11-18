import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

DETAILS = {
    "name": "Aarav",
    "birth_date": "1993-11-14",
    "birth_time": "10:15:00",
    "place_name": "Pune",
    "country": "India",
    "latitude": 18.5204,
    "longitude": 73.8567,
    "uncertainty_minutes": 10,
    "node_type": "MEAN",
    "language": "en",
}
HEADERS = {"X-User-Id": "U_ASK"}


@pytest.fixture
def ask_client():
    settings = Settings(
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        allow_draft_rules=True,
        geocode_provider="manual_only",
        ask_enabled=True,
        ask_weekly_free_quota=3,
    )
    return TestClient(create_app(settings))


@pytest.fixture
def dark_client():
    settings = Settings(
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        allow_draft_rules=True,
        geocode_provider="manual_only",
    )
    return TestClient(create_app(settings))


def test_ask_is_503_when_disabled(dark_client) -> None:
    r = dark_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "Will I change jobs?"},
        headers=HEADERS,
    )
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "ask_disabled"


def test_answered_career_question(ask_client) -> None:
    r = ask_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "Will I change jobs before mid-2027?"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["coverage"]["status"] == "answered"
    assert body["coverage"]["area"] == "career"
    assert body["coverage"]["available_areas"] == ["career", "relationships", "finances", "home"]
    assert body["statement"]["why_this"]["rule_id"] == "RULE_PARASHARI_CAREER_10H"
    assert body["statement"]["safety_verified"] is True
    assert body["llm"]["used"] is False
    assert body["ledger_entry_id"].startswith("ASK-")
    assert body["disclaimer"]


def test_answered_is_idempotent_in_the_ledger(ask_client) -> None:
    payload = {"details": DETAILS, "question": "Will I change jobs before mid-2027?"}
    first = ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS).json()
    second = ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS).json()
    assert first["ledger_entry_id"] == second["ledger_entry_id"]


def test_uncovered_question_costs_nothing(ask_client) -> None:
    payload = {"details": DETAILS, "question": "How is my health in 2027?"}
    r = ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["coverage"] == {
        "status": "uncovered",
        "area": None,
        "matched_terms": [],
        "available_areas": ["career", "relationships", "finances", "home"],
    }
    assert body["statement"] is None
    assert body["ledger_entry_id"] is None
    # Two more uncovered questions must not consume the 3-answer quota.
    for _ in range(2):
        assert ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS).status_code == 200
    answered = ask_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "Should I take a loan this year?"},
        headers=HEADERS,
    )
    assert answered.status_code == 200
    assert answered.json()["coverage"]["area"] == "finances"


def test_short_question_is_422(ask_client) -> None:
    r = ask_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "hi"},
        headers=HEADERS,
    )
    assert r.status_code == 422


def test_quota_blocks_the_fourth_answer(ask_client) -> None:
    payload = {"details": DETAILS, "question": "Should I take a loan this year?"}
    codes = [
        ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]
