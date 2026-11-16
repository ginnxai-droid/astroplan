"""Authentication dependency (Gap 22 / Gap 23).

In dev/test mode, accepts X-User-Id header (defaulting to 'dev-user').
In production mode (auth_mode='firebase'), verifies Bearer Firebase ID tokens.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Header, HTTPException

from app.config import Settings


def make_auth_dependency(settings: Settings) -> Callable[..., Coroutine[Any, Any, str]]:
    async def get_current_user(
        x_user_id: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> str:
        if settings.auth_mode == "dev":
            return x_user_id or "dev-user"
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, {"error": "missing_bearer_token"})
        token = authorization.removeprefix("Bearer ").strip()
        try:
            from firebase_admin import auth

            decoded = auth.verify_id_token(token)
            return str(decoded["uid"])
        except Exception as exc:
            raise HTTPException(401, {"error": "invalid_firebase_token"}) from exc

    return get_current_user
