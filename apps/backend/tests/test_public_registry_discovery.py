from __future__ import annotations

from typing import cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Campaign, CampaignRun, DiscoveryCandidate, Lead, SourceSystem
from app.domains.automation.enrichment import SafeWebsiteEnricher
from app.domains.automation.providers import (
    DiscoveredBusiness,
    DiscoveryBatch,
    EventDirectoryProvider,
    FhrsInstagramProvider,
    InstagramProfessionalProfile,
    MetaInstagramProvider,
    ProviderFailure,
    PublicRegistryProvider,
    generate_handle_guesses,
)
from app.domains.automation.service import CampaignAutomationService


def _campaign(**overrides: object) -> Campaign:
    defaults: dict[str, object] = {
        "id": "campaign-1",
        "name": "Test campaign",
        "segment": "Bakeries and home bakers",
        "primary_location": "Luton, United Kingdom",
        "radius_miles": 25.0,
        "keywords": ["bakery", "cake maker"],
        "product_categories": [],
    }
    defaults.update(overrides)
    return Campaign(**defaults)


class _ScriptedInstagramProvider:
    def __init__(
        self,
        responses: dict[str, InstagramProfessionalProfile | ProviderFailure],
        connected: bool = True,
        default_failure: ProviderFailure | None = None,
    ) -> None:
        self.responses = responses
        self.connected = connected
        self.default_failure = default_failure
        self.calls: list[str] = []

    def lookup_profile(self, profile_url: str) -> InstagramProfessionalProfile:
        self.calls.append(profile_url)
        result = self.responses.get(profile_url)
        if result is None:
            raise self.default_failure or ProviderFailure(
                "META_INSTAGRAM_PROFILE_UNAVAILABLE", "not found"
            )
        if isinstance(result, ProviderFailure):
            raise result
        return result

    profile_business = staticmethod(MetaInstagramProvider.profile_business)


def _ig(provider: _ScriptedInstagramProvider) -> MetaInstagramProvider:
    return cast(MetaInstagramProvider, provider)


def _profile(username: str, name: str) -> InstagramProfessionalProfile:
    return InstagramProfessionalProfile(
        account_id=f"account-{username}",
        username=username,
        profile_url=f"https://www.instagram.com/{username}",
        business_name=name,
        biography=None,
        website=None,
        public_email=None,
        public_phone=None,
        followers_count=None,
        media_count=None,
    )


def test_generate_handle_guesses_deterministic_and_capped() -> None:
    guesses = generate_handle_guesses("Luton Home Bakery", "Luton")
    assert guesses == [
        "https://www.instagram.com/lutonhomebakery",
        "https://www.instagram.com/luton_home_bakery",
        "https://www.instagram.com/lutonhomebakeryluton",
        "https://www.instagram.com/luton_home_bakery_luton",
    ]
    assert generate_handle_guesses("", "") == []


