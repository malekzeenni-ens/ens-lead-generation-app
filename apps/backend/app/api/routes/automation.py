from typing import Annotated, cast

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import Authenticated, DatabaseSession
from app.domains.automation.manager import CampaignRunManager
from app.domains.automation.schemas import (
    CampaignRunAllStart,
    CampaignRunRead,
    CampaignRunStart,
    CandidateDecision,
    DiscoveryCandidateRead,
    InstagramCampaignEnrichment,
    InstagramProfileImport,
    InstagramProfileLookup,
    InstagramProfileRead,
    ProviderCapabilityRead,
    SocialCandidateCapture,
)
from app.domains.automation.service import CampaignAutomationService

router = APIRouter(tags=["campaign automation"])


def _manager(request: Request) -> CampaignRunManager:
    return cast(CampaignRunManager, request.app.state.campaign_run_manager)


@router.get("/campaign-runs/capabilities", response_model=ProviderCapabilityRead)
def capabilities(request: Request, _: Authenticated) -> ProviderCapabilityRead:
    settings = request.app.state.settings
    meta = request.app.state.meta_connection_service.status()
    return ProviderCapabilityRead(
        google_places_configured=settings.google_places_enabled,
        instagram_configured=meta.configured,
        instagram_connected=meta.connected,
        instagram_account=(
            meta.selected_account.instagram_username if meta.selected_account else None
        ),
        instagram_status=meta.status,
        public_registries_available=True,
        maximum_results_per_campaign=settings.discovery_max_results,
        maximum_queries_per_campaign=settings.discovery_max_queries,
    )


@router.post("/campaign-runs", response_model=CampaignRunRead, status_code=status.HTTP_202_ACCEPTED)
def start_campaign_run(
    data: CampaignRunStart,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignRunRead:
    run_id = _manager(request).queue_one(
        data.campaign_id,
        data.provider,
        request.state.correlation_id,
    )
    return CampaignAutomationService(request.app.state.settings).get_run(session, run_id)


@router.post(
    "/campaign-runs/all",
    response_model=list[CampaignRunRead],
    status_code=status.HTTP_202_ACCEPTED,
)
def start_all_campaign_runs(
    data: CampaignRunAllStart,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> list[CampaignRunRead]:
    run_ids = _manager(request).queue_all(data.provider, request.state.correlation_id)
    service = CampaignAutomationService(request.app.state.settings)
    return [service.get_run(session, run_id) for run_id in run_ids]


@router.post(
    "/social-candidates",
    response_model=CampaignRunRead,
    status_code=status.HTTP_201_CREATED,
)
def capture_social_candidate(
    data: SocialCandidateCapture,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignRunRead:
    return CampaignAutomationService(request.app.state.settings).capture_social_candidate(
        session, data, request.state.correlation_id
    )


@router.post("/instagram/profiles/preview", response_model=InstagramProfileRead)
def preview_instagram_profile(
    data: InstagramProfileLookup,
    request: Request,
    _: Authenticated,
) -> InstagramProfileRead:
    service = CampaignAutomationService(
        request.app.state.settings,
        instagram_provider=_manager(request).instagram_provider,
    )
    return service.preview_instagram_profile(str(data.profile_url))


@router.post(
    "/instagram/profiles/import",
    response_model=CampaignRunRead,
    status_code=status.HTTP_201_CREATED,
)
def import_instagram_profile(
    data: InstagramProfileImport,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignRunRead:
    service = CampaignAutomationService(
        request.app.state.settings,
        instagram_provider=_manager(request).instagram_provider,
    )
    return service.import_instagram_profile(
        session,
        data.campaign_id,
        str(data.profile_url),
        request.state.correlation_id,
    )


@router.post(
    "/instagram/profiles/enrich-known",
    response_model=CampaignRunRead,
    status_code=status.HTTP_201_CREATED,
)
def enrich_known_instagram_profiles(
    data: InstagramCampaignEnrichment,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignRunRead:
    service = CampaignAutomationService(
        request.app.state.settings,
        instagram_provider=_manager(request).instagram_provider,
    )
    return service.enrich_known_instagram_profiles(
        session,
        data.campaign_id,
        request.state.correlation_id,
    )


@router.get("/campaign-runs", response_model=list[CampaignRunRead])
def list_campaign_runs(
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
    campaign_id: Annotated[str | None, Query(min_length=36, max_length=36)] = None,
) -> list[CampaignRunRead]:
    return CampaignAutomationService(request.app.state.settings).list_runs(
        session, campaign_id=campaign_id
    )


@router.get("/campaign-runs/{run_id}", response_model=CampaignRunRead)
def get_campaign_run(
    run_id: str, request: Request, _: Authenticated, session: DatabaseSession
) -> CampaignRunRead:
    return CampaignAutomationService(request.app.state.settings).get_run(session, run_id)


@router.post("/campaign-runs/{run_id}/cancel", response_model=CampaignRunRead)
def cancel_campaign_run(
    run_id: str, request: Request, _: Authenticated, session: DatabaseSession
) -> CampaignRunRead:
    return CampaignAutomationService(request.app.state.settings).request_cancellation(
        session, run_id, request.state.correlation_id
    )


@router.post(
    "/discovery-candidates/{candidate_id}/decision",
    response_model=DiscoveryCandidateRead,
)
def decide_candidate(
    candidate_id: str,
    data: CandidateDecision,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> DiscoveryCandidateRead:
    return CampaignAutomationService(request.app.state.settings).decide_candidate(
        session, candidate_id, data, request.state.correlation_id
    )
