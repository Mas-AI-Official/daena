"""Daena backend launcher with auto-port detection.

Usage:
    python run.py          # starts on PORT (default 8000), auto-finds free port
    python run.py --port 9000   # starts on 9000 or next free

Writes the actual port to .daena-port so bat files / frontend can read it.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import uvicorn

from app.core.config import get_settings


def find_free_port(start: int, max_tries: int = 20) -> int:
    """Return *start* if free, else scan upward until a free port is found."""
    for offset in range(max_tries):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}–{start + max_tries - 1}")


def _is_port_listening(port: int) -> bool:
    """Best-effort local listener check for stale port-file cleanup."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            return False


def _remove_stale_port_file(port_file: Path) -> None:
    """Remove `.daena-port` only when it points to a dead local port."""
    try:
        existing_port = int(port_file.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError, OSError):
        return
    if _is_port_listening(existing_port):
        return
    try:
        port_file.unlink()
        print(f"[Daena] Removed stale port file {port_file} -> {existing_port}")
    except OSError as exc:
        print(f"[Daena] Could not remove stale port file {port_file}: {exc}")


def main() -> None:
    settings = get_settings()
    desired_port = settings.port
    port_file = Path(__file__).parent / ".daena-port"
    _remove_stale_port_file(port_file)

    # CLI override: python run.py --port 9000
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            desired_port = int(sys.argv[idx + 1])

    if settings.auto_port:
        port = find_free_port(desired_port)
        if port != desired_port:
            print(f"[Daena] Port {desired_port} busy -> using {port}")
    else:
        port = desired_port

    # Do not publish `.daena-port` here. Uvicorn has not completed
    # FastAPI startup yet, and the frontend would proxy to a port that
    # may still be initializing or may fail before accepting requests.
    # `app.main.lifespan()` atomically writes this file only after
    # startup completes and removes it on shutdown.
    os.environ["DAENA_BOUND_PORT"] = str(port)
    os.environ["DAENA_PORT_FILE"] = str(port_file)
    diagnostics = settings.runtime_diagnostics()
    print(f"[Daena] Backend starting on http://localhost:{port}")
    print(
        "[Daena] Config contract: "
        f"{diagnostics['env_precedence']} "
        f"(env file: {diagnostics['env_file']}, present={diagnostics['env_file_present']})"
    )
    print(f"[Daena] API docs: http://localhost:{port}/docs")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
