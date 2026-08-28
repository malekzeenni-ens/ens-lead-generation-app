from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import Authenticated, DatabaseSession
from app.domains.outreach.schemas import (
    OutreachBatchCreate,
    OutreachBatchRead,
    OutreachDraftApproveMany,
    OutreachDraftEdit,
    OutreachDraftRead,
    OutreachDraftReject,
    OutreachLeadOptionRead,
    OutreachZohoHandoffRead,
    OutreachZohoOpenFailure,
)
from app.domains.outreach.service import OutreachService

router = APIRouter(prefix="/outreach", tags=["outreach"])
service = OutreachService()


@router.get("/lead-options", response_model=list[OutreachLeadOptionRead])
def list_lead_options(
    _: Authenticated,
    session: DatabaseSession,
    campaign_id: Annotated[str | None, Query(min_length=36, max_length=36)] = None,
) -> list[OutreachLeadOptionRead]:
    return service.lead_options(session, campaign_id=campaign_id)


@router.get("/batches", response_model=list[OutreachBatchRead])
def list_batches(_: Authenticated, session: DatabaseSession) -> list[OutreachBatchRead]:
    return service.list_batches(session)


@router.post("/batches", response_model=OutreachBatchRead, status_code=status.HTTP_201_CREATED)
def create_batch(
    data: OutreachBatchCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> OutreachBatchRead:
    return service.create_batch(session, data, request.state.correlation_id)


@router.get("/batches/{batch_id}", response_model=OutreachBatchRead)
def get_batch(batch_id: str, _: Authenticated, session: DatabaseSession) -> OutreachBatchRead:
    return service.get_batch(session, batch_id)


@router.patch("/drafts/{draft_id}", response_model=OutreachDraftRead)
def edit_draft(
    draft_id: str,
    data: OutreachDraftEdit,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> OutreachDraftRead:
    return service.edit_draft(session, draft_id, data, request.state.correlation_id)


@router.post("/drafts/approve-many", response_model=list[OutreachDraftRead])
def approve_many(
    data: OutreachDraftApproveMany,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> list[OutreachDraftRead]:
    return service.approve_many(session, data, request.state.correlation_id)


@router.post("/drafts/{draft_id}/approve", response_model=OutreachDraftRead)
def approve_draft(
    draft_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> OutreachDraftRead:
    return service.approve_draft(session, draft_id, request.state.correlation_id)


@router.post("/drafts/{draft_id}/reject", response_model=OutreachDraftRead)
def reject_draft(
    draft_id: str,
    data: OutreachDraftReject,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> OutreachDraftRead:
    return service.reject_draft(session, draft_id, data, request.state.correlation_id)


@router.post("/drafts/{draft_id}/reopen", response_model=OutreachDraftRead)
def reopen_draft(
    draft_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> OutreachDraftRead:
    return service.reopen_draft(session, draft_id, request.state.correlation_id)


@router.post("/drafts/{draft_id}/zoho-open", response_model=OutreachZohoHandoffRead)
def prepare_zoho_handoff(
    draft_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> OutreachZohoHandoffRead:
    return service.prepare_zoho_handoff(session, draft_id, request.state.correlation_id)


@router.post("/drafts/{draft_id}/zoho-open-failed", response_model=OutreachDraftRead)
def record_zoho_open_failure(
    draft_id: str,
    data: OutreachZohoOpenFailure,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> OutreachDraftRead:
    return service.record_zoho_open_failure(session, draft_id, data, request.state.correlation_id)


@router.post("/drafts/{draft_id}/sent-confirmed", response_model=OutreachDraftRead)
def confirm_sent(
    draft_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> OutreachDraftRead:
    return service.confirm_sent(session, draft_id, request.state.correlation_id)
