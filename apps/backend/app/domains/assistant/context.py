from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import (
    Campaign,
    FollowUp,
    KnowledgeNote,
    Lead,
    LeadCampaign,
    OutreachBatch,
    OutreachDraft,
    Product,
    ProvenFit,
    Shortlist,
    ShortlistItem,
)
from app.domains.assistant.schemas import AssistantContextSelection
from app.domains.campaigns.repository import CampaignRepository
from app.domains.catalogue.repository import CatalogueRepository
from app.domains.catalogue.service import CatalogueService
from app.domains.leads.repository import LeadRepository
from app.domains.outreach.repository import OutreachRepository
from app.domains.system.service import SystemService
from app.domains.templates.repository import TemplateRepository

_LEAD_LIMIT = 12
_CAMPAIGN_LIMIT = 12
_PRODUCT_LIMIT = 16
_FAMILY_LIMIT = 12
_TEMPLATE_LIMIT = 4
_FOLLOW_UP_LIMIT = 10
_SELECTED_ITEM_LIMIT = 10
# A fully enriched product costs roughly 170 tokens. Sending five in full and seven as a name
# plus a line beats sending thirty the model reads slowly and uses badly.
_FULL_PRODUCT_LIMIT = 5
_BRIEF_PRODUCT_LIMIT = 7
_KNOWLEDGE_NOTE_LIMIT = 2
_CATEGORY_LIMIT = 12
# A knowledge note runs to 1,500 characters in the pack. The opening covers who buys and why,
# which is the part that changes an answer.
_NOTE_EXCERPT = 700
_BRIEF_SUMMARY = 140
_PROVEN_FIT_LIMIT = 2

_SEARCH_STOP_WORDS = frozenset(
    {
        "about",
        "app",
        "campaign",
        "could",
        "from",
        "have",
        "lead",
        "please",
        "should",
        "that",
        "this",
        "what",
        "when",
        "where",
        "which",
        "with",
        "workspace",
        "would",
    }
)


def _excerpt(value: str | None, limit: int = 240) -> str | None:
    if value is None:
        return None
    compact = re.sub(r"\s+", " ", value).strip()
    if not compact:
        return None
    return compact[:limit] + ("…" if len(compact) > limit else "")


def _search_terms(user_request: str) -> list[str]:
    terms = {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]{2,}", user_request)
        if token.casefold() not in _SEARCH_STOP_WORDS
    }
    return sorted(terms, key=len, reverse=True)[:6]


def _relevance(text: str, terms: list[str]) -> int:
    folded = text.casefold()
    return sum(1 for term in terms if term in folded)


def _prune(value: Any) -> Any:
    """Drop empty values before serialising.

    Nulls and empty lists cost tokens and tell the model nothing. On a small context window
    that is budget better spent on another product.
    """
    if isinstance(value, dict):
        cleaned = {key: _prune(item) for key, item in value.items()}
        return {
            key: item
            for key, item in cleaned.items()
            if item not in (None, "", [], {}) or isinstance(item, bool)
        }
    if isinstance(value, list):
        pruned = [_prune(item) for item in value]
        return [item for item in pruned if item not in (None, "", [], {})]
    return value


def _prune_snapshot(value: dict[str, Any]) -> dict[str, Any]:
    return cast("dict[str, Any]", _prune(value))


def _product_score(
    product: Product,
    terms: list[str],
    *,
    lead_segments: set[str],
    prefer_business: bool,
) -> int:
    haystack = " ".join(
        (
            product.name,
            product.category,
            product.summary or "",
            product.b2b_notes or "",
            " ".join(product.materials),
            " ".join(product.target_segments),
            " ".join(product.example_use_cases),
            " ".join(product.occasions),
        )
    )
    score = _relevance(haystack, terms)
    # A product already tagged for this lead's trade is a far stronger signal than a word match.
    score += 4 * len(lead_segments & {segment.casefold() for segment in product.target_segments})
    if prefer_business and product.b2b_relevant:
        score += 3
    if prefer_business and product.bulk_ready:
        score += 1
    return score


def _product_full(product: Product) -> dict[str, Any]:
    return {
        "name": product.name,
        "category": product.category,
        "summary": product.summary,
        "materials": product.materials,
        "target_segments": product.target_segments,
        "example_use_cases": product.example_use_cases,
        "b2b_notes": product.b2b_notes,
        "custom_options": product.custom_options,
        "business_relevant": product.b2b_relevant,
        "bulk_ready": product.bulk_ready,
        "url": product.product_url,
        "sample_eligible": product.sample_eligible,
    }


