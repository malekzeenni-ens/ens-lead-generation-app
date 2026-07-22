from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.dependencies import Authenticated
from app.api.routes import (
    automation,
    backups,
    campaigns,
    catalogue,
    health,
    leads,
    qualification,
    system,
    templates,
)
from app.core.config import Settings
from app.core.errors import DomainError, ErrorResponse
from app.core.logging import configure_logging
from app.core.secrets import build_secret_store
from app.db.migrations import run_migrations
from app.db.session import Database
from app.domains.automation.manager import CampaignRunManager
from app.domains.automation.providers import MetaInstagramProvider
from app.domains.system.meta import MetaConnectionService

logger = logging.getLogger(__name__)


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", uuid4()))


def _error_response(
    request: Request,
    *,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        code=code,
        message=message,
        details=details or {},
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings()
    runtime_settings.prepare_directories()
    run_migrations(runtime_settings.database_path)
    configure_logging(runtime_settings.log_directory)
    logger.info("Etch N Shine local backend initialization started")
    database = Database(runtime_settings.database_path)
    secret_store = build_secret_store(runtime_settings.database_path.parent)
    meta_connection_service = MetaConnectionService(runtime_settings, secret_store)
    instagram_provider = MetaInstagramProvider(runtime_settings, meta_connection_service)
    campaign_run_manager = CampaignRunManager(
        database, runtime_settings, instagram_provider=instagram_provider
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
        campaign_run_manager.resume_incomplete()
        try:
            yield
        finally:
            logger.info("Etch N Shine local backend shutdown started")
            campaign_run_manager.shutdown()
            meta_connection_service.shutdown()
            database.close()

    app = FastAPI(
        title="Etch 'N' Shine Lead Generation API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        # Registered manually below behind Authenticated so the route/schema map
        # isn't fetchable without the session token.
        openapi_url=None,
    )
    app.state.settings = runtime_settings
    app.state.database = database
    app.state.campaign_run_manager = campaign_run_manager
    app.state.meta_connection_service = meta_connection_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Session-Token", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        incoming = request.headers.get("X-Correlation-ID", "")
        request.state.correlation_id = incoming[:100] if incoming else str(uuid4())
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return _error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        safe_errors = [
            {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return _error_response(
            request,
            code="VALIDATION_ERROR",
            message="The request contains invalid or missing values.",
            status_code=422,
            details={"errors": safe_errors},
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled application error",
            extra={"correlation_id": _correlation_id(request)},
        )
        return _error_response(
            request,
            code="INTERNAL_ERROR",
            message="An unexpected local application error occurred.",
            status_code=500,
        )

    @app.get("/api/v1/openapi.json", include_in_schema=False)
    async def openapi_schema(_: Authenticated) -> dict[str, Any]:
        return app.openapi()

    prefix = "/api/v1"
    app.include_router(health.router, prefix=prefix)
    app.include_router(campaigns.router, prefix=prefix)
    app.include_router(automation.router, prefix=prefix)
    app.include_router(leads.router, prefix=prefix)
    app.include_router(catalogue.router, prefix=prefix)
    app.include_router(qualification.router, prefix=prefix)
    app.include_router(backups.router, prefix=prefix)
    app.include_router(system.router, prefix=prefix)
    app.include_router(templates.router, prefix=prefix)
    return app
