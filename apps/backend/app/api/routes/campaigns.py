from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import Authenticated, DatabaseSession
from app.domains.campaigns.schemas import (
    CampaignCreate,
    CampaignDuplicate,
    CampaignRead,
    CampaignStatus,
    CampaignUpdate,
)
from app.domains.campaigns.service import CampaignService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
service = CampaignService()


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(
    data: CampaignCreate, request: Request, _: Authenticated, session: DatabaseSession
) -> CampaignRead:
    campaign = service.create(session, data, request.state.correlation_id)
    return CampaignRead.model_validate(campaign)


@router.get("", response_model=list[CampaignRead])
def list_campaigns(
    _: Authenticated,
    session: DatabaseSession,
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    campaign_status: Annotated[CampaignStatus | None, Query(alias="status")] = None,
) -> list[CampaignRead]:
    campaigns = service.list(
        session,
        query=query,
        status=campaign_status.value if campaign_status else None,
    )
    return [CampaignRead.model_validate(campaign) for campaign in campaigns]


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: str,
    data: CampaignUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignRead:
    campaign = service.update(session, campaign_id, data, request.state.correlation_id)
    return CampaignRead.model_validate(campaign)


@router.post(
    "/{campaign_id}/duplicate", response_model=CampaignRead, status_code=status.HTTP_201_CREATED
)
def duplicate_campaign(
    campaign_id: str,
    data: CampaignDuplicate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> CampaignRead:
    campaign = service.duplicate(session, campaign_id, data, request.state.correlation_id)
    return CampaignRead.model_validate(campaign)


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: str, _: Authenticated, session: DatabaseSession) -> CampaignRead:
    return CampaignRead.model_validate(service.get(session, campaign_id))