def test_fhrs_provider_promotes_first_successful_guess(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-version"] == "2"
        # The campaign's primary_location is "Luton, United Kingdom" - only the town should
        # be sent, since FHRS's address search returns zero results for the full string.
        assert request.url.params["address"] == "Luton"
        return httpx.Response(
            200,
            json={
                "establishments": [
                    {
                        "BusinessName": "Luton Home Bakery",
                        "BusinessType": "Retailers - other",
                        "AddressLine3": "Luton",
                        "PostCode": "LU1 1AA",
                        "FHRSID": 12345,
                    },
                    {
                        "BusinessName": "Riverside Fish Bar",
                        "BusinessType": "Takeaway/sandwich shop",
                        "AddressLine3": "Luton",
                        "PostCode": "LU1 2BB",
                        "FHRSID": 67890,
                    },
                ]
            },
        )

    instagram = _ScriptedInstagramProvider(
        {
            "https://www.instagram.com/lutonhomebakery": _profile(
                "lutonhomebakery", "Luton Home Bakery"
            )
        }
    )
    provider = FhrsInstagramProvider(
        settings, _ig(instagram), client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    batch = provider.discover(_campaign())

    assert [business.business_name for business in batch.businesses] == ["Luton Home Bakery"]
    assert batch.businesses[0].evidence["fhrs"]["fhrsid"] == 12345
    assert batch.businesses[0].location == "Luton, LU1 1AA"
    assert instagram.calls == ["https://www.instagram.com/lutonhomebakery"]
    assert not batch.warnings
    assert batch.queries == ["FHRS establishments near Luton"]


def test_fhrs_provider_warns_without_promoting_when_no_guess_resolves(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "establishments": [
                    {
                        "BusinessName": "Luton Home Bakery",
                        "BusinessType": "Retailers - other",
                        "PostCode": "LU1 1AA",
                        "FHRSID": 12345,
                    }
                ]
            },
        )

    instagram = _ScriptedInstagramProvider({})
    provider = FhrsInstagramProvider(
        settings, _ig(instagram), client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    batch = provider.discover(_campaign())

    assert batch.businesses == []
    assert batch.warnings is not None
    assert "No Instagram match for Luton Home Bakery" in batch.warnings[0]
    # No address line was supplied, so only the town-less guesses are tried.
    assert instagram.calls == [
        "https://www.instagram.com/lutonhomebakery",
        "https://www.instagram.com/luton_home_bakery",
    ]


def test_fhrs_provider_filters_out_irrelevant_business_types(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "establishments": [
                    {
                        "BusinessName": "Riverside Fish Bar",
                        "BusinessType": "Takeaway/sandwich shop",
                        "PostCode": "LU1 2BB",
                        "FHRSID": 67890,
                    }
                ]
            },
        )

    instagram = _ScriptedInstagramProvider({})
    provider = FhrsInstagramProvider(
        settings, _ig(instagram), client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    batch = provider.discover(_campaign())

    assert batch.businesses == []
    assert instagram.calls == []


def test_fhrs_provider_stops_on_systemic_meta_failure(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "establishments": [
                    {"BusinessName": "Luton Home Bakery", "BusinessType": "Bakers", "FHRSID": 1}
                ]
            },
        )

    instagram = _ScriptedInstagramProvider(
        {},
        default_failure=ProviderFailure("META_INSTAGRAM_UNAVAILABLE", "Meta is unreachable"),
    )
    provider = FhrsInstagramProvider(
        settings, _ig(instagram), client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(ProviderFailure, match="Meta is unreachable"):
        provider.discover(_campaign())


def test_fhrs_provider_requires_meta_connection(settings: Settings) -> None:
    instagram = _ScriptedInstagramProvider({}, connected=False)
    provider = FhrsInstagramProvider(settings, _ig(instagram))

    with pytest.raises(ProviderFailure, match="Connect an Instagram"):
        provider.discover(_campaign())


def test_event_directory_provider_follows_supplier_pages_and_verifies_instagram(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def address_info(*_: object, **__: object) -> list[tuple[object, ...]]:
        return [(2, 1, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr("app.domains.automation.enrichment.socket.getaddrinfo", address_info)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
            )
        if request.url.path == "/suppliers-directory/wedding-planners/":
            return httpx.Response(
                200,
                text=(
                    "<title>Wedding planners</title>"
                    '<a href="/suppliers-directory/wedding-planners/louisa-may">Louisa May</a>'
                    '<a href="/suppliers-directory/wedding-planners/amae-events">Amae Events</a>'
                ),
                headers={"content-type": "text/html"},
            )
        if request.url.path == "/suppliers-directory/wedding-planners/louisa-may":
            return httpx.Response(
                200,
                text=(
                    "<title>Louisa May Weddings</title>"
                    '<a href="https://www.instagram.com/louisamayweddings">Instagram</a>'
                ),
                headers={"content-type": "text/html"},
            )
        return httpx.Response(
            200, text="<title>Amae Events</title>", headers={"content-type": "text/html"}
        )

    instagram = _ScriptedInstagramProvider(
        {
            "https://www.instagram.com/louisamayweddings": _profile(
                "louisamayweddings", "Louisa May Weddings"
            )
        }
    )
    enricher = SafeWebsiteEnricher(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    provider = EventDirectoryProvider(settings, _ig(instagram), enricher)

    batch = provider.discover(_campaign(segment="Wedding and event planners", keywords=["wedding"]))

    assert [business.business_name for business in batch.businesses] == ["Louisa May Weddings"]
    assert batch.businesses[0].evidence["event_directory"]["source_url"].endswith("louisa-may")


def test_event_directory_provider_requires_meta_connection(settings: Settings) -> None:
    instagram = _ScriptedInstagramProvider({}, connected=False)
    provider = EventDirectoryProvider(settings, _ig(instagram), SafeWebsiteEnricher(settings))

    with pytest.raises(ProviderFailure, match="Connect an Instagram"):
        provider.discover(_campaign())


def test_registry_matcher_routes_bakery_campaign_to_fhrs_only(settings: Settings) -> None:
    calls: list[str] = []

    class _RecordingFhrs:
        def discover(self, campaign: Campaign) -> DiscoveryBatch:
            calls.append("fhrs")
            return DiscoveryBatch(businesses=[], queries=[], request_count=0, warnings=[])

    instagram = _ScriptedInstagramProvider({})
    provider = PublicRegistryProvider(settings, _ig(instagram))
    provider._factories["fhrs"] = _RecordingFhrs

    provider.discover(_campaign())

    assert calls == ["fhrs"]


def test_registry_matcher_returns_warning_when_nothing_matches(settings: Settings) -> None:
    instagram = _ScriptedInstagramProvider({})
    provider = PublicRegistryProvider(settings, _ig(instagram))

    batch = provider.discover(_campaign(segment="Plumbers", keywords=["boiler repair"]))

    assert batch.businesses == []
    assert batch.warnings is not None
    assert "No public registry source matches" in batch.warnings[0]


def test_public_registry_provider_isolates_one_registrys_failure_from_another(
    settings: Settings,
) -> None:
    class _FailingFhrs:
        def discover(self, campaign: Campaign) -> DiscoveryBatch:
            raise ProviderFailure("FHRS_UNAVAILABLE", "FHRS is down")

    class _WorkingEventDirectories:
        def discover(self, campaign: Campaign) -> DiscoveryBatch:
            business = DiscoveredBusiness(
                provider_record_id="acct-1",
                business_name="Louisa May Weddings",
                location=campaign.primary_location,
                website=None,
                phone=None,
                source_url="https://www.instagram.com/louisamayweddings",
                latitude=None,
                longitude=None,
                place_types=["instagram_professional"],
                evidence={},
            )
            return DiscoveryBatch(businesses=[business], queries=[], request_count=1, warnings=[])

    instagram = _ScriptedInstagramProvider({})
    provider = PublicRegistryProvider(settings, _ig(instagram))
    provider._factories["fhrs"] = _FailingFhrs
    provider._factories["event_directories"] = _WorkingEventDirectories

    batch = provider.discover(
        _campaign(segment="Bakery and wedding cakes", keywords=["bakery", "wedding"])
    )

    assert [business.business_name for business in batch.businesses] == ["Louisa May Weddings"]
    assert batch.warnings is not None
    assert any("FHRS is down" in warning for warning in batch.warnings)


def test_public_registries_supported_as_discovery_source(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    response = client.post(
        "/api/v1/campaigns",
        json={**campaign_payload, "discovery_sources": ["manual", "public_registries"]},
    )
    assert response.status_code == 201
    assert "public_registries" in response.json()["discovery_sources"]


def test_unsupported_discovery_source_still_rejected(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    response = client.post(
        "/api/v1/campaigns",
        json={**campaign_payload, "discovery_sources": ["manual", "not_a_real_source"]},
    )
    assert response.status_code == 422


def test_fhrs_lead_is_labeled_correctly_not_as_google_places(
    app: FastAPI, client: TestClient, settings: Settings, campaign_payload: dict[str, object]
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    service = CampaignAutomationService(settings)
    with app.state.database.session_factory() as session:
        run = CampaignRun(campaign_id=campaign["id"], trigger="manual_public_registries")
        session.add(run)
        session.flush()
        candidate = DiscoveryCandidate(
            run_id=run.id,
            campaign_id=campaign["id"],
            provider="public_registries",
            provider_record_id="account-lutonhomebakery",
            business_name="Luton Home Bakery",
            normalized_name="lutonhomebakery",
            location="Luton, LU1 1AA",
            evidence={"fhrs": {"fhrsid": 12345, "postcode": "LU1 1AA"}},
        )
        session.add(candidate)
        lead = Lead(
            business_name="Luton Home Bakery",
            normalized_name="lutonhomebakery",
            segment=campaign["segment"],
            location="Luton, LU1 1AA",
            contact_classification="unknown",
            pipeline_stage="new",
        )
        session.add(lead)
        session.flush()

        service._attach_evidence(session, candidate, lead)
        session.commit()

        source_names = set(session.scalars(select(SourceSystem.name)).all())

    assert "UK Food Standards Agency register (verified via Meta)" in source_names
    assert "Google Places" not in source_names
