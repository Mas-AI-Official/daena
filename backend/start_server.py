#!/usr/bin/env python3
"""
Simple server startup script to avoid uvicorn multiprocessing issues.
On Windows, if port 8000 fails with WinError 10013 (access forbidden) or
address already in use, finds a working port by testing the socket *before*
starting uvicorn (uvicorn with --reload binds in a child process, so we must
reserve the port in this process first).
"""
import os
import socket
import sys
import uvicorn

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set environment variables
os.environ["PYTHONPATH"] = project_root

# Ports to try (WinError 10013 / WSAEADDRINUSE)
PORT_RETRY_START = 8000
PORT_RETRY_END = 8010


def _can_bind(host: str, port: int) -> bool:
    """Try to bind to (host, port). Return True if successful, False on permission/in-use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


if __name__ == "__main__":
    host = os.getenv("BACKEND_HOST", os.getenv("HOST", "127.0.0.1"))
    port_env = os.getenv("BACKEND_PORT", os.getenv("PORT", ""))
    try:
        first_port = int(port_env) if port_env.strip() else PORT_RETRY_START
    except ValueError:
        first_port = PORT_RETRY_START
    reload_enabled = os.getenv("DAENA_RELOAD", "true").strip().lower() in ("1", "true", "yes", "on")

    ports_to_try = [first_port] + [p for p in range(PORT_RETRY_START, PORT_RETRY_END + 1) if p != first_port]
    chosen_port = None

    for port in ports_to_try:
        if _can_bind(host, port):
            chosen_port = port
            break
        if port == first_port:
            print(f"[DAENA] Port {port} not available (WinError 10013 or in use), trying next ...", flush=True)
        else:
            print(f"[DAENA] Port {port} not available, trying next ...", flush=True)

    if chosen_port is None:
        print(
            f"[DAENA] ERROR: Could not bind to any port in {ports_to_try}. "
            "Try closing other apps or set BACKEND_PORT=8011.",
            file=sys.stderr,
        )
        sys.exit(1)

    if chosen_port != first_port:
        print(f"[DAENA] Using port {chosen_port} (fallback).", flush=True)
    os.environ["BACKEND_PORT"] = str(chosen_port)

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=chosen_port,
        reload=reload_enabled,
        reload_dirs=[project_root],
        access_log=False,
        workers=1,
        loop="asyncio",
    ) 