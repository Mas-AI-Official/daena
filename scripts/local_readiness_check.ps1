<#
.SYNOPSIS
    Local readiness check for the founder's local-first Daena.

.DESCRIPTION
    Runs a battery of read-only checks against the local stack:
      - backend (FastAPI on .daena-port)
      - frontend (Vite dev on 5173)
      - llama-server (CUDA on 8080)
      - SQLite database file
      - vault KEK presence (boolean only -- never reads value)
      - MODELS_ROOT + Daena-Mind vault directories
      - WSL2 kali-linux availability
      - .env file presence

    Mirrors the structure of production_readiness_check.ps1 but for
    local development. NEVER prints secret values. Returns PASS /
    FAIL / WARN / SKIP per check, exits non-zero if any FAIL.

.PARAMETER BackendUrl
    Backend health URL. Default: discovers from backend/.daena-port,
    falls back to http://127.0.0.1:8000

.PARAMETER FrontendUrl
    Frontend URL. Default: http://127.0.0.1:5173

.PARAMETER LlamaServerUrl
    llama-server URL. Default: http://127.0.0.1:8080

.PARAMETER SkipBrowserChecks
    Skip backend / frontend / llama-server health probes.

.EXAMPLE
    pwsh scripts/local_readiness_check.ps1
    pwsh scripts/local_readiness_check.ps1 -SkipBrowserChecks

.NOTES
    SECURITY: this script never prints secret values. .env is checked
    for existence only. Vault KEK is checked via boolean -- "is the
    env var set" with no value display.
#>

param(
    [string]$BackendUrl = '',
    [string]$FrontendUrl = 'http://127.0.0.1:5173',
    [string]$LlamaServerUrl = 'http://127.0.0.1:8080',
    [switch]$SkipBrowserChecks
)

$ErrorActionPreference = 'Stop'

$script:Results = @()
$script:HasFailed = $false

function Add-Result {
    param([string]$Id, [string]$Status, [string]$Reason)
    $marker = switch ($Status) {
        'PASS' { '+' }
        'FAIL' { 'x' }
        'SKIP' { '.' }
        'WARN' { '!' }
        default { '?' }
    }
    $script:Results += [PSCustomObject]@{
        Id = $Id; Status = $Status; Reason = $Reason
    }
    if ($Status -eq 'FAIL') { $script:HasFailed = $true }
    Write-Host ("[{0}] {1,-32} {2}" -f $marker, $Id, $Reason)
}

function Test-Url {
    param([string]$Url, [int]$TimeoutSec = 3)
    try {
        $r = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec $TimeoutSec `
                               -UseBasicParsing -SkipHttpErrorCheck `
                               -ErrorAction Stop
        return @{ ok = $true; code = $r.StatusCode }
    } catch {
        return @{ ok = $false; error = $_.Exception.Message }
    }
}

# ─────────────────────────────────────────────────────────────────
# Path resolution
# ─────────────────────────────────────────────────────────────────

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$Backend = Join-Path $RepoRoot 'backend'
$Frontend = Join-Path $RepoRoot 'frontend'
$ModelsRoot = 'D:\Ideas\MODELS_ROOT'
$DaenaMind = 'D:\Ideas\Daena-Mind'

# Discover backend port from .daena-port if BackendUrl not set
if (-not $BackendUrl) {
    $portFile = Join-Path $Backend '.daena-port'
    $port = 8000
    if (Test-Path $portFile) {
        try {
            $port = [int](Get-Content $portFile -Raw).Trim()
        } catch {
            $port = 8000
        }
    }
    $BackendUrl = "http://127.0.0.1:$port"
}

Write-Host ""
Write-Host "=== Daena Local Readiness Check ===" -ForegroundColor Cyan
Write-Host "Repo root      : $RepoRoot"
Write-Host "Backend URL    : $BackendUrl"
Write-Host "Frontend URL   : $FrontendUrl"
Write-Host "llama-server   : $LlamaServerUrl"
Write-Host "MODELS_ROOT    : $ModelsRoot"
Write-Host "Daena-Mind     : $DaenaMind"
Write-Host "SkipBrowser    : $SkipBrowserChecks"
Write-Host ""
Write-Host "SECURITY: this script never prints secret values." -ForegroundColor Yellow
Write-Host ""

