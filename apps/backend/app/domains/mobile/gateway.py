"""The phone gateway: a second loopback listener in front of the shared app (ADR-025)."""

from __future__ import annotations

import logging
import socket
import sys
import threading
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import anyio
import uvicorn
from starlette.datastructures import Headers
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.channel import CHANNEL_SCOPE_KEY, DEVICE_SCOPE_KEY, PHONE_CHANNEL, current_actor
from app.core.config import Settings
from app.db.migrations import backend_directory
from app.db.session import Database
from app.domains.mobile.devices import COOKIE_NAME, DeviceRegistry

logger = logging.getLogger(__name__)


# The phone loads only this app's own files and talks only to this origin.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
    "manifest-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'self'"
)
# Windows' registry can map .js to text/plain, which browsers refuse for module scripts.
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
PUBLIC_API_PATHS = frozenset({"/api/v1/mobile/pair"})
_NOT_BUILT_PAGE = (
    "<!doctype html><meta charset=utf-8><title>Etch N Shine</title>"
    "<p>The phone app files are not built on this PC yet. "
    "Run <code>npm run frontend:build</code>, then reload.</p>"
)


def _device_cookie(headers: Headers) -> str | None:
    raw = headers.get("cookie")
    if not raw:
        return None
    cookie: SimpleCookie = SimpleCookie()
    try:
        cookie.load(raw)
    except Exception:
        return None
    morsel = cookie.get(COOKIE_NAME)
    return morsel.value if morsel else None


def resolve_frontend_directory(settings: Settings) -> Path:
    """Where the built frontend is: configured, bundled beside the packaged backend, or the
    repository's `apps/frontend/dist` in development."""
    if settings.mobile_frontend_directory is not None:
        return settings.mobile_frontend_directory
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "frontend"
    return backend_directory().parent / "frontend" / "dist"


def _security_headers(path: str) -> list[tuple[bytes, bytes]]:
    headers = [
        (b"content-security-policy", CONTENT_SECURITY_POLICY.encode()),
        (b"x-frame-options", b"DENY"),
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"no-referrer"),
        (b"strict-transport-security", b"max-age=31536000"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    ]
    if path.startswith("/api/"):
        # Nothing about leads is kept on the phone, not even in the browser's cache.
        headers.append((b"cache-control", b"no-store"))
    return headers


