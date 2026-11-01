"""The migration must build the same schema the ORM models describe."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from freshcast_api.db import Base


def test_migration_matches_models(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'm.db'}"
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    inspector = inspect(create_engine(url))
    assert set(Base.metadata.tables) <= set(inspector.get_table_names())
    for name, table in Base.metadata.tables.items():
        assert {c.name for c in table.columns} == {
            c["name"] for c in inspector.get_columns(name)
        }
    command.downgrade(cfg, "base")
