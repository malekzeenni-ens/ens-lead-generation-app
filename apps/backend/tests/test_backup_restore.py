from __future__ import annotations

import base64
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import cast
from zipfile import ZipFile

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
        "schema_version": "0016_seed_outreach_templates",
        "assistant_files_present": False,
        "assistant_files_checksum_matches": None,
        "assistant_files_count": 0,
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


def test_backup_bundles_and_restores_assistant_file_bytes(
    client: TestClient, app: FastAPI, tmp_path: Path
) -> None:
    from tests.test_general_assistant import FakeGeneralAssistantManager

    app.state.campaign_assistant_manager = FakeGeneralAssistantManager()
    conversation = client.post("/api/v1/assistant/conversations", json={}).json()
    upload = client.post(
        f"/api/v1/assistant/conversations/{conversation['id']}/messages",
        json={
            "content": "Keep this reference",
            "attachments": [
                {
                    "filename": "brief.txt",
                    "media_type": "text/plain",
                    "content_base64": base64.b64encode(b"Target Luton bakeries.").decode(),
                }
            ],
        },
    )
    assert upload.status_code == 200

    backup_directory = tmp_path / "backups"
    backup = client.post(
        "/api/v1/backups", json={"target_directory": str(backup_directory)}
    ).json()
    assert backup["assistant_files_count"] == 1
    archive_path = Path(backup["assistant_files_archive"])
    assert archive_path.is_file()

    verification = client.post(
        "/api/v1/backups/verify", json={"backup_path": backup["backup_path"]}
    ).json()
    assert verification["valid"] is True
    assert verification["assistant_files_present"] is True
    assert verification["assistant_files_checksum_matches"] is True
    assert verification["assistant_files_count"] == 1

    restored = tmp_path / "restore-test" / "restored.sqlite3"
    application = cast(FastAPI, client.app)
    result = BackupService(application.state.settings.database_path).restore_to_isolated_path(
        Path(backup["backup_path"]), restored
    )
    assert result.valid
    assert result.assistant_files_present is True
    restored_files_directory = restored.parent / "assistant_files"
    restored_files = list(restored_files_directory.glob("*.txt"))
    assert len(restored_files) == 1
    assert restored_files[0].read_bytes() == b"Target Luton bakeries."

    with ZipFile(archive_path, "a") as archive:
        archive.writestr("extra-injected-file.txt", "unexpected")
    tampered_result = BackupService(application.state.settings.database_path).verify(
        Path(backup["backup_path"])
    )
    assert tampered_result.assistant_files_checksum_matches is False
    assert tampered_result.valid is False
