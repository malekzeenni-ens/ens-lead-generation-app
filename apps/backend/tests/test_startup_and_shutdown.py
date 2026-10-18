"""Startup failures are always recorded, and the desktop host can stop the backend cleanly."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import cli, main
from app.core.config import Settings
from app.core.logging import configure_logging


def test_shutdown_requires_the_session_token(app: FastAPI) -> None:
    with TestClient(app) as unauthenticated:
        response = unauthenticated.post("/api/v1/system/shutdown")
    assert response.status_code == 401


def test_shutdown_stops_a_managed_server(client: TestClient, app: FastAPI) -> None:
    unmanaged = client.post("/api/v1/system/shutdown")
    assert unmanaged.status_code == 202
    assert unmanaged.json() == {"stopping": False}

    server = SimpleNamespace(should_exit=False)
    app.state.server = server
    managed = client.post("/api/v1/system/shutdown")
    assert managed.status_code == 202
    assert managed.json() == {"stopping": True}
    assert server.should_exit is True


def test_a_failed_migration_is_logged_before_startup_fails(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(_: Path) -> None:
        raise RuntimeError("simulated broken migration")

    monkeypatch.setattr(main, "run_migrations", broken)
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="broken migration"):
        main.create_app(settings)
    failure = next(
        record for record in caplog.records if record.getMessage().startswith("Database migration")
    )
    assert failure.exc_info is not None


def test_serve_writes_a_startup_error_log(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_: Settings) -> FastAPI:
        raise RuntimeError("simulated startup failure")

    monkeypatch.setattr(cli, "create_app", broken)
    settings.prepare_directories()
    with pytest.raises(RuntimeError, match="simulated startup failure"):
        cli._serve(settings)
    written = (settings.log_directory / "startup-error.log").read_text(encoding="utf-8")
    assert "RuntimeError: simulated startup failure" in written


def test_logging_follows_the_configured_directory_without_leaking_handlers(
    tmp_path: Path,
) -> None:
    root = logging.getLogger()
    first, second = tmp_path / "first", tmp_path / "second"
    configure_logging(first)
    configure_logging(first)
    configure_logging(second)
    file_handlers = [
        handler for handler in root.handlers if isinstance(handler, logging.FileHandler)
    ]
    assert [Path(handler.baseFilename).parent for handler in file_handlers] == [second.resolve()]

    logging.getLogger("tests.logging").warning("lands in the current directory")
    for handler in file_handlers:
        handler.flush()
    assert "lands in the current directory" in (second / "application.jsonl").read_text("utf-8")
