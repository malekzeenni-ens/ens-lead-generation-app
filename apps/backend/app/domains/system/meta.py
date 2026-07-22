from __future__ import annotations

import html
import logging
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from app.core.config import Settings
from app.core.errors import DomainError
from app.core.secrets import SecretStore
from app.domains.system.meta_schemas import (
    MetaAccountRead,
    MetaAuthorizationStartRead,
    MetaConfigurationWrite,
    MetaConnectionRead,
)

logger = logging.getLogger(__name__)

_CREDENTIALS_KEY = "meta.credentials"
_CONNECTION_KEY = "meta.connection"
_REQUIRED_SCOPES = (
    "pages_show_list",
    "pages_read_engagement",
    "instagram_basic",
)


@dataclass(frozen=True)
class MetaProviderCredentials:
    app_secret: str
    page_access_token: str
    page_id: str
    page_name: str
    instagram_account_id: str
    instagram_username: str


class _ReusableThreadingHttpServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class MetaConnectionService:
    def __init__(
        self,
        settings: Settings,
        secret_store: SecretStore,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.secret_store = secret_store
        self.client = client or httpx.Client(
            timeout=settings.provider_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )
        self._lock = threading.Lock()
        self._pending_state: str | None = None
        self._pending_expires_at: datetime | None = None
        self._pending_flow_id: str | None = None
        self._last_error: str | None = None
        self._callback_server: ThreadingHTTPServer | None = None
        self._callback_thread: threading.Thread | None = None

    def configure(self, data: MetaConfigurationWrite) -> MetaConnectionRead:
        self.secret_store.set_json(
            _CREDENTIALS_KEY,
            {
                "app_id": data.app_id,
                "app_secret": data.app_secret.get_secret_value(),
            },
        )
        self.secret_store.delete(_CONNECTION_KEY)
        with self._lock:
            self._pending_state = None
            self._pending_expires_at = None
            self._pending_flow_id = None
            self._last_error = None
        return self.status()

    def remove_configuration(self) -> MetaConnectionRead:
        self.secret_store.delete(_CONNECTION_KEY)
        self.secret_store.delete(_CREDENTIALS_KEY)
        with self._lock:
            self._pending_state = None
            self._pending_expires_at = None
            self._pending_flow_id = None
            self._last_error = None
        return self.status()

    def disconnect(self) -> MetaConnectionRead:
        self.secret_store.delete(_CONNECTION_KEY)
        with self._lock:
            self._pending_state = None
            self._pending_expires_at = None
            self._pending_flow_id = None
            self._last_error = None
        return self.status()

    def _credentials(self) -> tuple[str, str]:
        stored = self.secret_store.get_json(_CREDENTIALS_KEY)
        if not stored:
            raise DomainError(
                "META_NOT_CONFIGURED",
                "Save the Meta App ID and App Secret in Settings before connecting Instagram.",
                status_code=409,
            )
        app_id = str(stored.get("app_id", "")).strip()
        app_secret = str(stored.get("app_secret", "")).strip()
        if not app_id or not app_secret:
            raise DomainError(
                "META_CONFIGURATION_INVALID",
                "The protected Meta configuration is incomplete; save it again in Settings.",
                status_code=409,
            )
        return app_id, app_secret

    def status(self) -> MetaConnectionRead:
        configured = self.secret_store.get_json(_CREDENTIALS_KEY) is not None
        connection = self.secret_store.get_json(_CONNECTION_KEY) or {}
        accounts = [
            MetaAccountRead.model_validate(value)
            for value in cast(list[dict[str, object]], connection.get("accounts", []))
            if isinstance(value, dict)
        ]
        selected_page_id = str(connection.get("selected_page_id", ""))
        selected = next(
            (account for account in accounts if account.page_id == selected_page_id), None
        )
        expires_at_value = connection.get("expires_at")
        expires_at = datetime.fromisoformat(str(expires_at_value)) if expires_at_value else None
        expired = bool(expires_at and expires_at <= datetime.now(UTC))
        with self._lock:
            pending = bool(
                self._pending_state
                and self._pending_expires_at
                and self._pending_expires_at > datetime.now(UTC)
            )
            last_error = self._last_error
        if not configured:
            state = "not_configured"
        elif selected is not None and not expired:
            state = "connected"
        elif selected is not None and expired:
            state = "reauthorization_required"
        elif accounts:
            state = "selection_required"
        elif pending:
            state = "authorization_pending"
        elif last_error:
            state = "error"
        else:
            state = "configured"
        return MetaConnectionRead(
            configured=configured,
            connected=selected is not None and not expired,
            status=state,
            callback_url=self.settings.meta_oauth_callback_url,
            graph_version=self.settings.meta_graph_version,
            accounts=accounts,
            selected_account=selected,
            expires_at=expires_at,
            error_message=last_error,
        )

    def start_authorization(self) -> MetaAuthorizationStartRead:
        app_id, _ = self._credentials()
        self._ensure_callback_server()
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        state = secrets.token_urlsafe(32)
        flow_id = secrets.token_hex(6)
        with self._lock:
            self._pending_state = state
            self._pending_expires_at = expires_at
            self._pending_flow_id = flow_id
            self._last_error = None
        logger.info(
            "Meta OAuth authorization started flow=%s callback=%s expires_at=%s",
            flow_id,
            self.settings.meta_oauth_callback_url,
            expires_at.isoformat(),
        )
        query = urlencode(
            {
                "client_id": app_id,
                "redirect_uri": self.settings.meta_oauth_callback_url,
                "state": state,
                "response_type": "code",
                "scope": ",".join(_REQUIRED_SCOPES),
            }
        )
        return MetaAuthorizationStartRead(
            authorization_url=(
                f"https://www.facebook.com/{self.settings.meta_graph_version}/dialog/oauth?{query}"
            ),
            expires_at=expires_at,
        )

    def select_account(self, page_id: str) -> MetaConnectionRead:
        connection = self.secret_store.get_json(_CONNECTION_KEY)
        if connection is None:
            raise DomainError(
                "META_NOT_AUTHORIZED",
                "Connect Meta before selecting an Instagram account.",
                status_code=409,
            )
        accounts = cast(list[dict[str, object]], connection.get("accounts", []))
        if not any(str(account.get("page_id")) == page_id for account in accounts):
            raise DomainError(
                "META_ACCOUNT_NOT_FOUND",
                "The selected Facebook Page and Instagram account are not available.",
                status_code=404,
            )
        connection["selected_page_id"] = page_id
        self.secret_store.set_json(_CONNECTION_KEY, connection)
        return self.status()

    def provider_credentials(self) -> MetaProviderCredentials:
        _, app_secret = self._credentials()
        connection = self.secret_store.get_json(_CONNECTION_KEY) or {}
        expires_at_value = connection.get("expires_at")
        if expires_at_value and datetime.fromisoformat(str(expires_at_value)) <= datetime.now(UTC):
            raise DomainError(
                "META_TOKEN_EXPIRED",
                "The Meta authorization expired. Reconnect Instagram in Settings.",
                status_code=409,
            )
        selected_page_id = str(connection.get("selected_page_id", ""))
        accounts = cast(list[dict[str, object]], connection.get("accounts", []))
        selected = next(
            (account for account in accounts if str(account.get("page_id")) == selected_page_id),
            None,
        )
        if selected is None:
            raise DomainError(
                "META_INSTAGRAM_NOT_CONNECTED",
                "Connect and select an Instagram professional account in Settings.",
                status_code=409,
            )
        return MetaProviderCredentials(
            app_secret=app_secret,
            page_access_token=str(selected["page_access_token"]),
            page_id=str(selected["page_id"]),
            page_name=str(selected["page_name"]),
            instagram_account_id=str(selected["instagram_account_id"]),
            instagram_username=str(selected["instagram_username"]),
        )

    def _ensure_callback_server(self) -> None:
        with self._lock:
            if self._callback_thread and self._callback_thread.is_alive():
                return
            parsed = urlparse(self.settings.meta_oauth_callback_url)
            if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
                raise DomainError(
                    "META_CALLBACK_INVALID",
                    "The Meta callback must use the local loopback address.",
                    status_code=500,
                )
            port = parsed.port
            if port is None:
                raise DomainError(
                    "META_CALLBACK_INVALID",
                    "The Meta callback URL must include a local port.",
                    status_code=500,
                )
            service = self

            class CallbackHandler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:
                    service._serve_callback(self)

                def log_message(self, _format: str, *args: object) -> None:
                    return

            try:
                server = _ReusableThreadingHttpServer(("127.0.0.1", port), CallbackHandler)
            except OSError as exc:
                raise DomainError(
                    "META_CALLBACK_PORT_IN_USE",
                    f"Meta connection needs local callback port {port}, but another program "
                    "is using it.",
                    status_code=409,
                ) from exc
            thread = threading.Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.2},
                daemon=True,
                name="meta-oauth-callback",
            )
            self._callback_server = server
            self._callback_thread = thread
            thread.start()
            logger.info(
                "Meta OAuth callback listener started address=127.0.0.1 port=%s path=%s",
                port,
                parsed.path,
            )

    def _serve_callback(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        expected_path = urlparse(self.settings.meta_oauth_callback_url).path
        if parsed.path != expected_path:
            self._write_callback_response(handler, 404, "Unknown local callback.")
            return
        query = parse_qs(parsed.query)
        error_values = query.get("error_description") or query.get("error")
        error = error_values[0] if error_values else None
        with self._lock:
            flow_id = self._pending_flow_id
        logger.info(
            "Meta OAuth callback received flow=%s code_present=%s state_present=%s "
            "provider_error_present=%s query_fields=%s",
            flow_id or "none",
            bool(query.get("code")),
            bool(query.get("state")),
            bool(error),
            ",".join(sorted(query)) or "none",
        )
        if error:
            safe_error = str(error)[:300]
            with self._lock:
                self._last_error = f"Meta authorization was cancelled or denied: {safe_error}"
                self._pending_state = None
                self._pending_expires_at = None
                self._pending_flow_id = None
            logger.warning("Meta OAuth provider rejected authorization flow=%s", flow_id or "none")
            self._write_callback_response(
                handler,
                400,
                "Meta authorization was cancelled. You can close this tab and try again.",
            )
            return
        code = (query.get("code") or [""])[0]
        state = (query.get("state") or [""])[0]
        try:
            result = self._complete_authorization(str(code), str(state))
            logger.info(
                "Meta OAuth callback completed flow=%s connected=%s accounts=%s",
                flow_id or "none",
                result.connected,
                len(result.accounts),
            )
            message = (
                "Meta is connected. You can close this tab and return to Etch N Shine."
                if result.connected
                else "Authorization succeeded. Return to Etch N Shine and select the "
                "Instagram account to use."
            )
            self._write_callback_response(handler, 200, message)
        except DomainError as exc:
            with self._lock:
                self._last_error = exc.message
            logger.warning(
                "Meta OAuth callback failed flow=%s error_code=%s",
                flow_id or "none",
                exc.code,
            )
            self._write_callback_response(
                handler,
                exc.status_code,
                f"Connection failed: {exc.message} Close this tab and return to the app.",
            )

    @staticmethod
    def _write_callback_response(
        handler: BaseHTTPRequestHandler, status_code: int, message: str
    ) -> None:
        content = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Etch N Shine Meta connection</title></head>"
            "<body style='font-family:system-ui;background:#071824;color:#f5efe4;padding:3rem'>"
            "<main style='max-width:42rem;margin:auto'><h1>Etch N Shine</h1>"
            f"<p>{html.escape(message)}</p></main></body></html>"
        ).encode()
        handler.send_response(status_code)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(content)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header(
            "Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'"
        )
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.end_headers()
        handler.wfile.write(content)

    def _complete_authorization(self, code: str, state: str) -> MetaConnectionRead:
        with self._lock:
            expected_state = self._pending_state
            expires_at = self._pending_expires_at
            flow_id = self._pending_flow_id
            self._pending_state = None
            self._pending_expires_at = None
            self._pending_flow_id = None
        now = datetime.now(UTC)
        if not code:
            validation_failure = "authorization_code_missing"
            message = "Meta returned without an authorization code. Start the connection again."
        elif not state:
            validation_failure = "callback_state_missing"
            message = "Meta returned without the security state. Start the connection again."
        elif not expected_state or not expires_at:
            validation_failure = "pending_request_missing"
            message = "No matching Meta connection request is active. Start it again."
        elif expires_at <= now:
            validation_failure = "pending_request_expired"
            message = "The Meta connection request expired. Start it again."
        elif not secrets.compare_digest(state, expected_state):
            validation_failure = "callback_state_mismatch"
            message = (
                "The Meta callback did not match the active connection request. Start it again."
            )
        else:
            validation_failure = None
            message = ""
        if validation_failure:
            logger.warning(
                "Meta OAuth state validation failed flow=%s reason=%s code_present=%s "
                "state_present=%s pending_state_present=%s expiry_present=%s expired=%s",
                flow_id or "none",
                validation_failure,
                bool(code),
                bool(state),
                bool(expected_state),
                bool(expires_at),
                bool(expires_at and expires_at <= now),
            )
            raise DomainError(
                "META_OAUTH_STATE_INVALID",
                message,
                status_code=400,
            )
        logger.info("Meta OAuth state validated flow=%s", flow_id or "none")
        app_id, app_secret = self._credentials()
        logger.info("Meta OAuth token exchange started flow=%s", flow_id or "none")
        token_data = self._graph_get(
            "oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": self.settings.meta_oauth_callback_url,
                "code": code,
            },
            include_version=False,
        )
        short_token = str(token_data.get("access_token", ""))
        if not short_token:
            raise DomainError(
                "META_TOKEN_EXCHANGE_FAILED",
                "Meta did not return an access token for this authorization.",
                status_code=400,
            )
        try:
            long_data = self._graph_get(
                "oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": short_token,
                },
                include_version=False,
            )
            user_token = str(long_data.get("access_token", short_token))
            token_lifetime = int(long_data.get("expires_in", token_data.get("expires_in", 0)) or 0)
        except DomainError:
            logger.info(
                "Meta long-lived token exchange unavailable; retaining short-lived token flow=%s",
                flow_id or "none",
            )
            user_token = short_token
            token_lifetime = int(token_data.get("expires_in", 0) or 0)
        pages_data = self._graph_get(
            "me/accounts",
            params={
                "fields": "id,name,access_token,instagram_business_account{id,username,name}",
                "limit": "100",
                "access_token": user_token,
            },
        )
        account_values: list[dict[str, object]] = []
        raw_pages = pages_data.get("data", [])
        if isinstance(raw_pages, list):
            for page in raw_pages:
                if not isinstance(page, dict):
                    continue
                instagram = page.get("instagram_business_account")
                if not isinstance(instagram, dict) or not instagram.get("id"):
                    continue
                instagram_id = str(instagram["id"])
                username = str(instagram.get("username", "")).strip()
                if not username:
                    profile = self._graph_get(
                        instagram_id,
                        params={
                            "fields": "id,username,name",
                            "access_token": str(page.get("access_token", "")),
                        },
                    )
                    username = str(profile.get("username", "")).strip()
                page_token = str(page.get("access_token", "")).strip()
                if not username or not page_token:
                    continue
                account_values.append(
                    {
                        "page_id": str(page.get("id", "")),
                        "page_name": str(page.get("name", "Facebook Page")),
                        "page_access_token": page_token,
                        "instagram_account_id": instagram_id,
                        "instagram_username": username,
                    }
                )
        logger.info(
            "Meta Page lookup completed flow=%s pages_returned=%s instagram_accounts_available=%s",
            flow_id or "none",
            len(raw_pages) if isinstance(raw_pages, list) else 0,
            len(account_values),
        )
        if not account_values:
            raise DomainError(
                "META_INSTAGRAM_ACCOUNT_NOT_FOUND",
                "Meta returned no connected Instagram professional account. Check the Page "
                "link and permissions.",
                status_code=409,
            )
        selected_page_id = str(account_values[0]["page_id"]) if len(account_values) == 1 else ""
        self.secret_store.set_json(
            _CONNECTION_KEY,
            {
                "user_access_token": user_token,
                "accounts": account_values,
                "selected_page_id": selected_page_id,
                "expires_at": (
                    (datetime.now(UTC) + timedelta(seconds=token_lifetime)).isoformat()
                    if token_lifetime
                    else None
                ),
            },
        )
        with self._lock:
            self._last_error = None
        logger.info(
            "Meta OAuth connection stored flow=%s accounts=%s automatic_selection=%s",
            flow_id or "none",
            len(account_values),
            bool(selected_page_id),
        )
        return self.status()

    def _graph_get(
        self,
        path: str,
        *,
        params: dict[str, str],
        include_version: bool = True,
    ) -> dict[str, Any]:
        prefix = f"{self.settings.meta_graph_version}/" if include_version else ""
        url = f"https://graph.facebook.com/{prefix}{path.lstrip('/')}"
        try:
            response = self.client.get(url, params=params)
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DomainError(
                "META_CONNECTION_FAILED",
                "Meta could not be reached. Check your internet connection and try again.",
                status_code=502,
            ) from exc
        if response.is_error or not isinstance(payload, dict) or payload.get("error"):
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            error_message = (
                str(error.get("message", "Meta rejected the connection request."))
                if isinstance(error, dict)
                else "Meta rejected the connection request."
            )
            raise DomainError(
                "META_API_ERROR",
                f"Meta rejected the connection: {error_message[:300]}",
                status_code=400,
            )
        return payload

    def shutdown(self) -> None:
        with self._lock:
            server = self._callback_server
            thread = self._callback_thread
            self._callback_server = None
            self._callback_thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        self.client.close()
