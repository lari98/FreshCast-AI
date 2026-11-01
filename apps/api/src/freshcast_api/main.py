"""Application factory."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import Engine

from freshcast_api.config import Settings
from freshcast_api.db import make_engine, make_session_factory
from freshcast_api.routers import inventory, proposals


def create_app(
    settings: Settings | None = None, engine: Engine | None = None
) -> FastAPI:
    """Build the app; settings and engine are injectable for tests."""
    settings = settings or Settings()
    app = FastAPI(title="FreshCast AI API", version="0.1.0")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(
        engine or make_engine(settings.database_url)
    )
    app.include_router(inventory.router)
    app.include_router(proposals.router)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        """Liveness probe (no dependencies, no data)."""
        return {"status": "ok"}

    return app


def app_factory() -> FastAPI:
    """Entry point for ``uvicorn --factory freshcast_api.main:app_factory``."""
    return create_app()
