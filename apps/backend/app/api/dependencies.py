from __future__ import annotations

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.channel import is_phone, phone_device_id
from app.core.errors import DomainError
from app.db.session import Database


def require_session_token(
    request: Request,
    x_session_token: Annotated[str | None, Header()] = None,
) -> None:
    if is_phone(request):
        # The gateway has already checked the device cookie; it never accepts the session token.
        if phone_device_id(request) is None:
            raise DomainError(
                "PHONE_NOT_PAIRED",
                "This phone is not paired. Pair it from Settings on your PC.",
                status_code=401,
            )
        return
    expected = request.app.state.settings.session_token.get_secret_value()
    if x_session_token is None or not secrets.compare_digest(x_session_token, expected):
        raise DomainError(
            "SESSION_TOKEN_INVALID",
            "The local application session is not authorised.",
            status_code=401,
        )


def require_desktop(request: Request) -> None:
    """Refuse a route on the phone gateway (ADR-025 route policy)."""
    if is_phone(request):
        raise DomainError(
            "DESKTOP_ONLY",
            "Do this on your PC. It isn't available from a phone.",
            status_code=403,
        )


def get_session(request: Request) -> Iterator[Session]:
    database: Database = request.app.state.database
    yield from database.session()


Authenticated = Annotated[None, Depends(require_session_token)]
DesktopOnly = Annotated[None, Depends(require_desktop)]
DatabaseSession = Annotated[Session, Depends(get_session)]
