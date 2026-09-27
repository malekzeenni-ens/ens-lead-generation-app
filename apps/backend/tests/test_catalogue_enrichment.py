"""The catalogue import has to produce something the assistant can actually sell from.

The fixture is a real slice of the operator's Shopify export, chosen to keep the quirks the
derivation rules exist for: `Type` empty on most listings, taxonomy paths in `Product Category`,
prices inside `SEO Description`, and store tags that never use the `segment:` prefix.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.domains.catalogue import enrichment

FIXTURE = Path(__file__).parent / "fixtures" / "shopify_products_sample.csv"


def _csv_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _import(client: TestClient, content: str, filename: str = "export.csv") -> dict[str, object]:
    response = client.post(
        "/api/v1/catalogue/import/shopify",
        json={"filename": filename, "content": content},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def _products(client: TestClient) -> list[dict[str, object]]:
    response = client.get("/api/v1/catalogue/products")
    assert response.status_code == 200, response.text
    return list(response.json())


def test_the_segment_list_matches_the_shipped_enrichment_pack() -> None:
    # The pack, the AI enrichment enum and lead matching all share one vocabulary. If the pack
    # is regenerated with different trades, this is the test that says so.
    pack = Path(__file__).parents[3] / "product_enrichment.json"
    if not pack.exists():  # pragma: no cover - the pack is optional in a clean checkout
        pytest.skip("product_enrichment.json is not present")
    import json

    segments = json.loads(pack.read_text(encoding="utf-8"))["segments"]
    assert list(segments) == list(enrichment.SEGMENTS)


def test_import_gives_every_product_a_real_category_and_a_price_free_summary(
    client: TestClient,
) -> None:
    _import(client, _csv_text())
    products = _products(client)
    assert products

    assert [item for item in products if not str(item["category"]).strip()] == []
    # A taxonomy path must be reduced to its leaf, never stored whole.
    assert [item for item in products if ">" in str(item["category"])] == []

    # Every product with anything to summarise gets one. The three fixture rows without a
    # summary have neither an SEO description nor a body: two of them are Shopify option-set
    # helper rows rather than real products. On the full export this comes out at 93%.
    missing = [
        item["name"]
        for item in products
        if not str(item["summary"] or "").strip() and str(item["description"] or "").strip()
    ]
    assert missing == []
    with_summary = [item for item in products if str(item["summary"] or "").strip()]
    assert len(with_summary) >= len(products) * 0.85

    priced = [item["name"] for item in products if "£" in str(item["summary"] or "")]
    assert priced == [], f"summaries must never carry a price: {priced}"


def test_import_derives_the_sales_fields_the_shopify_export_does_not_provide(
    client: TestClient,
) -> None:
    _import(client, _csv_text())
    products = _products(client)

    # Before these rules existed every one of these was empty for every product, because no
    # listing uses the `segment:` or `use-case:` tag prefixes the importer looked for.
    assert any(item["target_segments"] for item in products)
    assert any(item["materials"] for item in products)
    assert any(item["b2b_relevant"] for item in products)
    assert all(item["product_url"] for item in products)

    for item in products:
        for segment in item["target_segments"]:
            assert segment in enrichment.SEGMENT_SET, segment
        for material in item["materials"]:
            # Approved material names only: no "plastic", "perspex" or "aluminum".
            assert material in set(enrichment._TAG_MATERIALS.values()) | {
                value for _, value in enrichment._TITLE_MATERIALS
            }


def test_a_corporate_tagged_product_is_flagged_for_business_buyers(client: TestClient) -> None:
    _import(client, _csv_text())
    corporate = [
        item
        for item in _products(client)
        if "corporate" in str(item["name"]).casefold() or item["target_segments"]
    ]
    assert corporate
    assert any(item["b2b_relevant"] for item in corporate)


def test_a_product_missing_from_a_newer_export_is_deactivated(client: TestClient) -> None:
    _import(client, _csv_text())
    products = _products(client)
    dropped = str(products[0]["shopify_handle"])

    lines = _csv_text().splitlines(keepends=True)
    trimmed = [lines[0]] + [
        line for line in lines[1:] if not line.casefold().startswith(f"{dropped},")
    ]
    result = _import(client, "".join(trimmed), filename="newer.csv")

    assert result["products_deactivated"] == 1
    after = {str(item["shopify_handle"]): item for item in _products(client)}
    assert after[dropped]["active"] is False


def test_a_manually_created_product_survives_a_shopify_import(client: TestClient) -> None:
    created = client.post(
        "/api/v1/catalogue/products",
        json={"name": "Hand-added slate coaster", "category": "Coasters"},
    )
    assert created.status_code == 201, created.text
    _import(client, _csv_text())
    names = {str(item["name"]) for item in _products(client) if item["active"]}
    assert "Hand-added slate coaster" in names


def test_an_import_never_overwrites_the_operators_own_sales_wording(client: TestClient) -> None:
    _import(client, _csv_text())
    target = _products(client)[0]

    edited = client.patch(
        f"/api/v1/catalogue/products/{target['id']}",
        json={
            "b2b_notes": "Runs of 50 or more, one setup fee, logo in white.",
            "custom_options": "logo, names, numbering",
            "summary": "My own wording, kept.",
            "bulk_ready": True,
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["enrichment_source"] == "manual"

    _import(client, _csv_text(), filename="again.csv")

    after = next(item for item in _products(client) if item["id"] == target["id"])
    assert after["b2b_notes"] == "Runs of 50 or more, one setup fee, logo in white."
    assert after["custom_options"] == "logo, names, numbering"
    assert after["summary"] == "My own wording, kept."
    assert after["bulk_ready"] is True
    assert after["enrichment_source"] == "manual"


def test_reimporting_the_same_export_creates_no_duplicates(client: TestClient) -> None:
    first = _import(client, _csv_text())
    before = len(_products(client))
    second = _import(client, _csv_text(), filename="again.csv")

    assert second["products_created"] == 0
    assert second["products_updated"] == first["products_created"]
    assert len(_products(client)) == before


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Only £12.99 today", "Only today"),
        ("From £8 to £15.50", ""),
        ("Save 20% off now", "now"),
        ("30% off this week", "this week"),
        ("Engraved into solid oak", "Engraved into solid oak"),
    ],
)
def test_price_phrasing_is_stripped_without_mangling_ordinary_copy(
    raw: str, expected: str
) -> None:
    assert enrichment.strip_prices(raw) == expected


def test_a_taxonomy_path_is_reduced_to_its_leaf() -> None:
    assert enrichment.derive_category("", "Home & Garden > Decor > Coasters") == "Coasters"
    # An explicit Type always wins, since the operator set it deliberately.
    assert enrichment.derive_category("Signage", "Home & Garden > Decor") == "Signage"
    assert enrichment.derive_category("", "") == "Uncategorised"
