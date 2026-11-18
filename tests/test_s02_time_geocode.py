from datetime import date, time

import pytest

from app.config import Settings
from app.core.errors import AmbiguousLocationError, GeocoderUnavailableError
from app.core.geocode import ManualOnlyProvider, NominatimProvider
from app.core.observability import emit_structured_event
from app.core.timeutil import jd_ut_to_local_datetime, local_to_utc

pytestmark = pytest.mark.s02


def test_1943_kolkata_wartime_dst() -> None:
    utc = local_to_utc(date(1943, 9, 1), time(0, 0), "Asia/Kolkata")
    assert (utc.year, utc.month, utc.day, utc.hour) == (1943, 8, 31, 17)


def test_1900_kolkata_lmt() -> None:
    utc = local_to_utc(date(1900, 1, 1), time(0, 0), "Asia/Kolkata")
    assert utc.year == 1899


def test_jd_ut_to_local_roundtrip() -> None:
    import swisseph as swe

    jd = swe.julday(2026, 11, 15, 6.5)
    local = jd_ut_to_local_datetime(jd, "Asia/Kolkata")
    assert local.hour == 12 and local.minute == 0


def test_zero_pii_structured_observability_strips_birth_fields() -> None:
    line = emit_structured_event(
        "test_event", path="/v1/chart", name="SecretName", place_name="Pune"
    )
    assert "SecretName" not in line and "Pune" not in line and "/v1/chart" in line


async def test_manual_requires_coords() -> None:
    with pytest.raises(AmbiguousLocationError):
        await ManualOnlyProvider().resolve(
            "Pune", manual_lat=None, manual_lon=None, tz_override=None
        )


async def test_manual_resolves() -> None:
    r = await ManualOnlyProvider().resolve(
        "Pune", manual_lat=18.5204, manual_lon=73.8567, tz_override=None
    )
    assert r.timezone_iana == "Asia/Kolkata"


async def test_nominatim_query_includes_country(monkeypatch) -> None:
    import httpx

    import app.core.geocode as g

    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["q"] = request.url.params["q"]
        return httpx.Response(
            200,
            json=[{"lat": "18.5204", "lon": "73.8567", "display_name": "Pune, India"}],
        )

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class Patched(original):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(g.httpx, "AsyncClient", Patched)
    r = await NominatimProvider(Settings(env="test")).resolve(
        "Pune", country="India", manual_lat=None, manual_lon=None, tz_override=None
    )
    assert captured["q"] == "Pune, India"
    assert r.latitude == 18.5204 and r.timezone_iana == "Asia/Kolkata"


async def test_nominatim_failure_maps_to_typed_error(monkeypatch) -> None:
    import httpx

    import app.core.geocode as g

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class Patched(original):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(g.httpx, "AsyncClient", Patched)
    with pytest.raises(GeocoderUnavailableError):
        await NominatimProvider(Settings(env="test")).resolve(
            "Nowhere", manual_lat=None, manual_lon=None, tz_override=None
        )
