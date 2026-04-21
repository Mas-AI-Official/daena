"""Lifecycle manager for llama.cpp ``llama-server.exe``.

Daena-owned llama-server process management. When a chat turn routes
to a specific GGUF (``coder`` for code tasks, ``gemma`` for
summarization, ``qwen3-8b`` for everything else), this manager
ensures that exact model is loaded before the provider makes its
HTTP request. Swap cost is ~5s cold start; we only pay it when a
different model is actually requested.

## Coordination with externally-launched llama-server

The user may have a llama-server running from the manual
``start-llama-server.ps1`` flow (e.g., Claude Code's MCP bridge
using the local worker for Opus delegation). Two safety modes:

* ``respect_external`` (default when LLAMA_SERVER_MANAGED=true):
  If the manager finds an existing llama-server it did not start
  (no Daena PID file), it will NOT kill it. Ensure-loaded becomes
  a no-op when the running model already matches; a mismatch logs
  a warning and falls back to "whatever is loaded" instead of
  swapping.

* ``force``: Daena always owns the process. Will SIGTERM any
  existing llama-server to install the requested model. Use only
  when you are not running Claude Code's MCP bridge concurrently.

## Mutex + cooldown

``ensure_loaded`` is protected by an asyncio lock so two concurrent
chat turns cannot race each other into spawning two processes. A
30s cooldown prevents thrash: if a swap just happened, a request
for a different model within the cooldown window prefers "use what
is loaded" over another swap. Both guards are tunable via env.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.providers.gguf_catalog import (
    CATALOG,
    DEFAULT_KEY,
    GGUFModel,
    find_by_served_name,
    get_model,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_LLAMA_SERVER_BIN = Path(r"D:\Ideas\llama.cpp\llama-server.exe")
_PID_FILE = Path(r"D:\Ideas\Daena\backend\.llama-server.pid")
_DEFAULT_PORT = 8080
_DEFAULT_NGL = 999
_STARTUP_TIMEOUT_S = 60.0   # Cold start on RTX 4060 is 5-10s; 60s is safe
_SWAP_COOLDOWN_S = 30.0     # Min seconds between swaps


class ManagedMode(str, Enum):
    """Three lifecycle modes gated by LLAMA_SERVER_MANAGED env."""
    OFF = "off"                      # Manual launch by user; manager is no-op
    RESPECT_EXTERNAL = "respect_external"  # Do not kill a server we did not start
    FORCE = "force"                  # Daena always owns the process


def _read_mode() -> ManagedMode:
    raw = (os.environ.get("LLAMA_SERVER_MANAGED") or "off").strip().lower()
    if raw in ("off", "false", "0", "no", ""):
        return ManagedMode.OFF
    if raw in ("true", "1", "yes"):
        # Generic "true" collapses to the SAFE mode so an accidental
        # flip does not clobber a Claude Code MCP session. You must
        # explicitly set "force" or "takeover" to get the kill-and-take
        # behavior.
        return ManagedMode.RESPECT_EXTERNAL
    if raw in ("respect", "respect_external"):
        return ManagedMode.RESPECT_EXTERNAL
    if raw in ("force", "kill", "takeover"):
        return ManagedMode.FORCE
    logger.warning(
        "llama_server_manager.unknown_mode",
        raw_value=raw,
        fallback="off",
    )
    return ManagedMode.OFF


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


@dataclass
class ManagerState:
    """Observable state snapshot, exposed via status endpoint."""

    mode: ManagedMode
    managed_pid: int | None
    external_pid: int | None
    current_model_key: str | None
    current_model_served: str | None
    last_swap_at: float
    port: int


class LlamaServerManager:
    """Singleton-ish manager for the llama-server process.

    In the WSL-backend / Windows-native split we shell out via
    subprocess to spawn llama-server on the Windows side. The PID we
    track is the Windows PID; SIGTERM/kill via ``taskkill`` when
    needed. When the backend runs native on Windows, standard
    subprocess signals work.
    """

    _instance: "LlamaServerManager | None" = None

    def __new__(cls) -> "LlamaServerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Idempotent init: __new__ returns the same instance so
        # subsequent __init__ calls must not reset live state.
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._lock = asyncio.Lock()
        self._mode = _read_mode()
        self._managed_pid: int | None = None
        self._current_model_key: str | None = None
        self._current_model_served: str | None = None
        self._last_swap_at: float = 0.0
        self._port = _DEFAULT_PORT
        self._base_url = f"http://127.0.0.1:{self._port}/v1"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def mode(self) -> ManagedMode:
        return self._mode

    def state(self) -> ManagerState:
        return ManagerState(
            mode=self._mode,
            managed_pid=self._managed_pid,
            external_pid=self._read_pid_file(),
            current_model_key=self._current_model_key,
            current_model_served=self._current_model_served,
            last_swap_at=self._last_swap_at,
            port=self._port,
        )

    async def ensure_loaded(self, model_key: str) -> GGUFModel:
        """Ensure the requested model is loaded on llama-server.

        Return the resolved ``GGUFModel`` entry so the caller can
        pass the ``served_name`` to the HTTP request. Behavior by
        mode:

        * OFF: no-op. Return the catalog entry for ``model_key`` and
          trust the caller to cope if llama-server has something else
          loaded (the vLLM provider will still forward the request;
          llama-server will usually just answer with whatever is in
          memory when the model-id does not match).

        * RESPECT_EXTERNAL: if the running server already has the
          requested model, no-op. Otherwise, if we started the
          server, swap. If it was externally launched, do NOT kill;
          log a warning and leave the current model.

        * FORCE: always swap to the requested model, killing any
          running llama-server first (ours or external).

        Raises RuntimeError on startup timeout or catalog-miss.
        """
        target = get_model(model_key)
        if target is None:
            raise RuntimeError(
                f"Unknown GGUF key {model_key!r}. "
                f"Catalog: {list(CATALOG.keys())}"
            )

        if self._mode == ManagedMode.OFF:
            return target

        async with self._lock:
            # Fast path: local in-memory state already knows this is
            # loaded. Avoids a redundant /v1/models probe AND makes
            # concurrent callers see the first caller's result
            # without a second network roundtrip (critical for the
            # mutex contract -- otherwise the second caller would
            # race into a duplicate spawn).
            if self._current_model_key == target.key:
                return target

            # Snapshot what is actually running right now.
            running = await self._probe_running_model()
            if running and self._matches(running, target):
                self._current_model_served = running
                self._current_model_key = target.key
                return target

            # Cooldown check: if we just swapped, prefer to serve with
            # whatever is loaded rather than thrash the GPU.
            if (
                self._last_swap_at
                and (time.time() - self._last_swap_at) < _SWAP_COOLDOWN_S
                and running
            ):
                logger.info(
                    "llama_server_manager.cooldown_active",
                    requested=target.key,
                    current=running,
                    seconds_since_swap=round(
                        time.time() - self._last_swap_at, 1,
                    ),
                )
                return target

            # Need to swap or start.
            external_pid = self._read_pid_file()
            if (
                self._mode == ManagedMode.RESPECT_EXTERNAL
                and external_pid is not None
                and self._managed_pid != external_pid
                and self._is_process_alive(external_pid)
            ):
                logger.warning(
                    "llama_server_manager.refused_to_swap",
                    reason="external_process_owns_server",
                    external_pid=external_pid,
                    requested=target.key,
                    running=running,
                    hint=(
                        "Set LLAMA_SERVER_MANAGED=force to let Daena "
                        "kill the external process."
                    ),
                )
                return target

            # Own or force-take the process.
            await self._stop_running()
            await self._start(target)
            self._last_swap_at = time.time()
            return target

    async def ensure_default(self) -> GGUFModel:
        """Ensure the default GGUF (qwen3-8b) is loaded."""
        return await self.ensure_loaded(DEFAULT_KEY)

    async def stop(self) -> None:
        """Best-effort stop of the managed process."""
        async with self._lock:
            await self._stop_running()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _probe_running_model(self) -> str | None:
        """Return served_name of the currently-loaded model, or None."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{self._base_url}/models")
                if r.status_code != 200:
                    return None
                data = r.json()
                models = data.get("data") or []
                if not models:
                    return None
                return str(models[0].get("id") or "")
        except Exception:
            return None

    def _matches(self, served_name: str, target: GGUFModel) -> bool:
        """True if the running server is serving the target model."""
        found = find_by_served_name(served_name)
        return found is not None and found.key == target.key

    async def _stop_running(self) -> None:
        """Terminate the managed llama-server if we have a PID."""
        pid = self._managed_pid or self._read_pid_file()
        if pid is None:
            return
        if not self._is_process_alive(pid):
            self._clear_pid_file()
            self._managed_pid = None
            return

        logger.info("llama_server_manager.stopping", pid=pid)
        try:
            # Windows: taskkill. Linux: os.kill.
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    check=False, capture_output=True, timeout=10,
                )
            else:
                os.kill(pid, signal.SIGTERM)
                await asyncio.sleep(1.0)
                if self._is_process_alive(pid):
                    os.kill(pid, signal.SIGKILL)
        except Exception as exc:  # pragma: no cover - best-effort
            logger.warning(
                "llama_server_manager.stop_failed", pid=pid, error=str(exc),
            )
        self._clear_pid_file()
        self._managed_pid = None
        self._current_model_key = None
        self._current_model_served = None

    async def _start(self, target: GGUFModel) -> None:
        """Spawn llama-server for ``target`` and wait for readiness."""
        if not _LLAMA_SERVER_BIN.is_file():
            raise RuntimeError(
                f"llama-server binary missing at {_LLAMA_SERVER_BIN}. "
                "Install llama.cpp CUDA build."
            )
        if not target.file_path.is_file():
            raise RuntimeError(
                f"Model file missing at {target.file_path}. "
                "Redownload under MODELS_ROOT/gguf."
            )

        cmd = [
            str(_LLAMA_SERVER_BIN),
            "-m", str(target.file_path),
            "-c", str(target.context_length),
            "-ngl", str(_DEFAULT_NGL),
            "--host", "127.0.0.1",
            "--port", str(self._port),
            "--jinja",
            "--parallel", "1",
        ]

        logger.info(
            "llama_server_manager.starting",
            model_key=target.key,
            file=str(target.file_path),
            port=self._port,
        )

        # Use DETACHED_PROCESS-ish spawn: stdout/stderr discarded so
        # the llama-server does not block Daena on its own buffer
        # fill. On Windows, CREATE_NEW_PROCESS_GROUP lets us
        # taskkill cleanly without affecting our own process tree.
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
                close_fds=(os.name != "nt"),
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to spawn llama-server: {exc}"
            ) from exc

        self._managed_pid = proc.pid
        self._write_pid_file(proc.pid)

        # Wait for readiness by polling /v1/models.
        deadline = time.time() + _STARTUP_TIMEOUT_S
        while time.time() < deadline:
            await asyncio.sleep(0.5)
            running = await self._probe_running_model()
            if running and self._matches(running, target):
                self._current_model_key = target.key
                self._current_model_served = running
                logger.info(
                    "llama_server_manager.ready",
                    model_key=target.key,
                    pid=proc.pid,
                    startup_seconds=round(
                        _STARTUP_TIMEOUT_S - (deadline - time.time()), 1,
                    ),
                )
                return

        # Timeout: kill and raise.
        logger.error(
            "llama_server_manager.startup_timeout",
            model_key=target.key,
            pid=proc.pid,
        )
        await self._stop_running()
        raise RuntimeError(
            f"llama-server did not serve {target.key!r} within "
            f"{_STARTUP_TIMEOUT_S}s. Check D:\\Ideas\\llama.cpp build."
        )

    # PID file helpers --------------------------------------------------

    def _read_pid_file(self) -> int | None:
        try:
            if not _PID_FILE.is_file():
                return None
            raw = _PID_FILE.read_text(encoding="utf-8").strip()
            return int(raw) if raw else None
        except Exception:
            return None

    def _write_pid_file(self, pid: int) -> None:
        try:
            _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            _PID_FILE.write_text(str(pid), encoding="utf-8")
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "llama_server_manager.pid_write_failed", error=str(exc),
            )

    def _clear_pid_file(self) -> None:
        try:
            _PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    def _is_process_alive(self, pid: int) -> bool:
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True, text=True, timeout=5,
                )
                return str(pid) in result.stdout
            os.kill(pid, 0)
            return True
        except Exception:
            return False


def get_manager() -> LlamaServerManager:
    """Module-level accessor for the singleton."""
    return LlamaServerManager()
