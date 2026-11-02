from __future__ import annotations

from contextlib import suppress

from sqlalchemy.orm import Session

from app.db.models import AppSetting
from app.domains.audit.service import record_audit_event
from app.domains.mobile.devices import DeviceRegistry
from app.domains.mobile.gateway import GatewayStartError, MobileGatewayManager
from app.domains.mobile.schemas import (
    MobileAccessConfig,
    MobileAccessConfigUpdate,
    MobileAccessStatus,
)

_CONFIG_KEY = "mobile_access"


class MobileAccessService:
    def __init__(self, manager: MobileGatewayManager, registry: DeviceRegistry) -> None:
        self.manager = manager
        self.registry = registry

    def config(self, session: Session) -> MobileAccessConfig:
        stored = session.get(AppSetting, _CONFIG_KEY)
        return MobileAccessConfig.model_validate(stored.value) if stored else MobileAccessConfig()

    def status(self, session: Session) -> MobileAccessStatus:
        config = self.config(session)
        return MobileAccessStatus(
            enabled=config.enabled,
            running=self.manager.running,
            port=self.manager.port,
            public_host=config.public_host,
            phone_url=f"https://{config.public_host}/" if config.public_host else None,
            error=self.manager.last_error,
            paired_devices=len(self.registry.list_devices(session)),
        )

    def update(
        self, session: Session, data: MobileAccessConfigUpdate, correlation_id: str
    ) -> MobileAccessStatus:
        current = self.config(session)
        updated = current.model_copy(update=data.model_dump(exclude_unset=True))
        stored = session.get(AppSetting, _CONFIG_KEY)
        if stored is None:
            session.add(AppSetting(key=_CONFIG_KEY, value=updated.model_dump()))
        else:
            stored.value = updated.model_dump()
        record_audit_event(
            session,
            action="mobile_access.updated",
            entity_type="app_setting",
            entity_id=_CONFIG_KEY,
            correlation_id=correlation_id,
            summary={"changed_fields": sorted(data.model_fields_set), "enabled": updated.enabled},
        )
        session.commit()
        self.apply(updated)
        return self.status(session)

    def apply(self, config: MobileAccessConfig) -> None:
        """Make the listener match the saved switch. A port clash is reported in the status."""
        if config.enabled:
            with suppress(GatewayStartError):
                self.manager.start()
        else:
            self.manager.stop()
