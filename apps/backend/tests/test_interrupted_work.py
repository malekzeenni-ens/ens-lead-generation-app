"""Work interrupted by a failure or a closed app never leaves a record stuck in progress."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.models import Campaign, CampaignDraft, CampaignRun, ProviderAttempt
from app.domains.campaign_assistant.schemas import ResourceProfile
from tests.test_campaign_assistant import install_fake_manager, ready_proposal


class _ExplodingManager:
    """Fails the first generation with an unexpected error, then behaves normally."""

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.ollama = delegate.ollama
        self.active_applications = delegate.active_applications
        self.failures_left = 1

    def resource_profile(self, protect_resources: bool = True) -> ResourceProfile:
        return ResourceProfile(self.delegate.resource_profile(protect_resources))

    def generate(self, messages: list[dict[str, str]], *, protect_resources: bool) -> Any:
        if self.failures_left:
            self.failures_left -= 1
            raise RuntimeError("simulated crash inside generation")
        return self.delegate.generate(messages, protect_resources=protect_resources)


def test_an_unexpected_generation_error_leaves_the_draft_editable(
    client: TestClient, app: FastAPI
) -> None:
    manager = _ExplodingManager(install_fake_manager(app, [ready_proposal()]))
    app.state.campaign_assistant_manager = manager

    with pytest.raises(RuntimeError, match="simulated crash"):
        client.post(
            "/api/v1/campaign-assistant/drafts", json={"message": "Create a Luton campaign"}
        )

    drafts = client.get("/api/v1/campaign-assistant/drafts").json()
    assert [draft["status"] for draft in drafts] == ["generation_failed"]
    retried = client.post(
        f"/api/v1/campaign-assistant/drafts/{drafts[0]['id']}/messages",
        json={"message": "Try again", "expected_version": drafts[0]["version"]},
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "ready"


def test_startup_recovers_drafts_and_provider_attempts_left_in_progress(app: FastAPI) -> None:
    database = app.state.database
    with database.session_factory() as session:
        campaign = Campaign(
            name="Interrupted campaign",
            segment="Bakeries",
            primary_location="Luton",
            radius_miles=10,
            weekly_shortlist_size=5,
            minimum_score_threshold=0,
        )
        session.add(campaign)
        session.flush()
        run = CampaignRun(campaign_id=campaign.id, status="completed", phase="completed")
        session.add(run)
        session.flush()
        session.add(ProviderAttempt(run_id=run.id, provider="google_places", query="bakery"))
        session.add(
            CampaignDraft(
                status="generating",
                original_request="Create a campaign",
                model_name="llama3.2:3b",
                prompt_version="test",
                resource_profile="standard",
            )
        )
        session.commit()

    # Read inside the app's lifetime: its shutdown disposes the engine.
    with TestClient(app), database.session_factory() as session:
        draft = session.query(CampaignDraft).one()
        attempt = session.query(ProviderAttempt).one()
    assert draft.status == "generation_failed"
    assert attempt.status == "interrupted"
    assert attempt.error_code == "PROCESS_INTERRUPTED"
    assert attempt.completed_at is not None
