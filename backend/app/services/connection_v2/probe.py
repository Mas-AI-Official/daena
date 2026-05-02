"""Probe contract + registry (Phase 4b PR 1).

Per ADR-002 + V2 spec §14: ``callable=true`` requires an authenticated
END capability call to succeed, NOT just "binary exists."

Phase 4b PR 1 ships the contract + a NoopProbe (test-only) + a
``ProbeRegistry`` keyed by ``ConnectionKind``. Per-kind real probe
implementations land in Phase 4b PR 2 alongside the 5 lying-CLI-adapter
rewrites (claude_code, codex, gemini_cli, grok_cli, mcp_bridge).

Phase 4b PR 1 deliberately does NOT implement the real probes -- those
need their own design pass with Founder review (HTTP allowlists,
DNS rebinding defense, rate limits per V2 §14 + ADR-002).

PR-CONNECTIONS-TRUTH-CLEANUP (2026-05-02): the registry no longer
auto-installs NoopProbe for every ConnectionKind. NoopProbe defaults
to ``success=True``, which made every unimplemented kind silently
report healthy. Now: an unregistered kind returns a structured
``probe_unavailable`` failure (success=False, failure_dim="callable")
so the V2 truth surface and audit log show the gap honestly.
NoopProbe is still available; tests register it explicitly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from app.models.connection_v2 import ConnectionKind, ConnectionV2


@dataclass
class ProbeResult:
    """Outcome of a single probe run.

    NEVER includes secret material. Failure_dim names which truth
    dimension is now false (per ADR-002 D-001 -- per-dim failure).
    """

    success: bool
    failure_dim: str | None = None  # 'reachable' | 'authenticated' | 'callable'
    failure_reason: str | None = None
    capabilities: list[dict] = field(default_factory=list)  # opaque per-kind
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Probe(ABC):
    """Abstract per-kind probe.

    Implementations live in Phase 4b PR 2; this PR ships only the
    contract + NoopProbe so the registry/state-machine wiring is
    testable without introducing real I/O.
    """

    kind: ConnectionKind

    @abstractmethod
    async def run(self, row: ConnectionV2) -> ProbeResult:
        """Run the probe and return a structured outcome.

        Implementations MUST NOT raise -- structured failure in
        ``ProbeResult.failure_dim`` is required so the registry can
        record per-dim failure metadata atomically.
        """
        raise NotImplementedError


class NoopProbe(Probe):
    """Test/dev probe that succeeds or fails based on row.config['_test_probe'].

    Used by tests to deterministically trigger success/failure paths.
    Real per-kind probes ship in Phase 4b PR 2.
    """

    kind = None  # type: ignore[assignment]

    def __init__(self, kind: ConnectionKind):
        self.kind = kind

    async def run(self, row: ConnectionV2) -> ProbeResult:
        directive = (row.config or {}).get("_test_probe", "success")
        if directive == "fail_reachable":
            return ProbeResult(success=False, failure_dim="reachable", failure_reason="unreachable (test)")
        if directive == "fail_auth":
            return ProbeResult(success=False, failure_dim="authenticated", failure_reason="auth failed (test)")
        if directive == "fail_callable":
            return ProbeResult(success=False, failure_dim="callable", failure_reason="capability call failed (test)")
        if directive == "raise":
            return ProbeResult(success=False, failure_dim="callable", failure_reason="probe raised (test)")
        return ProbeResult(
            success=True,
            capabilities=(row.config or {}).get("_test_capabilities", []),
        )


# Registry keyed by ConnectionKind value.
PROBE_REGISTRY: dict[str, Probe] = {}


def register_probe(probe: Probe) -> None:
    """Register a probe for a given ConnectionKind. Last-write-wins."""
    if probe.kind is None:
        raise ValueError("probe.kind must be set")
    key = probe.kind.value if hasattr(probe.kind, "value") else str(probe.kind)
    PROBE_REGISTRY[key] = probe


# Sentinel prefix for the "no real probe implementation yet" failure
# reason. The frontend can match on this prefix to render a distinct
# "Probe unavailable" pill (vs. "Probe failed").
PROBE_UNAVAILABLE_PREFIX = "probe_unavailable: "


async def run_probe(row: ConnectionV2) -> ProbeResult:
    """Resolve the probe for ``row.kind`` and run it. Always returns a
    ProbeResult; never raises (contract requirement).

    When no probe is registered for ``row.kind`` the result is
    structured (success=False, failure_dim="callable", failure_reason
    starts with PROBE_UNAVAILABLE_PREFIX) so the UI can distinguish
    "no probe implemented yet" from "probe ran and failed". This is
    the honest replacement for the prior auto-NoopProbe default that
    silently reported every kind healthy.
    """
    probe = PROBE_REGISTRY.get(row.kind)
    if probe is None:
        return ProbeResult(
            success=False,
            failure_dim="callable",
            failure_reason=(
                f"{PROBE_UNAVAILABLE_PREFIX}no real probe implementation "
                f"for kind {row.kind!r} yet -- callable cannot be proven"
            ),
        )
    try:
        return await probe.run(row)
    except Exception as exc:  # noqa: BLE001 -- contract: never raise
        return ProbeResult(
            success=False,
            failure_dim="callable",
            failure_reason=f"probe raised {type(exc).__name__}: {str(exc)[:200]}",
        )


def install_noop_probes_for_tests() -> None:
    """Test-only helper: register NoopProbe for every ConnectionKind.

    Production code path MUST NOT call this -- production wires real
    probes via ``app.services.connection_v2.probes.install_all_probes()``.
    Calling this from a test fixture lets tests exercise the
    state-machine + registry plumbing without doing real I/O.
    """
    for kind in ConnectionKind:
        PROBE_REGISTRY[kind.value] = NoopProbe(kind)
