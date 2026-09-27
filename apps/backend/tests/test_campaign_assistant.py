from __future__ import annotations

import json
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.campaign_assistant.monitor import ProtectedApplicationMonitor
from app.domains.campaign_assistant.ollama import (
    OLLAMA_CAMPAIGN_PROPOSAL_SCHEMA,
    OllamaResult,
)
from app.domains.campaign_assistant.schemas import (
    CampaignDraftProposal,
    OllamaGenerationMetrics,
    ResourceProfile,
)


class FakeOllamaStatus:
    preferred_model = ""

    def status(self) -> tuple[bool, set[str], set[str]]:
        return True, {"llama3.2:3b"}, set()

    def model_for(self, profile: ResourceProfile) -> str:
        return "llama3.2:3b"


class FakeCampaignAssistantManager:
    def __init__(self, proposals: list[dict[str, Any]]) -> None:
        self.ollama = FakeOllamaStatus()
        self.active_applications: set[str] = set()
        self.proposals = [CampaignDraftProposal.model_validate(item) for item in proposals]
        self.messages: list[list[dict[str, str]]] = []

    def resource_profile(self, protect_resources: bool = True) -> ResourceProfile:
        if protect_resources and self.active_applications:
            return ResourceProfile.DESIGN_SOFTWARE
        return ResourceProfile.STANDARD

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        protect_resources: bool,
    ) -> tuple[OllamaResult, ResourceProfile]:
        self.messages.append(messages)
        return (
            OllamaResult(
                proposal=self.proposals.pop(0),
                metrics=OllamaGenerationMetrics(
                    model="llama3.2:3b",
                    total_duration_ms=125,
                    prompt_eval_count=400,
                    eval_count=180,
                ),
            ),
            self.resource_profile(protect_resources),
        )


class FakeRuntimeOllama:
    def __init__(self) -> None:
        self.unload_count = 0

    def unload(self) -> None:
        self.unload_count += 1


class FakeMonitor:
    def start(self) -> None:
        return

    def stop(self) -> None:
        return


def ready_proposal(*, radius_miles: float = 25) -> dict[str, Any]:
    return {
        "outcome": "draft_ready",
        "assistant_message": "I prepared an optimised Luton bakery campaign for your review.",
        "assumptions": ["The audience is independent bakeries and cake makers."],
        "warnings": [],
        "questions": [],
        "campaign": {
            "name": "Luton Bakery Partnerships",
            "description": "Local bakery partnership campaign",
            "segment": "Independent bakeries and cake makers",
            "primary_location": "Luton, United Kingdom",
            "radius_miles": radius_miles,
            "keywords": ["bakery", "cake maker"],
            "exclusion_keywords": ["supermarket", "closed"],
            "product_categories": [],
            "discovery_sources": ["manual"],
            "weekly_shortlist_size": 5,
            "minimum_score_threshold": 50,
            "preferred_channels": ["email"],
            "offer_settings": {"digital_mock_up": True},
            "discovery_mode": "manual",
            "status": "active",
        },
    }


def install_fake_manager(
    app: FastAPI, proposals: list[dict[str, Any]]
) -> FakeCampaignAssistantManager:
    manager = FakeCampaignAssistantManager(proposals)
    app.state.campaign_assistant_manager = manager
    return manager


def test_assistant_generates_a_reviewable_draft_and_only_approval_creates_campaign(
    client: TestClient, app: FastAPI
) -> None:
    install_fake_manager(app, [ready_proposal()])

    status = client.get("/api/v1/campaign-assistant/status")
    assert status.status_code == 200
    assert status.json()["ready"] is True

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a baking campaign for Luton"},
    )
    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "ready"
    assert draft["campaign"]["status"] == "paused"
    assert draft["campaign"]["weekly_outreach_enabled"] is False
    assert client.get("/api/v1/campaigns").json() == []

    approval = client.post(
        f"/api/v1/campaign-assistant/drafts/{draft['id']}/approve",
        json={"expected_version": draft["version"]},
    )
    assert approval.status_code == 200
    approved = approval.json()
    assert approved["draft"]["status"] == "approved"
    assert approved["campaign"]["status"] == "paused"
    assert len(client.get("/api/v1/campaigns").json()) == 1

    repeated = client.post(
        f"/api/v1/campaign-assistant/drafts/{draft['id']}/approve",
        json={"expected_version": draft["version"]},
    )
    assert repeated.status_code == 200
    assert repeated.json()["campaign"]["id"] == approved["campaign"]["id"]
    assert len(client.get("/api/v1/campaigns").json()) == 1


