$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $repoRoot "apps\backend"
$desktopDirectory = Join-Path $repoRoot "apps\desktop\src-tauri"
$env:CARGO_TARGET_DIR = Join-Path $env:LOCALAPPDATA "EtchNShine\Build\cargo-target"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE"
    }
}

Push-Location $repoRoot
try {
    Invoke-Checked uv lock --check
    Invoke-Checked npm.cmd audit --audit-level=high
    Invoke-Checked npm.cmd run frontend:lint
    Invoke-Checked npm.cmd run frontend:typecheck
    Invoke-Checked npm.cmd run frontend:test
    Invoke-Checked npm.cmd run frontend:build

    Push-Location $backendDirectory
    try {
        Invoke-Checked uv run ruff check app tests
        Invoke-Checked uv run ruff format --check app tests
        Invoke-Checked uv run mypy app tests
        Invoke-Checked uv run pytest -q --cov=app --cov-report=term-missing
    }
    finally {
        Pop-Location
    }

    Push-Location $desktopDirectory
    try {
        Invoke-Checked cargo fmt --check
        Invoke-Checked cargo test --locked
        Invoke-Checked -Executable "cargo" -Arguments @(
            "clippy",
            "--all-targets",
            "--locked",
            "--",
            "-D",
            "warnings"
        )
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}

Write-Output "All local quality gates passed."
