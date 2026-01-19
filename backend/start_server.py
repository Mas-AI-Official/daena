#!/usr/bin/env python3
"""
Simple server startup script to avoid uvicorn multiprocessing issues
"""
import os
import sys
import uvicorn

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set environment variables
os.environ['PYTHONPATH'] = project_root

if __name__ == "__main__":
    # Start the server without multiprocessing
    host = os.getenv("BACKEND_HOST", os.getenv("HOST", "0.0.0.0"))
    port = int(os.getenv("BACKEND_PORT", os.getenv("PORT", "8000")))
    reload_enabled = os.getenv("DAENA_RELOAD", "true").strip().lower() in ("1", "true", "yes", "on")

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        reload_dirs=[project_root],
        access_log=False,
        workers=1,
        loop="asyncio"
    ) 