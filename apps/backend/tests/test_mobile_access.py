"""Phone access through the gateway (ADR-025): pairing, device cookies, route policy, request
checks, the phone app files and attribution. The gateway is exercised in-process; the real
listener is covered in test_mobile_gateway.py."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import require_desktop
from app.core.config import Settings
from app.db.models import AuditEvent, LeadNote, MobileDevice, MobilePairingCode
from app.domains.mobile.devices import COOKIE_NAME
from app.domains.mobile.tailscale import TailscaleState
from app.main import create_app
from tests.conftest import SESSION_TOKEN, lead_payload

PHONE_HOST = "ens-pc.tail1a2b.ts.net"
PHONE_ORIGIN = f"https://{PHONE_HOST}"
CHANGE_HEADERS = {"Origin": PHONE_ORIGIN, "X-ENS-Request": "1"}


@pytest.fixture
def frontend(tmp_path: Path) -> Path:
    directory = tmp_path / "dist"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text("<!doctype html><title>Etch N Shine</title>")
    (directory / "assets" / "index-abc123.js").write_text("console.log('app')")
    (tmp_path / "secret.txt").write_text("outside the app")
    return directory


@pytest.fixture
def phone_app(settings: Settings, frontend: Path) -> FastAPI:
    return create_app(settings.model_copy(update={"mobile_frontend_directory": frontend}))


@pytest.fixture
def desktop(phone_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(phone_app, headers={"X-Session-Token": SESSION_TOKEN}) as client:
        response = client.patch("/api/v1/mobile/config", json={"public_host": PHONE_HOST})
        assert response.status_code == 200
        yield client


@pytest.fixture
def phone(phone_app: FastAPI, desktop: TestClient) -> Iterator[TestClient]:
    gateway = phone_app.state.mobile_access_service.manager.gateway
    with TestClient(gateway, base_url=PHONE_ORIGIN) as client:
        yield client


def _code(desktop: TestClient) -> str:
    response = desktop.post("/api/v1/mobile/pairing-codes")
    assert response.status_code == 201
    body = response.json()
    assert body["pair_url"] == f"{PHONE_ORIGIN}/pair#{body['code']}"
    return str(body["code"])


def _pair(phone: TestClient, code: str, name: str = "Test phone") -> dict[str, object]:
    response = phone.post(
        "/api/v1/mobile/pair",
        json={"code": code, "name": name, "label": "Safari on iPhone"},
        headers=CHANGE_HEADERS,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _paired(phone: TestClient, desktop: TestClient) -> str:
    body = _pair(phone, _code(desktop))
    device = body["device"]
    assert isinstance(device, dict)
    return str(device["id"])


# Pairing


def test_an_unpaired_phone_is_asked_to_pair(phone: TestClient) -> None:
    response = phone.get("/api/v1/mobile/session")
    assert response.status_code == 401
    assert response.json()["code"] == "PHONE_NOT_PAIRED"


def test_pairing_sets_a_hashed_http_only_cookie(
    phone: TestClient, desktop: TestClient, phone_app: FastAPI
) -> None:
    code = _code(desktop)
    response = phone.post(
        "/api/v1/mobile/pair",
        json={"code": code.lower().replace("-", " "), "name": "Test phone"},
        headers=CHANGE_HEADERS,
    )
    assert response.status_code == 201
    cookie = response.headers["set-cookie"]
    assert f"{COOKIE_NAME}=" in cookie
    for attribute in ("HttpOnly", "Secure", "SameSite=strict", "Path=/api"):
        assert attribute.lower() in cookie.lower()
    secret = cookie.split("=", 1)[1].split(";", 1)[0].split(".", 1)[1]
    assert secret not in response.text

    session = phone.get("/api/v1/mobile/session").json()
    assert session["channel"] == "phone"
    assert session["device"]["name"] == "Test phone"
    with phone_app.state.database.session_factory() as db:
        device = db.scalars(select(MobileDevice)).one()
        assert device.secret_hash != secret
        assert len(device.secret_hash) == 64


def test_a_code_works_once(phone: TestClient, desktop: TestClient) -> None:
    code = _code(desktop)
    _pair(phone, code)
    phone.cookies.clear()
    again = phone.post(
        "/api/v1/mobile/pair", json={"code": code, "name": "Second"}, headers=CHANGE_HEADERS
    )
    assert again.status_code == 400
    assert again.json()["code"] == "PAIRING_CODE_EXPIRED"


def test_a_new_code_replaces_the_previous_one(phone: TestClient, desktop: TestClient) -> None:
    first = _code(desktop)
    second = _code(desktop)
    rejected = phone.post(
        "/api/v1/mobile/pair", json={"code": first, "name": "Phone"}, headers=CHANGE_HEADERS
    )
    assert rejected.status_code == 400
    _pair(phone, second)


def test_an_expired_code_is_refused(
    phone: TestClient, desktop: TestClient, phone_app: FastAPI
) -> None:
    code = _code(desktop)
    with phone_app.state.database.session_factory() as db:
        record = db.scalars(select(MobilePairingCode)).one()
        record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    response = phone.post(
        "/api/v1/mobile/pair", json={"code": code, "name": "Phone"}, headers=CHANGE_HEADERS
    )
    assert response.json()["code"] == "PAIRING_CODE_EXPIRED"


def test_five_wrong_codes_cancel_the_code(phone: TestClient, desktop: TestClient) -> None:
    code = _code(desktop)
    for remaining in (4, 3, 2, 1, 0):
        wrong = phone.post(
            "/api/v1/mobile/pair",
            json={"code": "AAAA-AAAA", "name": "Phone"},
            headers=CHANGE_HEADERS,
        )
        assert wrong.json()["code"] == "PAIRING_CODE_WRONG"
        assert wrong.json()["details"]["attempts_remaining"] == remaining
    right_but_too_late = phone.post(
        "/api/v1/mobile/pair", json={"code": code, "name": "Phone"}, headers=CHANGE_HEADERS
    )
    assert right_but_too_late.json()["code"] == "PAIRING_CODE_EXPIRED"


def test_repeated_failures_lock_pairing(phone: TestClient, desktop: TestClient) -> None:
    for _ in range(20):
        _code(desktop)
        phone.post(
            "/api/v1/mobile/pair",
            json={"code": "AAAA-AAAA", "name": "Phone"},
            headers=CHANGE_HEADERS,
        )
    locked = phone.post(
        "/api/v1/mobile/pair",
        json={"code": _code(desktop), "name": "Phone"},
        headers=CHANGE_HEADERS,
    )
    assert locked.status_code == 429
    assert locked.json()["code"] == "PAIRING_LOCKED"


def test_pairing_is_only_on_the_gateway(desktop: TestClient) -> None:
    response = desktop.post("/api/v1/mobile/pair", json={"code": _code(desktop), "name": "PC"})
    assert response.status_code == 404


# Devices


def test_revoking_a_phone_locks_it_out_at_once(phone: TestClient, desktop: TestClient) -> None:
    device_id = _paired(phone, desktop)
    assert phone.get("/api/v1/leads").status_code == 200
    listed = desktop.get("/api/v1/mobile/devices").json()
    assert [device["id"] for device in listed] == [device_id]
    assert desktop.get("/api/v1/mobile/status").json()["paired_devices"] == 1

    assert desktop.post(f"/api/v1/mobile/devices/{device_id}/revoke").status_code == 204
    assert phone.get("/api/v1/leads").status_code == 401
    assert desktop.get("/api/v1/mobile/devices").json() == []


def test_revoke_all(phone: TestClient, desktop: TestClient) -> None:
    _paired(phone, desktop)
    response = desktop.post("/api/v1/mobile/devices/revoke-all")
    assert response.json() == {"revoked": 1}
    assert phone.get("/api/v1/leads").status_code == 401


def test_a_phone_unused_for_thirty_days_must_pair_again(
    phone: TestClient, desktop: TestClient, phone_app: FastAPI
) -> None:
    _paired(phone, desktop)
    with phone_app.state.database.session_factory() as db:
        device = db.scalars(select(MobileDevice)).one()
        device.last_seen_at = datetime.now(UTC) - timedelta(days=31)
        db.commit()
    assert phone.get("/api/v1/leads").status_code == 401


def test_signing_out_revokes_this_phone(phone: TestClient, desktop: TestClient) -> None:
    _paired(phone, desktop)
    assert phone.post("/api/v1/mobile/sign-out", headers=CHANGE_HEADERS).status_code == 204
    assert phone.get("/api/v1/mobile/session").status_code == 401
    assert desktop.get("/api/v1/mobile/devices").json() == []


def test_a_forged_cookie_is_refused(phone: TestClient, desktop: TestClient) -> None:
    device_id = _paired(phone, desktop)
    phone.cookies.clear()
    phone.cookies.set(COOKIE_NAME, f"{device_id}.not-the-secret", domain=PHONE_HOST, path="/api")
    assert phone.get("/api/v1/leads").status_code == 401


# Route policy

# Every route a phone may not use. A new route is either added here or allowed on purpose.
DESKTOP_ONLY_ROUTES = {
    ("POST", "/api/v1/backups"),
    ("POST", "/api/v1/backups/verify"),
    ("POST", "/api/v1/catalogue/enrichment/run"),
    ("POST", "/api/v1/catalogue/import/enrichment"),
    ("POST", "/api/v1/catalogue/import/shopify"),
    ("PATCH", "/api/v1/catalogue/knowledge-notes/{note_id}"),
    ("POST", "/api/v1/catalogue/product-families"),
    ("PATCH", "/api/v1/catalogue/product-families/{family_id}"),
    ("DELETE", "/api/v1/catalogue/product-families/{family_id}"),
    ("POST", "/api/v1/catalogue/products"),
    ("PATCH", "/api/v1/catalogue/products/{product_id}"),
    ("PATCH", "/api/v1/catalogue/proven-fits/{fit_id}"),
    ("GET", "/api/v1/leads/export"),
    ("DELETE", "/api/v1/leads/{lead_id}"),
    ("PATCH", "/api/v1/scoring/profiles/{segment}"),
    ("PUT", "/api/v1/system/cloud-polish"),
    ("DELETE", "/api/v1/system/cloud-polish"),
    ("GET", "/api/v1/system/diagnostics"),
    ("PUT", "/api/v1/system/providers/meta"),
    ("DELETE", "/api/v1/system/providers/meta"),
    ("POST", "/api/v1/system/providers/meta/account"),
    ("POST", "/api/v1/system/providers/meta/authorize"),
    ("POST", "/api/v1/system/providers/meta/disconnect"),
    ("PATCH", "/api/v1/system/settings"),
    ("POST", "/api/v1/system/shutdown"),
    ("POST", "/api/v1/templates"),
    ("PATCH", "/api/v1/templates/{template_id}"),
    ("DELETE", "/api/v1/templates/{template_id}"),
    ("GET", "/api/v1/mobile/status"),
    ("PATCH", "/api/v1/mobile/config"),
    ("POST", "/api/v1/mobile/pairing-codes"),
    ("GET", "/api/v1/mobile/devices"),
    ("POST", "/api/v1/mobile/devices/revoke-all"),
    ("POST", "/api/v1/mobile/devices/{device_id}/revoke"),
    ("GET", "/api/v1/openapi.json"),
    ("GET", "/api/v1/mobile/tailscale"),
    ("POST", "/api/v1/catalogue/shopify/sync"),
    ("PUT", "/api/v1/system/providers/shopify"),
    ("DELETE", "/api/v1/system/providers/shopify"),
    ("POST", "/api/v1/system/providers/shopify/test"),
    ("POST", "/api/v1/mobile/tailscale/serve"),
    ("DELETE", "/api/v1/mobile/tailscale/serve"),
}


def _api_routes(app: FastAPI) -> list[tuple[str, str, APIRoute]]:
    found: list[tuple[str, str, APIRoute]] = []
    for entry in app.routes:
        routes = (
            [entry]
            if isinstance(entry, APIRoute)
            else list(getattr(entry, "original_router").routes)  # noqa: B009 -- FastAPI internal
        )
        for route in routes:
            assert isinstance(route, APIRoute)
            path = route.path if route.path.startswith("/api/") else f"/api/v1{route.path}"
            for method in (route.methods or set()) - {"HEAD"}:
                found.append((method, path, route))
    return found


def _is_desktop_only(route: APIRoute) -> bool:
    return any(dependency.call is require_desktop for dependency in route.dependant.dependencies)


def test_every_route_is_classified_for_phones(phone_app: FastAPI) -> None:
    routes = _api_routes(phone_app)
    assert len(routes) > 100
    marked = {(method, path) for method, path, route in routes if _is_desktop_only(route)}
    assert marked == DESKTOP_ONLY_ROUTES


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/leads/export"),
        ("POST", "/api/v1/backups"),
        ("PATCH", "/api/v1/system/settings"),
        ("POST", "/api/v1/mobile/pairing-codes"),
        ("POST", "/api/v1/templates"),
    ],
)
def test_desktop_only_routes_refuse_a_paired_phone(
    phone: TestClient, desktop: TestClient, method: str, path: str
) -> None:
    _paired(phone, desktop)
    response = phone.request(method, path, json={}, headers=CHANGE_HEADERS)
    assert response.status_code == 403
    assert response.json()["code"] == "DESKTOP_ONLY"


def test_a_paired_phone_can_read_settings_and_the_catalogue(
    phone: TestClient, desktop: TestClient
) -> None:
    _paired(phone, desktop)
    assert phone.get("/api/v1/system/settings").status_code == 200
    assert phone.get("/api/v1/catalogue/products").status_code == 200
    assert phone.get("/api/v1/templates").status_code == 200


# Request checks and headers


def test_a_foreign_host_is_refused(phone_app: FastAPI, desktop: TestClient) -> None:
    gateway = phone_app.state.mobile_access_service.manager.gateway
    with TestClient(gateway, base_url="https://attacker.example") as client:
        response = client.get("/api/v1/mobile/session")
    assert response.status_code == 421
    assert response.json()["code"] == "HOST_NOT_ALLOWED"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": PHONE_ORIGIN},
        {"X-ENS-Request": "1"},
        {"Origin": "https://attacker.example", "X-ENS-Request": "1"},
    ],
)
def test_a_change_needs_the_origin_and_request_header(
    phone: TestClient, desktop: TestClient, headers: dict[str, str]
) -> None:
    _paired(phone, desktop)
    response = phone.post(
        "/api/v1/leads/00000000-0000-0000-0000-000000000000/notes",
        json={"content": "x"},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_REJECTED"


def test_api_responses_are_not_cached_and_carry_a_strict_policy(
    phone: TestClient, desktop: TestClient
) -> None:
    _paired(phone, desktop)
    response = phone.get("/api/v1/leads")
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"


# The phone app files


def test_the_app_is_served_with_screens_falling_back_to_the_page(phone: TestClient) -> None:
    page = phone.get("/")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["cache-control"] == "no-cache"
    assert phone.get("/pair").text == page.text

    script = phone.get("/assets/index-abc123.js")
    assert script.headers["content-type"].startswith("text/javascript")
    assert "immutable" in script.headers["cache-control"]

    assert phone.get("/assets/missing.js").status_code == 404
    assert phone.post("/", headers=CHANGE_HEADERS).status_code == 405


def test_files_outside_the_app_cannot_be_reached(phone: TestClient) -> None:
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        response = phone.get(path)
        assert "outside the app" not in response.text


def test_missing_app_files_are_explained(settings: Settings, tmp_path: Path) -> None:
    app = create_app(settings.model_copy(update={"mobile_frontend_directory": tmp_path / "none"}))
    gateway = app.state.mobile_access_service.manager.gateway
    with TestClient(app, headers={"X-Session-Token": SESSION_TOKEN}) as desktop:
        assert desktop.get("/api/v1/mobile/status").json()["phone_app_ready"] is False
        with TestClient(gateway, base_url="http://127.0.0.1:8770") as client:
            response = client.get("/")
    assert response.status_code == 503
    assert "frontend:build" in response.text


# Attribution


def test_changes_from_a_phone_are_attributed_to_it(
    phone: TestClient,
    desktop: TestClient,
    phone_app: FastAPI,
    campaign_payload: dict[str, object],
) -> None:
    device_id = _paired(phone, desktop)
    campaign = desktop.post("/api/v1/campaigns", json=campaign_payload).json()
    lead = desktop.post("/api/v1/leads", json=lead_payload(campaign["id"]))
    assert lead.status_code == 201, lead.text
    lead_id = lead.json()["id"]
    note = phone.post(
        f"/api/v1/leads/{lead_id}/notes",
        json={"content": "Asked for samples"},
        headers=CHANGE_HEADERS,
    )
    assert note.status_code in (200, 201), note.text
    with phone_app.state.database.session_factory() as db:
        stored = db.scalars(select(LeadNote).where(LeadNote.lead_id == lead_id)).one()
        assert stored.actor == f"phone:{device_id}"
        created = db.scalars(select(AuditEvent).where(AuditEvent.action == "lead.created")).one()
        assert created.actor == "local_user"
        paired = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "mobile.device_paired")
        ).one()
        assert paired.entity_id == device_id


# Tailscale


class _FakeTailscale:
    def __init__(self, *, installed: bool = True, running: bool = True) -> None:
        self.installed = installed
        self.running = running
        self.serving = False

    def state(self, gateway_port: int) -> TailscaleState:
        return TailscaleState(
            installed=self.installed,
            running=self.running,
            dns_name="my-pc.tail9z8y.ts.net" if self.running else "",
            serving=self.serving,
        )

    def serve(self, gateway_port: int) -> None:
        self.serving = True

    def stop_serving(self) -> None:
        self.serving = False


def test_setting_up_tailscale_saves_the_phone_address(
    desktop: TestClient, phone_app: FastAPI
) -> None:
    fake = _FakeTailscale()
    phone_app.state.tailscale_client = fake
    response = desktop.post("/api/v1/mobile/tailscale/serve")
    assert response.status_code == 200
    assert response.json()["serving"] is True
    status = desktop.get("/api/v1/mobile/status").json()
    assert status["public_host"] == "my-pc.tail9z8y.ts.net"
    assert phone_app.state.mobile_access_service.manager.gateway.public_host == (
        "my-pc.tail9z8y.ts.net"
    )
    assert desktop.delete("/api/v1/mobile/tailscale/serve").json()["serving"] is False


def test_tailscale_must_be_signed_in_first(desktop: TestClient, phone_app: FastAPI) -> None:
    phone_app.state.tailscale_client = _FakeTailscale(running=False)
    response = desktop.post("/api/v1/mobile/tailscale/serve")
    assert response.status_code == 409
    assert response.json()["code"] == "TAILSCALE_NOT_RUNNING"


def test_tailscale_status_links_to_the_installer(desktop: TestClient, phone_app: FastAPI) -> None:
    phone_app.state.tailscale_client = _FakeTailscale(installed=False, running=False)
    body = desktop.get("/api/v1/mobile/tailscale").json()
    assert body["installed"] is False
    assert body["install_url"].startswith("https://tailscale.com/")


def test_tailscale_waiting_for_approval_returns_the_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tailscale prints an approval link and waits when Serve isn't enabled; the app must answer
    with the link instead of failing (found on the operator's PC, 2 November 2026)."""
    from app.core.errors import DomainError
    from app.domains.mobile import tailscale

    link = "https://login.tailscale.com/f/serve?node=example123"

    def waiting(*_: object, **__: object) -> object:
        raise subprocess.TimeoutExpired(
            cmd="tailscale serve",
            timeout=8,
            output=f"Serve is not enabled on your tailnet.\nTo enable, visit:\n{link}\n".encode(),
        )

    monkeypatch.setattr(tailscale, "_executable", lambda: "tailscale")
    monkeypatch.setattr(subprocess, "run", waiting)
    with pytest.raises(DomainError) as raised:
        tailscale.TailscaleClient().serve(8770)
    assert raised.value.code == "TAILSCALE_SERVE_FAILED"
    assert raised.value.details == {"admin_url": link}
