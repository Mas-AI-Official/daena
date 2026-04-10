#!/usr/bin/env bash
# =============================================================
# Daena — Linux Development Environment Setup
# =============================================================
# Installs: Python 3.12, Node.js 20, vLLM, Docker, project deps
# Tested on: Ubuntu 22.04+ / Debian 12+
# =============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN} DAENA — Linux Environment Setup${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# --- System packages ---
echo -e "${YELLOW}[1/7] System packages...${NC}"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential git curl wget \
    software-properties-common \
    libffi-dev libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev \
    libncurses5-dev libgdbm-dev liblzma-dev \
    tk-dev uuid-dev 2>/dev/null
echo -e "${GREEN}  Done.${NC}"

# --- Python 3.12 ---
echo -e "${YELLOW}[2/7] Python 3.12...${NC}"
if command -v python3.12 &> /dev/null; then
    echo -e "${GREEN}  Already installed: $(python3.12 --version)${NC}"
else
    sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
    echo -e "${GREEN}  Installed: $(python3.12 --version)${NC}"
fi

# --- Node.js 20 ---
echo -e "${YELLOW}[3/7] Node.js 20...${NC}"
if command -v node &> /dev/null; then
    NODE_V=$(node --version)
    echo -e "${GREEN}  Already installed: $NODE_V${NC}"
else
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y -qq nodejs
    echo -e "${GREEN}  Installed: $(node --version)${NC}"
fi

# --- Docker ---
echo -e "${YELLOW}[4/7] Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}  Already installed: $(docker --version)${NC}"
else
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    echo -e "${GREEN}  Installed. Log out and back in for group permissions.${NC}"
fi

# --- NVIDIA drivers + CUDA (for vLLM) ---
echo -e "${YELLOW}[5/7] GPU check...${NC}"
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}  GPU detected:${NC}"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi available but no GPU info)"
else
    echo -e "${YELLOW}  No NVIDIA GPU detected. vLLM requires a CUDA GPU.${NC}"
    echo "  For cloud GPU: RunPod A100 (~\$1.50/hr) or Lambda Labs (~\$1.29/hr)"
    echo "  Skipping vLLM install."
fi

# --- vLLM (GPU only) ---
echo -e "${YELLOW}[6/7] vLLM...${NC}"
if command -v nvidia-smi &> /dev/null; then
    if python3.12 -c "import vllm" 2>/dev/null; then
        echo -e "${GREEN}  Already installed.${NC}"
    else
        echo "  Installing vLLM (this takes a few minutes)..."
        pip install vllm 2>/dev/null || python3.12 -m pip install vllm
        echo -e "${GREEN}  vLLM installed.${NC}"
    fi
    echo ""
    echo "  To start vLLM with a model:"
    echo "    # 7B model (single GPU, 8GB+ VRAM):"
    echo "    vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8100"
    echo ""
    echo "    # 70B model (needs ~40GB VRAM, use tensor parallelism):"
    echo "    vllm serve meta-llama/Llama-3.1-70B-Instruct --port 8100 --tensor-parallel-size 2"
    echo ""
    echo "    # Qwen 2.5 72B (alternative, good at code):"
    echo "    vllm serve Qwen/Qwen2.5-72B-Instruct --port 8100 --tensor-parallel-size 2"
else
    echo -e "${YELLOW}  Skipped (no GPU). Use cloud GPU or Ollama instead.${NC}"
fi

# --- Python venv + deps ---
echo -e "${YELLOW}[7/7] Daena Python environment...${NC}"
VENV="$BACKEND/.venv"
if [ ! -f "$VENV/bin/python" ]; then
    python3.12 -m venv "$VENV"
    echo "  Created venv at $VENV"
fi
"$VENV/bin/pip" install --upgrade pip -q
if [ -f "$BACKEND/requirements.txt" ]; then
    "$VENV/bin/pip" install -r "$BACKEND/requirements.txt" -q
    echo -e "${GREEN}  Python deps installed.${NC}"
elif [ -f "$BACKEND/pyproject.toml" ]; then
    cd "$BACKEND"
    "$VENV/bin/pip" install -e "." -q
    echo -e "${GREEN}  Python deps installed.${NC}"
fi

# --- Frontend deps ---
if [ -f "$FRONTEND/package.json" ]; then
    cd "$FRONTEND"
    if [ ! -d "node_modules" ]; then
        npm install
    fi
    echo -e "${GREEN}  Frontend deps installed.${NC}"
fi

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${GREEN} DAENA Linux Setup Complete!${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo "  Next steps:"
echo "    1. Start vLLM:  vllm serve <model> --port 8100"
echo "    2. Start Daena:  ./start-daena.sh"
echo "    3. Run tests:    cd backend && .venv/bin/python -m pytest tests/ -q"
echo "    4. Run benchmark: curl -X POST http://localhost:8000/api/v1/benchmark/intelligence"
echo ""
echo -e "${CYAN}============================================${NC}"
