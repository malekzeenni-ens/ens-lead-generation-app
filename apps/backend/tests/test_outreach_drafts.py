from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db.migrations import backend_directory, run_migrations
from app.db.session import create_sqlite_engine, sqlite_url
from tests.conftest import lead_payload


def _ready_lead(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> tuple[dict[str, Any], dict[str, Any]]:
    campaign_response = client.post("/api/v1/campaigns", json=campaign_payload)
    assert campaign_response.status_code == 201
    campaign = cast(dict[str, Any], campaign_response.json())
    payload = lead_payload(str(campaign["id"]))
    payload.update(
        {
            "public_email": "owner@example.test",
            "contact_classification": "corporate_subscriber",
        }
    )
    lead_response = client.post("/api/v1/leads", json=payload)
    assert lead_response.status_code == 201
    lead = cast(dict[str, Any], lead_response.json())
    stage_response = client.post(
        f"/api/v1/leads/{lead['id']}/stage",
        json={"stage": "qualified", "reason": "Ready for controlled outreach"},
    )
    assert stage_response.status_code == 200
    return campaign, cast(dict[str, Any], stage_response.json())


def _template(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v1/templates",
        json={
            "topic": "Bakery introduction",
            "subject": "A local idea for {{business_name}}",
            "body": "Hello {{business_name}},\n\nI noticed your work in {{location}}.",
        },
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


def _batch(
    client: TestClient,
    campaign: dict[str, Any],
    lead: dict[str, Any],
    template: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/outreach/batches",
        json={
            "campaign_id": campaign["id"],
            "template_id": template["id"],
            "lead_ids": [lead["id"]],
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_local_draft_edit_approve_and_lead_change_requires_reapproval(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    note_response = client.post(
        f"/api/v1/leads/{lead['id']}/notes",
        json={"content": "Mention the seasonal cake range."},
    )
    assert note_response.status_code == 201
    template = _template(client)

    options = client.get("/api/v1/outreach/lead-options").json()
    option = next(item for item in options if item["id"] == lead["id"])
    assert option["ready"] is True
    assert option["latest_notes"] == ["Mention the seasonal cake range."]

    batch = _batch(client, campaign, lead, template)
    assert batch["status"] == "review"
    assert batch["pending_count"] == 1
    draft = batch["drafts"][0]
    assert draft["current_revision"]["subject"] == ("A local idea for Example Celebration Cakes")
    assert "I noticed your work in Luton." in draft["current_revision"]["body"]
    assert draft["sync_status"] == "local_only"

    edit_response = client.patch(
        f"/api/v1/outreach/drafts/{draft['id']}",
        json={
            "subject": "A personal note for Example Celebration Cakes",
            "body": "Hello,\n\nI especially liked your seasonal cake range.",
        },
    )
    assert edit_response.status_code == 200, edit_response.text
    edited = edit_response.json()
    assert edited["current_version"] == 2
    assert edited["revision_count"] == 2
    assert edited["review_status"] == "pending_review"

    approval = client.post(f"/api/v1/outreach/drafts/{draft['id']}/approve", json={})
    assert approval.status_code == 200, approval.text
    assert approval.json()["review_status"] == "approved"
    assert approval.json()["approved_version"] == 2
    assert approval.json()["approved_at"] is not None
    activity_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert [item["action"] for item in activity_lead["outreach_activities"]] == [
        "outreach.draft_generated",
        "outreach.draft_edited",
        "outreach.draft_approved",
    ]
    assert [item["version"] for item in activity_lead["outreach_activities"]] == [1, 2, 2]
    ready_batch = client.get(f"/api/v1/outreach/batches/{batch['id']}").json()
    assert ready_batch["status"] == "ready"

    changed_email = client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={"public_email": "hello@example.test"},
    )
    assert changed_email.status_code == 200
    invalidated = client.get(f"/api/v1/outreach/batches/{batch['id']}").json()["drafts"][0]
    assert invalidated["review_status"] == "pending_review"
    assert invalidated["sync_status"] == "blocked"
    assert invalidated["approved_version"] is None
    assert "changed after approval" in invalidated["blocked_reason"]

    reapproval = client.post(f"/api/v1/outreach/drafts/{draft['id']}/approve", json={})
    assert reapproval.status_code == 200
    assert reapproval.json()["recipient_email"] == "hello@example.test"
    assert reapproval.json()["sync_status"] == "local_only"


def test_rejection_only_closes_the_draft_and_can_be_reopened(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    batch = _batch(client, campaign, lead, _template(client))
    draft = batch["drafts"][0]

    rejected_response = client.post(
        f"/api/v1/outreach/drafts/{draft['id']}/reject",
        json={"reason": "Not the right message this week"},
    )
    assert rejected_response.status_code == 200
    rejected = rejected_response.json()
    assert rejected["review_status"] == "rejected"
    assert rejected["sync_status"] == "local_only"
    assert rejected["rejection_reason"] == "Not the right message this week"

    unchanged_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert unchanged_lead["suppressed"] is False
    assert unchanged_lead["pipeline_stage"] == "qualified"
    assert [item["action"] for item in unchanged_lead["outreach_activities"]] == [
        "outreach.draft_generated",
        "outreach.draft_rejected",
    ]
    assert unchanged_lead["outreach_activities"][-1]["reason"] == (
        "Not the right message this week"
    )
    assert client.get(f"/api/v1/outreach/batches/{batch['id']}").json()["status"] == "closed"

    reopened_response = client.post(f"/api/v1/outreach/drafts/{draft['id']}/reopen", json={})
    assert reopened_response.status_code == 200
    reopened = reopened_response.json()
    assert reopened["review_status"] == "pending_review"
    assert reopened["rejected_at"] is None
    assert reopened["rejection_reason"] is None
    reopened_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert reopened_lead["outreach_activities"][-1]["action"] == "outreach.draft_reopened"


def test_named_contact_context_renders_and_direct_email_is_preferred(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    context_response = client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={
            "contact_first_name": "Amira",
            "contact_last_name": "Khan",
            "contact_role": "Owner",
            "contact_email": "Amira@Direct.test",
            "personalisation_observation": "your hand-painted wedding cakes",
            "relevance_opportunity": "matching details can complete the presentation",
            "offer_angle": "a personalised sample set",
            "desired_next_step": "Would you like me to send three examples?",
        },
    )
    assert context_response.status_code == 200, context_response.text
    lead = context_response.json()
    template_response = client.post(
        "/api/v1/templates",
        json={
            "topic": "Personalised introduction",
            "subject": "An idea for {{contact_first_name}} at {{business_name}}",
            "body": (
                "Hi {{greeting_name}},\n\nI noticed {{personalisation_observation}}. "
                "{{relevance_opportunity}}. I can offer {{offer_angle}}. "
                "{{desired_next_step}}\n\n{{contact_full_name}} · {{contact_role}}"
            ),
        },
    )
    assert template_response.status_code == 201

    batch = _batch(client, campaign, lead, template_response.json())
    draft = batch["drafts"][0]
    assert draft["recipient_email"] == "amira@direct.test"
    assert draft["current_revision"]["subject"] == (
        "An idea for Amira at Example Celebration Cakes"
    )
    assert draft["current_revision"]["body"] == (
        "Hi Amira,\n\nI noticed your hand-painted wedding cakes. "
        "matching details can complete the presentation. I can offer a personalised sample set. "
        "Would you like me to send three examples?\n\nAmira Khan · Owner"
    )

    approval = client.post(f"/api/v1/outreach/drafts/{draft['id']}/approve", json={})
    assert approval.status_code == 200
    assert approval.json()["recipient_email"] == "amira@direct.test"
    context_change = client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={"avoid_mentioning": "Do not reference the discontinued range"},
    )
    assert context_change.status_code == 200
    invalidated = client.get(f"/api/v1/outreach/batches/{batch['id']}").json()["drafts"][0]
    assert invalidated["review_status"] == "pending_review"
    assert invalidated["sync_status"] == "blocked"

    reapproval = client.post(f"/api/v1/outreach/drafts/{draft['id']}/approve", json={})
    assert reapproval.status_code == 200
    handoff = client.post(f"/api/v1/outreach/drafts/{draft['id']}/zoho-open", json={})
    assert handoff.status_code == 200
    assert handoff.json()["recipient_email"] == "amira@direct.test"


def test_zoho_handoff_logs_each_click_and_manual_sent_confirmation(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    batch = _batch(client, campaign, lead, _template(client))
    draft = batch["drafts"][0]
    approval = client.post(f"/api/v1/outreach/drafts/{draft['id']}/approve", json={})
    assert approval.status_code == 200

    premature_confirmation = client.post(
        f"/api/v1/outreach/drafts/{draft['id']}/sent-confirmed", json={}
    )
    assert premature_confirmation.status_code == 409
    assert premature_confirmation.json()["code"] == "OUTREACH_DRAFT_NOT_CONFIRMABLE"

    first_open = client.post(f"/api/v1/outreach/drafts/{draft['id']}/zoho-open", json={})
    assert first_open.status_code == 200, first_open.text
    handoff = first_open.json()
    assert handoff == {
        "draft_id": draft["id"],
        "lead_id": lead["id"],
        "recipient_email": "owner@example.test",
        "subject": "A local idea for Example Celebration Cakes",
        "body": "Hello Example Celebration Cakes,\n\nI noticed your work in Luton.",
        "version": 1,
        "opened_at": handoff["opened_at"],
    }
    assert (
        client.get(f"/api/v1/outreach/batches/{batch['id']}").json()["drafts"][0]["sync_status"]
        == "opened_in_zoho"
    )

    second_open = client.post(f"/api/v1/outreach/drafts/{draft['id']}/zoho-open", json={})
    assert second_open.status_code == 200
    activity_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    click_events = [
        item
        for item in activity_lead["outreach_activities"]
        if item["action"] == "outreach.zoho_open_clicked"
    ]
    assert len(click_events) == 2
    assert all(item["version"] == 1 for item in click_events)
    assert all(item["recipient_email"] == "owner@example.test" for item in click_events)

    sent_response = client.post(f"/api/v1/outreach/drafts/{draft['id']}/sent-confirmed", json={})
    assert sent_response.status_code == 200, sent_response.text
    assert sent_response.json()["sync_status"] == "user_confirmed_sent"

    closed_batch = client.get(f"/api/v1/outreach/batches/{batch['id']}").json()
    assert closed_batch["status"] == "closed"
    assert closed_batch["approved_count"] == 0
    assert closed_batch["sent_count"] == 1

    updated_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert updated_lead["pipeline_stage"] == "qualified"
    assert len(updated_lead["communications"]) == 1
    communication = updated_lead["communications"][0]
    assert communication["channel"] == "email"
    assert communication["subject"] == handoff["subject"]
    assert communication["content"] == handoff["body"]
    assert communication["sent_status"] == "sent"
    assert communication["user_confirmed"] is True
    assert communication["sent_at"] is not None

    duplicate_confirmation = client.post(
        f"/api/v1/outreach/drafts/{draft['id']}/sent-confirmed", json={}
    )
    assert duplicate_confirmation.status_code == 409
    assert len(client.get(f"/api/v1/leads/{lead['id']}").json()["communications"]) == 1


def test_failed_zoho_open_is_logged_and_does_not_enable_sent_confirmation(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    batch = _batch(client, campaign, lead, _template(client))
    draft = batch["drafts"][0]
    approval = client.post(f"/api/v1/outreach/drafts/{draft['id']}/approve", json={})
    assert approval.status_code == 200
    opened = client.post(f"/api/v1/outreach/drafts/{draft['id']}/zoho-open", json={})
    assert opened.status_code == 200

    failed = client.post(
        f"/api/v1/outreach/drafts/{draft['id']}/zoho-open-failed",
        json={"reason": "No default email composer is configured."},
    )
    assert failed.status_code == 200
    assert failed.json()["sync_status"] == "local_only"

    activity_lead = client.get(f"/api/v1/leads/{lead['id']}").json()
    assert [item["action"] for item in activity_lead["outreach_activities"]][-2:] == [
        "outreach.zoho_open_clicked",
        "outreach.zoho_open_failed",
    ]
    assert activity_lead["outreach_activities"][-1]["reason"] == (
        "No default email composer is configured."
    )
    confirmation = client.post(f"/api/v1/outreach/drafts/{draft['id']}/sent-confirmed", json={})
    assert confirmation.status_code == 409
    assert client.get(f"/api/v1/leads/{lead['id']}").json()["communications"] == []


def test_eligibility_blocks_holds_and_duplicate_active_drafts(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    template = _template(client)
    hold_until = (datetime.now(UTC).date() + timedelta(days=7)).isoformat()

    hold_response = client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={
            "outreach_hold_reason": "Waiting for the autumn launch",
            "outreach_hold_until": hold_until,
        },
    )
    assert hold_response.status_code == 200
    held_option = next(
        item
        for item in client.get("/api/v1/outreach/lead-options").json()
        if item["id"] == lead["id"]
    )
    assert held_option["ready"] is False
    assert held_option["outreach_hold_until"] == hold_until
    assert any("outreach hold" in reason for reason in held_option["blockers"])

    blocked_batch = client.post(
        "/api/v1/outreach/batches",
        json={"template_id": template["id"], "lead_ids": [lead["id"]]},
    )
    assert blocked_batch.status_code == 409
    assert blocked_batch.json()["code"] == "OUTREACH_LEADS_NOT_READY"

    clear_response = client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={"outreach_hold_reason": None, "outreach_hold_until": None},
    )
    assert clear_response.status_code == 200
    _batch(client, campaign, lead, template)

    duplicate = client.post(
        "/api/v1/outreach/batches",
        json={"template_id": template["id"], "lead_ids": [lead["id"]]},
    )
    assert duplicate.status_code == 409
    blocked_reasons = duplicate.json()["details"]["blocked_leads"][0]["reasons"]
    assert any("active draft" in reason for reason in blocked_reasons)


def test_migration_upgrades_an_existing_0008_database(tmp_path: Path) -> None:
    database_path = tmp_path / "existing-0008.db"
    config = Config(str(backend_directory() / "alembic.ini"))
    config.set_main_option("script_location", str(backend_directory() / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlite_url(database_path))
    command.upgrade(config, "0008_template_product_families")

    run_migrations(database_path)

    engine = create_sqlite_engine(database_path)
    try:
        inspector = inspect(engine)
        assert {
            "outreach_batch",
            "outreach_draft",
            "outreach_draft_revision",
        }.issubset(inspector.get_table_names())
        lead_columns = {column["name"] for column in inspector.get_columns("lead")}
        assert {
            "outreach_hold_until",
            "outreach_hold_reason",
            "contact_first_name",
            "contact_last_name",
            "contact_role",
            "contact_email",
            "contact_source_reference",
            "personalisation_observation",
            "relevance_opportunity",
            "offer_angle",
            "desired_next_step",
            "avoid_mentioning",
        }.issubset(lead_columns)
    finally:
        engine.dispose()
