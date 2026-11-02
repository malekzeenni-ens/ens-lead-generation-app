"""The background job kinds and their handlers (ADR-022).

Handlers are closures over the app's shared services, registered once in `create_app`. Each reads
the workspace settings when it starts, so a setting changed while the job was queued applies.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.automation.enrichment import SafeWebsiteEnricher
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.catalogue.pack_autoload import apply_pack_if_changed
from app.domains.catalogue.schemas import EnrichmentRunRequest
from app.domains.catalogue.service import CatalogueService
from app.domains.catalogue.shopify_connection import ShopifyConnectionService, sync_error
from app.domains.lead_assistant.schemas import LeadAutofillRequest
from app.domains.lead_assistant.service import LeadAssistantService
from app.domains.system.service import SystemService
from app.jobs.manager import JobContext, JobManager

LEAD_AUTOFILL = "lead_autofill"
CATALOGUE_ENRICHMENT = "catalogue_enrichment"
CATALOGUE_SHOPIFY_SYNC = "catalogue_shopify_sync"


def register_job_kinds(
    jobs: JobManager,
    *,
    manager: Callable[[], CampaignAssistantManager],
    settings: Settings,
    shopify: ShopifyConnectionService | None = None,
) -> None:
    """`manager` is looked up when a job runs, so it is always the app's current one."""

    def lead_autofill(session: Session, context: JobContext) -> dict[str, Any]:
        enricher = SafeWebsiteEnricher(settings)
        try:
            response = LeadAssistantService().autofill_leads(
                session,
                LeadAutofillRequest.model_validate(context.payload),
                manager=manager(),
                runtime_settings=settings,
                workspace_settings=SystemService().get_settings(session),
                enricher=enricher,
                progress=context.report_progress,
                cancelled=context.cancelled,
            )
        finally:
            enricher.close()
        return response.model_dump(mode="json")

    def catalogue_enrichment(session: Session, context: JobContext) -> dict[str, Any]:
        result = CatalogueService().run_enrichment(
            session,
            EnrichmentRunRequest.model_validate(context.payload),
            manager=manager(),
            workspace_settings=SystemService().get_settings(session),
            correlation_id=context.correlation_id,
            progress=context.report_progress,
            cancelled=context.cancelled,
        )
        return result.model_dump(mode="json")

    def catalogue_shopify_sync(session: Session, context: JobContext) -> dict[str, Any]:
        """Fetch every product from Shopify, then apply them like a CSV import (ADR-026)."""
        if shopify is None:
            raise RuntimeError("The Shopify connection is not available.")
        client = shopify.client()
        context.report_progress(0, 2)
        try:
            products = client.fetch_products()
        except RuntimeError as error:
            raise sync_error(error) from error
        context.report_progress(1, 2)
        service = CatalogueService(settings=settings)
        result = service.sync_shopify(session, products, context.correlation_id)
        # The knowledge pack matches on handle, so re-apply it to the catalogue just synced.
        apply_pack_if_changed(session, settings, context.correlation_id, service)
        context.report_progress(2, 2)
        return result.model_dump(mode="json")

    jobs.register(LEAD_AUTOFILL, lead_autofill)
    jobs.register(CATALOGUE_SHOPIFY_SYNC, catalogue_shopify_sync)
    jobs.register(CATALOGUE_ENRICHMENT, catalogue_enrichment)
