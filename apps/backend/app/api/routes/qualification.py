from fastapi import APIRouter, Request

from app.api.dependencies import Authenticated, DatabaseSession
from app.domains.qualification.schemas import (
    ScoreCalculate,
    ScoreOverride,
    ScoreRunRead,
    ScoringProfileRead,
    ScoringProfileUpdate,
    ShortlistAction,
    ShortlistGenerate,
    ShortlistRead,
)
from app.domains.qualification.service import QualificationService

router = APIRouter(tags=["qualification"])
service = QualificationService()


@router.get("/scoring/profiles/{segment}", response_model=ScoringProfileRead)
def get_scoring_profile(
    segment: str, _: Authenticated, session: DatabaseSession
) -> ScoringProfileRead:
    return service.get_profile(session, segment)


@router.get("/scoring/profiles/{segment}/history", response_model=list[ScoringProfileRead])
def get_scoring_profile_history(
    segment: str, _: Authenticated, session: DatabaseSession
) -> list[ScoringProfileRead]:
    return service.profile_history(session, segment)


@router.patch("/scoring/profiles/{segment}", response_model=ScoringProfileRead)
def update_scoring_profile(
    segment: str,
    data: ScoringProfileUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ScoringProfileRead:
    return service.update_profile(session, segment, data, request.state.correlation_id)


@router.get("/scores/latest", response_model=list[ScoreRunRead])
def get_latest_scores(_: Authenticated, session: DatabaseSession) -> list[ScoreRunRead]:
    return service.latest_scores(session)


@router.get("/leads/{lead_id}/scores", response_model=list[ScoreRunRead])
def get_lead_score_history(
    lead_id: str, _: Authenticated, session: DatabaseSession
) -> list[ScoreRunRead]:
    return service.score_history(session, lead_id)


@router.post("/leads/{lead_id}/score", response_model=ScoreRunRead)
def calculate_lead_score(
    lead_id: str,
    data: ScoreCalculate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ScoreRunRead:
    return service.calculate(session, lead_id, data.campaign_id, request.state.correlation_id)


@router.post("/leads/{lead_id}/score/override", response_model=ScoreRunRead)
def override_lead_score(
    lead_id: str,
    data: ScoreOverride,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ScoreRunRead:
    return service.override(session, lead_id, data, request.state.correlation_id)


@router.get("/shortlists", response_model=list[ShortlistRead])
def list_shortlists(_: Authenticated, session: DatabaseSession) -> list[ShortlistRead]:
    return service.list_shortlists(session)


@router.post("/shortlists/generate", response_model=ShortlistRead)
def generate_shortlist(
    data: ShortlistGenerate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ShortlistRead:
    return service.generate(session, data, request.state.correlation_id)


@router.post(
    "/shortlists/{shortlist_id}/items/{item_id}/action",
    response_model=ShortlistRead,
)
def update_shortlist_item(
    shortlist_id: str,
    item_id: str,
    data: ShortlistAction,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ShortlistRead:
    return service.action(
        session,
        shortlist_id,
        item_id,
        data,
        request.state.correlation_id,
    )
