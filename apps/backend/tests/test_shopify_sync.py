"""The catalogue sync from Shopify (ADR-026).

A sync must leave the catalogue exactly as importing the same products from a CSV export would,
because both go through the same code. These tests use a fake Shopify; the live check against
the operator's store is recorded in the delivery log.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.catalogue import shopify_admin
from app.domains.catalogue.shopify_admin import ShopifyProduct, ShopifyVariant

FIXTURE = Path(__file__).parent / "fixtures" / "shopify_products_sample.csv"
CONNECTION = {
    "store_domain": "example-store.myshopify.com",
    "client_id": "client-id-for-tests",
    "client_secret": "client-secret-for-tests",
}


def _products_from_csv(text: str) -> list[ShopifyProduct]:
    """The fixture export, as the Admin API would describe the same products."""
    grouped: dict[str, dict[str, Any]] = {}
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        handle = (row.get("Handle") or "").strip()
        if not handle:
            continue
        item = grouped.setdefault(
            handle, {"rows": 0, "prices": [], "fields": {}, "tags": [], "images": []}
        )
        item["rows"] += 1
        for column in (
            "Title",
            "Body (HTML)",
            "Type",
            "Product Category",
            "SEO Description",
            "Status",
            "Published",
        ):
            if row.get(column) and column not in item["fields"]:
                item["fields"][column] = row[column]
        if row.get("Tags") and not item["tags"]:
            item["tags"] = [tag.strip() for tag in row["Tags"].split(",") if tag.strip()]
        if row.get("Image Src"):
            item["images"].append(row["Image Src"])
        item["prices"].append(row.get("Variant Price") or "")
    products = []
    for handle, item in grouped.items():
        fields = item["fields"]
        status = fields.get("Status") or (
            "active" if fields.get("Published", "").casefold() in {"true", "yes", "1"} else "draft"
        )
        products.append(
            ShopifyProduct(
                id=f"gid://shopify/Product/{handle}",
                legacy_resource_id="",
                handle=handle,
                title=fields.get("Title", ""),
                status=status.upper(),
                vendor="",
                product_type=fields.get("Type", ""),
                tags=item["tags"],
                body_html=fields.get("Body (HTML)", ""),
                image_urls=item["images"],
                variants=[
                    ShopifyVariant(legacy_resource_id="", title="", sku="", price=price)
                    for price in item["prices"]
                ],
                product_category=fields.get("Product Category", ""),
                seo_description=fields.get("SEO Description", ""),
            )
        )
    return products


class _FakeShopify:
    def __init__(self, products: list[ShopifyProduct]) -> None:
        self.products = products

    def fetch_products(self) -> list[ShopifyProduct]:
        return self.products


@pytest.fixture
def connected(client: TestClient, app: FastAPI) -> Iterator[list[ShopifyProduct]]:
    assert client.put("/api/v1/system/providers/shopify", json=CONNECTION).status_code == 200
    products = _products_from_csv(FIXTURE.read_text(encoding="utf-8"))
    service = app.state.shopify_connection_service
    original = service.client
    service.client = lambda: _FakeShopify(products)
    yield products
    service.client = original


def _sync(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/catalogue/shopify/sync")
    assert response.status_code == 202, response.text
    job = client.get(f"/api/v1/jobs/{response.json()['id']}").json()
    assert job["status"] == "succeeded", job
    return dict(job["result"])


def _catalogue(client: TestClient) -> dict[str, dict[str, Any]]:
    ignored = {"id", "created_at", "updated_at", "last_seen_import_at"}
    return {
        product["shopify_handle"]: {
            key: value for key, value in product.items() if key not in ignored
        }
        for product in client.get("/api/v1/catalogue/products").json()
    }


def test_a_sync_leaves_the_catalogue_exactly_as_the_csv_import_does(
    client: TestClient, connected: list[ShopifyProduct]
) -> None:
    imported = client.post(
        "/api/v1/catalogue/import/shopify",
        json={"filename": "export.csv", "content": FIXTURE.read_text(encoding="utf-8")},
    )
    assert imported.status_code == 200
    from_csv = _catalogue(client)

    result = _sync(client)
    assert result["products_created"] == 0
    assert result["products_updated"] == len(connected)
    assert result["filename"] == "Shopify (live)"
    assert _catalogue(client) == from_csv


def test_a_first_sync_creates_the_catalogue_and_retires_what_left_shopify(
    client: TestClient, connected: list[ShopifyProduct]
) -> None:
    manual = client.post(
        "/api/v1/catalogue/products",
        json={"name": "Made by hand", "category": "Coasters", "description": "Local only"},
    )
    assert manual.status_code == 201, manual.text
    first = _sync(client)
    assert first["products_created"] == len(connected)

    gone = connected.pop()
    second = _sync(client)
    assert second["products_deactivated"] == 1
    catalogue = _catalogue(client)
    assert catalogue[gone.handle.casefold()]["active"] is False
    # A product made in the app is never retired by Shopify.
    assert any(item["name"] == "Made by hand" and item["active"] for item in catalogue.values())


def test_syncing_needs_a_connection(client: TestClient) -> None:
    response = client.post("/api/v1/catalogue/shopify/sync")
    assert response.status_code == 409
    assert response.json()["code"] == "SHOPIFY_NOT_CONFIGURED"


def test_a_failed_fetch_changes_nothing_and_says_why(client: TestClient, app: FastAPI) -> None:
    client.put("/api/v1/system/providers/shopify", json=CONNECTION)

    class _Unreachable:
        def fetch_products(self) -> list[ShopifyProduct]:
            raise RuntimeError("Shopify could not be reached; no partial import was published.")

    app.state.shopify_connection_service.client = lambda: _Unreachable()
    response = client.post("/api/v1/catalogue/shopify/sync")
    job = client.get(f"/api/v1/jobs/{response.json()['id']}").json()
    assert job["status"] == "failed"
    assert "could not be reached" in job["error_message"]
    assert client.get("/api/v1/catalogue/products").json() == []


def test_the_connection_never_shows_its_secrets(client: TestClient) -> None:
    saved = client.put("/api/v1/system/providers/shopify", json=CONNECTION)
    assert saved.json() == {
        "configured": True,
        "store_domain": "example-store.myshopify.com",
        "api_version": "2026-04",
        "method": "client_credentials",
    }
    status = client.get("/api/v1/system/providers/shopify").text
    assert "client-secret-for-tests" not in status
    assert "client-id-for-tests" not in status
    removed = client.delete("/api/v1/system/providers/shopify").json()
    assert removed["configured"] is False


@pytest.mark.parametrize(
    "body",
    [
        {**CONNECTION, "store_domain": "evil.example.com"},
        {"store_domain": "example-store.myshopify.com", "client_id": "only-an-id"},
    ],
)
def test_the_connection_is_validated(client: TestClient, body: dict[str, str]) -> None:
    assert client.put("/api/v1/system/providers/shopify", json=body).status_code == 422


def test_the_client_reads_the_extra_fields_and_pages_five_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def node(handle: str) -> dict[str, Any]:
        return {
            "id": f"gid://shopify/Product/{handle}",
            "legacyResourceId": "1",
            "handle": handle,
            "title": handle.title(),
            "status": "ACTIVE",
            "vendor": "Etch N Shine",
            "productType": "",
            "tags": ["coaster"],
            "descriptionHtml": "<p>Slate</p>",
            "category": {"fullName": "Home & Garden > Coasters"},
            "seo": {"description": "Engraved slate coasters"},
            "images": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []},
            "variants": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {"legacyResourceId": "2", "title": "Default", "sku": "", "price": "12.00"}
                ],
            },
        }

    pages = [
        {
            "data": {
                "products": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                    "nodes": [node("a")],
                }
            }
        },
        {
            "data": {
                "products": {
                    "pageInfo": {"hasNextPage": False, "endCursor": "c2"},
                    "nodes": [node("b")],
                }
            }
        },
    ]

    def fake_post(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return pages[len(calls) - 1]

    monkeypatch.setattr(shopify_admin, "post_json", fake_post)
    client = shopify_admin.ShopifyAdminApiClient(
        store="example-store.myshopify.com",
        api_version="2026-04",
        access_token="token",  # noqa: S106 -- test value
    )
    products = client.fetch_products()
    assert [product.handle for product in products] == ["a", "b"]
    assert products[0].product_category == "Home & Garden > Coasters"
    assert products[0].seo_description == "Engraved slate coasters"
    assert calls[0]["variables"] == {"first": 5, "after": None}
    assert calls[1]["variables"] == {"first": 5, "after": "c1"}
