from __future__ import annotations

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


def _loc(body: object) -> list[str]:
    return [str(item.get("loc")) for item in body["detail"]]  # type: ignore[index]


def test_missing_name_is_rejected(client) -> None:
    payload = {k: v for k, v in DETAILS.items() if k != "name"}
    r = client.post("/v1/chart", json=payload)
    assert r.status_code == 422
    assert any("name" in loc for loc in _loc(r.json()))


def test_missing_country_is_rejected(client) -> None:
    payload = {k: v for k, v in DETAILS.items() if k != "country"}
    r = client.post("/v1/chart", json=payload)
    assert r.status_code == 422
    assert any("country" in loc for loc in _loc(r.json()))


def test_blank_name_and_country_use_stable_error_codes(client) -> None:
    r = client.post("/v1/chart", json={**DETAILS, "name": "   ", "country": "  "})
    assert r.status_code == 422
    body = str(r.json())
    assert "name_required" in body
    assert "country_required" in body


def test_identity_fields_are_echoed_and_trimmed(client) -> None:
    r = client.post("/v1/chart", json={**DETAILS, "name": " Aarav ", "country": " India "})
    assert r.status_code == 200, r.text
    summary = r.json()["input_summary"]
    assert summary["name"] == "Aarav"
    assert summary["country"] == "India"
