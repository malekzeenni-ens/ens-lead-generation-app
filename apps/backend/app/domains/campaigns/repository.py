from __future__ import annotations

import builtins

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Campaign,
    CampaignRun,
    Lead,
    LeadCampaign,
    OutreachBatch,
    OutreachDraft,
)


class CampaignRepository:
    def get(self, session: Session, campaign_id: str) -> Campaign | None:
        return session.get(Campaign, campaign_id)

    def get_by_name(self, session: Session, name: str) -> Campaign | None:
        return session.scalar(select(Campaign).where(Campaign.name == name))

    def list(
        self, session: Session, *, query: str | None = None, status: str | None = None
    ) -> list[Campaign]:
        statement = select(Campaign)
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(
                    Campaign.name.ilike(pattern),
                    Campaign.segment.ilike(pattern),
                    Campaign.primary_location.ilike(pattern),
                )
            )
        if status:
            statement = statement.where(Campaign.status == status)
        return list(session.scalars(statement.order_by(Campaign.created_at.desc())))

    def add(self, session: Session, campaign: Campaign) -> None:
        session.add(campaign)

    def has_active_run(self, session: Session, campaign_id: str) -> bool:
        return (
            session.scalar(
                select(CampaignRun.id)
                .where(
                    CampaignRun.campaign_id == campaign_id,
                    CampaignRun.status.in_(("queued", "running")),
                )
                .limit(1)
            )
            is not None
        )

    def deletion_leads(
        self, session: Session, campaign_id: str
    ) -> tuple[builtins.list[tuple[str, bool]], int]:
        linked_lead_ids = select(LeadCampaign.lead_id).where(
            LeadCampaign.campaign_id == campaign_id
        )
        rows = session.execute(
            select(
                Lead.id,
                Lead.suppressed,
                func.count(LeadCampaign.campaign_id).label("campaign_count"),
            )
            .join(LeadCampaign, LeadCampaign.lead_id == Lead.id)
            .where(Lead.id.in_(linked_lead_ids))
            .group_by(Lead.id, Lead.suppressed)
        ).all()
        exclusive = [(str(row.id), bool(row.suppressed)) for row in rows if row.campaign_count == 1]
        shared_count = sum(1 for row in rows if row.campaign_count > 1)
        return exclusive, shared_count

    def delete_cascade(
        self,
        session: Session,
        campaign_id: str,
        exclusive_lead_ids: builtins.list[str],
    ) -> int:
        linked_batch_ids: builtins.list[str] = []
        if exclusive_lead_ids:
            linked_batch_ids = builtins.list(
                session.scalars(
                    select(OutreachDraft.batch_id)
                    .where(OutreachDraft.lead_id.in_(exclusive_lead_ids))
                    .distinct()
                )
            )
        batch_count = int(
            session.scalar(
                select(func.count(OutreachBatch.id)).where(OutreachBatch.campaign_id == campaign_id)
            )
            or 0
        )
        session.execute(delete(OutreachBatch).where(OutreachBatch.campaign_id == campaign_id))
        if exclusive_lead_ids:
            session.execute(delete(Lead).where(Lead.id.in_(exclusive_lead_ids)))
        if linked_batch_ids:
            has_drafts = select(OutreachDraft.id).where(OutreachDraft.batch_id == OutreachBatch.id)
            empty_linked_batches = OutreachBatch.id.in_(linked_batch_ids) & ~has_drafts.exists()
            orphan_count = int(
                session.scalar(select(func.count(OutreachBatch.id)).where(empty_linked_batches))
                or 0
            )
            session.execute(delete(OutreachBatch).where(empty_linked_batches))
            batch_count += orphan_count
        session.execute(delete(Campaign).where(Campaign.id == campaign_id))
        return batch_count
