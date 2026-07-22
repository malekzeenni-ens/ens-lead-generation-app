from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Campaign(Base):
    __tablename__ = "campaign"
    __table_args__ = (
        CheckConstraint("radius_miles > 0", name="ck_campaign_radius_positive"),
        CheckConstraint(
            "weekly_shortlist_size BETWEEN 1 AND 50", name="ck_campaign_shortlist_size"
        ),
        CheckConstraint(
            "minimum_score_threshold BETWEEN 0 AND 100", name="ck_campaign_score_threshold"
        ),
        Index("ix_campaign_status_segment", "status", "segment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    segment: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_location: Mapped[str] = mapped_column(String(200), nullable=False)
    radius_miles: Mapped[float] = mapped_column(Float, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    exclusion_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    product_categories: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    product_family_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("product_family.id", ondelete="SET NULL")
    )
    discovery_sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    weekly_shortlist_size: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    minimum_score_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preferred_channels: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    offer_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    discovery_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    leads: Mapped[list[LeadCampaign]] = relationship(back_populates="campaign")
    score_runs: Mapped[list[ScoreRun]] = relationship(back_populates="campaign")
    shortlists: Mapped[list[Shortlist]] = relationship(back_populates="campaign")
    campaign_runs: Mapped[list[CampaignRun]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )
    product_family: Mapped[ProductFamily | None] = relationship(back_populates="campaigns")


class Lead(Base):
    __tablename__ = "lead"
    __table_args__ = (
        Index("ix_lead_normalized_name", "normalized_name"),
        Index("ix_lead_segment_stage", "segment", "pipeline_stage"),
        Index("ix_lead_suppressed", "suppressed"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    segment: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str | None] = mapped_column(String(2048))
    social_profile: Mapped[str | None] = mapped_column(String(2048))
    phone_number: Mapped[str | None] = mapped_column(String(100))
    public_email: Mapped[str | None] = mapped_column(String(320))
    contact_classification: Mapped[str] = mapped_column(
        String(50), nullable=False, default="unknown"
    )
    pipeline_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="new")
    suppressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimated_order_value: Mapped[float | None] = mapped_column(Float)
    quote_value: Mapped[float | None] = mapped_column(Float)
    won_value: Mapped[float | None] = mapped_column(Float)
    potential_recurrence: Mapped[str | None] = mapped_column(String(100))
    lost_reason: Mapped[str | None] = mapped_column(String(100))
    mock_up_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_offered")
    sample_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_applicable")
    quote_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_requested")
    retention_review_date: Mapped[date | None] = mapped_column(Date)
    current_score: Mapped[int | None] = mapped_column(Integer)
    score_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    campaigns: Mapped[list[LeadCampaign]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )
    observations: Mapped[list[SourceObservation]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )
    social_identities: Mapped[list[LeadSocialIdentity]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )
    stage_events: Mapped[list[LeadStageEvent]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )
    notes: Mapped[list[LeadNote]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )
    follow_ups: Mapped[list[FollowUp]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )
    communications: Mapped[list[Communication]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )
    suppression_records: Mapped[list[SuppressionRecord]] = relationship(
        back_populates="lead", passive_deletes=True
    )
    score_runs: Mapped[list[ScoreRun]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )
    shortlist_items: Mapped[list[ShortlistItem]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", passive_deletes=True
    )


class LeadCampaign(Base):
    __tablename__ = "lead_campaign"

    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="CASCADE"), primary_key=True
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaign.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    lead: Mapped[Lead] = relationship(back_populates="campaigns")
    campaign: Mapped[Campaign] = relationship(back_populates="leads")


class LeadSocialIdentity(Base):
    __tablename__ = "lead_social_identity"
    __table_args__ = (
        UniqueConstraint("platform", "profile_url", name="uq_social_identity_profile"),
        UniqueConstraint("platform", "normalized_handle", name="uq_social_identity_handle"),
        Index("ix_social_identity_lead", "lead_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_handle: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    classification: Mapped[str] = mapped_column(
        String(40), nullable=False, default="provider_observed"
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    lead: Mapped[Lead] = relationship(back_populates="social_identities")


class SourceSystem(Base):
    __tablename__ = "source_system"
    __table_args__ = (Index("ix_source_system_type", "source_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    observations: Mapped[list[SourceObservation]] = relationship(back_populates="source_system")


class SourceObservation(Base):
    __tablename__ = "source_observation"
    __table_args__ = (
        Index("ix_observation_lead_source", "lead_id", "source_system_id"),
        Index("ix_observation_collected_at", "collected_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="CASCADE"), nullable=False
    )
    source_system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_system.id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_value: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    collection_method: Mapped[str] = mapped_column(String(50), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    lead: Mapped[Lead] = relationship(back_populates="observations")
    source_system: Mapped[SourceSystem] = relationship(back_populates="observations")


class LeadStageEvent(Base):
    __tablename__ = "lead_stage_event"
    __table_args__ = (Index("ix_stage_event_lead_time", "lead_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="CASCADE"), nullable=False
    )
    previous_stage: Mapped[str | None] = mapped_column(String(50))
    new_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="local_user")
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    lead: Mapped[Lead] = relationship(back_populates="stage_events")


class LeadNote(Base):
    __tablename__ = "lead_note"
    __table_args__ = (Index("ix_lead_note_lead_time", "lead_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="local_user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    lead: Mapped[Lead] = relationship(back_populates="notes")


class FollowUp(Base):
    __tablename__ = "follow_up"
    __table_args__ = (
        Index("ix_follow_up_lead_due", "lead_id", "due_date"),
        Index("ix_follow_up_status_due", "status", "due_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="CASCADE"), nullable=False
    )
    follow_up_type: Mapped[str] = mapped_column(String(40), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    lead: Mapped[Lead] = relationship(back_populates="follow_ups")


class Communication(Base):
    __tablename__ = "communication"
    __table_args__ = (Index("ix_communication_lead_time", "lead_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    draft_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_applicable")
    approval_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="not_applicable"
    )
    sent_status: Mapped[str] = mapped_column(String(30), nullable=False, default="recorded")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    external_message_id: Mapped[str | None] = mapped_column(String(300))
    response_status: Mapped[str] = mapped_column(String(30), nullable=False, default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    lead: Mapped[Lead] = relationship(back_populates="communications")


class SuppressionRecord(Base):
    __tablename__ = "suppression_record"
    __table_args__ = (
        Index("ix_suppression_identifier_active", "identifier_hash", "active"),
        Index("ix_suppression_lead_time", "lead_id", "effective_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="SET NULL")
    )
    identifier_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    suppression_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lifted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped[Lead | None] = relationship(back_populates="suppression_records")


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="local_user")
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BackupManifest(Base):
    __tablename__ = "backup_manifest"
    __table_args__ = (Index("ix_backup_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    backup_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    integrity_result: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    application_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        Index("ix_product_active_category", "active", "category"),
        Index("ix_product_name", "name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    shopify_handle: Mapped[str | None] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_segments: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    example_use_cases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    image_reference: Mapped[str | None] = mapped_column(String(2048))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pricing_guidance: Mapped[str | None] = mapped_column(String(200))
    sample_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    variant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ProductFamily(Base):
    __tablename__ = "product_family"
    __table_args__ = (Index("ix_product_family_name", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    product_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    campaigns: Mapped[list[Campaign]] = relationship(back_populates="product_family")


class Template(Base):
    __tablename__ = "message_template"
    __table_args__ = (Index("ix_message_template_topic", "topic"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    product_family_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ScoringProfile(Base):
    __tablename__ = "scoring_profile"
    __table_args__ = (
        UniqueConstraint("segment", "version", name="uq_scoring_profile_segment_version"),
        Index("ix_scoring_profile_segment_active", "segment", "active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    segment: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    weights: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    score_runs: Mapped[list[ScoreRun]] = relationship(back_populates="profile")


class CampaignRun(Base):
    __tablename__ = "campaign_run"
    __table_args__ = (
        Index("ix_campaign_run_campaign_created", "campaign_id", "created_at"),
        Index("ix_campaign_run_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaign.id", ondelete="CASCADE"), nullable=False
    )
    trigger: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    phase: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    provider_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="not_requested"
    )
    query_summary: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    campaign: Mapped[Campaign] = relationship(back_populates="campaign_runs")
    candidates: Mapped[list[DiscoveryCandidate]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    attempts: Mapped[list[ProviderAttempt]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    score_runs: Mapped[list[ScoreRun]] = relationship(back_populates="campaign_run")


class DiscoveryCandidate(Base):
    __tablename__ = "discovery_candidate"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "provider", "provider_record_id", name="uq_candidate_run_provider_record"
        ),
        Index("ix_candidate_run_status", "run_id", "status"),
        Index("ix_candidate_provider_record", "provider", "provider_record_id"),
        Index("ix_candidate_normalized_name", "normalized_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaign_run.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaign.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    provider_record_id: Mapped[str] = mapped_column(String(300), nullable=False)
    business_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[str] = mapped_column(String(500), nullable=False)
    website: Mapped[str | None] = mapped_column(String(2048))
    phone: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    place_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="discovered")
    matched_lead_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="SET NULL")
    )
    duplicate_confidence: Mapped[float | None] = mapped_column(Float)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    run: Mapped[CampaignRun] = relationship(back_populates="candidates")


class ProviderAttempt(Base):
    __tablename__ = "provider_attempt"
    __table_args__ = (Index("ix_provider_attempt_run", "run_id", "started_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaign_run.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="running")
    query: Mapped[str] = mapped_column(Text, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[CampaignRun] = relationship(back_populates="attempts")


class ScoreRun(Base):
    __tablename__ = "score_run"
    __table_args__ = (
        Index("ix_score_run_lead_time", "lead_id", "created_at"),
        Index("ix_score_run_campaign_score", "campaign_id", "final_score"),
        Index(
            "ix_score_run_fingerprint",
            "lead_id",
            "campaign_id",
            "input_fingerprint",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaign.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scoring_profile.id"), nullable=False
    )
    campaign_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("campaign_run.id", ondelete="SET NULL")
    )
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    calculated_score: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False)
    manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text)
    breakdown: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    product_matches: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped[Lead] = relationship(back_populates="score_runs")
    campaign: Mapped[Campaign] = relationship(back_populates="score_runs")
    profile: Mapped[ScoringProfile] = relationship(back_populates="score_runs")
    campaign_run: Mapped[CampaignRun | None] = relationship(back_populates="score_runs")


class Shortlist(Base):
    __tablename__ = "shortlist"
    __table_args__ = (
        UniqueConstraint("campaign_id", "week_start", name="uq_shortlist_campaign_week"),
        Index("ix_shortlist_week", "week_start"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaign.id", ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    campaign: Mapped[Campaign] = relationship(back_populates="shortlists")
    items: Mapped[list[ShortlistItem]] = relationship(
        back_populates="shortlist", cascade="all, delete-orphan", passive_deletes=True
    )


class ShortlistItem(Base):
    __tablename__ = "shortlist_item"
    __table_args__ = (
        UniqueConstraint("shortlist_id", "lead_id", name="uq_shortlist_item_lead"),
        Index("ix_shortlist_item_decision", "shortlist_id", "decision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    shortlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shortlist.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead.id", ondelete="CASCADE"), nullable=False
    )
    score_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("score_run.id", ondelete="SET NULL")
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False, default="recommended")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    product_matches: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    shortlist: Mapped[Shortlist] = relationship(back_populates="items")
    lead: Mapped[Lead] = relationship(back_populates="shortlist_items")
