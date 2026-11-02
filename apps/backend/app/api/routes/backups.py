from fastapi import APIRouter, Request, status

from app.api.dependencies import DESKTOP_ONLY, Authenticated, DatabaseSession
from app.domains.backups.schemas import (
    BackupCreate,
    BackupResult,
    BackupVerify,
    VerificationResult,
)
from app.domains.backups.service import BackupService

router = APIRouter(prefix="/backups", tags=["backups"], dependencies=[DESKTOP_ONLY])


@router.post("", response_model=BackupResult, status_code=status.HTTP_201_CREATED)
def create_backup(
    data: BackupCreate, request: Request, _: Authenticated, session: DatabaseSession
) -> BackupResult:
    return BackupService(request.app.state.settings.database_path).create(
        session, data.target_directory
    )


@router.post("/verify", response_model=VerificationResult)
def verify_backup(data: BackupVerify, request: Request, _: Authenticated) -> VerificationResult:
    return BackupService(request.app.state.settings.database_path).verify(data.backup_path)
