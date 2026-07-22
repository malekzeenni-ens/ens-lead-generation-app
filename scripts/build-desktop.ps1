$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$env:CARGO_TARGET_DIR = Join-Path $env:LOCALAPPDATA "EtchNShine\Build\cargo-target"

# Vite inlines apps/frontend/.env* values as literals at build time. A leftover
# local-development env file would ship a dev session token/API URL inside the
# release installer's JS bundle.
$frontendDirectory = Join-Path $repoRoot "apps\frontend"
$leftoverEnvFiles = Get-ChildItem -LiteralPath $frontendDirectory -Filter ".env*" -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne ".env.example" }
if ($leftoverEnvFiles) {
    $names = ($leftoverEnvFiles | ForEach-Object { $_.Name }) -join ", "
    throw "Refusing to build a release with local .env file(s) present in apps/frontend: $names. Remove them before building; Vite inlines their values into the bundle."
}

Push-Location $repoRoot
try {
    & npm.cmd run tauri --workspace @ens/desktop -- build
    if ($LASTEXITCODE -ne 0) {
        throw "Tauri desktop build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$bundleDirectory = Join-Path $env:CARGO_TARGET_DIR "release\bundle\nsis"
$installer = Get-ChildItem -LiteralPath $bundleDirectory -File -Filter "*setup.exe" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($null -eq $installer) {
    throw "The NSIS installer was not found in $bundleDirectory"
}

$artifactDirectory = Join-Path $repoRoot "artifacts"
New-Item -ItemType Directory -Path $artifactDirectory -Force | Out-Null
$artifactPath = Join-Path $artifactDirectory $installer.Name
Copy-Item -LiteralPath $installer.FullName -Destination $artifactPath -Force
Write-Output "Created installer artifact: $artifactPath"

