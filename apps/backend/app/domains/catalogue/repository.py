from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeNote, Product, ProductFamily, ProvenFit


class CatalogueRepository:
    def get(self, session: Session, product_id: str) -> Product | None:
        return session.get(Product, product_id)

    def by_shopify_handle(self, session: Session, handle: str) -> Product | None:
        return session.scalar(select(Product).where(Product.shopify_handle == handle))

    def add(self, session: Session, product: Product) -> None:
        session.add(product)

    def by_ids(self, session: Session, product_ids: list[str]) -> list[Product]:
        if not product_ids:
            return []
        products = {
            product.id: product
            for product in session.scalars(select(Product).where(Product.id.in_(product_ids)))
        }
        return [products[product_id] for product_id in product_ids if product_id in products]

    def get_family(self, session: Session, family_id: str) -> ProductFamily | None:
        return session.get(ProductFamily, family_id)

    def get_family_by_name(self, session: Session, name: str) -> ProductFamily | None:
        return session.scalar(select(ProductFamily).where(ProductFamily.name == name))

    def add_family(self, session: Session, family: ProductFamily) -> None:
        session.add(family)

    def delete_family(self, session: Session, family: ProductFamily) -> None:
        session.delete(family)

    def deactivate_missing_shopify(self, session: Session, seen_handles: set[str]) -> int:
        """Retire Shopify products absent from the newest export.

        Only `shopify_csv` products are touched: a manually created product is the operator's
        own record and never disappears because an export did not mention it.
        """
        statement = select(Product).where(
            Product.source == "shopify_csv",
            Product.active.is_(True),
        )
        retired = 0
        for product in session.scalars(statement):
            if product.shopify_handle not in seen_handles:
                product.active = False
                retired += 1
        return retired

    def last_import_at(self, session: Session) -> datetime | None:
        return session.scalar(select(func.max(Product.last_seen_import_at)))

    def get_note(self, session: Session, note_id: str) -> KnowledgeNote | None:
        return session.get(KnowledgeNote, note_id)

    def add_note(self, session: Session, note: KnowledgeNote) -> None:
        session.add(note)

    def add_fit(self, session: Session, fit: ProvenFit) -> None:
        session.add(fit)

    def get_fit(self, session: Session, fit_id: str) -> ProvenFit | None:
        return session.get(ProvenFit, fit_id)

    def fit_exists_for_lead(self, session: Session, lead_id: str) -> bool:
        return (
            session.scalar(select(ProvenFit.id).where(ProvenFit.lead_id == lead_id)) is not None
        )

    # `list`/`list_families` are defined last: a method literally named `list`
    # shadows the builtin for any annotation appearing later in this class
    # body, so every other method's `list[...]` annotations must come first.
    def list_families(self, session: Session) -> list[ProductFamily]:
        return list(session.scalars(select(ProductFamily).order_by(ProductFamily.name)))

    def list_notes(self, session: Session) -> list[KnowledgeNote]:
        return list(session.scalars(select(KnowledgeNote).order_by(KnowledgeNote.title)))

    def list_fits(self, session: Session, *, segment: str | None = None) -> list[ProvenFit]:
        statement = select(ProvenFit)
        if segment is not None:
            statement = statement.where(ProvenFit.segment == segment)
        return list(session.scalars(statement.order_by(ProvenFit.created_at)))

    def list_pending_enrichment(
        self, session: Session, *, include_stale: bool = False
    ) -> list[Product]:
        """Products the local model may enrich.

        Never-enriched products always qualify. A product whose listing changed since it was
        enriched qualifies only when the operator opts in, because the seed pack and his own
        edits are better than what a small local model produces.
        """
        statement = select(Product).where(Product.active.is_(True))
        candidates = list(session.scalars(statement.order_by(Product.name)))
        pending = [item for item in candidates if not item.enrichment_source]
        if include_stale:
            pending.extend(
                item
                for item in candidates
                if item.enrichment_source in {"seed", "ai"} and item.stale_enrichment
            )
        return pending

    def list(
        self,
        session: Session,
        *,
        query: str | None = None,
        active: bool | None = None,
    ) -> list[Product]:
        statement = select(Product)
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(
                    Product.name.ilike(pattern),
                    Product.category.ilike(pattern),
                    Product.description.ilike(pattern),
                )
            )
        if active is not None:
            statement = statement.where(Product.active.is_(active))
        return list(session.scalars(statement.order_by(Product.name)))
