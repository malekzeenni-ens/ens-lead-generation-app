from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import Template
from app.domains.audit.service import record_audit_event
from app.domains.catalogue.repository import CatalogueRepository
from app.domains.templates.repository import TemplateRepository
from app.domains.templates.schemas import TemplateCreate, TemplateRead, TemplateUpdate


class TemplateService:
    def __init__(
        self,
        repository: TemplateRepository | None = None,
        catalogue_repository: CatalogueRepository | None = None,
    ) -> None:
        self.repository = repository or TemplateRepository()
        self.catalogue_repository = catalogue_repository or CatalogueRepository()

    def _require_families(self, session: Session, family_ids: list[str]) -> None:
        for family_id in family_ids:
            if self.catalogue_repository.get_family(session, family_id) is None:
                raise DomainError(
                    "PRODUCT_FAMILY_NOT_FOUND", "Product family not found.", status_code=404
                )

    def list(self, session: Session) -> list[TemplateRead]:
        return [TemplateRead.model_validate(template) for template in self.repository.list(session)]

    def create(self, session: Session, data: TemplateCreate, correlation_id: str) -> TemplateRead:
        self._require_families(session, data.product_family_ids)
        template = Template(**data.model_dump())
        self.repository.add(session, template)
        session.flush()
        record_audit_event(
            session,
            action="template.created",
            entity_type="template",
            entity_id=template.id,
            correlation_id=correlation_id,
            summary={"topic": template.topic},
        )
        session.commit()
        return TemplateRead.model_validate(template)

    def update(
        self,
        session: Session,
        template_id: str,
        data: TemplateUpdate,
        correlation_id: str,
    ) -> TemplateRead:
        template = self.repository.get(session, template_id)
        if template is None:
            raise DomainError("TEMPLATE_NOT_FOUND", "Template not found.", status_code=404)
        changes = data.model_dump(exclude_unset=True)
        if "product_family_ids" in changes:
            self._require_families(session, changes["product_family_ids"])
        for field, value in changes.items():
            setattr(template, field, value)
        record_audit_event(
            session,
            action="template.updated",
            entity_type="template",
            entity_id=template.id,
            correlation_id=correlation_id,
            summary={"changed_fields": sorted(changes)},
        )
        session.commit()
        session.refresh(template)
        return TemplateRead.model_validate(template)

    def delete(self, session: Session, template_id: str, correlation_id: str) -> None:
        template = self.repository.get(session, template_id)
        if template is None:
            raise DomainError("TEMPLATE_NOT_FOUND", "Template not found.", status_code=404)
        record_audit_event(
            session,
            action="template.deleted",
            entity_type="template",
            entity_id=template.id,
            correlation_id=correlation_id,
            summary={"topic": template.topic},
        )
        self.repository.delete(session, template)
        session.commit()
