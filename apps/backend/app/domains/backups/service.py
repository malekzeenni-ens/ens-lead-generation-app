from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app import __version__
from app.core.errors import DomainError
from app.db.models import BackupManifest
from app.domains.backups.schemas import BackupResult, VerificationResult


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inspect_database(path: Path) -> tuple[str, str]:
    with closing(sqlite3.connect(path)) as connection:
        integrity_row = connection.execute("PRAGMA integrity_check").fetchone()
        version_row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    integrity = str(integrity_row[0]) if integrity_row else "missing"
    version = str(version_row[0]) if version_row else "unknown"
    return integrity, version


class BackupService:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()

    def create(self, session: Session, target_directory: Path) -> BackupResult:
        target = target_directory.expanduser().resolve()
        if target == self.database_path or (target.exists() and not target.is_dir()):
            raise DomainError(
                "BACKUP_TARGET_INVALID",
                "Backup target must be a directory and cannot be the active database.",
            )
        target.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(UTC)
        stem = f"ens-leads-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        backup_path = target / f"{stem}.sqlite3"
        temporary_path = target / f".{stem}.tmp"
        manifest_path = target / f"{stem}.manifest.json"

        try:
            with (
                closing(sqlite3.connect(self.database_path)) as source,
                closing(sqlite3.connect(temporary_path)) as destination,
            ):
                source.backup(destination)
            integrity, schema_version = _inspect_database(temporary_path)
            if integrity != "ok":
                raise DomainError(
                    "BACKUP_INTEGRITY_FAILED",
                    "The backup failed its SQLite integrity check.",
                    details={"integrity_result": integrity},
                )
            os.replace(temporary_path, backup_path)
            checksum = _checksum(backup_path)
            manifest = {
                "backup_filename": backup_path.name,
                "checksum_sha256": checksum,
                "integrity_result": integrity,
                "schema_version": schema_version,
                "application_version": __version__,
                "created_at": created_at.isoformat(),
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
            )
            session.add(
                BackupManifest(
                    backup_filename=backup_path.name,
                    checksum_sha256=checksum,
                    integrity_result=integrity,
                    schema_version=schema_version,
                    application_version=__version__,
                )
            )
            session.commit()
            return BackupResult(
                backup_path=backup_path,
                manifest_path=manifest_path,
                checksum_sha256=checksum,
                integrity_result=integrity,
                schema_version=schema_version,
                application_version=__version__,
                created_at=created_at,
            )
        finally:
            temporary_path.unlink(missing_ok=True)

    def verify(self, backup_path: Path) -> VerificationResult:
        resolved = backup_path.expanduser().resolve()
        manifest_path = resolved.with_name(resolved.name.replace(".sqlite3", ".manifest.json"))
        if not resolved.is_file() or not manifest_path.is_file():
            raise DomainError(
                "BACKUP_NOT_FOUND",
                "The backup database or its manifest was not found.",
                status_code=404,
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        actual_checksum = _checksum(resolved)
        integrity, schema_version = _inspect_database(resolved)
        checksum_matches = actual_checksum == manifest.get("checksum_sha256")
        return VerificationResult(
            valid=checksum_matches and integrity == "ok",
            checksum_matches=checksum_matches,
            integrity_result=integrity,
            schema_version=schema_version,
        )

    def restore_to_isolated_path(
        self, backup_path: Path, destination_path: Path, *, replace: bool = False
    ) -> VerificationResult:
        verification = self.verify(backup_path)
        if not verification.valid:
            raise DomainError(
                "BACKUP_INVALID", "The backup failed verification and was not restored."
            )
        destination = destination_path.expanduser().resolve()
        if destination == self.database_path:
            raise DomainError(
                "ACTIVE_DATABASE_RESTORE_BLOCKED",
                (
                    "Stop the application and use the maintenance restore command for the "
                    "active database."
                ),
            )
        if destination.exists() and not replace:
            raise DomainError(
                "RESTORE_DESTINATION_EXISTS",
                "Restore destination exists; explicit replacement is required.",
                status_code=409,
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            with (
                closing(sqlite3.connect(backup_path.expanduser().resolve())) as source,
                closing(sqlite3.connect(temporary)) as target,
            ):
                source.backup(target)
            restored_integrity, restored_version = _inspect_database(temporary)
            if restored_integrity != "ok":
                raise DomainError("RESTORE_INTEGRITY_FAILED", "The restored database is not valid.")
            os.replace(temporary, destination)
            return VerificationResult(
                valid=True,
                checksum_matches=True,
                integrity_result=restored_integrity,
                schema_version=restored_version,
            )
        finally:
            temporary.unlink(missing_ok=True)
