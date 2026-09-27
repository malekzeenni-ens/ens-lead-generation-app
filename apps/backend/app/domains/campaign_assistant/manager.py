from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import DomainError
from app.domains.campaign_assistant.monitor import ProtectedApplicationMonitor
from app.domains.campaign_assistant.ollama import (
    OllamaChatResult,
    OllamaClient,
    OllamaResult,
    OllamaStructuredResult,
)
from app.domains.campaign_assistant.schemas import ResourceProfile

T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=BaseModel)


class CampaignAssistantManager:
    def __init__(
        self,
        settings: Settings,
        *,
        ollama_client: OllamaClient | None = None,
        monitor: ProtectedApplicationMonitor | None = None,
    ) -> None:
        self.settings = settings
        self.ollama = ollama_client or OllamaClient(settings)
        self._generation_lock = threading.Lock()
        self._active_applications: set[str] = set()
        self._protect_resources = True
        self._unload_after_current = threading.Event()
        self.monitor = monitor or ProtectedApplicationMonitor(
            settings.protected_process_names,
            settings.protected_app_poll_seconds,
            self._protected_apps_changed,
        )

    def start(self) -> None:
        if self.settings.campaign_assistant_enabled:
            self.ollama.open()
            self.monitor.start()

    def shutdown(self) -> None:
        self.monitor.stop()
        self.ollama.unload()
        self.ollama.close()

    @property
    def active_applications(self) -> set[str]:
        return set(self._active_applications)

    def resource_profile(self, protect_resources: bool = True) -> ResourceProfile:
        self._protect_resources = protect_resources
        if protect_resources and self._active_applications:
            return ResourceProfile.DESIGN_SOFTWARE
        return ResourceProfile.STANDARD

    def set_preferred_model(self, model: str) -> None:
        """Apply the operator's model choice from workspace settings.

        An empty string means follow the configured default. Switching models unloads the
        previous one so a larger model does not sit in memory unused.
        """
        if model == self.ollama.preferred_model:
            return
        if not self._generation_lock.locked():
            self.ollama.unload()
        self.ollama.preferred_model = model

    @property
    def active_model(self) -> str:
        return self.ollama.model_for(self.resource_profile(self._protect_resources))

    def set_protection_enabled(self, enabled: bool) -> None:
        self._protect_resources = enabled
        if not enabled:
            self._unload_after_current.clear()
        elif self._active_applications:
            if self._generation_lock.locked():
                self._unload_after_current.set()
            else:
                self.ollama.unload()

    def _protected_apps_changed(self, applications: set[str]) -> None:
        self._active_applications = applications
        if applications and self._protect_resources:
            if self._generation_lock.locked():
                self._unload_after_current.set()
            else:
                self.ollama.unload()

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        protect_resources: bool,
    ) -> tuple[OllamaResult, ResourceProfile]:
        return self._run_locked(
            lambda profile: self.ollama.generate(messages, profile),
            protect_resources=protect_resources,
            busy_message="The local assistant is already processing another request.",
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        protect_resources: bool,
        artifact_format: str | None = None,
    ) -> tuple[OllamaChatResult, ResourceProfile]:
        return self._run_locked(
            lambda profile: self.ollama.chat(
                messages,
                profile,
                artifact_format=artifact_format,
            ),
            protect_resources=protect_resources,
            busy_message="The local assistant is already processing another request.",
        )

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, object],
        model_cls: type[ModelT],
        error_prefix: str,
        protect_resources: bool,
    ) -> tuple[OllamaStructuredResult[ModelT], ResourceProfile]:
        return self._run_locked(
            lambda profile: self.ollama.generate_structured(
                messages,
                profile,
                schema=schema,
                model_cls=model_cls,
                error_prefix=error_prefix,
            ),
            protect_resources=protect_resources,
            busy_message="The local assistant is already processing another request.",
        )

    def _run_locked(
        self,
        run: Callable[[ResourceProfile], T],
        *,
        protect_resources: bool,
        busy_message: str,
    ) -> tuple[T, ResourceProfile]:
        if not self._generation_lock.acquire(blocking=False):
            raise DomainError(
                "CAMPAIGN_ASSISTANT_BUSY",
                busy_message,
                status_code=409,
            )
        profile = self.resource_profile(protect_resources)
        try:
            result = run(profile)
        finally:
            should_unload = (
                profile == ResourceProfile.DESIGN_SOFTWARE or self._unload_after_current.is_set()
            )
            self._generation_lock.release()
            if should_unload:
                self._unload_after_current.clear()
                self.ollama.unload()
        return result, profile
