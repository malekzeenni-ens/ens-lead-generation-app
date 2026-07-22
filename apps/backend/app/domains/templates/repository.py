from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Template


class TemplateRepository:
    def get(self, session: Session, template_id: str) -> Template | None:
        return session.get(Template, template_id)

    def list(self, session: Session) -> list[Template]:
        return list(session.scalars(select(Template).order_by(Template.topic)))

    def add(self, session: Session, template: Template) -> None:
        session.add(template)

    def delete(self, session: Session, template: Template) -> None:
        session.delete(template)
