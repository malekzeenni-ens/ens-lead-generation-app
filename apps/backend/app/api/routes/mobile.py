from typing import cast

from fastapi import APIRouter, Request

from app.api.dependencies import Authenticated, DatabaseSession, DesktopOnly
from app.domains.mobile.schemas import MobileAccessConfigUpdate, MobileAccessStatus
from app.domains.mobile.service import MobileAccessService

router = APIRouter(prefix="/mobile", tags=["mobile"])


def _service(request: Request) -> MobileAccessService:
    return cast(MobileAccessService, request.app.state.mobile_access_service)


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
