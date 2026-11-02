"""The Shopify connection for the catalogue sync (ADR-026).

The same custom app and credential rules as the Shopify-to-Etsy app's
`build_shopify_client_from_env`: an access token if one is stored, otherwise the client ID and
secret exchanged for one. The values live in the DPAPI vault, never in a file or the database.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.core.errors import DomainError
from app.core.secrets import SecretStore
from app.domains.catalogue.shopify_admin import (
    ShopifyAdminApiClient,
    exchange_client_credentials,
    post_json,
)

logger = logging.getLogger(__name__)

_KEY = "shopify_credentials"
# The Admin API version the Shopify-to-Etsy app uses by default.
DEFAULT_API_VERSION = "2026-04"
_STORE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}\.myshopify\.com$")


def _store_domain(value: str) -> str:
    value = value.strip().lower().removeprefix("https://").rstrip("/")
    if not _STORE.fullmatch(value):
        raise ValueError(
            "The store must be its myshopify.com address, e.g. your-store.myshopify.com"
        )
    return value


class ShopifyConnectionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_domain: str = Field(min_length=3, max_length=100)
    api_version: str = Field(default=DEFAULT_API_VERSION, pattern=r"^\d{4}-\d{2}$")
    client_id: str | None = Field(default=None, max_length=200)
    client_secret: SecretStr | None = Field(default=None, max_length=300)
    access_token: SecretStr | None = Field(default=None, max_length=300)

    _check_store = field_validator("store_domain")(_store_domain)

    @model_validator(mode="after")
    def require_credentials(self) -> ShopifyConnectionWrite:
        has_token = bool(self.access_token and self.access_token.get_secret_value().strip())
        has_client = bool(
            self.client_id
            and self.client_id.strip()
            and self.client_secret
            and self.client_secret.get_secret_value().strip()
        )
        if not (has_token or has_client):
            raise ValueError("Provide the client ID and secret, or an access token")
        return self


class ShopifyConnectionRead(BaseModel):
    configured: bool
    store_domain: str | None
    api_version: str | None
    method: str | None


class ShopifyTestResult(BaseModel):
    shop_name: str
    store_domain: str


def sync_error(error: Exception) -> DomainError:
    """The copied client raises RuntimeError with safe, specific messages; keep them."""
    return DomainError(
        "SHOPIFY_SYNC_FAILED",
        f"Shopify sync didn't complete: {str(error)[:300]} Nothing in the catalogue was changed.",
        status_code=502,
    )


class ShopifyConnectionService:
    def __init__(self, secret_store: SecretStore) -> None:
        self.secret_store = secret_store

    def status(self) -> ShopifyConnectionRead:
        stored = self.secret_store.get_json(_KEY)
        if not stored:
            return ShopifyConnectionRead(
                configured=False, store_domain=None, api_version=None, method=None
            )
        return ShopifyConnectionRead(
            configured=True,
            store_domain=str(stored.get("store_domain") or ""),
            api_version=str(stored.get("api_version") or DEFAULT_API_VERSION),
            method="access_token" if stored.get("access_token") else "client_credentials",
        )

    def configure(self, data: ShopifyConnectionWrite) -> ShopifyConnectionRead:
        self.secret_store.set_json(
            _KEY,
            {
                "store_domain": data.store_domain,
                "api_version": data.api_version,
                "client_id": (data.client_id or "").strip(),
                "client_secret": data.client_secret.get_secret_value().strip()
                if data.client_secret
                else "",
                "access_token": data.access_token.get_secret_value().strip()
                if data.access_token
                else "",
            },
        )
        logger.info("Shopify connection saved", extra={"event": "shopify_connection_saved"})
        return self.status()

    def remove(self) -> ShopifyConnectionRead:
        self.secret_store.delete(_KEY)
        logger.info("Shopify connection removed", extra={"event": "shopify_connection_removed"})
        return self.status()

    def client(self) -> ShopifyAdminApiClient:
        stored = self.secret_store.get_json(_KEY)
        if not stored:
            raise DomainError(
                "SHOPIFY_NOT_CONFIGURED",
                "Connect Shopify in Settings → Connections first.",
                status_code=409,
            )
        store = str(stored["store_domain"])
        try:
            token = str(stored.get("access_token") or "") or exchange_client_credentials(
                store=store,
                client_id=str(stored.get("client_id") or ""),
                client_secret=str(stored.get("client_secret") or ""),
            )
        except RuntimeError as error:
            raise sync_error(error) from error
        return ShopifyAdminApiClient(
            store=store,
            api_version=str(stored.get("api_version") or DEFAULT_API_VERSION),
            access_token=token,
        )

    def test(self) -> ShopifyTestResult:
        client = self.client()
        try:
            payload = post_json(
                f"https://{client.store}/admin/api/{client.api_version}/graphql.json",
                {"X-Shopify-Access-Token": client.access_token},
                {"query": "{ shop { name } }"},
            )
        except RuntimeError as error:
            raise sync_error(error) from error
        shop = (payload.get("data") or {}).get("shop") or {}
        if payload.get("errors") or not shop.get("name"):
            raise DomainError(
                "SHOPIFY_TEST_FAILED",
                "Shopify answered, but not with this store's details. Check the access scopes.",
                status_code=502,
            )
        return ShopifyTestResult(shop_name=str(shop["name"]), store_domain=client.store)
