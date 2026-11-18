from __future__ import annotations

from pathlib import Path

import pytest
from google.auth.exceptions import DefaultCredentialsError

from app.config import Settings
from app.main import create_app


def _no_default_app() -> None:
    raise ValueError("The default Firebase app does not exist")


def test_dev_auth_mode_never_initializes_firebase(monkeypatch: pytest.MonkeyPatch) -> None:
    import firebase_admin

    monkeypatch.setattr(
        firebase_admin,
        "initialize_app",
        lambda: pytest.fail("dev mode must not initialize the Firebase Admin SDK"),
    )
    create_app(Settings(env="test", allow_draft_rules=True))


def test_firebase_auth_mode_initializes_admin_sdk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key = tmp_path / "service-account.json"
    key.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key))
    import firebase_admin

    initialized: list[bool] = []
    monkeypatch.setattr(firebase_admin, "get_app", _no_default_app)
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda: initialized.append(True))

    create_app(Settings(env="test", allow_draft_rules=True, auth_mode="firebase"))

    assert initialized == [True]


def test_firebase_auth_mode_reuses_an_initialized_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key = tmp_path / "service-account.json"
    key.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key))
    import firebase_admin

    monkeypatch.setattr(firebase_admin, "get_app", lambda: object())
    monkeypatch.setattr(
        firebase_admin,
        "initialize_app",
        lambda: pytest.fail("must reuse the already initialized default app"),
    )

    create_app(Settings(env="test", allow_draft_rules=True, auth_mode="firebase"))


def test_firebase_auth_mode_fails_fast_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    import google.auth

    monkeypatch.setattr(
        google.auth,
        "default",
        lambda: (_ for _ in ()).throw(DefaultCredentialsError("no ADC")),
    )

    with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS"):
        create_app(Settings(env="test", allow_draft_rules=True, auth_mode="firebase"))


def test_firebase_auth_mode_fails_fast_when_credentials_file_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "not-there.json"))

    with pytest.raises(RuntimeError, match="missing file"):
        create_app(Settings(env="test", allow_draft_rules=True, auth_mode="firebase"))
