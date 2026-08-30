from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError
from app.domains.automation.enrichment import EnrichmentFailure, SafeWebsiteEnricher
from app.domains.campaign_assistant.gate import require_local_ai_enabled
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.campaigns.repository import CampaignRepository
from app.domains.lead_assistant.prompt import (
    _OLLAMA_AUTOFILL_SCHEMA,
    _OLLAMA_BRIEFING_SCHEMA,
    build_autofill_messages,
    build_briefing_messages,
    build_digest_messages,
    build_digest_schema,
    build_filter_messages,
    build_filter_schema,
)
from app.domains.lead_assistant.schemas import (
    DigestModel,
    LeadAutofillRequest,
    LeadAutofillResponse,
    LeadAutofillResultItem,
    LeadAutofillSuggestion,
    LeadBriefingResponse,
    LeadFilterTranslateRequest,
    LeadFilterTranslateResult,
    StalledLeadDigestRequest,
    StalledLeadDigestResponse,
    StalledLeadSuggestion,
)
from app.domains.lead_assistant.staleness import find_stalled_leads
from app.domains.leads.repository import LeadRepository
from app.domains.leads.schemas import PipelineStage
from app.domains.system.schemas import WorkspaceSettings


class LeadAssistantService:
    def __init__(
        self,
        *,
        lead_repository: LeadRepository | None = None,
        campaign_repository: CampaignRepository | None = None,
    ) -> None:
        self.lead_repository = lead_repository or LeadRepository()
        self.campaign_repository = campaign_repository or CampaignRepository()

    def translate_filter(
        self,
        session: Session,
        data: LeadFilterTranslateRequest,
        *,
        manager: CampaignAssistantManager,
        runtime_settings: Settings,
        workspace_settings: WorkspaceSettings,
    ) -> LeadFilterTranslateResult:
        require_local_ai_enabled(runtime_settings, workspace_settings)
        stages = [stage.value for stage in PipelineStage]
        source_types = self.lead_repository.distinct_source_types(session)
        campaigns = [
            {"id": campaign.id, "name": campaign.name}
            for campaign in self.campaign_repository.list(session)
        ]
        result, _profile = manager.generate_structured(
            build_filter_messages(
                query=data.query,
                available_stages=stages,
                available_source_types=source_types,
                campaigns=campaigns,
            ),
            schema=build_filter_schema(stages, source_types),
            model_cls=LeadFilterTranslateResult,
            error_prefix="LEAD_FILTER",
            protect_resources=workspace_settings.protect_design_software_resources,
        )
        value = result.value
        updates: dict[str, Any] = {}
        if value.stage is not None and value.stage not in stages:
            updates["stage"] = None
        if value.source_type is not None and value.source_type not in source_types:
            updates["source_type"] = None
        if (
            value.campaign_id is not None
            and self.campaign_repository.get(session, value.campaign_id) is None
        ):
            updates["campaign_id"] = None
        return value.model_copy(update=updates) if updates else value

    def brief(
        self,
        session: Session,
        lead_id: str,
        *,
        manager: CampaignAssistantManager,
        runtime_settings: Settings,
        workspace_settings: WorkspaceSettings,
    ) -> LeadBriefingResponse:
        require_local_ai_enabled(runtime_settings, workspace_settings)
        lead = self.lead_repository.get(session, lead_id)
        if lead is None:
            raise DomainError("LEAD_NOT_FOUND", "Lead not found.", status_code=404)
        context: dict[str, Any] = {
            "business_name": lead.business_name,
            "segment": lead.segment,
            "location": lead.location,
            "current_score": lead.current_score,
            "campaign_names": sorted(
                link.campaign.name for link in lead.campaigns if link.campaign is not None
            ),
        }
        personalisation = {
            "personalisation_observation": lead.personalisation_observation,
            "relevance_opportunity": lead.relevance_opportunity,
            "offer_angle": lead.offer_angle,
            "desired_next_step": lead.desired_next_step,
            "avoid_mentioning": lead.avoid_mentioning,
        }
        context.update({key: value for key, value in personalisation.items() if value})
        notes = sorted(lead.notes, key=lambda note: note.created_at, reverse=True)[:3]
        if notes:
            context["latest_notes"] = [note.content for note in notes]
        if lead.score_runs:
            latest_score = max(lead.score_runs, key=lambda score: score.created_at)
            context["latest_score_breakdown"] = latest_score.breakdown
        result, _profile = manager.generate_structured(
            build_briefing_messages(context=context),
            schema=_OLLAMA_BRIEFING_SCHEMA,
            model_cls=LeadBriefingResponse,
            error_prefix="LEAD_BRIEFING",
            protect_resources=workspace_settings.protect_design_software_resources,
        )
        return result.value

    def autofill_leads(
        self,
        session: Session,
        data: LeadAutofillRequest,
        *,
        manager: CampaignAssistantManager,
        runtime_settings: Settings,
        workspace_settings: WorkspaceSettings,
        enricher: SafeWebsiteEnricher,
    ) -> LeadAutofillResponse:
        require_local_ai_enabled(runtime_settings, workspace_settings)
        items: list[LeadAutofillResultItem] = []
        for lead_id in data.lead_ids:
            lead = self.lead_repository.get(session, lead_id)
            if lead is None:
                items.append(
                    LeadAutofillResultItem(
                        lead_id=lead_id,
                        business_name="",
                        suggestion=None,
                        skipped_reason="Lead not found.",
                    )
                )
                continue
            evidence = None
            if lead.website:
                try:
                    evidence = enricher.enrich(lead.website)
                except EnrichmentFailure:
                    evidence = None
            notes = " | ".join(
                note.content[:300]
                for note in sorted(lead.notes, key=lambda note: note.created_at, reverse=True)[:3]
            )
            messages = build_autofill_messages(
                business_name=lead.business_name,
                segment=lead.segment,
                location=lead.location,
                website_evidence=asdict(evidence) if evidence else None,
                existing_notes=notes,
            )
            try:
                result, _profile = manager.generate_structured(
                    messages,
                    schema=_OLLAMA_AUTOFILL_SCHEMA,
                    model_cls=LeadAutofillSuggestion,
                    error_prefix="LEAD_AUTOFILL",
                    protect_resources=workspace_settings.protect_design_software_resources,
                )
            except DomainError as exc:
                if exc.code == "CAMPAIGN_ASSISTANT_BUSY":
                    raise
                items.append(
                    LeadAutofillResultItem(
                        lead_id=lead.id,
                        business_name=lead.business_name,
                        suggestion=None,
                        skipped_reason=exc.message,
                    )
                )
                continue
            items.append(
                LeadAutofillResultItem(
                    lead_id=lead.id,
                    business_name=lead.business_name,
                    suggestion=result.value,
                )
            )
        return LeadAutofillResponse(items=items)

    def stalled_digest(
        self,
        session: Session,
        data: StalledLeadDigestRequest,
        *,
        manager: CampaignAssistantManager,
        runtime_settings: Settings,
        workspace_settings: WorkspaceSettings,
    ) -> StalledLeadDigestResponse:
        require_local_ai_enabled(runtime_settings, workspace_settings)
        candidates = find_stalled_leads(
            session,
            stale_after_days=runtime_settings.lead_stale_after_days,
            limit=data.limit or 15,
        )
        generated_at = datetime.now(UTC)
        if not candidates:
            return StalledLeadDigestResponse(generated_at=generated_at, items=[])
        candidate_ids = [lead.id for lead, _days in candidates]
        result, _profile = manager.generate_structured(
            build_digest_messages(
                candidates=[
                    {
                        "lead_id": lead.id,
                        "business_name": lead.business_name,
                        "segment": lead.segment,
                        "location": lead.location,
                        "pipeline_stage": lead.pipeline_stage,
                        "current_score": lead.current_score,
                        "days_stale": days_stale,
                        "outreach_hold_until": (
                            lead.outreach_hold_until.isoformat()
                            if lead.outreach_hold_until
                            else None
                        ),
                        "retention_review_date": (
                            lead.retention_review_date.isoformat()
                            if lead.retention_review_date
                            else None
                        ),
                    }
                    for lead, days_stale in candidates
                ]
            ),
            schema=build_digest_schema(candidate_ids),
            model_cls=DigestModel,
            error_prefix="LEAD_DIGEST",
            protect_resources=workspace_settings.protect_design_software_resources,
        )
        by_id = {lead.id: (lead, days_stale) for lead, days_stale in candidates}
        items = [
            StalledLeadSuggestion(
                lead_id=item.lead_id,
                business_name=by_id[item.lead_id][0].business_name,
                days_stale=by_id[item.lead_id][1],
                suggested_action=item.suggested_action,
            )
            for item in result.value.items
            if item.lead_id in by_id
        ]
        return StalledLeadDigestResponse(generated_at=generated_at, items=items)
