<#
.SYNOPSIS
    Production readiness check for Daena Cloud Run deployment.

.DESCRIPTION
    Runs a battery of read-only checks against:
      1. Local repo files (deploy-cloud.sh, main.py, Dockerfile)
      2. Cloud Run service env block (NAMES ONLY, never values)
      3. Secret Manager bindings (NAMES ONLY)

    NEVER prints secret values. Every check returns PASS/FAIL/SKIP and
    a short reason. The script exits non-zero if any required check
    fails.

    Local-only checks (no gcloud needed):
      - DEPLOY-MIGRATION-STEP: deploy-cloud.sh runs alembic upgrade head
      - CREATE-ALL-GUARD: app/main.py guards Base.metadata.create_all
        behind settings.is_production

    GCP checks (require `gcloud auth login` + project access; SKIPPED
    when -SkipGcp is passed):
      - DATABASE-URL-NOT-SQLITE: Cloud Run env DATABASE_URL is not a
        sqlite+ URL (checked by reading the env binding TYPE only --
        looks at whether DATABASE_URL is a Secret Manager ref; if it
        is, marks PASS without reading the value)
      - SECRET-MANAGER-BINDINGS: every required env var is bound from
        Secret Manager, not as a raw value
      - APP-ENV-PRODUCTION: APP_ENV=production
      - DISABLE-AUTH-FALSE: DISABLE_AUTH is unset or =false
      - CORS-ORIGINS-RESTRICTED: CORS_ORIGINS is set and not "*"
      - V2-FLAG-NOT-FLIPPED: USE_CONNECTION_REGISTRY_V2 is unset or
        =false (override with -AllowV2Flag flag)

.PARAMETER Project
    GCP project id. Default: daena-467315

.PARAMETER Region
    GCP region. Default: us-central1

.PARAMETER Service
    Cloud Run service name. Default: daena

.PARAMETER SkipGcp
    Skip GCP-side checks (only run local file checks).

.PARAMETER AllowV2Flag
    Allow USE_CONNECTION_REGISTRY_V2=true in production. Default: $false
    (refuse the deploy if the flag is on without explicit override).

.EXAMPLE
    pwsh scripts/production_readiness_check.ps1
    pwsh scripts/production_readiness_check.ps1 -SkipGcp
    pwsh scripts/production_readiness_check.ps1 -AllowV2Flag

.NOTES
    SECURITY: This script never prints secret values. It only reads
    env var NAMES + Secret Manager binding TYPES. If any check would
    require reading a value, it is marked SKIP with reason.
#>

param(
    [string]$Project = 'daena-467315',
    [string]$Region = 'us-central1',
    [string]$Service = 'daena-v2',
    [switch]$SkipGcp,
    [switch]$AllowV2Flag,
    [switch]$Verbose
)

$ErrorActionPreference = 'Stop'

# ─────────────────────────────────────────────────────────────────
# Config: list of secret env vars that MUST come from Secret Manager
# ─────────────────────────────────────────────────────────────────

# Names only -- this list is canonical. If a NEW secret is added, add
# its env var name here so the check covers it.
$RequiredSecretEnvNames = @(
    'DATABASE_URL',
    'DAENA_KEK',
    'JWT_SECRET_KEY',
    'VAULT_ENCRYPTION_KEY',
    'GROQ_API_KEY',
    'GEMINI_API_KEY',
    'GOOGLE_CLIENT_SECRET',
    'GITHUB_CLIENT_SECRET'
)

# Optional secrets -- present in some configs but not all. Flagged
# but not required to be Secret-Manager-bound for PASS.
$OptionalSecretEnvNames = @(
    'OPENAI_API_KEY',
    'ANTHROPIC_API_KEY',
    'PERPLEXITY_API_KEY',
    'OPENROUTER_API_KEY',
    'TOGETHER_API_KEY',
    'XAI_API_KEY'
)

