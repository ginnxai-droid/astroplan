"""Zero-PII structured JSON logging and request latency metrics (Gap 27)."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import Request, Response

logger = logging.getLogger("astroplan.observability")


def emit_structured_event(event: str, **fields: object) -> str:
    """Emits a zero-PII structured JSON log line (never logs birth data or request bodies)."""
    forbidden = {"name", "place_name", "latitude", "longitude", "birth_date", "birth_time"}
    safe_fields = {k: v for k, v in fields.items() if k not in forbidden}
    payload = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "event": event,
        **safe_fields,
    }
    line = json.dumps(payload, sort_keys=True)
    logger.info(line)
    return line


async def structured_observability_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
    emit_structured_event(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response
