# Troubleshooting

## Desktop reports that the backend is unavailable

- Use the error’s correlation reference and inspect `%LOCALAPPDATA%\EtchNShine\LeadGeneration\logs`.
- Confirm no endpoint/security product quarantined `ens-backend.exe`.
- In development, run `uv sync --all-packages --dev --locked` and confirm `apps\backend\app\cli.py` exists.
- Run the sidecar and packaged-host smoke commands from `BUILD_AND_PACKAGE.md` to distinguish Python packaging from UI problems.

## `npm.ps1` cannot run

The local execution policy may block PowerShell shims. Use `npm.cmd`, or invoke repository scripts through the provided npm commands. Do not weaken machine-wide execution policy for this project.

## Cargo build fails with access denied or file locks

Keep Cargo output outside the Dropbox workspace:

```powershell
$env:CARGO_TARGET_DIR = Join-Path $env:LOCALAPPDATA 'EtchNShine\Build\cargo-target'
```

The checked-in development, build and quality scripts already do this. Restart with `Start Etch N Shine.cmd`. The launcher now detects an existing desktop window and selects it; it also removes a verified orphaned Etch N Shine Vite process before starting. If an unrelated program owns port 1420, the launcher reports its name and process ID instead of terminating it. Do not open `http://127.0.0.1:1420` directly: that page has no desktop-managed API session when the Tauri host has failed.

## Database is locked

Wait for the current local operation, confirm only one desktop/backend instance is active, and retry. SQLite uses WAL and a five-second busy timeout, but it is not a multi-user network database. Runtime data must remain in local AppData, not a sync folder or network share.

## Migration or startup fails

Do not edit tables manually. Preserve the database and logs, create a filesystem-level incident copy only after the app is stopped, and verify the latest application backup. Record the Alembic revision from its manifest. Use the restore runbook if necessary.

## Installer warning or quarantine

The current NSIS installer is unsigned, so Windows reputation warnings are expected. Treat it as a development/pilot artefact. Production distribution requires code signing and clean-profile validation.

## Resetting disposable development data

Set `ENS_DATABASE_PATH` to a dedicated temporary path for tests. Do not delete the default AppData database unless it is confirmed to contain no needed data and a verified backup exists. Automated tests already use isolated temporary databases.
