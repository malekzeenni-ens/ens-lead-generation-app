"""Broad catalogue questions are answered by the app from the database, not by the local model.

A 3B model given twelve ranked products listed them as the whole range. These tests hold the
split: an overview for a broad question, exact lists for the reply to it, and the model for
anything that needs judgement.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.assistant.catalogue_answers import CATALOGUE_MODEL_NAME
from app.domains.assistant.prompt import GENERAL_SYSTEM_PROMPT
from app.domains.catalogue.enrichment import derive_group, is_add_on
from tests.test_general_assistant import create_conversation, install_manager
from tests.test_product_knowledge import _import_csv, _import_pack, _pack

_PRODUCTS: list[dict[str, Any]] = [
    {
        "name": "Personalised gym water bottle 900ml - engraved name or logo",
        "category": "Water Bottles",
        "summary": "A 900ml bottle for gym members. Only £9 each.",
        "target_segments": ["Gyms, studios and sports clubs"],
        "pricing_guidance": "£9 each, £7 over 50",
        "b2b_relevant": True,
    },
    {
        "name": "Personalised insulated travel coffee mug 350ml - rope handle",
        "category": "Travel Mugs",
        "summary": "A travel mug for cafés to sell with their logo.",
        "target_segments": ["Cafés, restaurants and takeaways"],
    },
    {
        "name": "Custom brass logo plaque - laser-engraved for offices and studios",
        "category": "Decorative Plaques",
        "summary": "A brass plaque for a reception wall.",
        "target_segments": ["Offices and corporate teams", "Gyms, studios and sports clubs"],
    },
    {"name": "Personalised acrylic name cake topper", "category": "Cake Toppers"},
    {"name": "Engraved", "category": "Uncategorized"},
    {"name": "Rush order - express next-business-day delivery", "category": "Uncategorized"},
]


def _catalogue(client: TestClient) -> None:
    for product in _PRODUCTS:
        response = client.post("/api/v1/catalogue/products", json=product)
        assert response.status_code == 201, response.text


def _ask(client: TestClient, conversation: dict[str, Any], content: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/assistant/conversations/{conversation['id']}/messages",
        json={"content": content},
    )
    assert response.status_code == 200, response.text
    message: dict[str, Any] = response.json()["messages"][-1]
    return message


def test_a_broad_question_gets_an_overview_that_asks_what_to_show(
    client: TestClient, app: FastAPI
) -> None:
    manager = install_manager(app)
    _catalogue(client)
    reply = _ask(client, create_conversation(client), "what are the products")

    assert reply["model_name"] == CATALOGUE_MODEL_NAME
    assert manager.messages == []
    content = reply["content"]
    assert content.startswith("You have 4 products in 3 groups:")
    assert "- Drinkware (2)" in content
    assert "Gyms, studios and sports clubs (2)" in content
    assert content.rstrip().endswith('Or reply "all" for the full list.')
    # Shopify add-on listings are options, not products.
    assert "Engraved" not in content and "Rush order" not in content


def test_replies_to_the_overview_list_exactly_and_everything_else_reaches_the_model(
    client: TestClient, app: FastAPI
) -> None:
    manager = install_manager(app)
    _catalogue(client)
    conversation = create_conversation(client)
    _ask(client, conversation, "what do we sell?")

    everything = _ask(client, conversation, "yes please")
    assert everything["model_name"] == CATALOGUE_MODEL_NAME
    assert everything["content"].startswith("All 4 products, by group:")
    for product in _PRODUCTS[:4]:
        assert f"- {product['name']}" in everything["content"]

    cafes = _ask(client, conversation, "cafés")
    assert cafes["content"].startswith("Cafés, restaurants and takeaways: 1 products")
    assert "travel coffee mug" in cafes["content"]
    assert "gym water bottle" not in cafes["content"]

    drinkware = _ask(client, conversation, "show me the drinkware")
    assert drinkware["content"].startswith("Drinkware: 2 products")
    assert manager.messages == []

    advice = _ask(client, conversation, "which is best for a gym opening?")
    assert advice["model_name"] == "llama3.2:3b"
    assert len(manager.messages) == 1


def test_questions_that_need_judgement_or_context_go_to_the_model(
    client: TestClient, app: FastAPI
) -> None:
    manager = install_manager(app)
    _catalogue(client)
    conversation = create_conversation(client)
    for question in ("what products suit a gym?", "draft an email to a cafe"):
        assert _ask(client, conversation, question)["model_name"] == "llama3.2:3b"
    assert len(manager.messages) == 2

    # A named group or trade, and nothing else, is answered exactly.
    assert _ask(client, conversation, "what products for gyms")["content"].startswith(
        "Gyms, studios and sports clubs: 2 products"
    )
    assert _ask(client, conversation, "list all products")["content"].startswith("All 4 products")


def test_no_price_reaches_a_catalogue_answer(client: TestClient, app: FastAPI) -> None:
    install_manager(app)
    _catalogue(client)
    conversation = create_conversation(client)
    replies = [
        _ask(client, conversation, question)["content"]
        for question in ("what are the products", "drinkware", "all", "what products for gyms")
    ]
    assert all("£" not in reply for reply in replies)


def test_the_model_is_told_it_sees_a_sample_of_the_range(client: TestClient, app: FastAPI) -> None:
    manager = install_manager(app)
    _catalogue(client)
    _ask(client, create_conversation(client), "which products suit a physio clinic?")

    system = manager.messages[0][0]["content"]
    assert '"active_product_count":4' in system
    assert '"products_shown":4' in system
    assert '"product_groups":{' in system
    assert '"Engraved"' not in system
    assert "Never present them as the full range" in GENERAL_SYSTEM_PROMPT


def test_group_comes_from_the_pack_or_falls_back_to_the_name() -> None:
    assert derive_group("Personalised kids water bottle 350ml", "Water Bottles") == "Drinkware"
    assert derive_group("Personalised baby milestone photo board - arch design", "") != (
        "Signage and plaques"
    ), "'design' must not match 'sign'"
    assert derive_group("Cheers bamboo bottle opener", "Bottle Openers") == "Home and kitchen"
    assert derive_group("Something unusual", "Misc") == "Other"
    assert is_add_on("Engraved") and is_add_on("Rush order - next day")
    assert not is_add_on("Engraved slate coaster")


def test_a_group_set_in_the_pack_overrides_the_derived_one(
    client: TestClient, app: FastAPI
) -> None:
    install_manager(app)
    _import_csv(client)
    product = next(
        item
        for item in client.get("/api/v1/catalogue/products").json()
        if item["active"]
        and not is_add_on(item["name"])
        and derive_group(item["name"], item["category"]) != ("Gifts and occasions")
    )
    pack = _pack([{"handle": product["shopify_handle"], "group": "Gifts and occasions"}])
    _import_pack(client, pack)

    listing = _ask(client, create_conversation(client), "list all products")["content"]
    gifts = listing.split("Gifts and occasions (")[1].split("\n\n")[0]
    assert f"- {product['name']}" in gifts