# Non-secret config that should remain plaintext env vars.
$AllowedPlaintextEnvNames = @(
    'APP_ENV', 'LOG_LEVEL', 'CORS_ORIGINS', 'OLLAMA_BASE_URL',
    'VLLM_BASE_URL', 'PORT', 'USE_CONNECTION_REGISTRY_V2',
    'DISABLE_AUTH', 'PYTHONUNBUFFERED', 'PYTHONPATH'
)

# ─────────────────────────────────────────────────────────────────
# Result accumulator
# ─────────────────────────────────────────────────────────────────

$script:Results = @()
$script:HasFailed = $false

function Add-Result {
    param([string]$Id, [string]$Status, [string]$Reason)
    $emoji = switch ($Status) {
        'PASS' { '✓' }
        'FAIL' { '✗' }
        'SKIP' { '·' }
        'WARN' { '!' }
        default { '?' }
    }
    $script:Results += [PSCustomObject]@{
        Id = $Id
        Status = $Status
        Reason = $Reason
    }
    if ($Status -eq 'FAIL') { $script:HasFailed = $true }
    Write-Host ("[{0}] {1,-32} {2}" -f $emoji, $Id, $Reason)
}

# ─────────────────────────────────────────────────────────────────
# Path resolution: assume script is at <repo-root>/scripts/...
# ─────────────────────────────────────────────────────────────────

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$DeployScript = Join-Path $RepoRoot 'deploy-cloud.sh'
$MainPy = Join-Path $RepoRoot 'backend/app/main.py'
$Dockerfile = Join-Path $RepoRoot 'Dockerfile'

Write-Host ""
Write-Host "=== Daena Production Readiness Check ===" -ForegroundColor Cyan
Write-Host "Repo root  : $RepoRoot"
Write-Host "GCP project: $Project"
Write-Host "Region     : $Region"
Write-Host "Service    : $Service"
Write-Host "SkipGcp    : $SkipGcp"
Write-Host "AllowV2Flag: $AllowV2Flag"
Write-Host ""
Write-Host "SECURITY: this script never prints secret values." -ForegroundColor Yellow
Write-Host ""

# ─────────────────────────────────────────────────────────────────
# Local file checks
# ─────────────────────────────────────────────────────────────────

# C1: deploy-cloud.sh exists and includes alembic upgrade head step
if (-not (Test-Path $DeployScript)) {
    Add-Result 'DEPLOY-SCRIPT-EXISTS' 'FAIL' "deploy-cloud.sh not found at $DeployScript"
} else {
    Add-Result 'DEPLOY-SCRIPT-EXISTS' 'PASS' "$DeployScript"
    $deployContent = Get-Content $DeployScript -Raw
    if ($deployContent -match 'alembic\s+(?:.*\s)?upgrade\s+head') {
        Add-Result 'DEPLOY-MIGRATION-STEP' 'PASS' "deploy-cloud.sh runs alembic upgrade head"
    } else {
        Add-Result 'DEPLOY-MIGRATION-STEP' 'FAIL' "deploy-cloud.sh does NOT run alembic upgrade head -- production schema not managed by Alembic"
    }

    if ($deployContent -match '--update-secrets') {
        Add-Result 'DEPLOY-USES-SECRETS' 'PASS' "deploy-cloud.sh uses --update-secrets bindings"
    } else {
        Add-Result 'DEPLOY-USES-SECRETS' 'FAIL' "deploy-cloud.sh does NOT use --update-secrets -- secrets are raw env vars"
    }

    if ($deployContent -match '--add-cloudsql-instances') {
        Add-Result 'DEPLOY-CLOUDSQL-LINK' 'PASS' "deploy-cloud.sh adds Cloud SQL instance link"
    } else {
        Add-Result 'DEPLOY-CLOUDSQL-LINK' 'FAIL' "deploy-cloud.sh does NOT add a Cloud SQL instance -- DB unreachable from Cloud Run"
    }
}

