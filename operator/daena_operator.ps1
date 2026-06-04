<#
.SYNOPSIS
  Daena Operator Runner -- Windows launcher for the safe local sprint supervisor.
.DESCRIPTION
  Thin entrypoint. Prefers to delegate to the Python supervisor (daena_operator.py). If Python is
  not installed, runs a NATIVE PowerShell DRY-RUN fallback (detect tools, find prompt, write state)
  that NEVER invokes an agent and NEVER fakes automation. See OPERATOR_PROTOCOL.md.
.EXAMPLE
  .\daena_operator.ps1 -DryRun
  .\daena_operator.ps1 -Once
  .\daena_operator.ps1 -Loop 3
#>
[CmdletBinding()]
param(
  [switch]$DryRun,
  [switch]$Once,
  [int]$Loop = 0,
  [string]$ConfigPath
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Here "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Find-Python {
  foreach ($c in @("python", "py", "python3")) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
  }
  return $null
}

# Map switches -> python args (default = dry-run).
$pyArgs = @()
if ($Once) { $pyArgs += "--once" }
elseif ($Loop -gt 0) { $pyArgs += @("--loop", "$Loop") }
else { $pyArgs += "--dry-run" }
if ($ConfigPath) { $pyArgs += @("--config", $ConfigPath) }

$py = Find-Python
if ($py) {
  Write-Host "[operator] delegating to Python supervisor: $py daena_operator.py $($pyArgs -join ' ')"
  & $py (Join-Path $Here "daena_operator.py") @pyArgs
  exit $LASTEXITCODE
}

# ---- Native PowerShell fallback: DRY-RUN ONLY, never invokes an agent ----
Write-Host "[operator] Python not found -- native PowerShell DRY-RUN fallback (no agent invoked)."
$tools = [ordered]@{}
foreach ($t in @("claude", "codex", "gemini", "perplexity", "python", "node", "git", "gh", "rtk", "ollama")) {
  $c = Get-Command $t -ErrorAction SilentlyContinue
  $tools[$t] = if ($c) { $c.Source } else { "NOT_FOUND" }
}
$promptPriority = @(
  "D:\Ideas\Daena\Doc\production-readiness\DAENA_NEXT_PROMPT.md",
  "D:\Ideas\Daena\Doc\company-ops\MAS_AI_NEXT_PROMPT.md",
  "D:\Ideas\Daena\Doc\production-readiness\DAENA_RESUME_PROMPT.md"
)
$prompt = $promptPriority | Where-Object { Test-Path $_ } | Select-Object -First 1
$usable = @("claude", "codex", "gemini") | Where-Object { $tools[$_] -ne "NOT_FOUND" }
$ts = (Get-Date).ToString("s")
$state = [ordered]@{
  state         = "DONE"
  mode          = "dry-run-native"
  ts            = $ts
  prompt        = $prompt
  usable_agents = $usable
  self_start    = "NO (native fallback never invokes an agent)"
}
($state | ConvertTo-Json -Depth 5) | Set-Content -Path (Join-Path $Logs "state.json") -Encoding UTF8
$plan = @"
# Daena Operator -- NATIVE PS DRY RUN
Generated $ts
Active prompt: $prompt
Usable agent CLIs: $($usable -join ', ')
Self-start: NO in native fallback. Install Python and run daena_operator.py, or invoke /loop manually.
This fallback never invokes an agent and never fakes automation.
"@
$plan | Set-Content -Path (Join-Path $Logs "last_result.md") -Encoding UTF8
Write-Host $plan
exit 0
