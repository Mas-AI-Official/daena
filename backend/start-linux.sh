#!/bin/bash
# Daena Backend -- Linux (WSL2) Startup Script
#
# Runs the backend on Linux with:
#   - 0.0.0.0 binding (accessible from Windows frontend)
#   - GPU access (CUDA via WSL2)
#   - CLI model access (claude, codex, gemini via Windows PATH interop)
#   - Security tools (nmap, sqlmap, nikto, hydra)
#
# Usage:
#   wsl -d Ubuntu -- bash /mnt/d/Ideas/Daena/backend/start-linux.sh
#
# Or from within WSL2:
#   cd /mnt/d/Ideas/Daena/backend && bash start-linux.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo " Daena Backend -- Linux Mode"
echo "=========================================="

# Activate Linux venv
if [ -d "$HOME/daena_venv" ]; then
    source "$HOME/daena_venv/bin/activate"
    echo "Python: $(python3 --version)"
    echo "Venv: $HOME/daena_venv"
else
    echo "ERROR: Linux venv not found at ~/daena_venv"
    echo "Create it with: python3 -m venv ~/daena_venv && source ~/daena_venv/bin/activate && pip install -e '.[dev]'"
    exit 1
fi

# Override host to 0.0.0.0 for WSL2 port forwarding to Windows
export HOST="0.0.0.0"
export DAENA_ENV="linux"

# Load .env if exists (for API keys etc.)
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "Loaded: .env"
fi

# Override host AFTER .env load (ensure 0.0.0.0 sticks)
export HOST="0.0.0.0"

# Check GPU
echo ""
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "unknown")
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null || echo "unknown")
    echo "GPU: $GPU_NAME ($GPU_MEM)"
else
    echo "GPU: not available"
fi

# Check CLI models
echo ""
echo "CLI Models:"
command -v claude.exe &>/dev/null && echo "  claude: OK" || echo "  claude: NOT FOUND"
command -v codex &>/dev/null && echo "  codex: OK" || echo "  codex: NOT FOUND"
command -v gemini &>/dev/null && echo "  gemini: OK" || echo "  gemini: NOT FOUND"

# Check security tools
echo ""
echo "Security Tools:"
command -v nmap &>/dev/null && echo "  nmap: $(nmap --version 2>/dev/null | head -1)" || echo "  nmap: not installed"
command -v sqlmap &>/dev/null && echo "  sqlmap: installed" || echo "  sqlmap: not installed"

echo ""
echo "Starting Daena backend on $HOST:${PORT:-8000}..."
echo "Frontend (Windows) connects via http://localhost:${PORT:-8000}"
echo "=========================================="
echo ""

# Start the backend.
#
# Log policy (2026-04-18): previously uvicorn's stdout went only to
# the launching TTY, which meant whenever the window was closed or
# the backend was started via a detached ``cmd /K`` we lost the ONLY
# copy of the error output. Now we ALSO duplicate to a file so
# operators / automation can always tail the last few minutes:
#
#     tail -F /tmp/daena-logs/backend.log
#
# ``tee -a`` means the TTY keeps showing output for interactive runs
# while the file captures everything. ``mkdir -p`` is safe on every
# restart; the file is never rotated automatically -- if it grows
# uncomfortably large, rotate or truncate manually (``: > file.log``).
mkdir -p /tmp/daena-logs
python3 run.py 2>&1 | tee -a /tmp/daena-logs/backend.log