# C2: app/main.py guards Base.metadata.create_all
if (-not (Test-Path $MainPy)) {
    Add-Result 'MAIN-PY-EXISTS' 'FAIL' "$MainPy not found"
} else {
    $mainContent = Get-Content $MainPy -Raw
    if ($mainContent -match 'Base\.metadata\.create_all') {
        # The call exists; check it's guarded.
        # Look for either 'if not settings.is_production' or
        # 'if settings.app_env != "production"' anywhere within ~10 lines
        # of the create_all call.
        $createAllIdx = $mainContent.IndexOf('Base.metadata.create_all')
        $window = $mainContent.Substring(
            [Math]::Max(0, $createAllIdx - 800),
            [Math]::Min(1000, $mainContent.Length - [Math]::Max(0, $createAllIdx - 800))
        )
        if ($window -match 'if\s+not\s+settings\.is_production' -or
            $window -match 'if\s+settings\.app_env\s*!=\s*[`"]production[`"]') {
            Add-Result 'CREATE-ALL-GUARD' 'PASS' "Base.metadata.create_all is guarded behind is_production check"
        } else {
            Add-Result 'CREATE-ALL-GUARD' 'FAIL' "Base.metadata.create_all is NOT guarded -- runs in production, masks Alembic stamp drift"
        }
    } else {
        Add-Result 'CREATE-ALL-GUARD' 'WARN' "Base.metadata.create_all not found in main.py -- verify schema strategy"
    }
}

# C3: Dockerfile entrypoint runs alembic before uvicorn (optional; many
# repos run alembic via deploy-cloud.sh instead)
if (Test-Path $Dockerfile) {
    $dockerContent = Get-Content $Dockerfile -Raw
    if ($dockerContent -match 'alembic\s+(?:.*\s)?upgrade\s+head' -or
        $dockerContent -match 'ENTRYPOINT.*start\.sh') {
        Add-Result 'DOCKER-MIGRATION-ENTRYPOINT' 'PASS' "Dockerfile entrypoint runs migrations"
    } else {
        Add-Result 'DOCKER-MIGRATION-ENTRYPOINT' 'WARN' "Dockerfile does not run alembic on container start -- ensure deploy-cloud.sh handles it"
    }
} else {
    Add-Result 'DOCKER-MIGRATION-ENTRYPOINT' 'SKIP' "Dockerfile not present -- using Cloud Run buildpacks?"
}

# ─────────────────────────────────────────────────────────────────
# GCP checks (require gcloud)
# ─────────────────────────────────────────────────────────────────

