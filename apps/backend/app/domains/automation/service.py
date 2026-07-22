from __future__ import annotations

import logging
from contextlib import suppress
from datetime import UTC, datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import (
    Campaign,
    CampaignRun,
    DiscoveryCandidate,
    Lead,
    LeadCampaign,
    LeadSocialIdentity,
    LeadStageEvent,
    ProviderAttempt,
    SourceObservation,
    SourceSystem,
)
from app.domains.audit.service import record_audit_event
from app.domains.automation.enrichment import EnrichmentFailure, SafeWebsiteEnricher
from app.domains.automation.providers import (
    DiscoveryBatch,
    DiscoveryProvider,
    GooglePlacesProvider,
    InstagramProfessionalProfile,
    MetaInstagramProvider,
    ProviderFailure,
    PublicRegistryProvider,
)
from app.domains.automation.repository import AutomationRepository
from app.domains.automation.schemas import (
    CampaignRunProvider,
    CampaignRunRead,
    CampaignRunStatus,
    CandidateDecision,
    CandidateDecisionAction,
    CandidateStatus,
    DiscoveryCandidateRead,
    InstagramProfileRead,
    ProviderAttemptRead,
    SocialCandidateCapture,
)
from app.domains.campaigns.repository import CampaignRepository
from app.domains.leads.identity import phone_match_key, social_identity
from app.domains.leads.repository import LeadRepository
from app.domains.leads.service import lead_identifier_hash, normalize_business_name
from app.domains.qualification.service import QualificationService

logger = logging.getLogger(__name__)

DEFAULT_METRICS = {
    "discovered": 0,
    "promoted": 0,
    "linked_existing": 0,
    "review_required": 0,
    "rejected": 0,
    "enriched": 0,
    "enrichment_failed": 0,
    "leads_scored": 0,
    "scores_unchanged": 0,
    "qualified": 0,
    "skipped": 0,
    "shortlist_selected": 0,
    "shortlist_created": 0,
    "failures": 0,
}


def _run_to_read(run: CampaignRun) -> CampaignRunRead:
    return CampaignRunRead(
        id=run.id,
        batch_id=run.batch_id,
        campaign_id=run.campaign_id,
        campaign_name=run.campaign.name,
        trigger=run.trigger,
        status=run.status,
        phase=run.phase,
        provider_status=run.provider_status,
        query_summary=run.query_summary,
        metrics=dict(DEFAULT_METRICS) | run.metrics,
        warnings=run.warnings,
        error_code=run.error_code,
        error_message=run.error_message,
        cancellation_requested=run.cancellation_requested,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        updated_at=run.updated_at,
        candidates=[
            DiscoveryCandidateRead.model_validate(candidate)
            for candidate in sorted(run.candidates, key=lambda item: item.created_at)
        ],
        attempts=[
            ProviderAttemptRead.model_validate(attempt)
            for attempt in sorted(run.attempts, key=lambda item: item.started_at)
        ],
    )


def _website_host(value: str | None) -> str | None:
    if not value:
        return None
    host = (urlparse(value).hostname or "").casefold()
    return host.removeprefix("www.") or None


def _candidate_website_evidence(candidate: DiscoveryCandidate) -> dict[str, object]:
    value = candidate.evidence.get("website")
    return value if isinstance(value, dict) else {}


def _candidate_public_email(candidate: DiscoveryCandidate) -> str | None:
    social = candidate.evidence.get("social_profile")
    if isinstance(social, dict) and social.get("public_email"):
        return str(social["public_email"]).casefold()
    emails = _candidate_website_evidence(candidate).get("public_emails")
    if isinstance(emails, list) and emails:
        return str(emails[0]).casefold()
    return None


def _candidate_phone(candidate: DiscoveryCandidate) -> str | None:
    if candidate.phone:
        return candidate.phone
    phones = _candidate_website_evidence(candidate).get("public_phones")
    return str(phones[0]) if isinstance(phones, list) and phones else None


def _candidate_social_profiles(
    candidate: DiscoveryCandidate,
) -> list[tuple[str, str, str]]:
    values: list[tuple[str, str, str]] = []
    social = candidate.evidence.get("social_profile")
    if isinstance(social, dict) and social.get("platform") and social.get("profile_url"):
        with suppress(ValueError):
            values.append(social_identity(str(social["profile_url"]), str(social["platform"])))
    links = _candidate_website_evidence(candidate).get("social_links")
    if isinstance(links, list):
        for link in links:
            try:
                identity = social_identity(str(link))
            except ValueError:
                continue
            if identity[0] in {"instagram", "facebook"} and identity not in values:
                values.append(identity)
    return values


