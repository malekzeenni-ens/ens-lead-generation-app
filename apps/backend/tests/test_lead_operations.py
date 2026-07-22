from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi.testclient import TestClient

from app.domains.leads.schemas import PipelineStage
from tests.conftest import lead_payload


def _create_lead(
    client: TestClient,
    campaign_payload: dict[str, object],
    *,
    business_name: str = "Example Celebration Cakes",
    location: str = "Luton",
) -> dict[str, object]:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    payload = lead_payload(str(campaign["id"]))
    payload["business_name"] = business_name
    payload["location"] = location
    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_pipeline_notes_follow_ups_communications_and_summary(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    lead = _create_lead(client, campaign_payload)
    lead_id = str(lead["id"])

    opportunity = client.patch(
        f"/api/v1/leads/{lead_id}",
        json={
            "estimated_order_value": 250,
            "quote_value": 225,
            "won_value": 200,
            "potential_recurrence": "Quarterly",
            "lost_reason": "price",
            "mock_up_status": "requested",
            "sample_status": "under_consideration",
            "quote_status": "preparing",
            "retention_review_date": "2027-07-18",
        },
    )
    assert opportunity.status_code == 200
    assert opportunity.json()["quote_value"] == 225
    assert opportunity.json()["mock_up_status"] == "requested"

    stages = [stage for stage in PipelineStage if stage is not PipelineStage.NEW]
    current = opportunity.json()
    for stage in stages:
        if stage is PipelineStage.DO_NOT_CONTACT:
            continue
        response = client.post(
            f"/api/v1/leads/{lead_id}/stage",
            json={"stage": stage.value, "reason": f"Moved to {stage.value}"},
        )
        assert response.status_code == 200
        current = response.json()
    assert current["pipeline_stage"] == "not_suitable"
    assert len(current["stage_events"]) == len(stages)

    note = client.post(f"/api/v1/leads/{lead_id}/notes", json={"content": "Owner prefers email."})
    assert note.status_code == 201
    assert note.json()["notes"][0]["content"] == "Owner prefers email."

    today = datetime.now(UTC).date()
    follow_up = client.post(
        f"/api/v1/leads/{lead_id}/follow-ups",
        json={"follow_up_type": "email", "due_date": today.isoformat(), "notes": "Check reply"},
    )
    assert follow_up.status_code == 201
    follow_up_id = follow_up.json()["follow_ups"][0]["id"]

    summary = client.get("/api/v1/system/summary")
    assert summary.status_code == 200
    assert summary.json()["due_today"] == 1
    assert summary.json()["open_follow_ups"] == 1

    completed = client.post(
        f"/api/v1/leads/{lead_id}/follow-ups/{follow_up_id}/complete",
        json={
            "next_follow_up": {
                "follow_up_type": "general",
                "due_date": (today + timedelta(days=3)).isoformat(),
                "notes": "Next action",
            }
        },
    )
    assert completed.status_code == 200
    assert [item["status"] for item in completed.json()["follow_ups"]] == [
        "completed",
        "open",
    ]

    unconfirmed = client.post(
        f"/api/v1/leads/{lead_id}/communications",
        json={"channel": "email", "content": "Manual email", "sent_status": "sent"},
    )
    assert unconfirmed.status_code == 422

    communication = client.post(
        f"/api/v1/leads/{lead_id}/communications",
        json={
            "channel": "email",
            "subject": "Cake topper range",
            "content": "Manual email recorded after sending.",
            "sent_status": "sent",
            "user_confirmed": True,
            "response_status": "none",
        },
    )
    assert communication.status_code == 201
    assert communication.json()["communications"][0]["user_confirmed"] is True


def test_suppression_blocks_operations_and_survives_privacy_deletion(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    lead = _create_lead(client, campaign_payload)
    lead_id = str(lead["id"])
    due_date = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    assert (
        client.post(
            f"/api/v1/leads/{lead_id}/follow-ups",
            json={"follow_up_type": "instagram", "due_date": due_date},
        ).status_code
        == 201
    )

    suppression = client.post(
        f"/api/v1/leads/{lead_id}/suppression",
        json={
            "suppression_type": "unsubscribe",
            "reason": "Business asked not to be contacted",
            "source": "Email reply",
        },
    )
    assert suppression.status_code == 201
    suppressed = suppression.json()
    assert suppressed["suppressed"] is True
    assert suppressed["pipeline_stage"] == "do_not_contact"
    assert suppressed["follow_ups"][0]["status"] == "cancelled"

    blocked_stage = client.post(f"/api/v1/leads/{lead_id}/stage", json={"stage": "qualified"})
    assert blocked_stage.status_code == 409
    assert blocked_stage.json()["code"] == "SUPPRESSED_LEAD_STAGE_BLOCKED"
    blocked_follow_up = client.post(
        f"/api/v1/leads/{lead_id}/follow-ups",
        json={"follow_up_type": "email", "due_date": due_date},
    )
    assert blocked_follow_up.status_code == 409
    blocked_message = client.post(
        f"/api/v1/leads/{lead_id}/communications",
        json={
            "channel": "email",
            "content": "Must not be recorded as sent",
            "sent_status": "sent",
            "user_confirmed": True,
        },
    )
    assert blocked_message.status_code == 409

    deleted = client.delete(f"/api/v1/leads/{lead_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "suppression_evidence_retained": True}
    assert client.get(f"/api/v1/leads/{lead_id}").status_code == 404

    campaign = client.get("/api/v1/campaigns").json()[0]
    recreated = client.post("/api/v1/leads", json=lead_payload(campaign["id"]))
    assert recreated.status_code == 409
    assert recreated.json()["code"] == "LEAD_IDENTIFIER_SUPPRESSED"


def test_export_settings_diagnostics_and_formula_protection(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    lead = _create_lead(client, campaign_payload)
    lead_id = str(lead["id"])
    assert (
        client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"business_name": '=HYPERLINK("https://example.test")'},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/leads/{lead_id}/notes", json={"content": "Exported activity note"}
        ).status_code
        == 201
    )

    csv_export = client.get("/api/v1/leads/export", params={"format": "csv"})
    assert csv_export.status_code == 200
    assert csv_export.headers["content-type"].startswith("text/csv")
    assert "'=HYPERLINK" in csv_export.text
    assert "Exported activity note" in csv_export.text

    json_export = client.get("/api/v1/leads/export", params={"format": "json"})
    assert json_export.status_code == 200
    assert json_export.json()[0]["notes"][0]["content"] == "Exported activity note"

    settings = client.patch(
        "/api/v1/system/settings",
        json={"retention_review_days": 730, "follow_up_window_days": 10},
    )
    assert settings.status_code == 200
    assert settings.json()["retention_review_days"] == 730
    assert client.get("/api/v1/system/settings").json()["follow_up_window_days"] == 10

    diagnostics = client.get("/api/v1/system/diagnostics")
    assert diagnostics.status_code == 200
    body = diagnostics.json()
    assert body["schema_version"] == "0008_template_product_families"
    assert body["journal_mode"] == "wal"
    assert body["foreign_keys_enabled"] is True
    assert body["provider_mode"] == "disabled"
    assert body["outbound_messaging"] == "disabled"
