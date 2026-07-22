from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Product, ProductFamily


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

    # `list`/`list_families` are defined last: a method literally named `list`
    # shadows the builtin for any annotation appearing later in this class
    # body, so every other method's `list[...]` annotations must come first.
    def list_families(self, session: Session) -> list[ProductFamily]:
        return list(session.scalars(select(ProductFamily).order_by(ProductFamily.name)))

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
