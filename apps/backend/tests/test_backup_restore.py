from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import DomainError
from app.domains.backups.service import BackupService
from tests.conftest import lead_payload


def test_consistent_backup_verification_and_isolated_restore(
    client: TestClient,
    tmp_path: Path,
    campaign_payload: dict[str, object],
) -> None:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    assert client.post("/api/v1/leads", json=lead_payload(campaign["id"])).status_code == 201

    backup_directory = tmp_path / "backups"
    response = client.post("/api/v1/backups", json={"target_directory": str(backup_directory)})
    assert response.status_code == 201
    backup = response.json()
    backup_path = Path(backup["backup_path"])
    assert backup_path.is_file()
    assert Path(backup["manifest_path"]).is_file()
    assert backup["integrity_result"] == "ok"
    assert len(backup["checksum_sha256"]) == 64

    verification = client.post("/api/v1/backups/verify", json={"backup_path": str(backup_path)})
    assert verification.status_code == 200
    assert verification.json() == {
        "valid": True,
        "checksum_matches": True,
        "integrity_result": "ok",
        "schema_version": "0008_template_product_families",
    }

    restored = tmp_path / "restore-test" / "restored.sqlite3"
    application = cast(FastAPI, client.app)
    result = BackupService(application.state.settings.database_path).restore_to_isolated_path(
        backup_path, restored
    )
    assert result.valid
    with closing(sqlite3.connect(restored)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM campaign").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM lead").fetchone()[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    with pytest.raises(DomainError, match="Stop the application"):
        BackupService(application.state.settings.database_path).restore_to_isolated_path(
            backup_path, application.state.settings.database_path
        )

    tampered_directory = tmp_path / "tampered"
    tampered_directory.mkdir()
    tampered_backup = tampered_directory / backup_path.name
    tampered_manifest = tampered_directory / Path(backup["manifest_path"]).name
    shutil.copy2(backup_path, tampered_backup)
    shutil.copy2(Path(backup["manifest_path"]), tampered_manifest)
    with tampered_backup.open("ab") as handle:
        handle.write(b"tampered")

    tampered_result = BackupService(application.state.settings.database_path).verify(
        tampered_backup
    )
    assert not tampered_result.valid
    assert not tampered_result.checksum_matches
