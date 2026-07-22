from __future__ import annotations

import csv
import io
from collections import defaultdict
from contextlib import suppress
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import Product, ProductFamily
from app.domains.audit.service import record_audit_event
from app.domains.catalogue.repository import CatalogueRepository
from app.domains.catalogue.schemas import (
    ImportIssue,
    ProductCreate,
    ProductFamilyCreate,
    ProductFamilyRead,
    ProductFamilyUpdate,
    ProductRead,
    ProductUpdate,
    ShopifyCsvImport,
    ShopifyImportResult,
)

MAX_SHOPIFY_ROWS = 10_000


class _PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


def _plain_text(value: str) -> str:
    parser = _PlainTextParser()
    parser.feed(value)
    return " ".join(parser.parts)[:20_000]


def _normalise_row(row: dict[str | None, str | None]) -> dict[str, str]:
    return {
        str(key).lstrip("\ufeff").strip().casefold(): (value or "").strip()
        for key, value in row.items()
        if key is not None
    }


def _tag_values(tags: set[str], prefix: str) -> list[str]:
    prefix_key = prefix.casefold()
    values = [tag.split(":", 1)[1].strip() for tag in tags if tag.casefold().startswith(prefix_key)]
    return sorted({value for value in values if value}, key=str.casefold)


def _pricing(prices: set[Decimal]) -> str | None:
    if not prices:
        return None
    low = min(prices)
    high = max(prices)
    if low == high:
        return f"£{low:.2f}"
    return f"£{low:.2f} to £{high:.2f}"


