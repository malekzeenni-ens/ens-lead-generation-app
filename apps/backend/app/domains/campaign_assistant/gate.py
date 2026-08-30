from app.core.config import Settings
from app.core.errors import DomainError
from app.domains.system.schemas import WorkspaceSettings


def require_local_ai_enabled(
    runtime_settings: Settings,
    workspace_settings: WorkspaceSettings,
) -> None:
    if not runtime_settings.campaign_assistant_enabled:
        raise DomainError(
            "CAMPAIGN_ASSISTANT_DISABLED",
            "The local campaign assistant is disabled by application configuration.",
            status_code=503,
        )
    if not workspace_settings.local_campaign_assistant_enabled:
        raise DomainError(
            "CAMPAIGN_ASSISTANT_DISABLED",
            "Enable the local campaign assistant in Settings before generating a response.",
            status_code=409,
        )
