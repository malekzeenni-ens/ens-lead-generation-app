from typing import cast

from fastapi import APIRouter, Request, Response

from app.api.dependencies import Authenticated, DatabaseSession, DesktopOnly
from app.core.channel import is_phone, phone_device_id
from app.core.errors import DomainError
from app.db.models import MobileDevice
from app.domains.mobile.devices import COOKIE_MAX_AGE, COOKIE_NAME
from app.domains.mobile.schemas import (
    MobileAccessConfigUpdate,
    MobileAccessStatus,
    MobileDeviceRead,
    MobileSessionRead,
    PairingCodeRead,
    PairRequest,
    TailscaleStatusRead,
)
from app.domains.mobile.service import MobileAccessService
from app.domains.mobile.tailscale import INSTALL_URL, TailscaleClient

router = APIRouter(prefix="/mobile", tags=["mobile"])


def _service(request: Request) -> MobileAccessService:
    return cast(MobileAccessService, request.app.state.mobile_access_service)


def _tailscale(request: Request) -> TailscaleClient:
    return cast(TailscaleClient, request.app.state.tailscale_client)


def _tailscale_status(request: Request) -> TailscaleStatusRead:
    state = _tailscale(request).state(_service(request).manager.port)
    return TailscaleStatusRead(
        installed=state.installed,
        running=state.running,
        dns_name=state.dns_name,
        serving=state.serving,
        install_url=INSTALL_URL,
    )


@router.get("/tailscale", response_model=TailscaleStatusRead)
def get_tailscale(request: Request, _: Authenticated, __: DesktopOnly) -> TailscaleStatusRead:
    return _tailscale_status(request)


@router.post("/tailscale/serve", response_model=TailscaleStatusRead)
def start_tailscale_serve(
    request: Request, _: Authenticated, __: DesktopOnly, session: DatabaseSession
) -> TailscaleStatusRead:
    """Map this PC's Tailscale HTTPS address to the gateway and remember the name."""
    service = _service(request)
    state = _tailscale(request).state(service.manager.port)
    if not state.running or not state.dns_name:
        raise DomainError(
            "TAILSCALE_NOT_RUNNING",
            "Tailscale is installed but not signed in. Open Tailscale and sign in, then try again.",
            status_code=409,
        )
    _tailscale(request).serve(service.manager.port)
    if service.config(session).public_host != state.dns_name:
        service.update(
            session,
            MobileAccessConfigUpdate(public_host=state.dns_name),
            request.state.correlation_id,
        )
    return _tailscale_status(request)


@router.delete("/tailscale/serve", response_model=TailscaleStatusRead)
def stop_tailscale_serve(
    request: Request, _: Authenticated, __: DesktopOnly
) -> TailscaleStatusRead:
    _tailscale(request).stop_serving()
    return _tailscale_status(request)


@router.get("/status", response_model=MobileAccessStatus)
def get_status(
    request: Request, _: Authenticated, __: DesktopOnly, session: DatabaseSession
) -> MobileAccessStatus:
    return _service(request).status(session)


@router.patch("/config", response_model=MobileAccessStatus)
def update_config(
    data: MobileAccessConfigUpdate,
    request: Request,
    _: Authenticated,
    __: DesktopOnly,
    session: DatabaseSession,
) -> MobileAccessStatus:
    return _service(request).update(session, data, request.state.correlation_id)


@router.post("/pairing-codes", response_model=PairingCodeRead, status_code=201)
def issue_pairing_code(
    request: Request, _: Authenticated, __: DesktopOnly, session: DatabaseSession
) -> PairingCodeRead:
    service = _service(request)
    issued = service.registry.issue_code(session, request.state.correlation_id)
    host = service.config(session).public_host
    return PairingCodeRead(
        code=issued.code,
        expires_at=issued.expires_at,
        # The code goes in the fragment, which browsers never send to a server.
        pair_url=f"https://{host}/pair#{issued.code}" if host else None,
    )


@router.get("/devices", response_model=list[MobileDeviceRead])
def list_devices(
    request: Request, _: Authenticated, __: DesktopOnly, session: DatabaseSession
) -> list[MobileDevice]:
    return _service(request).registry.list_devices(session)


@router.post("/devices/revoke-all", status_code=200)
def revoke_all_devices(
    request: Request, _: Authenticated, __: DesktopOnly, session: DatabaseSession
) -> dict[str, int]:
    count = _service(request).registry.revoke_all(session, request.state.correlation_id)
    return {"revoked": count}


@router.post("/devices/{device_id}/revoke", status_code=204)
def revoke_device(
    device_id: str,
    request: Request,
    _: Authenticated,
    __: DesktopOnly,
    session: DatabaseSession,
) -> Response:
    _service(request).registry.revoke(session, device_id, request.state.correlation_id)
    return Response(status_code=204)


@router.post("/pair", response_model=MobileSessionRead, status_code=201)
def pair_phone(
    data: PairRequest, request: Request, response: Response, session: DatabaseSession
) -> MobileSessionRead:
    """The one route a phone may call before it is paired. It exists only on the gateway."""
    if not is_phone(request):
        raise DomainError("PHONE_ONLY", "Pairing is done from the phone.", status_code=404)
    paired = _service(request).registry.pair(
        session,
        code=data.code,
        name=data.name,
        label=data.label,
        correlation_id=request.state.correlation_id,
    )
    response.set_cookie(
        COOKIE_NAME,
        paired.cookie_value,
        max_age=COOKIE_MAX_AGE,
        path="/api",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return MobileSessionRead(channel="phone", device=MobileDeviceRead.model_validate(paired.device))


@router.get("/session", response_model=MobileSessionRead)
def get_session(request: Request, _: Authenticated, session: DatabaseSession) -> MobileSessionRead:
    """Which phone this is, so the app can say "Signed in as …". 401 means "pair first"."""
    device_id = phone_device_id(request)
    if device_id is None:
        return MobileSessionRead(channel="desktop", device=None)
    device = session.get(MobileDevice, device_id)
    return MobileSessionRead(
        channel="phone",
        device=MobileDeviceRead.model_validate(device) if device else None,
    )


@router.post("/sign-out", status_code=204)
def sign_out(request: Request, _: Authenticated, session: DatabaseSession) -> Response:
    """Forget this phone: its credential is revoked, not only the cookie removed."""
    device_id = phone_device_id(request)
    if device_id is None:
        raise DomainError("PHONE_ONLY", "Signing out is done from the phone.", status_code=404)
    _service(request).registry.revoke(session, device_id, request.state.correlation_id)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path="/api", secure=True, httponly=True, samesite="strict")
    return response