# ─────────────────────────────────────────────────────────────────
# Local file checks (no network)
# ─────────────────────────────────────────────────────────────────

# L1: backend .env exists (don't read)
$envFile = Join-Path $Backend '.env'
if (Test-Path $envFile) {
    Add-Result 'ENV-FILE-PRESENT' 'PASS' 'backend/.env exists'
} else {
    $exampleFile = Join-Path $Backend '.env.example'
    if (Test-Path $exampleFile) {
        Add-Result 'ENV-FILE-PRESENT' 'WARN' 'backend/.env missing -- copy from .env.example'
    } else {
        Add-Result 'ENV-FILE-PRESENT' 'FAIL' 'backend/.env AND .env.example missing'
    }
}

# L2: backend venv exists
$venvCandidates = @(
    (Join-Path $Backend '.venv\Scripts\python.exe'),
    (Join-Path $Backend '.venv/bin/python'),
    (Join-Path $RepoRoot 'venv_daena\Scripts\python.exe')
)
$venvFound = $venvCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($venvFound) {
    Add-Result 'BACKEND-VENV' 'PASS' "found at $venvFound"
} else {
    Add-Result 'BACKEND-VENV' 'WARN' 'no project venv found -- using system Python?'
}

# L3: backend SQLite database file
$dbCandidates = @(
    (Join-Path $Backend 'daena.db'),
    (Join-Path $Backend 'daena_dev.db'),
    (Join-Path $Backend 'app.db')
)
$dbFound = $dbCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($dbFound) {
    $sizeMb = [math]::Round((Get-Item $dbFound).Length / 1MB, 2)
    Add-Result 'SQLITE-DB-EXISTS' 'PASS' ("$dbFound ({0} MB)" -f $sizeMb)
} else {
    Add-Result 'SQLITE-DB-EXISTS' 'WARN' 'no daena.db / daena_dev.db / app.db found -- backend has not booted yet?'
}

# L4: frontend node_modules
$nodeModules = Join-Path $Frontend 'node_modules'
if (Test-Path $nodeModules) {
    Add-Result 'FRONTEND-DEPS' 'PASS' 'frontend/node_modules present'
} else {
    Add-Result 'FRONTEND-DEPS' 'FAIL' 'frontend/node_modules missing -- run `cd frontend && npm install`'
}

# L5: MODELS_ROOT directory exists
if (Test-Path $ModelsRoot) {
    $ggufDir = Join-Path $ModelsRoot 'gguf'
    if (Test-Path $ggufDir) {
        $ggufCount = @(Get-ChildItem -Path $ggufDir -Recurse -Filter '*.gguf' -ErrorAction SilentlyContinue).Count
        Add-Result 'MODELS-ROOT' 'PASS' "$ModelsRoot ($ggufCount .gguf files in gguf/)"
    } else {
        Add-Result 'MODELS-ROOT' 'WARN' "$ModelsRoot exists but gguf/ subdir missing -- llama-server will have nothing to load"
    }
} else {
    Add-Result 'MODELS-ROOT' 'FAIL' "$ModelsRoot does not exist -- create per CLAUDE.md MODELS_ROOT convention"
}

# L6: Daena-Mind vault
if (Test-Path $DaenaMind) {
    $tiers = @('T0','T1','T2','T3','T4') | Where-Object { Test-Path (Join-Path $DaenaMind $_) }
    Add-Result 'DAENA-MIND-VAULT' 'PASS' ("$DaenaMind tiers present: " + ($tiers -join ', '))
} else {
    Add-Result 'DAENA-MIND-VAULT' 'WARN' "$DaenaMind missing -- T2/T3/T4 memory has no Obsidian-compatible mirror"
}

# L7: vault KEK presence in env (BOOLEAN ONLY -- never reads value)
$kekSet = $false
if (Test-Path $envFile) {
    # Use Select-String with -Pattern that matches the key=value SHAPE
    # but never expose the value. The match.Length tells us if the
    # line exists; we never echo the line.
    try {
        $kekLine = Get-Content $envFile | Select-String -Pattern '^DAENA_KEK\s*=\s*\S+' -SimpleMatch:$false
        $kekSet = ($kekLine.Count -gt 0)
    } catch {
        $kekSet = $false
    }
}
if ($kekSet) {
    Add-Result 'VAULT-KEK-CONFIGURED' 'PASS' 'DAENA_KEK is set in backend/.env (value not displayed)'
} else {
    Add-Result 'VAULT-KEK-CONFIGURED' 'WARN' 'DAENA_KEK not in backend/.env -- vault_boot.py will fall back to dev KEK with warning'
}

