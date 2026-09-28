"""Apply the private product knowledge pack from disk, so it never has to be uploaded by hand.

The pack is gitignored (ADR-021), so it lives on the operator's machine: beside the database in
an installed app, or at the repository root in a development checkout. It matches products on
Shopify handle, so it is applied at startup and again after every Shopify import, but only when
the file or the catalogue has changed since the last application. A broken or missing pack is
logged and skipped; it never stops the app starting or a catalogue import finishing.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import AppSetting
from app.domains.catalogue.schemas import EnrichmentImport, EnrichmentImportResult
from app.domains.catalogue.service import CatalogueService

logger = logging.getLogger(__name__)

PACK_FILENAME = "product_enrichment.json"
_STATE_KEY = "knowledge_pack_auto_import"
# app/domains/catalogue/pack_autoload.py -> repository root. Absent in an installed build.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]


def locate_pack(settings: Settings) -> Path | None:
    if not settings.knowledge_pack_auto_import:
        return None
    if settings.knowledge_pack_path is not None:
        return settings.knowledge_pack_path if settings.knowledge_pack_path.is_file() else None
    for candidate in (
        settings.database_path.parent / PACK_FILENAME,
        _REPOSITORY_ROOT / PACK_FILENAME,
    ):
        if candidate.is_file():
            return candidate
    return None


def apply_pack_if_changed(
    session: Session,
    settings: Settings,
    correlation_id: str,
    service: CatalogueService | None = None,
) -> EnrichmentImportResult | None:
    """Apply the pack when it or the catalogue changed since last time. Never raises."""
    path = locate_pack(settings)
    if path is None:
        return None
    catalogue = service or CatalogueService()
    try:
        content = path.read_text(encoding="utf-8-sig")
        catalogue_imported_at = catalogue.repository.last_import_at(session)
        fingerprint = {
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "catalogue_imported_at": (
                catalogue_imported_at.isoformat() if catalogue_imported_at else None
            ),
        }
        state = session.get(AppSetting, _STATE_KEY)
        if state is not None and state.value == fingerprint:
            return None
        result = catalogue.import_enrichment(
            session,
            EnrichmentImport(filename=path.name, content=content),
            correlation_id,
            keep_ai_wording=True,
        )
        if state is None:
            session.add(AppSetting(key=_STATE_KEY, value=fingerprint))
        else:
            state.value = fingerprint
        session.commit()
    except (OSError, UnicodeDecodeError, ValidationError, DomainError) as exc:
        session.rollback()
        logger.warning("Product knowledge pack at %s was not applied: %s", path, exc)
        return None
    logger.info(
        "Product knowledge pack applied from %s matched=%s enriched=%s unmatched=%s notes=%s "
        "fits=%s",
        path,
        result.products_matched,
        result.products_enriched,
        result.products_unmatched,
        result.notes_created + result.notes_updated,
        result.fits_created,
    )
    return result
