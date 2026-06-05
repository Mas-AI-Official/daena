<#
.SYNOPSIS
  DEP-001 preflight: report PRESENCE (not values) of required secrets in backend/.env.

.DESCRIPTION
  Prints only SET / PLACEHOLDER / MISSING for each required key. It NEVER prints,
  logs, copies, or transmits any secret value. Each value is reduced to a boolean
  the instant it is read and the raw string is discarded.

  Key list is derived dynamically from backend/.env.example (so it self-maintains)
  plus a small curated set of secrets that live in .env but not the example
  (DAENA_KEK, EVILBOB_KEY, HUNTER_API_KEY), per DAENA_SECRET_ROTATION_RUNBOOK.md.

  Read-only. Does not modify backend/.env. Safe to run any time.

.NOTES
  DEP-001 stays FOUNDER-GATED: this tells you WHICH required secrets are set so you
  can rotate/fill them. It does not rotate, generate, or change any secret.
  Exit code: 0 always (this is a report, not a gate).
#>
[CmdletBinding()]
param(
    [string]$EnvFile     = '',
    [string]$ExampleFile = ''
)

$ErrorActionPreference = 'Stop'

# Resolve the script directory robustly ($PSScriptRoot can be empty at
# param-default-eval time depending on how the script is invoked).
$baseDir = $PSScriptRoot
if (-not $baseDir) { $baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $baseDir) { $baseDir = (Get-Location).Path }
if (-not $EnvFile)     { $EnvFile     = Join-Path $baseDir '..\backend\.env' }
if (-not $ExampleFile) { $ExampleFile = Join-Path $baseDir '..\backend\.env.example' }

# Secret classification: a key is a "secret" if its NAME matches this pattern...
$SecretPattern = '(API_KEY|_SECRET|SECRET_KEY|_TOKEN$|PASSWORD|KEK|ENCRYPTION_KEY|EVILBOB)'
# ...but never these (numeric/string CONFIG that merely contains a secret-ish word).
$NotSecretPattern = '(EXPIRE|ALGORITHM|_MINUTES|_DAYS|_MODE|_HOST|_PORT)'
# DSNs may embed a password; treat the database URL as sensitive too.
$DsnKeys = @('DATABASE_URL')
# Known secrets that exist in .env but are NOT in .env.example (runbook section 1/3).
$ExtraSecrets = @('DAENA_KEK', 'EVILBOB_KEY', 'HUNTER_API_KEY')
# Value shapes that mean "not really filled in".
$PlaceholderPattern = '^(changeme|change-me|your[-_]?|xxx+|<.*>|placeholder|todo|generate|sk-xxx|example|dummy|test[-_]?key)'

function Get-EnvBooleanMap {
    # Returns a hashtable KEY -> @{ HasValue=$bool; IsPlaceholder=$bool }.
    # Captures ONLY booleans; the raw value never leaves this function.
    param([string]$Path)
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $eq = $t.IndexOf('=')
        if ($eq -lt 1) { continue }
        $key = $t.Substring(0, $eq).Trim()
        $val = $t.Substring($eq + 1).Trim().Trim('"').Trim("'")
        $hasValue = -not [string]::IsNullOrWhiteSpace($val)
        $isPlaceholder = $hasValue -and ($val -match $PlaceholderPattern)
        $map[$key] = @{ HasValue = $hasValue; IsPlaceholder = $isPlaceholder }
        Remove-Variable val   # discard the raw secret value immediately
    }
    return $map
}

function Get-ExampleKeys {
    param([string]$Path)
    $keys = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path $Path)) { return $keys }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^[A-Z][A-Z0-9_]+=') {
            $keys.Add(($line -split '=', 2)[0])
        }
    }
    return $keys
}

Write-Host ''
Write-Host '=== DAENA DEP-001 SECRET PRESENCE CHECK (values are never printed) ==='
Write-Host ("env file : {0}" -f $EnvFile)
Write-Host ("template : {0}" -f $ExampleFile)
Write-Host ''

if (-not (Test-Path $EnvFile)) {
    Write-Host "backend/.env NOT FOUND -> every required secret reports MISSING."
    Write-Host "(This is expected on a fresh checkout; the founder creates .env from .env.example.)"
}

$envMap      = Get-EnvBooleanMap -Path $EnvFile
$exampleKeys = Get-ExampleKeys   -Path $ExampleFile

# Build the secret key set: example keys that look secret + DSN keys + curated extras.
$secretKeys = New-Object System.Collections.Generic.List[string]
foreach ($k in $exampleKeys) {
    if ($k -match $NotSecretPattern) { continue }
    if ($k -match $SecretPattern -or $DsnKeys -contains $k) { $secretKeys.Add($k) }
}
foreach ($k in $ExtraSecrets) { if (-not $secretKeys.Contains($k)) { $secretKeys.Add($k) } }
$secretKeys = $secretKeys | Sort-Object -Unique

$set = 0; $placeholder = 0; $missing = 0
Write-Host 'SECRET KEYS (rotate/fill these for production):'
foreach ($k in $secretKeys) {
    $status = 'MISSING'
    if ($envMap.ContainsKey($k)) {
        if ($envMap[$k].IsPlaceholder) { $status = 'PLACEHOLDER' }
        elseif ($envMap[$k].HasValue)  { $status = 'SET' }
    }
    switch ($status) {
        'SET'         { $set++ }
        'PLACEHOLDER' { $placeholder++ }
        'MISSING'     { $missing++ }
    }
    Write-Host ("  {0,-32} {1}" -f $k, $status)
}

Write-Host ''
Write-Host ('SUMMARY: {0} set, {1} placeholder, {2} missing (of {3} secret keys).' -f `
    $set, $placeholder, $missing, $secretKeys.Count)
Write-Host ''
Write-Host 'DEP-001 stays FOUNDER-GATED. SET means a value exists, NOT that it is rotated/valid.'
Write-Host 'Next: rotate per Doc/production-readiness/DAENA_SECRET_ROTATION_RUNBOOK.md, then re-run.'
exit 0
