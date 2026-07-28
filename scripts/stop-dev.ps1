$ErrorActionPreference = "Stop"

$port = 8010
$listeningLines = netstat -ano -p tcp |
    Select-String ":$port" |
    Select-String "LISTENING"

if (-not $listeningLines) {
    Write-Host "No backend process is listening on port $port."
    exit 0
}

$processIds = $listeningLines |
    ForEach-Object {
        $tokens = $_.ToString() -split "\s+"
        $tokens[-1]
    } |
    Where-Object { $_ -match "^\d+$" } |
    Sort-Object -Unique

foreach ($processIdValue in $processIds) {
    $taskkillProcess = Start-Process -FilePath "taskkill.exe" `
        -ArgumentList "/PID", "$processIdValue", "/T", "/F" `
        -NoNewWindow `
        -Wait `
        -PassThru

    if ($taskkillProcess.ExitCode -eq 0) {
        Write-Host "Stopped process $processIdValue on port $port."
    } else {
        Write-Host "Process $processIdValue was already gone or could not be stopped cleanly."
    }
}

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    $remainingListeners = netstat -ano -p tcp |
        Select-String ":$port" |
        Select-String "LISTENING"
    if (-not $remainingListeners) {
        Write-Host "Port $port is now free."
        exit 0
    }
    Start-Sleep -Milliseconds 250
}

Write-Host "Port $port is still occupied after attempting to stop the backend."
exit 1
