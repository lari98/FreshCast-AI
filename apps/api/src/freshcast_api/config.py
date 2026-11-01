"""Application settings loaded from environment variables (12-factor)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; never hard-code secrets or connection strings."""

    model_config = SettingsConfigDict(env_prefix="FRESHCAST_", env_file=".env")

    env: str = "local"  # local | dev | prod
    database_url: str = "sqlite+pysqlite:///./freshcast_local.db"
    # Bedrock model or EU inference-profile id; unset = deterministic text only.
    bedrock_model_id: str | None = None
    bedrock_region: str = "eu-central-1"
