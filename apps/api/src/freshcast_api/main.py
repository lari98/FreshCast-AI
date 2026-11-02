"""Application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from freshcast.assistant.client import BedrockConverseModel, TextModel
from freshcast_api import hardening
from freshcast_api.config import Settings
from freshcast_api.db import make_engine, make_session_factory
from freshcast_api.routers import analyze, inventory, proposals


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    text_model: TextModel | None = None,
) -> FastAPI:
    """Build the app; settings, engine and text model are injectable for tests."""
    settings = settings or Settings()
    app = FastAPI(title="FreshCast AI API", version="0.2.0")
    app.state.settings = settings
    if text_model is None and settings.bedrock_model_id:
        text_model = BedrockConverseModel(
            settings.bedrock_model_id, settings.bedrock_region
        )
    app.state.text_model = text_model
    app.state.session_factory = make_session_factory(
        engine or make_engine(settings.database_url)
    )
    # Browser access for the local dashboard only; deployed environments set
    # FRESHCAST_CORS_ORIGINS explicitly instead of relying on a default.
    origins = settings.cors_origins or (
        ["http://localhost:3000", "http://127.0.0.1:3000"]
        if settings.env == "local"
        else []
    )
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["x-dev-user", "x-dev-role", "content-type"],
        )
    hardening.install(app, settings)
    app.include_router(analyze.router)
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
