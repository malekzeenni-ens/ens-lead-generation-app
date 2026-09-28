from app.core.secrets import SecretStore
from app.domains.system.cloud_polish_schemas import CloudPolishStatusRead
from app.domains.system.schemas import WorkspaceSettings

_KEY = "cloud_polish_credentials"


class CloudPolishConfigurationService:
    def __init__(self, secret_store: SecretStore) -> None:
        self.secret_store = secret_store

    def status(self, settings: WorkspaceSettings) -> CloudPolishStatusRead:
        return CloudPolishStatusRead(
            configured=self.secret_store.get_json(_KEY) is not None,
            enabled=settings.cloud_polish_enabled,
            model=settings.cloud_polish_model or "claude-sonnet-5",
        )

    def configure(self, api_key: str, settings: WorkspaceSettings) -> CloudPolishStatusRead:
        self.secret_store.set_json(_KEY, {"api_key": api_key})
        return self.status(settings)

    def remove(self, settings: WorkspaceSettings) -> CloudPolishStatusRead:
        self.secret_store.delete(_KEY)
        return self.status(settings)

    def credential(self) -> str | None:
        stored = self.secret_store.get_json(_KEY)
        value = stored.get("api_key") if stored else None
        return str(value) if value else None
