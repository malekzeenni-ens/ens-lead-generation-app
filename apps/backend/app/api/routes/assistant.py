from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.api.dependencies import Authenticated, DatabaseSession
from app.core.config import Settings
from app.domains.assistant.schemas import (
    AssistantConversationCreate,
    AssistantConversationRead,
    AssistantMessageCreate,
)
from app.domains.assistant.service import AssistantService
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.campaign_assistant.schemas import CampaignDraftRead
from app.domains.campaign_assistant.service import CampaignAssistantService
from app.domains.system.meta import MetaConnectionService
from app.domains.system.service import SystemService

router = APIRouter(prefix="/assistant", tags=["local assistant"])


def _manager(request: Request) -> CampaignAssistantManager:
    return cast(CampaignAssistantManager, request.app.state.campaign_assistant_manager)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _service(request: Request) -> AssistantService:
    return AssistantService(_manager(request), _settings(request))


@router.get("/conversations", response_model=list[AssistantConversationRead])
def list_conversations(
    request: Request, _: Authenticated, session: DatabaseSession
) -> list[AssistantConversationRead]:
    return _service(request).list(session)


@router.post("/conversations", response_model=AssistantConversationRead, status_code=201)
def create_conversation(
    data: AssistantConversationCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> AssistantConversationRead:
    return _service(request).create(session, data.title)


@router.get("/conversations/{conversation_id}", response_model=AssistantConversationRead)
def get_conversation(
    conversation_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> AssistantConversationRead:
    return _service(request).get(session, conversation_id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AssistantConversationRead,
)
def send_message(
    conversation_id: str,
    data: AssistantMessageCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> AssistantConversationRead:
    workspace_settings = SystemService().get_settings(session)
    meta = cast(MetaConnectionService, request.app.state.meta_connection_service)
    return _service(request).send(
        session,
        conversation_id=conversation_id,
        data=data,
        protect_resources=workspace_settings.protect_design_software_resources,
        instagram_connected=meta.status().connected,
        correlation_id=request.state.correlation_id,
    )


@router.get("/conversations/{conversation_id}/attachments/{attachment_id}")
def download_attachment(
    conversation_id: str,
    attachment_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> FileResponse:
    attachment, path = _service(request).attachment(session, conversation_id, attachment_id)
    return FileResponse(path, media_type=attachment.media_type, filename=attachment.filename)


@router.post(
    "/conversations/{conversation_id}/campaign-draft",
    response_model=CampaignDraftRead,
    status_code=201,
)
def create_campaign_draft_from_conversation(
    conversation_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignDraftRead:
    brief = _service(request).campaign_brief(session, conversation_id)
    workspace_settings = SystemService().get_settings(session)
    meta = cast(MetaConnectionService, request.app.state.meta_connection_service)
    return CampaignAssistantService(_manager(request), _settings(request)).generate(
        session,
        message=brief,
        workspace_settings=workspace_settings,
        instagram_connected=meta.status().connected,
        correlation_id=request.state.correlation_id,
    )
