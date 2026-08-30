from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CampaignDraft, CampaignDraftOverride, CampaignDraftRevision


class CampaignDraftRepository:
    def add(self, session: Session, draft: CampaignDraft) -> None:
        session.add(draft)

    def get(self, session: Session, draft_id: str) -> CampaignDraft | None:
        return session.scalar(
            select(CampaignDraft)
            .where(CampaignDraft.id == draft_id)
            .options(
                selectinload(CampaignDraft.revisions),
                selectinload(CampaignDraft.overrides),
            )
            .execution_options(populate_existing=True)
        )

    def list(self, session: Session, status: str | None = None) -> list[CampaignDraft]:
        statement = (
            select(CampaignDraft)
            .options(
                selectinload(CampaignDraft.revisions),
                selectinload(CampaignDraft.overrides),
            )
            .execution_options(populate_existing=True)
        )
        if status:
            statement = statement.where(CampaignDraft.status == status)
        return list(session.scalars(statement.order_by(CampaignDraft.updated_at.desc())))

    def add_revision(self, session: Session, revision: CampaignDraftRevision) -> None:
        session.add(revision)

    def add_override(self, session: Session, override: CampaignDraftOverride) -> None:
        session.add(override)

    def get_override(
        self, session: Session, draft_id: str, override_id: str
    ) -> CampaignDraftOverride | None:
        return session.scalar(
            select(CampaignDraftOverride).where(
                CampaignDraftOverride.id == override_id,
                CampaignDraftOverride.draft_id == draft_id,
            )
        )

    def pending_override(self, session: Session, draft_id: str) -> CampaignDraftOverride | None:
        return session.scalar(
            select(CampaignDraftOverride)
            .where(
                CampaignDraftOverride.draft_id == draft_id,
                CampaignDraftOverride.status == "pending",
            )
            .order_by(CampaignDraftOverride.created_at.desc())
            .limit(1)
        )
