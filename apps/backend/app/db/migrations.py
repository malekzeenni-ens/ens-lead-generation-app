import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, pool

from app.db.session import sqlite_url

logger = logging.getLogger(__name__)


def backend_directory() -> Path:
    return Path(__file__).resolve().parents[2]


def _config(database_path: Path) -> Config:
    config = Config(str(backend_directory() / "alembic.ini"))
    config.attributes["configure_logger"] = False
    config.set_main_option("script_location", str(backend_directory() / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlite_url(database_path))
    return config


def current_revision(database_path: Path) -> str | None:
    if not database_path.exists():
        return None
    engine = create_engine(sqlite_url(database_path), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def backup_before_upgrade(database_path: Path, revision: str) -> Path:
    """Copy the database beside itself before pending migrations change it.

    Some migrations cannot be reversed (0018 removes personal data from audit events), so the
    copy is the way back. It holds everything the database held, so the operator deletes it
    once the upgraded app has been checked.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = database_path.with_name(f"{database_path.stem}.pre-upgrade-{revision}-{stamp}.sqlite3")
    source = sqlite3.connect(database_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def run_migrations(database_path: Path) -> None:
    config = _config(database_path)
    head = ScriptDirectory.from_config(config).get_current_head()
    current = current_revision(database_path)
    if current is not None and current != head:
        copy = backup_before_upgrade(database_path, current)
        logger.warning(
            "Copied the database before upgrading it from %s to %s: %s. Delete the copy once "
            "the upgraded app has been checked; it holds everything the database held.",
            current,
            head,
            copy,
            extra={"from_revision": current, "to_revision": head},
        )
    command.upgrade(config, "head")
