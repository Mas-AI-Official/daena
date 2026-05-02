"""Probe truth contract tests (PR-CONNECTIONS-TRUTH-CLEANUP, 2026-05-02).

These tests pin the contract change introduced by Phase A of the
Connections Truth Cleanup:

  Before: ``probe.py`` auto-installed ``NoopProbe`` for every
  ``ConnectionKind`` at module import. ``NoopProbe`` defaults to
  ``success=True``, so every unimplemented kind silently reported
  healthy. This violated CLAUDE.md Rule 17 (Honesty + Persistence
  + Visibility): the V2 panel showed "callable" pills for kinds that
  had never proven callable.

  After: an unregistered kind returns a structured ``ProbeResult``
  with ``success=False``, ``failure_dim="callable"``, and a
  ``failure_reason`` that starts with the ``PROBE_UNAVAILABLE_PREFIX``
  sentinel. The frontend can match on the prefix to render a distinct
  "Probe unavailable" pill instead of "Connected" or "Probe failed".

  Real probes (today: ``ProviderProbe`` for kind=provider) replace
  the missing default via ``install_all_probes()``. Tests register
  ``NoopProbe`` explicitly via ``install_noop_probes_for_tests()``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.services.connection_v2.probe import (
    PROBE_REGISTRY,
    PROBE_UNAVAILABLE_PREFIX,
    NoopProbe,
    Probe,
    ProbeResult,
    install_noop_probes_for_tests,
    register_probe,
    run_probe,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _row(kind: ConnectionKind, *, config: dict | None = None) -> ConnectionV2:
    """Build an in-memory ConnectionV2 row for unit testing.

    No DB required -- ``run_probe`` only reads ``row.kind`` and
    ``row.config``; we never persist.
    """
    row = ConnectionV2(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        kind=kind.value,
        slug="probe-test",
        display_name="Probe Test",
        canonical_key=f"{kind.value}::probe-test",
        auth_method=AuthMethod.NONE.value,
        trust_tier="official",
        config=config or {},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return row


@pytest.fixture
def isolated_registry():
    """Snapshot + restore PROBE_REGISTRY around each test.

    These tests mutate the global registry. Without this fixture a
    test that wipes the registry would break subsequent tests that
    rely on default registration (e.g. test_connection_v2.py +
    test_phase7_provider_probes.py).
    """
    snapshot = dict(PROBE_REGISTRY)
    yield PROBE_REGISTRY
    PROBE_REGISTRY.clear()
    PROBE_REGISTRY.update(snapshot)


# ----------------------------------------------------------------------
# 1 -- unimplemented kind returns probe_unavailable, not 500
# ----------------------------------------------------------------------


class TestProbeUnavailable:
    @pytest.mark.asyncio
    async def test_no_probe_returns_probe_unavailable_not_500(
        self, isolated_registry,
    ):
        """run_probe on a kind with no registered probe returns a
        structured failure result. It MUST NOT raise -- the registry
        contract guarantees `never raises`."""
        PROBE_REGISTRY.clear()  # explicitly empty

        result = await run_probe(_row(ConnectionKind.PLUGIN))

        assert isinstance(result, ProbeResult)
        assert result.success is False
        assert result.failure_dim == "callable"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(PROBE_UNAVAILABLE_PREFIX)
        # Sentinel prefix is exactly what the UI matches on -- pin it
        # so a refactor doesn't silently change the wire shape.
        assert PROBE_UNAVAILABLE_PREFIX == "probe_unavailable: "

    @pytest.mark.asyncio
    async def test_probe_unavailable_reason_names_the_kind(
        self, isolated_registry,
    ):
        """The failure_reason must include the kind name so an
        operator reading the audit log can tell WHICH kind has no
        probe yet."""
        PROBE_REGISTRY.clear()

        for kind in (ConnectionKind.PLUGIN, ConnectionKind.OAUTH_APP, ConnectionKind.LOCAL_MODEL):
            result = await run_probe(_row(kind))
            assert kind.value in (result.failure_reason or ""), (
                f"failure_reason for {kind} should name the kind, got: "
                f"{result.failure_reason!r}"
            )


# ----------------------------------------------------------------------
# 2 -- registered probe is used (not the unavailable fallback)
# ----------------------------------------------------------------------


class TestRegisteredProbeUsed:
    @pytest.mark.asyncio
    async def test_registered_probe_runs_and_returns_real_result(
        self, isolated_registry,
    ):
        """When a probe IS registered for the kind, run_probe must
        dispatch to it -- the probe_unavailable fallback only fires
        when the registry has no entry for the kind."""
        PROBE_REGISTRY.clear()
        register_probe(NoopProbe(ConnectionKind.MCP_SERVER))

        # Default NoopProbe directive is "success".
        ok = await run_probe(_row(ConnectionKind.MCP_SERVER))
        assert ok.success is True
        assert ok.failure_dim is None

        # Directives still drive deterministic per-dim failures.
        fail = await run_probe(_row(
            ConnectionKind.MCP_SERVER,
            config={"_test_probe": "fail_reachable"},
        ))
        assert fail.success is False
        assert fail.failure_dim == "reachable"

    @pytest.mark.asyncio
    async def test_registered_probe_takes_precedence_over_fallback(
        self, isolated_registry,
    ):
        """Even if a kind would otherwise be unavailable, registering
        a probe makes the kind callable. Pins that the contract is
        registry-keyed by kind (no global lookup or hierarchy)."""
        PROBE_REGISTRY.clear()  # everything unavailable...
        bad = await run_probe(_row(ConnectionKind.PROVIDER))
        assert (bad.failure_reason or "").startswith(PROBE_UNAVAILABLE_PREFIX)

        register_probe(NoopProbe(ConnectionKind.PROVIDER))  # ...register one
        good = await run_probe(_row(ConnectionKind.PROVIDER))
        assert good.success is True


# ----------------------------------------------------------------------
# 3 -- failure_reason MUST NOT leak secret material
# ----------------------------------------------------------------------


class TestNoSecretLeakage:
    @pytest.mark.asyncio
    async def test_unavailable_failure_reason_never_includes_config_values(
        self, isolated_registry,
    ):
        """probe_unavailable is built from kind name only -- it MUST
        NOT echo back row.config values (where API keys could live in
        sloppy callers)."""
        PROBE_REGISTRY.clear()
        sneaky_value = "sk-NEVER_LOG_THIS_VALUE_xyz123abc456"

        result = await run_probe(_row(
            ConnectionKind.PROVIDER,
            config={
                "api_key": sneaky_value,
                "_provider_enum": "OPENAI",
                "secret_token": sneaky_value,
            },
        ))

        assert result.failure_reason is not None
        assert sneaky_value not in result.failure_reason
        assert "sk-" not in result.failure_reason
        assert "NEVER_LOG_THIS_VALUE" not in result.failure_reason

    @pytest.mark.asyncio
    async def test_raised_probe_failure_reason_never_includes_secrets(
        self, isolated_registry,
    ):
        """Even when a probe raises, run_probe wraps the exception in
        a ProbeResult whose failure_reason is bounded to the exception
        class name and a 200-char message snippet. Pin: the snippet
        truncates anything secret-shaped that a careless raise might
        have included."""

        class RaisingProbe(Probe):
            kind = ConnectionKind.PLUGIN

            async def run(self, row):
                raise RuntimeError(
                    "boom (do not include token "
                    + ("X" * 500)
                    + " here)"
                )

        register_probe(RaisingProbe())
        result = await run_probe(_row(ConnectionKind.PLUGIN))

        assert result.success is False
        assert result.failure_dim == "callable"
        assert result.failure_reason is not None
        # Truncation budget per probe.py: 200 chars after the prefix.
        # Total failure_reason fits within ~250 chars (prefix + class
        # name + bounded snippet).
        assert len(result.failure_reason) < 300
        assert "RuntimeError" in result.failure_reason


# ----------------------------------------------------------------------
# 4 -- module import does NOT auto-install NoopProbe defaults
# ----------------------------------------------------------------------


class TestNoAutoNoopInstall:
    def test_install_noop_probes_for_tests_is_explicit(self):
        """The OLD behavior was a module-level auto-install. The NEW
        contract is: tests opt in via ``install_noop_probes_for_tests``;
        production wires real probes via
        ``install_all_probes`` from ``connection_v2.probes``.

        Pin: ``install_noop_probes_for_tests`` is the only documented
        path to populate NoopProbe defaults. The legacy
        ``_install_default_noop_probes`` symbol is gone.
        """
        from app.services.connection_v2 import probe as probe_module

        assert hasattr(probe_module, "install_noop_probes_for_tests")
        assert not hasattr(probe_module, "_install_default_noop_probes"), (
            "The auto-install function was removed in PR-CONNECTIONS-TRUTH-"
            "CLEANUP. Adding it back would re-introduce the lying default."
        )

    def test_explicit_install_populates_every_kind(self, isolated_registry):
        """``install_noop_probes_for_tests`` is the test fixture's
        on-ramp: it registers a NoopProbe for every ConnectionKind so
        existing test_connection_v2.py + test_phase7_*.py tests still
        get deterministic _test_probe directive behavior."""
        PROBE_REGISTRY.clear()
        install_noop_probes_for_tests()
        for kind in ConnectionKind:
            assert kind.value in PROBE_REGISTRY
            assert isinstance(PROBE_REGISTRY[kind.value], NoopProbe)
