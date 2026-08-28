from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import CampaignRun, LeadCampaign
from app.domains.automation.weekly import current_week_start
from app.domains.outreach.schemas import OutreachBatchCreate, OutreachBatchRead
from app.domains.outreach.service import OutreachService
from tests.conftest import lead_payload


def _template(client: TestClient, *, require_context: bool = True) -> dict[str, Any]:
    body = "Hi {{greeting_name}},\n\nAn idea for {{business_name}}."
    if require_context:
        body = (
            "Hi {{greeting_name}},\n\nI noticed {{personalisation_observation}}. "
            "{{relevance_opportunity}}. {{offer_angle}}. {{desired_next_step}}"
        )
    response = client.post(
        "/api/v1/templates",
        json={
            "topic": "Weekly introduction",
            "subject": "An idea for {{business_name}}",
            "body": body,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def _enable_weekly(
    client: TestClient,
    campaign_id: str,
    template_id: str,
) -> dict[str, Any]:
    response = client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        json={
            "weekly_outreach_enabled": True,
            "weekly_outreach_template_id": template_id,
            "weekly_outreach_provider": "scoring",
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def _ready_lead(
    client: TestClient,
    campaign_id: str,
    *,
    name: str = "Example Celebration Cakes",
    include_context: bool = True,
) -> dict[str, Any]:
    payload = lead_payload(campaign_id)
    payload.update(
        {
            "business_name": name,
            "contact_first_name": "Amira",
            "contact_last_name": "Khan",
            "contact_role": "Owner",
            "contact_email": f"hello@{name.casefold().replace(' ', '-')}.test",
            "contact_classification": "corporate_subscriber",
        }
    )
    if include_context:
        payload.update(
            {
                "personalisation_observation": "your detailed celebration cakes",
                "relevance_opportunity": "small branded details can complete the presentation",
                "offer_angle": "a tailored digital mock-up",
                "desired_next_step": "Would you like me to send two examples?",
            }
        )
    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 201, response.text
    lead = cast(dict[str, Any], response.json())
    stage = client.post(
        f"/api/v1/leads/{lead['id']}/stage",
        json={"stage": "qualified", "reason": "Ready for weekly outreach"},
    )
    assert stage.status_code == 200, stage.text
    return cast(dict[str, Any], stage.json())


def test_first_open_weekly_check_is_idempotent_and_creates_review_draft(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    template = _template(client)
    _enable_weekly(client, campaign["id"], template["id"])
    lead = _ready_lead(client, campaign["id"])

    first = client.post("/api/v1/campaign-runs/weekly/ensure")
    assert first.status_code == 200, first.text
    runs = first.json()
    assert len(runs) == 1
    run = runs[0]
    assert run["trigger"] == "weekly_scoring"
    assert run["week_start"] == current_week_start().isoformat()
    assert run["status"] == "completed"
    assert run["metrics"]["drafts_created"] == 1
    assert run["outreach_batch_id"] is not None

    batches = client.get("/api/v1/outreach/batches").json()
    assert len(batches) == 1
    assert batches[0]["pending_count"] == 1
    assert batches[0]["drafts"][0]["lead_id"] == lead["id"]

    second = client.post("/api/v1/campaign-runs/weekly/ensure")
    assert second.status_code == 200, second.text
    assert [item["id"] for item in second.json()] == [run["id"]]
    assert len(client.get("/api/v1/outreach/batches").json()) == 1


def test_weekly_check_routes_missing_template_context_to_attention(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    template = _template(client)
    _enable_weekly(client, campaign["id"], template["id"])
    _ready_lead(client, campaign["id"], include_context=False)

    response = client.post("/api/v1/campaign-runs/weekly/ensure")
    assert response.status_code == 200, response.text
    run = response.json()[0]
    assert run["status"] == "completed_with_warnings"
    assert run["metrics"]["drafts_created"] == 0
    assert run["metrics"]["attention_required"] == 1
    assert run["metrics"]["missing_context"] == 1
    assert run["outreach_batch_id"] is None
    assert any("personalisation observation" in warning for warning in run["warnings"])
    assert client.get("/api/v1/outreach/batches").json() == []


def test_shared_lead_only_gets_one_draft_from_the_strongest_campaign(
    client: TestClient,
    app: FastAPI,
    campaign_payload: dict[str, object],
) -> None:
    primary = client.post("/api/v1/campaigns", json=campaign_payload).json()
    secondary = client.post(
        "/api/v1/campaigns",
        json={
            **campaign_payload,
            "name": "Unrelated florist campaign",
            "segment": "Florists",
            "product_categories": ["Signs"],
        },
    ).json()
    template = _template(client)
    _enable_weekly(client, primary["id"], template["id"])
    _enable_weekly(client, secondary["id"], template["id"])
    lead = _ready_lead(client, primary["id"])

    database = app.state.database
    with database.session_factory() as session:
        session.add(LeadCampaign(lead_id=lead["id"], campaign_id=secondary["id"]))
        session.commit()

    response = client.post("/api/v1/campaign-runs/weekly/ensure")
    assert response.status_code == 200, response.text
    runs = response.json()
    assert len(runs) == 2
    assert sum(run["metrics"]["drafts_created"] for run in runs) == 1
    assert sum(run["metrics"]["cross_campaign_duplicates"] for run in runs) == 1
    batches = client.get("/api/v1/outreach/batches").json()
    assert len(batches) == 1
    shortlists = client.get("/api/v1/shortlists").json()
    scores_by_campaign = {
        shortlist["campaign_id"]: shortlist["items"][0]["score"] for shortlist in shortlists
    }
    assert scores_by_campaign[batches[0]["campaign_id"]] == max(scores_by_campaign.values())
    assert batches[0]["drafts"][0]["lead_id"] == lead["id"]


def test_global_weekly_limit_caps_drafts_without_losing_shortlist_results(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    template = _template(client)
    _enable_weekly(client, campaign["id"], template["id"])
    _ready_lead(client, campaign["id"], name="Alpha Cakes")
    _ready_lead(client, campaign["id"], name="Beta Bakes")
    settings = client.patch(
        "/api/v1/system/settings",
        json={"weekly_outreach_global_limit": 1},
    )
    assert settings.status_code == 200, settings.text

    run = client.post("/api/v1/campaign-runs/weekly/ensure").json()[0]
    assert run["metrics"]["shortlist_selected"] == 2
    assert run["metrics"]["drafts_created"] == 1
    assert run["metrics"]["weekly_limit_skipped"] == 1


def test_failed_weekly_run_can_retry_the_same_week(
    client: TestClient,
    app: FastAPI,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    template = _template(client, require_context=False)
    _enable_weekly(client, campaign["id"], template["id"])
    run = client.post("/api/v1/campaign-runs/weekly/ensure").json()[0]

    database = app.state.database
    with database.session_factory() as session:
        stored = session.get(CampaignRun, run["id"])
        assert stored is not None
        stored.status = "failed"
        stored.phase = "failed"
        stored.error_code = "TEST_FAILURE"
        stored.error_message = "Synthetic failure"
        session.commit()

    retried = client.post(f"/api/v1/campaign-runs/{run['id']}/weekly-retry")
    assert retried.status_code == 200, retried.text
    assert retried.json()["id"] == run["id"]
    assert retried.json()["status"] == "completed"
    assert retried.json()["error_code"] is None


def test_one_campaign_draft_failure_does_not_stop_other_campaigns(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    campaign_payload: dict[str, object],
) -> None:
    failing = client.post("/api/v1/campaigns", json=campaign_payload).json()
    healthy = client.post(
        "/api/v1/campaigns",
        json={**campaign_payload, "name": "Healthy weekly campaign"},
    ).json()
    template = _template(client)
    _enable_weekly(client, failing["id"], template["id"])
    _enable_weekly(client, healthy["id"], template["id"])
    _ready_lead(client, failing["id"], name="Failing Cakes")
    _ready_lead(client, healthy["id"], name="Healthy Cakes")
    original_create_batch = OutreachService.create_batch

    def flaky_create_batch(
        service: OutreachService,
        session: Session,
        data: OutreachBatchCreate,
        correlation_id: str,
    ) -> OutreachBatchRead:
        if data.campaign_id == failing["id"]:
            raise RuntimeError("Synthetic campaign-specific failure")
        return original_create_batch(service, session, data, correlation_id)

    monkeypatch.setattr(OutreachService, "create_batch", flaky_create_batch)

    response = client.post("/api/v1/campaign-runs/weekly/ensure")
    assert response.status_code == 200, response.text
    runs = {run["campaign_id"]: run for run in response.json()}
    assert runs[failing["id"]]["status"] == "failed"
    assert runs[failing["id"]]["error_code"] == "WEEKLY_DRAFT_PREPARATION_FAILED"
    assert runs[healthy["id"]]["status"] == "completed"
    assert runs[healthy["id"]]["metrics"]["drafts_created"] == 1
    batches = client.get("/api/v1/outreach/batches").json()
    assert [batch["campaign_id"] for batch in batches] == [healthy["id"]]


def test_monday_and_tuesday_share_the_same_weekly_run_boundary() -> None:
    monday = datetime(2026, 8, 24, 12, tzinfo=UTC)
    tuesday = datetime(2026, 8, 25, 12, tzinfo=UTC)

    assert current_week_start(monday) == date(2026, 8, 24)
    assert current_week_start(tuesday) == date(2026, 8, 24)
