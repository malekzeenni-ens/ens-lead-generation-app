from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import OutreachBatch, OutreachDraft


def refresh_batch_status(session: Session, batch_id: str) -> None:
    # Sessions intentionally disable autoflush, so persist the review-state
    # transition before deriving the parent batch status.
    session.flush()
    batch = session.get(OutreachBatch, batch_id)
    if batch is None:
        return
    statuses = list(
        session.execute(
            select(OutreachDraft.review_status, OutreachDraft.sync_status).where(
                OutreachDraft.batch_id == batch_id
            )
        )
    )
    if any(review_status == "pending_review" for review_status, _ in statuses):
        batch.status = "review"
    elif any(
        review_status == "approved" and sync_status != "user_confirmed_sent"
        for review_status, sync_status in statuses
    ):
        batch.status = "ready"
    else:
        batch.status = "closed"


def invalidate_approved_drafts(session: Session, lead_id: str, reason: str) -> int:
    drafts = list(
        session.scalars(
            select(OutreachDraft).where(
                OutreachDraft.lead_id == lead_id,
                OutreachDraft.review_status == "approved",
                OutreachDraft.sync_status != "user_confirmed_sent",
            )
        )
    )
    batch_ids: set[str] = set()
    for draft in drafts:
        draft.review_status = "pending_review"
        draft.sync_status = "blocked"
        draft.approved_version = None
        draft.approved_content_hash = None
        draft.approved_at = None
        draft.blocked_reason = reason
        batch_ids.add(draft.batch_id)
    for batch_id in batch_ids:
        refresh_batch_status(session, batch_id)
    return len(drafts)
