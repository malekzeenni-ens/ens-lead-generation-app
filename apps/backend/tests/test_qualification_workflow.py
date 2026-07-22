from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient

from tests.conftest import lead_payload

SHOPIFY_CSV = (
    "Handle,Title,Body (HTML),Product Category,Type,Tags,Published,Variant Price,"
    "Image Src,Status\n"
    "personalised-cake-topper,Personalised Cake Topper,<p>Mirror acrylic topper</p>,"
    'Home & Garden,Cake toppers,"segment:Bakeries and home bakers,'
    'use-case:Celebration cakes,sample-eligible",TRUE,12.50,'
    "https://example.test/topper.jpg,active\n"
    "personalised-cake-topper,,,,,,,15.00,,\n"
    "cake-charm,Cake Charm,Small personalised charm,Home & Garden,Cake charms,"
    '"segment:Bakeries and home bakers",TRUE,4.00,,active\n'
)


def _campaign_and_lead(
    client: TestClient,
    campaign_payload: dict[str, object],
    *,
    name: str = "Example Celebration Cakes",
) -> tuple[dict[str, object], dict[str, object]]:
    campaign_data = {**campaign_payload, "weekly_shortlist_size": 2}
    campaign = client.post("/api/v1/campaigns", json=campaign_data).json()
    payload = lead_payload(str(campaign["id"]))
    payload["business_name"] = name
    lead = client.post("/api/v1/leads", json=payload).json()
    return campaign, lead


def _import_catalogue(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/catalogue/import/shopify",
        json={"filename": "products_export.csv", "content": SHOPIFY_CSV},
    )
    assert response.status_code == 200
    return cast(dict[str, object], response.json())


