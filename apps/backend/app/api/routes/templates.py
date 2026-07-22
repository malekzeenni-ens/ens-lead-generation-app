from fastapi import APIRouter, Request, status

from app.api.dependencies import Authenticated, DatabaseSession
from app.domains.templates.schemas import TemplateCreate, TemplateRead, TemplateUpdate
from app.domains.templates.service import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])
service = TemplateService()


@router.get("", response_model=list[TemplateRead])
def list_templates(_: Authenticated, session: DatabaseSession) -> list[TemplateRead]:
    return service.list(session)


@router.post("", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    data: TemplateCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> TemplateRead:
    return service.create(session, data, request.state.correlation_id)


@router.patch("/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: str,
    data: TemplateUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> TemplateRead:
    return service.update(session, template_id, data, request.state.correlation_id)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> None:
    service.delete(session, template_id, request.state.correlation_id)
