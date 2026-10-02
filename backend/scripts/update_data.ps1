# Runs "python -m app.update_data" and appends its output to backend\logs\update_data.log.
# Used by the weekly scheduled task (see register_update_task.ps1), but can also be run by hand:
#   powershell -ExecutionPolicy Bypass -File backend\scripts\update_data.ps1

$backend = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $backend "logs"
$logFile = Join-Path $logDir "update_data.log"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# Scheduled tasks don't always have uv on their PATH, so use its full path.
$uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"

Set-Location $backend
Add-Content -Path $logFile -Encoding utf8 -Value "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# Python prints UTF-8; capture stdout and stderr together into the log.
$env:PYTHONIOENCODING = "utf-8"
$output = & $uv run python -m app.update_data 2>&1
$exitCode = $LASTEXITCODE
Add-Content -Path $logFile -Encoding utf8 -Value ($output | ForEach-Object { "$_" })
Add-Content -Path $logFile -Encoding utf8 -Value "(exit code $exitCode)"

# A non-zero exit code shows up as "Last Run Result" in Task Scheduler.
exit $exitCode
