from pathlib import Path

from alembic import command
from alembic.config import Config

from app.db.session import sqlite_url


def backend_directory() -> Path:
    return Path(__file__).resolve().parents[2]


def run_migrations(database_path: Path) -> None:
    config = Config(str(backend_directory() / "alembic.ini"))
    config.set_main_option("script_location", str(backend_directory() / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlite_url(database_path))
    command.upgrade(config, "head")
