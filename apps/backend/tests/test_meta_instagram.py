from __future__ import annotations

import logging
import socket
from typing import cast
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import DomainError
from app.core.secrets import MemorySecretStore
from app.domains.automation.providers import (
    InstagramProfessionalProfile,
    MetaInstagramProvider,
)
from app.domains.automation.schemas import CampaignRunProvider
from app.domains.automation.service import CampaignAutomationService
from app.domains.system.meta import MetaConnectionService
from app.domains.system.meta_schemas import MetaConfigurationWrite


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _connected_store() -> MemorySecretStore:
    store = MemorySecretStore()
    store.set_json(
        "meta.credentials",
        {"app_id": "1596694465496867", "app_secret": "a-secure-meta-app-secret"},
    )
    store.set_json(
        "meta.connection",
        {
            "user_access_token": "user-token",
            "accounts": [
                {
                    "page_id": "page-1",
                    "page_name": "Etch N Shine",
                    "page_access_token": "page-token",
                    "instagram_account_id": "own-ig-id",
                    "instagram_username": "etchnshine",
                }
            ],
            "selected_page_id": "page-1",
            "expires_at": None,
        },
    )
    return store


def test_meta_configuration_response_never_contains_secret(
    client: TestClient, app: FastAPI, settings: Settings
) -> None:
    secret = "a-unique-meta-app-secret"  # noqa: S105 -- test fixture
    response = client.put(
        "/api/v1/system/providers/meta",
        json={"app_id": "1596694465496867", "app_secret": secret},
    )
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert secret not in response.text
    vault_files = list((settings.database_path.parent / "secrets").glob("*.vault"))
    assert vault_files
    assert all(secret.encode() not in path.read_bytes() for path in vault_files)
    assert app.state.meta_connection_service.status().connected is False


