from __future__ import annotations

from typing import cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.db.models import Campaign
from app.domains.automation.enrichment import EnrichmentFailure, SafeWebsiteEnricher
from app.domains.automation.providers import (
    DiscoveredBusiness,
    DiscoveryBatch,
    GooglePlacesProvider,
)
from app.domains.automation.schemas import CampaignRunProvider
from app.domains.automation.service import CampaignAutomationService
from tests.conftest import lead_payload
from tests.test_qualification_workflow import _import_catalogue


def test_campaign_run_scores_all_leads_and_preserves_weekly_shortlist(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    for name in ("Alpha Cakes", "Beta Bakes"):
        payload = lead_payload(campaign["id"])
        payload["business_name"] = name
        assert client.post("/api/v1/leads", json=payload).status_code == 201
    _import_catalogue(client)

    first = client.post(
        "/api/v1/campaign-runs",
        json={"campaign_id": campaign["id"], "provider": "scoring"},
    )
    assert first.status_code == 202
    run = first.json()
    assert run["status"] == "completed"
    assert run["phase"] == "completed"
    assert run["provider_status"] == "not_requested"
    assert run["metrics"]["leads_scored"] == 2
    assert run["metrics"]["qualified"] == 2
    assert run["metrics"]["shortlist_created"] == 1
    assert run["metrics"]["shortlist_selected"] == 2

    scores = client.get("/api/v1/scores/latest").json()
    assert len(scores) == 2
    assert all(score["campaign_run_id"] == run["id"] for score in scores)
    assert all(len(score["input_fingerprint"]) == 64 for score in scores)
    shortlists = client.get("/api/v1/shortlists").json()
    assert len(shortlists) == 1
    assert len(shortlists[0]["items"]) == 2

    second = client.post(
        "/api/v1/campaign-runs",
        json={"campaign_id": campaign["id"], "provider": "scoring"},
    )
    assert second.status_code == 202
    assert second.json()["metrics"]["shortlist_created"] == 0
    assert len(client.get("/api/v1/shortlists").json()) == 1

    third = client.post(
        "/api/v1/campaign-runs",
        json={"campaign_id": campaign["id"], "provider": "scoring"},
    )
    assert third.status_code == 202
    assert third.json()["metrics"]["scores_unchanged"] == 2
    assert third.json()["metrics"]["leads_scored"] == 0

    provider_not_selected = client.post(
        "/api/v1/campaign-runs",
        json={"campaign_id": campaign["id"], "provider": "instagram"},
    )
    assert provider_not_selected.status_code == 409
    assert provider_not_selected.json()["code"] == "CAMPAIGN_PROVIDER_NOT_SELECTED"


def test_run_all_uses_only_active_campaigns(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    active = client.post("/api/v1/campaigns", json=campaign_payload).json()
    paused_payload = {**campaign_payload, "name": "Paused campaign", "status": "paused"}
    paused = client.post("/api/v1/campaigns", json=paused_payload).json()

    response = client.post("/api/v1/campaign-runs/all", json={"provider": "scoring"})
    assert response.status_code == 202
    runs = response.json()
    assert [run["campaign_id"] for run in runs] == [active["id"]]
    assert runs[0]["trigger"] == "manual_all_scoring"

    rejected = client.post(
        "/api/v1/campaign-runs",
        json={"campaign_id": paused["id"], "provider": "scoring"},
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "CAMPAIGN_NOT_ACTIVE"


def test_run_all_filters_campaigns_by_requested_provider(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    client.post("/api/v1/campaigns", json=campaign_payload)
    google = client.post(
        "/api/v1/campaigns",
        json={
            **campaign_payload,
            "name": "Google campaign",
            "discovery_sources": ["manual", "google_places"],
        },
    ).json()
    instagram = client.post(
        "/api/v1/campaigns",
        json={
            **campaign_payload,
            "name": "Instagram campaign",
            "discovery_sources": ["manual", "instagram"],
        },
    ).json()

    google_runs = client.post(
        "/api/v1/campaign-runs/all", json={"provider": "google_places"}
    ).json()
    assert [run["campaign_id"] for run in google_runs] == [google["id"]]
    assert google_runs[0]["trigger"] == "manual_all_google_places"

    instagram_runs = client.post("/api/v1/campaign-runs/all", json={"provider": "instagram"}).json()
    assert [run["campaign_id"] for run in instagram_runs] == [instagram["id"]]
    assert instagram_runs[0]["trigger"] == "manual_all_instagram"


class _FakeProvider:
    def discover(self, campaign: Campaign) -> DiscoveryBatch:
        businesses = [
            DiscoveredBusiness(
                provider_record_id="new-bakery",
                business_name="New Discovery Bakery",
                location="Luton, United Kingdom",
                website=None,
                phone="01582 000001",
                source_url="https://maps.example/new-bakery",
                latitude=51.88,
                longitude=-0.42,
                place_types=["bakery"],
                evidence={"query": "bakery in Luton"},
            ),
            DiscoveredBusiness(
                provider_record_id="existing-bakery",
                business_name="Example Celebration Cakes",
                location="Luton, United Kingdom",
                website=None,
                phone=None,
                source_url="https://maps.example/existing-bakery",
                latitude=51.88,
                longitude=-0.42,
                place_types=["bakery"],
                evidence={"query": "bakery in Luton"},
            ),
            DiscoveredBusiness(
                provider_record_id="similar-bakery",
                business_name="Example Celebration Cake",
                location="Luton, United Kingdom",
                website=None,
                phone=None,
                source_url="https://maps.example/similar-bakery",
                latitude=51.88,
                longitude=-0.42,
                place_types=["bakery"],
                evidence={"query": "bakery in Luton"},
            ),
        ]
        return DiscoveryBatch(
            businesses=businesses,
            queries=[f"bakery in {campaign.primary_location}"],
            request_count=2,
        )


def test_discovery_promotes_links_and_stages_ambiguous_duplicates(
    client: TestClient,
    app: FastAPI,
    settings: Settings,
    campaign_payload: dict[str, object],
) -> None:
    payload = {
        **campaign_payload,
        "discovery_sources": ["google_places", "instagram"],
        "discovery_mode": "combined",
    }
    campaign = client.post("/api/v1/campaigns", json=payload).json()
    assert client.post("/api/v1/leads", json=lead_payload(campaign["id"])).status_code == 201
    provider_settings = settings.model_copy(
        update={"google_places_api_key": SecretStr("test-api-key")}
    )
    service = CampaignAutomationService(
        provider_settings,
        provider=cast(GooglePlacesProvider, _FakeProvider()),
    )
    database = app.state.database
    with database.session_factory() as session:
        run_id = service.queue(
            session,
            campaign["id"],
            requested_provider=CampaignRunProvider.GOOGLE_PLACES,
            correlation_id="test-correlation",
        )
    with database.session_factory() as session:
        service.execute(session, run_id, "test-correlation")

    run = client.get(f"/api/v1/campaign-runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["provider_status"] == "completed"
    assert run["metrics"]["discovered"] == 3
    assert run["metrics"]["promoted"] == 1
    assert run["metrics"]["linked_existing"] == 1
    assert run["metrics"]["review_required"] == 1
    review = next(item for item in run["candidates"] if item["status"] == "review_required")
    assert review["matched_lead_id"] is not None

    rejected = client.post(
        f"/api/v1/discovery-candidates/{review['id']}/decision",
        json={"action": "reject", "reason": "Confirmed duplicate"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    leads = client.get("/api/v1/leads").json()
    assert len(leads) == 2
    discovered = next(lead for lead in leads if lead["business_name"] == "New Discovery Bakery")
    assert discovered["phone_number"] == "01582 000001"

    with database.session_factory() as session:
        second_run_id = service.queue(
            session,
            campaign["id"],
            requested_provider=CampaignRunProvider.GOOGLE_PLACES,
            correlation_id="test-correlation-rerun",
        )
    with database.session_factory() as session:
        service.execute(session, second_run_id, "test-correlation-rerun")
    second_run = client.get(f"/api/v1/campaign-runs/{second_run_id}").json()
    assert second_run["metrics"]["promoted"] == 0
    assert second_run["metrics"]["linked_existing"] == 2
    assert len(client.get("/api/v1/leads").json()) == 2


def test_assisted_social_capture_deduplicates_and_scores(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    _import_catalogue(client)
    payload = {
        "campaign_id": campaign["id"],
        "platform": "instagram",
        "profile_url": "https://www.instagram.com/caky.licious/",
        "business_name": "Caky Licious",
        "location": "Luton, United Kingdom",
        "phone_number": "+44 1582 123456",
        "public_email": "hello@cakylicious.example",
        "public_bio": "Celebration cakes and personalised toppers in Luton",
    }
    first = client.post("/api/v1/social-candidates", json=payload)
    assert first.status_code == 201
    assert first.json()["metrics"]["promoted"] == 1
    assert first.json()["metrics"]["leads_scored"] == 1

    leads = client.get("/api/v1/leads").json()
    assert len(leads) == 1
    assert leads[0]["phone_number"] == "+44 1582 123456"
    assert leads[0]["public_email"] == "hello@cakylicious.example"
    assert leads[0]["social_identities"][0]["platform"] == "instagram"
    assert leads[0]["social_identities"][0]["normalized_handle"] == "caky.licious"

    second = client.post(
        "/api/v1/social-candidates",
        json={**payload, "business_name": "Caky.Licious"},
    )
    assert second.status_code == 201
    assert second.json()["metrics"]["promoted"] == 0
    assert second.json()["metrics"]["linked_existing"] == 1
    assert len(client.get("/api/v1/leads").json()) == 1


def test_google_provider_applies_exact_radius_filter(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"results": [{"location": {"latitude": 51.88, "longitude": -0.42}}]},
            )
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "nearby",
                        "displayName": {"text": "Nearby Bakery"},
                        "formattedAddress": "Luton",
                        "location": {"latitude": 51.881, "longitude": -0.42},
                        "types": ["bakery"],
                        "businessStatus": "OPERATIONAL",
                        "internationalPhoneNumber": "+44 1582 123456",
                    },
                    {
                        "id": "outside",
                        "displayName": {"text": "Distant Bakery"},
                        "formattedAddress": "Far Away",
                        "location": {"latitude": 52.2, "longitude": -0.42},
                        "types": ["bakery"],
                        "businessStatus": "OPERATIONAL",
                    },
                ]
            },
        )

    configured = settings.model_copy(update={"google_places_api_key": SecretStr("test-api-key")})
    provider = GooglePlacesProvider(
        configured,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    campaign = Campaign(
        name="Radius test",
        segment="Bakeries",
        primary_location="Luton",
        radius_miles=2,
        keywords=["bakery"],
        exclusion_keywords=[],
        product_categories=[],
        discovery_sources=["google_places"],
        weekly_shortlist_size=5,
        preferred_channels=[],
        offer_settings={},
        discovery_mode="combined",
        status="active",
    )
    result = provider.discover(campaign)
    assert [business.provider_record_id for business in result.businesses] == ["nearby"]
    assert result.businesses[0].phone == "+44 1582 123456"
    assert result.request_count == 2


def test_enrichment_rejects_private_and_malformed_addresses(settings: Settings) -> None:
    enricher = SafeWebsiteEnricher(settings)
    with pytest.raises(EnrichmentFailure, match="private or reserved") as blocked:
        enricher.enrich("http://127.0.0.1")
    assert blocked.value.code == "WEBSITE_ADDRESS_BLOCKED"

    with pytest.raises(EnrichmentFailure) as malformed:
        enricher.enrich("https://example.com:not-a-port")
    assert malformed.value.code == "WEBSITE_URL_UNSAFE"


def test_enrichment_checks_contact_pages_for_public_contacts(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def address_info(*_: object, **__: object) -> list[tuple[object, ...]]:
        return [(2, 1, 6, "", ("93.184.216.34", 443))]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
            )
        if request.url.path == "/contact":
            return httpx.Response(
                200,
                text=(
                    '<a href="mailto:hello@example.com">Email</a>'
                    '<a href="tel:+441582123456">Call</a>'
                    '<a href="https://instagram.com/examplecakes">Instagram</a>'
                ),
                headers={"content-type": "text/html"},
            )
        return httpx.Response(
            200,
            text=(
                "<title>Example Cakes</title>"
                '<a href="/contact">Contact us</a>'
                '<a href="https://facebook.com/examplecakes">Facebook</a>'
            ),
            headers={"content-type": "text/html"},
        )

    monkeypatch.setattr("app.domains.automation.enrichment.socket.getaddrinfo", address_info)
    enricher = SafeWebsiteEnricher(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    evidence = enricher.enrich("https://example.com")
    assert evidence.public_emails == ["hello@example.com"]
    assert evidence.public_phones == ["+441582123456"]
    assert set(evidence.social_links) == {
        "https://facebook.com/examplecakes",
        "https://instagram.com/examplecakes",
    }
    assert evidence.pages_checked == ["https://example.com", "https://example.com/contact"]
