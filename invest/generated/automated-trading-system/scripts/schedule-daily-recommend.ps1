#Requires -Version 5.1
<#
.SYNOPSIS
  Run or register the daily A-share recommend report.

.EXAMPLE
  # One-off run
  .\schedule-daily-recommend.ps1

.EXAMPLE
  # Register Windows Task Scheduler job (weekdays 15:35)
  .\schedule-daily-recommend.ps1 -Register

.EXAMPLE
  .\schedule-daily-recommend.ps1 -Unregister
#>
param(
  [switch]$Register,
  [switch]$Unregister,
  [string]$TaskName = "AShareDailyRecommend",
  [string]$Time = "15:35"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ($Unregister) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Unregistered task: $TaskName"
  exit 0
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

$ArgList = "-m trading_system.cli.main recommend daily"
$WorkDir = $Root

if ($Register) {
  $action = New-ScheduledTaskAction -Execute $Python -Argument $ArgList -WorkingDirectory $WorkDir
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $Time
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Write-Host "Registered '$TaskName' at $Time on weekdays."
  Write-Host "Ensure .env is configured under: $Root"
  exit 0
}

Write-Host "Running daily recommend..."
& $Python -m trading_system.cli.main recommend daily
exit $LASTEXITCODE
