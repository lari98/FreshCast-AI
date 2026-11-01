"""Application factory."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import Engine

from freshcast.assistant.client import BedrockConverseModel, TextModel
from freshcast_api.config import Settings
from freshcast_api.db import make_engine, make_session_factory
from freshcast_api.routers import inventory, proposals


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    text_model: TextModel | None = None,
) -> FastAPI:
    """Build the app; settings, engine and text model are injectable for tests."""
    settings = settings or Settings()
    app = FastAPI(title="FreshCast AI API", version="0.1.0")
    app.state.settings = settings
    if text_model is None and settings.bedrock_model_id:
        text_model = BedrockConverseModel(
            settings.bedrock_model_id, settings.bedrock_region
        )
    app.state.text_model = text_model
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
