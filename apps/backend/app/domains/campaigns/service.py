from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import Campaign, Template
from app.domains.audit.service import record_audit_event
from app.domains.campaigns.repository import CampaignRepository
from app.domains.campaigns.schemas import (
    CampaignCreate,
    CampaignDeleteResult,
    CampaignDuplicate,
    CampaignStatus,
    CampaignUpdate,
    DiscoveryMode,
)
from app.domains.catalogue.repository import CatalogueRepository


class CampaignService:
    def __init__(
        self,
        repository: CampaignRepository | None = None,
        catalogue_repository: CatalogueRepository | None = None,
    ) -> None:
        self.repository = repository or CampaignRepository()
        self.catalogue_repository = catalogue_repository or CatalogueRepository()

    def _require_family(self, session: Session, family_id: str) -> None:
        if self.catalogue_repository.get_family(session, family_id) is None:
            raise DomainError(
                "PRODUCT_FAMILY_NOT_FOUND", "Product family not found.", status_code=404
            )

    @staticmethod
    def _validate_weekly_outreach(
        session: Session,
        *,
        enabled: bool,
        template_id: str | None,
        provider: str,
        discovery_sources: list[str],
    ) -> None:
        if enabled and template_id is None:
            raise DomainError(
                "WEEKLY_OUTREACH_TEMPLATE_REQUIRED",
                "Choose an email template before enabling weekly outreach.",
            )
        if template_id is not None and session.get(Template, template_id) is None:
            raise DomainError("TEMPLATE_NOT_FOUND", "Template not found.", status_code=404)
        if provider != "scoring" and provider not in discovery_sources:
            raise DomainError(
                "WEEKLY_OUTREACH_PROVIDER_NOT_SELECTED",
                "The weekly provider must also be selected as a campaign discovery source.",
            )

    def create(self, session: Session, data: CampaignCreate, correlation_id: str) -> Campaign:
        return self._create(session, data, correlation_id, action="campaign.created")

    def _create(
        self,
        session: Session,
        data: CampaignCreate,
        correlation_id: str,
        *,
        action: str,
        source_campaign_id: str | None = None,
    ) -> Campaign:
        if self.repository.get_by_name(session, data.name) is not None:
            raise DomainError(
                "CAMPAIGN_NAME_EXISTS",
                "A campaign with this name already exists.",
                status_code=409,
            )
        if data.product_family_id is not None:
            self._require_family(session, data.product_family_id)
        self._validate_weekly_outreach(
            session,
            enabled=data.weekly_outreach_enabled,
            template_id=data.weekly_outreach_template_id,
            provider=data.weekly_outreach_provider,
            discovery_sources=data.discovery_sources,
        )
        campaign = Campaign(
            name=data.name,
            description=data.description,
            segment=data.segment,
            primary_location=data.primary_location,
            radius_miles=data.radius_miles,
            keywords=data.keywords,
            exclusion_keywords=data.exclusion_keywords,
            product_categories=data.product_categories,
            product_family_id=data.product_family_id,
            discovery_sources=data.discovery_sources,
            weekly_shortlist_size=data.weekly_shortlist_size,
            minimum_score_threshold=data.minimum_score_threshold,
            preferred_channels=data.preferred_channels,
            offer_settings=data.offer_settings,
            discovery_mode=data.discovery_mode.value,
            weekly_outreach_enabled=data.weekly_outreach_enabled,
            weekly_outreach_template_id=data.weekly_outreach_template_id,
            weekly_outreach_provider=data.weekly_outreach_provider,
            status=data.status.value,
        )
        self.repository.add(session, campaign)
        session.flush()
        record_audit_event(
            session,
            action=action,
            entity_type="campaign",
            entity_id=campaign.id,
            correlation_id=correlation_id,
            summary={
                "name": campaign.name,
                "segment": campaign.segment,
                **({"source_campaign_id": source_campaign_id} if source_campaign_id else {}),
            },
        )
        session.commit()
        session.refresh(campaign)
        return campaign

    def list(
        self, session: Session, *, query: str | None = None, status: str | None = None
    ) -> list[Campaign]:
        return self.repository.list(session, query=query, status=status)

    def get(self, session: Session, campaign_id: str) -> Campaign:
        campaign = self.repository.get(session, campaign_id)
        if campaign is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)
        return campaign

    def update(
        self,
        session: Session,
        campaign_id: str,
        data: CampaignUpdate,
        correlation_id: str,
    ) -> Campaign:
        campaign = self.get(session, campaign_id)
        changes = data.model_dump(exclude_unset=True)
        is_archiving = (
            changes.get("status") == CampaignStatus.INACTIVE
            and campaign.status != CampaignStatus.INACTIVE.value
        )
        if is_archiving and self.repository.has_active_run(session, campaign_id):
            raise DomainError(
                "CAMPAIGN_ARCHIVE_RUN_ACTIVE",
                (
                    "Wait for the active campaign run to finish or cancel it before archiving "
                    "this campaign."
                ),
                status_code=409,
            )
        if "name" in changes and changes["name"] != campaign.name:
            existing = self.repository.get_by_name(session, str(changes["name"]))
            if existing is not None:
                raise DomainError(
                    "CAMPAIGN_NAME_EXISTS",
                    "A campaign with this name already exists.",
                    status_code=409,
                )
        if changes.get("product_family_id") is not None:
            self._require_family(session, changes["product_family_id"])
        self._validate_weekly_outreach(
            session,
            enabled=bool(changes.get("weekly_outreach_enabled", campaign.weekly_outreach_enabled)),
            template_id=changes.get(
                "weekly_outreach_template_id", campaign.weekly_outreach_template_id
            ),
            provider=str(
                changes.get("weekly_outreach_provider", campaign.weekly_outreach_provider)
            ),
            discovery_sources=list(changes.get("discovery_sources", campaign.discovery_sources)),
        )
        before = {field: getattr(campaign, field) for field in changes}
        for field, value in changes.items():
            setattr(campaign, field, value.value if hasattr(value, "value") else value)
        record_audit_event(
            session,
            action="campaign.updated",
            entity_type="campaign",
            entity_id=campaign.id,
            correlation_id=correlation_id,
            summary={"before": before, "after": changes},
        )
        session.commit()
        session.refresh(campaign)
        return campaign

    def duplicate(
        self,
        session: Session,
        campaign_id: str,
        data: CampaignDuplicate,
        correlation_id: str,
    ) -> Campaign:
        source = self.get(session, campaign_id)
        duplicate = CampaignCreate(
            name=data.name,
            description=source.description,
            segment=data.segment or source.segment,
            primary_location=data.primary_location or source.primary_location,
            radius_miles=source.radius_miles,
            keywords=source.keywords,
            exclusion_keywords=source.exclusion_keywords,
            product_categories=source.product_categories,
            product_family_id=source.product_family_id,
            discovery_sources=source.discovery_sources,
            weekly_shortlist_size=source.weekly_shortlist_size,
            minimum_score_threshold=source.minimum_score_threshold,
            preferred_channels=source.preferred_channels,
            offer_settings=source.offer_settings,
            discovery_mode=DiscoveryMode(source.discovery_mode),
            weekly_outreach_enabled=False,
            weekly_outreach_template_id=source.weekly_outreach_template_id,
            weekly_outreach_provider=source.weekly_outreach_provider,
            status=data.status,
        )
        return self._create(
            session,
            duplicate,
            correlation_id,
            action="campaign.duplicated",
            source_campaign_id=source.id,
        )

    def delete(
        self,
        session: Session,
        campaign_id: str,
        correlation_id: str,
    ) -> CampaignDeleteResult:
        campaign = self.get(session, campaign_id)
        if self.repository.has_active_run(session, campaign_id):
            raise DomainError(
                "CAMPAIGN_DELETE_RUN_ACTIVE",
                (
                    "Wait for the active campaign run to finish or cancel it before deleting "
                    "this campaign."
                ),
                status_code=409,
            )

        exclusive_leads, shared_count = self.repository.deletion_leads(session, campaign_id)
        exclusive_lead_ids = [lead_id for lead_id, _ in exclusive_leads]
        associated_count = len(exclusive_lead_ids) + shared_count

        for lead_id, suppression_evidence_retained in exclusive_leads:
            record_audit_event(
                session,
                action="lead.deleted",
                entity_type="lead",
                entity_id=lead_id,
                correlation_id=correlation_id,
                summary={
                    "campaign_id": campaign_id,
                    "deletion_mode": "campaign_cascade",
                    "suppression_evidence_retained": suppression_evidence_retained,
                },
            )

        record_audit_event(
            session,
            action="campaign.deleted",
            entity_type="campaign",
            entity_id=campaign_id,
            correlation_id=correlation_id,
            summary={
                "name": campaign.name,
                "associated_leads": associated_count,
                "leads_deleted": len(exclusive_lead_ids),
                "shared_leads_retained": shared_count,
            },
        )
        outreach_batches_deleted = self.repository.delete_cascade(
            session,
            campaign_id,
            exclusive_lead_ids,
        )
        session.commit()
        return CampaignDeleteResult(
            deleted=True,
            campaign_id=campaign_id,
            associated_leads=associated_count,
            leads_deleted=len(exclusive_lead_ids),
            shared_leads_retained=shared_count,
            outreach_batches_deleted=outreach_batches_deleted,
        )
