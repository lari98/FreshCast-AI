"""Shared fixtures: in-memory SQLite stands in for PostgreSQL in unit tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from freshcast_api.config import Settings
from freshcast_api.db import Base
from freshcast_api.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = create_app(Settings(env="local", database_url="sqlite+pysqlite://"), engine)
    with TestClient(app) as test_client:
        yield test_client


def headers(user: str, role: str) -> dict[str, str]:
    return {"x-dev-user": user, "x-dev-role": role}
