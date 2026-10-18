from __future__ import annotations

import argparse
import json
import traceback
from datetime import UTC, datetime
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


def _serve(settings: Settings) -> None:
    """Run the API. A startup failure is also written to `startup-error.log`, because the desktop
    host may not show the process's own output."""
    try:
        app = create_app(settings)
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=settings.host,
                port=settings.port,
                access_log=False,
                server_header=False,
                log_config=None,
            )
        )
        # Lets the authenticated shutdown endpoint stop the server cleanly.
        app.state.server = server
    except Exception:
        (settings.log_directory / "startup-error.log").write_text(
            f"{datetime.now(UTC).isoformat()}\n{traceback.format_exc()}", encoding="utf-8"
        )
        raise
    server.run()


def main() -> None:
    args = _parser().parse_args()
    settings = Settings()
    settings.prepare_directories()
    if args.command == "serve":
        _serve(settings)
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
