"""Running discovery providers and staging their results as candidates.

Part of the CampaignAutomationService chain (R9); methods moved unchanged.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Campaign,
    CampaignRun,
    DiscoveryCandidate,
    LeadCampaign,
    LeadSocialIdentity,
    ProviderAttempt,
)
from app.domains.automation.candidate_data import (
    DEFAULT_METRICS,
)
from app.domains.automation.enrichment import EnrichmentFailure
from app.domains.automation.promotion import AutomationPromotion
from app.domains.automation.providers import (
    DiscoveryBatch,
    DiscoveryProvider,
    InstagramProfessionalProfile,
    MetaInstagramProvider,
    ProviderFailure,
    PublicRegistryProvider,
)
from app.domains.automation.schemas import (
    CampaignRunProvider,
    CandidateStatus,
)
from app.domains.leads.identity import (
    normalize_business_name,
)

logger = logging.getLogger(__name__)


class AutomationDiscovery(AutomationPromotion):
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
