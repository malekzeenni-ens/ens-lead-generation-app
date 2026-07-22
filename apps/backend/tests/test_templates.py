from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_qualification_workflow import _import_catalogue


def _create_template(
    client: TestClient,
    *,
    topic: str = "Follow-up",
    subject: str = "Following up, {{business_name}}",
    body: str = "Hi {{business_name}}, checking in about your order.",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/templates",
        json={"topic": topic, "subject": subject, "body": body},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_create_list_update_and_delete_template(client: TestClient) -> None:
    created = _create_template(client)
    assert created["topic"] == "Follow-up"
    assert created["subject"] == "Following up, {{business_name}}"
    assert created["product_family_ids"] == []
    assert created["id"]

    listed = client.get("/api/v1/templates")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]

    updated = client.patch(
        f"/api/v1/templates/{created['id']}",
        json={"body": "Updated body for {{business_name}}"},
    )
    assert updated.status_code == 200
    assert updated.json()["body"] == "Updated body for {{business_name}}"
    assert updated.json()["topic"] == "Follow-up"

    deleted = client.delete(f"/api/v1/templates/{created['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/templates").json() == []


def test_template_links_one_or_more_product_families(client: TestClient) -> None:
    _import_catalogue(client)
    products = {
        product["name"]: product["id"]
        for product in client.get("/api/v1/catalogue/products").json()
    }
    topper_family = client.post(
        "/api/v1/catalogue/product-families",
        json={"name": "Toppers", "product_ids": [products["Personalised Cake Topper"]]},
    ).json()
    charm_family = client.post(
        "/api/v1/catalogue/product-families",
        json={"name": "Charms", "product_ids": [products["Cake Charm"]]},
    ).json()

    created = _create_template(client)
    updated = client.patch(
        f"/api/v1/templates/{created['id']}",
        json={"product_family_ids": [topper_family["id"], charm_family["id"]]},
    )
    assert updated.status_code == 200
    assert set(updated.json()["product_family_ids"]) == {topper_family["id"], charm_family["id"]}


def test_template_rejects_unknown_product_family(client: TestClient) -> None:
    response = client.post(
        "/api/v1/templates",
        json={
            "topic": "Intro",
            "subject": "",
            "body": "Hello",
            "product_family_ids": ["11111111-1111-1111-1111-111111111111"],
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "PRODUCT_FAMILY_NOT_FOUND"


def test_template_requires_authentication(client: TestClient) -> None:
    with TestClient(cast(FastAPI, client.app)) as unauthenticated:
        response = unauthenticated.get("/api/v1/templates")
    assert response.status_code == 401


def test_create_template_rejects_empty_body(client: TestClient) -> None:
    response = client.post("/api/v1/templates", json={"topic": "Intro", "subject": "", "body": ""})
    assert response.status_code == 422


def test_update_template_requires_a_change(client: TestClient) -> None:
    created = _create_template(client)
    response = client.patch(f"/api/v1/templates/{created['id']}", json={})
    assert response.status_code == 422


def test_update_and_delete_unknown_template_returns_404(client: TestClient) -> None:
    assert client.patch("/api/v1/templates/missing", json={"topic": "New"}).status_code == 404
    assert client.delete("/api/v1/templates/missing").status_code == 404
