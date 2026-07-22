from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Product,
    ScoreRun,
    ScoringProfile,
    Shortlist,
    ShortlistItem,
)


class QualificationRepository:
    def active_profile(self, session: Session, segment: str) -> ScoringProfile | None:
        return session.scalar(
            select(ScoringProfile).where(
                ScoringProfile.segment.collate("NOCASE") == segment,
                ScoringProfile.active.is_(True),
            )
        )

    def profile_versions(self, session: Session, segment: str) -> list[ScoringProfile]:
        return list(
            session.scalars(
                select(ScoringProfile)
                .where(ScoringProfile.segment.collate("NOCASE") == segment)
                .order_by(ScoringProfile.version.desc())
            )
        )

    def active_products(self, session: Session) -> list[Product]:
        return list(
            session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name))
        )

    def latest_scores(self, session: Session, lead_id: str | None = None) -> list[ScoreRun]:
        statement = select(ScoreRun).options(selectinload(ScoreRun.profile))
        if lead_id:
            statement = statement.where(ScoreRun.lead_id == lead_id)
        return list(session.scalars(statement.order_by(ScoreRun.created_at.desc())))

    def latest_score(self, session: Session, lead_id: str) -> ScoreRun | None:
        return session.scalar(
            select(ScoreRun)
            .where(ScoreRun.lead_id == lead_id)
            .options(selectinload(ScoreRun.profile))
            .order_by(ScoreRun.created_at.desc())
            .limit(1)
        )

    def latest_score_for_campaign(
        self, session: Session, lead_id: str, campaign_id: str
    ) -> ScoreRun | None:
        return session.scalar(
            select(ScoreRun)
            .where(ScoreRun.lead_id == lead_id, ScoreRun.campaign_id == campaign_id)
            .options(selectinload(ScoreRun.profile))
            .order_by(ScoreRun.created_at.desc())
            .limit(1)
        )

    def latest_scores_for_campaign(self, session: Session, campaign_id: str) -> list[ScoreRun]:
        """All score runs for a campaign, newest first, to build a per-lead lookup in one query."""
        return list(
            session.scalars(
                select(ScoreRun)
                .where(ScoreRun.campaign_id == campaign_id)
                .options(selectinload(ScoreRun.profile))
                .order_by(ScoreRun.created_at.desc())
            )
        )

    def recently_recommended_lead_ids(
        self, session: Session, campaign_id: str, since: date, before: date
    ) -> set[str]:
        """Lead ids shortlisted for the campaign in [since, before), for one membership query."""
        return set(
            session.scalars(
                select(ShortlistItem.lead_id)
                .join(Shortlist, Shortlist.id == ShortlistItem.shortlist_id)
                .where(
                    Shortlist.campaign_id == campaign_id,
                    Shortlist.week_start >= since,
                    Shortlist.week_start < before,
                    ShortlistItem.decision != "deferred",
                )
            )
        )

    def shortlist_for_week(
        self, session: Session, campaign_id: str, week_start: date
    ) -> Shortlist | None:
        return session.scalar(
            select(Shortlist)
            .where(Shortlist.campaign_id == campaign_id, Shortlist.week_start == week_start)
            .options(
                selectinload(Shortlist.campaign),
                selectinload(Shortlist.items).selectinload(ShortlistItem.lead),
            )
        )

    def get_shortlist(self, session: Session, shortlist_id: str) -> Shortlist | None:
        return session.scalar(
            select(Shortlist)
            .where(Shortlist.id == shortlist_id)
            .options(
                selectinload(Shortlist.campaign),
                selectinload(Shortlist.items).selectinload(ShortlistItem.lead),
            )
        )

    def list_shortlists(self, session: Session) -> list[Shortlist]:
        return list(
            session.scalars(
                select(Shortlist)
                .options(
                    selectinload(Shortlist.campaign),
                    selectinload(Shortlist.items).selectinload(ShortlistItem.lead),
                )
                .order_by(Shortlist.week_start.desc(), Shortlist.created_at.desc())
            )
        )

    def item(self, session: Session, shortlist_id: str, item_id: str) -> ShortlistItem | None:
        return session.scalar(
            select(ShortlistItem)
            .where(ShortlistItem.id == item_id, ShortlistItem.shortlist_id == shortlist_id)
            .options(selectinload(ShortlistItem.lead))
        )
