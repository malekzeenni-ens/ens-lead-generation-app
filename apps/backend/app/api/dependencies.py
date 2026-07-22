from __future__ import annotations

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.session import Database


def require_session_token(
    request: Request,
    x_session_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = request.app.state.settings.session_token.get_secret_value()
    if x_session_token is None or not secrets.compare_digest(x_session_token, expected):
        raise DomainError(
            "SESSION_TOKEN_INVALID",
            "The local application session is not authorised.",
            status_code=401,
        )


def get_session(request: Request) -> Iterator[Session]:
    database: Database = request.app.state.database
    yield from database.session()


Authenticated = Annotated[None, Depends(require_session_token)]
DatabaseSession = Annotated[Session, Depends(get_session)]
