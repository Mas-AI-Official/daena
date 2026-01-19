#!/usr/bin/env python3
"""
Quick Start Server - Start Daena AI VP with minimal configuration
"""
import sys
import os
import subprocess
import time
import requests
from pathlib import Path

def check_server_running(port=8000):
    """Check if server is already running"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def start_server():
    """Start the FastAPI server"""
    print("="*70)
    print("Daena AI VP - Quick Start Server")
    print("="*70)
    print()
    
    # Check if server is already running
    if check_server_running():
        print("⚠️  Server is already running on port 8000")
        print("   Access: http://localhost:8000/command-center")
        return
    
    # Set minimal environment variables if not set
    if not os.getenv("DAENA_MEMORY_AES_KEY"):
        print("ℹ️  DAENA_MEMORY_AES_KEY not set, using default")
        os.environ["DAENA_MEMORY_AES_KEY"] = "default-key-change-in-production"
    
    if not os.getenv("DAENA_READ_MODE"):
        os.environ["DAENA_READ_MODE"] = "nbmf"
    
    if not os.getenv("DAENA_DUAL_WRITE"):
        os.environ["DAENA_DUAL_WRITE"] = "false"
    
    print("Starting FastAPI server...")
    print("Server will be available at: http://localhost:8000")
    print("Command Center: http://localhost:8000/command-center")
    print("API Docs: http://localhost:8000/docs")
    print()
    print("Press Ctrl+C to stop the server")
    print("="*70)
    print()
    
    # Start server
    try:
        import uvicorn
        uvicorn.run(
            "backend.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure all dependencies are installed: pip install -r requirements.txt")
        print("2. Check if port 8000 is available")
        print("3. Verify database is set up: python backend/scripts/recreate_database.py")
        sys.exit(1)

if __name__ == "__main__":
    start_server()

