from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Lead, OutreachBatch, OutreachDraft

_BATCH_LOAD = (
    selectinload(OutreachBatch.drafts).selectinload(OutreachDraft.revisions),
    selectinload(OutreachBatch.drafts).selectinload(OutreachDraft.lead).selectinload(Lead.notes),
)


class OutreachRepository:
    def get_batch(self, session: Session, batch_id: str) -> OutreachBatch | None:
        return session.scalar(
            select(OutreachBatch)
            .options(*_BATCH_LOAD)
            .where(OutreachBatch.id == batch_id)
            .execution_options(populate_existing=True)
        )

    def list_batches(self, session: Session) -> list[OutreachBatch]:
        return list(
            session.scalars(
                select(OutreachBatch)
                .options(*_BATCH_LOAD)
                .order_by(OutreachBatch.created_at.desc())
                .execution_options(populate_existing=True)
            ).unique()
        )

    def get_draft(self, session: Session, draft_id: str) -> OutreachDraft | None:
        return session.scalar(
            select(OutreachDraft)
            .options(
                selectinload(OutreachDraft.revisions),
                selectinload(OutreachDraft.lead).selectinload(Lead.notes),
            )
            .where(OutreachDraft.id == draft_id)
            .execution_options(populate_existing=True)
        )

    def active_draft_for_lead(
        self, session: Session, lead_id: str, *, exclude_draft_id: str | None = None
    ) -> OutreachDraft | None:
        query = select(OutreachDraft).where(
            OutreachDraft.lead_id == lead_id,
            OutreachDraft.review_status.in_(["pending_review", "approved"]),
            OutreachDraft.sync_status != "user_confirmed_sent",
        )
        if exclude_draft_id is not None:
            query = query.where(OutreachDraft.id != exclude_draft_id)
        return session.scalar(query.order_by(OutreachDraft.created_at.desc()).limit(1))
