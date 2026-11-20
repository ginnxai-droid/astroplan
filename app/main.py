from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import build_router
from app.config import Settings, get_settings
from app.core.ephemeris import configure
from app.core.firebase import configure_firebase
from app.core.observability import structured_observability_middleware
from app.db import crypto


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure(settings)
    crypto.configure(settings.field_encryption_keys, settings.env)
    configure_firebase(settings)
    app = FastAPI(
        title="Astroplan API v3.6",
        version="3.6.0",
        description=(
            "Vedic-native astrology API with verifiable calculations, "
            "Why-This explanations, Daily Insights, Yogas/Doshas, and Prediction Ledger v0."
        ),
    )
    app.middleware("http")(structured_observability_middleware)
    app.include_router(build_router(settings))
    return app
