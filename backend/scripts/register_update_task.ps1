# Creates (or replaces) a weekly Windows scheduled task that updates exchange rates and
# spot prices. Run once from PowerShell (no administrator rights needed):
#   powershell -ExecutionPolicy Bypass -File backend\scripts\register_update_task.ps1
#
# To remove it later:
#   Unregister-ScheduledTask -TaskName "Metals Tracker - update data" -Confirm:$false

$taskName = "Metals Tracker - update data"
$script = Join-Path $PSScriptRoot "update_data.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""

# Every Monday at 9:00 AM. Each run uses about 1 metals.dev request (100 allowed per month).
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9:00AM

# If the computer was off or asleep at 9:00, run as soon as possible afterwards.
# Stop it if it somehow runs for more than 10 minutes.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# Runs as you, only while you're signed in, so no password has to be stored.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Downloads the latest USD/CAD rates and metal spot prices for Metals Tracker." `
    -Force | Out-Null

$task = Get-ScheduledTask -TaskName $taskName
$info = $task | Get-ScheduledTaskInfo
Write-Output "Registered '$taskName'. Next run: $($info.NextRunTime)"
