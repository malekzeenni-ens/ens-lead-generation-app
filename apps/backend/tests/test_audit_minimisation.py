"""Audit events hold no personal data; outreach history lives with the lead (ADR-024, D2)."""

from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.migrations import backend_directory, run_migrations
from app.db.models import AuditEvent, OutreachActivity
from app.db.session import create_sqlite_engine, sqlite_url
from app.domains.audit.service import PERSONAL_DATA_KEYS, record_audit_event
from tests.test_outreach_drafts import _batch, _ready_lead, _template


def test_an_audit_summary_with_personal_data_is_refused(app: FastAPI) -> None:
    with app.state.database.session_factory() as session:
        with pytest.raises(ValueError, match=r"values\.after\.contact_email"):
            record_audit_event(
                session,
                action="lead.updated",
                entity_type="lead",
                entity_id="lead",
                correlation_id="test",
                summary={"values": {"after": {"contact_email": "a@b.test"}}},
            )
        with pytest.raises(ValueError, match="reason"):
            record_audit_event(
                session,
                action="lead.stage_changed",
                entity_type="lead",
                entity_id="lead",
                correlation_id="test",
                summary={"reason": "Spoke to Amira"},
            )


def test_no_audit_call_site_names_a_personal_data_key() -> None:
    """Catches a call on a path the suite does not exercise."""
    offenders: list[str] = []
    for path in sorted((backend_directory() / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call) and getattr(node.func, "id", "") == "record_audit_event"
            ):
                continue
            for keyword in node.keywords:
                if keyword.arg != "summary":
                    continue
                for inner in ast.walk(keyword.value):
                    if isinstance(inner, ast.Dict):
                        for key in inner.keys:
                            if (
                                isinstance(key, ast.Constant)
                                and isinstance(key.value, str)
                                and key.value in PERSONAL_DATA_KEYS
                            ):
                                offenders.append(f"{path.name}:{node.lineno} {key.value}")
    assert offenders == []


def test_outreach_history_is_kept_with_the_lead_and_deleted_with_it(
    client: TestClient, app: FastAPI, campaign_payload: dict[str, object]
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    draft = _batch(client, campaign, lead, _template(client))["drafts"][0]
    assert client.post(f"/api/v1/outreach/drafts/{draft['id']}/approve", json={}).status_code == 200
    assert (
        client.post(f"/api/v1/outreach/drafts/{draft['id']}/zoho-open", json={}).status_code == 200
    )
    failed = client.post(
        f"/api/v1/outreach/drafts/{draft['id']}/zoho-open-failed",
        json={"reason": "Amira's mail app was closed."},
    )
    assert failed.status_code == 200
    renamed = client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={"contact_first_name": "Amira", "quote_status": "requested"},
    )
    assert renamed.status_code == 200

    history = client.get(f"/api/v1/leads/{lead['id']}").json()["outreach_activities"]
    assert [item["action"] for item in history] == [
        "outreach.draft_generated",
        "outreach.draft_approved",
        "outreach.zoho_open_clicked",
        "outreach.zoho_open_failed",
    ]
    assert history[2]["recipient_email"] == "owner@example.test"
    assert history[3]["reason"] == "Amira's mail app was closed."

    with app.state.database.session_factory() as session:
        summaries = [json.dumps(event.summary) for event in session.query(AuditEvent)]
        update = next(
            event.summary for event in session.query(AuditEvent).filter_by(action="lead.updated")
        )
    audit_text = "\n".join(summaries)
    for personal in ("owner@example.test", "Amira", "Example Celebration Cakes"):
        assert personal not in audit_text
    assert update["changed_fields"] == ["contact_first_name", "quote_status"]
    assert update["values"] == {"quote_status": {"before": "not_requested", "after": "requested"}}

    assert client.delete(f"/api/v1/leads/{lead['id']}").status_code == 200
    with app.state.database.session_factory() as session:
        assert session.query(OutreachActivity).count() == 0


