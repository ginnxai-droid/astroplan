from __future__ import annotations

from datetime import date, timedelta

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


def test_future_birth_date_is_rejected_with_stable_error_code(client) -> None:
    future = (date.today() + timedelta(days=1)).isoformat()
    r = client.post("/v1/chart", json={**DETAILS, "birth_date": future})
    assert r.status_code == 422
    assert "birth_date_in_future" in str(r.json())


def test_today_and_past_birth_dates_are_accepted(client) -> None:
    for birth_date in (date.today(), date.today() - timedelta(days=1)):
        r = client.post("/v1/chart", json={**DETAILS, "birth_date": birth_date.isoformat()})
        assert r.status_code == 200, r.text
