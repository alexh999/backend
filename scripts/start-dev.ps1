$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$envPath = Join-Path $projectRoot ".env"
$exampleEnvPath = Join-Path $projectRoot ".env.example"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$port = 8010

Set-Location $projectRoot

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $exampleEnvPath -Destination $envPath
    Write-Host "Created .env from .env.example."
    Write-Host "Fill PANDAAI_USERNAME and PANDAAI_PASSWORD in .env, then rerun this script."
    exit 1
}

$envContent = Get-Content -LiteralPath $envPath -Raw
if ($envContent -match "PANDAAI_USERNAME=your_pandaai_username" -or $envContent -match "PANDAAI_PASSWORD=your_pandaai_password") {
    Write-Host "Replace the placeholder PandaAI credentials in .env before starting the backend."
    exit 1
}

function Test-PythonVersion {
    param(
        [string]$Command,
        [string[]]$Arguments = @()
    )

    & $Command @Arguments -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" | Out-Null
    return $LASTEXITCODE -eq 0
}

$pythonCommand = $null
$pythonArgs = @()
$candidates = @()

if (Test-Path -LiteralPath $venvPython) {
    $candidates += @{ command = $venvPython; args = @() }
}

$pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyLauncher) {
    $candidates += @{ command = $pyLauncher.Source; args = @("-3.12") }
}

$preferred312 = "F:\python 3.12\python.exe"
if (Test-Path -LiteralPath $preferred312) {
    $candidates += @{ command = $preferred312; args = @() }
}

$pythonExe = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pythonExe) {
    $candidates += @{ command = $pythonExe.Source; args = @() }
}

$pythonFallback = Get-Command python -ErrorAction SilentlyContinue
if ($pythonFallback) {
    $candidates += @{ command = $pythonFallback.Source; args = @() }
}

foreach ($candidate in $candidates) {
    if (Test-PythonVersion -Command $candidate.command -Arguments $candidate.args) {
        $pythonCommand = $candidate.command
        $pythonArgs = $candidate.args
        break
    }
}

if (-not $pythonCommand) {
    Write-Host "No Python interpreter was found. Install Python 3.12 or create backend-main/.venv first."
    exit 1
}

$listeningLines = netstat -ano -p tcp |
    Select-String ":$port" |
    Select-String "LISTENING"

if ($listeningLines) {
    $existingProcessIds = $listeningLines |
        ForEach-Object {
            $tokens = $_.ToString() -split "\s+"
            $tokens[-1]
        } |
        Where-Object { $_ -match "^\d+$" } |
        Sort-Object -Unique

    Write-Host "Port $port is already in use by PID(s): $($existingProcessIds -join ', ')."
    Write-Host "Run .\scripts\stop-dev.ps1 first, or stop the existing backend before starting a new one."
    exit 1
}

$dependencyProbeArgs = @()
$dependencyProbeArgs += $pythonArgs
$dependencyProbeArgs += @(
    "-c",
    "import importlib.util, sys; modules=('fastapi','httpx','pydantic_settings','pyarrow','uvicorn'); missing=[m for m in modules if importlib.util.find_spec(m) is None]; print('\n'.join(missing)); sys.exit(1 if missing else 0)"
)

& $pythonCommand @dependencyProbeArgs | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Install the backend dependencies before starting the server:"
    Write-Host '  python -m pip install -e ".[dev]"'
    exit 1
}

$launchArgs = @()
$launchArgs += $pythonArgs
$launchArgs += @(
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "$port",
    "--reload"
)

Write-Host "Starting StockApp backend on http://127.0.0.1:$port with $pythonCommand"
& $pythonCommand @launchArgs
