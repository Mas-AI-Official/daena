"""PR-CONN-LIVE-PARITY-REPAIR regression tests.

Pins three behaviors from the parity repair PR:

1. ``_failure_reason`` suppresses stale ``probe_unavailable`` messages
   once a real probe is registered for the row's kind. Without this
   guard, a row probed BEFORE ``install_all_probes()`` ran keeps
   surfacing the legacy "no real probe implementation" pill in
   Advanced > Runtimes (V2) forever.

2. ``_failure_reason`` STILL surfaces ``probe_unavailable`` for a kind
   whose probe is genuinely not registered (so the gap stays honest).

3. ``install_all_probes()`` registers cli_runtime, mcp_server,
   oauth_app, api_provider, and skill_pack -- guarding against silent
   regressions where a probe class disappears from the install list
   and rows fall back to NoopProbe / unregistered.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.connection_v2 import probe as probe_module
from app.services.connection_v2.marketplace_service import _failure_reason
from app.services.connection_v2.probe import (
    PROBE_REGISTRY,
    PROBE_UNAVAILABLE_PREFIX,
)
from app.services.connection_v2.probes import install_all_probes


def _row(
    kind: str,
    *,
    callable_failure_reason: str | None = None,
    authenticated_failure_reason: str | None = None,
    reachable_failure_reason: str | None = None,
    configured_failure_reason: str | None = None,
):
    return SimpleNamespace(
        kind=kind,
        callable_failure_reason=callable_failure_reason,
        authenticated_failure_reason=authenticated_failure_reason,
        reachable_failure_reason=reachable_failure_reason,
        configured_failure_reason=configured_failure_reason,
    )


def test_failure_reason_suppresses_stale_probe_unavailable_after_install(
    monkeypatch,
):
    """A row probed BEFORE install_all_probes ran should not keep
    bleeding the legacy 'no real probe implementation' message into
    the marketplace card surface once a real probe is registered.
    """
    # Force a probe to be registered for cli_runtime
    monkeypatch.setitem(PROBE_REGISTRY, "cli_runtime", object())

    stale = (
        f"{PROBE_UNAVAILABLE_PREFIX}no real probe implementation "
        "for kind 'cli_runtime' yet -- callable cannot be proven"
    )
    row = _row("cli_runtime", callable_failure_reason=stale)

    assert _failure_reason(row) is None, (
        "Stale probe_unavailable failure must be hidden once a real "
        "probe is registered for the kind"
    )


def test_failure_reason_keeps_real_probe_failure_after_install(monkeypatch):
    """A non-PROBE_UNAVAILABLE failure (real probe ran and failed) must
    still surface even when a probe is registered.
    """
    monkeypatch.setitem(PROBE_REGISTRY, "cli_runtime", object())

    row = _row("cli_runtime", callable_failure_reason="binary_not_found: claude")

    assert _failure_reason(row) == "binary_not_found: claude"


def test_failure_reason_keeps_probe_unavailable_when_kind_unregistered(
    monkeypatch,
):
    """If the row's kind has NO probe registered, the probe_unavailable
    message is the honest answer and must still surface.
    """
    # Make sure the kind is NOT in the registry for this test
    monkeypatch.setattr(probe_module, "PROBE_REGISTRY", {})

    stale = (
        f"{PROBE_UNAVAILABLE_PREFIX}no real probe implementation "
        "for kind 'unknown_kind' yet -- callable cannot be proven"
    )
    row = _row("unknown_kind", callable_failure_reason=stale)

    # Re-import _failure_reason so it sees the patched module-level dict
    from app.services.connection_v2.marketplace_service import (
        _failure_reason as fr,
    )
    assert fr(row) == stale


def test_failure_reason_walks_truth_ladder():
    """Without a stale probe_unavailable, _failure_reason still picks
    the most actionable reason across the truth ladder
    (callable -> authenticated -> reachable -> configured).
    """
    row = _row(
        "cli_runtime",
        callable_failure_reason=None,
        authenticated_failure_reason="auth_failed: token expired",
        reachable_failure_reason=None,
        configured_failure_reason="config_missing: no _runtime_id",
    )
    # authenticated wins over configured per priority
    assert _failure_reason(row) == "auth_failed: token expired"


def test_install_all_probes_registers_required_kinds():
    """Guard against a probe disappearing from install_all_probes().
    Without this test, removing a single line from the function would
    silently revert that kind's UI pill to 'probe_unavailable' on
    every probe call -- exactly the symptom this PR fixes.
    """
    # Reset registry to pristine state then install
    PROBE_REGISTRY.clear()
    install_all_probes()

    # NOTE: V2 row kind for provider entries is "provider" (legacy short
    # name) while the catalog uses "api_provider". The probe registers
    # under the V2 row kind because that's what PROBE_REGISTRY.get(row.kind)
    # looks up at probe time.
    required_kinds = {
        "cli_runtime",
        "mcp_server",
        "oauth_app",
        "provider",
        "skill_pack",
    }
    missing = required_kinds - set(PROBE_REGISTRY.keys())
    assert not missing, (
        f"install_all_probes() must register every required probe kind. "
        f"Missing: {sorted(missing)}. Present: {sorted(PROBE_REGISTRY.keys())}"
    )


def test_install_all_probes_is_idempotent():
    """Re-calling install_all_probes() must not raise or duplicate
    registrations (last-write-wins semantics).
    """
    PROBE_REGISTRY.clear()
    install_all_probes()
    first_count = len(PROBE_REGISTRY)
    install_all_probes()
    install_all_probes()
    assert len(PROBE_REGISTRY) == first_count
