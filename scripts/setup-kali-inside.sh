#!/bin/bash
# =============================================================
# Daena Backend Setup -- Inside Kali Linux (WSL2)
# =============================================================
# Run this ONCE after Kali is installed.
# From inside Kali terminal:
#   bash /mnt/d/Ideas/Daena/scripts/setup-kali-inside.sh
#
# What this does:
#   1. Updates Kali and installs system packages
#   2. Installs Python 3.12 + creates venv
#   3. Installs Daena backend dependencies
#   4. Installs offensive security tools
#   5. Installs vLLM for fast GPU inference
#   6. Creates start script for Daena backend
# =============================================================

set -e

DAENA_ROOT="/mnt/d/Ideas/Daena"
VENV_DIR="$DAENA_ROOT/venv_kali"

echo ""
echo "============================================"
echo " DAENA -- Kali Linux Backend Setup"
echo "============================================"
echo ""

# ── Step 1: System packages ──
echo "[1/6] Updating system and installing base packages..."
sudo apt update -y && sudo apt upgrade -y
sudo apt install -y \
    python3 python3-pip python3-venv python3-dev \
    git curl wget unzip \
    build-essential libssl-dev libffi-dev \
    net-tools dnsutils whois traceroute \
    jq tree htop tmux

# ── Step 2: Python venv ──
echo "[2/6] Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# ── Step 3: Daena backend dependencies ──
echo "[3/6] Installing Daena backend dependencies..."
cd "$DAENA_ROOT/backend"
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt 2>/dev/null || pip install \
    fastapi uvicorn[standard] pydantic httpx aiohttp \
    sqlalchemy[asyncio] aiosqlite asyncpg \
    python-jose[cryptography] passlib[bcrypt] \
    python-multipart structlog redis celery \
    beautifulsoup4 lxml markdown

# ── Step 4: Offensive security tools ──
echo "[4/6] Installing offensive security tools..."
sudo apt install -y \
    nmap \
    nikto \
    dirb \
    gobuster \
    sqlmap \
    whatweb \
    wfuzz \
    hydra \
    john \
    hashcat \
    seclists \
    wordlists \
    exploitdb \
    netcat-traditional \
    tcpdump \
    wireshark-common \
    tor \
    proxychains4 \
    2>/dev/null || echo "  Some tools may need manual install"

# Install nuclei (not in default repos)
echo "  Installing nuclei..."
if ! command -v nuclei &>/dev/null; then
    GO_NUCLEI_URL="https://github.com/projectdiscovery/nuclei/releases/latest/download/nuclei_$(uname -s)_$(uname -m).zip"
    wget -q "$GO_NUCLEI_URL" -O /tmp/nuclei.zip 2>/dev/null && \
        sudo unzip -o /tmp/nuclei.zip -d /usr/local/bin/ 2>/dev/null && \
        rm /tmp/nuclei.zip || echo "  Nuclei: install manually from github.com/projectdiscovery/nuclei"
fi

# Install subfinder
echo "  Installing subfinder..."
if ! command -v subfinder &>/dev/null; then
    go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest 2>/dev/null || \
        echo "  Subfinder: needs Go installed. Run: sudo apt install golang && go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
fi

# Install httpx (projectdiscovery, not Python httpx)
echo "  Installing httpx-toolkit..."
if ! command -v httpx &>/dev/null; then
    go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest 2>/dev/null || \
        echo "  httpx: needs Go. Run: sudo apt install golang && go install github.com/projectdiscovery/httpx/cmd/httpx@latest"
fi

# ── Step 5: vLLM (if NVIDIA GPU available) ──
echo "[5/6] Checking GPU and installing vLLM..."
if command -v nvidia-smi &>/dev/null; then
    echo "  NVIDIA GPU detected!"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    pip install vllm 2>/dev/null || echo "  vLLM install failed -- may need CUDA toolkit"
    echo ""
    echo "  To start vLLM with a model:"
    echo "    vllm serve Qwen/Qwen2.5-Coder-14B --host 0.0.0.0 --port 8100"
    echo ""
else
    echo "  No NVIDIA GPU detected in WSL2."
    echo "  To enable GPU passthrough:"
    echo "    1. Install NVIDIA drivers on Windows (not inside WSL)"
    echo "    2. The WSL2 kernel handles GPU forwarding automatically"
    echo "    3. Run 'nvidia-smi' inside WSL to verify"
    echo ""
    echo "  Skipping vLLM installation (CPU-only mode will use Ollama on Windows)"
fi

# ── Step 6: Create start script ──
echo "[6/6] Creating Daena backend start script..."

cat > "$DAENA_ROOT/scripts/start-backend-kali.sh" << 'SCRIPT'
#!/bin/bash
# Start Daena backend on Kali Linux (WSL2)
# Run from Windows: wsl bash /mnt/d/Ideas/Daena/scripts/start-backend-kali.sh

DAENA_ROOT="/mnt/d/Ideas/Daena"
VENV_DIR="$DAENA_ROOT/venv_kali"

source "$VENV_DIR/bin/activate"
cd "$DAENA_ROOT/backend"

# Load .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Auto-activate offensive mode on local
export EVILBOB_AUTO_ACTIVATE=true

echo ""
echo "============================================"
echo " DAENA Backend (Kali Linux)"
echo "============================================"
echo " Backend:  http://localhost:8000"
echo " API docs: http://localhost:8000/docs"
echo " Mode:     FULL OFFENSIVE (local)"
echo "============================================"
echo ""

python run.py
SCRIPT

chmod +x "$DAENA_ROOT/scripts/start-backend-kali.sh"

# ── Done ──
echo ""
echo "============================================"
echo " SETUP COMPLETE!"
echo "============================================"
echo ""
echo " Installed:"
echo "   - Python $(python3 --version 2>&1 | cut -d' ' -f2) with venv at $VENV_DIR"
echo "   - Daena backend dependencies"
echo "   - Offensive tools: nmap, nuclei, sqlmap, gobuster, etc."
if command -v nvidia-smi &>/dev/null; then
    echo "   - vLLM for GPU inference"
fi
echo ""
echo " To start Daena backend on Linux:"
echo "   bash /mnt/d/Ideas/Daena/scripts/start-backend-kali.sh"
echo ""
echo " Or from Windows PowerShell:"
echo "   wsl bash /mnt/d/Ideas/Daena/scripts/start-backend-kali.sh"
echo ""
echo " Frontend stays on Windows:"
echo "   cd D:\\Ideas\\Daena\\frontend && npm run dev"
echo ""
echo " Both share localhost -- frontend on :5173 talks to backend on :8000"
echo "============================================"
echo ""
