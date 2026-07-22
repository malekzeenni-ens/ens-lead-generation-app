from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "EtchNShine" / "LeadGeneration"


class Settings(BaseSettings):
    """Runtime settings. Secret values are never loaded from a source-controlled env file."""

    model_config = SettingsConfigDict(env_prefix="ENS_", env_file=None, extra="ignore")

    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    session_token: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)), min_length=24
    )
    database_path: Path = Field(default_factory=lambda: _default_data_directory() / "ens-leads.db")
    log_directory: Path = Field(default_factory=lambda: _default_data_directory() / "logs")
    google_places_api_key: SecretStr | None = None
    meta_graph_version: str = Field(default="v25.0", pattern=r"^v[0-9]+\.[0-9]+$")
    meta_oauth_callback_url: str = "http://localhost:8766/meta/oauth/callback"
    discovery_max_results: int = Field(default=40, ge=1, le=60)
    discovery_max_queries: int = Field(default=3, ge=1, le=10)
    provider_timeout_seconds: float = Field(default=12.0, ge=2.0, le=60.0)
    enrichment_max_bytes: int = Field(default=524_288, ge=65_536, le=2_097_152)
    enrichment_timeout_seconds: float = Field(default=8.0, ge=2.0, le=30.0)
    fhrs_max_businesses_per_run: int = Field(default=15, ge=1, le=60)
    fhrs_handle_guesses_per_business: int = Field(default=4, ge=1, le=5)
    fhrs_max_instagram_lookups_per_run: int = Field(default=60, ge=1, le=200)
    registry_max_instagram_candidates: int = Field(default=30, ge=1, le=100)
    campaign_run_inline: bool = False
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:1420",
        "http://localhost:1420",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    )

    @field_validator("host")
    @classmethod
    def require_loopback(cls, value: str) -> str:
        if value != "127.0.0.1":
            raise ValueError("The local API must bind to 127.0.0.1")
        return value

    def prepare_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_directory.mkdir(parents=True, exist_ok=True)

    @property
    def google_places_enabled(self) -> bool:
        return bool(
            self.google_places_api_key and self.google_places_api_key.get_secret_value().strip()
        )
