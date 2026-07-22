# Backup and restore

## Principles

Never copy the live `.db`, `.db-wal`, and `.db-shm` files as an application backup. The backup service uses SQLite’s online backup API, then runs `PRAGMA integrity_check`, atomically publishes the snapshot, calculates SHA-256, and writes a JSON manifest containing the schema and application versions.

## Create and verify a backup

From `apps/backend`, using the default local AppData database:

```powershell
$backupDirectory = Join-Path $env:USERPROFILE 'Documents\EtchNShineBackups'
uv run python -m app.cli backup --target $backupDirectory
```

The JSON output contains the exact `.sqlite3` and `.manifest.json` paths. Verify before relying on it:

```powershell
uv run python -m app.cli verify-backup --backup 'C:\exact\path\ens-leads-...sqlite3'
```

A usable result has `valid: true`, `checksum_matches: true`, and `integrity_result: "ok"`. Store the database and matching manifest together. Periodically copy verified backups to a second approved, access-controlled location and test recovery.

## Test an isolated restore

```powershell
uv run python -m app.cli restore-isolated `
  --backup 'C:\exact\path\ens-leads-...sqlite3' `
  --destination 'C:\exact\recovery-test\restored.sqlite3'
```

The destination cannot be the configured active database, and an existing destination is rejected unless `--replace` is supplied. Open the isolated result only in a deliberately configured test run.

## Recover the active database

The current release intentionally has no one-click live restore. For a real recovery:

1. Create and verify a fresh backup if the damaged database is still readable.
2. Verify the chosen recovery backup and restore it to an isolated path.
3. Exit the desktop application and confirm its backend process has stopped.
4. Preserve the existing active database and any WAL/SHM files under a timestamped incident folder; do not overwrite the only copy.
5. Copy the verified isolated database to `%LOCALAPPDATA%\EtchNShine\LeadGeneration\ens-leads.db` while the application is stopped.
6. Start the application, let Alembic apply only forward migrations, inspect campaigns/leads, and immediately create and verify a new backup.
7. Record the selected backup, checksum, schema version, recovery time, operator, and validation result.

If any target path is uncertain, stop and obtain a second review before moving data.
