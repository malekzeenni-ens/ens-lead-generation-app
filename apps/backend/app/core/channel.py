"""Which listener a request arrived on (ADR-025).

The phone gateway marks each request's ASGI scope before handing it to the shared app. The
marks are set only by the gateway, never from request data, so the desktop listener can never
carry them.
"""

from __future__ import annotations

from contextvars import ContextVar

from starlette.requests import HTTPConnection

CHANNEL_SCOPE_KEY = "ens.channel"
DEVICE_SCOPE_KEY = "ens.device_id"
PHONE_CHANNEL = "phone"

# The audit actor for work done while handling this request. Sync endpoints run in a worker
# thread that copies the context, so the value set by the gateway reaches them.
current_actor: ContextVar[str] = ContextVar("ens_actor", default="local_user")


def is_phone(connection: HTTPConnection) -> bool:
    return connection.scope.get(CHANNEL_SCOPE_KEY) == PHONE_CHANNEL


def phone_device_id(connection: HTTPConnection) -> str | None:
    value = connection.scope.get(DEVICE_SCOPE_KEY)
    return value if isinstance(value, str) else None
