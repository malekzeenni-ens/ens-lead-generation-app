"""Instagram profile preview, import and refresh, and assisted social capture.

Part of the CampaignAutomationService chain (R9); methods moved unchanged.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import (
    Campaign,
    CampaignRun,
    DiscoveryCandidate,
    LeadCampaign,
    LeadSocialIdentity,
    ProviderAttempt,
)
from app.domains.audit.service import record_audit_event
from app.domains.automation.candidate_data import (
    DEFAULT_METRICS,
)
from app.domains.automation.discovery import AutomationDiscovery
from app.domains.automation.enrichment import EnrichmentFailure
from app.domains.automation.providers import (
    DiscoveryBatch,
    InstagramProfessionalProfile,
    MetaInstagramProvider,
    ProviderFailure,
)
from app.domains.automation.schemas import (
    CampaignRunRead,
    CampaignRunStatus,
    CandidateStatus,
    InstagramProfileRead,
    SocialCandidateCapture,
)
from app.domains.leads.identity import (
    normalize_business_name,
    social_identity,
)

logger = logging.getLogger(__name__)


class AutomationSocial(AutomationDiscovery):
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