def test_material_playbook_override_requires_confirmation_before_generation(
    client: TestClient, app: FastAPI
) -> None:
    override_proposal = {
        "outcome": "confirmation_required",
        "assistant_message": "That radius overrides the local campaign recommendation.",
        "questions": [],
        "assumptions": [],
        "warnings": ["A wider radius may reduce local relevance."],
        "override_request": {
            "summary": "Use a 100-mile radius instead of the 25-mile workspace default.",
            "items": [
                {
                    "rule_id": "local-radius",
                    "field": "radius_miles",
                    "playbook_recommendation": 25,
                    "requested_value": 100,
                    "impact": "This increases prospect volume but weakens local relevance.",
                }
            ],
        },
    }
    manager = install_fake_manager(app, [override_proposal, ready_proposal(radius_miles=25)])

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a Luton bakery campaign with a 100 mile radius"},
    )
    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "awaiting_override_confirmation"
    assert draft["campaign"] is None
    pending_override = draft["overrides"][0]
    assert pending_override["status"] == "pending"

    blocked_approval = client.post(
        f"/api/v1/campaign-assistant/drafts/{draft['id']}/approve",
        json={"expected_version": draft["version"]},
    )
    assert blocked_approval.status_code == 409

    decision = client.post(
        (
            f"/api/v1/campaign-assistant/drafts/{draft['id']}/overrides/"
            f"{pending_override['id']}/decision"
        ),
        json={"expected_version": draft["version"], "decision": "confirm"},
    )
    assert decision.status_code == 200
    confirmed = decision.json()
    assert confirmed["status"] == "ready"
    assert confirmed["campaign"]["radius_miles"] == 100
    assert confirmed["overrides"][0]["status"] == "confirmed"
    assert "confirmed_overrides" in manager.messages[-1][1]["content"]
    assert '"decision": "confirmed"' in manager.messages[-1][1]["content"]
    assert (
        "Create a Luton bakery campaign with a 100 mile radius"
        in manager.messages[-1][1]["content"]
    )


def test_playbook_gate_catches_a_radius_override_missed_by_the_local_model(
    client: TestClient, app: FastAPI
) -> None:
    install_fake_manager(app, [ready_proposal(radius_miles=100)])

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a Luton bakery campaign with a 100 mile radius"},
    )

    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "awaiting_override_confirmation"
    assert draft["campaign"] is None
    items = draft["overrides"][0]["items"]
    assert len(items) == 1
    assert items[0]["rule_id"] == "local-radius"
    assert items[0]["requested_value"] == 100


def test_model_cannot_invent_a_radius_when_the_user_omits_it(
    client: TestClient, app: FastAPI
) -> None:
    install_fake_manager(app, [ready_proposal(radius_miles=100)])

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a baking campaign for Luton"},
    )

    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "ready"
    assert draft["campaign"]["radius_miles"] == 25
    assert draft["overrides"] == []


def test_hard_playbook_constraint_cannot_be_confirmed(client: TestClient, app: FastAPI) -> None:
    install_fake_manager(
        app,
        [
            {
                "outcome": "confirmation_required",
                "assistant_message": "Please confirm automatic activation.",
                "questions": [],
                "assumptions": [],
                "warnings": [],
                "override_request": {
                    "summary": "Activate the campaign automatically.",
                    "items": [
                        {
                            "rule_id": "paused-review-boundary",
                            "field": "status",
                            "playbook_recommendation": "paused",
                            "requested_value": "active",
                            "impact": "This would bypass the approval boundary.",
                        }
                    ],
                },
            }
        ],
    )

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create and immediately activate a campaign"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "CAMPAIGN_ASSISTANT_OVERRIDE_FORBIDDEN"
    drafts = client.get(
        "/api/v1/campaign-assistant/drafts", params={"status": "generation_failed"}
    ).json()
    assert len(drafts) == 1


def test_clarification_required_outcome_awaits_operator_input(
    client: TestClient, app: FastAPI
) -> None:
    install_fake_manager(
        app,
        [
            {
                "outcome": "clarification_required",
                "assistant_message": "I need a location or audience to plan this campaign.",
                "questions": ["Which town or city should this campaign target?"],
                "assumptions": [],
                "warnings": [],
            }
        ],
    )

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a campaign"},
    )
    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "awaiting_input"
    assert draft["campaign"] is None
    assert draft["questions"] == ["Which town or city should this campaign target?"]
    assert draft["overrides"] == []


