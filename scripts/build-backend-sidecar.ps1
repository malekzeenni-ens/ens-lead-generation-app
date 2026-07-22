$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $repoRoot "apps\backend"
$sidecarDirectory = Join-Path $repoRoot "apps\desktop\src-tauri\resources\ens-backend"
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$buildRoot = Join-Path $tempRoot ("ens-sidecar-build-" + [guid]::NewGuid().ToString("N"))
$distDirectory = Join-Path $buildRoot "dist"
$workDirectory = Join-Path $buildRoot "build"
$specDirectory = Join-Path $buildRoot "spec"
$alembicConfig = Join-Path $backendDirectory "alembic.ini"
$migrationsDirectory = Join-Path $backendDirectory "migrations"

$resolvedRepoRoot = [IO.Path]::GetFullPath($repoRoot)
$resolvedSidecarDirectory = [IO.Path]::GetFullPath($sidecarDirectory)
if (-not $resolvedSidecarDirectory.StartsWith($resolvedRepoRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to replace a sidecar directory outside the repository"
}

try {
    New-Item -ItemType Directory -Path $specDirectory -Force | Out-Null
    Push-Location $backendDirectory
    try {
        # sqlalchemy's bundled PyInstaller hook collects every sqlalchemy.ext.mypy.*
        # submodule, which imports mypy at analysis time and pulls the dev-only
        # `mypy` package into the customer-facing binary unless excluded here.
        & uv run pyinstaller `
            --noconfirm `
            --clean `
            --onedir `
            --name ens-backend `
            --paths . `
            --distpath $distDirectory `
            --workpath $workDirectory `
            --specpath $specDirectory `
            --add-data "$alembicConfig;." `
            --add-data "$migrationsDirectory;migrations" `
            --collect-all uvicorn `
            --exclude-module mypy `
            app\cli.py
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller sidecar build failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }

    $builtDirectory = Join-Path $distDirectory "ens-backend"
    $builtExecutable = Join-Path $builtDirectory "ens-backend.exe"
    if (-not (Test-Path -LiteralPath $builtExecutable -PathType Leaf)) {
        throw "Expected sidecar executable was not created: $builtExecutable"
    }

    if (Test-Path -LiteralPath $sidecarDirectory) {
        foreach ($item in (Get-ChildItem -LiteralPath $sidecarDirectory -Force)) {
            if ($item.Name -eq "README.md") {
                continue
            }
            $resolvedItem = [IO.Path]::GetFullPath($item.FullName)
            if (-not $resolvedItem.StartsWith($resolvedSidecarDirectory, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to remove a generated sidecar item outside its target directory"
            }
            # This directory lives under a synced folder (e.g. Dropbox), whose sync daemon
            # can briefly hold a read lock on a just-written file. Retry with backoff instead
            # of failing the whole build on that kind of transient contention.
            $maxAttempts = 5
            for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
                try {
                    Remove-Item -LiteralPath $resolvedItem -Recurse -Force -ErrorAction Stop
                    break
                }
                catch {
                    if ($attempt -eq $maxAttempts) {
                        throw
                    }
                    Start-Sleep -Milliseconds (500 * $attempt)
                }
            }
        }
    }
    New-Item -ItemType Directory -Path $sidecarDirectory -Force | Out-Null
    Copy-Item -Path (Join-Path $builtDirectory "*") -Destination $sidecarDirectory -Recurse -Force
    Write-Output "Created Tauri sidecar resource: $sidecarDirectory"
}
finally {
    $resolvedBuildRoot = [IO.Path]::GetFullPath($buildRoot)
    if (-not $resolvedBuildRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a sidecar build directory outside the system temp directory"
    }
    if (Test-Path -LiteralPath $resolvedBuildRoot) {
        Remove-Item -LiteralPath $resolvedBuildRoot -Recurse -Force
    }
}
