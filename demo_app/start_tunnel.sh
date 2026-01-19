#!/bin/bash
# ============================================
# Daena Live Demo - Cloudflare Tunnel Setup
# Exposes your local Daena instance to the internet
# ============================================

echo ""
echo "========================================"
echo " DAENA LIVE DEMO - CLOUDFLARE TUNNEL"
echo "========================================"
echo ""

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "[ERROR] cloudflared not found!"
    echo ""
    echo "Please install Cloudflare Tunnel:"
    echo "  macOS:   brew install cloudflare/cloudflare/cloudflared"
    echo "  Linux:   curl -LO https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x cloudflared-linux-amd64 && sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared"
    echo ""
    exit 1
fi

# Get the port (default 8000)
PORT=${1:-8000}

echo "[1/3] Starting Cloudflare Tunnel..."
echo "     Local server: http://localhost:$PORT"
echo ""

# Start tunnel (quick share mode - no account needed)
echo "[INFO] Creating temporary tunnel (valid for 24 hours)"
echo "[INFO] Share the URL that appears below with demo attendees"
echo ""

cloudflared tunnel --url http://localhost:$PORT

echo ""
echo "[DONE] Tunnel closed."
