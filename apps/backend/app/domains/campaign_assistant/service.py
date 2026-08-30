from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import Campaign, CampaignDraft, CampaignDraftOverride, CampaignDraftRevision
from app.domains.audit.service import record_audit_event
from app.domains.campaign_assistant.gate import require_local_ai_enabled
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.campaign_assistant.prompt import (
    CAMPAIGN_ASSISTANT_PROMPT_VERSION,
    OVERRIDABLE_RULE_IDS,
    PLAYBOOK_RULE_IDS,
    build_messages,
)
from app.domains.campaign_assistant.repository import CampaignDraftRepository
from app.domains.campaign_assistant.schemas import (
    AssistantStatusRead,
    CampaignDraftApprovalResult,
    CampaignDraftManualUpdate,
    CampaignDraftOverrideRead,
    CampaignDraftProposal,
    CampaignDraftRead,
    CampaignDraftRevisionRead,
    DraftStatus,
    OverrideDecision,
    OverrideDecisionValue,
    OverrideItemProposal,
    OverrideItemRead,
    OverrideRequestProposal,
    ProposalOutcome,
    ResourceProfile,
)
from app.domains.campaigns.repository import CampaignRepository
from app.domains.campaigns.schemas import (
    CampaignCreate,
    CampaignRead,
    CampaignStatus,
    DiscoveryMode,
)
from app.domains.campaigns.service import CampaignService
from app.domains.catalogue.repository import CatalogueRepository
from app.domains.system.schemas import WorkspaceSettings

ALLOWED_CHANNELS = frozenset({"email", "instagram"})
ALLOWED_OFFER_SETTINGS = frozenset({"digital_mock_up", "introductory_pricing"})
RADIUS_REQUEST_PATTERN = re.compile(
    r"\bradius\b|\b\d+(?:\.\d+)?\s*(?:mile|miles|mi)\b|\bwithin\b|\bnearby\b|\bvery local\b",
    re.IGNORECASE,
)
ACTIVE_DRAFT_STATUSES = frozenset(
    {
        DraftStatus.AWAITING_INPUT.value,
        DraftStatus.AWAITING_OVERRIDE_CONFIRMATION.value,
        DraftStatus.READY.value,
        DraftStatus.GENERATION_FAILED.value,
    }
)


