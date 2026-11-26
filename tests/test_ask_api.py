import re

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


def test_house_question_answers_timing_not_the_catalog(ask_client) -> None:
    r = ask_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "when I buy new house"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    text = body["statement"]["simple_text"]
    assert body["coverage"]["area"] == "home"
    assert "Lagna is" not in text
    assert "नक्षत्र" not in text
    assert re.search(r"home|house", text, re.IGNORECASE)
    assert re.search(r"wait|period|through", text, re.IGNORECASE)
    assert "Be cautious here" not in text


def test_job_change_answers_work_not_the_catalog(ask_client) -> None:
    r = ask_client.post(
        "/v1/readings/ask",
        json={
            "details": DETAILS,
            "question": "I'm desperate to change my job...when will I get it",
        },
        headers=HEADERS,
    )
    assert r.status_code == 200
    text = r.json()["statement"]["simple_text"]
    assert "Lagna is" not in text
    assert re.search(r"work|job", text, re.IGNORECASE)
    assert re.search(r"period|wait|suit|fit|through", text, re.IGNORECASE)
    assert not text.startswith("Lagna")


def test_car_question_is_answered_without_a_life_area(ask_client) -> None:
    r = ask_client.post(
        "/v1/readings/ask",
        json={"details": DETAILS, "question": "When will I buy my first car?"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    text = body["statement"]["simple_text"]
    assert body["coverage"]["status"] == "answered"
    assert body["coverage"]["area"] is None
    assert body["statement"]["category"] == "others"
    assert body["ledger_entry_id"] is None
    assert re.search(r"car|vehicle", text, re.IGNORECASE)
    assert re.search(r"may|can|wait|period", text, re.IGNORECASE)
    assert "Lagna is" not in text
    assert "नक्षत्र" not in text
    assert "?" not in text


def test_quota_blocks_the_fourth_answer(ask_client) -> None:
    payload = {"details": DETAILS, "question": "Should I take a loan this year?"}
    responses = [
        ask_client.post("/v1/readings/ask", json=payload, headers=HEADERS) for _ in range(4)
    ]
    assert [r.status_code for r in responses] == [200, 200, 200, 429]
    detail = responses[-1].json()["detail"]
    assert detail["error"] == "ask_quota_exhausted"
    assert "three" not in str(detail["message"]).lower()


def test_default_weekly_quota_allows_repeated_personal_testing() -> None:
    settings = Settings(
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        allow_draft_rules=True,
        geocode_provider="manual_only",
        ask_enabled=True,
    )
    assert settings.ask_weekly_free_quota == 100
    client = TestClient(create_app(settings))
    payload = {"details": DETAILS, "question": "Should I take a loan this year?"}
    codes = [
        client.post("/v1/readings/ask", json=payload, headers=HEADERS).status_code for _ in range(4)
    ]
    assert codes == [200, 200, 200, 200]
