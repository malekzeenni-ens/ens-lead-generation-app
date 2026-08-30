from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from app.api.routes import lead_assistant as lead_assistant_route
from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import Lead, LeadNote
from app.db.session import Database
from app.domains.automation.enrichment import EnrichmentFailure
from app.domains.campaign_assistant.ollama import OllamaStructuredResult
from app.domains.campaign_assistant.schemas import OllamaGenerationMetrics, ResourceProfile
from app.domains.lead_assistant.prompt import (
    _OLLAMA_AUTOFILL_SCHEMA,
    _OLLAMA_BRIEFING_SCHEMA,
    build_digest_schema,
    build_filter_schema,
)
from app.domains.lead_assistant.schemas import (
    LeadBriefingResponse,
    StalledLeadDigestRequest,
)
from app.domains.lead_assistant.service import LeadAssistantService
from app.domains.lead_assistant.staleness import find_stalled_leads
from app.domains.leads.activity import latest_activity_at
from app.domains.outreach.prompt import _OLLAMA_REFINE_SCHEMA
from app.domains.system.schemas import WorkspaceSettings
from tests.conftest import lead_payload


class FakeStructuredManager:
    def __init__(self, values: list[dict[str, Any]], *, busy: bool = False) -> None:
        self.values = values
        self.busy = busy
        self.calls: list[list[dict[str, str]]] = []

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, object],
        model_cls: type[BaseModel],
        error_prefix: str,
        protect_resources: bool,
    ) -> tuple[OllamaStructuredResult[BaseModel], ResourceProfile]:
        del schema, error_prefix, protect_resources
        self.calls.append(messages)
        if self.busy:
            raise DomainError(
                "CAMPAIGN_ASSISTANT_BUSY",
                "The local assistant is already processing another request.",
                status_code=409,
            )
        value = model_cls.model_validate(self.values.pop(0))
        return (
            OllamaStructuredResult(
                value=value,
                metrics=OllamaGenerationMetrics(model="llama3.2:3b"),
            ),
            ResourceProfile.STANDARD,
        )


class FailingEnricher:
    calls = 0

    def enrich(self, url: str) -> None:
        self.calls += 1
        raise EnrichmentFailure("WEBSITE_FETCH_FAILED", f"Could not fetch {url}")

    def close(self) -> None:
        return


def _campaign(client: TestClient, campaign_payload: dict[str, object]) -> dict[str, Any]:
    response = client.post("/api/v1/campaigns", json=campaign_payload)
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


def _lead(
    client: TestClient,
    campaign_id: str,
    *,
    name: str,
    website: bool = True,
) -> dict[str, Any]:
    payload = lead_payload(campaign_id)
    payload["business_name"] = name
    if website:
        payload["website"] = f"https://{name.casefold().replace(' ', '-')}.test"
        source = cast(dict[str, Any], payload["source"])
        source["source_url"] = payload["website"]
    else:
        payload.pop("website", None)
        payload["instagram_url"] = f"https://instagram.com/{name.casefold().replace(' ', '')}"
        source = cast(dict[str, Any], payload["source"])
        source["source_url"] = payload["instagram_url"]
    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_filter_translation_revalidates_campaign_and_preserves_valid_filters(
    client: TestClient,
    app: FastAPI,
    campaign_payload: dict[str, object],
) -> None:
    campaign = _campaign(client, campaign_payload)
    manager = FakeStructuredManager(
        [
            {
                "stage": "qualified",
                "suppressed": False,
                "campaign_id": campaign["id"],
                "source_type": None,
                "keyword": None,
            },
            {
                "stage": None,
                "suppressed": None,
                "campaign_id": "hallucinated-campaign",
                "source_type": None,
                "keyword": None,
            },
            {
                "stage": None,
                "suppressed": None,
                "campaign_id": None,
                "source_type": None,
                "keyword": "custom wording",
            },
        ]
    )
    app.state.campaign_assistant_manager = manager

    valid = client.post(
        "/api/v1/lead-assistant/search-filter",
        json={"query": "qualified unsuppressed leads in the bakery campaign"},
    )
    assert valid.status_code == 200
    assert valid.json()["stage"] == "qualified"
    assert valid.json()["campaign_id"] == campaign["id"]
    assert valid.json()["suppressed"] is False

    hallucinated = client.post(
        "/api/v1/lead-assistant/search-filter",
        json={"query": "use a campaign that does not exist"},
    )
    assert hallucinated.status_code == 200
    assert hallucinated.json()["campaign_id"] is None

    residual = client.post(
        "/api/v1/lead-assistant/search-filter",
        json={"query": "custom wording"},
    )
    assert residual.status_code == 200
    assert residual.json() == {
        "stage": None,
        "suppressed": None,
        "campaign_id": None,
        "source_type": None,
        "keyword": "custom wording",
    }


