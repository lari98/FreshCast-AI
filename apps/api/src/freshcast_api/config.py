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
    # Allowed browser origins (JSON list in the environment). Empty = none.
    cors_origins: list[str] = []
    # Optional ClamAV daemon for signature scans of uploads. If set and the
    # daemon is unreachable, uploads are refused (fail closed).
    clamd_host: str | None = None
    clamd_port: int = 3310
    # Per client address and minute. In-memory, so per process: a managed WAF or
    # API Gateway throttle is still needed in front of a deployed API.
    rate_limit_per_minute: int = 600
    analyze_rate_limit_per_minute: int = 20
    # Upload analysis is the heavy job: at most this many run at once (others get
    # 503 and Retry-After); identical uploads come from a small in-memory cache.
    analyze_max_concurrent: int = 2
    analyze_cache_entries: int = 8
    analyze_cache_ttl_seconds: int = 900
