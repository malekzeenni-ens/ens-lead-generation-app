# Build and package

## Development artefacts

Build and smoke-test the packaged Python backend:

```powershell
npm.cmd run desktop:sidecar
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/test-backend-sidecar.ps1
```

The build script creates a PyInstaller `onedir` resource at `apps\desktop\src-tauri\resources\ens-backend`. Generated binaries are ignored by Git; only the explanatory `README.md` is versioned. Alembic configuration and migrations are bundled with the executable.

## Windows installer

```powershell
npm.cmd run desktop:build
```

The command rebuilds the backend resource and frontend, compiles the Tauri release host, creates an NSIS installer, and copies it to `artifacts\`. Cargo output is deliberately placed under `%LOCALAPPDATA%\EtchNShine\Build\cargo-target` to avoid Dropbox file-locking problems.

Smoke-test the exact release host and bundled backend without opening a UI:

```powershell
$releaseExe = Join-Path $env:LOCALAPPDATA 'EtchNShine\Build\cargo-target\release\ens-lead-generation-desktop.exe'
& $releaseExe --smoke-test
```

The command starts the packaged backend against a disposable database on an ephemeral loopback port, performs an authenticated health request, terminates the child, and removes its test directory.

Generate release evidence:

```powershell
Get-ChildItem -LiteralPath artifacts -Filter '*setup.exe' | Get-FileHash -Algorithm SHA256
```

## Current packaging status

The Windows NSIS build and packaged-host smoke test pass on the kickoff machine. The installer is unsigned and has not passed a separate clean-profile install/uninstall exercise. Do not distribute it as a production release until code signing, provenance, clean-profile installation, backup upgrade/recovery, and pilot acceptance gates are complete.