def test_override_not_allowed_outcome_awaits_operator_input(
    client: TestClient, app: FastAPI
) -> None:
    install_fake_manager(
        app,
        [
            {
                "outcome": "override_not_allowed",
                "assistant_message": (
                    "I cannot create an active campaign directly. I can prepare a paused "
                    "draft for your review instead."
                ),
                "questions": [],
                "assumptions": [],
                "warnings": [],
            }
        ],
    )

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create and activate a campaign immediately, skip review"},
    )
    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "awaiting_input"
    assert draft["campaign"] is None
    assert "paused draft" in draft["assistant_message"]


def test_partial_override_confirmation_applies_only_confirmed_items(
    client: TestClient, app: FastAPI
) -> None:
    override_proposal = {
        "outcome": "confirmation_required",
        "assistant_message": "Two settings depart from the playbook.",
        "questions": [],
        "assumptions": [],
        "warnings": [],
        "override_request": {
            "summary": "Confirm the radius and shortlist size changes.",
            "items": [
                {
                    "rule_id": "local-radius",
                    "field": "radius_miles",
                    "playbook_recommendation": 25,
                    "requested_value": 100,
                    "impact": "Wider radius, less local relevance.",
                },
                {
                    "rule_id": "conservative-shortlist",
                    "field": "weekly_shortlist_size/minimum_score_threshold",
                    "playbook_recommendation": {
                        "weekly_shortlist_size": 5,
                        "minimum_score_threshold": 50,
                    },
                    "requested_value": {
                        "weekly_shortlist_size": 20,
                        "minimum_score_threshold": 10,
                    },
                    "impact": "Higher volume, lower quality bar.",
                },
            ],
        },
    }
    install_fake_manager(app, [override_proposal, ready_proposal(radius_miles=25)])

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Wider radius and a bigger weekly shortlist please"},
    )
    draft = response.json()
    pending_override = draft["overrides"][0]
    radius_item_id = next(
        item["item_id"]
        for item in pending_override["items"]
        if item["rule_id"] == "local-radius"
    )

    decision = client.post(
        (
            f"/api/v1/campaign-assistant/drafts/{draft['id']}/overrides/"
            f"{pending_override['id']}/decision"
        ),
        json={
            "expected_version": draft["version"],
            "decision": "partial",
            "confirmed_item_ids": [radius_item_id],
        },
    )
    assert decision.status_code == 200
    confirmed = decision.json()
    assert confirmed["status"] == "ready"
    assert confirmed["campaign"]["radius_miles"] == 100
    override_after = confirmed["overrides"][0]
    assert override_after["status"] == "partially_confirmed"
    decisions = {item["rule_id"]: item["decision"] for item in override_after["items"]}
    assert decisions["local-radius"] == "confirmed"
    assert decisions["conservative-shortlist"] == "rejected"


def test_rejected_override_keeps_the_playbook_recommendation(
    client: TestClient, app: FastAPI
) -> None:
    override_proposal = {
        "outcome": "confirmation_required",
        "assistant_message": "That radius overrides the local campaign recommendation.",
        "questions": [],
        "assumptions": [],
        "warnings": [],
        "override_request": {
            "summary": "Use a 100-mile radius instead of the 25-mile workspace default.",
            "items": [
                {
                    "rule_id": "local-radius",
                    "field": "radius_miles",
                    "playbook_recommendation": 25,
                    "requested_value": 100,
                    "impact": "Wider radius, less local relevance.",
                }
            ],
        },
    }
    install_fake_manager(app, [override_proposal, ready_proposal(radius_miles=25)])

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a Luton bakery campaign with a 100 mile radius"},
    )
    draft = response.json()
    pending_override = draft["overrides"][0]

    decision = client.post(
        (
            f"/api/v1/campaign-assistant/drafts/{draft['id']}/overrides/"
            f"{pending_override['id']}/decision"
        ),
        json={"expected_version": draft["version"], "decision": "reject"},
    )
    assert decision.status_code == 200
    rejected = decision.json()
    assert rejected["status"] == "ready"
    assert rejected["campaign"]["radius_miles"] == 25
    assert rejected["overrides"][0]["status"] == "rejected"


