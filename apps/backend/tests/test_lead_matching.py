"""Duplicate matching ranks identifiers and respects location (FR-015, decision D1)."""

from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.db.models import Campaign
from app.domains.automation.enrichment import SafeWebsiteEnricher
from app.domains.automation.providers import DiscoveryBatch, GooglePlacesProvider
from app.domains.automation.schemas import CampaignRunProvider
from app.domains.automation.service import CampaignAutomationService
from app.domains.leads.matching import (
    NAME_ONLY_REVIEW_REASON,
    MatchKind,
    MatchRank,
    locality,
    match,
    match_keys,
    same_locality,
)
from tests.conftest import lead_payload
from tests.test_suppression_identifiers import _business, _OfflineEnricher


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("Luton", "Luton, United Kingdom", True),
        ("Leeds", "12 High Street, Leeds LS1 1AA, UK", True),
        ("Camden, London NW1 8AB", "London", True),
        ("Leeds LS1 1AA", "Wellington Street, Leeds LS1 4DL", True),
        ("Leeds LS1 1AA", "Leeds LS2 7EW", False),
        ("Luton", "Leeds", False),
        ("Luton", "", False),
        ("", "", False),
    ],
)
def test_locality_comparison(first: str, second: str, expected: bool) -> None:
    assert same_locality(locality(first), locality(second)) is expected


def test_locality_extracts_the_postcode_district_and_ignores_numbers() -> None:
    parsed = locality("Unit 4, 12 High Street, Leeds ls1 1aa, United Kingdom")
    assert parsed.outward_code == "LS1"
    assert parsed.tokens == frozenset({"unit", "high", "street", "leeds"})


def _keys(name: str, location: str = "Luton", **fields: Any) -> Any:
    return match_keys(business_name=name, location=location, **fields)


@pytest.mark.parametrize(
    ("candidate", "lead", "rank", "kind"),
    [
        (
            _keys("A", social=[("instagram", "crown")]),
            _keys("B", social=[("instagram", "crown")]),
            MatchRank.SOCIAL,
            MatchKind.EXACT,
        ),
        (
            _keys("A", website="https://www.crown.test/x"),
            _keys("B", website="http://crown.test"),
            MatchRank.WEBSITE,
            MatchKind.EXACT,
        ),
        (
            _keys("A", phone="+44 1582 000 001"),
            _keys("B", phone="01582 000001"),
            MatchRank.PHONE,
            MatchKind.EXACT,
        ),
        (
            _keys("A", emails=["Hello@Crown.test"]),
            _keys("B", emails=[None, "hello@crown.test"]),
            MatchRank.EMAIL,
            MatchKind.EXACT,
        ),
        (
            _keys("The Crown", "Luton, United Kingdom"),
            _keys("The Crown", "Luton"),
            MatchRank.NAME_AND_LOCALITY,
            MatchKind.EXACT,
        ),
        (_keys("The Crown", "Leeds"), _keys("The Crown", "Luton"), MatchRank.NAME_ONLY, None),
        (_keys("The Crown", ""), _keys("The Crown", "Luton"), MatchRank.NAME_ONLY, None),
        (
            _keys("Example Celebration Cake"),
            _keys("Example Celebration Cakes"),
            MatchRank.FUZZY_NAME,
            MatchKind.REVIEW,
        ),
    ],
)
def test_each_rank(candidate: Any, lead: Any, rank: MatchRank, kind: MatchKind | None) -> None:
    result = match(candidate, [("lead", lead)])
    assert result.rank is rank
    assert result.lead_id == "lead"
    if rank is MatchRank.NAME_ONLY:
        assert result.kind is MatchKind.REVIEW
        assert result.reason == NAME_ONLY_REVIEW_REASON
    else:
        assert result.kind is kind


def test_short_phone_fragments_and_unrelated_names_do_not_match() -> None:
    assert (
        match(_keys("Alpha", phone="1234"), [("lead", _keys("Beta", phone="001234"))]).kind
        is MatchKind.NONE
    )
    assert match(_keys("Alpha Cakes"), [("lead", _keys("Harbour Cafe"))]).kind is MatchKind.NONE


