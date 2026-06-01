"""Sprint-8 PR-4 follow-up: AcceptanceStatusPanel must not lie about
backend health when the self-diagnostic endpoint is unavailable.

Bug surfaced from a live screenshot 2026-05-05: the panel showed
"Backend healthy: Backend not responding to /health." while
``curl http://127.0.0.1:8000/health`` returned 200. Root cause: the
panel derived ``backendStatus`` from ``diag === null`` (which is
true whenever ``/api/v1/system/self-diagnostic`` returns 401 for an
unauthenticated tab, even though /health itself is healthy).

This test pins the fix at the source level so a future refactor
can't reconflate the two signals:

  1. The panel imports + invokes a separate ``fetchHealth`` probe
     against the unauth'd /health endpoint.
  2. ``backendStatus`` is derived from the health probe, NOT from
     ``diag``.
  3. The "Backend not responding" copy gates on the loading flag so
     the panel never flashes a false-negative during initial load.
"""

from __future__ import annotations

from pathlib import Path


PANEL = (
    Path(__file__).resolve().parents[1].parent
    / "frontend" / "src" / "pages" / "connections" / "AcceptanceStatusPanel.tsx"
)


def test_panel_calls_health_endpoint_separately():
    src = PANEL.read_text(encoding="utf-8")
    assert "fetchHealth" in src, (
        "panel must probe /health independently of the auth-required "
        "self-diagnostic; otherwise a 401 on diag mislabels backend as "
        "down (Sprint-8 PR-4 honesty fix)"
    )
    assert "/health" in src
    # The probe must use raw fetch, NOT the api client (which carries
    # the JWT interceptor + would also 401-redirect to /login on a
    # missing token).
    #
    # 2026-06-01: the panel was intentionally refactored to hit the bare
    # ``fetch('/api/v1/health', ...)`` path instead of ``${base}/health``
    # (its own comments document the CORS reason). The contract is "raw
    # fetch to a /health path, not the axios api client" - assert THAT,
    # not the exact URL-construction syntax. Guard against regressing to
    # the api client by also forbidding ``api.get(.../health)``.
    assert "fetch(" in src and "/health" in src, (
        "panel must probe /health via raw fetch (not the api client)"
    )
    assert "api.get('/health')" not in src and 'api.get("/health")' not in src, (
        "panel must NOT route /health through the JWT api client"
    )


def test_panel_decouples_backend_from_self_diagnostic():
    src = PANEL.read_text(encoding="utf-8")
    # Rejected: deriving backendStatus from `diag === null`. The fix
    # routes backendStatus through the health probe.
    assert "diag === null && !loading\n    ? 'blocked'" not in src, (
        "panel must NOT mark backend blocked just because diag is null"
    )
    # Required: backendStatus is derived from `health` state.
    assert "backendStatus: RowStatus" in src
    assert "(health === 'unknown' ? 'blocked' : health)" in src, (
        "backendStatus must come from the /health probe state"
    )


def test_panel_self_diag_warning_when_backend_healthy_but_diag_failed():
    """If /health is green AND self-diag null, the selfdiag row should
    say warning (auth required / partial), not blocked. This matches
    reality: backend is up, but the auth'd diagnostic isn't available
    on this tab."""
    src = PANEL.read_text(encoding="utf-8")
    assert "backendStatus === 'healthy' ? 'warning' : 'blocked'" in src


def test_panel_loading_state_does_not_flash_false_negative():
    src = PANEL.read_text(encoding="utf-8")
    # The "Backend not responding" detail must gate on !loading so
    # the row doesn't briefly flash blocked during the initial probe.
    assert "loading\n    ? 'unknown'" in src or "loading ? 'Probing /health" in src
