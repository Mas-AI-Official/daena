#!/bin/bash
# Daena AI VP System - Linux/MacOS Launcher
# Version 2.1.0 - Enterprise-DNA + NBMF

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "   DAENA AI VP SYSTEM - LAUNCHER"
echo "   Version 2.1.0 - Enterprise-DNA + NBMF"
echo "   Phase 0-7 Complete (All Features)"
echo "========================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python is installed
echo "[1/12] Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 is not installed or not in PATH${NC}"
    echo "Please install Python 3.9+ and try again"
    exit 1
fi

python3 --version
echo ""

# Kill any existing Daena processes
echo "[2/12] Cleaning up existing processes..."
pkill -f "python.*backend.*start_server" 2>/dev/null || true
sleep 1
echo ""

# Check if virtual environment exists, create if not
echo "[3/12] Setting up virtual environment..."
if [ ! -d "venv_daena_main_py310" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv_daena_main_py310
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to create virtual environment${NC}"
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv_daena_main_py310/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Failed to activate virtual environment${NC}"
    exit 1
fi
echo ""

# Install/upgrade pip
echo "[4/12] Upgrading pip..."
pip install --upgrade pip --quiet
echo ""

# Install dependencies
echo "[5/12] Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}[WARNING] Some dependencies may have failed to install${NC}"
    fi
fi
echo ""

# Check database
echo "[6/12] Checking database..."
if [ ! -f "backend/daena.db" ]; then
    echo "Database not found, will be created on first run"
fi
echo ""

# Verify structure
echo "[7/12] Verifying organization structure..."
python3 Tools/verify_org_structure.py 2>/dev/null || echo -e "${YELLOW}[INFO] Structure verification skipped (non-critical)${NC}"
echo ""

# Start backend server
echo "[8/12] Starting backend server..."
echo ""
python3 backend/start_server.py &
SERVER_PID=$!

# Wait for server to start
echo "[9/12] Waiting for server to initialize..."
sleep 8

# Check if server is running
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${RED}[ERROR] Server failed to start${NC}"
    exit 1
fi

# Health check
echo "[10/12] Performing health check..."
for i in {1..10}; do
    if curl -s http://localhost:8000/api/v1/health/ > /dev/null 2>&1; then
        echo -e "${GREEN}[OK] Server is responding${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${YELLOW}[WARNING] Server may not be fully ready${NC}"
    else
        sleep 1
    fi
done
echo ""

# Display URLs
echo "========================================"
echo "   DAENA AI VP SYSTEM LAUNCHED"
echo "========================================"
echo ""
echo "Services:"
echo "   Backend Server:    http://localhost:8000"
echo "   API Docs:          http://localhost:8000/docs"
echo "   Health Check:      http://localhost:8000/api/v1/health/"
echo "   Structure Verify:  http://localhost:8000/api/v1/structure/verify"
echo "   DNA Health:        http://localhost:8000/api/v1/dna/{tenant_id}/health"
echo "   System Summary:    http://localhost:8000/api/v1/system/summary"
echo ""
echo "Dashboards:"
echo "   Main Dashboard:    http://localhost:8000"
echo "   Enhanced Dashboard: http://localhost:8000/enhanced-dashboard"
echo ""
echo "========================================"
echo ""

# Open browser (if on macOS or Linux with GUI)
if command -v open &> /dev/null; then
    # macOS
    open http://localhost:8000 2>/dev/null || true
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open http://localhost:8000 2>/dev/null || true
fi

echo -e "${GREEN}[SUCCESS] Daena AI VP System is running!${NC}"
echo ""
echo "Server PID: $SERVER_PID"
echo "To stop the server, run: kill $SERVER_PID"
echo ""
echo "Press Ctrl+C to exit (server will continue running in background)"
echo ""

# Keep script running
trap "echo ''; echo 'Exiting...'; exit 0" INT TERM
wait $SERVER_PID

