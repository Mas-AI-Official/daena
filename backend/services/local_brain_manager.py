"""
Local Brain Manager – Daena-managed Ollama fallback.

When primary Ollama (e.g. port 11434) is down, this module can start and manage
a local Ollama process on a fallback port (e.g. 11435) using MODELS_ROOT/ollama.
Uses the same Ollama binary so upgrades apply to both. GPU/CUDA-friendly env
to avoid crashes (OLLAMA_NUM_GPU, CUDA_VISIBLE_DEVICES).
"""

import os
import sys
import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_process: Optional[object] = None  # subprocess or asyncio create_subprocess
_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_models_path() -> str:
    try:
        from backend.config.settings import get_settings
        s = get_settings()
        path = getattr(s, "ollama_models_path", None) or (Path(s.models_root) / "ollama")
        return str(Path(path).resolve())
    except Exception:
        return str(Path(os.getenv("MODELS_ROOT", ".")) / "ollama")


def _get_fallback_port() -> int:
    try:
        from backend.config.settings import get_settings
        return int(get_settings().ollama_fallback_port)
    except Exception:
        return 11435


def _get_fallback_url() -> str:
    return f"http://127.0.0.1:{_get_fallback_port()}"


def _env_for_local_brain() -> dict:
    """Environment for Daena local Ollama: MODELS_ROOT, GPU limits, no telemetry."""
    env = os.environ.copy()
    models_path = _get_models_path()
    port = _get_fallback_port()
    env["OLLAMA_MODELS"] = models_path
    env["OLLAMA_HOST"] = f"127.0.0.1:{port}"
    # GPU: use one GPU by default to avoid OOM; user can override with CUDA_VISIBLE_DEVICES
    if "OLLAMA_NUM_GPU" not in env:
        env["OLLAMA_NUM_GPU"] = "1"
    # Optional: reserve GPU overhead to reduce crashes (e.g. 10% of VRAM)
    if "OLLAMA_GPU_OVERHEAD" not in env:
        env["OLLAMA_GPU_OVERHEAD"] = "10"
    env.setdefault("OLLAMA_ORIGINS", "*")
    return env


def _ollama_binary() -> Optional[str]:
    """Path to ollama executable (same binary as system Ollama)."""
    return shutil.which("ollama")


async def ensure_local_brain_running() -> bool:
    """
    If primary Ollama is down, start Daena local Ollama on fallback port.
    Returns True if fallback is (now) running, False otherwise.
    """
    try:
        from backend.config.settings import get_settings
        if not get_settings().ollama_use_local_brain_fallback:
            return False
    except Exception:
        return False

    global _process
    port = _get_fallback_port()
    url = _get_fallback_url()

    # Already running?
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{url}/api/tags")
            if r.status_code == 200:
                return True
    except Exception:
        pass

    binary = _ollama_binary()
    if not binary:
        logger.warning("Local brain fallback: 'ollama' not found in PATH. Install Ollama to enable fallback.")
        return False

    # Start ollama serve for fallback port (OLLAMA_HOST=127.0.0.1:port)
    env = _env_for_local_brain()
    try:
        proc = await asyncio.create_subprocess_exec(
            binary, "serve",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=os.getcwd(),
        )
        _process = proc
        logger.info("Local brain (Ollama fallback) starting on port %s with OLLAMA_MODELS=%s", port, env.get("OLLAMA_MODELS"))
        # Wait a few seconds for serve to bind
        for _ in range(15):
            await asyncio.sleep(1)
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    r = await client.get(f"{url}/api/tags")
                    if r.status_code == 200:
                        logger.info("Local brain (Ollama fallback) ready at %s", url)
                        return True
            except Exception:
                pass
            if proc.returncode is not None:
                stderr = (await proc.stderr.read()).decode() if proc.stderr else ""
                logger.warning("Local brain process exited: returncode=%s stderr=%s", proc.returncode, stderr[:500])
                return False
        logger.warning("Local brain did not respond within 15s")
        return False
    except Exception as e:
        logger.warning("Failed to start local brain fallback: %s", e)
        return False


def get_effective_ollama_base_url_sync() -> str:
    """
    Synchronous helper: return primary URL. Caller should use try/fallback logic
    in async code via try_primary_then_fallback.
    """
    try:
        from backend.config.settings import get_settings
        return get_settings().ollama_base_url or "http://localhost:11434"
    except Exception:
        return "http://localhost:11434"


async def try_primary_then_fallback() -> str:
    """
    Try primary Ollama; if unreachable, ensure local brain and return fallback URL.
    Returns the base URL to use (with /api/...).
    """
    import httpx
    try:
        from backend.config.settings import get_settings
        primary = (get_settings().ollama_base_url or "http://localhost:11434").strip()
    except Exception:
        primary = "http://localhost:11434"

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{primary.rstrip('/')}/api/tags")
            if r.status_code == 200:
                return primary
    except Exception as e:
        logger.debug("Primary Ollama not available: %s", e)

    try:
        from backend.config.settings import get_settings
        if not get_settings().ollama_use_local_brain_fallback:
            return primary
    except Exception:
        pass

    fallback_url = _get_fallback_url()
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{fallback_url}/api/tags")
            if r.status_code == 200:
                return fallback_url
    except Exception:
        pass

    if await ensure_local_brain_running():
        return fallback_url
    return primary
