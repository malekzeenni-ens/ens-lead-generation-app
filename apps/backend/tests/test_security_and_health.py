import json
import logging
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from app.core.config import Settings
from app.core.logging import JsonFormatter, redact
from app.main import create_app
from tests.conftest import SESSION_TOKEN


def test_non_loopback_host_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match=r"must bind to 127\.0\.0\.1"):
        Settings(
            host="0.0.0.0",  # noqa: S104 -- asserting this value is rejected
            session_token=SESSION_TOKEN,
            database_path=tmp_path / "blocked.db",
        )


def test_health_requires_ephemeral_session_token(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as unauthenticated:
        response = unauthenticated.get("/api/v1/health")
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_TOKEN_INVALID"
    assert response.json()["correlation_id"]


def test_openapi_schema_requires_session_token(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as unauthenticated:
        blocked = unauthenticated.get("/api/v1/openapi.json")
    assert blocked.status_code == 401

    with TestClient(app, headers={"X-Session-Token": SESSION_TOKEN}) as authenticated:
        allowed = authenticated.get("/api/v1/openapi.json")
    assert allowed.status_code == 200
    assert allowed.json()["info"]["title"] == "Etch 'N' Shine Lead Generation API"


def test_health_and_sqlite_safety_pragmas(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Correlation-ID": "test-health"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Correlation-ID"] == "test-health"
    assert response.headers["X-Content-Type-Options"] == "nosniff"

    database = cast(FastAPI, client.app).state.database
    with database.engine.connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar_one().lower() == "wal"
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000


def test_log_redaction_is_recursive() -> None:
    value = {
        "token": "secret",
        "nested": {"password": "hidden", "state": "oauth-state"},
        "code": "oauth-code",
        "safe": "visible",
    }
    assert redact(value) == {
        "token": "[REDACTED]",
        "nested": {"password": "[REDACTED]", "state": "[REDACTED]"},
        "code": "[REDACTED]",
        "safe": "visible",
    }


def test_json_formatter_redacts_extra_kwargs_on_real_log_records() -> None:
    logger = logging.getLogger("test.redaction")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        0,
        "Meta OAuth callback received",
        (),
        None,
        extra={"access_token": "should-not-appear", "campaign_run_id": "run-123"},
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["extra"] == {"access_token": "[REDACTED]", "campaign_run_id": "run-123"}
