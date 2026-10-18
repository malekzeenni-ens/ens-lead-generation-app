"""Creating and editing leads and moving them through the pipeline.

Part of the LeadService chain (R9); methods moved unchanged.
"""

from __future__ import annotations

import builtins
import logging
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import (
    Lead,
    LeadStageEvent,
    ProvenFit,
    SourceObservation,
    SourceSystem,
    Template,
)
from app.domains.audit.service import record_audit_event
from app.domains.catalogue.repository import CatalogueRepository
from app.domains.leads.identity import (
    normalize_business_name,
)
from app.domains.leads.lead_base import LeadServiceBase
from app.domains.leads.lead_read import (
    _AUDITED_VALUE_FIELDS,
    _IDENTIFIER_FIELDS,
    _audit_value,
)
from app.domains.leads.schemas import (
    LeadBulkUpdateRequest,
    LeadCreate,
    LeadRead,
    LeadUpdate,
    PipelineStage,
    StageChange,
)
from app.domains.leads.suppression import (
    identifier_hashes,
    lead_identifier_hashes,
    social_keys_from_urls,
)
from app.domains.outreach.state import invalidate_approved_drafts

logger = logging.getLogger(__name__)


class LeadEditing(LeadServiceBase):
    def create(self, session: Session, data: LeadCreate, correlation_id: str) -> LeadRead:
        campaign = self.campaign_repository.get(session, data.campaign_id)
        if campaign is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)

        self._assert_identifiers_allowed(
            session,
            identifier_hashes(
                business_name=data.business_name,
                location=data.location,
                website=str(data.website) if data.website else None,
                phones=[data.phone_number],
                emails=[data.public_email, data.contact_email],
                social_keys=social_keys_from_urls(
                    [
                        str(url) if url else None
                        for url in (data.social_profile, data.instagram_url, data.facebook_url)
                    ]
                ),
            ),
        )
        normalized_name = normalize_business_name(data.business_name)
        duplicate = self.repository.find_exact(session, normalized_name, data.location)
        if duplicate is not None:
            raise DomainError(
                "LEAD_DUPLICATE_REVIEW_REQUIRED",
                "A lead with the same normalised name and location requires review.",
                status_code=409,
                details={"candidate_lead_id": duplicate.id},
            )

        lead = Lead(
            business_name=data.business_name,
            normalized_name=normalized_name,
            segment=data.segment,
            location=data.location,
            website=str(data.website) if data.website else None,
            social_profile=str(data.social_profile or data.instagram_url or data.facebook_url)
            if (data.social_profile or data.instagram_url or data.facebook_url)
            else None,
            phone_number=data.phone_number,
            public_email=data.public_email.casefold() if data.public_email else None,
            contact_first_name=data.contact_first_name,
            contact_last_name=data.contact_last_name,
            contact_role=data.contact_role,
            contact_email=data.contact_email.casefold() if data.contact_email else None,
            contact_source_reference=data.contact_source_reference,
            personalisation_observation=data.personalisation_observation,
            relevance_opportunity=data.relevance_opportunity,
            offer_angle=data.offer_angle,
            desired_next_step=data.desired_next_step,
            avoid_mentioning=data.avoid_mentioning,
            contact_classification=data.contact_classification.value,
            pipeline_stage=PipelineStage.NEW.value,
        )
        self.repository.add(session, lead)
        session.flush()
        for platform, profile in (
            (None, data.social_profile),
            ("instagram", data.instagram_url),
            ("facebook", data.facebook_url),
        ):
            if profile:
                self._upsert_social_identity(
                    session,
                    lead,
                    str(profile),
                    platform=platform,
                    source_url=str(data.source.source_url) if data.source.source_url else None,
                )
        self.repository.link_campaign(session, lead.id, data.campaign_id)

        source_system = session.scalar(
            select(SourceSystem).where(SourceSystem.name == data.source.name)
        )
        if source_system is None:
            source_system = SourceSystem(
                name=data.source.name,
                source_type=data.source.source_type.value,
            )
            session.add(source_system)
            session.flush()

        session.add(
            SourceObservation(
                lead_id=lead.id,
                source_system_id=source_system.id,
                field_name="business_identity",
                observed_value=data.business_name,
                classification=data.source.classification.value,
                source_url=str(data.source.source_url) if data.source.source_url else None,
                collection_method="manual_entry",
                collected_at=data.source.collected_at,
            )
        )
        for field_name, observed_value in (
            ("public_phone", data.phone_number),
            ("public_email", data.public_email),
        ):
            if observed_value:
                session.add(
                    SourceObservation(
                        lead_id=lead.id,
                        source_system_id=source_system.id,
                        field_name=field_name,
                        observed_value=observed_value,
                        classification=data.source.classification.value,
                        source_url=str(data.source.source_url) if data.source.source_url else None,
                        collection_method="manual_entry",
                        collected_at=data.source.collected_at,
                    )
                )
        session.add(
            LeadStageEvent(
                lead_id=lead.id,
                previous_stage=None,
                new_stage=PipelineStage.NEW.value,
                actor="local_user",
                reason="Manual lead entry",
            )
        )
        record_audit_event(
            session,
            action="lead.created",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": data.campaign_id,
                "source_type": data.source.source_type.value,
            },
        )
        session.commit()
        return self._reload(session, lead.id)

    def update(
        self,
        session: Session,
        lead_id: str,
        data: LeadUpdate,
        correlation_id: str,
        *,
        commit: bool = True,
    ) -> LeadRead:
        lead = self._get_model(session, lead_id)
        changes = data.model_dump(exclude_unset=True)
        social_changes = {
            field: changes.pop(field)
            for field in ("instagram_url", "facebook_url")
            if field in changes
        }
        next_name = str(changes.get("business_name", lead.business_name))
        next_location = str(changes.get("location", lead.location))
        if "business_name" in changes or "location" in changes:
            duplicate = self.repository.find_exact(
                session, normalize_business_name(next_name), next_location
            )
            if duplicate is not None and duplicate.id != lead.id:
                raise DomainError(
                    "LEAD_DUPLICATE_REVIEW_REQUIRED",
                    "A lead with the same normalised name and location requires review.",
                    status_code=409,
                    details={"candidate_lead_id": duplicate.id},
                )

        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for field, value in changes.items():
            before[field] = _audit_value(getattr(lead, field))
            stored_value = value.value if isinstance(value, Enum) else value
            if field in {"website", "social_profile"} and stored_value is not None:
                stored_value = str(stored_value)
            if field in {"public_email", "contact_email"} and stored_value:
                stored_value = str(stored_value).casefold()
            setattr(lead, field, stored_value)
            after[field] = _audit_value(stored_value)
            if field == "social_profile" and stored_value:
                self._upsert_social_identity(session, lead, stored_value)
        for field, value in social_changes.items():
            platform = field.removesuffix("_url")
            current = next(
                (
                    identity.profile_url
                    for identity in lead.social_identities
                    if identity.platform == platform
                ),
                None,
            )
            before[field] = current
            if value is None:
                self._remove_social_identity(session, lead, platform)
                after[field] = None
            else:
                identity = self._upsert_social_identity(
                    session, lead, str(value), platform=platform
                )
                lead.social_profile = lead.social_profile or identity.profile_url
                after[field] = identity.profile_url
        if "business_name" in changes:
            lead.normalized_name = normalize_business_name(lead.business_name)
        if _IDENTIFIER_FIELDS.intersection(changes) or social_changes:
            # Checked against the lead as it will be saved, social identities included.
            session.flush()
            self._assert_identifiers_allowed(
                session, lead_identifier_hashes(session, lead), current_lead_id=lead.id
            )

        approval_sensitive_fields = {
            "public_email",
            "contact_first_name",
            "contact_last_name",
            "contact_role",
            "contact_email",
            "contact_source_reference",
            "personalisation_observation",
            "relevance_opportunity",
            "offer_angle",
            "desired_next_step",
            "avoid_mentioning",
            "contact_classification",
            "outreach_hold_until",
            "outreach_hold_reason",
        }
        invalidated_drafts = 0
        if approval_sensitive_fields.intersection(changes):
            invalidated_drafts = invalidate_approved_drafts(
                session,
                lead.id,
                "Lead contact or outreach-hold details changed after approval.",
            )

        record_audit_event(
            session,
            action="lead.updated",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "changed_fields": sorted(after),
                "values": {
                    field: {"before": before[field], "after": after[field]}
                    for field in sorted(after)
                    if field in _AUDITED_VALUE_FIELDS
                },
                "invalidated_outreach_drafts": invalidated_drafts,
            },
        )
        if commit:
            session.commit()
        else:
            session.flush()
        return self._reload(session, lead.id)

    def bulk_update(
        self,
        session: Session,
        data: LeadBulkUpdateRequest,
        correlation_id: str,
    ) -> builtins.list[LeadRead]:
        for item in data.items:
            if self.repository.get(session, item.lead_id) is None:
                raise DomainError("LEAD_NOT_FOUND", "Lead not found.", status_code=404)
        try:
            for item in data.items:
                self.update(
                    session,
                    item.lead_id,
                    item.changes,
                    correlation_id,
                    commit=False,
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
        return [self._reload(session, item.lead_id) for item in data.items]

    def change_stage(
        self,
        session: Session,
        lead_id: str,
        data: StageChange,
        correlation_id: str,
    ) -> LeadRead:
        lead = self._get_model(session, lead_id)
        if lead.suppressed and data.stage is not PipelineStage.DO_NOT_CONTACT:
            raise DomainError(
                "SUPPRESSED_LEAD_STAGE_BLOCKED",
                "Lift suppression before moving this lead out of Do Not Contact.",
                status_code=409,
            )
        if lead.pipeline_stage == data.stage.value:
            raise DomainError(
                "LEAD_STAGE_UNCHANGED",
                "The lead is already in this pipeline stage.",
                status_code=409,
            )
        previous_stage = lead.pipeline_stage
        lead.pipeline_stage = data.stage.value
        invalidated_drafts = invalidate_approved_drafts(
            session,
            lead.id,
            "Lead pipeline stage changed after approval.",
        )
        session.add(
            LeadStageEvent(
                lead_id=lead.id,
                previous_stage=previous_stage,
                new_stage=data.stage.value,
                actor="local_user",
                reason=data.reason,
            )
        )
        recorded_fit = False
        if data.stage is PipelineStage.WON:
            recorded_fit = self._record_proven_fit(session, lead)
        record_audit_event(
            session,
            action="lead.stage_changed",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "previous_stage": previous_stage,
                "new_stage": data.stage.value,
                "reason_provided": bool(data.reason),
                "invalidated_outreach_drafts": invalidated_drafts,
                "proven_fit_recorded": recorded_fit,
            },
        )
        session.commit()
        return self._reload(session, lead.id)

    @staticmethod
    def _record_proven_fit(session: Session, lead: Lead) -> bool:
        """Capture a won lead as evidence for future outreach.

        Created without a dialog, because the operator should not have to stop and fill a form to
        record something the app already knows. It starts unconfirmed and with the client's name
        withheld, so nothing reaches a prospect until he says it can.
        """
        repository = CatalogueRepository()
        if repository.fit_exists_for_lead(session, lead.id):
            return False
        approved = [
            draft
            for draft in lead.outreach_drafts
            if draft.review_status == "approved" or draft.sync_status == "user_confirmed_sent"
        ]
        handles: list[str] = []
        for draft in approved:
            template = session.get(Template, draft.template_id) if draft.template_id else None
            if template is None:
                continue
            for family_id in template.product_family_ids:
                family = repository.get_family(session, family_id)
                if family is None:
                    continue
                for product in repository.by_ids(session, family.product_ids):
                    if product.shopify_handle and product.shopify_handle not in handles:
                        handles.append(product.shopify_handle)
        location = lead.location.split(",")[0].strip() if lead.location else ""
        label = f"a {lead.segment} in {location}" if location else f"a {lead.segment}"
        repository.add_fit(
            session,
            ProvenFit(
                segment=lead.segment,
                product_handles=handles,
                use=("Won through this app. Confirm what was made before using this in an email."),
                outcome="Won.",
                client_label=label,
                client_name=lead.business_name,
                share_client_name=False,
                status="please_confirm",
                lead_id=lead.id,
            ),
        )
        return True
