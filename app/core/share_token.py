"""HMAC-SHA256 signed, expiring, SQL-revocable share tokens (Gap 20 / M5 / Contradiction 6)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker


class ShareTokenManager:
    def __init__(self, secret: str, session_factory: sessionmaker[Session] | None = None) -> None:
        self._secret = secret.encode("utf-8")
        self._sf = session_factory
        self._revoked: set[str] = set()

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_token(self, chart_id: str, user_id: str, ttl_seconds: int = 86400) -> str:
        payload = {
            "chart_id": chart_id,
            "user_id": user_id,
            "exp": int(time.time()) + ttl_seconds,
        }
        raw = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode("utf-8")).decode(
            "ascii"
        )
        sig = hmac.new(self._secret, raw.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{raw}.{sig}"

    def revoke_token(self, token: str) -> None:
        th = self._hash(token)
        self._revoked.add(th)
        if self._sf is not None:
            from app.db.models import RevokedShareTokenRow

            with self._sf() as s, s.begin():
                s.merge(RevokedShareTokenRow(token_hash=th))

    def _is_revoked(self, token: str) -> bool:
        th = self._hash(token)
        if th in self._revoked:
            return True
        if self._sf is not None:
            from app.db.models import RevokedShareTokenRow

            with self._sf() as s:
                row = s.scalar(
                    select(RevokedShareTokenRow).where(RevokedShareTokenRow.token_hash == th)
                )
                return row is not None
        return False

    def verify_token(self, token: str) -> dict[str, object]:
        if "." not in token or self._is_revoked(token):
            raise ValueError("invalid_or_revoked_share_token")
        raw, sig = token.split(".", 1)
        expected = hmac.new(self._secret, raw.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("invalid_share_token_signature")
        data = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))
        if int(data["exp"]) < int(time.time()):
            raise ValueError("expired_share_token")
        return cast(dict[str, object], data)
