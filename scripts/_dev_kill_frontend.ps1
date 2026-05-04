# _dev_kill_frontend.ps1 (Sprint-6 PR-1, 2026-05-04)
# Kills stale Vite dev-server processes for THIS repo's frontend only.
#
# Two-pass strategy mirroring _dev_kill_uvicorn.ps1:
#   Pass A: kill any node.exe whose CommandLine matches a Vite dev signature
#           AND whose CWD or CommandLine references THIS repo's frontend
#           directory. Path-scoped so we never kill a contentops or
#           unrelated Vite project living elsewhere.
#   Pass B: backstop -- kill anything still listening on :5173.
#
# Exits 0 always; prints one line per kill.

$ErrorActionPreference = 'SilentlyContinue'

$repoFrontend = (Resolve-Path "$PSScriptRoot\..\frontend").Path
# Normalise to forward slashes for substring match (CommandLine may use either).
$frontendForward = $repoFrontend.Replace('\', '/')
$frontendBack = $repoFrontend

Write-Host "       Frontend dir: $repoFrontend"

# Pass A: path-scoped node.exe kills.
$matches = Get-CimInstance Win32_Process -Filter "name='node.exe'" |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -match 'vite' -or
            $_.CommandLine -match 'npm.*run.*dev'
        ) -and (
            $_.CommandLine -match [regex]::Escape($frontendBack) -or
            $_.CommandLine -match [regex]::Escape($frontendForward)
        )
    }

if (-not $matches) {
    Write-Host "       (no path-scoped node/vite processes found)"
} else {
    foreach ($p in $matches) {
        $cmdShort = $p.CommandLine
        if ($cmdShort.Length -gt 90) { $cmdShort = $cmdShort.Substring(0, 90) + '...' }
        Write-Host ("       Killing PID {0,-6} ({1})" -f $p.ProcessId, $cmdShort)
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

# Pass B: backstop -- anything still listening on :5173.
$conns = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($conns) {
    foreach ($c in $conns) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            # Safety: confirm the process path is inside this repo before kill.
            $procPath = $proc.Path
            $isOurs = $false
            if ($procPath) {
                if ($procPath -match [regex]::Escape($repoFrontend)) { $isOurs = $true }
            }
            # Heuristic fallback: node.exe processes on :5173 with no path
            # info we can resolve are still likely Vite -- but only if no
            # other Vite project is running. We err on the side of NOT
            # killing if we can't confirm; the user can re-run the script.
            if ($isOurs) {
                Write-Host ("       Pass B kill PID {0} (path-scoped)" -f $proc.Id)
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            } else {
                Write-Host ("       Pass B SKIP PID {0} ({1}) -- not in repo frontend" -f $proc.Id, $procPath)
            }
        }
    }
} else {
    Write-Host "       (port 5173 already free)"
}

exit 0
