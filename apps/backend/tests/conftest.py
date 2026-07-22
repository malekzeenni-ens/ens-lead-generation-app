from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

SESSION_TOKEN = "test-session-token-with-at-least-thirty-two-characters"  # noqa: S105 -- test fixture


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        session_token=SESSION_TOKEN,
        database_path=tmp_path / "data" / "ens-leads.db",
        log_directory=tmp_path / "logs",
        campaign_run_inline=True,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, headers={"X-Session-Token": SESSION_TOKEN}) as test_client:
        yield test_client


@pytest.fixture
def campaign_payload() -> dict[str, object]:
    return {
        "name": "Luton Bakery Partnerships",
        "description": "Synthetic local bakery pilot",
        "segment": "Bakeries and home bakers",
        "primary_location": "Luton, United Kingdom",
        "radius_miles": 25,
        "keywords": ["bakery", "cake maker"],
        "exclusion_keywords": [],
        "product_categories": ["Cake toppers", "Cake charms"],
        "discovery_sources": ["manual"],
        "weekly_shortlist_size": 5,
        "minimum_score_threshold": 0,
        "preferred_channels": ["email", "instagram"],
        "offer_settings": {"digital_mock_up": True},
        "discovery_mode": "manual",
        "status": "active",
    }


def lead_payload(campaign_id: str) -> dict[str, object]:
    return {
        "campaign_id": campaign_id,
        "business_name": "Example Celebration Cakes",
        "segment": "Bakeries and home bakers",
        "location": "Luton",
        "website": "https://example.test",
        "contact_classification": "unknown",
        "source": {
            "name": "Manual entry",
            "source_type": "manual",
            "source_url": "https://example.test",
            "classification": "user_verified",
        },
    }
