#!/bin/bash

# ============================================================================
# DAENA + OPENCLAW AUTOMATIC INSTALLATION
# One-click setup for the complete system
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                                                          ║"
    echo "║      ██████╗  █████╗ ███████╗███╗   ██╗ █████╗        ║"
    echo "║      ██╔══██╗██╔══██╗██╔════╝████╗  ██║██╔══██╗       ║"
    echo "║      ██║  ██║███████║█████╗  ██╔██╗ ██║███████║       ║"
    echo "║      ██║  ██║██╔══██║██╔══╝  ██║╚██╗██║██╔══██║       ║"
    echo "║      ██████╔╝██║  ██║███████╗██║ ╚████║██║  ██║       ║"
    echo "║      ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝       ║"
    echo "║                                                          ║"
    echo "║            AUTOMATIC INSTALLATION                        ║"
    echo "║                                                          ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        return 1
    fi
    return 0
}

# ============================================================================
# MAIN INSTALLATION
# ============================================================================

print_header

echo ""
echo "This script will install:"
echo "  ✓ Ollama (Local LLM)"
echo "  ✓ Local LLM Models"
echo "  ✓ OpenClaw (in Docker)"
echo "  ✓ Daena System"
echo "  ✓ All dependencies"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    exit 1
fi

# ============================================================================
# STEP 1: CHECK PREREQUISITES
# ============================================================================

print_step "Step 1/7: Checking prerequisites..."

# Check Docker
if ! check_command docker; then
    print_error "Docker not found. Please install Docker first:"
    echo "  https://docs.docker.com/get-docker/"
    exit 1
fi
print_step "  ✓ Docker found"

# Check Python
if ! check_command python3; then
    print_error "Python 3 not found. Please install Python 3.9+:"
    echo "  https://www.python.org/downloads/"
    exit 1
fi
print_step "  ✓ Python found"

# Check pip
if ! check_command pip3; then
    print_error "pip not found. Installing..."
    python3 -m ensurepip
fi
print_step "  ✓ pip found"

# ============================================================================
# STEP 2: INSTALL OLLAMA
# ============================================================================

print_step "Step 2/7: Installing Ollama..."

if ! check_command ollama; then
    print_step "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    print_step "  ✓ Ollama installed"
else
    print_step "  ✓ Ollama already installed"
fi

# Start Ollama service
print_step "  Starting Ollama service..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open -a Ollama 2>/dev/null || true
else
    # Linux
    sudo systemctl start ollama 2>/dev/null || true
fi

sleep 2

# ============================================================================
# STEP 3: DOWNLOAD LLM MODELS
# ============================================================================

print_step "Step 3/7: Downloading LLM models (this may take a while)..."

# Ask user which model to download
echo ""
echo "Choose your model (affects performance and size):"
echo "  1) llama3.1:8b  (Fast, 4.7GB)  - Recommended for testing"
echo "  2) llama3.1:70b (Best, 40GB)   - Recommended for production"
echo "  3) codellama:34b (Code, 20GB)  - Best for coding tasks"
echo "  4) All of the above"
echo ""
read -p "Enter choice (1-4): " model_choice

case $model_choice in
    1)
        print_step "  Downloading llama3.1:8b..."
        ollama pull llama3.1:8b
        PRIMARY_MODEL="llama3.1:8b"
        ;;
    2)
        print_step "  Downloading llama3.1:70b..."
        ollama pull llama3.1:70b
        PRIMARY_MODEL="llama3.1:70b"
        ;;
    3)
        print_step "  Downloading codellama:34b..."
        ollama pull codellama:34b
        PRIMARY_MODEL="codellama:34b"
        ;;
    4)
        print_step "  Downloading all models..."
        ollama pull llama3.1:8b
        ollama pull llama3.1:70b
        ollama pull codellama:34b
        PRIMARY_MODEL="llama3.1:70b"
        ;;
    *)
        print_warning "Invalid choice, downloading llama3.1:8b"
        ollama pull llama3.1:8b
        PRIMARY_MODEL="llama3.1:8b"
        ;;
esac

print_step "  ✓ Models downloaded"

# ============================================================================
# STEP 4: SET UP OPENCLAW
# ============================================================================

print_step "Step 4/7: Setting up OpenClaw..."

# Create network
print_step "  Creating Docker network..."
docker network create daena-secure-net 2>/dev/null || print_step "  Network already exists"

# Generate gateway token
OPENCLAW_TOKEN=$(openssl rand -hex 32)

# Run OpenClaw container
print_step "  Starting OpenClaw container..."
docker run -d \
    --name openclaw-worker \
    --network daena-secure-net \
    -v openclaw-workspace:/workspace \
    -e OLLAMA_BASE_URL="http://host.docker.internal:11434" \
    -e LLM_PROVIDER="ollama" \
    -e LLM_MODEL="$PRIMARY_MODEL" \
    -p 18789:18789 \
    --restart unless-stopped \
    ghcr.io/openclaw/openclaw:latest 2>/dev/null || {
        print_warning "  OpenClaw container already exists, restarting..."
        docker restart openclaw-worker
    }