def test_shopify_csv_upserts_editable_catalogue(
    client: TestClient,
) -> None:
    result = _import_catalogue(client)
    assert result == {
        "filename": "products_export.csv",
        "rows_read": 3,
        "products_created": 2,
        "products_updated": 0,
        "products_skipped": 0,
        "issues": [],
    }
    products = client.get("/api/v1/catalogue/products").json()
    topper = next(
        product for product in products if product["shopify_handle"] == "personalised-cake-topper"
    )
    assert topper["variant_count"] == 2
    assert topper["pricing_guidance"] == "£12.50 to £15.00"
    assert topper["description"] == "Mirror acrylic topper"
    assert topper["target_segments"] == ["Bakeries and home bakers"]
    assert topper["example_use_cases"] == ["Celebration cakes"]
    assert topper["sample_eligible"] is True

    updated_csv = SHOPIFY_CSV.replace("Personalised Cake Topper", "Custom Cake Topper")
    reimport = client.post(
        "/api/v1/catalogue/import/shopify",
        json={"filename": "products_export.csv", "content": updated_csv},
    )
    assert reimport.json()["products_updated"] == 2
    assert len(client.get("/api/v1/catalogue/products").json()) == 2

    edited = client.patch(
        f"/api/v1/catalogue/products/{topper['id']}",
        json={"active": False, "sample_eligible": False},
    )
    assert edited.status_code == 200
    assert edited.json()["active"] is False

    invalid = client.post(
        "/api/v1/catalogue/import/shopify",
        json={"filename": "wrong.csv", "content": "Name,Price\nTopper,10"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "SHOPIFY_CSV_HEADERS_INVALID"


def test_deterministic_scoring_explanation_versions_and_override(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, lead = _campaign_and_lead(client, campaign_payload)
    _import_catalogue(client)

    response = client.post(
        f"/api/v1/leads/{lead['id']}/score",
        json={"campaign_id": campaign["id"]},
    )
    assert response.status_code == 200
    score = response.json()
    assert 0 <= score["final_score"] <= 100
    assert score["calculated_score"] == score["final_score"]
    assert score["rule_version"] == "deterministic-local-v4"
    assert score["profile_version"] == 1
    assert len(score["breakdown"]) == 7
    assert sum(item["points_available"] for item in score["breakdown"]) == 100
    assert all(item["ai_inference"] is None for item in score["breakdown"])
    assert score["product_matches"][0]["rule_based"] is True
    assert score["product_matches"][0]["evidence"]

    weights = {
        "business_relevance": 20,
        "activity": 25,
        "product_fit": 20,
        "local_relevance": 15,
        "commercial_potential": 10,
        "reach_credibility": 5,
        "contactability": 5,
    }
    version = client.patch(
        "/api/v1/scoring/profiles/Bakeries%20and%20home%20bakers",
        json={"name": "Bakery local model", "weights": weights},
    )
    assert version.status_code == 200
    assert version.json()["version"] == 2

    recalculated = client.post(
        f"/api/v1/leads/{lead['id']}/score",
        json={"campaign_id": campaign["id"]},
    ).json()
    assert recalculated["profile_version"] == 2
    assert len(client.get(f"/api/v1/leads/{lead['id']}/scores").json()) == 2

    overridden = client.post(
        f"/api/v1/leads/{lead['id']}/score/override",
        json={"final_score": 88, "reason": "Owner verified strong repeat-order potential"},
    )
    assert overridden.status_code == 200
    assert overridden.json()["calculated_score"] == recalculated["calculated_score"]
    assert overridden.json()["final_score"] == 88
    assert overridden.json()["manual_override"] is True


def test_scoring_v3_categories_do_not_penalise_fresh_unworked_leads(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, lead = _campaign_and_lead(client, campaign_payload)
    _import_catalogue(client)

    score = client.post(
        f"/api/v1/leads/{lead['id']}/score",
        json={"campaign_id": campaign["id"]},
    ).json()

    by_category = {item["category"]: item for item in score["breakdown"]}
    assert by_category["Business relevance"]["points_available"] == 25
    assert by_category["Activity"]["points_available"] == 10
    assert by_category["Product fit"]["points_available"] == 25
    assert by_category["Local relevance"]["points_available"] == 15
    assert by_category["Commercial potential"]["points_available"] == 5
    assert by_category["Reach and credibility"]["points_available"] == 10
    assert by_category["Contactability"]["points_available"] == 10

    # A brand-new lead was just captured and its evidence just collected, so
    # Activity should award full marks rather than requiring a work-log entry
    # that cannot exist yet on an unworked lead.
    assert by_category["Activity"]["points_awarded"] == 10
    assert by_category["Activity"]["missing_evidence"] == []

    # The old freetext-note-dependent checks no longer exist at all.
    business_terms = (
        by_category["Business relevance"]["evidence_used"]
        + by_category["Business relevance"]["missing_evidence"]
    )
    assert "Personalised or event-work evidence" not in business_terms
    product_terms = (
        by_category["Product fit"]["evidence_used"] + by_category["Product fit"]["missing_evidence"]
    )
    assert "Specific product-need evidence" not in product_terms
    contact_terms = (
        by_category["Contactability"]["evidence_used"]
        + by_category["Contactability"]["missing_evidence"]
    )
    assert "Resolved contact classification" not in contact_terms


def test_product_match_gives_partial_credit_when_segment_tags_are_missing(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, lead = _campaign_and_lead(client, campaign_payload)
    _import_catalogue(client)
    untagged = client.post(
        "/api/v1/catalogue/products",
        json={
            "name": "Untagged Cake Charm",
            "category": "Cake charms",
            "target_segments": [],
            "example_use_cases": [],
            "active": True,
            "sample_eligible": False,
        },
    )
    assert untagged.status_code == 201

    score = client.post(
        f"/api/v1/leads/{lead['id']}/score",
        json={"campaign_id": campaign["id"]},
    ).json()
    matches = {item["product_name"]: item for item in score["product_matches"]}
    assert matches["Cake Charm"]["match_score"] == 100
    assert matches["Untagged Cake Charm"]["match_score"] == 60
    assert "assign a product family" in matches["Untagged Cake Charm"]["reason"]


def test_weekly_shortlist_capacity_repeat_and_suppression_controls(
    client: TestClient,
    campaign_payload: dict[str, object],
) -> None:
    campaign, first = _campaign_and_lead(client, campaign_payload, name="Alpha Celebration Cakes")
    for name in ("Beta Wedding Cakes", "Gamma Home Bakery"):
        payload = lead_payload(str(campaign["id"]))
        payload["business_name"] = name
        assert client.post("/api/v1/leads", json=payload).status_code == 201
    _import_catalogue(client)

    over_capacity = client.post(
        "/api/v1/shortlists/generate",
        json={"campaign_id": campaign["id"], "week_start": "2026-07-20", "size": 3},
    )
    assert over_capacity.status_code == 409
    assert over_capacity.json()["code"] == "SHORTLIST_CAPACITY_EXCEEDED"

    generated = client.post(
        "/api/v1/shortlists/generate",
        json={"campaign_id": campaign["id"], "week_start": "2026-07-20", "size": 2},
    )
    assert generated.status_code == 200
    shortlist = generated.json()
    assert len(shortlist["items"]) == 2
    assert all(item["reason"].startswith("Score ") for item in shortlist["items"])
    assert all(item["product_matches"] for item in shortlist["items"])

    approved = client.post(
        f"/api/v1/shortlists/{shortlist['id']}/items/{shortlist['items'][0]['id']}/action",
        json={"action": "approved", "reason": "Fits this week's capacity"},
    )
    assert approved.status_code == 200
    assert approved.json()["items"][0]["decision"] == "approved"

    shortlisted_first = next(
        (item for item in shortlist["items"] if item["lead_id"] == first["id"]), None
    )
    if shortlisted_first:
        suppression = client.post(
            f"/api/v1/leads/{first['id']}/suppression",
            json={
                "suppression_type": "unsubscribe",
                "reason": "Business opted out",
                "source": "Test",
            },
        )
        assert suppression.status_code == 201
        current = client.get("/api/v1/shortlists").json()[0]
        suppressed_item = next(item for item in current["items"] if item["lead_id"] == first["id"])
        assert suppressed_item["decision"] == "suppressed"

    next_week = client.post(
        "/api/v1/shortlists/generate",
        json={"campaign_id": campaign["id"], "week_start": "2026-07-27", "size": 2},
    )
    assert next_week.status_code == 200
    assert all(
        item["lead_id"] not in {entry["lead_id"] for entry in shortlist["items"]}
        for item in next_week.json()["items"]
    )
