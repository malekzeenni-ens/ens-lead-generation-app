from typing import cast

from fastapi import APIRouter, Request

from app.api.dependencies import Authenticated, DatabaseSession
from app.api.routes.jobs import job_manager
from app.core.config import Settings
from app.domains.campaign_assistant.gate import require_local_ai_enabled
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.lead_assistant.schemas import (
    LeadAutofillRequest,
    LeadBriefingResponse,
    LeadFilterTranslateRequest,
    LeadFilterTranslateResult,
    StalledLeadDigestRequest,
    StalledLeadDigestResponse,
)
from app.domains.lead_assistant.service import LeadAssistantService
from app.domains.system.service import SystemService
from app.jobs.kinds import LEAD_AUTOFILL
from app.jobs.schemas import BackgroundJobRead

router = APIRouter(prefix="/lead-assistant", tags=["lead-assistant"])
service = LeadAssistantService()


def _manager(request: Request) -> CampaignAssistantManager:
    return cast(CampaignAssistantManager, request.app.state.campaign_assistant_manager)


def _runtime_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.post("/search-filter", response_model=LeadFilterTranslateResult)
def translate_filter(
    data: LeadFilterTranslateRequest,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadFilterTranslateResult:
    return service.translate_filter(
        session,
        data,
        manager=_manager(request),
        runtime_settings=_runtime_settings(request),
        workspace_settings=SystemService().get_settings(session),
    )


@router.post("/leads/{lead_id}/briefing", response_model=LeadBriefingResponse)
def brief_lead(
    lead_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadBriefingResponse:
    return service.brief(
        session,
        lead_id,
        manager=_manager(request),
        runtime_settings=_runtime_settings(request),
        workspace_settings=SystemService().get_settings(session),
    )


@router.post("/autofill", response_model=BackgroundJobRead, status_code=202)
def autofill_leads(
    data: LeadAutofillRequest,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> BackgroundJobRead:
    """Queue context suggestions for up to 20 leads; poll the returned job for the result."""
    require_local_ai_enabled(_runtime_settings(request), SystemService().get_settings(session))
    return job_manager(request).submit(
        session, LEAD_AUTOFILL, data.model_dump(mode="json"), request.state.correlation_id
    )


@router.post("/stalled-digest", response_model=StalledLeadDigestResponse)
def stalled_digest(
    data: StalledLeadDigestRequest,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> StalledLeadDigestResponse:
    return service.stalled_digest(
        session,
        data,
        manager=_manager(request),
        runtime_settings=_runtime_settings(request),
        workspace_settings=SystemService().get_settings(session),
    )