print_step "  ✓ OpenClaw running"

# ============================================================================
# STEP 5: INSTALL DAENA DEPENDENCIES
# ============================================================================

print_step "Step 5/7: Installing Daena dependencies..."

# Create virtual environment
if [ ! -d "venv" ]; then
    print_step "  Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
print_step "  Installing Python packages..."
pip install --quiet --upgrade pip
pip install --quiet \
    aiohttp \
    websockets \
    python-dotenv \
    pydantic \
    fastapi \
    uvicorn

print_step "  ✓ Dependencies installed"

# ============================================================================
# STEP 6: CONFIGURE ENVIRONMENT
# ============================================================================

print_step "Step 6/7: Configuring environment..."

# Create .env file
cat > .env << ENV
# Local LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
PRIMARY_LLM_MODEL=$PRIMARY_MODEL
FAST_LLM_MODEL=llama3.1:8b
CODE_LLM_MODEL=codellama:34b

# OpenClaw Configuration
OPENCLAW_GATEWAY_URL=ws://localhost:18789/ws
OPENCLAW_GATEWAY_TOKEN=$OPENCLAW_TOKEN

# Daena Configuration
DAENA_MODE=god_mode
DAENA_SELF_AWARE=true
AUTO_APPROVE_SAFE=true
AUTO_APPROVE_LOW=true

# Security
EMERGENCY_STOP_ENABLED=true
ENV

print_step "  ✓ Environment configured"
print_step "  OpenClaw Gateway Token: $OPENCLAW_TOKEN"

# ============================================================================
# STEP 7: CREATE QUICK START SCRIPTS
# ============================================================================

print_step "Step 7/7: Creating quick start scripts..."

# Start script
cat > start_daena.sh << 'SCRIPT'
#!/bin/bash
source venv/bin/activate
python daena_complete_implementation.py
SCRIPT

chmod +x start_daena.sh

# Status check script
cat > check_status.sh << 'SCRIPT'
#!/bin/bash
echo "Checking Daena system status..."
echo ""
echo "Ollama:"
curl -s http://localhost:11434/api/tags | python3 -m json.tool 2>/dev/null || echo "  Not running"
echo ""
echo "OpenClaw:"
docker ps | grep openclaw-worker || echo "  Not running"
echo ""
echo "Models available:"
ollama list
SCRIPT

chmod +x check_status.sh

print_step "  ✓ Scripts created"

# ============================================================================
# FINAL CHECKS
# ============================================================================

print_step "Running final checks..."

# Test Ollama
if curl -s http://localhost:11434/api/tags > /dev/null; then
    print_step "  ✓ Ollama is responding"
else
    print_warning "  Ollama may not be ready yet"
fi

# Test OpenClaw
if docker ps | grep openclaw-worker > /dev/null; then
    print_step "  ✓ OpenClaw is running"
else
    print_warning "  OpenClaw container check failed"
fi

# ============================================================================
# INSTALLATION COMPLETE
# ============================================================================

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║              INSTALLATION COMPLETE! 🎉                  ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "System Details:"
echo "  • Ollama:    http://localhost:11434"
echo "  • OpenClaw:  http://localhost:18789"
echo "  • Model:     $PRIMARY_MODEL"
echo ""
echo "Quick Start:"
echo "  1. Start Daena:   ./start_daena.sh"
echo "  2. Check status:  ./check_status.sh"
echo ""
echo "Configuration saved in: .env"
echo "Gateway token: $OPENCLAW_TOKEN"
echo ""
echo "Try these commands after starting:"
echo "  • chat Hello Daena, how are you?"
echo "  • status"
echo "  • task Research AI companies"
echo "  • reflect"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo "  Save your OpenClaw gateway token somewhere safe!"
echo "  You'll need it to access the OpenClaw UI."
echo ""
echo "Need help? Check the documentation:"
echo "  • DAENA_OPENCLAW_LOCAL_LLM_INTEGRATION.md"
echo "  • IMPLEMENTATION_GUIDE.md"
echo ""
echo -e "${GREEN}Happy building! 🚀${NC}"
echo ""

# Save installation info
cat > installation_info.txt << INFO
Daena Installation Complete
Date: $(date)
Primary Model: $PRIMARY_MODEL
OpenClaw Token: $OPENCLAW_TOKEN

Services:
- Ollama: http://localhost:11434
- OpenClaw: http://localhost:18789

Quick Start:
./start_daena.sh

Check Status:
./check_status.sh
INFO

echo "Installation info saved to: installation_info.txt"
echo ""
