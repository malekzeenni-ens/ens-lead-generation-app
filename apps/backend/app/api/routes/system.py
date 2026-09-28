from typing import cast

from fastapi import APIRouter, Request, status

from app.api.dependencies import Authenticated, DatabaseSession
from app.core.config import Settings
from app.domains.campaign_assistant.manager import CampaignAssistantManager
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


def _meta(request: Request) -> MetaConnectionService:
    return cast(MetaConnectionService, request.app.state.meta_connection_service)


def _cloud_polish(request: Request) -> CloudPolishConfigurationService:
    return cast(
        CloudPolishConfigurationService, request.app.state.cloud_polish_configuration_service
    )


@router.get("/settings", response_model=WorkspaceSettings)
def get_settings(_: Authenticated, session: DatabaseSession) -> WorkspaceSettings:
    return service.get_settings(session)


@router.patch("/settings", response_model=WorkspaceSettings)
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


@router.get("/diagnostics", response_model=DiagnosticsRead)
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


@router.put("/cloud-polish", response_model=CloudPolishStatusRead)
def configure_cloud_polish(
    data: CloudPolishConfigurationWrite,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CloudPolishStatusRead:
    return _cloud_polish(request).configure(
        data.api_key.get_secret_value(), service.get_settings(session)
    )


@router.delete("/cloud-polish", response_model=CloudPolishStatusRead)
def remove_cloud_polish(
    request: Request, _: Authenticated, session: DatabaseSession
) -> CloudPolishStatusRead:
    return _cloud_polish(request).remove(service.get_settings(session))


@router.put("/providers/meta", response_model=MetaConnectionRead)
def configure_meta(
    data: MetaConfigurationWrite, request: Request, _: Authenticated
) -> MetaConnectionRead:
    return _meta(request).configure(data)


@router.delete("/providers/meta", response_model=MetaConnectionRead)
def remove_meta_configuration(request: Request, _: Authenticated) -> MetaConnectionRead:
    return _meta(request).remove_configuration()


@router.post(
    "/providers/meta/authorize",
    response_model=MetaAuthorizationStartRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_meta_authorization(request: Request, _: Authenticated) -> MetaAuthorizationStartRead:
    return _meta(request).start_authorization()


@router.post("/providers/meta/account", response_model=MetaConnectionRead)
def select_meta_account(
    data: MetaAccountSelect, request: Request, _: Authenticated
) -> MetaConnectionRead:
    return _meta(request).select_account(data.page_id)


@router.post("/providers/meta/disconnect", response_model=MetaConnectionRead)
def disconnect_meta(request: Request, _: Authenticated) -> MetaConnectionRead:
    return _meta(request).disconnect()
