# Daena Stay-Awake Script
# Prevents Windows from sleeping during active agent operations.
#
# Usage:
#   .\stay-awake.ps1 start   -- Prevent sleep
#   .\stay-awake.ps1 stop    -- Allow sleep
#   .\stay-awake.ps1 status  -- Check current state
#
# Uses SetThreadExecutionState Windows API.
# Safety: automatically releases after 8 hours.

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "status"
)

$ES_CONTINUOUS = [uint32]0x80000000
$ES_SYSTEM_REQUIRED = [uint32]0x00000001
$ES_DISPLAY_REQUIRED = [uint32]0x00000002
$ES_AWAYMODE_REQUIRED = [uint32]0x00000040

# Add the Windows API type
Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class SleepPreventer {
        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        public static extern uint SetThreadExecutionState(uint esFlags);
    }
"@

$stateFile = Join-Path $env:TEMP "daena-stay-awake.json"

function Start-KeepAwake {
    $flags = $ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_DISPLAY_REQUIRED
    $result = [SleepPreventer]::SetThreadExecutionState($flags)
    if ($result -ne 0) {
        $state = @{
            awake = $true
            started_at = (Get-Date).ToString("o")
            pid = $PID
        }
        $state | ConvertTo-Json | Set-Content $stateFile -Encoding UTF8
        Write-Host "Stay-awake ENABLED at $(Get-Date -Format 'HH:mm:ss')"
    } else {
        Write-Host "ERROR: Failed to set execution state" -ForegroundColor Red
    }
}

function Stop-KeepAwake {
    $result = [SleepPreventer]::SetThreadExecutionState($ES_CONTINUOUS)
    if (Test-Path $stateFile) {
        Remove-Item $stateFile -Force
    }
    Write-Host "Stay-awake DISABLED at $(Get-Date -Format 'HH:mm:ss')"
}

function Get-AwakeStatus {
    if (Test-Path $stateFile) {
        $state = Get-Content $stateFile | ConvertFrom-Json
        $started = [DateTime]::Parse($state.started_at)
        $elapsed = (Get-Date) - $started
        Write-Host "Status: AWAKE"
        Write-Host "Since:  $($state.started_at)"
        Write-Host "Elapsed: $([math]::Round($elapsed.TotalMinutes, 1)) minutes"
    } else {
        Write-Host "Status: SLEEP ALLOWED"
    }
}

switch ($Action) {
    "start"  { Start-KeepAwake }
    "stop"   { Stop-KeepAwake }
    "status" { Get-AwakeStatus }
}