if ($SkipGcp) {
    Add-Result 'GCP-CHECKS' 'SKIP' "-SkipGcp specified; skipping all gcloud-side checks"
} else {
    # Verify gcloud is authenticated (read-only check).
    $gcloudOk = $true
    try {
        $null = & gcloud config get-value project 2>$null
        if ($LASTEXITCODE -ne 0) {
            $gcloudOk = $false
        }
    } catch {
        $gcloudOk = $false
    }

    if (-not $gcloudOk) {
        Add-Result 'GCLOUD-AUTH' 'FAIL' "gcloud not authenticated. Run 'gcloud auth login' then retry."
    } else {
        Add-Result 'GCLOUD-AUTH' 'PASS' "gcloud authenticated"

        # Fetch the env block. We use --format='value(...)' to
        # extract NAMES ONLY for the env-key list, then a separate
        # query for which entries have valueFrom (Secret Manager
        # ref) vs raw value. We never extract the value field.

        $envJson = $null
        try {
            $envJson = & gcloud run services describe $Service `
                --project=$Project --region=$Region `
                --format='json(spec.template.spec.containers[0].env)' 2>$null
        } catch {
            Add-Result 'CLOUDRUN-DESCRIBE' 'FAIL' "Failed to describe Cloud Run service '$Service' in ${Region}: $($_.Exception.Message)"
        }

        if ($envJson) {
            try {
                $envBlock = ($envJson | ConvertFrom-Json).spec.template.spec.containers[0].env
            } catch {
                Add-Result 'CLOUDRUN-DESCRIBE' 'FAIL' "Could not parse Cloud Run env JSON"
                $envBlock = @()
            }
            Add-Result 'CLOUDRUN-DESCRIBE' 'PASS' "Cloud Run service '$Service' described OK"

            # Build a map: name -> 'secret' | 'plaintext' | 'unknown'
            # (we never store the actual value)
            $envMap = @{}
            foreach ($entry in $envBlock) {
                $name = $entry.name
                if ($null -ne $entry.valueFrom) {
                    $envMap[$name] = 'secret'
                } elseif ($null -ne $entry.value) {
                    $envMap[$name] = 'plaintext'
                } else {
                    $envMap[$name] = 'unknown'
                }
            }

            # G1: DATABASE-URL-NOT-SQLITE
            if (-not $envMap.ContainsKey('DATABASE_URL')) {
                Add-Result 'DATABASE-URL-NOT-SQLITE' 'FAIL' "DATABASE_URL not set in Cloud Run env -- production falls back to SQLite default in app/core/config.py"
            } elseif ($envMap['DATABASE_URL'] -eq 'secret') {
                Add-Result 'DATABASE-URL-NOT-SQLITE' 'PASS' "DATABASE_URL is a Secret Manager binding (value not inspected)"
            } else {
                # Raw env -- we have to inspect to verify it's not SQLite.
                # We do this WITHOUT exposing the URL. Just check whether
                # it starts with 'sqlite'. If yes, FAIL. If not, WARN
                # (because raw values for DATABASE_URL violate the
                # Secret Manager rule anyway).
                $dbUrlEntry = $envBlock | Where-Object { $_.name -eq 'DATABASE_URL' } | Select-Object -First 1
                $rawValue = if ($dbUrlEntry) { $dbUrlEntry.value } else { '' }
                $isSqlite = $rawValue -like 'sqlite*'
                # Clear local variable immediately to limit exposure.
                $rawValue = $null
                Remove-Variable rawValue -ErrorAction SilentlyContinue
                if ($isSqlite) {
                    Add-Result 'DATABASE-URL-NOT-SQLITE' 'FAIL' "DATABASE_URL appears to be a SQLite URL -- production state is ephemeral. Move to Cloud SQL Postgres."
                } else {
                    Add-Result 'DATABASE-URL-NOT-SQLITE' 'WARN' "DATABASE_URL is plaintext (not SQLite) -- still violates Secret Manager rule; bind via --update-secrets"
                }
            }

            # G2: SECRET-MANAGER-BINDINGS
            $missingSecrets = @()
            $plaintextSecrets = @()
            foreach ($name in $RequiredSecretEnvNames) {
                if (-not $envMap.ContainsKey($name)) {
                    $missingSecrets += $name
                } elseif ($envMap[$name] -ne 'secret') {
                    $plaintextSecrets += $name
                }
            }
            if ($missingSecrets.Count -eq 0 -and $plaintextSecrets.Count -eq 0) {
                Add-Result 'SECRET-MANAGER-BINDINGS' 'PASS' "All $($RequiredSecretEnvNames.Count) required secrets are Secret Manager bindings"
            } else {
                $msg = ""
                if ($missingSecrets.Count -gt 0) {
                    $msg += "missing: $($missingSecrets -join ', '); "
                }
                if ($plaintextSecrets.Count -gt 0) {
                    $msg += "PLAINTEXT (rotate + bind to Secret Manager): $($plaintextSecrets -join ', ')"
                }
                Add-Result 'SECRET-MANAGER-BINDINGS' 'FAIL' $msg
            }

            # G2b: optional secrets check (informational)
            $optionalPlaintext = @()
            foreach ($name in $OptionalSecretEnvNames) {
                if ($envMap.ContainsKey($name) -and $envMap[$name] -ne 'secret') {
                    $optionalPlaintext += $name
                }
            }
            if ($optionalPlaintext.Count -gt 0) {
                Add-Result 'OPTIONAL-SECRETS-PLAINTEXT' 'WARN' "Optional secrets present as plaintext (bind to Secret Manager): $($optionalPlaintext -join ', ')"
            }

            # G3: APP-ENV-PRODUCTION
            if (-not $envMap.ContainsKey('APP_ENV')) {
                Add-Result 'APP-ENV-PRODUCTION' 'FAIL' "APP_ENV not set"
            } elseif ($envMap['APP_ENV'] -eq 'plaintext') {
                $appEnvEntry = $envBlock | Where-Object { $_.name -eq 'APP_ENV' } | Select-Object -First 1
                if ($appEnvEntry.value -eq 'production') {
                    Add-Result 'APP-ENV-PRODUCTION' 'PASS' "APP_ENV=production"
                } else {
                    Add-Result 'APP-ENV-PRODUCTION' 'FAIL' "APP_ENV is set but not 'production' (saw: $($appEnvEntry.value))"
                }
            } else {
                Add-Result 'APP-ENV-PRODUCTION' 'WARN' "APP_ENV is bound from Secret Manager -- unusual; this is not a secret"
            }

            # G4: DISABLE-AUTH-FALSE
            if ($envMap.ContainsKey('DISABLE_AUTH')) {
                $authEntry = $envBlock | Where-Object { $_.name -eq 'DISABLE_AUTH' } | Select-Object -First 1
                $authValue = if ($authEntry) { $authEntry.value } else { '' }
                if ($authValue -eq 'false' -or $authValue -eq 'False' -or $authValue -eq '0' -or $authValue -eq '') {
                    Add-Result 'DISABLE-AUTH-FALSE' 'PASS' "DISABLE_AUTH is false / unset"
                } else {
                    Add-Result 'DISABLE-AUTH-FALSE' 'FAIL' "DISABLE_AUTH=$authValue in production -- auth bypass enabled"
                }
            } else {
                Add-Result 'DISABLE-AUTH-FALSE' 'PASS' "DISABLE_AUTH not set (defaults to false)"
            }

            # G5: CORS-ORIGINS-RESTRICTED
            if (-not $envMap.ContainsKey('CORS_ORIGINS')) {
                Add-Result 'CORS-ORIGINS-RESTRICTED' 'WARN' "CORS_ORIGINS not set -- using app default; verify it's restrictive"
            } else {
                $corsEntry = $envBlock | Where-Object { $_.name -eq 'CORS_ORIGINS' } | Select-Object -First 1
                $corsValue = if ($corsEntry) { $corsEntry.value } else { '' }
                if ([string]::IsNullOrEmpty($corsValue) -or $corsValue -eq '*') {
                    Add-Result 'CORS-ORIGINS-RESTRICTED' 'FAIL' "CORS_ORIGINS is empty or '*' -- any origin can hit the API"
                } else {
                    Add-Result 'CORS-ORIGINS-RESTRICTED' 'PASS' "CORS_ORIGINS is set to a non-wildcard list"
                }
            }

            # G6: V2-FLAG-NOT-FLIPPED
            if (-not $envMap.ContainsKey('USE_CONNECTION_REGISTRY_V2')) {
                Add-Result 'V2-FLAG-NOT-FLIPPED' 'PASS' "USE_CONNECTION_REGISTRY_V2 unset (defaults to false)"
            } else {
                $v2Entry = $envBlock | Where-Object { $_.name -eq 'USE_CONNECTION_REGISTRY_V2' } | Select-Object -First 1
                $v2Value = if ($v2Entry) { $v2Entry.value } else { '' }
                if ($v2Value -eq 'true' -or $v2Value -eq 'True' -or $v2Value -eq '1') {
                    if ($AllowV2Flag) {
                        Add-Result 'V2-FLAG-NOT-FLIPPED' 'WARN' "USE_CONNECTION_REGISTRY_V2=true (override accepted via -AllowV2Flag)"
                    } else {
                        Add-Result 'V2-FLAG-NOT-FLIPPED' 'FAIL' "USE_CONNECTION_REGISTRY_V2=true in production WITHOUT -AllowV2Flag override -- premature flip"
                    }
                } else {
                    Add-Result 'V2-FLAG-NOT-FLIPPED' 'PASS' "USE_CONNECTION_REGISTRY_V2=$v2Value (not flipped)"
                }
            }

            # G7: ENV-LIST-OBSERVABILITY (informational)
            $envCount = $envMap.Count
            $secretCount = ($envMap.Values | Where-Object { $_ -eq 'secret' }).Count
            $plaintextCount = ($envMap.Values | Where-Object { $_ -eq 'plaintext' }).Count
            Add-Result 'ENV-INVENTORY' 'PASS' "Cloud Run env: $envCount entries ($secretCount secret refs, $plaintextCount plaintext)"
        }

        # G8: Cloud SQL connection link
        try {
            $cloudsqlJson = & gcloud run services describe $Service `
                --project=$Project --region=$Region `
                --format='value(spec.template.metadata.annotations[run.googleapis.com/cloudsql-instances])' 2>$null
            $cloudsqlAnnot = if ($cloudsqlJson) { $cloudsqlJson.Trim() } else { '' }
            if ($cloudsqlAnnot) {
                Add-Result 'CLOUDSQL-LINK' 'PASS' "Cloud SQL link present: $cloudsqlAnnot"
            } else {
                Add-Result 'CLOUDSQL-LINK' 'FAIL' "No Cloud SQL instance linked to Cloud Run -- production cannot reach a managed Postgres"
            }
        } catch {
            Add-Result 'CLOUDSQL-LINK' 'WARN' "Could not query Cloud SQL annotation: $($_.Exception.Message)"
        }

        # G9: Secret Manager secrets exist for the required names
        # (NAMES ONLY -- never reads versions / values).
        try {
            $existingSecrets = & gcloud secrets list `
                --project=$Project `
                --format='value(name)' 2>$null
            $existingSet = @{}
            if ($existingSecrets) {
                foreach ($line in $existingSecrets) {
                    $shortName = ($line -split '/')[-1]
                    $existingSet[$shortName] = $true
                }
            }
            $missingInSm = @()
            foreach ($envName in $RequiredSecretEnvNames) {
                # Convention: env name -> secret name = lowercase, underscores -> dashes,
                # prefixed with 'daena-'. e.g. JWT_SECRET_KEY -> daena-jwt-secret-key.
                $smName = 'daena-' + ($envName.ToLower() -replace '_', '-')
                if (-not $existingSet.ContainsKey($smName)) {
                    $missingInSm += "$envName (expected $smName)"
                }
            }
            if ($missingInSm.Count -eq 0) {
                Add-Result 'SECRET-MANAGER-SECRETS-EXIST' 'PASS' "All $($RequiredSecretEnvNames.Count) required secrets exist in Secret Manager"
            } else {
                Add-Result 'SECRET-MANAGER-SECRETS-EXIST' 'FAIL' "Missing in Secret Manager: $($missingInSm -join '; ')"
            }
        } catch {
            Add-Result 'SECRET-MANAGER-SECRETS-EXIST' 'WARN' "Could not list Secret Manager secrets: $($_.Exception.Message)"
        }
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
    Write-Host "❌ Production NOT ready. Resolve FAILs before deploying." -ForegroundColor Red
    exit 1
} elseif ($warn -gt 0) {
    Write-Host "⚠️  Production may deploy but WARNs should be reviewed." -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "✅ Production readiness checks PASS." -ForegroundColor Green
    exit 0
}
