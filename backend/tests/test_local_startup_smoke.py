"""PR-DAENA-ONE-CLICK-LOCAL-START-SMOKE (Sprint-7 PR-1) tests.

Static validation of ``scripts/start-daena-local.bat`` plus opt-in
network probes that run only when a backend is actually up on
127.0.0.1:8000. These tests are safe to run in CI (network probes
auto-skip if no listener is present).

Pinned invariants:

  1. The launcher exists at the expected path.
  2. It calls the EXISTING path-scoped helpers (cleanup-stale-dev.ps1,
     start-backend-dev.bat, start-frontend-dev.bat) -- not raw
     ``taskkill /F /IM python.exe`` which would kill unrelated work
     elsewhere on the system.
  3. It prints the URLs the operator needs (health, diagnostic,
     connections page).
  4. It contains no blanket destructive patterns (format, rd /s,
     del /q /s C:\\, etc.).
  5. Optional: if backend is live, ``/health`` returns 200 and
     ``/api/v1/system/self-diagnostic`` returns 401/403 (route exists +
     auth gate intact).
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "start-daena-local.bat"
BACKEND = "http://127.0.0.1:8000"


# ──────────────────────────────────────────────────────────────────
# Static validation -- always runs
# ──────────────────────────────────────────────────────────────────


def test_script_exists():
    assert SCRIPT.is_file(), f"missing one-click launcher: {SCRIPT}"


def test_script_references_path_scoped_helpers():
    """The launcher must wrap the EXISTING safe helpers, not invent
    its own destructive process killers."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "cleanup-stale-dev.ps1" in text, (
        "must call the path-scoped cleanup helper"
    )
    assert "start-backend-dev.bat" in text, (
        "must delegate backend launch to the venv-pinned helper"
    )
    assert "start-frontend-dev.bat" in text, (
        "must delegate frontend launch to the path-scoped helper"
    )


def test_script_prints_user_urls():
    """A script that succeeds silently is useless; the operator needs
    to see the URLs to click."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "127.0.0.1:8000" in text
    assert "/health" in text
    assert "127.0.0.1:5173" in text
    assert "self-diagnostic" in text
    assert "/connections" in text


def test_script_has_no_blanket_destructive_calls():
    """A one-click launcher must NEVER reach for ``taskkill /F /IM
    python.exe`` style blanket killers that would terminate unrelated
    Python work on the laptop (Daena-Mind backups, ContentOps queues,
    LangChain experiments, etc.)."""
    text = SCRIPT.read_text(encoding="utf-8").lower()
    forbidden = [
        "taskkill /f /im python.exe",
        "taskkill /f /im node.exe",
        "format ",
        "rd /s ",
        "rmdir /s ",
        "del /q /s c:\\",
        # Also forbid anything that would mass-kill by uvicorn-without-path-scope
        "stop-process -name python",
        "stop-process -name node",
    ]
    for needle in forbidden:
        assert needle not in text, (
            f"start-daena-local.bat contains destructive pattern: {needle!r}"
        )


def test_script_does_not_use_uvicorn_reload():
    """Windows + venv + uvicorn --reload = the silent worker bug
    documented in start-backend-dev.bat. The one-click script must
    not regress this -- so ``--reload`` must not appear on any
    EXECUTABLE (non-comment, non-banner) line."""
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    for raw in lines:
        stripped = raw.lstrip().lower()
        # Skip bat-style comments (`::` or `rem `) and pure echo banners.
        if stripped.startswith("::") or stripped.startswith("rem "):
            continue
        if stripped.startswith("echo "):
            # Banners that document policy are fine.
            continue
        assert "--reload" not in stripped, (
            f"executable line uses uvicorn --reload (forbidden on Windows): {raw!r}"
        )


def test_script_probes_ipv6_and_port_roll():
    """Sprint-7 acceptance fix: Vite default-binds IPv6 (::1) and rolls
    to the next free port (5174..5180) when 5173 is held by another
    Vite. The launcher's frontend probe MUST cover both, otherwise it
    falsely reports 'frontend down' even when Vite is happily serving.
    Pinned here so a future PR cannot silently re-narrow the probe."""
    text = SCRIPT.read_text(encoding="utf-8")
    # IPv6 loopback probe present.
    assert "[::1]:" in text, (
        "frontend probe must hit IPv6 loopback; Vite default-binds ::1"
    )
    # Port roll covered (Vite picks the next free port up to ~5180).
    for port in (5174, 5175, 5176, 5177, 5178, 5179, 5180):
        assert str(port) in text, (
            f"frontend probe must cover Vite roll port {port}; otherwise "
            "the launcher reports 'frontend down' when 5173 is held"
        )


def test_script_documents_next_action_on_failure():
    """When backend or frontend doesn't come up, the script must tell
    the operator what to do next, not silently exit 0."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "[WARN]" in text
    assert "cleanup-stale-dev" in text  # appears in the failure hints too
    # Hint at the most common backend recovery paths
    assert "alembic upgrade head" in text
    assert "pip install -r requirements.txt" in text


# ──────────────────────────────────────────────────────────────────
# Opt-in network probes -- skip if backend not running
# ──────────────────────────────────────────────────────────────────


def _backend_up() -> bool:
    try:
        r = httpx.get(BACKEND + "/health", timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_health_endpoint_responds():
    r = httpx.get(BACKEND + "/health", timeout=2.0)
    assert r.status_code == 200


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_self_diagnostic_endpoint_route_is_registered():
    """Route IS registered (Sprint-6 PR-7). Without auth we expect
    401/403 -- the gate is intact."""
    r = httpx.get(BACKEND + "/api/v1/system/self-diagnostic", timeout=3.0)
    assert r.status_code in (401, 403), (
        f"diagnostic endpoint should require auth, got {r.status_code}"
    )
