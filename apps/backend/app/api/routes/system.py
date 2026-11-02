import logging
from typing import Any, cast

from fastapi import APIRouter, Request, status

from app.api.dependencies import DESKTOP_ONLY, Authenticated, DatabaseSession
from app.core.config import Settings
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.catalogue.shopify_connection import (
    ShopifyConnectionRead,
    ShopifyConnectionService,
    ShopifyConnectionWrite,
    ShopifyTestResult,
)
from app.domains.system.cloud_polish import CloudPolishConfigurationService
from app.domains.system.cloud_polish_schemas import (
    CloudPolishConfigurationWrite,
    CloudPolishStatusRead,
)
from app.domains.system.meta import MetaConnectionService
from app.domains.system.meta_schemas import (
    MetaAccountSelect,
    MetaAuthorizationStartRead,
    MetaConfigurationWrite,
    MetaConnectionRead,
)
from app.domains.system.schemas import (
    DiagnosticsRead,
    OperationsSummary,
    WorkspaceSettings,
    WorkspaceSettingsUpdate,
)
from app.domains.system.service import SystemService

router = APIRouter(prefix="/system", tags=["system"])
service = SystemService()
logger = logging.getLogger(__name__)


def _meta(request: Request) -> MetaConnectionService:
    return cast(MetaConnectionService, request.app.state.meta_connection_service)


def _cloud_polish(request: Request) -> CloudPolishConfigurationService:
    return cast(
        CloudPolishConfigurationService, request.app.state.cloud_polish_configuration_service
    )


@router.get("/settings", response_model=WorkspaceSettings)
def get_settings(_: Authenticated, session: DatabaseSession) -> WorkspaceSettings:
    return service.get_settings(session)


@router.patch("/settings", dependencies=[DESKTOP_ONLY], response_model=WorkspaceSettings)
def update_settings(
    data: WorkspaceSettingsUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> WorkspaceSettings:
    updated = service.update_settings(session, data, request.state.correlation_id)
    manager = cast(
        CampaignAssistantManager,
        request.app.state.campaign_assistant_manager,
    )
    manager.set_protection_enabled(updated.protect_design_software_resources)
    manager.set_preferred_model(updated.local_ai_model)
    return updated


@router.get("/diagnostics", dependencies=[DESKTOP_ONLY], response_model=DiagnosticsRead)
def get_diagnostics(
    request: Request, _: Authenticated, session: DatabaseSession
) -> DiagnosticsRead:
    runtime_settings: Settings = request.app.state.settings
    return service.diagnostics(session, runtime_settings)


@router.get("/summary", response_model=OperationsSummary)
def get_operations_summary(_: Authenticated, session: DatabaseSession) -> OperationsSummary:
    return service.operations_summary(session)


@router.get("/providers/meta", response_model=MetaConnectionRead)
def get_meta_connection(request: Request, _: Authenticated) -> MetaConnectionRead:
    return _meta(request).status()


@router.get("/cloud-polish", response_model=CloudPolishStatusRead)
def get_cloud_polish(
    request: Request, _: Authenticated, session: DatabaseSession
) -> CloudPolishStatusRead:
    return _cloud_polish(request).status(service.get_settings(session))


@router.put("/cloud-polish", dependencies=[DESKTOP_ONLY], response_model=CloudPolishStatusRead)
def configure_cloud_polish(
    data: CloudPolishConfigurationWrite,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CloudPolishStatusRead:
    return _cloud_polish(request).configure(
        data.api_key.get_secret_value(), service.get_settings(session)
    )


@router.delete("/cloud-polish", dependencies=[DESKTOP_ONLY], response_model=CloudPolishStatusRead)
def remove_cloud_polish(
    request: Request, _: Authenticated, session: DatabaseSession
) -> CloudPolishStatusRead:
    return _cloud_polish(request).remove(service.get_settings(session))


def _shopify(request: Request) -> ShopifyConnectionService:
    return cast(ShopifyConnectionService, request.app.state.shopify_connection_service)


@router.get("/providers/shopify", response_model=ShopifyConnectionRead)
def get_shopify_connection(request: Request, _: Authenticated) -> ShopifyConnectionRead:
    return _shopify(request).status()


@router.put("/providers/shopify", dependencies=[DESKTOP_ONLY], response_model=ShopifyConnectionRead)
def configure_shopify_connection(
    data: ShopifyConnectionWrite, request: Request, _: Authenticated
) -> ShopifyConnectionRead:
    return _shopify(request).configure(data)


@router.delete(
    "/providers/shopify", dependencies=[DESKTOP_ONLY], response_model=ShopifyConnectionRead
)
def remove_shopify_connection(request: Request, _: Authenticated) -> ShopifyConnectionRead:
    return _shopify(request).remove()


@router.post(
    "/providers/shopify/test", dependencies=[DESKTOP_ONLY], response_model=ShopifyTestResult
)
def test_shopify_connection(request: Request, _: Authenticated) -> ShopifyTestResult:
    return _shopify(request).test()


@router.put("/providers/meta", dependencies=[DESKTOP_ONLY], response_model=MetaConnectionRead)
def configure_meta(
    data: MetaConfigurationWrite, request: Request, _: Authenticated
) -> MetaConnectionRead:
    return _meta(request).configure(data)


@router.delete("/providers/meta", dependencies=[DESKTOP_ONLY], response_model=MetaConnectionRead)
def remove_meta_configuration(request: Request, _: Authenticated) -> MetaConnectionRead:
    return _meta(request).remove_configuration()


@router.post(
    "/providers/meta/authorize",
    dependencies=[DESKTOP_ONLY],
    response_model=MetaAuthorizationStartRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_meta_authorization(request: Request, _: Authenticated) -> MetaAuthorizationStartRead:
    return _meta(request).start_authorization()


@router.post(
    "/providers/meta/account", dependencies=[DESKTOP_ONLY], response_model=MetaConnectionRead
)
def select_meta_account(
    data: MetaAccountSelect, request: Request, _: Authenticated
) -> MetaConnectionRead:
    return _meta(request).select_account(data.page_id)


@router.post(
    "/providers/meta/disconnect", dependencies=[DESKTOP_ONLY], response_model=MetaConnectionRead
)
def disconnect_meta(request: Request, _: Authenticated) -> MetaConnectionRead:
    return _meta(request).disconnect()


@router.post("/shutdown", dependencies=[DESKTOP_ONLY], status_code=status.HTTP_202_ACCEPTED)
def request_shutdown(request: Request, _: Authenticated) -> dict[str, bool]:
    """Let the desktop host stop the backend cleanly, so lifespan shutdown runs before exit.

    Accepted only from the authenticated host. Without a managed server (in tests) nothing stops.
    """
    server: Any = getattr(request.app.state, "server", None)
    if server is None:
        logger.info("Shutdown requested without a managed server; ignored")
        return {"stopping": False}
    logger.info("Shutdown requested by the desktop host")
    server.should_exit = True
    return {"stopping": True}
