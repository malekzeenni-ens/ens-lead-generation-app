from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from app.core.config import Settings
from app.db.migrations import run_migrations
from app.db.session import Database
from app.domains.backups.service import BackupService
from app.main import create_app


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Etch 'N' Shine local backend maintenance")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="Run the loopback API")
    backup = commands.add_parser("backup", help="Create and verify a consistent backup")
    backup.add_argument("--target", type=Path, required=True)
    verify = commands.add_parser("verify-backup", help="Verify a backup and manifest")
    verify.add_argument("--backup", type=Path, required=True)
    restore = commands.add_parser("restore-isolated", help="Restore to a non-active database path")
    restore.add_argument("--backup", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    restore.add_argument("--replace", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    settings = Settings()
    settings.prepare_directories()
    if args.command == "serve":
        uvicorn.run(
            create_app(settings),
            host=settings.host,
            port=settings.port,
            access_log=False,
            server_header=False,
            log_config=None,
        )
        return

    run_migrations(settings.database_path)
    service = BackupService(settings.database_path)
    if args.command == "backup":
        database = Database(settings.database_path)
        try:
            with database.session_factory() as session:
                backup_result = service.create(session, args.target)
        finally:
            database.close()
        print(backup_result.model_dump_json(indent=2))
    elif args.command == "verify-backup":
        print(service.verify(args.backup).model_dump_json(indent=2))
    elif args.command == "restore-isolated":
        restore_result = service.restore_to_isolated_path(
            args.backup, args.destination, replace=args.replace
        )
        print(restore_result.model_dump_json(indent=2))
    else:
        raise RuntimeError(json.dumps({"error": "unsupported command"}))


if __name__ == "__main__":
    main()