class PhoneGateway:
    """Checks where a request came from, recognises a paired device by its cookie, serves the
    app's files, and hands API requests to the shared app marked as coming from a phone."""

    def __init__(
        self,
        app: ASGIApp,
        database: Database,
        registry: DeviceRegistry,
        settings: Settings,
    ) -> None:
        self.app = app
        self.database = database
        self.registry = registry
        self.port = settings.mobile_gateway_port
        self.frontend_directory = resolve_frontend_directory(settings)
        # Kept in step with the saved Tailscale name by MobileAccessService.
        self.public_host = ""

    @property
    def frontend_ready(self) -> bool:
        return (self.frontend_directory / "index.html").is_file()

    def allowed_hosts(self) -> set[str]:
        hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        if self.public_host:
            hosts |= {self.public_host, f"{self.public_host}:443"}
        return hosts

    def allowed_origins(self) -> set[str]:
        origins = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
        if self.public_host:
            origins.add(f"https://{self.public_host}")
        return origins

    def _device_id(self, cookie_value: str | None) -> str | None:
        if cookie_value is None:
            return None
        with self.database.session_factory() as session:
            device = self.registry.authenticate(session, cookie_value)
            return device.id if device else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            # The shared app's lifespan belongs to the desktop listener; it runs once.
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            return
        path: str = scope["path"]
        send = self._with_headers(send, path)
        headers = Headers(scope=scope)
        # A page on another site that points its own name at 127.0.0.1 (DNS rebinding) still
        # sends its own Host, so it stops here.
        if headers.get("host", "").lower() not in self.allowed_hosts():
            await self._reject(scope, receive, send, "host", 421, "HOST_NOT_ALLOWED")
            return
        if not path.startswith("/api/"):
            await self._serve_file(scope, receive, send)
            return
        if scope["method"] in _UNSAFE_METHODS and (
            headers.get("origin") not in self.allowed_origins()
            or headers.get("x-ens-request") != "1"
        ):
            await self._reject(scope, receive, send, "origin", 403, "ORIGIN_REJECTED")
            return
        cookie_value = _device_cookie(headers)
        device_id = await anyio.to_thread.run_sync(self._device_id, cookie_value)
        if device_id is None and cookie_value is not None:
            logger.info(
                "Phone request with an unknown, expired or revoked device",
                extra={"event": "mobile_request_rejected", "reason": "device"},
            )
        marked = {**scope, CHANNEL_SCOPE_KEY: PHONE_CHANNEL, DEVICE_SCOPE_KEY: device_id}
        token = current_actor.set(f"phone:{device_id}" if device_id else "phone:unpaired")
        try:
            await self.app(marked, receive, send)
        finally:
            current_actor.reset(token)

    def _with_headers(self, send: Send, path: str) -> Send:
        extra = _security_headers(path)

        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {name.lower() for name, _ in message.get("headers", [])}
                message = {
                    **message,
                    "headers": [
                        *message.get("headers", []),
                        *[(name, value) for name, value in extra if name not in present],
                    ],
                }
            await send(message)

        return wrapped

    async def _reject(
        self, scope: Scope, receive: Receive, send: Send, reason: str, status: int, code: str
    ) -> None:
        logger.warning(
            "Phone request rejected",
            extra={"event": "mobile_request_rejected", "reason": reason},
        )
        response = JSONResponse(
            {
                "code": code,
                "message": "This request was refused by the phone gateway.",
                "details": {},
                "correlation_id": "",
            },
            status_code=status,
        )
        await response(scope, receive, send)

    async def _serve_file(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["method"] not in {"GET", "HEAD"}:
            await PlainTextResponse("Method not allowed", status_code=405)(scope, receive, send)
            return
        if not self.frontend_ready:
            await HTMLResponse(_NOT_BUILT_PAGE, status_code=503)(scope, receive, send)
            return
        root = self.frontend_directory.resolve()
        relative = scope["path"].lstrip("/")
        candidate = (root / relative).resolve() if relative else root / "index.html"
        if not candidate.is_relative_to(root):
            await PlainTextResponse("Not found", status_code=404)(scope, receive, send)
            return
        if not candidate.is_file():
            if Path(relative).suffix:
                await PlainTextResponse("Not found", status_code=404)(scope, receive, send)
                return
            # A screen such as /pair: the app's own code handles it.
            candidate = root / "index.html"
        content_type = _CONTENT_TYPES.get(candidate.suffix.lower(), "application/octet-stream")
        # Built assets carry a content hash in their name; the page itself is always fresh.
        cache = (
            "public, max-age=31536000, immutable"
            if candidate.parent.name == "assets"
            else "no-cache"
        )
        response = FileResponse(
            candidate, media_type=content_type, headers={"cache-control": cache}
        )
        await response(scope, receive, send)


class GatewayStartError(Exception):
    pass


class MobileGatewayManager:
    """Starts and stops the gateway listener at runtime, in its own thread and event loop."""

    def __init__(self, gateway: PhoneGateway, settings: Settings) -> None:
        self.gateway = gateway
        self._gateway = gateway
        self._settings = settings
        self._lock = threading.Lock()
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    @property
    def port(self) -> int:
        return self._settings.mobile_gateway_port

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            # Bind here, not in the thread, so a port clash is reported to the caller.
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                listener.bind((self._settings.host, self.port))
            except OSError as error:
                listener.close()
                self.last_error = f"Port {self.port} is already in use on this PC."
                logger.warning(
                    "Phone gateway could not start",
                    extra={"event": "mobile_gateway_start_failed", "port": self.port},
                )
                raise GatewayStartError(self.last_error) from error
            listener.set_inheritable(True)
            config = uvicorn.Config(
                self._gateway,
                lifespan="off",
                access_log=False,
                server_header=False,
                log_config=None,
            )
            server = uvicorn.Server(config)
            thread = threading.Thread(
                target=self._run, args=(server, listener), name="ens-phone-gateway", daemon=True
            )
            self._server = server
            self._thread = thread
            self.last_error = None
            thread.start()
        logger.info(
            "Phone gateway started",
            extra={"event": "mobile_gateway_started", "port": self.port},
        )

    def _run(self, server: uvicorn.Server, listener: socket.socket) -> None:
        try:
            server.run(sockets=[listener])
        except Exception:
            logger.exception("Phone gateway stopped unexpectedly")
        finally:
            listener.close()

    def wait_until_serving(self, timeout: float = 5.0) -> bool:
        """For tests and the runtime switch: whether the listener accepted startup in time."""
        server = self._server
        if server is None:
            return False
        stop = threading.Event()
        for _ in range(int(timeout / 0.05)):
            if server.started:
                return True
            stop.wait(0.05)
        return bool(server.started)

    def stop(self) -> None:
        with self._lock:
            server, thread = self._server, self._thread
            self._server = None
            self._thread = None
        if server is None or thread is None:
            return
        server.should_exit = True
        thread.join(timeout=10)
        logger.info(
            "Phone gateway stopped",
            extra={"event": "mobile_gateway_stopped", "port": self.port},
        )

    def status(self) -> dict[str, Any]:
        return {"running": self.running, "port": self.port, "error": self.last_error}
