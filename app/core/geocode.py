"""Geocoding interface + Nominatim adapter with bounded LRU cache and disambiguation (Gap 31)."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol

import httpx
from timezonefinder import TimezoneFinder

from app.config import Settings
from app.core.errors import AmbiguousLocationError, GeocoderUnavailableError
from app.core.timeutil import load_zone


@dataclass(frozen=True)
class ResolvedPlace:
    latitude: float
    longitude: float
    timezone_iana: str
    source: str
    display_name: str = ""


class GeocodeProvider(Protocol):
    async def resolve(
        self,
        place_name: str,
        *,
        country: str | None = None,
        manual_lat: float | None,
        manual_lon: float | None,
        tz_override: str | None,
    ) -> ResolvedPlace: ...

    async def search_candidates(self, query: str, limit: int = 5) -> list[ResolvedPlace]: ...


def _resolve_manual(
    tf: TimezoneFinder, place: str, lat: float, lon: float, tz_override: str | None
) -> ResolvedPlace:
    tz = tz_override or tf.timezone_at(lat=lat, lng=lon)
    if tz is None:
        raise AmbiguousLocationError(place)
    load_zone(tz)
    return ResolvedPlace(lat, lon, tz, "manual", display_name=place)


class ManualOnlyProvider:
    def __init__(self) -> None:
        self._tf = TimezoneFinder()

    async def resolve(
        self,
        place_name: str,
        *,
        country: str | None = None,
        manual_lat: float | None,
        manual_lon: float | None,
        tz_override: str | None,
    ) -> ResolvedPlace:
        if manual_lat is None or manual_lon is None:
            raise AmbiguousLocationError(place_name)
        return _resolve_manual(self._tf, place_name, manual_lat, manual_lon, tz_override)

    async def search_candidates(self, query: str, limit: int = 5) -> list[ResolvedPlace]:
        return []


class NominatimProvider:
    def __init__(self, settings: Settings, max_cache_size: int = 2048) -> None:
        self._s = settings
        self._tf = TimezoneFinder()
        self._cache: OrderedDict[str, ResolvedPlace] = OrderedDict()
        self._max_cache_size = max_cache_size
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def _search_nominatim(self, query: str, limit: int) -> list[ResolvedPlace]:
        async with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)
            self._last = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        f"{self._s.nominatim_url}/search",
                        params={"q": query, "format": "json", "limit": limit},
                        headers={"User-Agent": self._s.geocode_user_agent},
                    )
                    resp.raise_for_status()
                    data = resp.json()
            except httpx.HTTPError as exc:
                raise GeocoderUnavailableError(query) from exc
        out: list[ResolvedPlace] = []
        if not isinstance(data, list):
            return out
        for row in data:
            lat, lon = float(row["lat"]), float(row["lon"])
            tz = self._tf.timezone_at(lat=lat, lng=lon)
            if tz:
                out.append(
                    ResolvedPlace(
                        lat,
                        lon,
                        tz,
                        "nominatim",
                        display_name=str(row.get("display_name", query)),
                    )
                )
        return out

    async def _search_open_meteo(self, query: str, limit: int) -> list[ResolvedPlace]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": query, "count": limit, "language": "en", "format": "json"},
                    headers={"User-Agent": self._s.geocode_user_agent},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GeocoderUnavailableError(query) from exc
        if not isinstance(data, dict):
            return []
        rows = data.get("results")
        out: list[ResolvedPlace] = []
        for row in rows or []:
            lat, lon = float(row["latitude"]), float(row["longitude"])
            tz = row.get("timezone") or self._tf.timezone_at(lat=lat, lng=lon)
            if tz:
                out.append(
                    ResolvedPlace(
                        lat,
                        lon,
                        str(tz),
                        "open-meteo",
                        display_name=str(row.get("name", query)),
                    )
                )
        return out

    async def search_candidates(self, query: str, limit: int = 5) -> list[ResolvedPlace]:
        # Public Nominatim rejects many cloud hosts. Resolve with Open-Meteo first.
        meteo_down = False
        try:
            found = await self._search_open_meteo(query, limit)
        except GeocoderUnavailableError:
            found = []
            meteo_down = True
        if found:
            return found
        try:
            return await self._search_nominatim(query, limit)
        except GeocoderUnavailableError:
            if meteo_down:
                raise
            return []

    async def resolve(
        self,
        place_name: str,
        *,
        country: str | None = None,
        manual_lat: float | None,
        manual_lon: float | None,
        tz_override: str | None,
    ) -> ResolvedPlace:
        if manual_lat is not None and manual_lon is not None:
            return _resolve_manual(self._tf, place_name, manual_lat, manual_lon, tz_override)
        query = f"{place_name}, {country}" if country else place_name
        key = query.strip().lower()
        if key in self._cache:
            self._cache.move_to_end(key)
            c = self._cache[key]
            return ResolvedPlace(
                c.latitude, c.longitude, tz_override or c.timezone_iana, "cache", c.display_name
            )
        candidates = await self.search_candidates(query, limit=5)
        if not candidates:
            raise AmbiguousLocationError(query)
        first = candidates[0]
        tz = tz_override or first.timezone_iana
        load_zone(tz)
        resolved = ResolvedPlace(
            first.latitude, first.longitude, tz, first.source, first.display_name
        )
        self._cache[key] = resolved
        if len(self._cache) > self._max_cache_size:
            self._cache.popitem(last=False)
        return resolved


def make_provider(settings: Settings) -> GeocodeProvider:
    return (
        ManualOnlyProvider()
        if settings.geocode_provider == "manual_only"
        else NominatimProvider(settings)
    )
