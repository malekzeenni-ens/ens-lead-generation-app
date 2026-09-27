from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import KnowledgeNote, Product, ProductFamily, ProvenFit
from app.domains.audit.service import record_audit_event
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.campaign_assistant.schemas import ResourceProfile
from app.domains.catalogue import enrichment
from app.domains.catalogue.enrichment_prompt import (
    PRODUCT_ENRICHMENT_PROMPT_VERSION,
    build_enrichment_messages,
    enrichment_schema,
)
from app.domains.catalogue.pack import EnrichmentPack
from app.domains.catalogue.repository import CatalogueRepository
from app.domains.catalogue.schemas import (
    EnrichmentImport,
    EnrichmentImportResult,
    EnrichmentRunRequest,
    EnrichmentRunResult,
    EnrichmentStatus,
    ImportIssue,
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
from app.domains.system.schemas import WorkspaceSettings


class ProductEnrichmentProposal(BaseModel):
    """What the local model returns for one product."""

    target_segments: list[str] = Field(default_factory=list)
    example_use_cases: list[str] = Field(default_factory=list)
    b2b_notes: str = ""
    custom_options: str = ""
    bulk_ready: bool = False


MAX_SHOPIFY_ROWS = 10_000

# Past this, the assistant says once that product details may be out of date.
CATALOGUE_STALE_AFTER_DAYS = 30

# Editing any of these by hand marks the product `manual`: its sales knowledge is then the
# operator's and is never replaced by an import or an enrichment run.
SALES_FIELDS = frozenset(
    {
        "summary",
        "materials",
        "occasions",
        "target_segments",
        "example_use_cases",
        "b2b_relevant",
        "bulk_ready",
        "b2b_notes",
        "custom_options",
    }
)


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
    def __init__(
        self,
        repository: CatalogueRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository or CatalogueRepository()
        self.settings = settings or Settings()

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
        if SALES_FIELDS & set(changes):
            # The operator's own wording outranks the seed pack and the local model, so mark it
            # and never let an import or an enrichment run overwrite it.
            product.enrichment_source = "manual"
            product.enriched_hash = product.source_hash
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
                    ("seo description", "seo_description"),
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
        imported_at = datetime.now(UTC)
        for handle, item in grouped.items():
            title = str(item.get("title", "")).strip()
            if not title:
                skipped += 1
                if len(issues) < 50:
                    issues.append(ImportIssue(handle=handle, message="Product title is missing."))
                continue
            tags: set[str] = item["tags"]
            status = str(item.get("status", "")).casefold()
            published = str(item.get("published", "")).casefold()
            seo_description = str(item.get("seo_description", ""))
            description = _plain_text(str(item.get("description", "")))
            tag_segments = _tag_values(tags, "segment:")
            # Fields the CSV is authoritative for. These are always refreshed.
            csv_owned: dict[str, Any] = {
                "name": title,
                "category": enrichment.derive_category(
                    str(item.get("type", "")), str(item.get("product_category", ""))
                ),
                "description": description,
                "image_reference": str(item.get("image"))[:2048] or None,
                "active": status == "active" if status else published in {"true", "yes", "1"},
                "pricing_guidance": _pricing(item["prices"]),
                "sample_eligible": any(
                    tag.casefold() in {"sample eligible", "sample-eligible"} for tag in tags
                ),
                "source": "shopify_csv",
                "variant_count": int(item["rows"]),
                "product_url": self.settings.product_url(handle),
                "last_seen_import_at": imported_at,
            }
            # Sales knowledge derived from the CSV. Only ever used to fill a product that has
            # never been enriched: the seed pack, the local model and the operator all produce
            # better values than these heuristics, and none of them may be silently replaced.
            derived_segments = sorted(
                set(tag_segments) | set(enrichment.derive_segments_from_tags(tags)),
                key=str.casefold,
            )
            enrichment_defaults: dict[str, Any] = {
                "summary": enrichment.derive_summary(seo_description, description),
                "materials": enrichment.derive_materials(tags, title),
                "target_segments": derived_segments,
                "example_use_cases": _tag_values(tags, "use-case:"),
                "b2b_relevant": enrichment.derive_b2b_relevant(tags, title, tag_segments),
            }
            fresh_hash = enrichment.source_hash(title, seo_description, tags)
            product = self.repository.by_shopify_handle(session, handle)
            if product is None:
                product = Product(
                    shopify_handle=handle,
                    source_hash=fresh_hash,
                    **csv_owned,
                    **enrichment_defaults,
                )
                self.repository.add(session, product)
                created += 1
            else:
                for field, value in csv_owned.items():
                    setattr(product, field, value)
                if not product.enrichment_source:
                    for field, value in enrichment_defaults.items():
                        setattr(product, field, value)
                # Recorded even for enriched products, so a listing that has changed since it
                # was enriched can be reported as stale without overwriting anything.
                product.source_hash = fresh_hash
                updated += 1

        deactivated = self.repository.deactivate_missing_shopify(session, set(grouped))

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
                "deactivated": deactivated,
            },
        )
        session.commit()
        return ShopifyImportResult(
            filename=data.filename,
            rows_read=rows_read,
            products_created=created,
            products_updated=updated,
            products_skipped=skipped,
            products_deactivated=deactivated,
            issues=issues,
        )

    def import_enrichment(
        self,
        session: Session,
        data: EnrichmentImport,
        correlation_id: str,
    ) -> EnrichmentImportResult:
        """Apply the shipped sales-knowledge pack, matched on Shopify handle.

        Idempotent: re-importing the same pack updates in place rather than duplicating.
        Products the operator has edited by hand are left alone, and proven fits arrive
        unconfirmed so nothing unverified can reach a prospect.
        """
        try:
            pack = EnrichmentPack.model_validate(json.loads(data.content))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise DomainError(
                "ENRICHMENT_PACK_INVALID",
                "The enrichment file could not be read.",
                status_code=422,
                details={"validation": str(exc)[:2_000]},
            ) from exc

        issues: list[ImportIssue] = []
        if pack.segments and list(pack.segments) != list(enrichment.SEGMENTS):
            issues.append(
                ImportIssue(
                    handle=None,
                    message=(
                        "The pack's trade list differs from the application's. Segment matching "
                        "may not line up until they agree."
                    ),
                )
            )

        matched = 0
        enriched = 0
        unmatched = 0
        for item in pack.products:
            handle = item.handle.strip().casefold()
            product = self.repository.by_shopify_handle(session, handle)
            if product is None:
                unmatched += 1
                if len(issues) < 50:
                    issues.append(
                        ImportIssue(
                            handle=item.handle,
                            message="No catalogue product with this handle; import the CSV first.",
                        )
                    )
                continue
            matched += 1
            if product.enrichment_source == "manual":
                # The operator's own wording always wins.
                continue
            product.summary = enrichment.strip_prices(item.summary)[:400] or product.summary
            product.materials = item.materials or product.materials
            product.occasions = item.occasions or product.occasions
            product.target_segments = [
                segment for segment in item.target_segments if segment in enrichment.SEGMENT_SET
            ] or product.target_segments
            product.example_use_cases = item.example_use_cases or product.example_use_cases
            product.b2b_notes = enrichment.strip_prices(item.b2b_notes) or product.b2b_notes
            product.custom_options = item.custom_options[:300] or product.custom_options
            product.b2b_relevant = item.b2b_relevant
            product.bulk_ready = item.bulk_ready
            product.product_url = item.url or product.product_url
            # Fields the Product model has no column for still reach the assistant through here.
            product.attributes = {
                key: value
                for key, value in {
                    "listing_status": item.listing_status,
                    "sizes_and_packs": item.sizes_and_packs,
                    "colour_options": item.colour_options,
                    "collections": item.collections,
                    "shopify_updated_at": item.shopify_updated_at,
                }.items()
                if value
            }
            product.enrichment_source = "seed"
            # Staleness means "the listing changed after we enriched it here", so baseline
            # against this database's current fingerprint. The pack's own hash was computed from
            # a later Shopify snapshot than most local exports, so using it would mark almost
            # every seeded product stale the moment it was imported.
            product.enriched_hash = product.source_hash
            if item.source_hash:
                product.attributes = {**product.attributes, "pack_source_hash": item.source_hash}
            enriched += 1

        notes_created = 0
        notes_updated = 0
        for note in pack.knowledge_notes:
            existing = self.repository.get_note(session, note.id)
            if existing is None:
                self.repository.add_note(
                    session,
                    KnowledgeNote(
                        id=note.id,
                        title=note.title,
                        segments=list(note.segments),
                        product_handles=list(note.product_handles),
                        body=enrichment.strip_prices(note.body),
                        source="seed",
                        manual=False,
                    ),
                )
                notes_created += 1
            elif not existing.manual:
                existing.title = note.title
                existing.segments = list(note.segments)
                existing.product_handles = list(note.product_handles)
                existing.body = enrichment.strip_prices(note.body)
                existing.source = "seed"
                notes_updated += 1

        fits_created = 0
        fits_skipped = 0
        known_fits = {
            (fit.segment, fit.client_label) for fit in self.repository.list_fits(session)
        }
        for fit in pack.proven_fits:
            if (fit.segment, fit.client_label) in known_fits:
                fits_skipped += 1
                continue
            allowed = {"confirmed_from_website", "please_confirm"}
            status = fit.status if fit.status in allowed else "please_confirm"
            self.repository.add_fit(
                session,
                ProvenFit(
                    segment=fit.segment,
                    product_handles=list(fit.products),
                    use=enrichment.strip_prices(fit.use),
                    outcome=fit.outcome[:400],
                    client_label=fit.client_label,
                    client_name=fit.client_name,
                    share_client_name=fit.share_client_name,
                    status=status,
                ),
            )
            known_fits.add((fit.segment, fit.client_label))
            fits_created += 1

        record_audit_event(
            session,
            action="catalogue.enrichment_imported",
            entity_type="catalogue",
            entity_id="enrichment_pack",
            correlation_id=correlation_id,
            summary={
                "filename": data.filename,
                "products_matched": matched,
                "products_enriched": enriched,
                "products_unmatched": unmatched,
                "notes_created": notes_created,
                "notes_updated": notes_updated,
                "fits_created": fits_created,
            },
        )
        session.commit()
        status_now = self.enrichment_status(session)
        return EnrichmentImportResult(
            filename=data.filename,
            products_matched=matched,
            products_enriched=enriched,
            products_unmatched=unmatched,
            notes_created=notes_created,
            notes_updated=notes_updated,
            fits_created=fits_created,
            fits_skipped=fits_skipped,
            products_awaiting_enrichment=status_now.products_awaiting_enrichment,
            fits_awaiting_confirmation=status_now.fits_awaiting_confirmation,
            issues=issues,
        )

    def enrichment_status(self, session: Session) -> EnrichmentStatus:
        products = self.repository.list(session, active=True)
        imported_at = self.repository.last_import_at(session)
        stale_catalogue = False
        if imported_at is not None:
            recorded = imported_at if imported_at.tzinfo else imported_at.replace(tzinfo=UTC)
            stale_catalogue = datetime.now(UTC) - recorded > timedelta(
                days=CATALOGUE_STALE_AFTER_DAYS
            )
        fits = self.repository.list_fits(session)
        return EnrichmentStatus(
            catalogue_imported_at=imported_at,
            catalogue_stale=stale_catalogue,
            products_total=len(products),
            products_enriched=sum(1 for item in products if item.enrichment_source),
            products_awaiting_enrichment=sum(
                1 for item in products if not item.enrichment_source
            ),
            products_stale_enrichment=sum(1 for item in products if item.stale_enrichment),
            knowledge_notes=len(self.repository.list_notes(session)),
            proven_fits=len(fits),
            fits_awaiting_confirmation=sum(1 for item in fits if item.status != "confirmed"),
        )

    def update_note(
        self,
        session: Session,
        note_id: str,
        data: KnowledgeNoteUpdate,
        correlation_id: str,
    ) -> KnowledgeNoteRead:
        note = self.repository.get_note(session, note_id)
        if note is None:
            raise DomainError(
                "KNOWLEDGE_NOTE_NOT_FOUND", "Knowledge note not found.", status_code=404
            )
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(note, field, value)
        # Edited by hand, so no automatic refresh may replace it.
        note.manual = True
        note.source = "manual"
        record_audit_event(
            session,
            action="catalogue.knowledge_note_updated",
            entity_type="knowledge_note",
            entity_id=note.id,
            correlation_id=correlation_id,
            summary={"changed_fields": sorted(changes)},
        )
        session.commit()
        session.refresh(note)
        return KnowledgeNoteRead.model_validate(note)

    def update_fit(
        self,
        session: Session,
        fit_id: str,
        data: ProvenFitUpdate,
        correlation_id: str,
    ) -> ProvenFitRead:
        fit = self.repository.get_fit(session, fit_id)
        if fit is None:
            raise DomainError("PROVEN_FIT_NOT_FOUND", "Proven fit not found.", status_code=404)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(fit, field, value)
        record_audit_event(
            session,
            action="catalogue.proven_fit_updated",
            entity_type="proven_fit",
            entity_id=fit.id,
            correlation_id=correlation_id,
            summary={"changed_fields": sorted(changes), "status": fit.status},
        )
        session.commit()
        session.refresh(fit)
        return ProvenFitRead.model_validate(fit)

    def list_notes(self, session: Session) -> list[KnowledgeNoteRead]:
        return [
            KnowledgeNoteRead.model_validate(note)
            for note in self.repository.list_notes(session)
        ]

    def list_fits(
        self, session: Session, *, segment: str | None = None
    ) -> list[ProvenFitRead]:
        return [
            ProvenFitRead.model_validate(fit)
            for fit in self.repository.list_fits(session, segment=segment)
        ]

    def run_enrichment(
        self,
        session: Session,
        data: EnrichmentRunRequest,
        *,
        manager: CampaignAssistantManager,
        workspace_settings: WorkspaceSettings,
        correlation_id: str,
    ) -> EnrichmentRunResult:
        """Fill in sales knowledge for products the shipped pack does not cover.

        Runs in the foreground, one product at a time, because every local generation shares a
        single non-blocking lock: a background run would make the operator's own assistant
        requests fail while it worked. Refused while the engraving software is running, which is
        when the GPU is needed elsewhere.
        """
        if not workspace_settings.local_campaign_assistant_enabled:
            raise DomainError(
                "LOCAL_AI_DISABLED",
                "The local AI assistant is disabled in Settings.",
                status_code=409,
            )
        if manager.resource_profile(
            workspace_settings.protect_design_software_resources
        ) == ResourceProfile.DESIGN_SOFTWARE:
            raise DomainError(
                "ENRICHMENT_PROTECTED_PROFILE",
                "Enrichment is paused while the engraving software is running.",
                status_code=409,
            )

        pending = self.repository.list_pending_enrichment(
            session, include_stale=data.include_stale
        )[: data.limit]
        issues: list[ImportIssue] = []
        enriched = 0
        failed = 0
        for product in pending:
            try:
                result, _profile = manager.generate_structured(
                    build_enrichment_messages(product),
                    schema=enrichment_schema(),
                    model_cls=ProductEnrichmentProposal,
                    error_prefix="PRODUCT_ENRICHMENT",
                    protect_resources=(
                        workspace_settings.protect_design_software_resources
                    ),
                )
            except DomainError as exc:
                failed += 1
                if len(issues) < 50:
                    issues.append(
                        ImportIssue(handle=product.shopify_handle, message=exc.message)
                    )
                continue
            proposal = result.value
            segments = [
                segment
                for segment in proposal.target_segments
                if segment in enrichment.SEGMENT_SET
            ]
            if segments:
                product.target_segments = segments
            if proposal.example_use_cases:
                product.example_use_cases = proposal.example_use_cases[:3]
            notes = enrichment.strip_prices(proposal.b2b_notes)[:600]
            if notes:
                product.b2b_notes = notes
            options = enrichment.strip_prices(proposal.custom_options)[:300]
            if options:
                product.custom_options = options
            product.bulk_ready = proposal.bulk_ready
            product.b2b_relevant = product.b2b_relevant or bool(segments)
            product.enrichment_source = "ai"
            product.enriched_hash = product.source_hash
            enriched += 1

        notes_refreshed = self._refresh_generated_notes(session)

        record_audit_event(
            session,
            action="catalogue.enrichment_run",
            entity_type="catalogue",
            entity_id="enrichment",
            correlation_id=correlation_id,
            summary={
                "considered": len(pending),
                "enriched": enriched,
                "failed": failed,
                "include_stale": data.include_stale,
                "prompt_version": PRODUCT_ENRICHMENT_PROMPT_VERSION,
            },
        )
        session.commit()
        status_now = self.enrichment_status(session)
        return EnrichmentRunResult(
            products_considered=len(pending),
            products_enriched=enriched,
            products_failed=failed,
            notes_refreshed=notes_refreshed,
            products_awaiting_enrichment=status_now.products_awaiting_enrichment,
            issues=issues,
        )

    def _refresh_generated_notes(self, session: Session) -> int:
        """Rebuild the product list on notes this app generated.

        Seed notes are left untouched: their wording is better than anything assembled from
        product summaries, and a note the operator edited is marked manual and never rewritten.
        """
        refreshed = 0
        products = self.repository.list(session, active=True)
        for note in self.repository.list_notes(session):
            if note.manual or note.source != "ai":
                continue
            handles = sorted(
                str(product.shopify_handle)
                for product in products
                if product.shopify_handle
                and set(product.target_segments) & set(note.segments)
            )
            if handles != list(note.product_handles):
                note.product_handles = handles
                refreshed += 1
        return refreshed

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
