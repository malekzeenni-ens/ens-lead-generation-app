from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import lead_payload
from tests.test_qualification_workflow import _import_catalogue


def _create_products(client: TestClient) -> dict[str, str]:
    _import_catalogue(client)
    products = client.get("/api/v1/catalogue/products").json()
    return {product["name"]: product["id"] for product in products}


def test_create_list_update_delete_product_family(client: TestClient) -> None:
    products = _create_products(client)
    topper_id = products["Personalised Cake Topper"]
    charm_id = products["Cake Charm"]

    created = client.post(
        "/api/v1/catalogue/product-families",
        json={
            "name": "Cake celebration range",
            "description": "Everything for a celebration cake order.",
            "product_ids": [topper_id, charm_id],
        },
    )
    assert created.status_code == 201
    family = created.json()
    assert family["name"] == "Cake celebration range"
    assert [product["id"] for product in family["products"]] == [topper_id, charm_id]

    listed = client.get("/api/v1/catalogue/product-families").json()
    assert [item["id"] for item in listed] == [family["id"]]

    updated = client.patch(
        f"/api/v1/catalogue/product-families/{family['id']}",
        json={"product_ids": [charm_id]},
    )
    assert updated.status_code == 200
    assert [product["id"] for product in updated.json()["products"]] == [charm_id]

    deleted = client.delete(f"/api/v1/catalogue/product-families/{family['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/catalogue/product-families").json() == []


def test_create_family_rejects_duplicate_name(client: TestClient) -> None:
    products = _create_products(client)
    payload = {"name": "Duplicate range", "product_ids": [next(iter(products.values()))]}
    assert client.post("/api/v1/catalogue/product-families", json=payload).status_code == 201
    conflict = client.post("/api/v1/catalogue/product-families", json=payload)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "PRODUCT_FAMILY_NAME_EXISTS"


def test_create_family_rejects_unknown_product_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/catalogue/product-families",
        json={"name": "Broken range", "product_ids": ["11111111-1111-1111-1111-111111111111"]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "PRODUCT_FAMILY_UNKNOWN_PRODUCT"


def test_campaign_rejects_unknown_product_family_id(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    response = client.post(
        "/api/v1/campaigns",
        json={
            **campaign_payload,
            "name": "Family-linked campaign",
            "product_family_id": "22222222-2222-2222-2222-222222222222",
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "PRODUCT_FAMILY_NOT_FOUND"


def test_family_assigned_campaign_overrides_automatic_product_matching(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    products = _create_products(client)
    topper_id = products["Personalised Cake Topper"]

    family = client.post(
        "/api/v1/catalogue/product-families",
        json={"name": "Topper only", "product_ids": [topper_id]},
    ).json()

    with_family = client.post(
        "/api/v1/campaigns",
        json={
            **campaign_payload,
            "name": "Family assigned campaign",
            "product_family_id": family["id"],
        },
    ).json()
    without_family = client.post(
        "/api/v1/campaigns", json={**campaign_payload, "name": "No family campaign"}
    ).json()

    second_lead = lead_payload(without_family["id"])
    second_lead["business_name"] = "Second Celebration Cakes"

    lead_with_family = client.post("/api/v1/leads", json=lead_payload(with_family["id"])).json()
    lead_without_family = client.post("/api/v1/leads", json=second_lead).json()

    scored_with_family = client.post(
        f"/api/v1/leads/{lead_with_family['id']}/score",
        json={"campaign_id": with_family["id"]},
    ).json()
    scored_without_family = client.post(
        f"/api/v1/leads/{lead_without_family['id']}/score",
        json={"campaign_id": without_family["id"]},
    ).json()

    family_matches = scored_with_family["product_matches"]
    assert [match["product_id"] for match in family_matches] == [topper_id]
    assert family_matches[0]["match_score"] == 100
    assert "Topper only" in family_matches[0]["reason"]

    heuristic_matches = scored_without_family["product_matches"]
    assert {match["product_id"] for match in heuristic_matches} == set(products.values())
    assert all("product family" not in match["reason"].casefold() for match in heuristic_matches)


def test_deleting_product_family_falls_back_to_automatic_matching(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    products = _create_products(client)
    topper_id = products["Personalised Cake Topper"]
    family = client.post(
        "/api/v1/catalogue/product-families",
        json={"name": "Removable range", "product_ids": [topper_id]},
    ).json()
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            **campaign_payload,
            "name": "Fallback campaign",
            "product_family_id": family["id"],
        },
    ).json()
    lead = client.post("/api/v1/leads", json=lead_payload(campaign["id"])).json()

    assert client.delete(f"/api/v1/catalogue/product-families/{family['id']}").status_code == 204

    scored = client.post(
        f"/api/v1/leads/{lead['id']}/score",
        json={"campaign_id": campaign["id"]},
    ).json()
    assert {match["product_id"] for match in scored["product_matches"]} == set(products.values())
    assert all(
        "product family" not in match["reason"].casefold() for match in scored["product_matches"]
    )
