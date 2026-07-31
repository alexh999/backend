param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$NoReload
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot

$pythonExe = Join-Path $scriptRoot ".venv\Scripts\python.exe"
$arguments = @("-m", "uvicorn", "app.main:app", "--host", $BindHost, "--port", $Port)

if (-not $NoReload) {
    $arguments += "--reload"
}

& $pythonExe @arguments
