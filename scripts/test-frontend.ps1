$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$coverageDirectory = Join-Path $env:LOCALAPPDATA "EtchNShine\Build\frontend-coverage"
New-Item -ItemType Directory -Path $coverageDirectory -Force | Out-Null

Push-Location $repoRoot
try {
    & npm.cmd run test --workspace "@ens/frontend" -- "--coverage.reportsDirectory=$coverageDirectory"
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend tests failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