def test_the_strongest_identifier_wins_across_leads() -> None:
    candidate = _keys("The Crown", "Luton", phone="01582 000001")
    leads = [
        ("same-name", _keys("The Crown", "Luton")),
        ("same-phone", _keys("Crown Bakehouse", "Dunstable", phone="+44 1582 000001")),
    ]
    result = match(candidate, leads)
    assert result.lead_id == "same-phone"
    assert result.rank is MatchRank.PHONE


def test_a_tie_goes_to_the_first_and_newest_lead() -> None:
    candidate = _keys("Crown", website="https://crown.test")
    leads = [("newer", _keys("X", website="https://crown.test")), ("older", _keys("Y"))]
    assert match(candidate, leads).lead_id == "newer"


class _Provider:
    def __init__(self, *businesses: Any) -> None:
        self.businesses = list(businesses)

    def discover(self, campaign: Campaign) -> DiscoveryBatch:
        return DiscoveryBatch(businesses=self.businesses, queries=["test"], request_count=1)


def _run(app: FastAPI, settings: Settings, campaign_id: str, provider: _Provider) -> str:
    service = CampaignAutomationService(
        settings.model_copy(update={"google_places_api_key": SecretStr("test-api-key")}),
        provider=cast(GooglePlacesProvider, provider),
        enricher=cast(SafeWebsiteEnricher, _OfflineEnricher()),
    )
    with app.state.database.session_factory() as session:
        run_id = service.queue(
            session,
            campaign_id,
            requested_provider=CampaignRunProvider.GOOGLE_PLACES,
            correlation_id="matching-test",
        )
    with app.state.database.session_factory() as session:
        service.execute(session, run_id, "matching-test")
    return run_id


def _campaign_with_leads(
    client: TestClient, campaign_payload: dict[str, object], *leads: dict[str, object]
) -> dict[str, Any]:
    campaign = cast(
        dict[str, Any],
        client.post(
            "/api/v1/campaigns",
            json={**campaign_payload, "discovery_sources": ["google_places"]},
        ).json(),
    )
    for fields in leads:
        created = client.post("/api/v1/leads", json={**lead_payload(campaign["id"]), **fields})
        assert created.status_code == 201, created.text
    return campaign


def test_same_name_in_another_town_goes_to_review_instead_of_linking(
    client: TestClient, app: FastAPI, settings: Settings, campaign_payload: dict[str, object]
) -> None:
    campaign = _campaign_with_leads(
        client,
        campaign_payload,
        {"business_name": "The Crown", "location": "Luton", "website": "https://crown-luton.test"},
    )
    run_id = _run(
        app,
        settings,
        campaign["id"],
        _Provider(_business("leeds-crown", "The Crown", "12 Briggate, Leeds LS1 6HD, UK")),
    )

    candidate = client.get(f"/api/v1/campaign-runs/{run_id}").json()["candidates"][0]
    assert candidate["status"] == "review_required"
    assert candidate["review_reason"] == NAME_ONLY_REVIEW_REASON
    assert candidate["matched_lead_id"] is not None
    assert len(client.get("/api/v1/leads").json()) == 1

    promoted = client.post(
        f"/api/v1/discovery-candidates/{candidate['id']}/decision",
        json={"action": "promote", "reason": "A different pub"},
    )
    assert promoted.status_code == 200, promoted.text
    assert len(client.get("/api/v1/leads").json()) == 2


def test_a_phone_match_beats_a_name_match_on_another_lead(
    client: TestClient, app: FastAPI, settings: Settings, campaign_payload: dict[str, object]
) -> None:
    campaign = _campaign_with_leads(
        client,
        campaign_payload,
        {"business_name": "The Crown", "location": "Luton", "website": "https://crown-a.test"},
        {
            "business_name": "Crown Bakehouse",
            "location": "Dunstable",
            "website": "https://crown-b.test",
            "phone_number": "01582 000001",
        },
    )
    run_id = _run(
        app,
        settings,
        campaign["id"],
        _Provider(_business("crown", "The Crown", "Luton, UK", phone="+44 1582 000001")),
    )

    candidate = client.get(f"/api/v1/campaign-runs/{run_id}").json()["candidates"][0]
    assert candidate["status"] == "linked_existing"
    linked = client.get(f"/api/v1/leads/{candidate['matched_lead_id']}").json()
    assert linked["business_name"] == "Crown Bakehouse"
