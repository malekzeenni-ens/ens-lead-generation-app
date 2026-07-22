from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Campaign


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
