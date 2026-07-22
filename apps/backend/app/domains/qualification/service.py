from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import (
    Campaign,
    Lead,
    LeadStageEvent,
    Product,
    ScoreRun,
    ScoringProfile,
    Shortlist,
    ShortlistItem,
)
from app.domains.audit.service import record_audit_event
from app.domains.campaigns.repository import CampaignRepository
from app.domains.catalogue.repository import CatalogueRepository
from app.domains.leads.repository import LeadRepository
from app.domains.qualification.repository import QualificationRepository
from app.domains.qualification.schemas import (
    CategoryBreakdown,
    ProductMatch,
    ScoreOverride,
    ScoreRunRead,
    ScoringProfileRead,
    ScoringProfileUpdate,
    ScoringWeights,
    ShortlistAction,
    ShortlistDecision,
    ShortlistGenerate,
    ShortlistItemRead,
    ShortlistRead,
)

RULE_VERSION = "deterministic-local-v4"
EXCLUDED_STAGES = {"won", "lost", "not_suitable", "do_not_contact"}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _normalise(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _profile_to_read(profile: ScoringProfile) -> ScoringProfileRead:
    return ScoringProfileRead(
        id=profile.id,
        name=profile.name,
        segment=profile.segment,
        version=profile.version,
        weights=ScoringWeights.model_validate(profile.weights),
        active=profile.active,
        created_at=profile.created_at,
    )


def _score_to_read(run: ScoreRun) -> ScoreRunRead:
    return ScoreRunRead(
        id=run.id,
        lead_id=run.lead_id,
        campaign_id=run.campaign_id,
        profile_id=run.profile_id,
        profile_name=run.profile.name,
        profile_version=run.profile.version,
        rule_version=run.rule_version,
        campaign_run_id=run.campaign_run_id,
        input_fingerprint=run.input_fingerprint,
        calculated_score=run.calculated_score,
        final_score=run.final_score,
        manual_override=run.manual_override,
        override_reason=run.override_reason,
        breakdown=[CategoryBreakdown.model_validate(item) for item in run.breakdown],
        product_matches=[ProductMatch.model_validate(item) for item in run.product_matches],
        created_at=run.created_at,
        overridden_at=run.overridden_at,
    )


@dataclass(frozen=True)
class CampaignQualificationResult:
    score_runs: dict[str, ScoreRun]
    scored: int
    unchanged: int
    qualified: int
    skipped: int


@dataclass(frozen=True)
class ShortlistPreparationResult:
    shortlist: ShortlistRead
    created: bool


class QualificationService:
    def __init__(
        self,
        repository: QualificationRepository | None = None,
        lead_repository: LeadRepository | None = None,
        campaign_repository: CampaignRepository | None = None,
        catalogue_repository: CatalogueRepository | None = None,
    ) -> None:
        self.repository = repository or QualificationRepository()
        self.lead_repository = lead_repository or LeadRepository()
        self.campaign_repository = campaign_repository or CampaignRepository()
        self.catalogue_repository = catalogue_repository or CatalogueRepository()

    def _profile(
        self,
        session: Session,
        segment: str,
        cache: dict[str, ScoringProfile] | None = None,
    ) -> ScoringProfile:
        if cache is not None and segment in cache:
            return cache[segment]
        profile = self.repository.active_profile(session, segment)
        if profile is None:
            profile = ScoringProfile(
                name=f"{segment} deterministic model",
                segment=segment,
                version=1,
                weights=ScoringWeights().model_dump(),
                active=True,
            )
            session.add(profile)
            session.flush()
        if cache is not None:
            cache[segment] = profile
        return profile

    def get_profile(self, session: Session, segment: str) -> ScoringProfileRead:
        profile = self._profile(session, segment)
        session.commit()
        return _profile_to_read(profile)

    def profile_history(self, session: Session, segment: str) -> list[ScoringProfileRead]:
        profiles = self.repository.profile_versions(session, segment)
        if not profiles:
            return [self.get_profile(session, segment)]
        return [_profile_to_read(profile) for profile in profiles]

    def update_profile(
        self,
        session: Session,
        segment: str,
        data: ScoringProfileUpdate,
        correlation_id: str,
    ) -> ScoringProfileRead:
        current = self._profile(session, segment)
        current.active = False
        profile = ScoringProfile(
            name=data.name,
            segment=segment,
            version=current.version + 1,
            weights=data.weights.model_dump(),
            active=True,
        )
        session.add(profile)
        session.flush()
        record_audit_event(
            session,
            action="scoring.profile_version_created",
            entity_type="scoring_profile",
            entity_id=profile.id,
            correlation_id=correlation_id,
            summary={"segment": segment, "version": profile.version},
        )
        session.commit()
        return _profile_to_read(profile)

    def _family_product_matches(
        self, session: Session, campaign: Campaign
    ) -> list[ProductMatch] | None:
        """Curated matches from the campaign's assigned product family, if any.

        Returns None (not an empty list) when the campaign has no family, so the
        caller can fall back to the automatic segment/category heuristic instead
        of treating "no family" the same as "family with zero products".
        """
        if campaign.product_family_id is None:
            return None
        family = self.catalogue_repository.get_family(session, campaign.product_family_id)
        if family is None:
            return None
        products = self.catalogue_repository.by_ids(session, family.product_ids)
        matches = [
            ProductMatch(
                product_id=product.id,
                product_name=product.name,
                category=product.category,
                match_score=100,
                reason=(
                    f'Curated for this campaign\'s "{family.name}" product family '
                    "— included by the operator, not automatically matched."
                ),
                evidence=[f"campaign.product_family:{family.name}"],
            )
            for product in products
            if product.active
        ]
        return matches[:5]

    def _product_matches(
        self,
        session: Session,
        lead: Lead,
        campaign: Campaign,
        products: list[Product] | None = None,
    ) -> list[ProductMatch]:
        family_matches = self._family_product_matches(session, campaign)
        if family_matches is not None:
            return family_matches

        segment = _normalise(lead.segment)
        campaign_categories = {_normalise(value) for value in campaign.product_categories}
        catalogue = products if products is not None else self.repository.active_products(session)
        matches: list[ProductMatch] = []
        for product in catalogue:
            evidence: list[str] = []
            reasons: list[str] = []
            match_score = 0
            target_segments = {_normalise(value) for value in product.target_segments}
            if target_segments:
                if segment in target_segments:
                    match_score += 60
                    evidence.append(f"lead.segment:{lead.segment}")
                    reasons.append("target segment matches the lead")
            else:
                # No target-segment tags were imported for this product (e.g. the
                # Shopify catalogue was never tagged `segment:...`). Treat that as
                # unconfirmed rather than a hard non-match, so untagged products
                # aren't scored identically to ones explicitly tagged for a
                # different segment.
                match_score += 20
                evidence.append("catalogue.target_segments:not tagged")
                reasons.append(
                    "not yet confirmed for this segment — assign a product family to this "
                    "campaign in Catalogue → Product families for a precise, curated match"
                )
            if _normalise(product.category) in campaign_categories:
                match_score += 40
                evidence.append(f"campaign.product_category:{product.category}")
                reasons.append("category is enabled for the campaign")
            if match_score == 0:
                continue
            matches.append(
                ProductMatch(
                    product_id=product.id,
                    product_name=product.name,
                    category=product.category,
                    match_score=match_score,
                    reason="; ".join(reasons).capitalize() + ".",
                    evidence=evidence,
                )
            )
        return sorted(matches, key=lambda item: (-item.match_score, item.product_name.casefold()))[
            :5
        ]

    @staticmethod
    def _category(
        name: str,
        weight: int,
        checks: list[tuple[bool, int, str, str]],
    ) -> CategoryBreakdown:
        available = sum(units for _, units, _, _ in checks)
        earned = sum(units for passed, units, _, _ in checks if passed)
        return CategoryBreakdown(
            category=name,
            points_awarded=round(weight * earned / available) if available else 0,
            points_available=weight,
            evidence_used=[evidence for passed, _, evidence, _ in checks if passed],
            missing_evidence=[missing for passed, _, _, missing in checks if not passed],
        )

    def _calculate_model(
        self,
        session: Session,
        lead: Lead,
        campaign: Campaign,
        correlation_id: str,
        *,
        campaign_run_id: str | None = None,
        input_fingerprint: str | None = None,
        products: list[Product] | None = None,
        profile_cache: dict[str, ScoringProfile] | None = None,
    ) -> ScoreRun:
        if not any(link.campaign_id == campaign.id for link in lead.campaigns):
            raise DomainError(
                "LEAD_CAMPAIGN_MISMATCH",
                "The lead does not belong to the selected campaign.",
                status_code=409,
            )
        profile = self._profile(session, lead.segment, profile_cache)
        weights = ScoringWeights.model_validate(profile.weights)
        matched_products = self._product_matches(session, lead, campaign, products)
        now = datetime.now(UTC)
        text = " ".join(
            [
                lead.business_name,
                lead.segment,
                *(note.content for note in lead.notes),
                *(observation.observed_value for observation in lead.observations),
            ]
        ).casefold()
        has_recent_observation = any(
            (now - _aware(observation.collected_at)).days <= 90 for observation in lead.observations
        )
        local_token = campaign.primary_location.split(",", 1)[0].strip().casefold()
        value_present = any(
            value is not None
            for value in (lead.estimated_order_value, lead.quote_value, lead.won_value)
        )
        contact_route_count = sum(
            bool(route)
            for route in (lead.website, lead.social_profile, lead.public_email, lead.phone_number)
        )
        local_area = local_token or "the campaign area"
        category_values = {
            "business_relevance": self._category(
                "Business relevance",
                weights.business_relevance,
                [
                    (
                        "baker" in lead.segment.casefold(),
                        2,
                        f'Segment "{lead.segment}" confirms this is a bakery',
                        "Lead segment does not confirm a bakery business",
                    ),
                    (
                        "cake" in text,
                        1,
                        "Notes or evidence mention celebration cakes",
                        "No mention of celebration cakes in notes or evidence yet",
                    ),
                    (
                        bool(
                            lead.website
                            or lead.social_profile
                            or lead.phone_number
                            or lead.public_email
                        ),
                        1,
                        "Lead has a public contact route (website, social, phone or email)",
                        "No public contact route on file yet",
                    ),
                ],
            ),
            "activity": self._category(
                "Activity",
                weights.activity,
                [
                    (
                        has_recent_observation,
                        1,
                        "New public evidence recorded in the last 90 days",
                        "No public evidence recorded in the last 90 days",
                    ),
                    (
                        (now - _aware(lead.updated_at)).days <= 30,
                        1,
                        "Lead record updated in the last 30 days",
                        "Lead record has not been updated in the last 30 days",
                    ),
                ],
            ),
            "product_fit": self._category(
                "Product fit",
                weights.product_fit,
                [
                    (
                        bool(matched_products),
                        3,
                        f"Matches {len(matched_products)} active catalogue product"
                        f"{'s' if len(matched_products) != 1 else ''}",
                        "No active catalogue product matches this lead yet",
                    ),
                    (
                        bool(campaign.product_categories) or campaign.product_family_id is not None,
                        1,
                        "Campaign has product categories or a product family configured",
                        "Campaign has no product categories or product family configured",
                    ),
                ],
            ),
            "local_relevance": self._category(
                "Local relevance",
                weights.local_relevance,
                [
                    (
                        bool(local_token and local_token in lead.location.casefold()),
                        2,
                        f"Lead location matches {local_area} ({lead.location})",
                        f"Lead location does not mention {local_area} "
                        f"({lead.location or 'not on file'})",
                    ),
                    (
                        bool(lead.location),
                        1,
                        f"Lead location on file ({lead.location})",
                        "Lead has no location on file",
                    ),
                    (
                        True,
                        1,
                        "Lead is linked to this campaign",
                        "Lead is not linked to this campaign",
                    ),
                ],
            ),
            "commercial_potential": self._category(
                "Commercial potential",
                weights.commercial_potential,
                [
                    (
                        value_present,
                        1,
                        "Estimated order, quote or won value recorded",
                        "No estimated order, quote or won value recorded yet",
                    ),
                    (
                        bool(lead.potential_recurrence),
                        1,
                        "Marked as a potential repeat-order customer",
                        "Not yet marked as a potential repeat-order customer",
                    ),
                    (
                        lead.pipeline_stage not in {"new", "researching"},
                        1,
                        "Pipeline stage has moved past initial research "
                        f'(now "{lead.pipeline_stage}")',
                        'Still in the initial "new" or "researching" stage',
                    ),
                ],
            ),
            "reach_credibility": self._category(
                "Reach and credibility",
                weights.reach_credibility,
                [
                    (
                        bool(lead.website),
                        1,
                        "Public website on file",
                        "No public website on file",
                    ),
                    (
                        bool(lead.social_profile),
                        1,
                        "Public social profile on file",
                        "No public social profile on file",
                    ),
                ],
            ),
            "contactability": self._category(
                "Contactability",
                weights.contactability,
                [
                    (
                        bool(lead.website),
                        1,
                        "Website available as a contact route",
                        "No website available as a contact route",
                    ),
                    (
                        bool(lead.social_profile),
                        1,
                        "Social profile available as a message route",
                        "No social profile available as a message route",
                    ),
                    (
                        bool(lead.public_email),
                        1,
                        "Public email address on file",
                        "No public email address on file",
                    ),
                    (
                        bool(lead.phone_number),
                        1,
                        "Public phone number on file",
                        "No public phone number on file",
                    ),
                    (
                        contact_route_count >= 2,
                        1,
                        f"{contact_route_count} independent contact routes on file",
                        f"Only {contact_route_count} contact route"
                        f"{'s' if contact_route_count != 1 else ''} on file (2 or more needed)",
                    ),
                ],
            ),
        }
        breakdown = list(category_values.values())
        calculated = min(100, max(0, sum(item.points_awarded for item in breakdown)))
        run = ScoreRun(
            lead_id=lead.id,
            campaign_id=campaign.id,
            profile_id=profile.id,
            rule_version=RULE_VERSION,
            campaign_run_id=campaign_run_id,
            input_fingerprint=input_fingerprint,
            calculated_score=calculated,
            final_score=calculated,
            breakdown=[item.model_dump(mode="json") for item in breakdown],
            product_matches=[item.model_dump(mode="json") for item in matched_products],
        )
        session.add(run)
        session.flush()
        lead.current_score = calculated
        lead.score_updated_at = now
        record_audit_event(
            session,
            action="lead.score_calculated",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": campaign.id,
                "score": calculated,
                "profile_version": profile.version,
                "rule_version": RULE_VERSION,
            },
        )
        return run

    def _input_fingerprint(
        self,
        session: Session,
        lead: Lead,
        campaign: Campaign,
        profile: ScoringProfile,
        products: list[Product] | None = None,
    ) -> str:
        products = products if products is not None else self.repository.active_products(session)
        family = (
            self.catalogue_repository.get_family(session, campaign.product_family_id)
            if campaign.product_family_id
            else None
        )
        payload = {
            "rule_version": RULE_VERSION,
            "campaign": {
                "id": campaign.id,
                "segment": campaign.segment,
                "primary_location": campaign.primary_location,
                "radius_miles": campaign.radius_miles,
                "keywords": campaign.keywords,
                "exclusion_keywords": campaign.exclusion_keywords,
                "product_categories": campaign.product_categories,
                "minimum_score_threshold": campaign.minimum_score_threshold,
                "updated_at": campaign.updated_at.isoformat(),
                "product_family": (
                    {
                        "id": family.id,
                        "product_ids": family.product_ids,
                        "updated_at": family.updated_at.isoformat(),
                    }
                    if family is not None
                    else None
                ),
            },
            "lead": {
                "id": lead.id,
                "business_name": lead.business_name,
                "segment": lead.segment,
                "location": lead.location,
                "website": lead.website,
                "social_profile": lead.social_profile,
                "phone_number": lead.phone_number,
                "public_email": lead.public_email,
                "contact_classification": lead.contact_classification,
                "pipeline_stage": lead.pipeline_stage,
                "estimated_order_value": lead.estimated_order_value,
                "quote_value": lead.quote_value,
                "won_value": lead.won_value,
                "potential_recurrence": lead.potential_recurrence,
                "notes": [
                    (item.id, item.content, item.created_at.isoformat()) for item in lead.notes
                ],
                "observations": [
                    (
                        item.id,
                        item.field_name,
                        item.observed_value,
                        item.classification,
                        item.collected_at.isoformat(),
                    )
                    for item in lead.observations
                ],
                "follow_ups": [
                    (item.id, item.status, item.due_date.isoformat(), item.updated_at.isoformat())
                    for item in lead.follow_ups
                ],
                "communications": [
                    (item.id, item.sent_status, item.response_status, item.created_at.isoformat())
                    for item in lead.communications
                ],
            },
            "profile": {
                "id": profile.id,
                "version": profile.version,
                "weights": profile.weights,
            },
            "products": [
                (
                    item.id,
                    item.category,
                    item.target_segments,
                    item.example_use_cases,
                    item.active,
                    item.updated_at.isoformat(),
                )
                for item in products
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def refresh_campaign_scores(
        self,
        session: Session,
        campaign: Campaign,
        campaign_run_id: str,
        correlation_id: str,
    ) -> CampaignQualificationResult:
        score_runs: dict[str, ScoreRun] = {}
        scored = 0
        unchanged = 0
        qualified = 0
        skipped = 0
        products = self.repository.active_products(session)
        profile_cache: dict[str, ScoringProfile] = {}
        latest_by_lead: dict[str, ScoreRun] = {}
        for run in self.repository.latest_scores_for_campaign(session, campaign.id):
            latest_by_lead.setdefault(run.lead_id, run)
        for lead in self.lead_repository.list(session, campaign_id=campaign.id):
            if lead.suppressed or lead.pipeline_stage in EXCLUDED_STAGES:
                skipped += 1
                continue
            profile = self._profile(session, lead.segment, profile_cache)
            fingerprint = self._input_fingerprint(session, lead, campaign, profile, products)
            latest = latest_by_lead.get(lead.id)
            if latest is not None and latest.input_fingerprint == fingerprint:
                run = latest
                unchanged += 1
            else:
                run = self._calculate_model(
                    session,
                    lead,
                    campaign,
                    correlation_id,
                    campaign_run_id=campaign_run_id,
                    input_fingerprint=fingerprint,
                    products=products,
                    profile_cache=profile_cache,
                )
                scored += 1
            score_runs[lead.id] = run
            if run.final_score >= campaign.minimum_score_threshold:
                qualified += 1
        session.commit()
        return CampaignQualificationResult(
            score_runs=score_runs,
            scored=scored,
            unchanged=unchanged,
            qualified=qualified,
            skipped=skipped,
        )

    def prepare_shortlist_from_scores(
        self,
        session: Session,
        campaign: Campaign,
        score_runs: dict[str, ScoreRun],
        correlation_id: str,
    ) -> ShortlistPreparationResult:
        week_start = self._monday(None)
        existing = self.repository.shortlist_for_week(session, campaign.id, week_start)
        if existing is not None:
            return ShortlistPreparationResult(
                shortlist=self._shortlist_to_read(session, existing), created=False
            )
        candidates: list[tuple[Lead, ScoreRun, str]] = []
        recommended_lead_ids = self.repository.recently_recommended_lead_ids(
            session, campaign.id, week_start - timedelta(days=28), week_start
        )
        for lead in self.lead_repository.list(session, campaign_id=campaign.id):
            if (
                lead.suppressed
                or lead.pipeline_stage in EXCLUDED_STAGES
                or self._recently_recommended(session, lead, week_start, recommended_lead_ids)
            ):
                continue
            run = score_runs.get(lead.id)
            if run is None or run.final_score < campaign.minimum_score_threshold:
                continue
            product_names = [item["product_name"] for item in run.product_matches[:2]]
            contact = (
                "public contact route"
                if lead.website or lead.social_profile or lead.public_email or lead.phone_number
                else "contact route missing"
            )
            reason = f"Score {run.final_score}/100; {contact}"
            if product_names:
                reason += f"; matched {', '.join(product_names)}"
            reason += f"; pipeline stage {lead.pipeline_stage.replace('_', ' ')}."
            candidates.append((lead, run, reason))
        candidates.sort(
            key=lambda item: (
                -item[1].final_score,
                bool(item[0].communications),
                item[0].business_name.casefold(),
            )
        )
        shortlist = Shortlist(
            campaign_id=campaign.id,
            week_start=week_start,
            capacity=campaign.weekly_shortlist_size,
            status="active",
        )
        session.add(shortlist)
        session.flush()
        for rank, (lead, run, reason) in enumerate(
            candidates[: campaign.weekly_shortlist_size], start=1
        ):
            session.add(
                ShortlistItem(
                    shortlist_id=shortlist.id,
                    lead_id=lead.id,
                    score_run_id=run.id,
                    rank=rank,
                    decision="recommended",
                    reason=reason,
                    product_matches=run.product_matches,
                )
            )
            if lead.pipeline_stage in {"new", "researching", "qualified"}:
                previous = lead.pipeline_stage
                lead.pipeline_stage = "recommended_this_week"
                session.add(
                    LeadStageEvent(
                        lead_id=lead.id,
                        previous_stage=previous,
                        new_stage="recommended_this_week",
                        actor="campaign_run",
                        reason=f"Selected for shortlist beginning {week_start.isoformat()}",
                    )
                )
        record_audit_event(
            session,
            action="shortlist.prepared_by_campaign_run",
            entity_type="shortlist",
            entity_id=shortlist.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": campaign.id,
                "week_start": week_start.isoformat(),
                "selected": min(len(candidates), campaign.weekly_shortlist_size),
            },
        )
        session.commit()
        session.expire_all()
        stored = self.repository.get_shortlist(session, shortlist.id)
        if stored is None:
            raise RuntimeError("Prepared shortlist could not be reloaded")
        return ShortlistPreparationResult(
            shortlist=self._shortlist_to_read(session, stored), created=True
        )

    def calculate(
        self,
        session: Session,
        lead_id: str,
        campaign_id: str,
        correlation_id: str,
    ) -> ScoreRunRead:
        lead = self.lead_repository.get(session, lead_id)
        campaign = self.campaign_repository.get(session, campaign_id)
        if lead is None:
            raise DomainError("LEAD_NOT_FOUND", "Lead not found.", status_code=404)
        if campaign is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)
        self._calculate_model(session, lead, campaign, correlation_id)
        session.commit()
        session.expire_all()
        stored = self.repository.latest_score(session, lead_id)
        if stored is None:
            raise RuntimeError("Score run could not be reloaded")
        return _score_to_read(stored)

    def score_history(self, session: Session, lead_id: str) -> list[ScoreRunRead]:
        return [_score_to_read(run) for run in self.repository.latest_scores(session, lead_id)]

    def latest_scores(self, session: Session) -> list[ScoreRunRead]:
        latest: dict[str, ScoreRun] = {}
        for run in self.repository.latest_scores(session):
            latest.setdefault(run.lead_id, run)
        return [_score_to_read(run) for run in latest.values()]

    def override(
        self,
        session: Session,
        lead_id: str,
        data: ScoreOverride,
        correlation_id: str,
    ) -> ScoreRunRead:
        lead = self.lead_repository.get(session, lead_id)
        run = self.repository.latest_score(session, lead_id)
        if lead is None:
            raise DomainError("LEAD_NOT_FOUND", "Lead not found.", status_code=404)
        if run is None:
            raise DomainError(
                "SCORE_REQUIRED",
                "Calculate a deterministic score before overriding it.",
                status_code=409,
            )
        run.final_score = data.final_score
        run.manual_override = True
        run.override_reason = data.reason
        run.overridden_at = datetime.now(UTC)
        lead.current_score = data.final_score
        lead.score_updated_at = run.overridden_at
        record_audit_event(
            session,
            action="lead.score_overridden",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "calculated_score": run.calculated_score,
                "final_score": data.final_score,
                "reason": data.reason,
            },
        )
        session.commit()
        session.expire_all()
        stored = self.repository.latest_score(session, lead_id)
        if stored is None:
            raise RuntimeError("Score run could not be reloaded")
        return _score_to_read(stored)

    @staticmethod
    def _monday(value: date | None) -> date:
        selected = value or datetime.now(UTC).date()
        return selected - timedelta(days=selected.weekday())

    def _recently_recommended(
        self,
        session: Session,
        lead: Lead,
        week_start: date,
        recommended_lead_ids: set[str] | None = None,
    ) -> bool:
        due_follow_up = any(
            follow_up.status == "open" and follow_up.due_date <= datetime.now(UTC).date()
            for follow_up in lead.follow_ups
        )
        if due_follow_up:
            return False
        if recommended_lead_ids is not None:
            return lead.id in recommended_lead_ids
        count = session.scalar(
            select(func.count())
            .select_from(ShortlistItem)
            .join(Shortlist, Shortlist.id == ShortlistItem.shortlist_id)
            .where(
                ShortlistItem.lead_id == lead.id,
                Shortlist.week_start >= week_start - timedelta(days=28),
                Shortlist.week_start < week_start,
                ShortlistItem.decision != "deferred",
            )
        )
        return bool(count)

    def _rank_candidates(
        self,
        session: Session,
        campaign: Campaign,
        week_start: date,
        correlation_id: str,
        excluded_ids: set[str] | None = None,
    ) -> list[tuple[Lead, ScoreRun, str]]:
        candidates: list[tuple[Lead, ScoreRun, str]] = []
        excluded = excluded_ids or set()
        products = self.repository.active_products(session)
        profile_cache: dict[str, ScoringProfile] = {}
        recommended_lead_ids = self.repository.recently_recommended_lead_ids(
            session, campaign.id, week_start - timedelta(days=28), week_start
        )
        for lead in self.lead_repository.list(session, campaign_id=campaign.id):
            if (
                lead.id in excluded
                or lead.suppressed
                or lead.pipeline_stage in EXCLUDED_STAGES
                or self._recently_recommended(session, lead, week_start, recommended_lead_ids)
            ):
                continue
            run = self._calculate_model(
                session,
                lead,
                campaign,
                correlation_id,
                products=products,
                profile_cache=profile_cache,
            )
            if run.final_score < campaign.minimum_score_threshold:
                continue
            product_names = [item["product_name"] for item in run.product_matches[:2]]
            contact = (
                "public contact route"
                if lead.website or lead.social_profile or lead.public_email or lead.phone_number
                else "contact route missing"
            )
            reason = f"Score {run.final_score}/100; {contact}"
            if product_names:
                reason += f"; matched {', '.join(product_names)}"
            reason += f"; pipeline stage {lead.pipeline_stage.replace('_', ' ')}."
            candidates.append((lead, run, reason))
        return sorted(
            candidates,
            key=lambda item: (
                -item[1].final_score,
                bool(item[0].communications),
                item[0].business_name.casefold(),
            ),
        )

    def _shortlist_to_read(self, session: Session, shortlist: Shortlist) -> ShortlistRead:
        items: list[ShortlistItemRead] = []
        for item in sorted(shortlist.items, key=lambda value: (value.rank, value.created_at)):
            score = session.get(ScoreRun, item.score_run_id) if item.score_run_id else None
            items.append(
                ShortlistItemRead(
                    id=item.id,
                    lead_id=item.lead.id,
                    business_name=item.lead.business_name,
                    segment=item.lead.segment,
                    location=item.lead.location,
                    pipeline_stage=item.lead.pipeline_stage,
                    score=score.final_score if score else (item.lead.current_score or 0),
                    rank=item.rank,
                    decision=item.decision,
                    reason=item.reason,
                    product_matches=[
                        ProductMatch.model_validate(match) for match in item.product_matches
                    ],
                    created_at=item.created_at,
                    decided_at=item.decided_at,
                )
            )
        return ShortlistRead(
            id=shortlist.id,
            campaign_id=shortlist.campaign_id,
            campaign_name=shortlist.campaign.name,
            week_start=shortlist.week_start,
            capacity=shortlist.capacity,
            status=shortlist.status,
            items=items,
            created_at=shortlist.created_at,
            updated_at=shortlist.updated_at,
        )

    def generate(
        self,
        session: Session,
        data: ShortlistGenerate,
        correlation_id: str,
    ) -> ShortlistRead:
        campaign = self.campaign_repository.get(session, data.campaign_id)
        if campaign is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)
        if campaign.status != "active":
            raise DomainError(
                "CAMPAIGN_NOT_ACTIVE",
                "Only active campaigns can generate a weekly shortlist.",
                status_code=409,
            )
        capacity = data.size or campaign.weekly_shortlist_size
        if capacity > campaign.weekly_shortlist_size:
            raise DomainError(
                "SHORTLIST_CAPACITY_EXCEEDED",
                "Requested shortlist size exceeds the campaign weekly capacity.",
                status_code=409,
                details={"campaign_capacity": campaign.weekly_shortlist_size},
            )
        week_start = self._monday(data.week_start)
        existing = self.repository.shortlist_for_week(session, campaign.id, week_start)
        if existing is not None:
            return self._shortlist_to_read(session, existing)
        shortlist = Shortlist(
            campaign_id=campaign.id,
            week_start=week_start,
            capacity=capacity,
            status="active",
        )
        session.add(shortlist)
        session.flush()
        candidates = self._rank_candidates(session, campaign, week_start, correlation_id)
        for rank, (lead, run, reason) in enumerate(candidates[:capacity], start=1):
            session.add(
                ShortlistItem(
                    shortlist_id=shortlist.id,
                    lead_id=lead.id,
                    score_run_id=run.id,
                    rank=rank,
                    decision="recommended",
                    reason=reason,
                    product_matches=run.product_matches,
                )
            )
            if lead.pipeline_stage in {"new", "researching", "qualified"}:
                previous = lead.pipeline_stage
                lead.pipeline_stage = "recommended_this_week"
                session.add(
                    LeadStageEvent(
                        lead_id=lead.id,
                        previous_stage=previous,
                        new_stage="recommended_this_week",
                        actor="local_user",
                        reason=f"Selected for shortlist beginning {week_start.isoformat()}",
                    )
                )
        record_audit_event(
            session,
            action="shortlist.generated",
            entity_type="shortlist",
            entity_id=shortlist.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": campaign.id,
                "week_start": week_start.isoformat(),
                "capacity": capacity,
                "selected": min(len(candidates), capacity),
            },
        )
        session.commit()
        session.expire_all()
        stored = self.repository.get_shortlist(session, shortlist.id)
        if stored is None:
            raise RuntimeError("Shortlist could not be reloaded")
        return self._shortlist_to_read(session, stored)

    def list_shortlists(self, session: Session) -> list[ShortlistRead]:
        return [
            self._shortlist_to_read(session, shortlist)
            for shortlist in self.repository.list_shortlists(session)
        ]

    def action(
        self,
        session: Session,
        shortlist_id: str,
        item_id: str,
        data: ShortlistAction,
        correlation_id: str,
    ) -> ShortlistRead:
        shortlist = self.repository.get_shortlist(session, shortlist_id)
        item = self.repository.item(session, shortlist_id, item_id)
        if shortlist is None or item is None:
            raise DomainError(
                "SHORTLIST_ITEM_NOT_FOUND", "Shortlist item not found.", status_code=404
            )
        if data.action is ShortlistDecision.APPROVED:
            if item.lead.suppressed:
                raise DomainError(
                    "LEAD_SUPPRESSED",
                    "Suppressed leads cannot be approved for weekly contact.",
                    status_code=409,
                )
            approved = sum(1 for entry in shortlist.items if entry.decision == "approved")
            if item.decision != "approved" and approved >= shortlist.capacity:
                raise DomainError(
                    "SHORTLIST_CAPACITY_EXCEEDED",
                    "Weekly contact capacity has already been reached.",
                    status_code=409,
                )
            item.decision = "approved"
        elif data.action is ShortlistDecision.DEFERRED:
            item.decision = "deferred"
        elif data.action is ShortlistDecision.DISMISSED:
            item.decision = "dismissed"
        else:
            item.decision = "replaced"
        item.decided_at = datetime.now(UTC)
        if data.reason:
            item.reason = f"{item.reason} Decision: {data.reason}"

        if data.action is ShortlistDecision.REPLACE:
            campaign = shortlist.campaign
            excluded = {entry.lead_id for entry in shortlist.items}
            replacements = self._rank_candidates(
                session,
                campaign,
                shortlist.week_start,
                correlation_id,
                excluded,
            )
            if replacements:
                lead, run, reason = replacements[0]
                session.add(
                    ShortlistItem(
                        shortlist_id=shortlist.id,
                        lead_id=lead.id,
                        score_run_id=run.id,
                        rank=max(entry.rank for entry in shortlist.items) + 1,
                        decision="recommended",
                        reason=reason,
                        product_matches=run.product_matches,
                    )
                )
        record_audit_event(
            session,
            action=f"shortlist.item_{data.action.value}",
            entity_type="shortlist_item",
            entity_id=item.id,
            correlation_id=correlation_id,
            summary={"shortlist_id": shortlist.id, "lead_id": item.lead_id},
        )
        session.commit()
        session.expire_all()
        stored = self.repository.get_shortlist(session, shortlist_id)
        if stored is None:
            raise RuntimeError("Shortlist could not be reloaded")
        return self._shortlist_to_read(session, stored)
