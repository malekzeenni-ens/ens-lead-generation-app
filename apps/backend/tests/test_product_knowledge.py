"""The sales-knowledge layer, and the two rules it must never break.

Pricing never reaches a model or an email, and an unconfirmed job never carries its client's
name. Both are enforced in code rather than asked for in a prompt, so both are tested here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

FIXTURE = Path(__file__).parent / "fixtures" / "shopify_products_sample.csv"


def _import_csv(client: TestClient) -> None:
    response = client.post(
        "/api/v1/catalogue/import/shopify",
        json={"filename": "export.csv", "content": FIXTURE.read_text(encoding="utf-8")},
    )
    assert response.status_code == 200, response.text


def _pack(products: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "segments": [
            "Gyms, studios and sports clubs",
            "Salons, barbers and beauty",
            "Cafés, restaurants and takeaways",
            "Bakeries and cake makers",
            "Clinics, dental and healthcare",
            "Offices and corporate teams",
            "Estate agents and property",
            "Event planners and venues",
            "Wedding planners and venues",
            "Schools and nurseries",
            "Independent shops and market stalls",
            "Hotels, B&Bs and holiday lets",
            "Mosques, charities and community groups",
            "Pet groomers, vets and kennels",
            "Kitchen, interior and trade businesses",
            "Freelancers, sole traders and creators",
        ],
        "products": products,
        "knowledge_notes": [
            {
                "id": "premises-signage",
                "title": "Premises signage for gyms and clinics",
                "segments": ["Gyms, studios and sports clubs"],
                "product_handles": [],
                "body": (
                    "Who buys: owners fitting out a premises. Typical order: a set of door signs "
                    "plus one entrance sign. Pricing is always quoted by Malek."
                ),
            },
            {
                "id": "bakery-branding",
                "title": "Branding for bakeries",
                "segments": ["Bakeries and cake makers"],
                "product_handles": [],
                "body": "Who buys: cake makers wanting branded toppers and tags.",
            },
        ],
        "proven_fits": [
            {
                "segment": "Gyms, studios and sports clubs",
                "client_label": "a new grappling gym in Bedford",
                "client_name": "Example Grappling Club",
                "share_client_name": False,
                "products": [],
                "use": "Full set of black acrylic directional signs.",
                "outcome": "Delivered.",
                "status": "please_confirm",
            }
        ],
    }


def _import_pack(client: TestClient, pack: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        "/api/v1/catalogue/import/enrichment",
        json={"filename": "product_enrichment.json", "content": json.dumps(pack)},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def _seeded_pack_for(client: TestClient) -> dict[str, Any]:
    handle = str(client.get("/api/v1/catalogue/products").json()[0]["shopify_handle"])
    return _pack(
        [
            {
                "handle": handle,
                "title": "Seeded product",
                "summary": "A slate coaster set for a counter. Only £3.50 each.",
                "materials": ["slate"],
                "occasions": ["Corporate gifting"],
                "b2b_relevant": True,
                "bulk_ready": True,
                "target_segments": ["Gyms, studios and sports clubs", "Not A Real Trade"],
                "example_use_cases": ["Reception coasters"],
                "b2b_notes": "Runs of 50 upwards. Save 20% off bigger orders.",
                "custom_options": "logo, names",
                "url": "https://etchnshine.com/products/x",
                "sizes_and_packs": None,
                "colour_options": None,
                "source_hash": "abc123",
            }
        ]
    )


def test_the_pack_applies_and_strips_any_price_it_contains(client: TestClient) -> None:
    _import_csv(client)
    result = _import_pack(client, _seeded_pack_for(client))
    assert result["products_enriched"] == 1

    product = next(
        item
        for item in client.get("/api/v1/catalogue/products").json()
        if item["enrichment_source"] == "seed"
    )
    assert product["bulk_ready"] is True
    assert product["custom_options"] == "logo, names"
    # The pack is meant to be price-free; if one slips in it is removed rather than trusted.
    assert "£" not in str(product["summary"])
    assert "%" not in str(product["b2b_notes"])
    # An unknown trade is dropped rather than stored.
    assert product["target_segments"] == ["Gyms, studios and sports clubs"]


def test_the_pack_import_is_idempotent(client: TestClient) -> None:
    _import_csv(client)
    pack = _seeded_pack_for(client)
    first = _import_pack(client, pack)
    second = _import_pack(client, pack)

    assert first["notes_created"] == 2
    assert second["notes_created"] == 0
    assert second["notes_updated"] == 2
    assert second["fits_created"] == 0
    assert second["fits_skipped"] == 1
    assert len(client.get("/api/v1/catalogue/knowledge-notes").json()) == 2
    assert len(client.get("/api/v1/catalogue/proven-fits").json()) == 1


def test_a_product_with_no_matching_handle_is_reported_not_created(client: TestClient) -> None:
    _import_csv(client)
    before = len(client.get("/api/v1/catalogue/products").json())
    pack = _pack([{"handle": "not-a-real-handle", "title": "Ghost"}])
    result = _import_pack(client, pack)

    assert result["products_unmatched"] == 1
    assert result["products_matched"] == 0
    assert any("import the CSV first" in issue["message"] for issue in result["issues"])
    assert len(client.get("/api/v1/catalogue/products").json()) == before


def test_a_pack_that_cannot_be_read_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/v1/catalogue/import/enrichment",
        json={"filename": "broken.json", "content": "{not json"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "ENRICHMENT_PACK_INVALID"


def test_an_edited_knowledge_note_is_never_overwritten_by_a_reimport(
    client: TestClient,
) -> None:
    _import_csv(client)
    pack = _seeded_pack_for(client)
    _import_pack(client, pack)

    edited = client.patch(
        "/api/v1/catalogue/knowledge-notes/premises-signage",
        json={"body": "My own note about gyms."},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["manual"] is True

    _import_pack(client, pack)
    notes = {
        item["id"]: item for item in client.get("/api/v1/catalogue/knowledge-notes").json()
    }
    assert notes["premises-signage"]["body"] == "My own note about gyms."


def test_the_assistant_snapshot_carries_product_knowledge_and_never_a_price(
    client: TestClient,
) -> None:
    from app.core.config import Settings
    from app.domains.assistant.context import build_app_context
    from app.domains.assistant.schemas import AssistantContextSelection

    _import_csv(client)
    _import_pack(client, _seeded_pack_for(client))

    database = client.app.state.database  # type: ignore[attr-defined]
    with database.session_factory() as session:
        snapshot = build_app_context(
            session,
            user_request="which products suit a gym?",
            runtime_settings=Settings(session_token="x" * 32),
            instagram_connected=False,
            selection=AssistantContextSelection(kind="workspace"),
        )

    serialised = json.dumps(snapshot, ensure_ascii=False)
    assert "pricing_guidance" not in serialised
    assert "£" not in serialised
    assert snapshot["catalogue"]["products"]
    assert "product_knowledge" in snapshot


def test_an_unconfirmed_fit_never_exposes_the_client_name_to_the_model(
    client: TestClient,
) -> None:
    from app.core.config import Settings
    from app.domains.assistant.context import build_app_context
    from app.domains.assistant.schemas import AssistantContextSelection

    _import_csv(client)
    _import_pack(client, _seeded_pack_for(client))

    database = client.app.state.database  # type: ignore[attr-defined]
    with database.session_factory() as session:
        snapshot = build_app_context(
            session,
            user_request="what should I offer a gym?",
            runtime_settings=Settings(session_token="x" * 32),
            instagram_connected=False,
            selection=AssistantContextSelection(kind="workspace"),
        )

    serialised = json.dumps(snapshot, ensure_ascii=False)
    # The fit is real but unconfirmed, so the label may travel and the name may not.
    assert "Example Grappling Club" not in serialised


def test_confirming_a_fit_and_allowing_the_name_lets_it_through(client: TestClient) -> None:
    from app.core.config import Settings
    from app.domains.assistant.context import build_app_context
    from app.domains.assistant.schemas import AssistantContextSelection

    _import_csv(client)
    _import_pack(client, _seeded_pack_for(client))

    fit = client.get("/api/v1/catalogue/proven-fits").json()[0]
    confirmed = client.patch(
        f"/api/v1/catalogue/proven-fits/{fit['id']}",
        json={"status": "confirmed", "share_client_name": True},
    )
    assert confirmed.status_code == 200, confirmed.text

    database = client.app.state.database  # type: ignore[attr-defined]
    with database.session_factory() as session:
        snapshot = build_app_context(
            session,
            user_request="what should I offer a gym?",
            runtime_settings=Settings(session_token="x" * 32),
            instagram_connected=False,
            selection=AssistantContextSelection(kind="workspace"),
        )

    assert "Example Grappling Club" in json.dumps(snapshot, ensure_ascii=False)


def test_enrichment_status_reports_what_still_needs_attention(client: TestClient) -> None:
    _import_csv(client)
    _import_pack(client, _seeded_pack_for(client))

    status = client.get("/api/v1/catalogue/enrichment/status").json()
    assert status["catalogue_imported_at"]
    assert status["catalogue_stale"] is False
    assert status["products_enriched"] == 1
    assert status["products_awaiting_enrichment"] == status["products_total"] - 1
    # A freshly seeded product is not stale: staleness means the listing changed afterwards.
    assert status["products_stale_enrichment"] == 0
    assert status["knowledge_notes"] == 2
    assert status["fits_awaiting_confirmation"] == 1
