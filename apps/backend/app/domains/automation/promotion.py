"""Turning a discovery candidate into a lead, or linking it to an existing one.

Part of the CampaignAutomationService chain (R9); methods moved unchanged.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Campaign,
    DiscoveryCandidate,
    Lead,
    LeadCampaign,
    LeadSocialIdentity,
    LeadStageEvent,
)
from app.domains.automation.base import AutomationBase
from app.domains.automation.candidate_data import (
    _candidate_phone,
    _candidate_public_email,
    _candidate_social_profiles,
    _lead_match_keys,
)
from app.domains.automation.schemas import (
    CandidateStatus,
)
from app.domains.leads.identity import (
    normalize_business_name,
)
from app.domains.leads.matching import MatchKind, match, match_keys
from app.domains.leads.suppression import find_active_suppression, identifier_hashes

logger = logging.getLogger(__name__)


class AutomationPromotion(AutomationBase):
    def _attach_evidence(self, session: Session, candidate: DiscoveryCandidate, lead: Lead) -> None:
        social_capture = candidate.provider.startswith("assisted_")
        if social_capture:
            source_name = f"Assisted {candidate.provider.removeprefix('assisted_').title()} capture"
            source_type = candidate.provider.removeprefix("assisted_")
            collection_method = "operator_assisted_social_capture"
        elif candidate.provider == "instagram":
            source_name = "Instagram via official Meta API"
            source_type = "instagram"
            collection_method = "official_meta_business_discovery"
        elif candidate.provider == "public_registries":
            collection_method = "official_meta_business_discovery"
            if "fhrs" in candidate.evidence:
                source_name = "UK Food Standards Agency register (verified via Meta)"
                source_type = "fhrs"
            elif "event_directory" in candidate.evidence:
                source_name = "Event directory (verified via Meta)"
                source_type = "event_directory"
            else:
                source_name = "Public registries and directories"
                source_type = "public_registries"
        else:
            source_name = "Google Places"
            source_type = "google"
            collection_method = "google_places_text_search"
        provider_source = self._source_system(session, source_name, source_type)
        self._add_observation(
            session,
            lead_id=lead.id,
            source=provider_source,
            field_name="business_identity",
            value=candidate.business_name,
            source_url=candidate.source_url,
            collection_method=collection_method,
        )
        self._add_observation(
            session,
            lead_id=lead.id,
            source=provider_source,
            field_name="business_location",
            value=candidate.location,
            source_url=candidate.source_url,
            collection_method=collection_method,
        )
        self._add_observation(
            session,
            lead_id=lead.id,
            source=provider_source,
            field_name="public_phone",
            value=_candidate_phone(candidate),
            source_url=candidate.source_url,
            collection_method=collection_method,
        )
        self._add_observation(
            session,
            lead_id=lead.id,
            source=provider_source,
            field_name="provider_types",
            value=", ".join(candidate.place_types) or None,
            source_url=candidate.source_url,
            collection_method=collection_method,
        )
        candidate_phone = _candidate_phone(candidate)
        candidate_email = _candidate_public_email(candidate)
        if not lead.website and candidate.website:
            lead.website = candidate.website
        if not lead.phone_number and candidate_phone:
            lead.phone_number = candidate_phone[:100]
        if not lead.public_email and candidate_email:
            lead.public_email = candidate_email[:320]

        for platform, handle, canonical in _candidate_social_profiles(candidate):
            existing = session.scalar(
                select(LeadSocialIdentity).where(
                    LeadSocialIdentity.platform == platform,
                    LeadSocialIdentity.normalized_handle == handle,
                )
            )
            if existing is None:
                session.add(
                    LeadSocialIdentity(
                        lead_id=lead.id,
                        platform=platform,
                        profile_url=canonical,
                        normalized_handle=handle,
                        source_url=candidate.source_url or canonical,
                        classification="provider_observed",
                        collected_at=datetime.now(UTC),
                    )
                )
            elif existing.lead_id == lead.id:
                existing.profile_url = canonical
                existing.source_url = candidate.source_url or canonical
            lead.social_profile = lead.social_profile or canonical
        website_evidence = candidate.evidence.get("website")
        if isinstance(website_evidence, dict):
            website = self._source_system(session, "Public website", "website")
            for field_name in ("title", "description"):
                value = website_evidence.get(field_name)
                self._add_observation(
                    session,
                    lead_id=lead.id,
                    source=website,
                    field_name=f"website_{field_name}",
                    value=str(value) if value else None,
                    source_url=candidate.website,
                    collection_method="safe_homepage_enrichment",
                )
            emails = website_evidence.get("public_emails")
            if isinstance(emails, list):
                self._add_observation(
                    session,
                    lead_id=lead.id,
                    source=website,
                    field_name="public_email",
                    value=", ".join(str(value) for value in emails),
                    source_url=candidate.website,
                    collection_method="safe_homepage_enrichment",
                )
            phones = website_evidence.get("public_phones")
            if isinstance(phones, list):
                self._add_observation(
                    session,
                    lead_id=lead.id,
                    source=website,
                    field_name="public_phone",
                    value=", ".join(str(value) for value in phones),
                    source_url=candidate.website,
                    collection_method="safe_contact_enrichment",
                )
            for social_link in website_evidence.get("social_links", []):
                self._add_observation(
                    session,
                    lead_id=lead.id,
                    source=website,
                    field_name="social_profile",
                    value=str(social_link),
                    source_url=candidate.website,
                    collection_method="safe_contact_enrichment",
                )
        social_evidence = candidate.evidence.get("social_profile")
        if isinstance(social_evidence, dict):
            for field_name in ("public_email", "public_bio"):
                value = social_evidence.get(field_name)
                self._add_observation(
                    session,
                    lead_id=lead.id,
                    source=provider_source,
                    field_name=field_name,
                    value=str(value) if value else None,
                    source_url=candidate.source_url,
                    collection_method=collection_method,
                )

    def _link_existing(self, session: Session, candidate: DiscoveryCandidate, lead: Lead) -> None:
        if not self.repository.is_linked(session, lead.id, candidate.campaign_id):
            session.add(LeadCampaign(lead_id=lead.id, campaign_id=candidate.campaign_id))
        self._attach_evidence(session, candidate, lead)
        candidate.matched_lead_id = lead.id
        candidate.status = CandidateStatus.LINKED_EXISTING.value

    def _promote_candidate(
        self, session: Session, candidate: DiscoveryCandidate, *, force: bool = False
    ) -> Lead | None:
        previous = self.repository.previous_provider_match(
            session, candidate.provider, candidate.provider_record_id
        )
        if previous is not None and previous.matched_lead_id:
            lead = self.lead_repository.get(session, previous.matched_lead_id)
            if lead is not None:
                self._link_existing(session, candidate, lead)
                return lead

        existing_leads = {lead.id: lead for lead in self.repository.candidate_leads(session)}
        result = match(
            match_keys(
                business_name=candidate.business_name,
                location=candidate.location,
                website=candidate.website,
                phone=_candidate_phone(candidate),
                emails=[_candidate_public_email(candidate)],
                social=[
                    (platform, handle)
                    for platform, handle, _ in _candidate_social_profiles(candidate)
                ],
            ),
            ((lead.id, _lead_match_keys(lead)) for lead in existing_leads.values()),
        )
        log_context = {
            "discovery_candidate_id": candidate.id,
            "campaign_run_id": candidate.run_id,
            "matched_lead_id": result.lead_id,
            "match_rank": result.rank.name if result.rank else None,
        }
        if result.kind is MatchKind.EXACT and result.lead_id is not None:
            lead = existing_leads[result.lead_id]
            self._link_existing(session, candidate, lead)
            logger.info("Discovery candidate linked to an existing lead", extra=log_context)
            return lead
        if result.kind is MatchKind.REVIEW and not force:
            candidate.status = CandidateStatus.REVIEW_REQUIRED.value
            candidate.matched_lead_id = result.lead_id
            candidate.duplicate_confidence = result.confidence
            candidate.review_reason = result.reason
            logger.info("Discovery candidate held for duplicate review", extra=log_context)
            return None

        lead_name = candidate.business_name[:200]
        lead_location = candidate.location[:200]
        suppression = find_active_suppression(
            session,
            identifier_hashes(
                business_name=lead_name,
                location=lead_location,
                website=candidate.website,
                phones=[_candidate_phone(candidate)],
                emails=[_candidate_public_email(candidate)],
                social_keys=[
                    (platform, handle)
                    for platform, handle, _ in _candidate_social_profiles(candidate)
                ],
            ),
            include_name_only=not force,
        )
        if suppression is not None:
            log_context = {
                "discovery_candidate_id": candidate.id,
                "campaign_run_id": candidate.run_id,
                "suppression_id": suppression.record.id,
                "matched_identifier": suppression.kind.value,
            }
            if suppression.strong:
                candidate.status = CandidateStatus.REJECTED.value
                candidate.rejection_reason = (
                    f"Matched an active suppression by its {suppression.label}."
                )
                logger.info("Discovery candidate rejected by a suppression", extra=log_context)
            else:
                candidate.status = CandidateStatus.REVIEW_REQUIRED.value
                candidate.matched_lead_id = suppression.record.lead_id
                candidate.review_reason = (
                    "The name matches a suppressed business. Promote it only if this is a "
                    "different business."
                )
                logger.info("Discovery candidate held for suppression review", extra=log_context)
            return None
        lead = Lead(
            business_name=lead_name,
            normalized_name=normalize_business_name(lead_name)[:200],
            segment=candidate.run.campaign.segment,
            location=lead_location,
            website=candidate.website,
            social_profile=(
                _candidate_social_profiles(candidate)[0][2]
                if _candidate_social_profiles(candidate)
                else None
            ),
            phone_number=_candidate_phone(candidate),
            public_email=_candidate_public_email(candidate),
            contact_classification="unknown",
            pipeline_stage="new",
        )
        session.add(lead)
        session.flush()
        session.add(LeadCampaign(lead_id=lead.id, campaign_id=candidate.campaign_id))
        session.add(
            LeadStageEvent(
                lead_id=lead.id,
                previous_stage=None,
                new_stage="new",
                actor="campaign_run",
                reason="Promoted from controlled provider discovery",
            )
        )
        self._attach_evidence(session, candidate, lead)
        candidate.matched_lead_id = lead.id
        candidate.status = CandidateStatus.PROMOTED.value
        return lead

    @staticmethod
    def _excluded(candidate: DiscoveryCandidate, campaign: Campaign) -> str | None:
        text = " ".join(
            [
                candidate.business_name,
                candidate.location,
                candidate.website or "",
                *candidate.place_types,
            ]
        ).casefold()
        for keyword in campaign.exclusion_keywords:
            if keyword.casefold() in text:
                return f"Matched campaign exclusion keyword: {keyword}"
        return None
