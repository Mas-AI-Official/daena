# install-all-security-tools.ps1
# ------------------------------------------------------------------------------
# Installs every tool in Daena's SecurityTool catalog that is compatible with
# the current Windows host. Uses:
#   * Chocolatey (choco) for native binaries: nmap, git, ripgrep, gitleaks, trivy
#   * pip (backend venv) for Python-based scanners: bandit, semgrep, detect-secrets
#   * npm global for Node-based scanners: retire, @cyclonedx/cdxgen
#   * go install for ProjectDiscovery tools (nuclei, subfinder, httpx, naabu, ...)
#
# Tools that are Linux-only (wpscan via Ruby, proxychains, aircrack-ng, hashcat
# on Windows is awkward) are skipped and reported at the end.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install-all-security-tools.ps1
#   powershell -ExecutionPolicy Bypass -File install-all-security-tools.ps1 -DryRun
#   powershell -ExecutionPolicy Bypass -File install-all-security-tools.ps1 -OnlyCategory recon
# ------------------------------------------------------------------------------

param(
    [switch]$DryRun,
    [string]$OnlyCategory = "",
    [switch]$SkipGo,
    [switch]$SkipPip,
    [switch]$SkipChoco,
    [switch]$SkipNpm
)

$ErrorActionPreference = "Continue"
$InformationPreference = "Continue"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Split-Path -Parent $scriptRoot
$venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Warning "Backend venv not found at $venvPython; using system python"
    $venvPython = "python"
}

function Write-Section([string]$title) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor DarkGray
    Write-Host $title -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor DarkGray
}

function Test-Cmd([string]$name) {
    return $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

function Invoke-Install([string]$label, [string]$cmd, [string]$category) {
    if ($OnlyCategory -and $OnlyCategory -ne $category) { return }
    Write-Host ""
    Write-Host "[$category] $label" -ForegroundColor Yellow
    if ($DryRun) {
        Write-Host "  (dry-run) $cmd" -ForegroundColor DarkGray
        return
    }
    Write-Host "  $cmd" -ForegroundColor DarkGray
    & powershell.exe -NoProfile -Command $cmd 2>&1 | ForEach-Object {
        Write-Host "    $_" -ForegroundColor DarkGray
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FAILED] exit $LASTEXITCODE" -ForegroundColor Red
        $script:failed += $label
    } else {
        Write-Host "  [OK]" -ForegroundColor Green
        $script:installed += $label
    }
}

$installed = @()
$failed = @()
$skipped = @()

Write-Section "Daena Security Tools Installer"
Write-Host "Backend venv: $venvPython"
Write-Host "DryRun:       $DryRun"
Write-Host "Only:         $(if ($OnlyCategory) { $OnlyCategory } else { '(all)' })"

# ------------------------------------------------------------------------------
# Chocolatey (Windows-native binaries)
# ------------------------------------------------------------------------------

if (-not $SkipChoco) {
    if (Test-Cmd "choco") {
        Write-Section "Chocolatey binaries"
        Invoke-Install "nmap"      "choco install nmap -y --no-progress"       "recon"
        Invoke-Install "git"       "choco install git -y --no-progress"        "infra"
        Invoke-Install "ripgrep"   "choco install ripgrep -y --no-progress"    "scanning"
        Invoke-Install "gitleaks"  "choco install gitleaks -y --no-progress"   "scanning"
        Invoke-Install "trivy"     "choco install trivy -y --no-progress"      "container"
        Invoke-Install "sqlmap"    "choco install sqlmap -y --no-progress"     "exploitation"
        Invoke-Install "hashcat"   "choco install hashcat -y --no-progress"    "credential"
        Invoke-Install "john"      "choco install john -y --no-progress"       "credential"
        Invoke-Install "wireshark" "choco install wireshark -y --no-progress"  "network"
    } else {
        Write-Warning "choco not found; skipping Chocolatey block. Install from https://chocolatey.org/install"
        $skipped += "choco-block"
    }
}

# ------------------------------------------------------------------------------
# pip (Python-based scanners)
# ------------------------------------------------------------------------------

if (-not $SkipPip) {
    Write-Section "Python tooling (backend venv)"
    $pipPkgs = @(
        @{ name = "bandit";         cmd = "bandit";         cat = "scanning" },
        @{ name = "semgrep";        cmd = "semgrep";        cat = "scanning" },
        @{ name = "detect-secrets"; cmd = "detect-secrets"; cat = "scanning" },
        @{ name = "safety";         cmd = "safety";         cat = "scanning" },
        @{ name = "yara-python";    cmd = "-";              cat = "scanning" },
        @{ name = "sslyze";         cmd = "sslyze";         cat = "scanning" },
        @{ name = "dirsearch";      cmd = "dirsearch";      cat = "web" },
        @{ name = "wafw00f";        cmd = "wafw00f";        cat = "web" },
        @{ name = "theHarvester";   cmd = "theHarvester";   cat = "osint" }
    )
    foreach ($pkg in $pipPkgs) {
        Invoke-Install $pkg.name "& `"$venvPython`" -m pip install --upgrade $($pkg.name)" $pkg.cat
    }
}

# ------------------------------------------------------------------------------
# npm (Node-based scanners)
# ------------------------------------------------------------------------------

if (-not $SkipNpm) {
    if (Test-Cmd "npm") {
        Write-Section "npm global scanners"
        Invoke-Install "retire"              "npm install -g retire"              "scanning"
        Invoke-Install "@cyclonedx/cdxgen"   "npm install -g @cyclonedx/cdxgen"   "scanning"
        Invoke-Install "snyk"                "npm install -g snyk"                "scanning"
    } else {
        Write-Warning "npm not found; skipping npm block."
        $skipped += "npm-block"
    }
}

# ------------------------------------------------------------------------------
# Go install (ProjectDiscovery suite)
# ------------------------------------------------------------------------------

if (-not $SkipGo) {
    if (Test-Cmd "go") {
        Write-Section "Go-based recon/scanning (ProjectDiscovery)"
        $goPkgs = @(
            @{ name = "subfinder"; url = "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"; cat = "recon" },
            @{ name = "httpx";     url = "github.com/projectdiscovery/httpx/cmd/httpx@latest";           cat = "recon" },
            @{ name = "dnsx";      url = "github.com/projectdiscovery/dnsx/cmd/dnsx@latest";             cat = "recon" },
            @{ name = "naabu";     url = "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest";        cat = "recon" },
            @{ name = "nuclei";    url = "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest";      cat = "scanning" },
            @{ name = "katana";    url = "github.com/projectdiscovery/katana/cmd/katana@latest";         cat = "web" },
            @{ name = "amass";     url = "github.com/owasp-amass/amass/v4/...@master";                  cat = "recon" }
        )
        foreach ($pkg in $goPkgs) {
            Invoke-Install $pkg.name "go install -v $($pkg.url)" $pkg.cat
        }
    } else {
        Write-Warning "go not found; skipping Go block. Install from https://go.dev/dl/"
        $skipped += "go-block"
    }
}

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------

Write-Section "Summary"
Write-Host ("Installed OK: {0}" -f $installed.Count) -ForegroundColor Green
$installed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Green }
if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host ("Failed: {0}" -f $failed.Count) -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}
if ($skipped.Count -gt 0) {
    Write-Host ""
    Write-Host ("Skipped blocks: {0}" -f $skipped.Count) -ForegroundColor Yellow
    $skipped | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
}
Write-Host ""
Write-Host "Done. Restart any terminal that already had Daena loaded so PATH picks up the new binaries." -ForegroundColor Cyan
