from fastapi.testclient import TestClient


def test_campaign_edit_pause_search_and_duplicate(
    client: TestClient, campaign_payload: dict[str, object]
) -> None:
    created_response = client.post("/api/v1/campaigns", json=campaign_payload)
    assert created_response.status_code == 201
    campaign = created_response.json()

    updated_response = client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        json={
            "description": "Updated local campaign",
            "weekly_shortlist_size": 8,
            "status": "paused",
        },
    )
    assert updated_response.status_code == 200
    updated = updated_response.json()
    assert updated["description"] == "Updated local campaign"
    assert updated["weekly_shortlist_size"] == 8
    assert updated["status"] == "paused"

    search = client.get("/api/v1/campaigns", params={"query": "bakery", "status": "paused"})
    assert search.status_code == 200
    assert [item["id"] for item in search.json()] == [campaign["id"]]

    duplicate_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/duplicate",
        json={
            "name": "Milton Keynes Bakery Partnerships",
            "primary_location": "Milton Keynes, United Kingdom",
        },
    )
    assert duplicate_response.status_code == 201
    duplicate = duplicate_response.json()
    assert duplicate["name"] == "Milton Keynes Bakery Partnerships"
    assert duplicate["primary_location"] == "Milton Keynes, United Kingdom"
    assert duplicate["status"] == "paused"
    assert duplicate["product_categories"] == campaign["product_categories"]

    conflict = client.patch(f"/api/v1/campaigns/{campaign['id']}", json={"name": duplicate["name"]})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "CAMPAIGN_NAME_EXISTS"
