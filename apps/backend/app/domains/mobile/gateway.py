"""The phone gateway: a second loopback listener in front of the shared app (ADR-025)."""

from __future__ import annotations

import logging
import socket
import threading
from typing import Any

import uvicorn
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.channel import CHANNEL_SCOPE_KEY, PHONE_CHANNEL
from app.core.config import Settings

logger = logging.getLogger(__name__)


class PhoneGateway:
    """Marks every request as coming from a phone, then hands it to the shared app."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

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
        await self.app({**scope, CHANNEL_SCOPE_KEY: PHONE_CHANNEL}, receive, send)


class GatewayStartError(Exception):
    pass


class MobileGatewayManager:
    """Starts and stops the gateway listener at runtime, in its own thread and event loop."""

    def __init__(self, gateway: ASGIApp, settings: Settings) -> None:
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
