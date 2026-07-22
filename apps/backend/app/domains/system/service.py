from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings as RuntimeSettings
from app.db.models import (
    AppSetting,
    AuditEvent,
    BackupManifest,
    Campaign,
    CampaignRun,
    DiscoveryCandidate,
    FollowUp,
    Lead,
    Product,
    ScoreRun,
    Shortlist,
    ShortlistItem,
)
from app.domains.audit.service import record_audit_event
from app.domains.system.schemas import (
    DiagnosticsRead,
    OperationsSummary,
    WorkspaceSettings,
    WorkspaceSettingsUpdate,
)

_WORKSPACE_SETTINGS_KEY = "workspace"


class SystemService:
    def get_settings(self, session: Session) -> WorkspaceSettings:
        stored = session.get(AppSetting, _WORKSPACE_SETTINGS_KEY)
        if stored is None:
            return WorkspaceSettings()
        return WorkspaceSettings.model_validate(stored.value)

    def update_settings(
        self,
        session: Session,
        data: WorkspaceSettingsUpdate,
        correlation_id: str,
    ) -> WorkspaceSettings:
        current = self.get_settings(session)
        updated = current.model_copy(update=data.model_dump(exclude_unset=True))
        stored = session.get(AppSetting, _WORKSPACE_SETTINGS_KEY)
        if stored is None:
            stored = AppSetting(key=_WORKSPACE_SETTINGS_KEY, value=updated.model_dump())
            session.add(stored)
        else:
            stored.value = updated.model_dump()
        record_audit_event(
            session,
            action="settings.updated",
            entity_type="settings",
            entity_id=_WORKSPACE_SETTINGS_KEY,
            correlation_id=correlation_id,
            summary={"changed_fields": sorted(data.model_fields_set)},
        )
        session.commit()
        return updated

    def diagnostics(self, session: Session, runtime_settings: RuntimeSettings) -> DiagnosticsRead:
        schema_version = session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        journal_mode = str(session.execute(text("PRAGMA journal_mode")).scalar_one())
        foreign_keys = bool(session.execute(text("PRAGMA foreign_keys")).scalar_one())
        return DiagnosticsRead(
            api_status="ok",
            database_status="connected",
            schema_version=str(schema_version),
            database_size_bytes=(
                runtime_settings.database_path.stat().st_size
                if runtime_settings.database_path.exists()
                else 0
            ),
            journal_mode=journal_mode,
            foreign_keys_enabled=foreign_keys,
            data_directory=str(runtime_settings.database_path.parent),
            log_directory=str(runtime_settings.log_directory),
            campaigns=session.scalar(select(func.count()).select_from(Campaign)) or 0,
            leads=session.scalar(select(func.count()).select_from(Lead)) or 0,
            audit_events=session.scalar(select(func.count()).select_from(AuditEvent)) or 0,
            backups=session.scalar(select(func.count()).select_from(BackupManifest)) or 0,
            products=session.scalar(select(func.count()).select_from(Product)) or 0,
            score_runs=session.scalar(select(func.count()).select_from(ScoreRun)) or 0,
            shortlists=session.scalar(select(func.count()).select_from(Shortlist)) or 0,
            campaign_runs=session.scalar(select(func.count()).select_from(CampaignRun)) or 0,
            discovery_candidates=(
                session.scalar(select(func.count()).select_from(DiscoveryCandidate)) or 0
            ),
            provider_mode=(
                "google_places_configured" if runtime_settings.google_places_enabled else "disabled"
            ),
            outbound_messaging="disabled",
        )

    def operations_summary(self, session: Session) -> OperationsSummary:
        today = datetime.now(UTC).date()
        settings = self.get_settings(session)
        week_end = today + timedelta(days=settings.follow_up_window_days)
        week_start = today - timedelta(days=today.weekday())
        pipeline_rows = session.execute(
            select(Lead.pipeline_stage, func.count()).group_by(Lead.pipeline_stage)
        ).all()
        open_follow_up = FollowUp.status == "open"
        return OperationsSummary(
            campaigns=session.scalar(select(func.count()).select_from(Campaign)) or 0,
            active_campaigns=session.scalar(
                select(func.count()).select_from(Campaign).where(Campaign.status == "active")
            )
            or 0,
            leads=session.scalar(select(func.count()).select_from(Lead)) or 0,
            suppressed_leads=session.scalar(
                select(func.count()).select_from(Lead).where(Lead.suppressed.is_(True))
            )
            or 0,
            review_required=session.scalar(
                select(func.count())
                .select_from(Lead)
                .where(Lead.contact_classification == "unknown")
            )
            or 0,
            open_follow_ups=session.scalar(
                select(func.count()).select_from(FollowUp).where(open_follow_up)
            )
            or 0,
            due_today=session.scalar(
                select(func.count())
                .select_from(FollowUp)
                .where(open_follow_up, FollowUp.due_date == today)
            )
            or 0,
            overdue=session.scalar(
                select(func.count())
                .select_from(FollowUp)
                .where(open_follow_up, FollowUp.due_date < today)
            )
            or 0,
            due_this_week=session.scalar(
                select(func.count())
                .select_from(FollowUp)
                .where(open_follow_up, FollowUp.due_date > today, FollowUp.due_date <= week_end)
            )
            or 0,
            products=session.scalar(
                select(func.count()).select_from(Product).where(Product.active.is_(True))
            )
            or 0,
            scored_leads=session.scalar(
                select(func.count()).select_from(Lead).where(Lead.current_score.is_not(None))
            )
            or 0,
            shortlisted_this_week=session.scalar(
                select(func.count())
                .select_from(ShortlistItem)
                .join(Shortlist, Shortlist.id == ShortlistItem.shortlist_id)
                .where(
                    Shortlist.week_start == week_start,
                    ShortlistItem.decision.in_(["recommended", "approved"]),
                )
            )
            or 0,
            pipeline={str(stage): int(count) for stage, count in pipeline_rows},
        )
