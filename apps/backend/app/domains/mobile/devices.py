"""Pairing phones and recognising them on every request (ADR-025)."""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import MobileDevice, MobilePairingCode
from app.domains.audit.service import record_audit_event

logger = logging.getLogger(__name__)

# No I, L, O, 0 or 1, so a code read off a screen cannot be mistyped.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
CODE_LIFETIME = timedelta(minutes=5)
CODE_MAX_ATTEMPTS = 5
DEVICE_IDLE_LIMIT = timedelta(days=30)
# Writing last-seen on every request would turn each read into a write.
LAST_SEEN_RESOLUTION = timedelta(minutes=5)
# Across all codes: more failures than this in the window refuses pairing for a while.
FAILURE_WINDOW_SECONDS = 600.0
FAILURE_LIMIT = 20

COOKIE_NAME = "ens_device"
# Browsers cap cookie lifetime at 400 days; the 30-day idle limit is enforced here instead.
COOKIE_MAX_AGE = 400 * 24 * 3600


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def normalise_code(code: str) -> str:
    return "".join(character for character in code.upper() if character.isalnum())


def format_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


@dataclass(frozen=True)
class IssuedCode:
    code: str
    expires_at: datetime


@dataclass(frozen=True)
class PairedDevice:
    device: MobileDevice
    cookie_value: str


class DeviceRegistry:
    def __init__(self) -> None:
        self._failures: deque[float] = deque()
        self._failures_lock = threading.Lock()

    def issue_code(self, session: Session, correlation_id: str) -> IssuedCode:
        """A new code replaces any earlier one still open."""
        now = datetime.now(UTC)
        session.execute(
            update(MobilePairingCode)
            .where(MobilePairingCode.closed_at.is_(None))
            .values(closed_at=now)
        )
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        record = MobilePairingCode(code_hash=_hash(code), expires_at=now + CODE_LIFETIME)
        session.add(record)
        session.flush()
        record_audit_event(
            session,
            action="mobile.pairing_code_issued",
            entity_type="mobile_pairing_code",
            entity_id=record.id,
            correlation_id=correlation_id,
            summary={"expires_in_seconds": int(CODE_LIFETIME.total_seconds())},
        )
        session.commit()
        logger.info(
            "Phone pairing code issued",
            extra={"event": "mobile_pairing_code_issued", "pairing_code_id": record.id},
        )
        return IssuedCode(code=format_code(code), expires_at=record.expires_at)

    def _too_many_failures(self) -> bool:
        cutoff = time.monotonic() - FAILURE_WINDOW_SECONDS
        with self._failures_lock:
            while self._failures and self._failures[0] < cutoff:
                self._failures.popleft()
            return len(self._failures) >= FAILURE_LIMIT

    def _record_failure(self) -> None:
        with self._failures_lock:
            self._failures.append(time.monotonic())

    def pair(
        self, session: Session, *, code: str, name: str, label: str, correlation_id: str
    ) -> PairedDevice:
        if self._too_many_failures():
            raise DomainError(
                "PAIRING_LOCKED",
                "Too many wrong codes. Wait ten minutes, then show a new code on your PC.",
                status_code=429,
            )
        now = datetime.now(UTC)
        active = session.scalars(
            select(MobilePairingCode)
            .where(MobilePairingCode.closed_at.is_(None))
            .order_by(MobilePairingCode.created_at.desc())
        ).first()
        if active is None or _aware(active.expires_at) <= now:
            if active is not None:
                active.closed_at = now
                session.commit()
            self._record_failure()
            self._log_failure(None, "expired_or_missing")
            raise DomainError(
                "PAIRING_CODE_EXPIRED",
                "This code has expired or was already used. Show a new code on your PC.",
                status_code=400,
            )
        if not secrets.compare_digest(active.code_hash, _hash(normalise_code(code))):
            active.attempts += 1
            if active.attempts >= CODE_MAX_ATTEMPTS:
                active.closed_at = now
            session.commit()
            self._record_failure()
            self._log_failure(active.id, "wrong_code", active.attempts)
            remaining = max(0, CODE_MAX_ATTEMPTS - active.attempts)
            raise DomainError(
                "PAIRING_CODE_WRONG",
                (
                    f"That code doesn't match. {remaining} tries left."
                    if remaining
                    else "That code doesn't match, and it has now been cancelled. "
                    "Show a new code on your PC."
                ),
                status_code=400,
                details={"attempts_remaining": remaining},
            )
        active.closed_at = now
        secret = secrets.token_urlsafe(32)
        device = MobileDevice(
            name=name.strip()[:60] or "Phone",
            label=label.strip()[:60],
            secret_hash=_hash(secret),
            created_at=now,
            last_seen_at=now,
        )
        session.add(device)
        session.flush()
        record_audit_event(
            session,
            action="mobile.device_paired",
            entity_type="mobile_device",
            entity_id=device.id,
            correlation_id=correlation_id,
            summary={"pairing_code_id": active.id},
        )
        session.commit()
        logger.info(
            "Phone paired",
            extra={"event": "mobile_pairing_succeeded", "device_id": device.id},
        )
        return PairedDevice(device=device, cookie_value=f"{device.id}.{secret}")

    def _log_failure(self, code_id: str | None, reason: str, attempts: int = 0) -> None:
        logger.warning(
            "Phone pairing failed",
            extra={
                "event": "mobile_pairing_failed",
                "pairing_code_id": code_id,
                "reason": reason,
                "attempts": attempts,
            },
        )

    def authenticate(self, session: Session, cookie_value: str | None) -> MobileDevice | None:
        """The paired, unrevoked, recently used device the cookie belongs to, if any."""
        if not cookie_value or "." not in cookie_value:
            return None
        device_id, _, secret = cookie_value.partition(".")
        device = session.get(MobileDevice, device_id[:36])
        if device is None or device.revoked_at is not None:
            return None
        if not secrets.compare_digest(device.secret_hash, _hash(secret)):
            return None
        now = datetime.now(UTC)
        last_seen = _aware(device.last_seen_at)
        if now - last_seen > DEVICE_IDLE_LIMIT:
            return None
        if now - last_seen > LAST_SEEN_RESOLUTION:
            device.last_seen_at = now
            session.commit()
        return device

    def list_devices(self, session: Session) -> list[MobileDevice]:
        return list(
            session.scalars(
                select(MobileDevice)
                .where(MobileDevice.revoked_at.is_(None))
                .order_by(MobileDevice.created_at.desc())
            )
        )

    def revoke(self, session: Session, device_id: str, correlation_id: str) -> None:
        device = session.get(MobileDevice, device_id)
        if device is None or device.revoked_at is not None:
            raise DomainError("DEVICE_NOT_FOUND", "That phone is not paired.", status_code=404)
        self._revoke(session, device, correlation_id)
        session.commit()

    def revoke_all(self, session: Session, correlation_id: str) -> int:
        devices = self.list_devices(session)
        for device in devices:
            self._revoke(session, device, correlation_id)
        session.commit()
        return len(devices)

    def _revoke(self, session: Session, device: MobileDevice, correlation_id: str) -> None:
        device.revoked_at = datetime.now(UTC)
        record_audit_event(
            session,
            action="mobile.device_revoked",
            entity_type="mobile_device",
            entity_id=device.id,
            correlation_id=correlation_id,
            summary={},
        )
        logger.info(
            "Phone access revoked",
            extra={"event": "mobile_device_revoked", "device_id": device.id},
        )