def test_meta_oauth_exchanges_token_and_selects_single_instagram_account(
    settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/access_token":
            if request.url.params.get("grant_type") == "fb_exchange_token":
                return httpx.Response(200, json={"access_token": "long-token", "expires_in": 3600})
            return httpx.Response(200, json={"access_token": "short-token", "expires_in": 600})
        if request.url.path.endswith("/me/accounts"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "page-1",
                            "name": "Etch N Shine",
                            "access_token": "page-token",
                            "instagram_business_account": {
                                "id": "own-ig-id",
                                "username": "etchnshine",
                            },
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected Meta request: {request.url}")

    callback_port = _free_loopback_port()
    configured = settings.model_copy(
        update={
            "meta_oauth_callback_url": (f"http://127.0.0.1:{callback_port}/meta/oauth/callback")
        }
    )
    store = MemorySecretStore()
    service = MetaConnectionService(
        configured,
        store,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    try:
        service.configure(
            MetaConfigurationWrite(
                app_id="1596694465496867",
                app_secret=SecretStr("a-secure-meta-app-secret"),
            )
        )
        authorization = service.start_authorization()
        authorization_query = parse_qs(urlparse(authorization.authorization_url).query)
        state = authorization_query["state"][0]
        assert authorization_query["scope"][0].split(",") == [
            "pages_show_list",
            "pages_read_engagement",
            "instagram_basic",
        ]
        result = service._complete_authorization("authorization-code", state)
        assert result.connected is True
        assert result.selected_account is not None
        assert result.selected_account.instagram_username == "etchnshine"
    finally:
        service.shutdown()


def test_meta_oauth_reports_safe_state_validation_reason(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    callback_port = _free_loopback_port()
    configured = settings.model_copy(
        update={
            "meta_oauth_callback_url": (f"http://localhost:{callback_port}/meta/oauth/callback")
        }
    )
    store = MemorySecretStore()
    service = MetaConnectionService(configured, store)
    meta_logger = logging.getLogger("app.domains.system.meta")
    logger_was_disabled = meta_logger.disabled
    meta_logger.disabled = False
    try:
        service.configure(
            MetaConfigurationWrite(
                app_id="1596694465496867",
                app_secret=SecretStr("a-secure-meta-app-secret"),
            )
        )
        authorization = service.start_authorization()
        expected_state = parse_qs(urlparse(authorization.authorization_url).query)["state"][0]
        supplied_state = "different-state-value"
        with (
            caplog.at_level(logging.INFO, logger="app.domains.system.meta"),
            pytest.raises(DomainError, match="did not match"),
        ):
            service._complete_authorization("authorization-code", supplied_state)
        assert "reason=callback_state_mismatch" in caplog.text
        assert expected_state not in caplog.text
        assert supplied_state not in caplog.text
        assert "authorization-code" not in caplog.text
    finally:
        meta_logger.disabled = logger_was_disabled
        service.shutdown()


def test_instagram_provider_looks_up_operator_selected_professional_profile(
    settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/own-ig-id")
        fields = request.url.params["fields"]
        assert "business_discovery.username(donmillersuk)" in fields
        assert "follows_count" not in fields
        assert "profile_picture_url" not in fields
        return httpx.Response(
            200,
            json={
                "business_discovery": {
                    "id": "business-42",
                    "username": "donmillersuk",
                    "name": "Don Millers",
                    "biography": "Luton bakery. Call +44 1582 111222 or sales@donmillers.example",
                    "website": "https://donmillers.example",
                    "followers_count": 850,
                    "media_count": 95,
                }
            },
        )

    connection = MetaConnectionService(settings, _connected_store())
    provider = MetaInstagramProvider(
        settings,
        connection,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    profile = provider.lookup_profile("https://www.instagram.com/donmillersuk/")

    assert profile.account_id == "business-42"
    assert profile.business_name == "Don Millers"
    assert profile.public_email == "sales@donmillers.example"
    assert profile.public_phone == "+44 1582 111222"
    assert profile.followers_count == 850


class _ReadyInstagramProvider:
    connected = True

    def lookup_profile(self, profile_url: str) -> InstagramProfessionalProfile:
        username = profile_url.rstrip("/").rsplit("/", 1)[-1].casefold()
        return InstagramProfessionalProfile(
            account_id=f"profile-{username}",
            username=username,
            profile_url=f"https://www.instagram.com/{username}",
            business_name="Don Millers",
            biography="Luton bakery. Email hello@donmillers.example",
            website=None,
            public_email="hello@donmillers.example",
            public_phone="+44 1582 111222",
            followers_count=850,
            media_count=95,
        )

    profile_business = staticmethod(MetaInstagramProvider.profile_business)


def test_instagram_campaign_run_refreshes_saved_profile_without_duplicate(
    client: TestClient,
    app: FastAPI,
    settings: Settings,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            **campaign_payload,
            "discovery_sources": ["manual", "instagram"],
            "discovery_mode": "combined",
        },
    ).json()
    service = CampaignAutomationService(
        settings,
        instagram_provider=cast(MetaInstagramProvider, _ReadyInstagramProvider()),
    )
    with app.state.database.session_factory() as session:
        imported = service.import_instagram_profile(
            session,
            campaign["id"],
            "https://www.instagram.com/instagrambakery/",
            "import",
        )
    assert imported.metrics["promoted"] == 1

    with app.state.database.session_factory() as session:
        first_run = service.queue(
            session,
            campaign["id"],
            requested_provider=CampaignRunProvider.INSTAGRAM,
            correlation_id="first",
        )
    with app.state.database.session_factory() as session:
        service.execute(session, first_run, "first")
    first_refresh = client.get(f"/api/v1/campaign-runs/{first_run}").json()
    assert first_refresh["metrics"]["promoted"] == 0
    assert first_refresh["metrics"]["linked_existing"] == 1

    with app.state.database.session_factory() as session:
        second_run = service.queue(
            session,
            campaign["id"],
            requested_provider=CampaignRunProvider.INSTAGRAM,
            correlation_id="second",
        )
    with app.state.database.session_factory() as session:
        service.execute(session, second_run, "second")
    rerun = client.get(f"/api/v1/campaign-runs/{second_run}").json()
    assert rerun["metrics"]["promoted"] == 0
    assert rerun["metrics"]["linked_existing"] == 1
    assert len(client.get("/api/v1/leads").json()) == 1


def test_instagram_profile_preview_import_and_bulk_enrichment_are_deduplicated(
    client: TestClient,
    app: FastAPI,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    app.state.campaign_run_manager.instagram_provider = cast(
        MetaInstagramProvider, _ReadyInstagramProvider()
    )

    preview = client.post(
        "/api/v1/instagram/profiles/preview",
        json={"profile_url": "https://www.instagram.com/donmillersuk/"},
    )
    assert preview.status_code == 200
    assert preview.json()["username"] == "donmillersuk"
    assert preview.json()["public_email"] == "hello@donmillers.example"

    imported = client.post(
        "/api/v1/instagram/profiles/import",
        json={
            "campaign_id": campaign["id"],
            "profile_url": "https://www.instagram.com/donmillersuk/",
        },
    )
    assert imported.status_code == 201
    assert imported.json()["metrics"]["promoted"] == 1
    assert imported.json()["metrics"]["leads_scored"] == 1

    enriched = client.post(
        "/api/v1/instagram/profiles/enrich-known",
        json={"campaign_id": campaign["id"]},
    )
    assert enriched.status_code == 201
    assert enriched.json()["metrics"]["promoted"] == 0
    assert enriched.json()["metrics"]["linked_existing"] == 1
    leads = client.get("/api/v1/leads").json()
    assert len(leads) == 1
    assert leads[0]["phone_number"] == "+44 1582 111222"
    assert leads[0]["public_email"] == "hello@donmillers.example"
    assert {source["source_type"] for source in leads[0]["sources"]} == {"instagram"}
