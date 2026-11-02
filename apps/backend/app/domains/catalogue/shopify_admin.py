"""Shopify Admin API client for the catalogue sync (ADR-026).

Copied from the Shopify-to-Etsy app (`backend/app/integrations/shopify/admin_api.py`), which
syncs the same store with the same custom app. Kept as close to the source as possible so a fix
in one can be carried to the other. Differences: the product category and SEO description are
also read, five products are fetched per page instead of one, and the CSV, JSON and Globo
writers, which this app does not use, are left out.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

# Each product page asks for up to 25 images and 100 variants, so five products cost about 630
# of Shopify's 1,000-point limit per query.
PRODUCTS_PER_PAGE = 5


@dataclass(frozen=True)
class ShopifyVariant:
    legacy_resource_id: str
    title: str
    sku: str
    price: str
    selected_options: dict[str, str] = field(default_factory=dict)
    image_url: str = ""
    inventory_tracked: bool | None = None
    inventory_quantity: int | None = None


@dataclass(frozen=True)
class ShopifyProduct:
    id: str
    legacy_resource_id: str
    handle: str
    title: str
    status: str
    vendor: str
    product_type: str
    tags: list[str]
    body_html: str
    image_urls: list[str]
    variants: list[ShopifyVariant]
    # Lead generation additions: the Shopify taxonomy path and the SEO description.
    product_category: str = ""
    seo_description: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


class ShopifyClient(Protocol):
    def fetch_products(self) -> list[ShopifyProduct]: ...


class ShopifyAdminApiClient:
    def __init__(
        self,
        *,
        store: str,
        api_version: str,
        access_token: str,
    ) -> None:
        self.store = store
        self.api_version = api_version
        self.access_token = access_token

    def fetch_products(self) -> list[ShopifyProduct]:
        url = f"https://{self.store}/admin/api/{self.api_version}/graphql.json"
        query = """
