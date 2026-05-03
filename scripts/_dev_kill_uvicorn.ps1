# _dev_kill_uvicorn.ps1
# Helper for scripts/start-backend-dev.bat.
#
# Kills every python.exe whose CommandLine references
# "uvicorn app.main:app" (covers BOTH the .venv launcher parent
# AND its base-interpreter child -- the netstat PID is usually
# only the child, but the parent owns the listening socket).
#
# Exits 0 always so the caller continues regardless. Prints one
# line per kill so the .bat can echo it through.
#
# This script intentionally targets ONLY the uvicorn-bound python
# processes -- it leaves other python.exe instances (local-llm
# bridge, contentops, MCP servers) untouched.

$ErrorActionPreference = 'SilentlyContinue'

$matches = Get-CimInstance Win32_Process -Filter "name='python.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -match 'uvicorn\s+app\.main:app' }

if (-not $matches) {
    Write-Host "       (no uvicorn app.main:app processes found)"
    exit 0
}

foreach ($p in $matches) {
    $cmdShort = $p.CommandLine
    if ($cmdShort.Length -gt 90) { $cmdShort = $cmdShort.Substring(0, 90) + '...' }
    Write-Host ("       Killing PID {0,-6} ({1})" -f $p.ProcessId, $cmdShort)
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

exit 0
