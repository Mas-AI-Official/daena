#!/usr/bin/env bash
# =============================================================
# Daena — Start Development Environment (Linux)
# =============================================================
# Starts: vLLM (if not running), Backend (run.py), Frontend (vite)
# Opens: http://localhost:5173 in default browser
# =============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PORT_FILE="$BACKEND/.daena-port"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN} DAENA — Starting Development Environment${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# --- Find Python venv ---
VENV=""
if [ -f "$ROOT/venv_daena/bin/python" ]; then
    VENV="$ROOT/venv_daena"
elif [ -f "$BACKEND/.venv/bin/python" ]; then
    VENV="$BACKEND/.venv"
else
    echo -e "${RED}[ERROR] Virtual environment not found.${NC}"
    echo "        Checked: $ROOT/venv_daena and $BACKEND/.venv"
    echo "        Run: python3.12 -m venv $BACKEND/.venv && $BACKEND/.venv/bin/pip install -r $BACKEND/requirements.txt"
    exit 1
fi
echo -e " Using venv: ${GREEN}$VENV${NC}"

# --- Check if vLLM is running (Linux GPU inference) ---
echo -e " [1/4] Checking vLLM..."
if curl -s http://localhost:8100/v1/models > /dev/null 2>&1; then
    echo -e "        ${GREEN}vLLM already running.${NC}"
else
    echo -e "        ${YELLOW}vLLM not running.${NC}"
    echo "        To start vLLM (requires GPU):"
    echo "          vllm serve <model-name> --port 8100 --host 0.0.0.0"
    echo "        Example:"
    echo "          vllm serve meta-llama/Llama-3.1-70B-Instruct --port 8100 --tensor-parallel-size 2"
    echo ""
    echo "        Continuing without vLLM (will use Ollama or API keys)..."
fi

# --- Also check Ollama ---
if command -v ollama &> /dev/null; then
    if pgrep -x "ollama" > /dev/null 2>&1; then
        echo -e "        ${GREEN}Ollama running.${NC}"
    else
        echo "        Starting Ollama..."
        ollama serve &> /dev/null &
        sleep 3
        echo -e "        ${GREEN}Ollama started.${NC}"
    fi
fi

# --- Start Backend ---
echo -e " [2/4] Starting backend..."
rm -f "$PORT_FILE"
cd "$BACKEND"
"$VENV/bin/python" run.py &
BACKEND_PID=$!

# Wait for port file
for i in $(seq 1 20); do
    if [ -f "$PORT_FILE" ]; then
        BACKEND_PORT=$(cat "$PORT_FILE")
        break
    fi
    sleep 1
done

if [ -z "${BACKEND_PORT:-}" ]; then
    echo -e "${RED}[ERROR] Backend port file not written after 20s.${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi
echo -e "        Backend: ${GREEN}http://localhost:$BACKEND_PORT${NC}"

# --- Start Frontend ---
echo -e " [3/4] Starting frontend..."
cd "$FRONTEND"
if [ ! -d "node_modules" ]; then
    echo "        Running npm install..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!
sleep 3

# --- Open browser ---
echo -e " [4/4] Opening browser..."
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5173 2>/dev/null &
elif command -v open &> /dev/null; then
    open http://localhost:5173
fi

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${GREEN} DAENA is running!${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo -e "  Frontend:  ${GREEN}http://localhost:5173${NC}"
echo -e "  Backend:   ${GREEN}http://localhost:$BACKEND_PORT${NC}"
echo -e "  API docs:  ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}"
echo -e "  vLLM:      ${YELLOW}http://localhost:8100/v1${NC}"
echo ""
echo "  To stop: press Ctrl+C or run ./stop-daena.sh"
echo -e "${CYAN}============================================${NC}"
echo ""

# Wait for both processes
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
