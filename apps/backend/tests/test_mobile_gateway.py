from __future__ import annotations

import socket
from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import SESSION_TOKEN


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def gateway_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"mobile_gateway_port": _free_port()})


@pytest.fixture
def gateway_app(gateway_settings: Settings) -> FastAPI:
    return create_app(gateway_settings)


@pytest.fixture
def desktop(gateway_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(gateway_app, headers={"X-Session-Token": SESSION_TOKEN}) as client:
        yield client


def _enable(desktop: TestClient, enabled: bool) -> dict[str, object]:
    response = desktop.patch("/api/v1/mobile/config", json={"enabled": enabled})
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_phone_access_is_off_by_default(desktop: TestClient) -> None:
    status = desktop.get("/api/v1/mobile/status").json()
    assert status["enabled"] is False
    assert status["running"] is False
    assert status["phone_url"] is None


def test_switching_on_starts_a_loopback_listener_that_refuses_the_session_token(
    desktop: TestClient, gateway_app: FastAPI, gateway_settings: Settings
) -> None:
    status = _enable(desktop, True)
    assert status["running"] is True
    assert gateway_app.state.mobile_access_service.manager.wait_until_serving()

    url = f"http://127.0.0.1:{gateway_settings.mobile_gateway_port}/api/v1/health"
    # The phone channel never accepts the desktop token, so it cannot be replayed through it.
    response = httpx.get(url, headers={"X-Session-Token": SESSION_TOKEN})
    assert response.status_code == 401
    assert response.json()["code"] == "PHONE_NOT_PAIRED"

    status = _enable(desktop, False)
    assert status["running"] is False
    # Windows retries a refused connection for about two seconds, so this may time out instead.
    with pytest.raises(httpx.TransportError):
        httpx.get(url, timeout=2)
    # The desktop listener is unaffected.
    assert desktop.get("/api/v1/health").status_code == 200


def test_the_switch_survives_a_restart(gateway_settings: Settings) -> None:
    first = create_app(gateway_settings)
    with TestClient(first, headers={"X-Session-Token": SESSION_TOKEN}) as client:
        _enable(client, True)
    second = create_app(gateway_settings)
    with TestClient(second, headers={"X-Session-Token": SESSION_TOKEN}) as client:
        assert client.get("/api/v1/mobile/status").json()["running"] is True
        _enable(client, False)


def test_a_port_clash_is_reported_instead_of_failing(
    desktop: TestClient, gateway_settings: Settings
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupier:
        occupier.bind(("127.0.0.1", gateway_settings.mobile_gateway_port))
        occupier.listen()
        status = _enable(desktop, True)
    assert status["enabled"] is True
    assert status["running"] is False
    assert "already in use" in str(status["error"])


def test_phone_address_must_be_a_tailscale_name(desktop: TestClient) -> None:
    bad = desktop.patch("/api/v1/mobile/config", json={"public_host": "evil.example.com"})
    assert bad.status_code == 422
    good = desktop.patch("/api/v1/mobile/config", json={"public_host": "ENS-PC.tail1a2b.ts.net."})
    assert good.json()["public_host"] == "ens-pc.tail1a2b.ts.net"
    assert good.json()["phone_url"] == "https://ens-pc.tail1a2b.ts.net/"


def test_gateway_port_is_validated() -> None:
    with pytest.raises(ValueError):
        Settings(mobile_gateway_port=80)