def test_briefing_handles_sparse_lead_and_response_bounds(
    client: TestClient,
    app: FastAPI,
    campaign_payload: dict[str, object],
) -> None:
    campaign = _campaign(client, campaign_payload)
    lead = _lead(client, str(campaign["id"]), name="Sparse Cakes")
    manager = FakeStructuredManager(
        [
            {
                "summary": "A new local bakery lead with limited recorded history.",
                "talking_points": ["Ask about current presentation needs."],
                "watch_out_for": None,
            }
        ]
    )
    app.state.campaign_assistant_manager = manager

    response = client.post(f"/api/v1/lead-assistant/leads/{lead['id']}/briefing", json={})
    assert response.status_code == 200
    assert response.json()["talking_points"] == ["Ask about current presentation needs."]
    assert manager.calls

    missing = client.post("/api/v1/lead-assistant/leads/missing/briefing", json={})
    assert missing.status_code == 404

    with pytest.raises(ValidationError):
        LeadBriefingResponse.model_validate(
            {
                "summary": "Too many points",
                "talking_points": ["one", "two", "three", "four"],
                "watch_out_for": None,
            }
        )


def test_autofill_degrades_per_lead_and_busy_aborts_batch(
    client: TestClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    campaign_payload: dict[str, object],
) -> None:
    campaign = _campaign(client, campaign_payload)
    with_site = _lead(client, str(campaign["id"]), name="Website Cakes")
    without_site = _lead(
        client,
        str(campaign["id"]),
        name="Social Cakes",
        website=False,
    )
    enricher = FailingEnricher()
    monkeypatch.setattr(
        lead_assistant_route,
        "SafeWebsiteEnricher",
        lambda _settings: enricher,
    )
    manager = FakeStructuredManager(
        [
            {
                "personalisation_observation": "A bakery in Luton.",
                "relevance_opportunity": "Presentation details may be relevant.",
                "offer_angle": "Offer examples for review.",
                "desired_next_step": "Ask whether examples would help.",
            },
            {
                "personalisation_observation": "A social-first bakery in Luton.",
                "relevance_opportunity": "A location-led introduction is appropriate.",
                "offer_angle": None,
                "desired_next_step": "Ask about current priorities.",
            },
        ]
    )
    app.state.campaign_assistant_manager = manager

    response = client.post(
        "/api/v1/lead-assistant/autofill",
        json={"lead_ids": [with_site["id"], without_site["id"], "missing-lead"]},
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items[0]["suggestion"] is not None
    assert items[1]["suggestion"] is not None
    assert items[2]["skipped_reason"] == "Lead not found."
    assert enricher.calls == 1
    assert len(manager.calls) == 2

    app.state.campaign_assistant_manager = FakeStructuredManager([], busy=True)
    busy = client.post(
        "/api/v1/lead-assistant/autofill",
        json={"lead_ids": [without_site["id"]]},
    )
    assert busy.status_code == 409
    assert busy.json()["code"] == "CAMPAIGN_ASSISTANT_BUSY"


def test_bulk_update_is_all_or_nothing_at_request_validation(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign = _campaign(client, campaign_payload)
    first = _lead(client, str(campaign["id"]), name="First Cakes")
    second = _lead(client, str(campaign["id"]), name="Second Cakes")

    response = client.patch(
        "/api/v1/leads/bulk",
        json={
            "items": [
                {
                    "lead_id": first["id"],
                    "changes": {"offer_angle": "A valid reviewed suggestion."},
                },
                {
                    "lead_id": second["id"],
                    "changes": {"desired_next_step": "x" * 2_001},
                },
            ]
        },
    )
    assert response.status_code == 422
    unchanged = client.get(f"/api/v1/leads/{first['id']}").json()
    assert unchanged["offer_angle"] is None


def test_stalled_selection_is_deterministic_and_excludes_ineligible_leads(
    app: FastAPI,
    client: TestClient,
) -> None:
    del client
    database = cast(Database, app.state.database)
    now = datetime.now(UTC)
    today = date.today()
    with database.session_factory() as session:
        leads = [
            Lead(
                business_name="Expired hold",
                normalized_name="expired hold",
                segment="Bakery",
                location="Luton",
                pipeline_stage="qualified",
                outreach_hold_until=today,
                current_score=90,
            ),
            Lead(
                business_name="Retention review",
                normalized_name="retention review",
                segment="Bakery",
                location="Luton",
                pipeline_stage="researching",
                retention_review_date=today,
                current_score=80,
            ),
            Lead(
                business_name="Suppressed",
                normalized_name="suppressed",
                segment="Bakery",
                location="Luton",
                pipeline_stage="qualified",
                suppressed=True,
            ),
            Lead(
                business_name="Won lead",
                normalized_name="won lead",
                segment="Bakery",
                location="Luton",
                pipeline_stage="won",
            ),
        ]
        session.add_all(leads)
        session.flush()
        session.add_all(
            [
                LeadNote(lead_id=leads[0].id, content="Recent hold note", created_at=now),
                LeadNote(lead_id=leads[1].id, content="Recent retention note", created_at=now),
            ]
        )
        session.commit()

        results = find_stalled_leads(session, stale_after_days=21, limit=25)
        result_names = [lead.business_name for lead, _days in results]
        assert result_names == ["Expired hold", "Retention review"]


def test_digest_skips_ollama_when_empty_and_filters_unknown_ids(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
) -> None:
    del client
    database = cast(Database, app.state.database)
    service = LeadAssistantService()
    manager = FakeStructuredManager([])
    with database.session_factory() as session:
        empty = service.stalled_digest(
            session,
            StalledLeadDigestRequest(),
            manager=cast(Any, manager),
            runtime_settings=settings,
            workspace_settings=WorkspaceSettings(),
        )
        assert empty.items == []
        assert manager.calls == []

        lead = Lead(
            business_name="Stalled Cakes",
            normalized_name="stalled cakes",
            segment="Bakery",
            location="Luton",
            pipeline_stage="qualified",
        )
        session.add(lead)
        session.commit()
        manager.values.append(
            {"items": [{"lead_id": "not-a-candidate", "suggested_action": "Do something"}]}
        )
        digest = service.stalled_digest(
            session,
            StalledLeadDigestRequest(limit=1),
            manager=cast(Any, manager),
            runtime_settings=settings,
            workspace_settings=WorkspaceSettings(),
        )
        assert digest.items == []
        assert len(manager.calls) == 1


def test_digest_limit_above_twenty_five_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/lead-assistant/stalled-digest", json={"limit": 26})
    assert response.status_code == 422


def test_old_activity_is_stale() -> None:
    lead = Lead(
        business_name="Old lead",
        normalized_name="old lead",
        segment="Bakery",
        location="Luton",
        pipeline_stage="qualified",
    )
    occurred_at = datetime.now(UTC) - timedelta(days=22)
    lead.notes = [
        LeadNote(
            lead_id=lead.id,
            content="Old note",
            created_at=occurred_at,
        )
    ]
    assert latest_activity_at(lead) == occurred_at


def test_new_ollama_schemas_remain_inline_and_grammar_compatible() -> None:
    schemas = [
        _OLLAMA_REFINE_SCHEMA,
        _OLLAMA_BRIEFING_SCHEMA,
        _OLLAMA_AUTOFILL_SCHEMA,
        build_filter_schema(["qualified"], ["manual"]),
        build_digest_schema(["known-lead"]),
    ]
    for schema in schemas:
        encoded = json.dumps(schema)
        assert '"$defs"' not in encoded
        assert '"maxLength"' not in encoded