def _product_brief(product: Product) -> dict[str, Any]:
    return {"name": product.name, "summary": _excerpt(product.summary, _BRIEF_SUMMARY)}


def _note_summary(note: KnowledgeNote) -> dict[str, Any]:
    return {
        "title": note.title,
        "trades": note.segments,
        "notes": _excerpt(note.body, _NOTE_EXCERPT),
    }


def _fit_summary(fit: ProvenFit) -> dict[str, Any]:
    """A past job, with the client's name withheld unless sharing it was allowed.

    The name is removed here rather than left to the prompt: a rule the data cannot break is
    worth more than a rule the model is asked to follow.
    """
    confirmed = fit.status == "confirmed"
    return {
        "trade": fit.segment,
        "client": fit.client_name if (confirmed and fit.share_client_name) else fit.client_label,
        "what_was_made": _excerpt(fit.use, 240),
        "outcome": fit.outcome,
        "confirmed_by_operator": confirmed,
        "usable_in_prospect_copy": confirmed,
    }


def _lead_candidates(session: Session, user_request: str) -> list[Lead]:
    options = (
        selectinload(Lead.campaigns).selectinload(LeadCampaign.campaign),
        selectinload(Lead.follow_ups),
    )
    relevant: list[Lead] = []
    predicates: list[ColumnElement[bool]] = []
    for term in _search_terms(user_request):
        pattern = f"%{term}%"
        predicates.extend(
            (
                Lead.business_name.ilike(pattern),
                Lead.segment.ilike(pattern),
                Lead.location.ilike(pattern),
                Lead.contact_first_name.ilike(pattern),
                Lead.contact_last_name.ilike(pattern),
            )
        )
    if predicates:
        relevant = list(
            session.scalars(
                select(Lead)
                .options(*options)
                .where(or_(*predicates))
                .order_by(Lead.updated_at.desc())
                .limit(_LEAD_LIMIT)
            )
        )
    recent = list(
        session.scalars(
            select(Lead)
            .options(*options)
            .order_by(Lead.updated_at.desc())
            .limit(_LEAD_LIMIT)
        )
    )
    combined: list[Lead] = []
    seen: set[str] = set()
    for lead in [*relevant, *recent]:
        if lead.id in seen:
            continue
        combined.append(lead)
        seen.add(lead.id)
        if len(combined) == _LEAD_LIMIT:
            break
    return combined


def _campaign_summary(campaign: Campaign) -> dict[str, Any]:
    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": _excerpt(campaign.description),
        "status": campaign.status,
        "segment": campaign.segment,
        "location": campaign.primary_location,
        "radius_miles": campaign.radius_miles,
        "minimum_score": campaign.minimum_score_threshold,
        "weekly_shortlist_size": campaign.weekly_shortlist_size,
        "keywords": campaign.keywords,
        "exclusion_keywords": campaign.exclusion_keywords,
        "product_categories": campaign.product_categories,
        "product_family_id": campaign.product_family_id,
        "discovery_sources": campaign.discovery_sources,
        "preferred_channels": campaign.preferred_channels,
        "offer_settings": campaign.offer_settings,
        "weekly_outreach_enabled": campaign.weekly_outreach_enabled,
    }


def _lead_summary(lead: Lead) -> dict[str, Any]:
    return {
        "id": lead.id,
        "business_name": lead.business_name,
        "segment": lead.segment,
        "location": lead.location,
        "website": lead.website,
        "pipeline_stage": lead.pipeline_stage,
        "current_score": lead.current_score,
        "suppressed": lead.suppressed,
        "contact_classification": lead.contact_classification,
        "contact_name": " ".join(
            part for part in (lead.contact_first_name, lead.contact_last_name) if part
        )
        or None,
        "contact_role": lead.contact_role,
        "contact_email": lead.contact_email or lead.public_email,
        "phone_number": lead.phone_number,
        "personalisation_observation": _excerpt(lead.personalisation_observation),
        "relevance_opportunity": _excerpt(lead.relevance_opportunity),
        "offer_angle": _excerpt(lead.offer_angle),
        "desired_next_step": _excerpt(lead.desired_next_step),
        "avoid_mentioning": _excerpt(lead.avoid_mentioning),
        "campaigns": sorted(link.campaign.name for link in lead.campaigns),
        "open_follow_ups": [
            {
                "type": follow_up.follow_up_type,
                "due_date": follow_up.due_date.isoformat(),
                "notes": _excerpt(follow_up.notes),
            }
            for follow_up in sorted(lead.follow_ups, key=lambda item: item.due_date)
            if follow_up.status == "open"
        ],
    }