query ProductCatalogueSync($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      legacyResourceId
      handle
      title
      status
      vendor
      productType
      tags
      descriptionHtml
      category { fullName }
      seo { description }
      images(first: 25) { pageInfo { hasNextPage endCursor } nodes { url } }
      variants(first: 100) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          legacyResourceId
          title
          sku
          price
          inventoryQuantity
          inventoryItem { tracked }
          selectedOptions { name value }
          image { url }
        }
      }
    }
  }
}
"""
        products: list[ShopifyProduct] = []
        after: str | None = None
        seen_cursors: set[str] = set()
        for _ in range(10000):
            payload = post_json(
                url,
                {"X-Shopify-Access-Token": self.access_token},
                {"query": query, "variables": {"first": PRODUCTS_PER_PAGE, "after": after}},
            )
            if payload.get("errors"):
                raise RuntimeError(
                    f"GraphQL errors returned: {json.dumps(payload['errors'])[:500]}"
                )
            page = payload["data"]["products"]
            for node in page["nodes"]:
                self.complete_connection(url, node, "variants")
                self.complete_connection(url, node, "images")
            products.extend(parse_products(page["nodes"]))
            if not page["pageInfo"]["hasNextPage"]:
                return products
            after = advancing_cursor(page["pageInfo"], seen_cursors)
        raise RuntimeError("Shopify product pagination exceeded the safety page limit.")

    def complete_connection(self, url: str, node: dict[str, Any], field: str) -> None:
        connection = node[field]
        if "pageInfo" not in connection:
            raise RuntimeError(f"Shopify omitted {field} pagination; the import was not published.")
        seen: set[str] = set()
        fields = (
            "url"
            if field == "images"
            else "id legacyResourceId title sku price inventoryQuantity inventoryItem { tracked } "
            "selectedOptions { name value } image { url }"
        )
        for _ in range(10000):
            if not connection["pageInfo"]["hasNextPage"]:
                return
            cursor = advancing_cursor(connection["pageInfo"], seen)
            query = (
                "query ProductConnection($id: ID!, $after: String) { product(id: $id) { "
                + field
                + "(first: 100, after: $after) { pageInfo { hasNextPage endCursor } nodes { "
                + fields
                + " } } } }"
            )
            payload = post_json(
                url,
                {"X-Shopify-Access-Token": self.access_token},
                {"query": query, "variables": {"id": node["id"], "after": cursor}},
            )
            if payload.get("errors") or not payload.get("data", {}).get("product"):
                raise RuntimeError(
                    "Shopify returned an incomplete product page; the import was not published."
                )
            next_connection = payload["data"]["product"][field]
            if "pageInfo" not in next_connection:
                raise RuntimeError("Shopify omitted nested pagination metadata.")
            node[field]["nodes"].extend(next_connection["nodes"])
            connection = next_connection
        raise RuntimeError("Shopify nested pagination exceeded the safety page limit.")


def advancing_cursor(page_info: dict[str, Any], seen: set[str]) -> str:
    cursor = str(page_info.get("endCursor") or "")
    if not cursor or cursor in seen:
        raise RuntimeError(
            "Shopify returned a missing or repeated page cursor; the import was not published."
        )
    seen.add(cursor)
    return cursor


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 -- https://<validated store>.myshopify.com only
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    parsed: Any = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- https://<validated store>.myshopify.com only
                parsed = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 502, 503, 504} and attempt < 2:
                time.sleep(min(2**attempt, 2))
                continue
            raise RuntimeError(
                f"Shopify request failed with HTTP {exc.code}; no partial import was published."
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(
                "Shopify could not be reached; no partial import was published."
            ) from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Shopify returned an unexpected response.")
    return parsed


def exchange_client_credentials(store: str, client_id: str, client_secret: str) -> str:
    token_url = f"https://{store}/admin/oauth/access_token"
    form = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 -- https://<validated store>.myshopify.com only
        token_url,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- https://<validated store>.myshopify.com only
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Token exchange failed with HTTP {exc.code}: {body[:500]}") from exc

    access_token = str(payload.get("access_token") or "")
    if not access_token:
        raise RuntimeError("Token exchange did not return an access token.")
    return access_token


def parse_products(nodes: list[dict[str, Any]]) -> list[ShopifyProduct]:
    products: list[ShopifyProduct] = []
    for node in nodes:
        products.append(
            ShopifyProduct(
                id=str(node.get("id") or ""),
                legacy_resource_id=str(node.get("legacyResourceId") or ""),
                handle=str(node.get("handle") or ""),
                title=str(node.get("title") or ""),
                status=str(node.get("status") or ""),
                vendor=str(node.get("vendor") or ""),
                product_type=str(node.get("productType") or ""),
                tags=[str(tag) for tag in node.get("tags", [])],
                body_html=str(node.get("descriptionHtml") or ""),
                image_urls=[
                    str(image.get("url") or "")
                    for image in node.get("images", {}).get("nodes", [])
                    if image.get("url")
                ],
                variants=parse_variants(node.get("variants", {}).get("nodes", [])),
                product_category=str((node.get("category") or {}).get("fullName") or ""),
                seo_description=str((node.get("seo") or {}).get("description") or ""),
            )
        )
    return products


def parse_variants(nodes: list[dict[str, Any]]) -> list[ShopifyVariant]:
    variants: list[ShopifyVariant] = []
    for node in nodes:
        selected_options = {
            str(option.get("name") or ""): str(option.get("value") or "")
            for option in node.get("selectedOptions", [])
            if option.get("name")
        }
        image = node.get("image") or {}
        variants.append(
            ShopifyVariant(
                legacy_resource_id=str(node.get("legacyResourceId") or ""),
                title=str(node.get("title") or ""),
                sku=str(node.get("sku") or ""),
                price=str(node.get("price") or ""),
                selected_options=selected_options,
                image_url=str(image.get("url") or ""),
                inventory_tracked=(node.get("inventoryItem") or {}).get("tracked"),
                inventory_quantity=node.get("inventoryQuantity"),
            )
        )
    return variants