class CampaignAutomationService:
    def __init__(
        self,
        settings: Settings,
        repository: AutomationRepository | None = None,
        campaign_repository: CampaignRepository | None = None,
        lead_repository: LeadRepository | None = None,
        qualification: QualificationService | None = None,
        provider: GooglePlacesProvider | None = None,
        instagram_provider: MetaInstagramProvider | None = None,
        enricher: SafeWebsiteEnricher | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or AutomationRepository()
        self.campaign_repository = campaign_repository or CampaignRepository()
        self.lead_repository = lead_repository or LeadRepository()
        self.qualification = qualification or QualificationService()
        self.provider = provider or GooglePlacesProvider(settings)
        self.instagram_provider = instagram_provider
        self.enricher = enricher or SafeWebsiteEnricher(settings)

    def queue(
        self,
        session: Session,
        campaign_id: str,
        *,
        batch_id: str | None = None,
        trigger: str | None = None,
        requested_provider: CampaignRunProvider = CampaignRunProvider.SCORING,
        correlation_id: str,
    ) -> str:
        campaign = self.campaign_repository.get(session, campaign_id)
        if campaign is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)
        if campaign.status != "active":
            raise DomainError(
                "CAMPAIGN_NOT_ACTIVE",
                "Only active campaigns can be run.",
                status_code=409,
            )
        if (
            requested_provider is not CampaignRunProvider.SCORING
            and requested_provider.value not in campaign.discovery_sources
        ):
            raise DomainError(
                "CAMPAIGN_PROVIDER_NOT_SELECTED",
                f"{requested_provider.value.replace('_', ' ').title()} is not selected for "
                "this campaign.",
                status_code=409,
            )
        active = session.scalar(
            select(CampaignRun).where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status.in_(("queued", "running")),
            )
        )
        if active is not None:
            raise DomainError(
                "CAMPAIGN_RUN_ACTIVE",
                "This campaign already has an active run.",
                status_code=409,
                details={"campaign_run_id": active.id},
            )
        run = CampaignRun(
            batch_id=batch_id or str(uuid4()),
            campaign_id=campaign_id,
            trigger=trigger or f"manual_{requested_provider.value}",
            status=CampaignRunStatus.QUEUED.value,
            phase="queued",
            metrics=dict(DEFAULT_METRICS),
        )
        session.add(run)
        session.flush()
        record_audit_event(
            session,
            action="campaign_run.queued",
            entity_type="campaign_run",
            entity_id=run.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": campaign_id,
                "batch_id": run.batch_id,
                "provider": requested_provider.value,
            },
        )
        session.commit()
        return run.id

    def list_runs(
        self, session: Session, *, campaign_id: str | None = None
    ) -> list[CampaignRunRead]:
        return [
            _run_to_read(run) for run in self.repository.list_runs(session, campaign_id=campaign_id)
        ]

    def get_run(self, session: Session, run_id: str) -> CampaignRunRead:
        run = self.repository.get_run(session, run_id)
        if run is None:
            raise DomainError("CAMPAIGN_RUN_NOT_FOUND", "Campaign run not found.", status_code=404)
        return _run_to_read(run)

    def request_cancellation(
        self, session: Session, run_id: str, correlation_id: str
    ) -> CampaignRunRead:
        run = self.repository.get_run(session, run_id)
        if run is None:
            raise DomainError("CAMPAIGN_RUN_NOT_FOUND", "Campaign run not found.", status_code=404)
        if run.status not in {"queued", "running"}:
            raise DomainError(
                "CAMPAIGN_RUN_FINISHED",
                "Only an active campaign run can be cancelled.",
                status_code=409,
            )
        run.cancellation_requested = True
        record_audit_event(
            session,
            action="campaign_run.cancellation_requested",
            entity_type="campaign_run",
            entity_id=run.id,
            correlation_id=correlation_id,
            summary={"campaign_id": run.campaign_id},
        )
        session.commit()
        session.expire_all()
        stored = self.repository.get_run(session, run_id)
        if stored is None:
            raise RuntimeError("Campaign run could not be reloaded")
        return _run_to_read(stored)

    @staticmethod
    def _cancel_if_requested(session: Session, run: CampaignRun) -> None:
        session.refresh(run, attribute_names=["cancellation_requested"])
        if run.cancellation_requested:
            run.status = CampaignRunStatus.CANCELLED.value
            run.phase = "cancelled"
            run.completed_at = datetime.now(UTC)
            session.commit()
            raise InterruptedError("Campaign run cancelled")

    @staticmethod
    def _source_system(session: Session, name: str, source_type: str) -> SourceSystem:
        source = session.scalar(select(SourceSystem).where(SourceSystem.name == name))
        if source is None:
            source = SourceSystem(name=name, source_type=source_type)
            session.add(source)
            session.flush()
        return source

    @staticmethod
    def _add_observation(
        session: Session,
        *,
        lead_id: str,
        source: SourceSystem,
        field_name: str,
        value: str | None,
        source_url: str | None,
        collection_method: str,
    ) -> None:
        if not value:
            return
        existing = session.scalar(
            select(SourceObservation).where(
                SourceObservation.lead_id == lead_id,
                SourceObservation.source_system_id == source.id,
                SourceObservation.field_name == field_name,
                SourceObservation.observed_value == value,
                SourceObservation.source_url == source_url,
            )
        )
        if existing is not None:
            return
        session.add(
            SourceObservation(
                lead_id=lead_id,
                source_system_id=source.id,
                field_name=field_name,
                observed_value=value,
                classification="provider_observed",
                source_url=source_url,
                collection_method=collection_method,
                collected_at=datetime.now(UTC),
            )
        )

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

        candidates = self.repository.candidate_leads(session)
        candidate_host = _website_host(candidate.website)
        candidate_phone_key = phone_match_key(_candidate_phone(candidate))
        candidate_email = _candidate_public_email(candidate)
        candidate_social_keys = {
            (platform, handle) for platform, handle, _ in _candidate_social_profiles(candidate)
        }
        exact: Lead | None = None
        fuzzy: tuple[Lead, float] | None = None
        for lead in candidates:
            same_host = candidate_host and candidate_host == _website_host(lead.website)
            same_name = lead.normalized_name == candidate.normalized_name
            same_phone = bool(
                candidate_phone_key and candidate_phone_key == phone_match_key(lead.phone_number)
            )
            same_email = bool(
                candidate_email
                and lead.public_email
                and candidate_email == lead.public_email.casefold()
            )
            lead_social_keys = {
                (identity.platform, identity.normalized_handle)
                for identity in lead.social_identities
            }
            same_social = bool(candidate_social_keys & lead_social_keys)
            if same_host or same_name or same_phone or same_email or same_social:
                exact = lead
                break
            confidence = SequenceMatcher(
                None, candidate.normalized_name, lead.normalized_name
            ).ratio()
            if confidence >= 0.94 and (fuzzy is None or confidence > fuzzy[1]):
                fuzzy = (lead, confidence)
        if exact is not None:
            self._link_existing(session, candidate, exact)
            return exact
        if fuzzy is not None and not force:
            candidate.status = CandidateStatus.REVIEW_REQUIRED.value
            candidate.matched_lead_id = fuzzy[0].id
            candidate.duplicate_confidence = round(fuzzy[1], 3)
            return None

        lead_name = candidate.business_name[:200]
        lead_location = candidate.location[:200]
        suppression = self.lead_repository.active_suppression_by_hash(
            session, lead_identifier_hash(lead_name, lead_location)
        )
        if suppression is not None:
            candidate.status = CandidateStatus.REJECTED.value
            candidate.rejection_reason = "Matched an active suppression identifier."
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

    def _store_discovery_batch(
        self,
        session: Session,
        run: CampaignRun,
        campaign: Campaign,
        provider_name: str,
        batch: DiscoveryBatch,
    ) -> None:
        metrics = dict(DEFAULT_METRICS) | run.metrics
        for business in batch.businesses:
            existing = session.scalar(
                select(DiscoveryCandidate).where(
                    DiscoveryCandidate.run_id == run.id,
                    DiscoveryCandidate.provider == provider_name,
                    DiscoveryCandidate.provider_record_id == business.provider_record_id,
                )
            )
            if existing is not None:
                continue
            candidate = DiscoveryCandidate(
                run_id=run.id,
                campaign_id=campaign.id,
                provider=provider_name,
                provider_record_id=business.provider_record_id,
                business_name=business.business_name,
                normalized_name=normalize_business_name(business.business_name)[:300],
                location=business.location,
                website=business.website,
                phone=business.phone,
                source_url=business.source_url,
                latitude=business.latitude,
                longitude=business.longitude,
                place_types=business.place_types,
                evidence=business.evidence,
            )
            session.add(candidate)
            session.flush()
            metrics["discovered"] += 1
            exclusion = self._excluded(candidate, campaign)
            if exclusion:
                candidate.status = CandidateStatus.REJECTED.value
                candidate.rejection_reason = exclusion
                metrics["rejected"] += 1
                continue
            if candidate.website:
                try:
                    evidence = self.enricher.enrich(candidate.website)
                    candidate.evidence = {
                        **candidate.evidence,
                        "website": {
                            "final_url": evidence.final_url,
                            "title": evidence.title,
                            "description": evidence.description,
                            "public_emails": evidence.public_emails,
                            "public_phones": evidence.public_phones,
                            "social_links": evidence.social_links,
                            "contact_links": evidence.contact_links,
                            "pages_checked": evidence.pages_checked,
                        },
                    }
                    metrics["enriched"] += 1
                except EnrichmentFailure as exc:
                    candidate.evidence = {
                        **candidate.evidence,
                        "website_enrichment": {
                            "status": "skipped",
                            "code": exc.code,
                            "message": exc.safe_message,
                        },
                    }
                    metrics["enrichment_failed"] += 1
            self._promote_candidate(session, candidate)
            if candidate.status == CandidateStatus.PROMOTED.value:
                metrics["promoted"] += 1
            elif candidate.status == CandidateStatus.LINKED_EXISTING.value:
                metrics["linked_existing"] += 1
            elif candidate.status == CandidateStatus.REVIEW_REQUIRED.value:
                metrics["review_required"] += 1
            elif candidate.status == CandidateStatus.REJECTED.value:
                metrics["rejected"] += 1
            self._cancel_if_requested(session, run)
        run.metrics = metrics
        if batch.warnings:
            run.warnings = [*run.warnings, *batch.warnings]

    def _run_discovery_provider(
        self,
        session: Session,
        run: CampaignRun,
        campaign: Campaign,
        provider_name: str,
        provider: DiscoveryProvider,
    ) -> bool:
        planned_query = ", ".join(campaign.keywords or [campaign.segment])
        attempt = ProviderAttempt(
            run_id=run.id,
            provider=provider_name,
            status="running",
            query=f"{planned_query} in {campaign.primary_location}",
        )
        self.repository.add_attempt(session, attempt)
        run.provider_status = "running"
        session.commit()
        try:
            batch = provider.discover(campaign)
            query_summary = "; ".join(batch.queries)
            attempt.query = query_summary or attempt.query
            attempt.request_count = batch.request_count
            attempt.response_count = len(batch.businesses)
            attempt.status = "completed"
            attempt.completed_at = datetime.now(UTC)
            summaries = [value for value in (run.query_summary, query_summary) if value]
            run.query_summary = " | ".join(summaries)
            self._store_discovery_batch(session, run, campaign, provider_name, batch)
            session.commit()
            return True
        except ProviderFailure as exc:
            attempt.status = "failed"
            attempt.error_code = exc.code
            attempt.error_message = exc.safe_message
            attempt.completed_at = datetime.now(UTC)
            run.warnings = [*run.warnings, exc.safe_message]
            metrics = dict(DEFAULT_METRICS) | run.metrics
            metrics["failures"] += 1
            run.metrics = metrics
            session.commit()
            return False

    def _run_saved_instagram_profiles(
        self,
        session: Session,
        run: CampaignRun,
        campaign: Campaign,
        provider: MetaInstagramProvider,
    ) -> bool:
        identities = list(
            session.scalars(
                select(LeadSocialIdentity)
                .join(LeadCampaign, LeadCampaign.lead_id == LeadSocialIdentity.lead_id)
                .where(
                    LeadCampaign.campaign_id == campaign.id,
                    LeadSocialIdentity.platform == "instagram",
                )
                .order_by(LeadSocialIdentity.normalized_handle)
            )
        )
        attempt = ProviderAttempt(
            run_id=run.id,
            provider="instagram",
            status="running",
            query=f"Saved Instagram profiles for {campaign.name}",
        )
        self.repository.add_attempt(session, attempt)
        run.provider_status = "running"
        session.commit()
        if not identities:
            attempt.status = "completed"
            attempt.completed_at = datetime.now(UTC)
            run.query_summary = "No saved Instagram profiles"
            run.warnings = [
                *run.warnings,
                "No Instagram profiles are stored for this campaign. Find a profile in Social "
                "Leads, then paste its URL into Instagram import.",
            ]
            session.commit()
            return True

        profiles: list[InstagramProfessionalProfile] = []
        failures: list[str] = []
        for identity in identities:
            try:
                profiles.append(provider.lookup_profile(identity.profile_url))
            except ProviderFailure as exc:
                failures.append(f"@{identity.normalized_handle}: {exc.safe_message}")
        attempt.request_count = len(identities)
        attempt.response_count = len(profiles)
        attempt.completed_at = datetime.now(UTC)
        attempt.status = "completed" if profiles else "failed"
        if failures and not profiles:
            attempt.error_code = "META_INSTAGRAM_PROFILE_UNAVAILABLE"
            attempt.error_message = "Meta could not expose any saved Instagram profile."
        query_summary = "; ".join(f"@{profile.username}" for profile in profiles)
        run.query_summary = query_summary or f"Checked {len(identities)} saved profiles"
        metrics = dict(DEFAULT_METRICS) | run.metrics
        metrics["failures"] += len(failures)
        run.metrics = metrics
        if profiles:
            batch = DiscoveryBatch(
                businesses=[provider.profile_business(profile, campaign) for profile in profiles],
                queries=[f"@{profile.username}" for profile in profiles],
                request_count=len(identities),
                warnings=[
                    *failures,
                    "Instagram does not verify campaign radius for saved profiles; the selected "
                    "campaign location remains review context.",
                ],
            )
            self._store_discovery_batch(session, run, campaign, "instagram", batch)
        else:
            run.warnings = [*run.warnings, *failures]
        session.commit()
        return bool(profiles) or not failures

    def _discover(self, session: Session, run: CampaignRun, campaign: Campaign) -> None:
        requested_provider = next(
            (
                provider
                for provider in CampaignRunProvider
                if run.trigger.endswith(f"_{provider.value}")
            ),
            None,
        )
        if requested_provider is CampaignRunProvider.SCORING:
            run.provider_status = "not_requested"
            session.commit()
            return
        wants_google = (
            requested_provider in {None, CampaignRunProvider.GOOGLE_PLACES}
            and "google_places" in campaign.discovery_sources
        )
        wants_instagram = (
            requested_provider in {None, CampaignRunProvider.INSTAGRAM}
            and "instagram" in campaign.discovery_sources
        )
        wants_public_registries = (
            requested_provider in {None, CampaignRunProvider.PUBLIC_REGISTRIES}
            and "public_registries" in campaign.discovery_sources
        )
        if not wants_google and not wants_instagram and not wants_public_registries:
            run.provider_status = "not_requested"
            run.warnings = [
                *run.warnings,
                "This campaign uses existing leads only; no external discovery source is selected.",
            ]
            session.commit()
            return

        outcomes: list[bool] = []
        unavailable = 0
        if wants_google:
            if self.settings.google_places_enabled:
                outcomes.append(
                    self._run_discovery_provider(
                        session, run, campaign, "google_places", self.provider
                    )
                )
            else:
                unavailable += 1
                run.warnings = [
                    *run.warnings,
                    "Google Places is selected but no API key is configured; existing leads "
                    "were still refreshed.",
                ]
        if wants_instagram:
            if self.instagram_provider is not None and self.instagram_provider.connected:
                outcomes.append(
                    self._run_saved_instagram_profiles(
                        session, run, campaign, self.instagram_provider
                    )
                )
            else:
                unavailable += 1
                run.warnings = [
                    *run.warnings,
                    "Instagram is selected but no Meta professional account is connected; "
                    "existing leads were still refreshed.",
                ]
        if wants_public_registries:
            if self.instagram_provider is not None and self.instagram_provider.connected:
                registry_provider = PublicRegistryProvider(
                    self.settings, self.instagram_provider, self.enricher
                )
                outcomes.append(
                    self._run_discovery_provider(
                        session, run, campaign, "public_registries", registry_provider
                    )
                )
            else:
                unavailable += 1
                run.warnings = [
                    *run.warnings,
                    "Public registries is selected but no Meta professional account is "
                    "connected; existing leads were still refreshed.",
                ]

        if outcomes and all(outcomes) and unavailable == 0:
            run.provider_status = "completed"
        elif outcomes and any(outcomes):
            run.provider_status = "partial"
        elif outcomes:
            run.provider_status = "failed"
        else:
            run.provider_status = "not_configured"
        session.commit()

    def _refresh_qualification(
        self,
        session: Session,
        run: CampaignRun,
        campaign: Campaign,
        correlation_id: str,
    ) -> None:
        qualification = self.qualification.refresh_campaign_scores(
            session, campaign, run.id, correlation_id
        )
        metrics = dict(DEFAULT_METRICS) | run.metrics
        metrics.update(
            {
                "leads_scored": qualification.scored,
                "scores_unchanged": qualification.unchanged,
                "qualified": qualification.qualified,
                "skipped": qualification.skipped,
            }
        )
        prepared = self.qualification.prepare_shortlist_from_scores(
            session, campaign, qualification.score_runs, correlation_id
        )
        metrics["shortlist_selected"] = len(prepared.shortlist.items)
        metrics["shortlist_created"] = int(prepared.created)
        run.metrics = metrics

    def _active_campaign_for_social(self, session: Session, campaign_id: str) -> Campaign:
        campaign = self.campaign_repository.get(session, campaign_id)
        if campaign is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)
        if campaign.status != "active":
            raise DomainError(
                "CAMPAIGN_NOT_ACTIVE",
                "Only active campaigns can import or enrich Instagram profiles.",
                status_code=409,
            )
        active = session.scalar(
            select(CampaignRun).where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status.in_(("queued", "running")),
            )
        )
        if active is not None:
            raise DomainError(
                "CAMPAIGN_RUN_ACTIVE",
                "Wait for the active campaign run to finish before importing Instagram profiles.",
                status_code=409,
                details={"campaign_run_id": active.id},
            )
        return campaign

    def _ready_instagram_provider(self) -> MetaInstagramProvider:
        if self.instagram_provider is None or not self.instagram_provider.connected:
            raise DomainError(
                "META_INSTAGRAM_NOT_CONNECTED",
                "Connect an Instagram professional account in Settings before looking up profiles.",
                status_code=409,
            )
        return self.instagram_provider

    @staticmethod
    def _profile_read(profile: InstagramProfessionalProfile) -> InstagramProfileRead:
        return InstagramProfileRead(
            account_id=profile.account_id,
            username=profile.username,
            profile_url=profile.profile_url,
            business_name=profile.business_name,
            biography=profile.biography,
            website=profile.website,
            public_email=profile.public_email,
            public_phone=profile.public_phone,
            followers_count=profile.followers_count,
            media_count=profile.media_count,
        )

    @staticmethod
    def _instagram_domain_error(exc: ProviderFailure) -> DomainError:
        status_code = 409 if exc.code == "META_INSTAGRAM_NOT_CONNECTED" else 422
        return DomainError(exc.code, exc.safe_message, status_code=status_code)

    def preview_instagram_profile(self, profile_url: str) -> InstagramProfileRead:
        provider = self._ready_instagram_provider()
        try:
            return self._profile_read(provider.lookup_profile(profile_url))
        except ProviderFailure as exc:
            raise self._instagram_domain_error(exc) from exc

    def _complete_instagram_profile_run(
        self,
        session: Session,
        *,
        campaign: Campaign,
        trigger: str,
        query_summary: str,
        profiles: list[InstagramProfessionalProfile],
        failures: list[str],
        request_count: int,
        correlation_id: str,
    ) -> CampaignRunRead:
        started_at = datetime.now(UTC)
        run = CampaignRun(
            campaign_id=campaign.id,
            trigger=trigger,
            status=CampaignRunStatus.RUNNING.value,
            phase="instagram_profile_enrichment",
            provider_status="running",
            query_summary=query_summary,
            metrics=dict(DEFAULT_METRICS),
            started_at=started_at,
        )
        session.add(run)
        session.flush()
        attempt = ProviderAttempt(
            run_id=run.id,
            provider="instagram",
            status="completed" if profiles else "failed",
            query=query_summary,
            request_count=request_count,
            response_count=len(profiles),
            error_code="META_INSTAGRAM_PROFILE_UNAVAILABLE" if failures and not profiles else None,
            error_message=(
                "No saved profile could be exposed by Meta." if failures and not profiles else None
            ),
            completed_at=datetime.now(UTC),
        )
        self.repository.add_attempt(session, attempt)
        warnings = list(failures)
        if profiles:
            warnings.append(
                "Instagram does not verify campaign radius for profile imports; the selected "
                "campaign location is retained as review context."
            )
            batch = DiscoveryBatch(
                businesses=[
                    self._ready_instagram_provider().profile_business(profile, campaign)
                    for profile in profiles
                ],
                queries=[f"@{profile.username}" for profile in profiles],
                request_count=request_count,
                warnings=warnings,
            )
            self._store_discovery_batch(session, run, campaign, "instagram", batch)
        else:
            run.warnings = warnings or [
                "No Instagram profiles are stored for this campaign yet. Paste a profile URL "
                "to import the first one."
            ]
        metrics = dict(DEFAULT_METRICS) | run.metrics
        metrics["failures"] += len(failures)
        run.metrics = metrics
        if any(candidate.matched_lead_id for candidate in run.candidates):
            run.phase = "qualification"
            session.flush()
            self._refresh_qualification(session, run, campaign, correlation_id)
        elif any(
            candidate.status == CandidateStatus.REVIEW_REQUIRED.value
            for candidate in run.candidates
        ):
            run.warnings = [
                *run.warnings,
                "A possible duplicate needs your decision before this profile is scored.",
            ]
        run.provider_status = (
            "completed" if profiles and not failures else "partial" if profiles else "not_available"
        )
        run.phase = "completed"
        run.status = (
            CampaignRunStatus.COMPLETED_WITH_WARNINGS.value
            if run.warnings
            else CampaignRunStatus.COMPLETED.value
        )
        run.completed_at = datetime.now(UTC)
        record_audit_event(
            session,
            action=f"instagram_profile.{trigger}",
            entity_type="campaign_run",
            entity_id=run.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": campaign.id,
                "profiles_requested": request_count,
                "profiles_resolved": len(profiles),
                "profiles_unavailable": len(failures),
                "metrics": run.metrics,
            },
        )
        session.commit()
        return self.get_run(session, run.id)

    def import_instagram_profile(
        self,
        session: Session,
        campaign_id: str,
        profile_url: str,
        correlation_id: str,
    ) -> CampaignRunRead:
        campaign = self._active_campaign_for_social(session, campaign_id)
        provider = self._ready_instagram_provider()
        try:
            profile = provider.lookup_profile(profile_url)
        except ProviderFailure as exc:
            raise self._instagram_domain_error(exc) from exc
        return self._complete_instagram_profile_run(
            session,
            campaign=campaign,
            trigger="instagram_profile_import",
            query_summary=f"Imported Instagram profile @{profile.username}",
            profiles=[profile],
            failures=[],
            request_count=1,
            correlation_id=correlation_id,
        )

    def enrich_known_instagram_profiles(
        self,
        session: Session,
        campaign_id: str,
        correlation_id: str,
    ) -> CampaignRunRead:
        campaign = self._active_campaign_for_social(session, campaign_id)
        provider = self._ready_instagram_provider()
        identities = list(
            session.scalars(
                select(LeadSocialIdentity)
                .join(LeadCampaign, LeadCampaign.lead_id == LeadSocialIdentity.lead_id)
                .where(
                    LeadCampaign.campaign_id == campaign.id,
                    LeadSocialIdentity.platform == "instagram",
                )
                .order_by(LeadSocialIdentity.normalized_handle)
            )
        )
        profiles: list[InstagramProfessionalProfile] = []
        failures: list[str] = []
        for identity in identities:
            try:
                profiles.append(provider.lookup_profile(identity.profile_url))
            except ProviderFailure as exc:
                failures.append(f"@{identity.normalized_handle}: {exc.safe_message}")
        return self._complete_instagram_profile_run(
            session,
            campaign=campaign,
            trigger="instagram_saved_enrich",
            query_summary=f"Enriched {len(identities)} saved Instagram profiles",
            profiles=profiles,
            failures=failures,
            request_count=len(identities),
            correlation_id=correlation_id,
        )

    def capture_social_candidate(
        self,
        session: Session,
        data: SocialCandidateCapture,
        correlation_id: str,
    ) -> CampaignRunRead:
        campaign = self.campaign_repository.get(session, data.campaign_id)
        if campaign is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)
        if campaign.status != "active":
            raise DomainError(
                "CAMPAIGN_NOT_ACTIVE", "Only active campaigns can capture leads.", status_code=409
            )
        platform, handle, profile_url = social_identity(str(data.profile_url), data.platform.value)
        started_at = datetime.now(UTC)
        run = CampaignRun(
            campaign_id=campaign.id,
            trigger="assisted_social_capture",
            status=CampaignRunStatus.RUNNING.value,
            phase="social_capture",
            provider_status="assisted",
            query_summary=f"Operator captured {platform} profile @{handle}",
            metrics=dict(DEFAULT_METRICS),
            started_at=started_at,
        )
        session.add(run)
        session.flush()
        candidate = DiscoveryCandidate(
            run_id=run.id,
            campaign_id=campaign.id,
            provider=f"assisted_{platform}",
            provider_record_id=handle,
            business_name=data.business_name,
            normalized_name=normalize_business_name(data.business_name)[:300],
            location=data.location,
            website=str(data.website) if data.website else None,
            phone=data.phone_number,
            source_url=profile_url,
            place_types=[platform],
            evidence={
                "social_profile": {
                    "platform": platform,
                    "profile_url": profile_url,
                    "handle": handle,
                    "public_email": data.public_email.casefold() if data.public_email else None,
                    "public_bio": data.public_bio,
                    "capture_method": "operator_assisted",
                }
            },
        )
        session.add(candidate)
        session.flush()
        metrics = dict(DEFAULT_METRICS)
        metrics["discovered"] = 1
        exclusion = self._excluded(candidate, campaign)
        if exclusion:
            candidate.status = CandidateStatus.REJECTED.value
            candidate.rejection_reason = exclusion
        else:
            if candidate.website:
                try:
                    evidence = self.enricher.enrich(candidate.website)
                    candidate.evidence = {
                        **candidate.evidence,
                        "website": {
                            "final_url": evidence.final_url,
                            "title": evidence.title,
                            "description": evidence.description,
                            "public_emails": evidence.public_emails,
                            "public_phones": evidence.public_phones,
                            "social_links": evidence.social_links,
                            "contact_links": evidence.contact_links,
                            "pages_checked": evidence.pages_checked,
                        },
                    }
                    metrics["enriched"] = 1
                except EnrichmentFailure as exc:
                    candidate.evidence = {
                        **candidate.evidence,
                        "website_enrichment": {
                            "status": "skipped",
                            "code": exc.code,
                            "message": exc.safe_message,
                        },
                    }
                    metrics["enrichment_failed"] = 1
                    run.warnings = [*run.warnings, exc.safe_message]
            self._promote_candidate(session, candidate)
        if candidate.status in metrics:
            metrics[candidate.status] += 1
        run.metrics = metrics
        if candidate.matched_lead_id:
            run.phase = "qualification"
            session.flush()
            self._refresh_qualification(session, run, campaign, correlation_id)
        elif candidate.status == CandidateStatus.REVIEW_REQUIRED.value:
            run.warnings = [
                *run.warnings,
                "A possible duplicate needs your decision before this lead is scored.",
            ]
        run.phase = "completed"
        run.status = (
            CampaignRunStatus.COMPLETED_WITH_WARNINGS.value
            if run.warnings
            else CampaignRunStatus.COMPLETED.value
        )
        run.completed_at = datetime.now(UTC)
        record_audit_event(
            session,
            action="social_candidate.captured",
            entity_type="discovery_candidate",
            entity_id=candidate.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": campaign.id,
                "platform": platform,
                "status": candidate.status,
                "matched_lead_id": candidate.matched_lead_id,
            },
        )
        session.commit()
        return self.get_run(session, run.id)

    def execute(self, session: Session, run_id: str, correlation_id: str) -> None:
        run = self.repository.get_run(session, run_id)
        if run is None:
            return
        if run.status in {
            CampaignRunStatus.COMPLETED.value,
            CampaignRunStatus.COMPLETED_WITH_WARNINGS.value,
            CampaignRunStatus.CANCELLED.value,
        }:
            return
        run.status = CampaignRunStatus.RUNNING.value
        run.phase = "discovery"
        run.started_at = run.started_at or datetime.now(UTC)
        run.error_code = None
        run.error_message = None
        session.commit()
        try:
            campaign = self.campaign_repository.get(session, run.campaign_id)
            if campaign is None or campaign.status != "active":
                raise DomainError(
                    "CAMPAIGN_NOT_ACTIVE",
                    "The campaign is no longer active.",
                    status_code=409,
                )
            self._cancel_if_requested(session, run)
            self._discover(session, run, campaign)
            self._cancel_if_requested(session, run)
            run.phase = "qualification"
            session.commit()
            qualification = self.qualification.refresh_campaign_scores(
                session,
                campaign,
                run.id,
                correlation_id,
            )
            metrics = dict(DEFAULT_METRICS) | run.metrics
            metrics.update(
                {
                    "leads_scored": qualification.scored,
                    "scores_unchanged": qualification.unchanged,
                    "qualified": qualification.qualified,
                    "skipped": qualification.skipped,
                }
            )
            run.metrics = metrics
            run.phase = "shortlist"
            session.commit()
            self._cancel_if_requested(session, run)
            prepared = self.qualification.prepare_shortlist_from_scores(
                session,
                campaign,
                qualification.score_runs,
                correlation_id,
            )
            metrics = dict(DEFAULT_METRICS) | run.metrics
            metrics["shortlist_selected"] = len(prepared.shortlist.items)
            metrics["shortlist_created"] = int(prepared.created)
            run.metrics = metrics
            run.phase = "completed"
            run.status = (
                CampaignRunStatus.COMPLETED_WITH_WARNINGS.value
                if run.warnings
                else CampaignRunStatus.COMPLETED.value
            )
            run.completed_at = datetime.now(UTC)
            record_audit_event(
                session,
                action="campaign_run.completed",
                entity_type="campaign_run",
                entity_id=run.id,
                correlation_id=correlation_id,
                summary={
                    "campaign_id": run.campaign_id,
                    "status": run.status,
                    "metrics": run.metrics,
                },
            )
            session.commit()
        except InterruptedError:
            return
        except DomainError as exc:
            run.status = CampaignRunStatus.FAILED.value
            run.phase = "failed"
            run.error_code = exc.code
            run.error_message = exc.message
            run.completed_at = datetime.now(UTC)
            session.commit()
        except Exception:
            logger.exception("Campaign run failed", extra={"campaign_run_id": run_id})
            session.rollback()
            stored = self.repository.get_run(session, run_id)
            if stored is not None:
                stored.status = CampaignRunStatus.FAILED.value
                stored.phase = "failed"
                stored.error_code = "CAMPAIGN_RUN_FAILED"
                stored.error_message = "The campaign run failed safely; existing data was retained."
                stored.completed_at = datetime.now(UTC)
                session.commit()

    def decide_candidate(
        self,
        session: Session,
        candidate_id: str,
        data: CandidateDecision,
        correlation_id: str,
    ) -> DiscoveryCandidateRead:
        candidate = self.repository.get_candidate(session, candidate_id)
        if candidate is None:
            raise DomainError(
                "DISCOVERY_CANDIDATE_NOT_FOUND", "Discovery candidate not found.", status_code=404
            )
        if candidate.status not in {"review_required", "discovered"}:
            raise DomainError(
                "DISCOVERY_CANDIDATE_DECIDED",
                "This discovery candidate already has a final decision.",
                status_code=409,
            )
        previous_status = candidate.status
        if data.action is CandidateDecisionAction.REJECT:
            candidate.status = CandidateStatus.REJECTED.value
            candidate.rejection_reason = data.reason or "Rejected during duplicate review."
        elif data.action is CandidateDecisionAction.LINK:
            if data.lead_id is None:
                raise DomainError(
                    "LEAD_ID_REQUIRED",
                    "A lead ID is required when linking a candidate.",
                    status_code=422,
                )
            lead = self.lead_repository.get(session, data.lead_id)
            if lead is None:
                raise DomainError("LEAD_NOT_FOUND", "Lead not found.", status_code=404)
            self._link_existing(session, candidate, lead)
        else:
            candidate.matched_lead_id = None
            candidate.duplicate_confidence = None
            self._promote_candidate(session, candidate, force=True)
        metrics = dict(DEFAULT_METRICS) | candidate.run.metrics
        if previous_status in metrics:
            metrics[previous_status] = max(0, metrics[previous_status] - 1)
        if candidate.status in metrics:
            metrics[candidate.status] += 1
        candidate.run.metrics = metrics
        if candidate.matched_lead_id and data.action is not CandidateDecisionAction.REJECT:
            campaign = self.campaign_repository.get(session, candidate.campaign_id)
            if campaign is not None:
                self._refresh_qualification(session, candidate.run, campaign, correlation_id)
        record_audit_event(
            session,
            action=f"discovery_candidate.{data.action.value}",
            entity_type="discovery_candidate",
            entity_id=candidate.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": candidate.campaign_id,
                "matched_lead_id": candidate.matched_lead_id,
                "reason": data.reason,
            },
        )
        session.commit()
        session.refresh(candidate)
        return DiscoveryCandidateRead.model_validate(candidate)
