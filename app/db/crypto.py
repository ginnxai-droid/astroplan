"""Fernet field encryption for birth name, place & coordinates at rest (G5)."""

from __future__ import annotations

from cryptography.fernet import Fernet, MultiFernet

_fernet: MultiFernet | None = None


def configure(keys_csv: str, env: str) -> None:
    global _fernet
    raw_keys = [k.strip() for k in keys_csv.split(",") if k.strip()]
    if not raw_keys:
        if env == "production":
            raise RuntimeError("G5: field_encryption_keys required in production")
        raw_keys = [Fernet.generate_key().decode()]
    _fernet = MultiFernet([Fernet(k.encode()) for k in raw_keys])


def encrypt_str(plaintext: str) -> bytes:
    if _fernet is None:
        configure("", "dev")
    assert _fernet is not None
    return _fernet.encrypt(plaintext.encode("utf-8"))


def decrypt_str(token: bytes) -> str:
    if _fernet is None:
        configure("", "dev")
    assert _fernet is not None
    return _fernet.decrypt(token).decode("utf-8")
