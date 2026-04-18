#!/bin/bash
# AIME 2025 Cognitive Forcing Benchmark -- Linux Execution
#
# Runs the benchmark on Linux with powerful CLI models (Claude, Gemini, Codex).
# No local Ollama models -- CLI subscription models only.
#
# Usage:
#   wsl -d Ubuntu -- bash /mnt/d/Ideas/Daena/backend/run-benchmark-linux.sh
#
# Or from within WSL2:
#   cd /mnt/d/Ideas/Daena/backend && bash run-benchmark-linux.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo " AIME 2025 I -- Cognitive Forcing Benchmark"
echo " Running on Linux with CLI models"
echo "=========================================="

# Activate Linux venv
if [ -d "$HOME/daena_venv" ]; then
    source "$HOME/daena_venv/bin/activate"
else
    echo "ERROR: ~/daena_venv not found. Run start-linux.sh first."
    exit 1
fi

# Load .env for API keys
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Pre-flight check
echo ""
echo "CLI Models:"
CLI_COUNT=0
command -v claude.exe &>/dev/null && echo "  claude: OK" && ((CLI_COUNT++)) || echo "  claude: NOT FOUND"
command -v codex &>/dev/null && echo "  codex: OK" && ((CLI_COUNT++)) || echo "  codex: NOT FOUND"
command -v gemini &>/dev/null && echo "  gemini: OK" && ((CLI_COUNT++)) || echo "  gemini: NOT FOUND"

if [ "$CLI_COUNT" -eq 0 ]; then
    echo ""
    echo "ERROR: No CLI models found. This benchmark requires powerful models."
    exit 1
fi

echo ""
echo "Starting benchmark with $CLI_COUNT CLI model(s)..."
echo "Results: aime_cognitive_results.json"
echo "Log: aime_cognitive_log.txt"
echo "=========================================="
echo ""

python3 run_aime_cognitive.py
