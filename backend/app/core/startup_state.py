"""Startup state tracker -- single source of truth for backend warming status.

Why this exists:
    Lifespan startup is split into two phases (2026-04-29 stabilization):
      * Essentials (sync, must complete before /health responds): logging,
        guardrail validation, table create_all, ALTER TABLE migrations,
        Redis health probe.
      * Deferred (background, runs after essentials + port-file publish):
        founder seed, dept seed, connector catalog, MCP registry, background
        queue, cron scheduler, runtime registry refresh, dream engine, TLM,
        evilbob auto-activate.

    `_publish_ready_port_file()` fires the moment essentials complete, so the
    frontend proxy follows the live port within 2s of `python run.py`. The
    deferred phase keeps progressing; consumers that need it (auth login for
    fresh-install founder, /api/v1/runtimes warming gate) read this state.

    Single shared instance per process. Thread-safe enough for our async
    cooperative use -- writes happen sequentially in the lifespan task,
    reads happen from request handlers.

Usage:
    from app.core.startup_state import startup_state

    # At lifespan start
    startup_state.mark_started()

    # As essentials complete
    startup_state.mark_essentials_ready()

    # As each deferred step starts
    startup_state.set_seed_phase("founder_seed")

    # When deferred completes
    startup_state.mark_seedings_complete()

    # In a request handler
    if not startup_state.seedings_complete:
        ...graceful warming behavior...
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class StartupState:
    """In-process startup state. One instance per process, lives in memory only."""

    started_at: float = 0.0
    essentials_ready: bool = False
    essentials_ready_at: float = 0.0
    seedings_complete: bool = False
    seedings_complete_at: float = 0.0
    seed_phase: str = "not_started"
    seed_errors: list[str] = field(default_factory=list)

    def mark_started(self) -> None:
        self.started_at = time.monotonic()
        self.seed_phase = "essentials"
        self.essentials_ready = False
        self.seedings_complete = False
        self.seed_errors = []

    def mark_essentials_ready(self) -> None:
        self.essentials_ready = True
        self.essentials_ready_at = time.monotonic()
        self.seed_phase = "deferred_pending"

    def set_seed_phase(self, phase: str) -> None:
        self.seed_phase = phase

    def record_seed_error(self, phase: str, error: str) -> None:
        # Keep the list bounded so a misbehaving probe loop can't grow this.
        self.seed_errors.append(f"{phase}: {error}")
        if len(self.seed_errors) > 20:
            self.seed_errors = self.seed_errors[-20:]

    def mark_seedings_complete(self) -> None:
        self.seedings_complete = True
        self.seedings_complete_at = time.monotonic()
        self.seed_phase = "complete"

    def to_dict(self) -> dict:
        """Serializable snapshot for /health/detailed."""
        now = time.monotonic()
        essentials_ms: int | None = None
        seedings_ms: int | None = None
        if self.essentials_ready_at and self.started_at:
            essentials_ms = int((self.essentials_ready_at - self.started_at) * 1000)
        if self.seedings_complete_at and self.started_at:
            seedings_ms = int((self.seedings_complete_at - self.started_at) * 1000)
        uptime_ms = int((now - self.started_at) * 1000) if self.started_at else 0
        return {
            "essentials_ready": self.essentials_ready,
            "seedings_complete": self.seedings_complete,
            "seed_phase": self.seed_phase,
            "uptime_ms": uptime_ms,
            "essentials_ms": essentials_ms,
            "seedings_ms": seedings_ms,
            "seed_errors": list(self.seed_errors),
        }


# Single shared instance. Imported across the codebase.
startup_state = StartupState()