def _selected_context(
    session: Session,
    selection: AssistantContextSelection,
) -> tuple[dict[str, Any], list[Lead]]:
    if selection.kind == "workspace":
        return (
            {
                "kind": "workspace",
                "id": None,
                "label": "Whole workspace",
                "record": None,
            },
            [],
        )

    record_id = selection.id
    if record_id is None:  # The request schema enforces this; retained for type narrowing.
        raise DomainError("ASSISTANT_CONTEXT_INVALID", "The assistant context is invalid.")

    if selection.kind == "campaign":
        campaign = CampaignRepository().get(session, record_id)
        if campaign is not None:
            leads = LeadRepository().list(session, campaign_id=campaign.id)[:_LEAD_LIMIT]
            return (
                {
                    "kind": selection.kind,
                    "id": campaign.id,
                    "label": campaign.name,
                    "record": _campaign_summary(campaign),
                },
                leads,
            )
    elif selection.kind == "lead":
        lead = LeadRepository().get(session, record_id)
        if lead is not None:
            record = _lead_summary(lead)
            record.update(
                {
                    "notes": [
                        {
                            "content": _excerpt(note.content, 300),
                            "created_at": note.created_at.isoformat(),
                        }
                        for note in sorted(lead.notes, key=lambda item: item.created_at)[-5:]
                    ],
                    "recent_communications": [
                        {
                            "channel": item.channel,
                            "subject": item.subject,
                            "content": _excerpt(item.content, 300),
                            "sent_status": item.sent_status,
                            "response_status": item.response_status,
                            "created_at": item.created_at.isoformat(),
                        }
                        for item in sorted(
                            lead.communications, key=lambda item: item.created_at
                        )[-5:]
                    ],
                    "source_evidence": [
                        {
                            "field": item.field_name,
                            "value": _excerpt(item.observed_value, 300),
                            "classification": item.classification,
                            "source": item.source_system.name,
                        }
                        for item in sorted(
                            lead.observations, key=lambda item: item.collected_at, reverse=True
                        )[:8]
                    ],
                }
            )
            return (
                {
                    "kind": selection.kind,
                    "id": lead.id,
                    "label": lead.business_name,
                    "record": record,
                },
                [lead],
            )
    elif selection.kind == "outreach_batch":
        batch = OutreachRepository().get_batch(session, record_id)
        if batch is not None:
            template = (
                TemplateRepository().get(session, batch.template_id) if batch.template_id else None
            )
            campaign = (
                CampaignRepository().get(session, batch.campaign_id) if batch.campaign_id else None
            )
            leads_by_id = {draft.lead.id: draft.lead for draft in batch.drafts}
            return (
                {
                    "kind": selection.kind,
                    "id": batch.id,
                    "label": (
                        f"{template.topic} · {batch.created_at.date().isoformat()}"
                        if template
                        else f"Draft batch {batch.id[:8]}"
                    ),
                    "record": {
                        "status": batch.status,
                        "campaign": campaign.name if campaign else None,
                        "template": template.topic if template else None,
                        "template_subject": template.subject if template else None,
                        "template_body": _excerpt(template.body, 500) if template else None,
                        "created_at": batch.created_at.isoformat(),
                        "draft_count": len(batch.drafts),
                        "draft_status_counts": dict(
                            Counter(draft.review_status for draft in batch.drafts)
                        ),
                        "drafts": [
                            {
                                "business_name": draft.lead.business_name,
                                "recipient_email": draft.recipient_email,
                                "review_status": draft.review_status,
                                "sync_status": draft.sync_status,
                                "current_version": draft.current_version,
                                "subject": next(
                                    (
                                        revision.subject
                                        for revision in draft.revisions
                                        if revision.version == draft.current_version
                                    ),
                                    None,
                                ),
                                "body": _excerpt(
                                    next(
                                        (
                                            revision.body
                                            for revision in draft.revisions
                                            if revision.version == draft.current_version
                                        ),
                                        None,
                                    ),
                                    500,
                                ),
                            }
                            for draft in batch.drafts[:_SELECTED_ITEM_LIMIT]
                        ],
                    },
                },
                list(leads_by_id.values())[:_LEAD_LIMIT],
            )
    elif selection.kind == "shortlist":
        shortlist = session.scalar(
            select(Shortlist)
            .options(
                selectinload(Shortlist.campaign),
                selectinload(Shortlist.items).selectinload(ShortlistItem.lead),
            )
            .where(Shortlist.id == record_id)
        )
        if shortlist is not None:
            return (
                {
                    "kind": selection.kind,
                    "id": shortlist.id,
                    "label": f"{shortlist.campaign.name} · {shortlist.week_start.isoformat()}",
                    "record": {
                        "campaign": shortlist.campaign.name,
                        "week_start": shortlist.week_start.isoformat(),
                        "capacity": shortlist.capacity,
                        "status": shortlist.status,
                        "item_count": len(shortlist.items),
                        "decision_counts": dict(
                            Counter(item.decision for item in shortlist.items)
                        ),
                        "items": [
                            {
                                "business_name": item.lead.business_name,
                                "rank": item.rank,
                                "decision": item.decision,
                                "reason": item.reason,
                                "product_matches": item.product_matches,
                            }
                            for item in sorted(shortlist.items, key=lambda item: item.rank)[
                                :_SELECTED_ITEM_LIMIT
                            ]
                        ],
                    },
                },
                [item.lead for item in sorted(shortlist.items, key=lambda item: item.rank)][
                    :_LEAD_LIMIT
                ],
            )

    raise DomainError(
        "ASSISTANT_CONTEXT_NOT_FOUND",
        "The selected assistant context no longer exists.",
        status_code=404,
        details={"kind": selection.kind, "id": record_id},
    )


