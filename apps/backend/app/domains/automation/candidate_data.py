"""Run metrics and the evidence a discovery candidate carries (R9 split)."""

from __future__ import annotations

from contextlib import suppress

from app.db.models import (
    CampaignRun,
    DiscoveryCandidate,
    Lead,
)
from app.domains.automation.schemas import (
    CampaignRunRead,
    DiscoveryCandidateRead,
    ProviderAttemptRead,
)
from app.domains.leads.identity import (
    social_identity,
)
from app.domains.leads.matching import MatchKeys, match_keys

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
    "drafts_created": 0,
    "attention_required": 0,
    "missing_context": 0,
    "cross_campaign_duplicates": 0,
    "weekly_limit_skipped": 0,
    "outreach_skipped": 0,
    "failures": 0,
}


def _run_to_read(run: CampaignRun) -> CampaignRunRead:
    return CampaignRunRead(
        id=run.id,
        batch_id=run.batch_id,
        campaign_id=run.campaign_id,
        campaign_name=run.campaign.name,
        trigger=run.trigger,
        week_start=run.week_start,
        outreach_batch_id=run.outreach_batch_id,
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


def _lead_match_keys(lead: Lead) -> MatchKeys:
    return match_keys(
        business_name=lead.business_name,
        location=lead.location,
        website=lead.website,
        phone=lead.phone_number,
        emails=[lead.public_email, lead.contact_email],
        social=[
            (identity.platform, identity.normalized_handle) for identity in lead.social_identities
        ],
    )


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
