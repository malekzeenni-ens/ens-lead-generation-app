from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import Authenticated, DatabaseSession
from app.domains.catalogue.schemas import (
    ProductCreate,
    ProductFamilyCreate,
    ProductFamilyRead,
    ProductFamilyUpdate,
    ProductRead,
    ProductUpdate,
    ShopifyCsvImport,
    ShopifyImportResult,
)
from app.domains.catalogue.service import CatalogueService

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
