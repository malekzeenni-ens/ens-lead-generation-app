from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.migrations import backend_directory, run_migrations
from app.main import create_app

SESSION_TOKEN = "test-session-token-with-at-least-thirty-two-characters"  # noqa: S105 -- test fixture


def head_revision() -> str:
    """The latest migration, so schema-version assertions need no edit per migration."""
    config = Config(str(backend_directory() / "alembic.ini"))
    config.set_main_option("script_location", str(backend_directory() / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


@pytest.fixture(scope="session")
def migrated_database_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database at the head revision, built once per test session.

    Running every migration costs about 1.6 s; upgrading a database already at head costs under
    0.1 s. Each test copies this file, and `create_app` still runs its upgrade as in production.
    """
    template = tmp_path_factory.mktemp("migrated-template") / "ens-leads.db"
    run_migrations(template)
    return template


@pytest.fixture
def settings(tmp_path: Path, migrated_database_template: Path) -> Settings:
    database_path = tmp_path / "data" / "ens-leads.db"
    database_path.parent.mkdir(parents=True)
    shutil.copyfile(migrated_database_template, database_path)
    return Settings(
        session_token=SESSION_TOKEN,
        database_path=database_path,
        log_directory=tmp_path / "logs",
        google_places_api_key=None,
        campaign_run_inline=True,
        # The real pack sits at the repository root on the operator's machine; keep it out.
        knowledge_pack_auto_import=False,
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
