$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sidecar = Join-Path $repoRoot "apps\desktop\src-tauri\resources\ens-backend\ens-backend.exe"
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$smokeDirectory = Join-Path $tempRoot ("ens-sidecar-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $smokeDirectory | Out-Null

$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()

$token = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
$env:ENS_HOST = "127.0.0.1"
$env:ENS_PORT = $port.ToString()
$env:ENS_SESSION_TOKEN = $token
$env:ENS_DATABASE_PATH = Join-Path $smokeDirectory "smoke.db"
$env:ENS_LOG_DIRECTORY = Join-Path $smokeDirectory "logs"

$process = Start-Process -FilePath $sidecar -ArgumentList "serve" -PassThru -WindowStyle Hidden
try {
    $result = $null
    for ($attempt = 0; $attempt -lt 150; $attempt++) {
        if ($process.HasExited) {
            throw "Sidecar exited during startup with code $($process.ExitCode)"
        }
        try {
            $result = Invoke-RestMethod `
                -Uri ("http://127.0.0.1:{0}/api/v1/health" -f $port) `
                -Headers @{ "X-Session-Token" = $token } `
                -TimeoutSec 1
            break
        }
        catch {
            Start-Sleep -Milliseconds 100
        }
    }
    if ($null -eq $result -or $result.status -ne "ok") {
        throw "Sidecar health check did not succeed"
    }
    [PSCustomObject]@{
        Status = $result.status
        BindHost = "127.0.0.1"
        DatabaseCreated = Test-Path -LiteralPath $env:ENS_DATABASE_PATH
    } | Format-List
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        $process.WaitForExit()
    }
    Start-Sleep -Milliseconds 200
    $resolvedSmokeDirectory = [IO.Path]::GetFullPath($smokeDirectory)
    if (-not $resolvedSmokeDirectory.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove smoke directory outside the system temp directory"
    }
    Remove-Item -LiteralPath $resolvedSmokeDirectory -Recurse -Force
}

