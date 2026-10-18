"""The lead register is paged and filtered on the server (R10)."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.db.models import Campaign, Lead, LeadCampaign, SourceObservation, SourceSystem
from tests.conftest import lead_payload


def _create(client: TestClient, campaign_id: str, name: str, **fields: object) -> dict[str, Any]:
    payload = {
        **lead_payload(campaign_id),
        "business_name": name,
        "website": f"https://{name.casefold().replace(' ', '-')}.test",
        **fields,
    }
    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def _page(client: TestClient, **params: object) -> dict[str, Any]:
    response = client.get("/api/v1/leads/page", params=params)
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def test_pages_are_newest_first_with_totals(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    for name in ("Alpha Cakes", "Beta Bakes", "Gamma Bread"):
        _create(client, campaign["id"], name)

    first = _page(client, limit=2)
    second = _page(client, limit=2, offset=2)

    assert first["total"] == second["total"] == 3
    assert [item["business_name"] for item in first["items"]] == ["Gamma Bread", "Beta Bakes"]
    assert [item["business_name"] for item in second["items"]] == ["Alpha Cakes"]
    assert first["limit"] == 2 and second["offset"] == 2


def test_items_carry_what_the_register_shows(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    lead = _create(
        client,
        campaign["id"],
        "Alpha Cakes",
        contact_first_name="Amira",
        phone_number="01582 000001",
    )
    soon = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()
    later = (datetime.now(UTC).date() + timedelta(days=9)).isoformat()
    for due in (later, soon):
        created = client.post(
            f"/api/v1/leads/{lead['id']}/follow-ups",
            json={"follow_up_type": "email", "due_date": due},
        )
        assert created.status_code == 201, created.text

    (item,) = _page(client)["items"]

    assert item["campaign_ids"] == [campaign["id"]]
    assert item["source_types"] == ["manual"]
    assert item["next_follow_up_due"] == soon
    assert item["contact_first_name"] == "Amira"
    assert item["phone_number"] == "01582 000001"
    assert "observations" not in item and "outreach_activities" not in item


def test_every_filter_matches_the_register(
    client: TestClient, app: FastAPI, campaign_payload: dict[str, object]
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    other = client.post(
        "/api/v1/campaigns", json={**campaign_payload, "name": "Other campaign"}
    ).json()
    alpha = _create(client, campaign["id"], "Alpha Cakes", contact_email="amira@alpha.test")
    beta = _create(client, other["id"], "Beta Bakes", contact_classification="corporate_subscriber")
    gamma = _create(client, campaign["id"], "Gamma Bread")
    assert (
        client.post(f"/api/v1/leads/{beta['id']}/stage", json={"stage": "qualified"}).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/leads/{gamma['id']}/suppression",
            json={"suppression_type": "unsubscribe", "reason": "Asked", "source": "Email"},
        ).status_code
        == 201
    )
    # A lead whose only evidence is a website observation has no named source.
    with app.state.database.session_factory() as session:
        session.query(SourceObservation).filter_by(lead_id=alpha["id"]).delete()
        session.commit()

    def names(**params: object) -> list[str]:
        return sorted(item["business_name"] for item in _page(client, **params)["items"])

    assert names(query="AMIRA@alpha") == ["Alpha Cakes"]
    assert names(stage="qualified") == ["Beta Bakes"]
    assert names(suppressed=True) == ["Gamma Bread"]
    assert names(suppressed=False) == ["Alpha Cakes", "Beta Bakes"]
    assert names(campaign_id=other["id"]) == ["Beta Bakes"]
    assert names(needs_review=True) == ["Alpha Cakes", "Gamma Bread"]
    assert names(needs_review=False) == ["Beta Bakes"]
    assert names(source_type="Manual") == ["Beta Bakes", "Gamma Bread"]
    assert names(source_type="unknown") == ["Alpha Cakes"]
    assert _page(client, source_type="unknown")["items"][0]["source_types"] == ["unknown"]
    assert client.get("/api/v1/leads/source-types").json() == ["manual"]


def test_five_thousand_leads_page_quickly(client: TestClient, app: FastAPI) -> None:
    campaign_id = str(uuid4())
    now = datetime.now(UTC)
    with app.state.database.session_factory() as session:
        session.execute(
            insert(Campaign),
            [
                {
                    "id": campaign_id,
                    "name": "Volume",
                    "segment": "Bakeries",
                    "primary_location": "Luton",
                    "radius_miles": 10,
                    "keywords": [],
                    "exclusion_keywords": [],
                    "product_categories": [],
                    "discovery_sources": [],
                    "weekly_shortlist_size": 5,
                    "minimum_score_threshold": 0,
                    "preferred_channels": [],
                    "offer_settings": {},
                    "discovery_mode": "manual",
                    "status": "active",
                    "weekly_outreach_enabled": False,
                    "weekly_outreach_provider": "scoring",
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )
        source = SourceSystem(name="Volume source", source_type="google")
        session.add(source)
        session.flush()
        leads = [
            {
                "id": str(uuid4()),
                "business_name": f"Bakery {index:05d}",
                "normalized_name": f"bakery {index:05d}",
                "segment": "Bakeries",
                "location": "Luton",
                "contact_classification": "unknown",
                "pipeline_stage": "new",
                "suppressed": False,
                "mock_up_status": "not_offered",
                "sample_status": "not_applicable",
                "quote_status": "not_requested",
                "created_at": now - timedelta(seconds=index),
                "updated_at": now,
            }
            for index in range(5_000)
        ]
        session.execute(insert(Lead), leads)
        session.execute(
            insert(LeadCampaign),
            [{"lead_id": lead["id"], "campaign_id": campaign_id} for lead in leads],
        )
        session.execute(
            insert(SourceObservation),
            [
                {
                    "id": str(uuid4()),
                    "lead_id": lead["id"],
                    "source_system_id": source.id,
                    "field_name": "business_identity",
                    "observed_value": lead["business_name"],
                    "classification": "provider_observed",
                    "collection_method": "provider",
                    "collected_at": now,
                }
                for lead in leads
            ],
        )
        session.commit()

    started = time.perf_counter()
    page = _page(client, limit=50)
    elapsed = time.perf_counter() - started
    filtered = _page(client, limit=50, source_type="google", query="Bakery 04")

    assert page["total"] == 5_000
    assert page["items"][0]["business_name"] == "Bakery 00000"
    assert page["items"][0]["source_types"] == ["google"]
    assert filtered["total"] == 1_000
    # Measured about 0.1 s locally; the bound leaves room for a slow CI machine.
    assert elapsed < 1.0, f"first page took {elapsed:.3f} s"
