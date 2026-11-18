"""Firebase Admin bootstrap for G5 production auth.

verify_id_token requires an initialized default app. Fail fast at startup when
credentials are absent so production never serves a misleading 401 per request.
"""

from __future__ import annotations

import os

from app.config import Settings


def _require_credentials() -> None:
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if path:
        if not os.path.isfile(path):
            raise RuntimeError("G5: GOOGLE_APPLICATION_CREDENTIALS points to a missing file")
        return
    from google.auth import default as default_credentials
    from google.auth.exceptions import DefaultCredentialsError

    try:
        default_credentials()
    except DefaultCredentialsError as exc:
        raise RuntimeError(
            "G5: Firebase credentials unavailable; "
            "set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON"
        ) from exc


def configure_firebase(settings: Settings) -> None:
    if settings.auth_mode != "firebase":
        return
    _require_credentials()
    import firebase_admin

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()
