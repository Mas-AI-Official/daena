# cleanup-stale-dev.ps1 (Sprint-6 PR-1, 2026-05-04)
#
# Combined safe cleanup of stale Daena dev processes.
# Calls the existing path-scoped helpers. Does NOT kill unrelated
# python.exe / node.exe processes elsewhere on the system.
#
# Usage:
#   pwsh.exe -NoProfile -ExecutionPolicy Bypass -File scripts\cleanup-stale-dev.ps1
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\cleanup-stale-dev.ps1
#
# What this DOES kill:
#   * python.exe whose CommandLine references "uvicorn app.main:app"
#     (any worker/parent for THIS repo's backend, since the package
#      name is repo-specific)
#   * node.exe Vite/npm-run-dev processes whose CommandLine references
#     THIS repo's frontend directory
#   * any process still LISTENING on :8000 only after the above pass
#   * any process still LISTENING on :5173 IF its image path is inside
#     THIS repo's frontend (otherwise SKIP with a notice)
#
# What this NEVER kills:
#   * llama-server.exe (Daena talks to it; killing breaks local LLM)
#   * contentops dashboards, MCP servers, local-llm-bridge
#   * other Vite projects living outside D:\Ideas\Daena\frontend
#   * other Python projects living outside this repo

$ErrorActionPreference = 'SilentlyContinue'
$here = $PSScriptRoot

Write-Host ""
Write-Host " === Daena dev cleanup (path-scoped) ==="
Write-Host ""

Write-Host " [1/2] Backend (uvicorn app.main:app)..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here '_dev_kill_uvicorn.ps1')

Start-Sleep -Seconds 2

Write-Host ""
Write-Host " [2/2] Frontend (Vite for this repo only)..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here '_dev_kill_frontend.ps1')

Start-Sleep -Seconds 1

Write-Host ""
Write-Host " === Final port state ==="
$ports = @(8000, 5173)
foreach ($p in $ports) {
    $listen = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($listen) {
        foreach ($c in $listen) {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            $procName = if ($proc) { $proc.ProcessName } else { '?' }
            $procPath = if ($proc) { $proc.Path } else { '?' }
            Write-Host (" :{0} STILL LISTENING -> PID {1} ({2}) {3}" -f $p, $c.OwningProcess, $procName, $procPath)
        }
    } else {
        Write-Host (" :{0} free" -f $p)
    }
}
Write-Host ""

exit 0
