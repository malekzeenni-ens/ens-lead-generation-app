from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies import Authenticated, DatabaseSession
from app.domains.leads.schemas import (
    CommunicationCreate,
    FollowUpComplete,
    FollowUpCreate,
    LeadCreate,
    LeadDeleteResult,
    LeadRead,
    LeadUpdate,
    NoteCreate,
    PipelineStage,
    StageChange,
    SuppressionCreate,
)
from app.domains.leads.service import LeadService

router = APIRouter(prefix="/leads", tags=["leads"])
service = LeadService()


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    data: LeadCreate, request: Request, _: Authenticated, session: DatabaseSession
) -> LeadRead:
    return service.create(session, data, request.state.correlation_id)


@router.get("", response_model=list[LeadRead])
def list_leads(
    _: Authenticated,
    session: DatabaseSession,
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    stage: PipelineStage | None = None,
    suppressed: bool | None = None,
    campaign_id: Annotated[str | None, Query(min_length=36, max_length=36)] = None,
) -> list[LeadRead]:
    return service.list(
        session,
        query=query,
        stage=stage.value if stage else None,
        suppressed=suppressed,
        campaign_id=campaign_id,
    )


@router.get("/export")
def export_leads(
    _: Authenticated,
    session: DatabaseSession,
    export_format: Annotated[Literal["csv", "json"], Query(alias="format")] = "json",
) -> Response:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    if export_format == "csv":
        return Response(
            content=service.export_csv(session),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="etch-n-shine-leads-{stamp}.csv"'
            },
        )
    return JSONResponse(
        content=service.export_json(session),
        headers={"Content-Disposition": f'attachment; filename="etch-n-shine-leads-{stamp}.json"'},
    )


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(lead_id: str, _: Authenticated, session: DatabaseSession) -> LeadRead:
    return service.get(session, lead_id)


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: str,
    data: LeadUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadRead:
    return service.update(session, lead_id, data, request.state.correlation_id)


@router.post("/{lead_id}/stage", response_model=LeadRead)
def change_lead_stage(
    lead_id: str,
    data: StageChange,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadRead:
    return service.change_stage(session, lead_id, data, request.state.correlation_id)


@router.post("/{lead_id}/notes", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def add_lead_note(
    lead_id: str,
    data: NoteCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadRead:
    return service.add_note(session, lead_id, data, request.state.correlation_id)


@router.post("/{lead_id}/follow-ups", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def add_follow_up(
    lead_id: str,
    data: FollowUpCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadRead:
    return service.add_follow_up(session, lead_id, data, request.state.correlation_id)


@router.post("/{lead_id}/follow-ups/{follow_up_id}/complete", response_model=LeadRead)
def complete_follow_up(
    lead_id: str,
    follow_up_id: str,
    data: FollowUpComplete,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadRead:
    return service.complete_follow_up(
        session,
        lead_id,
        follow_up_id,
        data,
        request.state.correlation_id,
    )


@router.post(
    "/{lead_id}/communications", response_model=LeadRead, status_code=status.HTTP_201_CREATED
)
def add_communication(
    lead_id: str,
    data: CommunicationCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadRead:
    return service.add_communication(session, lead_id, data, request.state.correlation_id)


@router.post("/{lead_id}/suppression", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def suppress_lead(
    lead_id: str,
    data: SuppressionCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadRead:
    return service.suppress(session, lead_id, data, request.state.correlation_id)


@router.delete("/{lead_id}/suppression", response_model=LeadRead)
def lift_lead_suppression(
    lead_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadRead:
    return service.lift_suppression(session, lead_id, request.state.correlation_id)


@router.delete("/{lead_id}", response_model=LeadDeleteResult)
def delete_lead(
    lead_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> LeadDeleteResult:
    return service.delete(session, lead_id, request.state.correlation_id)