# L8: WSL2 kali-linux availability (optional)
try {
    $wslOut = & wsl -d kali-linux -- echo ok 2>&1
    if ($LASTEXITCODE -eq 0 -and $wslOut -match 'ok') {
        Add-Result 'WSL2-KALI-LINUX' 'PASS' 'WSL2 kali-linux available'
    } else {
        Add-Result 'WSL2-KALI-LINUX' 'WARN' 'WSL2 kali-linux not available -- backend will run on Windows fallback'
    }
} catch {
    Add-Result 'WSL2-KALI-LINUX' 'WARN' 'WSL2 not on PATH or kali-linux distro missing'
}

# ─────────────────────────────────────────────────────────────────
# Network checks (skip if -SkipBrowserChecks)
# ─────────────────────────────────────────────────────────────────

if ($SkipBrowserChecks) {
    Add-Result 'NETWORK-CHECKS' 'SKIP' '-SkipBrowserChecks specified'
} else {
    # N1: backend health
    $r = Test-Url -Url "$BackendUrl/api/v1/health" -TimeoutSec 3
    if ($r.ok -and $r.code -ge 200 -and $r.code -lt 300) {
        Add-Result 'BACKEND-HEALTHY' 'PASS' "$BackendUrl/api/v1/health -> $($r.code)"
    } elseif ($r.ok) {
        Add-Result 'BACKEND-HEALTHY' 'WARN' "$BackendUrl/api/v1/health -> $($r.code)"
    } else {
        Add-Result 'BACKEND-HEALTHY' 'FAIL' "$BackendUrl/api/v1/health unreachable. Run: python backend/run.py"
    }

    # N2: frontend
    $r = Test-Url -Url $FrontendUrl -TimeoutSec 3
    if ($r.ok) {
        Add-Result 'FRONTEND-HEALTHY' 'PASS' "$FrontendUrl -> $($r.code)"
    } else {
        Add-Result 'FRONTEND-HEALTHY' 'WARN' "$FrontendUrl unreachable. Run: cd frontend && npm run dev"
    }

    # N3: llama-server
    $r = Test-Url -Url "$LlamaServerUrl/v1/models" -TimeoutSec 3
    if ($r.ok -and $r.code -ge 200 -and $r.code -lt 300) {
        Add-Result 'LLAMA-SERVER-UP' 'PASS' "$LlamaServerUrl/v1/models -> $($r.code)"
    } else {
        Add-Result 'LLAMA-SERVER-UP' 'WARN' "$LlamaServerUrl unreachable. Local LLM offline; cloud APIs still work if keys configured."
    }

    # N4: backend health/detailed (if backend is up, get richer info)
    $r = Test-Url -Url "$BackendUrl/api/v1/health/detailed" -TimeoutSec 5
    if ($r.ok -and $r.code -ge 200 -and $r.code -lt 300) {
        Add-Result 'BACKEND-DETAILED' 'PASS' "$BackendUrl/api/v1/health/detailed -> $($r.code)"
    } else {
        Add-Result 'BACKEND-DETAILED' 'SKIP' 'backend not responding to /health/detailed (only basic /health checked)'
    }
}

# ─────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
$pass = ($script:Results | Where-Object { $_.Status -eq 'PASS' }).Count
$fail = ($script:Results | Where-Object { $_.Status -eq 'FAIL' }).Count
$warn = ($script:Results | Where-Object { $_.Status -eq 'WARN' }).Count
$skip = ($script:Results | Where-Object { $_.Status -eq 'SKIP' }).Count
Write-Host "PASS: $pass  FAIL: $fail  WARN: $warn  SKIP: $skip"
Write-Host ""

if ($script:HasFailed) {
    Write-Host "Local Daena NOT ready. Resolve FAILs before launching." -ForegroundColor Red
    exit 1
} elseif ($warn -gt 0) {
    Write-Host "Local Daena boots but WARNs should be reviewed." -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "Local Daena ready." -ForegroundColor Green
    exit 0
}