class CatalogueService:
    def __init__(self, repository: CatalogueRepository | None = None) -> None:
        self.repository = repository or CatalogueRepository()

    def create(self, session: Session, data: ProductCreate, correlation_id: str) -> ProductRead:
        product = Product(**data.model_dump(), source="manual", variant_count=1)
        self.repository.add(session, product)
        session.flush()
        record_audit_event(
            session,
            action="product.created",
            entity_type="product",
            entity_id=product.id,
            correlation_id=correlation_id,
            summary={"name": product.name, "category": product.category},
        )
        session.commit()
        return ProductRead.model_validate(product)

    def update(
        self,
        session: Session,
        product_id: str,
        data: ProductUpdate,
        correlation_id: str,
    ) -> ProductRead:
        product = self.repository.get(session, product_id)
        if product is None:
            raise DomainError("PRODUCT_NOT_FOUND", "Product not found.", status_code=404)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(product, field, value)
        record_audit_event(
            session,
            action="product.updated",
            entity_type="product",
            entity_id=product.id,
            correlation_id=correlation_id,
            summary={"changed_fields": sorted(changes)},
        )
        session.commit()
        session.refresh(product)
        return ProductRead.model_validate(product)

    def _family_to_read(self, session: Session, family: ProductFamily) -> ProductFamilyRead:
        products = self.repository.by_ids(session, family.product_ids)
        return ProductFamilyRead(
            id=family.id,
            name=family.name,
            description=family.description,
            products=[ProductRead.model_validate(product) for product in products],
            created_at=family.created_at,
            updated_at=family.updated_at,
        )

    def create_family(
        self, session: Session, data: ProductFamilyCreate, correlation_id: str
    ) -> ProductFamilyRead:
        if self.repository.get_family_by_name(session, data.name) is not None:
            raise DomainError(
                "PRODUCT_FAMILY_NAME_EXISTS",
                "A product family with this name already exists.",
                status_code=409,
            )
        matched = self.repository.by_ids(session, data.product_ids)
        if len(matched) != len(set(data.product_ids)):
            raise DomainError(
                "PRODUCT_FAMILY_UNKNOWN_PRODUCT",
                "One or more selected products could not be found.",
                status_code=422,
            )
        family = ProductFamily(
            name=data.name,
            description=data.description,
            product_ids=data.product_ids,
        )
        self.repository.add_family(session, family)
        session.flush()
        record_audit_event(
            session,
            action="product_family.created",
            entity_type="product_family",
            entity_id=family.id,
            correlation_id=correlation_id,
            summary={"name": family.name, "product_count": len(family.product_ids)},
        )
        session.commit()
        return self._family_to_read(session, family)

    def update_family(
        self,
        session: Session,
        family_id: str,
        data: ProductFamilyUpdate,
        correlation_id: str,
    ) -> ProductFamilyRead:
        family = self.repository.get_family(session, family_id)
        if family is None:
            raise DomainError(
                "PRODUCT_FAMILY_NOT_FOUND", "Product family not found.", status_code=404
            )
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] != family.name:
            existing = self.repository.get_family_by_name(session, str(changes["name"]))
            if existing is not None:
                raise DomainError(
                    "PRODUCT_FAMILY_NAME_EXISTS",
                    "A product family with this name already exists.",
                    status_code=409,
                )
        if "product_ids" in changes:
            matched = self.repository.by_ids(session, changes["product_ids"])
            if len(matched) != len(set(changes["product_ids"])):
                raise DomainError(
                    "PRODUCT_FAMILY_UNKNOWN_PRODUCT",
                    "One or more selected products could not be found.",
                    status_code=422,
                )
        for field, value in changes.items():
            setattr(family, field, value)
        record_audit_event(
            session,
            action="product_family.updated",
            entity_type="product_family",
            entity_id=family.id,
            correlation_id=correlation_id,
            summary={"changed_fields": sorted(changes)},
        )
        session.commit()
        session.refresh(family)
        return self._family_to_read(session, family)

    def delete_family(self, session: Session, family_id: str, correlation_id: str) -> None:
        family = self.repository.get_family(session, family_id)
        if family is None:
            raise DomainError(
                "PRODUCT_FAMILY_NOT_FOUND", "Product family not found.", status_code=404
            )
        record_audit_event(
            session,
            action="product_family.deleted",
            entity_type="product_family",
            entity_id=family.id,
            correlation_id=correlation_id,
            summary={"name": family.name},
        )
        self.repository.delete_family(session, family)
        session.commit()

    def import_shopify(
        self,
        session: Session,
        data: ShopifyCsvImport,
        correlation_id: str,
    ) -> ShopifyImportResult:
        try:
            reader = csv.DictReader(io.StringIO(data.content.lstrip("\ufeff")))
        except csv.Error as exc:
            raise DomainError(
                "SHOPIFY_CSV_INVALID", "The CSV could not be read.", status_code=422
            ) from exc
        headers = {str(header).strip().casefold() for header in (reader.fieldnames or [])}
        required = {"handle", "title"}
        if not required.issubset(headers):
            raise DomainError(
                "SHOPIFY_CSV_HEADERS_INVALID",
                "Shopify CSV headers must include Handle and Title.",
                status_code=422,
                details={"missing_headers": sorted(required - headers)},
            )

        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"rows": 0, "tags": set(), "prices": set()}
        )
        rows_read = 0
        try:
            for raw_row in reader:
                rows_read += 1
                if rows_read > MAX_SHOPIFY_ROWS:
                    raise DomainError(
                        "SHOPIFY_CSV_TOO_MANY_ROWS",
                        f"Shopify CSV files are limited to {MAX_SHOPIFY_ROWS:,} rows.",
                        status_code=422,
                    )
                row = _normalise_row(raw_row)
                handle = row.get("handle", "").strip().casefold()
                if not handle:
                    continue
                item = grouped[handle]
                item["rows"] += 1
                for source, target in (
                    ("title", "title"),
                    ("body (html)", "description"),
                    ("type", "type"),
                    ("product category", "product_category"),
                    ("image src", "image"),
                    ("status", "status"),
                    ("published", "published"),
                ):
                    if row.get(source) and not item.get(target):
                        item[target] = row[source]
                item["tags"].update(
                    tag.strip() for tag in row.get("tags", "").split(",") if tag.strip()
                )
                price = row.get("variant price", "")
                if price:
                    with suppress(InvalidOperation):
                        item["prices"].add(Decimal(price))
        except csv.Error as exc:
            raise DomainError(
                "SHOPIFY_CSV_INVALID", "The CSV contains invalid row data.", status_code=422
            ) from exc

        created = 0
        updated = 0
        skipped = 0
        issues: list[ImportIssue] = []
        for handle, item in grouped.items():
            title = str(item.get("title", "")).strip()
            if not title:
                skipped += 1
                if len(issues) < 50:
                    issues.append(ImportIssue(handle=handle, message="Product title is missing."))
                continue
            tags: set[str] = item["tags"]
            category = str(item.get("type") or item.get("product_category") or "Uncategorised")
            status = str(item.get("status", "")).casefold()
            published = str(item.get("published", "")).casefold()
            values = {
                "name": title,
                "category": category[:200],
                "description": _plain_text(str(item.get("description", ""))),
                "target_segments": _tag_values(tags, "segment:"),
                "example_use_cases": _tag_values(tags, "use-case:"),
                "image_reference": str(item.get("image"))[:2048] or None,
                "active": status == "active" if status else published in {"true", "yes", "1"},
                "pricing_guidance": _pricing(item["prices"]),
                "sample_eligible": any(
                    tag.casefold() in {"sample eligible", "sample-eligible"} for tag in tags
                ),
                "source": "shopify_csv",
                "variant_count": int(item["rows"]),
            }
            product = self.repository.by_shopify_handle(session, handle)
            if product is None:
                product = Product(shopify_handle=handle, **values)
                self.repository.add(session, product)
                created += 1
            else:
                for field, value in values.items():
                    setattr(product, field, value)
                updated += 1

        record_audit_event(
            session,
            action="catalogue.shopify_csv_imported",
            entity_type="catalogue",
            entity_id="shopify_csv",
            correlation_id=correlation_id,
            summary={
                "filename": data.filename,
                "rows_read": rows_read,
                "created": created,
                "updated": updated,
                "skipped": skipped,
            },
        )
        session.commit()
        return ShopifyImportResult(
            filename=data.filename,
            rows_read=rows_read,
            products_created=created,
            products_updated=updated,
            products_skipped=skipped,
            issues=issues,
        )

    # `list`/`list_families` are defined last: a class method literally named
    # `list` shadows the builtin for any annotation appearing later in this
    # class body, so every other method's `list[...]` annotations must come
    # before these two.
    def list_families(self, session: Session) -> list[ProductFamilyRead]:
        return [
            self._family_to_read(session, family)
            for family in self.repository.list_families(session)
        ]

    def list(
        self, session: Session, *, query: str | None = None, active: bool | None = None
    ) -> list[ProductRead]:
        return [
            ProductRead.model_validate(product)
            for product in self.repository.list(session, query=query, active=active)
        ]