def build_app_context(
    session: Session,
    *,
    user_request: str,
    runtime_settings: Settings,
    instagram_connected: bool,
    selection: AssistantContextSelection,
) -> dict[str, Any]:
    """Build a bounded, read-only snapshot for the local assistant.

    Everything in here is data the model may read, never instructions it may follow. Two rules
    are enforced here rather than asked for in the prompt: no pricing reaches the model, and an
    unconfirmed job never carries its client's name.
    """
    system_service = SystemService()
    workspace_settings = system_service.get_settings(session)
    operations = system_service.operations_summary(session)
    catalogue_service = CatalogueService(settings=runtime_settings)
    enrichment_status = catalogue_service.enrichment_status(session)
    catalogue_imported_at = enrichment_status.catalogue_imported_at
    catalogue_stale = enrichment_status.catalogue_stale
    selected_context, selected_leads = _selected_context(session, selection)
    search_terms = _search_terms(f"{user_request} {selected_context['label']}")
    campaigns = CampaignRepository().list(session)
    products = CatalogueRepository().list(session, active=True)
    families = CatalogueRepository().list_families(session)
    templates = TemplateRepository().list(session)
    campaigns.sort(
        key=lambda item: -_relevance(
            " ".join((item.name, item.segment, item.primary_location)), search_terms
        )
    )
    products.sort(
        key=lambda item: -_relevance(
            " ".join((item.name, item.category, item.description)), search_terms
        )
    )
    families.sort(
        key=lambda item: -_relevance(
            " ".join((item.name, item.description or "")), search_terms
        )
    )
    templates.sort(
        key=lambda item: -_relevance(
            " ".join((item.topic, item.subject, item.body)), search_terms
        )
    )
    campaigns = campaigns[:_CAMPAIGN_LIMIT]
    families = families[:_FAMILY_LIMIT]
    templates = templates[:_TEMPLATE_LIMIT]
    leads = selected_leads or _lead_candidates(session, user_request)
    category_counts = Counter(product.category for product in products)

    # Rank products for this request rather than sending the first N by name. A lead, campaign or
    # draft batch means a business is the buyer, so business-ready products come first.
    prefer_business = selection.kind in {"lead", "campaign", "outreach_batch", "shortlist"}
    lead_segments = {lead.segment.casefold() for lead in leads if lead.segment}
    if selection.kind == "campaign" and selected_context["record"] is not None:
        record = selected_context["record"]
        if isinstance(record, dict) and record.get("segment"):
            lead_segments.add(str(record["segment"]).casefold())
    products.sort(
        key=lambda item: -_product_score(
            item, search_terms, lead_segments=lead_segments, prefer_business=prefer_business
        )
    )
    full_products = products[:_FULL_PRODUCT_LIMIT]
    brief_products = products[_FULL_PRODUCT_LIMIT : _FULL_PRODUCT_LIMIT + _BRIEF_PRODUCT_LIMIT]

    notes = CatalogueRepository().list_notes(session)
    notes.sort(
        key=lambda item: -(
            4 * len(lead_segments & {segment.casefold() for segment in item.segments})
            + _relevance(f"{item.title} {item.body}", search_terms)
        )
    )
    relevant_notes = [
        note
        for note in notes[:_KNOWLEDGE_NOTE_LIMIT]
        if lead_segments & {segment.casefold() for segment in note.segments}
        or _relevance(f"{note.title} {note.body}", search_terms)
    ]
    fits = [
        fit
        for fit in CatalogueRepository().list_fits(session)
        if not lead_segments or fit.segment.casefold() in lead_segments
    ][:_PROVEN_FIT_LIMIT]
    follow_up_rows = (
        session.execute(
            select(FollowUp, Lead.business_name)
            .join(Lead, Lead.id == FollowUp.lead_id)
            .where(FollowUp.status == "open")
            .order_by(FollowUp.due_date, Lead.business_name)
            .limit(_FOLLOW_UP_LIMIT)
        ).all()
        if selection.kind == "workspace"
        else []
    )
    batch_status_rows = session.execute(
        select(OutreachBatch.status, func.count())
        .group_by(OutreachBatch.status)
        .order_by(OutreachBatch.status)
    ).all()
    draft_status_rows = session.execute(
        select(OutreachDraft.review_status, func.count())
        .group_by(OutreachDraft.review_status)
        .order_by(OutreachDraft.review_status)
    ).all()

    return _prune_snapshot(
        {
        "snapshot_at": datetime.now(UTC).isoformat(),
        "selected_context": selected_context,
        "application": {
            "name": "Etch 'N' Shine Lead Generation",
            "purpose": (
                "A local-first operator workbench for finding, qualifying and managing "
                "business leads for Etch 'N' Shine products."
            ),
            "workspaces": [
                "Overview",
                "AI assistant",
                "Campaigns",
                "All leads",
                "Weekly shortlist",
                "Pipeline",
                "Email drafts",
                "Catalogue",
                "Templates",
                "Settings",
            ],
        },
        "operations": operations.model_dump(mode="json"),
        "workspace_settings": workspace_settings.model_dump(mode="json"),
        "provider_capabilities": {
            "manual": True,
            "public_registries": True,
            "google_places": runtime_settings.google_places_enabled,
            "instagram": instagram_connected,
            "maximum_discovery_queries": runtime_settings.discovery_max_queries,
            "maximum_discovery_results": runtime_settings.discovery_max_results,
        },
        "campaigns": [
            _campaign_summary(campaign)
            for campaign in campaigns
        ],
        "relevant_or_recent_leads": [_lead_summary(lead) for lead in leads],
        "next_open_follow_ups": [
            {
                "business_name": business_name,
                "type": follow_up.follow_up_type,
                "due_date": follow_up.due_date.isoformat(),
                "notes": _excerpt(follow_up.notes),
            }
            for follow_up, business_name in follow_up_rows
        ],
        "catalogue": {
            "active_product_count": len(products),
            "last_imported_at": (
                catalogue_imported_at.isoformat() if catalogue_imported_at else None
            ),
            "may_be_out_of_date": catalogue_stale,
            "largest_categories": dict(category_counts.most_common(_CATEGORY_LIMIT)),
            # `pricing_guidance` is deliberately absent. Pricing is quoted per job and must
            # never reach a model or an email. See ADR-021.
            "products": [
                _product_full(product)
                for product in full_products
                if selection.kind not in {"outreach_batch", "shortlist"}
            ],
            "more_products": [
                _product_brief(product)
                for product in brief_products
                if selection.kind not in {"outreach_batch", "shortlist"}
            ],
            "product_families": [
                {
                    "name": family.name,
                    "description": _excerpt(family.description),
                    "product_count": len(family.product_ids),
                }
                for family in families
                if selection.kind not in {"outreach_batch", "shortlist"}
            ],
        },
        "templates": [
            {
                "topic": template.topic,
                "subject": template.subject,
                "body_excerpt": _excerpt(template.body, 160),
                "product_family_ids": template.product_family_ids,
            }
            for template in templates
            if selection.kind not in {"outreach_batch", "shortlist"}
        ],
        "outreach": {
            "batch_status_counts": {
                str(status): int(count) for status, count in batch_status_rows
            },
            "draft_review_status_counts": {
                str(status): int(count) for status, count in draft_status_rows
            },
        },
        "product_knowledge": [_note_summary(note) for note in relevant_notes],
        "proven_fits": [_fit_summary(fit) for fit in fits],
        "snapshot_limits": (
            "Named lists are bounded for the local model. Do not infer that an omitted record "
            "does not exist; use the operation counts and say when the supplied snapshot is "
            "insufficient."
        ),
        }
    )
