# Daena Windows Node - start local "hands" server (127.0.0.1:18888)
# Optional: $env:WINDOWS_NODE_TOKEN = "your-secret"
# Optional: $env:EXECUTION_WORKSPACE_ROOT = "D:\Ideas\Daena_old_upgrade_20251213"

$ErrorActionPreference = "Stop"
$NodeDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $NodeDir "..\..")).Path
$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\backend;$env:PYTHONPATH"
if (-not $env:EXECUTION_WORKSPACE_ROOT) { $env:EXECUTION_WORKSPACE_ROOT = $ProjectRoot }
Set-Location $NodeDir
Write-Host "Starting Daena Windows Node at http://127.0.0.1:18888 (workspace: $env:EXECUTION_WORKSPACE_ROOT)"
python -m uvicorn node_server:app --host 127.0.0.1 --port 18888