def _database_at_0017(tmp_path: Path) -> Path:
    database_path = tmp_path / "existing-0017.db"
    config = Config(str(backend_directory() / "alembic.ini"))
    config.set_main_option("script_location", str(backend_directory() / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlite_url(database_path))
    command.upgrade(config, "0017_suppression_identifiers")
    return database_path


def _seed(database_path: Path, statements: list[tuple[str, dict[str, Any]]]) -> None:
    engine = create_sqlite_engine(database_path)
    try:
        with engine.begin() as connection:
            for statement, parameters in statements:
                connection.execute(text(statement), parameters)
    finally:
        engine.dispose()


def _audit(event_id: str, action: str, entity: str, entity_id: str, summary: Any, when: str) -> Any:
    return (
        "INSERT INTO audit_event (id, action, entity_type, entity_id, actor, correlation_id, "
        "summary, created_at) VALUES (:id, :action, :entity, :entity_id, 'local_user', 'c', "
        ":summary, :when)",
        {
            "id": event_id,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "summary": json.dumps(summary),
            "when": when,
        },
    )


def test_migration_moves_outreach_history_and_scrubs_audit_events(tmp_path: Path) -> None:
    database_path = _database_at_0017(tmp_path)
    now = "2026-10-01T09:00:00+00:00"
    _seed(
        database_path,
        [
            (
                "INSERT INTO campaign (id, name, segment, primary_location, radius_miles, "
                "keywords, exclusion_keywords, product_categories, discovery_sources, "
                "weekly_shortlist_size, minimum_score_threshold, preferred_channels, "
                "offer_settings, discovery_mode, status, weekly_outreach_enabled, "
                "weekly_outreach_provider, created_at, updated_at) VALUES ('c1', 'C', 'S', "
                "'Luton', 5, '[]', '[]', '[]', '[]', 5, 0, '[]', '{}', 'manual', 'active', 0, "
                "'scoring', :now, :now)",
                {"now": now},
            ),
            (
                "INSERT INTO lead (id, business_name, normalized_name, segment, location, "
                "contact_classification, pipeline_stage, suppressed, mock_up_status, "
                "sample_status, quote_status, created_at, updated_at) VALUES ('l1', 'Crown', "
                "'crown', 'S', 'Luton', 'unknown', 'qualified', 0, 'not_offered', "
                "'not_applicable', 'not_requested', :now, :now)",
                {"now": now},
            ),
            (
                "INSERT INTO outreach_batch (id, campaign_id, status, created_at, updated_at) "
                "VALUES ('b1', 'c1', 'ready', :now, :now)",
                {"now": now},
            ),
            (
                "INSERT INTO outreach_draft (id, batch_id, lead_id, recipient_email, "
                "review_status, sync_status, current_version, created_at, updated_at) VALUES "
                "('d1', 'b1', 'l1', 'owner@crown.test', 'approved', 'local_only', 1, :now, :now)",
                {"now": now},
            ),
            _audit(
                "e1",
                "outreach.draft_generated",
                "outreach_draft",
                "d1",
                {"lead_id": "l1", "version": 1},
                "2026-10-01T09:00:01+00:00",
            ),
            _audit(
                "e2",
                "outreach.zoho_open_clicked",
                "outreach_draft",
                "d1",
                {
                    "lead_id": "l1",
                    "version": 1,
                    "recipient_email": "owner@crown.test",
                    "sending_confirmed": False,
                },
                "2026-10-01T09:00:02+00:00",
            ),
            _audit(
                "e3",
                "outreach.zoho_open_failed",
                "outreach_draft",
                "d1",
                {
                    "lead_id": "l1",
                    "version": 1,
                    "recipient_email": "owner@crown.test",
                    "reason": "Mail app closed",
                },
                "2026-10-01T09:00:03+00:00",
            ),
            _audit(
                "e4",
                "lead.updated",
                "lead",
                "l1",
                {
                    "before": {"contact_email": None, "quote_status": "not_requested"},
                    "after": {"contact_email": "amira@crown.test", "quote_status": "requested"},
                    "invalidated_outreach_drafts": 0,
                },
                "2026-10-01T09:00:04+00:00",
            ),
            _audit(
                "e5",
                "lead.created",
                "lead",
                "l1",
                {"business_name": "Crown", "campaign_id": "c1"},
                now,
            ),
            _audit(
                "e6",
                "outreach.draft_generated",
                "outreach_draft",
                "gone",
                {"lead_id": "x", "version": 1},
                now,
            ),
        ],
    )

    run_migrations(database_path)

    engine = create_sqlite_engine(database_path)
    try:
        with engine.connect() as connection:
            activities = connection.execute(
                text(
                    "SELECT id, action, reason, recipient_email FROM outreach_activity "
                    "ORDER BY created_at"
                )
            ).all()
            opened = connection.execute(
                text("SELECT zoho_opened_at FROM outreach_draft WHERE id = 'd1'")
            ).scalar_one()
            summaries = {
                row.id: json.loads(row.summary)
                for row in connection.execute(text("SELECT id, summary FROM audit_event"))
            }
    finally:
        engine.dispose()

    assert [(row.id, row.action) for row in activities] == [
        ("e1", "outreach.draft_generated"),
        ("e2", "outreach.zoho_open_clicked"),
        ("e3", "outreach.zoho_open_failed"),
    ]
    assert activities[2].reason == "Mail app closed"
    assert activities[1].recipient_email == "owner@crown.test"
    assert str(opened).startswith("2026-10-01")
    assert summaries["e3"] == {
        "lead_id": "l1",
        "version": 1,
        "reason_provided": True,
    }
    assert summaries["e4"] == {
        "invalidated_outreach_drafts": 0,
        "changed_fields": ["contact_email", "quote_status"],
        "values": {"quote_status": {"before": "not_requested", "after": "requested"}},
    }
    assert summaries["e5"] == {"campaign_id": "c1"}
    backups = list(
        tmp_path.glob("existing-0017.pre-upgrade-0017_suppression_identifiers-*.sqlite3")
    )
    assert len(backups) == 1
    # The copy is the way back: it still holds the audit data the upgrade removed.
    copy = sqlite3.connect(backups[0])
    try:
        (raw,) = copy.execute("SELECT summary FROM audit_event WHERE id = 'e3'").fetchone()
    finally:
        copy.close()
    assert json.loads(raw)["recipient_email"] == "owner@crown.test"
