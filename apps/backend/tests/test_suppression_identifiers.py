"""Suppression covers every identifier, not only name and location (ADR-023, FR-161, FR-163)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from app.core.config import Settings
from app.db.migrations import backend_directory, run_migrations
from app.db.models import Campaign
from app.db.session import create_sqlite_engine, sqlite_url
from app.domains.automation.enrichment import EnrichmentFailure, SafeWebsiteEnricher
from app.domains.automation.providers import (
    DiscoveredBusiness,
    DiscoveryBatch,
    GooglePlacesProvider,
)
from app.domains.automation.schemas import CampaignRunProvider
from app.domains.automation.service import CampaignAutomationService
from app.domains.leads.identity import lead_identifier_hash
from app.domains.leads.suppression import IdentifierKind, identifier_hashes
from tests.conftest import lead_payload

SUPPRESSED = {
    "business_name": "Crown Bakery",
    "location": "Leeds",
    "website": "https://crownbakery.test",
    "phone_number": "0113 496 0000",
    "public_email": "hello@crownbakery.test",
    "instagram_url": "https://www.instagram.com/crownbakery",
}


def _business(record_id: str, name: str, location: str, **fields: Any) -> DiscoveredBusiness:
    return DiscoveredBusiness(
        provider_record_id=record_id,
        business_name=name,
        location=location,
        website=fields.get("website"),
        phone=fields.get("phone"),
        source_url=f"https://maps.example/{record_id}",
        latitude=53.8,
        longitude=-1.55,
        place_types=["bakery"],
        evidence=fields.get("evidence", {}),
    )


class _RediscoveryProvider:
    """Google reports the suppressed bakery again, every time under a formatted address."""

    def discover(self, campaign: Campaign) -> DiscoveryBatch:
        return DiscoveryBatch(
            businesses=[
                _business(
                    "by-phone",
                    "Crown Bakery Ltd",
                    "12 High Street, Leeds LS1 1AA, UK",
                    phone="+44 113 496 0000",
                ),
                _business(
                    "by-website",
                    "Crown Cakes",
                    "Unit 4, Leeds LS2 7EW, UK",
                    website="https://www.crownbakery.test/about",
                ),
                _business(
                    "by-social",
                    "CB Studio",
                    "Leeds LS3 1AB, UK",
                    evidence={
                        "social_profile": {
                            "platform": "instagram",
                            "profile_url": "https://www.instagram.com/CrownBakery/",
                        }
                    },
                ),
                _business(
                    "by-email",
                    "Crown Celebrations",
                    "Leeds LS4 2AA, UK",
                    evidence={
                        "social_profile": {
                            "platform": "instagram",
                            "profile_url": "https://www.instagram.com/crowncelebrations",
                            "public_email": "Hello@CrownBakery.test",
                        }
                    },
                ),
                _business("by-name", "Crown Bakery", "Bristol BS1 4DJ, UK"),
                _business("unrelated", "Harbour Cafe", "Leeds LS5 3AA, UK", phone="0113 222 3333"),
            ],
            queries=["bakery in Leeds"],
            request_count=1,
        )


class _OfflineEnricher:
    def enrich(self, url: str) -> None:
        raise EnrichmentFailure("WEBSITE_FETCH_FAILED", f"Offline in tests: {url}")


def _campaign(client: TestClient, campaign_payload: dict[str, object]) -> dict[str, Any]:
    response = client.post(
        "/api/v1/campaigns",
        json={
            **campaign_payload,
            "primary_location": "Leeds, United Kingdom",
            "discovery_sources": ["google_places"],
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def _website(name: object) -> str:
    return "https://" + str(name).casefold().replace(" ", "-") + ".test"


def _create(client: TestClient, campaign_id: str, **fields: object) -> dict[str, Any]:
    payload = {
        **lead_payload(campaign_id),
        "website": _website(fields.get("business_name", "lead")),
        **fields,
    }
    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def _suppress(client: TestClient, lead_id: str) -> None:
    response = client.post(
        f"/api/v1/leads/{lead_id}/suppression",
        json={
            "suppression_type": "unsubscribe",
            "reason": "Asked not to be contacted",
            "source": "Email reply",
        },
    )
    assert response.status_code == 201, response.text


def _run_discovery(app: FastAPI, settings: Settings, campaign_id: str) -> str:
    service = CampaignAutomationService(
        settings.model_copy(update={"google_places_api_key": SecretStr("test-api-key")}),
        provider=cast(GooglePlacesProvider, _RediscoveryProvider()),
        enricher=cast(SafeWebsiteEnricher, _OfflineEnricher()),
    )
    database = app.state.database
    with database.session_factory() as session:
        run_id = service.queue(
            session,
            campaign_id,
            requested_provider=CampaignRunProvider.GOOGLE_PLACES,
            correlation_id="suppression-test",
        )
    with database.session_factory() as session:
        service.execute(session, run_id, "suppression-test")
    return run_id


def test_a_deleted_suppressed_business_is_not_rediscovered_by_any_identifier(
    client: TestClient,
    app: FastAPI,
    settings: Settings,
    campaign_payload: dict[str, object],
) -> None:
    campaign = _campaign(client, campaign_payload)
    lead = _create(client, campaign["id"], **SUPPRESSED)
    _suppress(client, lead["id"])
    assert client.delete(f"/api/v1/leads/{lead['id']}").status_code == 200

    run_id = _run_discovery(app, settings, campaign["id"])

    run = client.get(f"/api/v1/campaign-runs/{run_id}").json()
    assert run["status"] == "completed", run
    candidates = {item["provider_record_id"]: item for item in run["candidates"]}
    expected_reasons = {
        "by-phone": "phone number",
        "by-website": "website",
        "by-social": "social profile",
        "by-email": "email address",
    }
    for record_id, label in expected_reasons.items():
        assert candidates[record_id]["status"] == "rejected", candidates[record_id]
        assert candidates[record_id]["rejection_reason"] == (
            f"Matched an active suppression by its {label}."
        )
    name_only = candidates["by-name"]
    assert name_only["status"] == "review_required"
    assert "suppressed business" in name_only["review_reason"]
    assert name_only["matched_lead_id"] is None
    assert candidates["unrelated"]["status"] == "promoted"

    names = [item["business_name"] for item in client.get("/api/v1/leads").json()]
    assert names == ["Harbour Cafe"]


def test_promoting_a_name_only_match_is_allowed_after_review(
    client: TestClient,
    app: FastAPI,
    settings: Settings,
    campaign_payload: dict[str, object],
) -> None:
    campaign = _campaign(client, campaign_payload)
    lead = _create(client, campaign["id"], **SUPPRESSED)
    _suppress(client, lead["id"])
    assert client.delete(f"/api/v1/leads/{lead['id']}").status_code == 200
    run = client.get(
        f"/api/v1/campaign-runs/{_run_discovery(app, settings, campaign['id'])}"
    ).json()
    name_only = next(item for item in run["candidates"] if item["provider_record_id"] == "by-name")
    by_phone = next(item for item in run["candidates"] if item["provider_record_id"] == "by-phone")

    promoted = client.post(
        f"/api/v1/discovery-candidates/{name_only['id']}/decision",
        json={"action": "promote", "reason": "A different bakery in Bristol"},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["status"] == "promoted"

    # A strong identifier cannot be overridden from the review queue.
    blocked = client.post(
        f"/api/v1/discovery-candidates/{by_phone['id']}/decision",
        json={"action": "promote"},
    )
    assert blocked.status_code == 409


def test_manual_create_and_update_are_checked_against_every_identifier(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    campaign = _campaign(client, campaign_payload)
    suppressed = _create(client, campaign["id"], **SUPPRESSED)
    _suppress(client, suppressed["id"])

    same_website = client.post(
        "/api/v1/leads",
        json={
            **lead_payload(campaign["id"]),
            "business_name": "Totally New Name",
            "website": "https://crownbakery.test/shop",
        },
    )
    assert same_website.status_code == 409
    assert same_website.json()["code"] == "LEAD_IDENTIFIER_SUPPRESSED"
    assert same_website.json()["details"] == {"matched_identifier": "website_host"}

    other = _create(client, campaign["id"], business_name="Other Bakery", location="York")
    adds_email = client.patch(
        f"/api/v1/leads/{other['id']}", json={"contact_email": "HELLO@crownbakery.test"}
    )
    assert adds_email.status_code == 409
    assert adds_email.json()["details"] == {"matched_identifier": "email"}
    adds_social = client.patch(
        f"/api/v1/leads/{other['id']}",
        json={"instagram_url": "https://www.instagram.com/crownbakery/"},
    )
    assert adds_social.status_code == 409
    assert client.get(f"/api/v1/leads/{other['id']}").json()["contact_email"] is None

    # The suppressed lead itself stays editable.
    own_edit = client.patch(
        f"/api/v1/leads/{suppressed['id']}", json={"phone_number": "0113 496 0001"}
    )
    assert own_edit.status_code == 200, own_edit.text


def test_lifting_a_suppression_releases_its_identifiers(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    campaign = _campaign(client, campaign_payload)
    suppressed = _create(client, campaign["id"], **SUPPRESSED)
    _suppress(client, suppressed["id"])
    lifted = client.delete(f"/api/v1/leads/{suppressed['id']}/suppression")
    assert lifted.status_code == 200, lifted.text

    reused_phone = client.post(
        "/api/v1/leads",
        json={
            **lead_payload(campaign["id"]),
            "business_name": "Shared Line Bakery",
            "website": _website("Shared Line Bakery"),
            "phone_number": SUPPRESSED["phone_number"],
        },
    )
    assert reused_phone.status_code == 201, reused_phone.text


def test_identifiers_learned_after_suppression_are_kept_on_deletion(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    campaign = _campaign(client, campaign_payload)
    lead = _create(client, campaign["id"], business_name="Quiet Bakery", location="Leeds")
    _suppress(client, lead["id"])
    learned = client.patch(f"/api/v1/leads/{lead['id']}", json={"phone_number": "0113 555 0199"})
    assert learned.status_code == 200, learned.text
    assert client.delete(f"/api/v1/leads/{lead['id']}").status_code == 200

    recreated = client.post(
        "/api/v1/leads",
        json={
            **lead_payload(campaign["id"]),
            "business_name": "Renamed Bakery",
            "website": _website("Renamed Bakery"),
            "phone_number": "+44 113 555 0199",
        },
    )
    assert recreated.status_code == 409
    assert recreated.json()["details"] == {"matched_identifier": "phone"}


def test_migration_backfills_identifiers_from_existing_suppressions(tmp_path: Path) -> None:
    database_path = tmp_path / "existing-0016.db"
    config = Config(str(backend_directory() / "alembic.ini"))
    config.set_main_option("script_location", str(backend_directory() / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlite_url(database_path))
    command.upgrade(config, "0016_seed_outreach_templates")

    now = datetime.now(UTC)
    engine = create_sqlite_engine(database_path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO lead (id, business_name, normalized_name, segment, location, "
                    "website, phone_number, public_email, contact_classification, "
                    "pipeline_stage, suppressed, mock_up_status, sample_status, quote_status, "
                    "created_at, updated_at) VALUES ('lead-1', 'Crown Bakery', 'crown bakery', "
                    "'Bakeries', 'Leeds', 'https://www.crownbakery.test', '0113 496 0000', "
                    "'hello@crownbakery.test', 'unknown', 'do_not_contact', 1, 'not_offered', "
                    "'not_applicable', 'not_requested', :now, :now)"
                ),
                {"now": now.isoformat()},
            )
            connection.execute(
                text(
                    "INSERT INTO lead_social_identity (id, lead_id, platform, profile_url, "
                    "normalized_handle, classification, collected_at, created_at) VALUES "
                    "('social-1', 'lead-1', 'instagram', 'https://www.instagram.com/crownbakery', "
                    "'crownbakery', 'user_verified', :now, :now)"
                ),
                {"now": now.isoformat()},
            )
            for record_id, lead_id, name, location in (
                ("kept", "lead-1", "Crown Bakery", "Leeds"),
                ("orphan", None, "Gone Bakery", "York"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO suppression_record (id, lead_id, identifier_hash, "
                        "suppression_type, reason, source, active, effective_at) VALUES "
                        "(:id, :lead_id, :hash, 'unsubscribe', 'Asked', 'Email', 1, :now)"
                    ),
                    {
                        "id": record_id,
                        "lead_id": lead_id,
                        "hash": lead_identifier_hash(name, location),
                        "now": now.isoformat(),
                    },
                )
    finally:
        engine.dispose()

    run_migrations(database_path)

    engine = create_sqlite_engine(database_path)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT suppression_id, kind, value_hash FROM suppression_identifier")
            ).all()
    finally:
        engine.dispose()
    stored = {(row.suppression_id, row.kind, row.value_hash) for row in rows}
    expected = identifier_hashes(
        business_name="Crown Bakery",
        location="Leeds",
        website="https://www.crownbakery.test",
        phones=["0113 496 0000"],
        emails=["hello@crownbakery.test"],
        social_keys=[("instagram", "crownbakery")],
    )
    # The migration's frozen hashing must agree with the application's.
    assert {("kept", kind.value, value) for kind, value in expected} == {
        row for row in stored if row[0] == "kept"
    }
    assert {row[1] for row in stored if row[0] == "orphan"} == {IdentifierKind.NAME_LOCATION.value}