def test_stale_draft_version_is_rejected_with_conflict(
    client: TestClient, app: FastAPI
) -> None:
    install_fake_manager(app, [ready_proposal(), ready_proposal(radius_miles=10)])

    draft = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a baking campaign for Luton"},
    ).json()

    stale = client.post(
        f"/api/v1/campaign-assistant/drafts/{draft['id']}/messages",
        json={"message": "Make it 10 miles", "expected_version": draft["version"] + 1},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "CAMPAIGN_DRAFT_VERSION_CONFLICT"


def test_discard_closes_a_non_approved_draft(client: TestClient, app: FastAPI) -> None:
    install_fake_manager(app, [ready_proposal()])
    draft = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a baking campaign for Luton"},
    ).json()

    discarded = client.post(
        f"/api/v1/campaign-assistant/drafts/{draft['id']}/discard",
        json={"expected_version": draft["version"]},
    )
    assert discarded.status_code == 200
    assert discarded.json()["status"] == "discarded"

    blocked_approval = client.post(
        f"/api/v1/campaign-assistant/drafts/{draft['id']}/approve",
        json={"expected_version": draft["version"]},
    )
    assert blocked_approval.status_code == 409
    assert client.get("/api/v1/campaigns").json() == []


def test_manual_edit_updates_a_ready_draft_and_forbids_protected_fields(
    client: TestClient, app: FastAPI
) -> None:
    install_fake_manager(app, [ready_proposal()])
    draft = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a baking campaign for Luton"},
    ).json()

    edited = client.patch(
        f"/api/v1/campaign-assistant/drafts/{draft['id']}",
        json={"expected_version": draft["version"], "changes": {"radius_miles": 15}},
    )
    assert edited.status_code == 200
    edited_draft = edited.json()
    assert edited_draft["campaign"]["radius_miles"] == 15
    assert edited_draft["version"] == draft["version"] + 1

    forbidden = client.patch(
        f"/api/v1/campaign-assistant/drafts/{draft['id']}",
        json={
            "expected_version": edited_draft["version"],
            "changes": {"status": "active"},
        },
    )
    assert forbidden.status_code == 400
    assert forbidden.json()["code"] == "CAMPAIGN_DRAFT_PROTECTED_FIELD"


def test_unavailable_discovery_source_is_removed_with_a_visible_warning(
    client: TestClient, app: FastAPI
) -> None:
    proposal = ready_proposal()
    proposal["campaign"]["discovery_sources"] = ["manual", "google_places"]
    install_fake_manager(app, [proposal])

    response = client.post(
        "/api/v1/campaign-assistant/drafts",
        json={"message": "Create a baking campaign for Luton using Google Places"},
    )
    assert response.status_code == 201
    draft = response.json()
    assert "google_places" not in draft["campaign"]["discovery_sources"]
    assert any("Unavailable discovery sources" in warning for warning in draft["warnings"])


def test_protected_application_monitor_uses_exact_process_names() -> None:
    changes: list[set[str]] = []
    processes = ["LightBurn.exe", "not-xcs.exe"]
    monitor = ProtectedApplicationMonitor(
        ("lightburn.exe", "xcs.exe"),
        poll_seconds=10,
        callback=changes.append,
        process_supplier=lambda: processes,
    )

    assert monitor.check_now() == {"LightBurn"}
    assert changes == [{"LightBurn"}]

    processes[:] = ["xcs.exe"]
    assert monitor.check_now() == {"xTool Creative Space"}
    assert changes[-1] == {"xTool Creative Space"}


def test_model_is_restricted_only_while_protected_applications_are_active(
    settings: Settings,
) -> None:
    ollama = FakeRuntimeOllama()
    manager = CampaignAssistantManager(
        settings,
        ollama_client=cast(Any, ollama),
        monitor=cast(Any, FakeMonitor()),
    )

    assert manager.resource_profile(True) == ResourceProfile.STANDARD
    manager._protected_apps_changed({"LightBurn"})
    assert manager.resource_profile(True) == ResourceProfile.DESIGN_SOFTWARE
    assert ollama.unload_count == 1

    manager.set_protection_enabled(False)
    manager._protected_apps_changed({"xTool Creative Space"})
    assert manager.resource_profile(False) == ResourceProfile.STANDARD
    assert ollama.unload_count == 1

    manager._protected_apps_changed(set())
    manager.set_protection_enabled(True)
    assert manager.resource_profile(True) == ResourceProfile.STANDARD


def test_ollama_schema_keeps_each_outcome_unambiguous_and_grammar_compatible() -> None:
    encoded = json.dumps(OLLAMA_CAMPAIGN_PROPOSAL_SCHEMA)

    assert '"$defs"' not in encoded
    assert '"maxLength"' not in encoded
    outcomes = {
        variant["properties"]["outcome"]["const"]
        for variant in OLLAMA_CAMPAIGN_PROPOSAL_SCHEMA["oneOf"]
    }
    assert outcomes == {
        "draft_ready",
        "clarification_required",
        "confirmation_required",
        "override_not_allowed",
    }