class CampaignAssistantService:
    def __init__(
        self,
        manager: CampaignAssistantManager,
        runtime_settings: Settings,
        *,
        repository: CampaignDraftRepository | None = None,
        catalogue_repository: CatalogueRepository | None = None,
        campaign_repository: CampaignRepository | None = None,
        campaign_service: CampaignService | None = None,
    ) -> None:
        self.manager = manager
        self.runtime_settings = runtime_settings
        self.repository = repository or CampaignDraftRepository()
        self.catalogue_repository = catalogue_repository or CatalogueRepository()
        self.campaign_repository = campaign_repository or CampaignRepository()
        self.campaign_service = campaign_service or CampaignService()

    def status(
        self,
        workspace_settings: WorkspaceSettings,
    ) -> AssistantStatusRead:
        enabled = bool(
            self.runtime_settings.campaign_assistant_enabled
            and workspace_settings.local_campaign_assistant_enabled
        )
        profile = self.manager.resource_profile(
            workspace_settings.protect_design_software_resources
        )
        if not enabled:
            return AssistantStatusRead(
                enabled=False,
                ollama_reachable=False,
                model_installed=False,
                model_loaded=False,
                model=self.runtime_settings.ollama_model,
                resource_profile=profile,
                protected_applications=sorted(self.manager.active_applications),
                ready=False,
                message="The local AI assistant is disabled in Settings.",
            )
        reachable, installed, loaded = self.manager.ollama.status()
        model = self.runtime_settings.ollama_model
        model_installed = model in installed or f"{model}:latest" in installed
        model_loaded = model in loaded or f"{model}:latest" in loaded
        protected = sorted(self.manager.active_applications)
        if not reachable:
            message = "Ollama is not installed or is not currently running."
        elif not model_installed:
            message = f"Ollama is running, but {model} is not installed."
        elif profile == ResourceProfile.DESIGN_SOFTWARE:
            message = f"Ready in reduced-resource mode because {', '.join(protected)} is running."
        else:
            message = "The local AI assistant is ready."
        return AssistantStatusRead(
            enabled=True,
            ollama_reachable=reachable,
            model_installed=model_installed,
            model_loaded=model_loaded,
            model=model,
            resource_profile=profile,
            protected_applications=protected,
            ready=reachable and model_installed,
            message=message,
        )

    def list_drafts(self, session: Session, status: str | None = None) -> list[CampaignDraftRead]:
        return [self._read(draft) for draft in self.repository.list(session, status)]

    def get(self, session: Session, draft_id: str) -> CampaignDraftRead:
        return self._read(self._require_draft(session, draft_id))

    def generate(
        self,
        session: Session,
        *,
        message: str,
        workspace_settings: WorkspaceSettings,
        instagram_connected: bool,
        correlation_id: str,
    ) -> CampaignDraftRead:
        self._require_enabled(workspace_settings)
        profile = self.manager.resource_profile(
            workspace_settings.protect_design_software_resources
        )
        draft = CampaignDraft(
            status=DraftStatus.GENERATING.value,
            original_request=message,
            model_name=self.runtime_settings.ollama_model,
            prompt_version=CAMPAIGN_ASSISTANT_PROMPT_VERSION,
            resource_profile=profile.value,
        )
        self.repository.add(session, draft)
        session.commit()
        session.refresh(draft)
        try:
            return self._generate_revision(
                session,
                draft=draft,
                message=message,
                revision_source="generated",
                next_version=1,
                workspace_settings=workspace_settings,
                instagram_connected=instagram_connected,
                correlation_id=correlation_id,
            )
        except DomainError:
            self._mark_failed(session, draft)
            raise

    def message(
        self,
        session: Session,
        *,
        draft_id: str,
        message: str,
        expected_version: int,
        workspace_settings: WorkspaceSettings,
        instagram_connected: bool,
        correlation_id: str,
    ) -> CampaignDraftRead:
        self._require_enabled(workspace_settings)
        draft = self._require_draft(session, draft_id)
        self._require_version(draft, expected_version)
        if draft.status == DraftStatus.AWAITING_OVERRIDE_CONFIRMATION.value:
            raise DomainError(
                "CAMPAIGN_OVERRIDE_DECISION_REQUIRED",
                "Confirm or reject the pending playbook override before refining the draft.",
                status_code=409,
            )
        if draft.status not in ACTIVE_DRAFT_STATUSES:
            raise DomainError(
                "CAMPAIGN_DRAFT_NOT_EDITABLE",
                "This campaign draft can no longer be changed.",
                status_code=409,
            )
        draft.status = DraftStatus.GENERATING.value
        session.commit()
        try:
            return self._generate_revision(
                session,
                draft=draft,
                message=message,
                revision_source="assistant_refinement",
                next_version=draft.version + 1,
                workspace_settings=workspace_settings,
                instagram_connected=instagram_connected,
                correlation_id=correlation_id,
            )
        except DomainError:
            self._mark_failed(session, draft)
            raise

    def manual_update(
        self,
        session: Session,
        draft_id: str,
        data: CampaignDraftManualUpdate,
        correlation_id: str,
        *,
        instagram_connected: bool,
    ) -> CampaignDraftRead:
        draft = self._require_draft(session, draft_id)
        self._require_version(draft, data.expected_version)
        if draft.status != DraftStatus.READY.value or draft.current_payload is None:
            raise DomainError(
                "CAMPAIGN_DRAFT_NOT_READY",
                "Generate a complete campaign draft before editing its fields.",
                status_code=409,
            )
        forbidden = {
            "status",
            "weekly_outreach_enabled",
            "weekly_outreach_template_id",
            "weekly_outreach_provider",
        }
        if forbidden & data.changes.model_fields_set:
            raise DomainError(
                "CAMPAIGN_DRAFT_PROTECTED_FIELD",
                "Campaign status and weekly automation cannot be changed in an assistant draft.",
            )
        merged = {**draft.current_payload, **data.changes.model_dump(exclude_unset=True)}
        campaign = self._validate_campaign(
            session,
            CampaignCreate.model_validate(merged),
            instagram_connected=instagram_connected,
            warnings=draft.warnings,
        )
        next_version = draft.version + 1
        draft.current_payload = campaign.model_dump(mode="json")
        draft.version = next_version
        draft.status = DraftStatus.READY.value
        self.repository.add_revision(
            session,
            self._revision(
                draft,
                version=next_version,
                source="manual_edit",
                instruction="Manual field edit",
            ),
        )
        record_audit_event(
            session,
            action="campaign_draft.edited",
            entity_type="campaign_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={"version": next_version, "fields": sorted(data.changes.model_fields_set)},
        )
        session.commit()
        return self.get(session, draft.id)

    def decide_override(
        self,
        session: Session,
        *,
        draft_id: str,
        override_id: str,
        data: OverrideDecision,
        workspace_settings: WorkspaceSettings,
        instagram_connected: bool,
        correlation_id: str,
    ) -> CampaignDraftRead:
        self._require_enabled(workspace_settings)
        draft = self._require_draft(session, draft_id)
        self._require_version(draft, data.expected_version)
        override = self.repository.get_override(session, draft_id, override_id)
        if override is None:
            raise DomainError(
                "CAMPAIGN_OVERRIDE_NOT_FOUND",
                "The campaign playbook override was not found.",
                status_code=404,
            )
        if override.status != "pending":
            raise DomainError(
                "CAMPAIGN_OVERRIDE_ALREADY_DECIDED",
                "This campaign playbook override already has a decision.",
                status_code=409,
            )
        item_ids = {str(item["item_id"]) for item in override.items}
        confirmed_ids = set(data.confirmed_item_ids)
        if data.decision == OverrideDecisionValue.CONFIRM and not confirmed_ids:
            confirmed_ids = item_ids
        if not confirmed_ids.issubset(item_ids):
            raise DomainError(
                "CAMPAIGN_OVERRIDE_ITEM_INVALID",
                "One or more selected override items are not part of this request.",
            )
        if data.decision == OverrideDecisionValue.PARTIAL and not confirmed_ids:
            raise DomainError(
                "CAMPAIGN_OVERRIDE_PARTIAL_EMPTY",
                "Choose at least one override item for a partial confirmation.",
            )
        if data.decision == OverrideDecisionValue.REJECT:
            confirmed_ids = set()

        now = datetime.now(UTC)
        decided_items: list[dict[str, Any]] = []
        for item in override.items:
            decided_items.append(
                {
                    **item,
                    "decision": (
                        "confirmed" if str(item["item_id"]) in confirmed_ids else "rejected"
                    ),
                }
            )
        override.items = decided_items
        if confirmed_ids == item_ids:
            override.status = "confirmed"
            override.confirmed_at = now
        elif confirmed_ids:
            override.status = "partially_confirmed"
            override.confirmed_at = now
            override.rejected_at = now
        else:
            override.status = "rejected"
            override.rejected_at = now
        draft.status = DraftStatus.GENERATING.value
        session.commit()

        confirmed_context = self._override_context(draft)
        instruction = (
            f"Original campaign request: {draft.original_request}\n"
            "Generate the complete campaign now using the recorded override decisions. "
            "Apply confirmed items exactly and retain playbook recommendations for rejected items."
        )
        try:
            return self._generate_revision(
                session,
                draft=draft,
                message=instruction,
                revision_source="assistant_refinement",
                next_version=draft.version + 1,
                workspace_settings=workspace_settings,
                instagram_connected=instagram_connected,
                correlation_id=correlation_id,
                confirmed_overrides=confirmed_context,
            )
        except DomainError:
            self._mark_failed(session, draft)
            raise

    def discard(
        self, session: Session, draft_id: str, expected_version: int, correlation_id: str
    ) -> CampaignDraftRead:
        draft = self._require_draft(session, draft_id)
        self._require_version(draft, expected_version)
        if draft.status == DraftStatus.APPROVED.value:
            raise DomainError(
                "CAMPAIGN_DRAFT_ALREADY_APPROVED",
                "An approved campaign draft cannot be discarded.",
                status_code=409,
            )
        draft.status = DraftStatus.DISCARDED.value
        record_audit_event(
            session,
            action="campaign_draft.discarded",
            entity_type="campaign_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={"version": draft.version},
        )
        session.commit()
        return self.get(session, draft.id)

    def approve(
        self,
        session: Session,
        *,
        draft_id: str,
        expected_version: int,
        instagram_connected: bool,
        correlation_id: str,
    ) -> CampaignDraftApprovalResult:
        draft = self._require_draft(session, draft_id)
        if draft.status == DraftStatus.APPROVED.value and draft.approved_campaign_id:
            campaign = session.get(Campaign, draft.approved_campaign_id)
            if campaign is not None:
                return CampaignDraftApprovalResult(
                    draft=self._read(draft), campaign=CampaignRead.model_validate(campaign)
                )
        self._require_version(draft, expected_version)
        if draft.status != DraftStatus.READY.value or draft.current_payload is None:
            raise DomainError(
                "CAMPAIGN_DRAFT_NOT_READY",
                "Resolve questions and playbook overrides before approving this campaign draft.",
                status_code=409,
            )
        if self.repository.pending_override(session, draft.id) is not None:
            raise DomainError(
                "CAMPAIGN_OVERRIDE_DECISION_REQUIRED",
                "Resolve the pending playbook override before approving this campaign draft.",
                status_code=409,
            )
        campaign_data = self._validate_campaign(
            session,
            CampaignCreate.model_validate(draft.current_payload),
            instagram_connected=instagram_connected,
            warnings=draft.warnings,
        )
        campaign = self.campaign_service.create_in_transaction(
            session, campaign_data, correlation_id
        )
        draft.approved_campaign_id = campaign.id
        draft.approved_at = datetime.now(UTC)
        draft.status = DraftStatus.APPROVED.value
        record_audit_event(
            session,
            action="campaign_draft.approved",
            entity_type="campaign_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={
                "version": draft.version,
                "campaign_id": campaign.id,
                "confirmed_override_ids": [
                    item.id
                    for item in draft.overrides
                    if item.status in {"confirmed", "partially_confirmed"}
                ],
            },
        )
        session.commit()
        session.refresh(campaign)
        return CampaignDraftApprovalResult(
            draft=self.get(session, draft.id),
            campaign=CampaignRead.model_validate(campaign),
        )

    def _generate_revision(
        self,
        session: Session,
        *,
        draft: CampaignDraft,
        message: str,
        revision_source: str,
        next_version: int,
        workspace_settings: WorkspaceSettings,
        instagram_connected: bool,
        correlation_id: str,
        confirmed_overrides: list[dict[str, Any]] | None = None,
    ) -> CampaignDraftRead:
        context = self._context(
            session,
            workspace_settings=workspace_settings,
            instagram_connected=instagram_connected,
        )
        resolved_overrides = (
            confirmed_overrides
            if confirmed_overrides is not None
            else self._override_context(draft)
        )
        messages = build_messages(
            message=message,
            context=context,
            current_campaign=draft.current_payload,
            confirmed_overrides=resolved_overrides,
        )
        result, profile = self.manager.generate(
            messages,
            protect_resources=workspace_settings.protect_design_software_resources,
        )
        proposal = result.proposal
        if proposal.outcome == ProposalOutcome.DRAFT_READY and proposal.campaign is not None:
            campaign = self._apply_defaults_for_unmentioned_settings(
                proposal.campaign,
                message=message,
                workspace_settings=workspace_settings,
            )
            campaign = self._apply_confirmed_structured_overrides(
                campaign,
                confirmed_overrides=resolved_overrides,
            )
            proposal = proposal.model_copy(update={"campaign": campaign})
        if not self.runtime_settings.google_places_enabled:
            proposal = proposal.model_copy(
                update={"warnings": self._without_cost_warnings(proposal.warnings)}
            )
        if proposal.outcome == ProposalOutcome.DRAFT_READY and proposal.campaign is not None:
            missed_override = self._structured_override_request(
                proposal.campaign,
                workspace_settings=workspace_settings,
                confirmed_overrides=resolved_overrides,
            )
            if missed_override is not None:
                proposal = CampaignDraftProposal(
                    outcome=ProposalOutcome.CONFIRMATION_REQUIRED,
                    assistant_message=(
                        "This draft departs from the campaign playbook. Confirm the "
                        "listed override before I prepare the final draft."
                    ),
                    assumptions=proposal.assumptions,
                    warnings=proposal.warnings,
                    override_request=missed_override,
                )
        draft.resource_profile = profile.value
        draft.model_name = result.metrics.model
        draft.model_digest = result.metrics.model_digest
        draft.generation_duration_ms = result.metrics.total_duration_ms
        draft.prompt_token_count = result.metrics.prompt_eval_count
        draft.output_token_count = result.metrics.eval_count
        draft.assistant_message = proposal.assistant_message
        draft.assumptions = proposal.assumptions
        draft.warnings = proposal.warnings
        draft.questions = proposal.questions
        draft.version = next_version

        if proposal.outcome == ProposalOutcome.DRAFT_READY:
            if proposal.campaign is None:
                raise DomainError(
                    "CAMPAIGN_ASSISTANT_INVALID_RESPONSE",
                    "The local model did not provide a complete campaign draft.",
                )
            campaign = self._validate_campaign(
                session,
                proposal.campaign,
                instagram_connected=instagram_connected,
                warnings=draft.warnings,
            )
            draft.current_payload = campaign.model_dump(mode="json")
            draft.status = DraftStatus.READY.value
        elif proposal.outcome == ProposalOutcome.CONFIRMATION_REQUIRED:
            self._save_override(session, draft, message, proposal)
            draft.status = DraftStatus.AWAITING_OVERRIDE_CONFIRMATION.value
        else:
            draft.status = DraftStatus.AWAITING_INPUT.value

        self.repository.add_revision(
            session,
            self._revision(
                draft,
                version=next_version,
                source=revision_source,
                instruction=message,
            ),
        )
        record_audit_event(
            session,
            action="campaign_draft.generated",
            entity_type="campaign_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={
                "version": next_version,
                "status": draft.status,
                "model": draft.model_name,
                "prompt_version": draft.prompt_version,
                "resource_profile": draft.resource_profile,
            },
        )
        session.commit()
        return self.get(session, draft.id)

    def _context(
        self,
        session: Session,
        *,
        workspace_settings: WorkspaceSettings,
        instagram_connected: bool,
    ) -> dict[str, Any]:
        products = self.catalogue_repository.list(session, active=True)
        families = self.catalogue_repository.list_families(session)
        campaigns = self.campaign_repository.list(session)
        return {
            "workspace_defaults": {
                "radius_miles": workspace_settings.default_campaign_radius_miles,
                "weekly_shortlist_size": workspace_settings.default_weekly_shortlist_size,
                "minimum_score_threshold": 50,
            },
            "provider_limits": {
                "maximum_queries": self.runtime_settings.discovery_max_queries,
                "maximum_results": self.runtime_settings.discovery_max_results,
            },
            "providers": [
                {"id": "manual", "available": True, "may_incur_charges": False},
                {
                    "id": "google_places",
                    "available": self.runtime_settings.google_places_enabled,
                    "may_incur_charges": True,
                },
                {
                    "id": "instagram",
                    "available": instagram_connected,
                    "may_incur_charges": False,
                },
                {
                    "id": "public_registries",
                    "available": True,
                    "may_incur_charges": False,
                },
            ],
            "product_categories": sorted({product.category for product in products}),
            "product_families": [
                {
                    "id": family.id,
                    "name": family.name,
                    "description": family.description,
                    "product_count": len(family.product_ids),
                }
                for family in families
            ],
            "existing_campaign_names": [campaign.name for campaign in campaigns],
            "allowed_channels": sorted(ALLOWED_CHANNELS),
            "allowed_offer_settings": sorted(ALLOWED_OFFER_SETTINGS),
        }

    def _validate_campaign(
        self,
        session: Session,
        campaign: CampaignCreate,
        *,
        instagram_connected: bool,
        warnings: list[str],
    ) -> CampaignCreate:
        payload = campaign.model_dump(mode="json")
        available_sources = {"manual", "public_registries"}
        if self.runtime_settings.google_places_enabled:
            available_sources.add("google_places")
        if instagram_connected:
            available_sources.add("instagram")
        sources = ["manual"] + [
            source for source in payload["discovery_sources"] if source != "manual"
        ]
        sources = list(dict.fromkeys(sources))
        unavailable = set(sources) - available_sources
        sources = [source for source in sources if source in available_sources]
        if unavailable:
            warnings.append(
                "Unavailable discovery sources were removed from the draft: "
                + ", ".join(sorted(unavailable))
                + "."
            )
        payload.update(
            {
                "discovery_sources": sources,
                "discovery_mode": (
                    DiscoveryMode.COMBINED.value if len(sources) > 1 else DiscoveryMode.MANUAL.value
                ),
                "weekly_outreach_enabled": False,
                "weekly_outreach_template_id": None,
                "weekly_outreach_provider": "scoring",
                "status": CampaignStatus.PAUSED.value,
            }
        )
        validated = CampaignCreate.model_validate(payload)
        if len(validated.keywords) > self.runtime_settings.discovery_max_queries:
            raise DomainError(
                "CAMPAIGN_ASSISTANT_QUERY_LIMIT",
                (
                    "Use no more than "
                    f"{self.runtime_settings.discovery_max_queries} discovery keywords."
                ),
            )
        unsupported_channels = set(validated.preferred_channels) - ALLOWED_CHANNELS
        if unsupported_channels:
            raise DomainError(
                "CAMPAIGN_ASSISTANT_CHANNEL_UNSUPPORTED",
                "The local model selected an unsupported outreach channel.",
                details={"channels": sorted(unsupported_channels)},
            )
        unsupported_offers = set(validated.offer_settings) - ALLOWED_OFFER_SETTINGS
        if unsupported_offers:
            raise DomainError(
                "CAMPAIGN_ASSISTANT_OFFER_UNSUPPORTED",
                "The local model selected an unsupported offer setting.",
                details={"offer_settings": sorted(unsupported_offers)},
            )
        products = self.catalogue_repository.list(session, active=True)
        categories = {product.category.casefold(): product.category for product in products}
        unknown_categories = [
            category
            for category in validated.product_categories
            if category.casefold() not in categories
        ]
        if unknown_categories:
            raise DomainError(
                "CAMPAIGN_ASSISTANT_CATEGORY_UNKNOWN",
                "The local model selected product categories that are not in the active catalogue.",
                details={"categories": unknown_categories},
            )
        if (
            validated.product_family_id is not None
            and self.catalogue_repository.get_family(session, validated.product_family_id) is None
        ):
            raise DomainError(
                "CAMPAIGN_ASSISTANT_FAMILY_UNKNOWN",
                "The local model selected a product family that does not exist.",
            )
        if self.campaign_repository.get_by_name(session, validated.name) is not None:
            raise DomainError(
                "CAMPAIGN_NAME_EXISTS",
                "A campaign with this name already exists.",
                status_code=409,
            )
        warnings[:] = self._without_cost_warnings(warnings)
        if "google_places" in validated.discovery_sources:
            cost_warning = (
                "Google Places may incur provider usage charges when this campaign is run."
            )
            if cost_warning not in warnings:
                warnings.append(cost_warning)
        return validated

    @staticmethod
    def _apply_defaults_for_unmentioned_settings(
        campaign: CampaignCreate,
        *,
        message: str,
        workspace_settings: WorkspaceSettings,
    ) -> CampaignCreate:
        payload = campaign.model_dump(mode="json")
        folded = message.casefold()
        if RADIUS_REQUEST_PATTERN.search(message) is None:
            payload["radius_miles"] = workspace_settings.default_campaign_radius_miles
        if "shortlist" not in folded and "weekly list" not in folded:
            payload["weekly_shortlist_size"] = workspace_settings.default_weekly_shortlist_size
        if "threshold" not in folded and "minimum score" not in folded:
            payload["minimum_score_threshold"] = 50
        return CampaignCreate.model_validate(payload)

    @staticmethod
    def _without_cost_warnings(warnings: list[str]) -> list[str]:
        charge_terms = ("charge", "cost", "billable", "fee")
        return [
            warning
            for warning in warnings
            if not any(term in warning.casefold() for term in charge_terms)
        ]

    def _apply_confirmed_structured_overrides(
        self,
        campaign: CampaignCreate,
        *,
        confirmed_overrides: list[dict[str, Any]],
    ) -> CampaignCreate:
        payload = campaign.model_dump(mode="json")
        for override in confirmed_overrides:
            for item in override.get("items", []):
                if item.get("decision") != "confirmed":
                    continue
                rule_id = item.get("rule_id")
                requested = item.get("requested_value")
                if rule_id == "local-radius":
                    radius = self._number_from_override(requested)
                    if radius is not None:
                        payload["radius_miles"] = radius
                elif rule_id == "conservative-shortlist" and isinstance(requested, dict):
                    if "weekly_shortlist_size" in requested:
                        payload["weekly_shortlist_size"] = requested["weekly_shortlist_size"]
                    if "minimum_score_threshold" in requested:
                        payload["minimum_score_threshold"] = requested["minimum_score_threshold"]
                elif (
                    rule_id == "billable-provider"
                    and self.runtime_settings.google_places_enabled
                    and "google" in str(requested).casefold()
                ):
                    payload["discovery_sources"] = list(
                        dict.fromkeys([*payload["discovery_sources"], "google_places"])
                    )
        return CampaignCreate.model_validate(payload)

    @staticmethod
    def _number_from_override(value: Any) -> float | None:
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
        match = re.search(r"\d+(?:\.\d+)?", str(value))
        return float(match.group()) if match is not None else None

    def _structured_override_request(
        self,
        campaign: CampaignCreate,
        *,
        workspace_settings: WorkspaceSettings,
        confirmed_overrides: list[dict[str, Any]],
    ) -> OverrideRequestProposal | None:
        confirmed_rule_ids = {
            str(item.get("rule_id"))
            for override in confirmed_overrides
            for item in override.get("items", [])
            if item.get("decision") == "confirmed"
        }
        items: list[OverrideItemProposal] = []
        if (
            campaign.radius_miles != workspace_settings.default_campaign_radius_miles
            and "local-radius" not in confirmed_rule_ids
        ):
            items.append(
                OverrideItemProposal(
                    rule_id="local-radius",
                    field="radius_miles",
                    playbook_recommendation=(workspace_settings.default_campaign_radius_miles),
                    requested_value=campaign.radius_miles,
                    impact=(
                        "A wider area can reduce local relevance; a narrower area can reduce "
                        "the number of suitable prospects."
                    ),
                )
            )
        shortlist_changed = (
            campaign.weekly_shortlist_size != workspace_settings.default_weekly_shortlist_size
            or campaign.minimum_score_threshold != 50
        )
        if shortlist_changed and "conservative-shortlist" not in confirmed_rule_ids:
            items.append(
                OverrideItemProposal(
                    rule_id="conservative-shortlist",
                    field="weekly_shortlist_size/minimum_score_threshold",
                    playbook_recommendation={
                        "weekly_shortlist_size": (workspace_settings.default_weekly_shortlist_size),
                        "minimum_score_threshold": 50,
                    },
                    requested_value={
                        "weekly_shortlist_size": campaign.weekly_shortlist_size,
                        "minimum_score_threshold": campaign.minimum_score_threshold,
                    },
                    impact=(
                        "Changing volume or the score threshold affects review workload and "
                        "lead quality."
                    ),
                )
            )
        if (
            "google_places" in campaign.discovery_sources
            and self.runtime_settings.google_places_enabled
            and "billable-provider" not in confirmed_rule_ids
        ):
            items.append(
                OverrideItemProposal(
                    rule_id="billable-provider",
                    field="discovery_sources",
                    playbook_recommendation="Use no-cost providers unless charges are confirmed.",
                    requested_value="google_places",
                    impact="Google Places can incur provider usage charges when discovery runs.",
                )
            )
        if not items:
            return None
        return OverrideRequestProposal(
            summary="Confirm the campaign settings that differ from the playbook.",
            items=items,
        )

    def _save_override(
        self,
        session: Session,
        draft: CampaignDraft,
        message: str,
        proposal: CampaignDraftProposal,
    ) -> None:
        request = proposal.override_request
        if request is None:
            raise DomainError(
                "CAMPAIGN_ASSISTANT_INVALID_OVERRIDE",
                "The local model did not explain the requested playbook override.",
            )
        items: list[dict[str, Any]] = []
        for item in request.items:
            if item.rule_id not in PLAYBOOK_RULE_IDS:
                raise DomainError(
                    "CAMPAIGN_ASSISTANT_RULE_UNKNOWN",
                    "The local model referenced an unknown campaign playbook rule.",
                    details={"rule_id": item.rule_id},
                )
            if item.rule_id not in OVERRIDABLE_RULE_IDS:
                raise DomainError(
                    "CAMPAIGN_ASSISTANT_OVERRIDE_FORBIDDEN",
                    "This campaign playbook rule cannot be overridden.",
                    details={"rule_id": item.rule_id},
                )
            items.append(
                {
                    "item_id": str(uuid4()),
                    **item.model_dump(mode="json"),
                    "decision": "pending",
                }
            )
        self.repository.add_override(
            session,
            CampaignDraftOverride(
                draft_id=draft.id,
                draft_version=draft.version,
                status="pending",
                originating_message=message,
                summary=request.summary,
                items=items,
                playbook_version=CAMPAIGN_ASSISTANT_PROMPT_VERSION,
            ),
        )

    @staticmethod
    def _override_context(draft: CampaignDraft) -> list[dict[str, Any]]:
        return [
            {
                "override_id": override.id,
                "status": override.status,
                "summary": override.summary,
                "items": override.items,
            }
            for override in draft.overrides
            if override.status in {"confirmed", "partially_confirmed", "rejected"}
        ]

    def _revision(
        self,
        draft: CampaignDraft,
        *,
        version: int,
        source: str,
        instruction: str,
    ) -> CampaignDraftRevision:
        return CampaignDraftRevision(
            draft_id=draft.id,
            version=version,
            revision_source=source,
            user_instruction=instruction,
            payload=draft.current_payload,
            assistant_message=draft.assistant_message,
            assumptions=draft.assumptions,
            warnings=draft.warnings,
            questions=draft.questions,
            resource_profile=draft.resource_profile,
            model_name=draft.model_name,
            prompt_version=draft.prompt_version,
        )

    def _mark_failed(self, session: Session, draft: CampaignDraft) -> None:
        draft.status = DraftStatus.GENERATION_FAILED.value
        session.commit()

    def _require_enabled(self, settings: WorkspaceSettings) -> None:
        require_local_ai_enabled(self.runtime_settings, settings)

    def _require_draft(self, session: Session, draft_id: str) -> CampaignDraft:
        draft = self.repository.get(session, draft_id)
        if draft is None:
            raise DomainError(
                "CAMPAIGN_DRAFT_NOT_FOUND", "Campaign draft not found.", status_code=404
            )
        return draft

    @staticmethod
    def _require_version(draft: CampaignDraft, expected_version: int) -> None:
        if draft.version != expected_version:
            raise DomainError(
                "CAMPAIGN_DRAFT_VERSION_CONFLICT",
                "The campaign draft changed. Refresh it before continuing.",
                status_code=409,
                details={"expected": expected_version, "current": draft.version},
            )

    @staticmethod
    def _read(draft: CampaignDraft) -> CampaignDraftRead:
        revisions = sorted(draft.revisions, key=lambda item: item.version)
        overrides = sorted(draft.overrides, key=lambda item: item.created_at)
        return CampaignDraftRead(
            id=draft.id,
            status=draft.status,
            original_request=draft.original_request,
            campaign=(
                CampaignCreate.model_validate(draft.current_payload)
                if draft.current_payload is not None
                else None
            ),
            assistant_message=draft.assistant_message,
            assumptions=draft.assumptions,
            warnings=draft.warnings,
            questions=draft.questions,
            version=draft.version,
            model_name=draft.model_name,
            prompt_version=draft.prompt_version,
            resource_profile=draft.resource_profile,
            generation_duration_ms=draft.generation_duration_ms,
            prompt_token_count=draft.prompt_token_count,
            output_token_count=draft.output_token_count,
            approved_campaign_id=draft.approved_campaign_id,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
            approved_at=draft.approved_at,
            overrides=[
                CampaignDraftOverrideRead(
                    id=item.id,
                    draft_id=item.draft_id,
                    draft_version=item.draft_version,
                    status=item.status,
                    summary=item.summary,
                    items=[OverrideItemRead.model_validate(value) for value in item.items],
                    playbook_version=item.playbook_version,
                    created_at=item.created_at,
                    confirmed_at=item.confirmed_at,
                    rejected_at=item.rejected_at,
                )
                for item in overrides
            ],
            revisions=[CampaignDraftRevisionRead.model_validate(item) for item in revisions],
        )
