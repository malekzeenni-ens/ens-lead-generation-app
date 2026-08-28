from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AuditEvent, CampaignRun, LeadCampaign, OutreachBatch, OutreachDraft


def test_campaign_edit_pause_search_and_duplicate(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    created_response = client.post("/api/v1/campaigns", json=campaign_payload)
    assert created_response.status_code == 201
    campaign = created_response.json()

    updated_response = client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        json={
            "description": "Updated local campaign",
            "weekly_shortlist_size": 8,
            "status": "paused",
        },
    )
    assert updated_response.status_code == 200
    updated = updated_response.json()
    assert updated["description"] == "Updated local campaign"
    assert updated["weekly_shortlist_size"] == 8
    assert updated["status"] == "paused"

    search = client.get("/api/v1/campaigns", params={"query": "bakery", "status": "paused"})
    assert search.status_code == 200
    assert [item["id"] for item in search.json()] == [campaign["id"]]

    duplicate_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/duplicate",
        json={
            "name": "Milton Keynes Bakery Partnerships",
            "primary_location": "Milton Keynes, United Kingdom",
        },
    )
    assert duplicate_response.status_code == 201
    duplicate = duplicate_response.json()
    assert duplicate["name"] == "Milton Keynes Bakery Partnerships"
    assert duplicate["primary_location"] == "Milton Keynes, United Kingdom"
    assert duplicate["status"] == "paused"
    assert duplicate["product_categories"] == campaign["product_categories"]

    conflict = client.patch(f"/api/v1/campaigns/{campaign['id']}", json={"name": duplicate["name"]})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "CAMPAIGN_NAME_EXISTS"


def test_campaign_archive_preserves_leads_and_unarchives_as_paused(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    lead = client.post(
        "/api/v1/leads",
        json=_campaign_lead_payload(campaign["id"], "Archived Campaign Bakery"),
    ).json()

    archived_response = client.patch(
        f"/api/v1/campaigns/{campaign['id']}", json={"status": "inactive"}
    )

    assert archived_response.status_code == 200
    assert archived_response.json()["status"] == "inactive"
    assert [item["id"] for item in client.get("/api/v1/leads").json()] == [lead["id"]]
    archived_search = client.get("/api/v1/campaigns", params={"status": "inactive"})
    assert [item["id"] for item in archived_search.json()] == [campaign["id"]]

    unarchived_response = client.patch(
        f"/api/v1/campaigns/{campaign['id']}", json={"status": "paused"}
    )

    assert unarchived_response.status_code == 200
    assert unarchived_response.json()["status"] == "paused"
    assert [item["id"] for item in client.get("/api/v1/leads").json()] == [lead["id"]]


def _campaign_lead_payload(campaign_id: str, business_name: str) -> dict[str, object]:
    slug = business_name.casefold().replace(" ", "-")
    return {
        "campaign_id": campaign_id,
        "business_name": business_name,
        "segment": "Bakeries and home bakers",
        "location": "Luton",
        "website": f"https://{slug}.example.test",
        "contact_classification": "unknown",
        "source": {
            "name": "Manual entry",
            "source_type": "manual",
            "source_url": f"https://{slug}.example.test",
            "classification": "user_verified",
        },
    }


def test_campaign_delete_removes_exclusive_leads_and_retains_shared_leads(
    client: TestClient,
    app: FastAPI,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    other_campaign = client.post(
        "/api/v1/campaigns",
        json={**campaign_payload, "name": "Shared Lead Campaign"},
    ).json()
    exclusive_lead = client.post(
        "/api/v1/leads",
        json=_campaign_lead_payload(campaign["id"], "Exclusive Bakery"),
    ).json()
    shared_lead = client.post(
        "/api/v1/leads",
        json=_campaign_lead_payload(campaign["id"], "Shared Bakery"),
    ).json()
    with app.state.database.session_factory() as session:
        batch = OutreachBatch(campaign_id=None, template_id=None)
        session.add(batch)
        session.flush()
        session.add(
            OutreachDraft(
                batch_id=batch.id,
                lead_id=exclusive_lead["id"],
                template_id=None,
                recipient_email="owner@exclusive-bakery.example.test",
            )
        )
        session.add(LeadCampaign(lead_id=shared_lead["id"], campaign_id=other_campaign["id"]))
        session.commit()

    response = client.delete(f"/api/v1/campaigns/{campaign['id']}")

    assert response.status_code == 200
    assert response.json() == {
        "deleted": True,
        "campaign_id": campaign["id"],
        "associated_leads": 2,
        "leads_deleted": 1,
        "shared_leads_retained": 1,
        "outreach_batches_deleted": 1,
    }
    assert client.get(f"/api/v1/campaigns/{campaign['id']}").status_code == 404
    remaining_leads = client.get("/api/v1/leads").json()
    assert [lead["id"] for lead in remaining_leads] == [shared_lead["id"]]
    assert remaining_leads[0]["campaign_ids"] == [other_campaign["id"]]
    assert all(lead["id"] != exclusive_lead["id"] for lead in remaining_leads)

    with app.state.database.session_factory() as session:
        assert session.get(OutreachBatch, batch.id) is None
        audit_actions = list(
            session.scalars(
                select(AuditEvent.action).where(
                    AuditEvent.correlation_id == response.headers["X-Correlation-ID"]
                )
            )
        )
    assert audit_actions.count("lead.deleted") == 1
    assert audit_actions.count("campaign.deleted") == 1


def test_campaign_delete_is_blocked_while_a_run_is_active(
    client: TestClient,
    app: FastAPI,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    with app.state.database.session_factory() as session:
        session.add(CampaignRun(campaign_id=campaign["id"], status="running"))
        session.commit()

    response = client.delete(f"/api/v1/campaigns/{campaign['id']}")

    assert response.status_code == 409
    assert response.json()["code"] == "CAMPAIGN_DELETE_RUN_ACTIVE"
    assert client.get(f"/api/v1/campaigns/{campaign['id']}").status_code == 200


def test_campaign_archive_is_blocked_while_a_run_is_active(
    client: TestClient,
    app: FastAPI,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    with app.state.database.session_factory() as session:
        session.add(CampaignRun(campaign_id=campaign["id"], status="queued"))
        session.commit()

    response = client.patch(f"/api/v1/campaigns/{campaign['id']}", json={"status": "inactive"})

    assert response.status_code == 409
    assert response.json()["code"] == "CAMPAIGN_ARCHIVE_RUN_ACTIVE"
    campaign_response = client.get(f"/api/v1/campaigns/{campaign['id']}")
    assert campaign_response.json()["status"] == "active"
