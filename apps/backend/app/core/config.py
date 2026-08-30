from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

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
    campaign_assistant_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = Field(default="llama3.2:3b", pattern=r"^llama3\.2:3b$")
    ollama_timeout_seconds: float = Field(default=120.0, ge=10.0, le=300.0)
    ollama_standard_context: int = Field(default=8_192, ge=2_048, le=16_384)
    ollama_protected_context: int = Field(default=4_096, ge=2_048, le=8_192)
    ollama_standard_output_limit: int = Field(default=1_200, ge=300, le=2_000)
    ollama_protected_output_limit: int = Field(default=900, ge=300, le=1_200)
    ollama_standard_keep_alive: str = "5m"
    assistant_attachment_max_bytes: int = Field(default=5_242_880, ge=65_536, le=20_971_520)
    assistant_attachment_context_chars: int = Field(default=30_000, ge=2_000, le=100_000)
    protected_app_poll_seconds: float = Field(default=10.0, ge=2.0, le=60.0)
    lead_stale_after_days: int = Field(default=21, ge=1, le=365)
    protected_process_names: tuple[str, ...] = (
        "lightburn.exe",
        "xcs.exe",
        "xtool creative space.exe",
    )
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

    @field_validator("ollama_base_url")
    @classmethod
    def require_ollama_loopback(cls, value: str) -> str:
        parsed = urlparse(value.rstrip("/"))
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("The Ollama API must use a local loopback HTTP address")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("The Ollama API address must not contain credentials or parameters")
        return value.rstrip("/")

    def prepare_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_directory.mkdir(parents=True, exist_ok=True)

    @property
    def google_places_enabled(self) -> bool:
        return bool(
            self.google_places_api_key and self.google_places_api_key.get_secret_value().strip()
        )
