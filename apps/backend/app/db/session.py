from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def create_sqlite_engine(path: Path) -> Engine:
    engine = create_engine(
        sqlite_url(path),
        connect_args={"check_same_thread": False, "timeout": 5.0},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.engine = create_sqlite_engine(path)
        self.session_factory = sessionmaker(
            bind=self.engine, class_=Session, expire_on_commit=False, autoflush=False
        )

    def session(self) -> Iterator[Session]:
        with self.session_factory() as session:
            yield session

    def close(self) -> None:
        self.engine.dispose()
