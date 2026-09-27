from typing import Annotated, cast

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import Authenticated, DatabaseSession
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.catalogue.schemas import (
    EnrichmentImport,
    EnrichmentImportResult,
    EnrichmentRunRequest,
    EnrichmentRunResult,
    EnrichmentStatus,
    KnowledgeNoteRead,
    KnowledgeNoteUpdate,
    ProductCreate,
    ProductFamilyCreate,
    ProductFamilyRead,
    ProductFamilyUpdate,
    ProductRead,
    ProductUpdate,
    ProvenFitRead,
    ProvenFitUpdate,
    ShopifyCsvImport,
    ShopifyImportResult,
)
from app.domains.catalogue.service import CatalogueService
from app.domains.system.service import SystemService

router = APIRouter(prefix="/catalogue", tags=["catalogue"])
service = CatalogueService()


@router.get("/product-families", response_model=list[ProductFamilyRead])
def list_product_families(_: Authenticated, session: DatabaseSession) -> list[ProductFamilyRead]:
    return service.list_families(session)


@router.post(
    "/product-families", response_model=ProductFamilyRead, status_code=status.HTTP_201_CREATED
)
def create_product_family(
    data: ProductFamilyCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ProductFamilyRead:
    return service.create_family(session, data, request.state.correlation_id)


@router.patch("/product-families/{family_id}", response_model=ProductFamilyRead)
def update_product_family(
    family_id: str,
    data: ProductFamilyUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ProductFamilyRead:
    return service.update_family(session, family_id, data, request.state.correlation_id)


@router.delete("/product-families/{family_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_family(
    family_id: str,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> None:
    service.delete_family(session, family_id, request.state.correlation_id)


@router.get("/products", response_model=list[ProductRead])
def list_products(
    _: Authenticated,
    session: DatabaseSession,
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    active: bool | None = None,
) -> list[ProductRead]:
    return service.list(session, query=query, active=active)


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ProductRead:
    return service.create(session, data, request.state.correlation_id)


@router.patch("/products/{product_id}", response_model=ProductRead)
def update_product(
    product_id: str,
    data: ProductUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ProductRead:
    return service.update(session, product_id, data, request.state.correlation_id)


@router.post("/import/shopify", response_model=ShopifyImportResult)
def import_shopify_csv(
    data: ShopifyCsvImport,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ShopifyImportResult:
    return service.import_shopify(session, data, request.state.correlation_id)


@router.post("/import/enrichment", response_model=EnrichmentImportResult)
def import_enrichment_pack(
    data: EnrichmentImport,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> EnrichmentImportResult:
    return service.import_enrichment(session, data, request.state.correlation_id)


@router.get("/enrichment/status", response_model=EnrichmentStatus)
def get_enrichment_status(_: Authenticated, session: DatabaseSession) -> EnrichmentStatus:
    return service.enrichment_status(session)


@router.post("/enrichment/run", response_model=EnrichmentRunResult)
def run_enrichment(
    data: EnrichmentRunRequest,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> EnrichmentRunResult:
    """Enrich pending products with the local model, in the foreground.

    Deliberately not a background job: every local generation shares one non-blocking lock, so
    a background run would make the operator's own assistant requests fail while it worked.
    """
    manager = cast(CampaignAssistantManager, request.app.state.campaign_assistant_manager)
    workspace_settings = SystemService().get_settings(session)
    return service.run_enrichment(
        session,
        data,
        manager=manager,
        workspace_settings=workspace_settings,
        correlation_id=request.state.correlation_id,
    )


@router.get("/knowledge-notes", response_model=list[KnowledgeNoteRead])
def list_knowledge_notes(_: Authenticated, session: DatabaseSession) -> list[KnowledgeNoteRead]:
    return service.list_notes(session)


@router.patch("/knowledge-notes/{note_id}", response_model=KnowledgeNoteRead)
def update_knowledge_note(
    note_id: str,
    data: KnowledgeNoteUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> KnowledgeNoteRead:
    return service.update_note(session, note_id, data, request.state.correlation_id)


@router.get("/proven-fits", response_model=list[ProvenFitRead])
def list_proven_fits(_: Authenticated, session: DatabaseSession) -> list[ProvenFitRead]:
    return service.list_fits(session)


@router.patch("/proven-fits/{fit_id}", response_model=ProvenFitRead)
def update_proven_fit(
    fit_id: str,
    data: ProvenFitUpdate,
    request: Request,
    _: Authenticated,
    session: DatabaseSession,
) -> ProvenFitRead:
    return service.update_fit(session, fit_id, data, request.state.correlation_id)
