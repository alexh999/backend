param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$NoReload
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot

$pythonExe = Join-Path $scriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: Project virtual environment Python was not found at: $pythonExe" -ForegroundColor Red
    exit 1
}

Write-Host "Applying database migrations..."
& $pythonExe -m alembic upgrade head

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Database migration failed. Backend server was not started." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Database is up to date. Starting backend server..."
$arguments = @("-m", "uvicorn", "app.main:app", "--host", $BindHost, "--port", $Port)

if (-not $NoReload) {
    $arguments += "--reload"
}

& $pythonExe @arguments
exit $LASTEXITCODE
