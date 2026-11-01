"""Alembic environment: reads the database URL from application settings."""

from alembic import context
from sqlalchemy import create_engine

from freshcast_api import models  # noqa: F401  (registers tables on Base.metadata)
from freshcast_api.config import Settings
from freshcast_api.db import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    url = context.config.get_main_option("sqlalchemy.url") or Settings().database_url
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
