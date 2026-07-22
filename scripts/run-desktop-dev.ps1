param(
    [switch]$PreflightOnly
)

$ErrorActionPreference = "Stop"

function Get-DesktopPortListener {
    Get-NetTCPConnection `
        -State Listen `
        -LocalAddress "127.0.0.1" `
        -LocalPort 1420 `
        -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Get-ProcessDetails([int]$ProcessId) {
    Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
}

function Test-EtchNShineDevServer($ProcessDetails) {
    if ($null -eq $ProcessDetails -or $ProcessDetails.Name -ne "node.exe") {
        return $false
    }

    $commandLine = [string]$ProcessDetails.CommandLine
    if ($commandLine -notmatch "(?i)vite" -or $commandLine -notmatch "--port\s+1420") {
        return $false
    }

    try {
        $response = Invoke-WebRequest `
            -Uri "http://127.0.0.1:1420" `
            -UseBasicParsing `
            -TimeoutSec 2
        return $response.Content -match "Etch.+Shine Lead Generation"
    }
    catch {
        return $false
    }
}

function Focus-RunningDesktopApp {
    $desktopApp = Get-CimInstance Win32_Process `
        -Filter "Name = 'ens-lead-generation-desktop.exe'" `
        -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $desktopApp) {
        return $false
    }

    try {
        $shell = New-Object -ComObject WScript.Shell
        [void]$shell.AppActivate([int]$desktopApp.ProcessId)
    }
    catch {
        # The app is still running even if Windows declines the focus request.
    }
    return $true
}

function Assert-DesktopDevPortAvailable {
    if (Focus-RunningDesktopApp) {
        Write-Output "Etch N Shine is already running. The existing desktop window was selected."
        exit 0
    }

    $listener = Get-DesktopPortListener
    if ($null -eq $listener) {
        return
    }

    $owner = Get-ProcessDetails -ProcessId ([int]$listener.OwningProcess)
    if (-not (Test-EtchNShineDevServer -ProcessDetails $owner)) {
        $ownerName = if ($null -ne $owner) { $owner.Name } else { "unknown process" }
        throw "Port 1420 is used by $ownerName (PID $($listener.OwningProcess)). Close that program, then start Etch N Shine again."
    }

    $parent = Get-ProcessDetails -ProcessId ([int]$owner.ParentProcessId)
    if ($null -ne $parent) {
        Write-Output "Etch N Shine is already starting in another command window (Vite PID $($owner.ProcessId))."
        exit 0
    }

    Write-Output "Removing orphaned Etch N Shine development server (PID $($owner.ProcessId))..."
    Stop-Process -Id ([int]$owner.ProcessId) -Force
    for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
        if ($null -eq (Get-DesktopPortListener)) {
            return
        }
        Start-Sleep -Milliseconds 100
    }
    throw "The orphaned development server did not release port 1420. Restart Windows, then try again."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    throw "LOCALAPPDATA is not available; the safe desktop build directory cannot be selected."
}

$env:CARGO_TARGET_DIR = Join-Path $env:LOCALAPPDATA "EtchNShine\Build\cargo-target"
New-Item -ItemType Directory -Path $env:CARGO_TARGET_DIR -Force | Out-Null

Write-Output "Desktop build cache: $env:CARGO_TARGET_DIR"

Assert-DesktopDevPortAvailable
if ($PreflightOnly) {
    Write-Output "Desktop development port is ready."
    exit 0
}

Push-Location $repoRoot
try {
    & npm.cmd run tauri --workspace "@ens/desktop" -- dev
    if ($LASTEXITCODE -ne 0) {
        throw "Tauri desktop development host failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
