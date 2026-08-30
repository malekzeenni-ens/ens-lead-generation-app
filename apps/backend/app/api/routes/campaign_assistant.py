from typing import Annotated, cast

from fastapi import APIRouter, Query, Request

from app.api.dependencies import Authenticated, DatabaseSession
from app.core.config import Settings
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.campaign_assistant.schemas import (
    AssistantStatusRead,
    CampaignDraftApproval,
    CampaignDraftApprovalResult,
    CampaignDraftGenerate,
    CampaignDraftManualUpdate,
    CampaignDraftMessage,
    CampaignDraftRead,
    DraftStatus,
    OverrideDecision,
)
from app.domains.campaign_assistant.service import CampaignAssistantService
from app.domains.system.meta import MetaConnectionService
from app.domains.system.service import SystemService

router = APIRouter(prefix="/campaign-assistant", tags=["campaign assistant"])


def _manager(request: Request) -> CampaignAssistantManager:
    return cast(CampaignAssistantManager, request.app.state.campaign_assistant_manager)


def _meta(request: Request) -> MetaConnectionService:
    return cast(MetaConnectionService, request.app.state.meta_connection_service)


def _service(request: Request) -> CampaignAssistantService:
    settings = cast(Settings, request.app.state.settings)
    return CampaignAssistantService(_manager(request), settings)


@router.get("/status", response_model=AssistantStatusRead)
def assistant_status(
    request: Request, _: Authenticated, session: DatabaseSession
) -> AssistantStatusRead:
    workspace_settings = SystemService().get_settings(session)
    return _service(request).status(workspace_settings)


@router.post("/drafts", response_model=CampaignDraftRead, status_code=201)
def generate_draft(
    data: CampaignDraftGenerate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignDraftRead:
    return _service(request).generate(
        session,
        message=data.message,
        workspace_settings=SystemService().get_settings(session),
        instagram_connected=_meta(request).status().connected,
        correlation_id=request.state.correlation_id,
    )


@router.get("/drafts", response_model=list[CampaignDraftRead])
def list_drafts(
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
    draft_status: Annotated[DraftStatus | None, Query(alias="status")] = None,
) -> list[CampaignDraftRead]:
    return _service(request).list_drafts(
        session, status=draft_status.value if draft_status is not None else None
    )


@router.get("/drafts/{draft_id}", response_model=CampaignDraftRead)
def get_draft(
    draft_id: str, request: Request, _: Authenticated, session: DatabaseSession
) -> CampaignDraftRead:
    return _service(request).get(session, draft_id)


@router.post("/drafts/{draft_id}/messages", response_model=CampaignDraftRead)
def refine_draft(
    draft_id: str,
    data: CampaignDraftMessage,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignDraftRead:
    return _service(request).message(
        session,
        draft_id=draft_id,
        message=data.message,
        expected_version=data.expected_version,
        workspace_settings=SystemService().get_settings(session),
        instagram_connected=_meta(request).status().connected,
        correlation_id=request.state.correlation_id,
    )


@router.patch("/drafts/{draft_id}", response_model=CampaignDraftRead)
def update_draft(
    draft_id: str,
    data: CampaignDraftManualUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignDraftRead:
    return _service(request).manual_update(
        session,
        draft_id,
        data,
        request.state.correlation_id,
        instagram_connected=_meta(request).status().connected,
    )


@router.post(
    "/drafts/{draft_id}/overrides/{override_id}/decision",
    response_model=CampaignDraftRead,
)
def decide_override(
    draft_id: str,
    override_id: str,
    data: OverrideDecision,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignDraftRead:
    return _service(request).decide_override(
        session,
        draft_id=draft_id,
        override_id=override_id,
        data=data,
        workspace_settings=SystemService().get_settings(session),
        instagram_connected=_meta(request).status().connected,
        correlation_id=request.state.correlation_id,
    )


@router.post("/drafts/{draft_id}/approve", response_model=CampaignDraftApprovalResult)
def approve_draft(
    draft_id: str,
    data: CampaignDraftApproval,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignDraftApprovalResult:
    return _service(request).approve(
        session,
        draft_id=draft_id,
        expected_version=data.expected_version,
        instagram_connected=_meta(request).status().connected,
        correlation_id=request.state.correlation_id,
    )


@router.post("/drafts/{draft_id}/discard", response_model=CampaignDraftRead)
def discard_draft(
    draft_id: str,
    data: CampaignDraftApproval,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignDraftRead:
    return _service(request).discard(
        session,
        draft_id,
        data.expected_version,
        request.state.correlation_id,
    )
