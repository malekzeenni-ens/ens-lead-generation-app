"""A failed campaign run keeps committed work and nothing half-written (R6)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import Lead
from app.domains.automation.service import CampaignAutomationService
from tests.test_lead_matching import _Provider, _run
from tests.test_suppression_identifiers import _business


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (DomainError("EVIDENCE_REJECTED", "Simulated domain failure."), "EVIDENCE_REJECTED"),
        (RuntimeError("simulated crash"), "CAMPAIGN_RUN_FAILED"),
    ],
)
def test_a_failure_mid_promotion_leaves_no_partial_lead(
    client: TestClient,
    app: FastAPI,
    settings: Settings,
    campaign_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    code: str,
) -> None:
    campaign = client.post(
        "/api/v1/campaigns", json={**campaign_payload, "discovery_sources": ["google_places"]}
    ).json()

    def fail_after_the_lead_is_added(*_: Any) -> None:
        raise failure

    # Runs after the new lead and its campaign link are added to the session.
    monkeypatch.setattr(CampaignAutomationService, "_attach_evidence", fail_after_the_lead_is_added)
    run_id = _run(
        app, settings, campaign["id"], _Provider(_business("new", "Fresh Bakery", "Luton, UK"))
    )

    run = client.get(f"/api/v1/campaign-runs/{run_id}").json()
    assert run["status"] == "failed"
    assert run["error_code"] == code
    assert [attempt["status"] for attempt in run["attempts"]] == ["failed"]
    assert run["attempts"][0]["error_code"] == code
    with app.state.database.session_factory() as session:
        assert session.query(Lead).count() == 0
