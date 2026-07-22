from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models import AuditEvent, LeadStageEvent, SourceObservation
from app.main import create_app
from tests.conftest import SESSION_TOKEN, lead_payload


def test_campaign_validation_has_consistent_error_shape(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    invalid = {**campaign_payload, "radius_miles": 0}
    response = client.post("/api/v1/campaigns", json=invalid)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"]
    assert body["correlation_id"]


def test_manual_lead_flow_is_audited_and_survives_restart(
    client: TestClient,
    settings: Settings,
    campaign_payload: dict[str, object],
) -> None:
    campaign_response = client.post("/api/v1/campaigns", json=campaign_payload)
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    lead_response = client.post("/api/v1/leads", json=lead_payload(campaign["id"]))
    assert lead_response.status_code == 201
    lead = lead_response.json()
    assert lead["business_name"] == "Example Celebration Cakes"
    assert lead["campaign_ids"] == [campaign["id"]]
    assert lead["sources"][0]["source_type"] == "manual"
    assert lead["sources"][0]["classification"] == "user_verified"
    assert lead["stage_events"][0]["new_stage"] == "new"
    assert lead["contact_classification"] == "unknown"

    detail = client.get(f"/api/v1/leads/{lead['id']}")
    assert detail.status_code == 200
    assert detail.json()["sources"][0]["observed_value"] == lead["business_name"]

    duplicate = client.post("/api/v1/leads", json=lead_payload(campaign["id"]))
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "LEAD_DUPLICATE_REVIEW_REQUIRED"

    application = cast(FastAPI, client.app)
    with application.state.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 2
        assert session.scalar(select(func.count()).select_from(SourceObservation)) == 1
        assert session.scalar(select(func.count()).select_from(LeadStageEvent)) == 1

    application.state.database.close()
    restarted = create_app(settings)
    with TestClient(restarted, headers={"X-Session-Token": SESSION_TOKEN}) as restarted_client:
        leads = restarted_client.get("/api/v1/leads")
        campaigns = restarted_client.get("/api/v1/campaigns")
        assert leads.status_code == 200
        assert campaigns.status_code == 200
        assert [item["id"] for item in leads.json()] == [lead["id"]]
        assert [item["id"] for item in campaigns.json()] == [campaign["id"]]
