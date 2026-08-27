param(
    [switch]$CheckOnly,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$appFile = Join-Path $projectRoot "app.py"
$runtimeDirectory = Join-Path $projectRoot "data\runtime"
$serverStateFile = Join-Path $runtimeDirectory "youffice_server.json"
$serverUrl = "http://127.0.0.1:8501"

function Test-YoufficeHealth {
    try {
        $health = Invoke-WebRequest -UseBasicParsing "$serverUrl/_stcore/health" -TimeoutSec 3
        return $health.StatusCode -eq 200 -and $health.Content.Trim() -eq "ok"
    }
    catch {
        return $false
    }
}

function Get-ServerState {
    if (-not (Test-Path -LiteralPath $serverStateFile)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $serverStateFile -Raw | ConvertFrom-Json
    }
    catch {
        Remove-Item -LiteralPath $serverStateFile -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Test-ManagedServerRunning($state) {
    if ($null -eq $state -or $state.project_root -ne $projectRoot) {
        return $false
    }
    try {
        $process = Get-Process -Id ([int]$state.process_id) -ErrorAction Stop
        return $process.Path -eq $pythonExe
    }
    catch {
        return $false
    }
}

function Save-ServerState([int]$processId) {
    New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
    [ordered]@{
        project_root = $projectRoot
        process_id = $processId
        started_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $serverStateFile -Encoding utf8
}

function Remove-ServerState {
    Remove-Item -LiteralPath $serverStateFile -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Host "[YOUFFICE] Python environment not found: $pythonExe" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Test-Path -LiteralPath $appFile)) {
    Write-Host "[YOUFFICE] app.py not found: $appFile" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

Set-Location $projectRoot

Write-Host "[YOUFFICE] Starting system check..."
& $pythonExe ".\tools\preflight_check.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[YOUFFICE] System check failed." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

if ($CheckOnly) {
    Write-Host "[YOUFFICE] System check passed."
    exit 0
}

$state = Get-ServerState
$managedServerRunning = Test-ManagedServerRunning $state
$healthOk = Test-YoufficeHealth

if ($managedServerRunning -and $healthOk) {
    Write-Host "[YOUFFICE] The managed server is already running (PID $($state.process_id))." -ForegroundColor Green
    Write-Host "Opening the existing YOUFFICE page."
    if (-not $NoBrowser) {
        Start-Process $serverUrl
    }
    exit 0
}

if ($null -ne $state -and -not $managedServerRunning) {
    Remove-ServerState
}

$listener = Get-NetTCPConnection -State Listen -LocalPort 8501 -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    if ($healthOk) {
        Write-Host "[YOUFFICE] A healthy Streamlit server is already using port 8501 (PID $($listener.OwningProcess))." -ForegroundColor Yellow
        Write-Host "It is not recorded as this launcher's server, so it will not be closed automatically."
        Write-Host "Use the existing browser page, or close only the confirmed old server before starting again."
        if (-not $NoBrowser) {
            Start-Process $serverUrl
        }
        exit 0
    }

    Write-Host "[YOUFFICE] Port 8501 is in use by another program (PID $($listener.OwningProcess))." -ForegroundColor Yellow
    Write-Host "Close only that confirmed program, then run this launcher again."
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host ""
Write-Host "[YOUFFICE] System check passed. Starting one managed server..."
$serverProcess = Start-Process -FilePath $pythonExe -ArgumentList @(
    "-m", "streamlit", "run", $appFile,
    "--server.address", "127.0.0.1",
    "--server.port", "8501"
) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
Save-ServerState $serverProcess.Id

$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
    if (Test-YoufficeHealth) {
        Write-Host "[YOUFFICE] Server started successfully (PID $($serverProcess.Id))." -ForegroundColor Green
        if (-not $NoBrowser) {
            Start-Process $serverUrl
        }
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

if (-not (Get-Process -Id $serverProcess.Id -ErrorAction SilentlyContinue)) {
    Remove-ServerState
}
Write-Host "[YOUFFICE] The server did not become ready within 15 seconds." -ForegroundColor Red
Write-Host "Check the terminal or run the system check again."
Read-Host "Press Enter to close"
exit 1
