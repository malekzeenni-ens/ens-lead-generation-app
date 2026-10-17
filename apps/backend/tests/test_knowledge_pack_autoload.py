"""The knowledge pack is picked up from disk, so the operator never has to upload it by hand.

Every pack here is synthetic. The real one is gitignored and lives only on the operator's machine.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import AuditEvent, Product
from app.domains.catalogue.pack_autoload import PACK_FILENAME, apply_pack_if_changed, locate_pack
from app.main import create_app
from tests.conftest import SESSION_TOKEN
from tests.test_product_knowledge import FIXTURE, _pack


def _first_handle() -> str:
    with FIXTURE.open(encoding="utf-8") as handle:
        return next(csv.DictReader(handle))["Handle"].strip().casefold()


def _write_pack(path: Path, summary: str = "A slate coaster set for a reception counter.") -> None:
    pack = _pack([{"handle": _first_handle(), "title": "Seeded", "summary": summary}])
    path.write_text(json.dumps(pack), encoding="utf-8")


def _settings(tmp_path: Path, pack_path: Path | None) -> Settings:
    return Settings(
        session_token=SESSION_TOKEN,
        database_path=tmp_path / "data" / "ens-leads.db",
        log_directory=tmp_path / "logs",
        campaign_run_inline=True,
        knowledge_pack_path=pack_path,
    )


def _client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings), headers={"X-Session-Token": SESSION_TOKEN})


def _import_csv(client: TestClient) -> None:
    response = client.post(
        "/api/v1/catalogue/import/shopify",
        json={"filename": "export.csv", "content": FIXTURE.read_text(encoding="utf-8")},
    )
    assert response.status_code == 200, response.text


def _applications(client: TestClient) -> int:
    with client.app.state.database.session_factory() as session:  # type: ignore[attr-defined]
        return int(
            session.query(AuditEvent).filter_by(action="catalogue.enrichment_imported").count()
        )


def _seeded(client: TestClient) -> list[dict[str, Any]]:
    products = client.get("/api/v1/catalogue/products").json()
    return [item for item in products if item["enrichment_source"] == "seed"]


def test_startup_loads_notes_and_a_shopify_import_applies_the_products(tmp_path: Path) -> None:
    pack_path = tmp_path / PACK_FILENAME
    _write_pack(pack_path)
    with _client(_settings(tmp_path, pack_path)) as client:
        notes = client.get("/api/v1/catalogue/knowledge-notes").json()
        assert {note["id"] for note in notes} == {"premises-signage", "bakery-branding"}
        assert _seeded(client) == []

        _import_csv(client)
        seeded = _seeded(client)
        assert [item["shopify_handle"] for item in seeded] == [_first_handle()]
        assert seeded[0]["summary"] == "A slate coaster set for a reception counter."


def test_an_unchanged_pack_and_catalogue_is_not_reapplied(tmp_path: Path) -> None:
    pack_path = tmp_path / PACK_FILENAME
    _write_pack(pack_path)
    settings = _settings(tmp_path, pack_path)
    with _client(settings) as client:
        _import_csv(client)
        applied = _applications(client)
    with _client(settings) as client:
        assert _applications(client) == applied

        _write_pack(pack_path, summary="Reworded by the operator in the pack file.")
        with client.app.state.database.session_factory() as session:  # type: ignore[attr-defined]
            assert apply_pack_if_changed(session, settings, "test") is not None
        assert _applications(client) == applied + 1


def test_reapplying_never_rolls_back_ai_or_hand_written_wording(tmp_path: Path) -> None:
    pack_path = tmp_path / PACK_FILENAME
    _write_pack(pack_path)
    settings = _settings(tmp_path, pack_path)
    with _client(settings) as client:
        _import_csv(client)
        with client.app.state.database.session_factory() as session:  # type: ignore[attr-defined]
            product = session.query(Product).filter_by(shopify_handle=_first_handle()).one()
            product.enrichment_source = "ai"
            product.summary = "Newer wording from an AI run."
            session.commit()

            _write_pack(pack_path, summary="Older wording from the pack.")
            apply_pack_if_changed(session, settings, "test")
            session.refresh(product)
            assert product.enrichment_source == "ai"
            assert product.summary == "Newer wording from an AI run."


def test_a_broken_pack_blocks_neither_startup_nor_a_catalogue_import(
    tmp_path: Path, capfd: Any
) -> None:
    pack_path = tmp_path / PACK_FILENAME
    pack_path.write_text("{ not json", encoding="utf-8")
    with _client(_settings(tmp_path, pack_path)) as client:
        _import_csv(client)
        assert client.get("/api/v1/catalogue/knowledge-notes").json() == []
    # The app's own log handler writes to stderr rather than propagating to caplog.
    assert "was not applied" in capfd.readouterr().err


def test_the_pack_is_found_beside_the_database_when_no_path_is_set(tmp_path: Path) -> None:
    settings = _settings(tmp_path, None)
    settings.prepare_directories()
    beside_database = settings.database_path.parent / PACK_FILENAME
    _write_pack(beside_database)
    assert locate_pack(settings) == beside_database
    assert locate_pack(settings.model_copy(update={"knowledge_pack_auto_import": False})) is None
