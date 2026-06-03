"""Sprint-13 PR-1 -- /api/v1/system/autonomy-mode contract.

Pins:
  1. GET + PUT mounted under /system/autonomy-mode.
  2. Five-state enum is locked: off, observe, research_draft,
     propose_actions, approved_execution.
  3. Default mode is research_draft.
  4. The hard-blocked action class list ALWAYS contains the items
     that map to Sprint-13's hard stops -- even in the most
     permissive mode (approved_execution). The blocker set is the
     wall, not the mode.
  5. PUT persists; subsequent GET reflects the change.
  6. Persistence file is gitignored (no secret leak path).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


# Hard-blocked classes the frontend depends on rendering verbatim.
_REQUIRED_HARD_BLOCKED = {
    "external_send_unapproved",
    "external_submit_unapproved",
    "external_post_unapproved",
    "external_apply_unapproved",
    "external_pay",
    "scan_unauthorized_target",
    "install_packages_globally",
    "deploy_production",
    "force_push",
    "secret_read",
}


class TestEndpointMounted:
    async def test_get_mounted_under_v1(self):
        from app.api.v1 import router as api_v1_router
        paths = [getattr(r, "path", "") for r in api_v1_router.routes]
        assert "/system/autonomy-mode" in paths

    async def test_put_mounted_under_v1(self):
        from app.api.v1 import router as api_v1_router
        # The same path serves both GET and PUT; verifying mount once
        # is enough, but we also verify both methods are registered.
        methods_for_path = set()
        for r in api_v1_router.routes:
            if getattr(r, "path", None) == "/system/autonomy-mode":
                methods_for_path.update(getattr(r, "methods", set()) or set())
        assert {"GET", "PUT"}.issubset(methods_for_path)

    async def test_put_is_role_gated(self):
        """GOV-01: the PUT (mutation) must be FOUNDER-gated.

        Autonomy mode is persisted to a single process-wide file (not
        tenant-scoped), so it governs the whole instance. Before the fix
        any authenticated user could change it. This asserts the PUT route
        carries the require_role dependency so the gate cannot silently
        regress; the GET (read) stays open to any authenticated user.
        """
        from app.api.v1 import router as api_v1_router

        put_route = next(
            r for r in api_v1_router.routes
            if getattr(r, "path", None) == "/system/autonomy-mode"
            and "PUT" in (getattr(r, "methods", set()) or set())
        )
        dep_calls = " ".join(
            repr(getattr(d, "call", d)) for d in put_route.dependant.dependencies
        )
        assert "check_role" in dep_calls or "require_role" in dep_calls, (
            "PUT /system/autonomy-mode must carry a require_role dependency "
            f"(GOV-01). Dependencies seen: {dep_calls}"
        )


class TestEnumLocked:
    async def test_five_states_locked(self):
        from app.api.v1.autonomy_mode import AutonomyMode

        # Locked set. Adding a state requires touching this test on
        # purpose so the frontend mode selector + hard-blocked map
        # never drift apart.
        expected = {
            "off",
            "observe",
            "research_draft",
            "propose_actions",
            "approved_execution",
        }
        actual = {m.value for m in AutonomyMode}
        assert actual == expected

    async def test_default_is_research_draft(self):
        from app.api.v1.autonomy_mode import _DEFAULT_MODE, AutonomyMode

        assert _DEFAULT_MODE == AutonomyMode.RESEARCH_DRAFT


class TestHardBlockedAlways:
    async def test_hard_blocked_set_present(self):
        from app.api.v1.autonomy_mode import _HARD_BLOCKED

        actual = set(_HARD_BLOCKED)
        missing = _REQUIRED_HARD_BLOCKED - actual
        assert not missing, (
            f"hard-blocked action classes missing: {sorted(missing)}"
        )

    async def test_no_mode_lifts_hard_blocks(self):
        """Even approved_execution, the most permissive mode, must
        never contain a hard-blocked class in its allowed list."""
        from app.api.v1.autonomy_mode import (
            _ALLOWED_BY_MODE,
            _HARD_BLOCKED,
            AutonomyMode,
        )

        hard = set(_HARD_BLOCKED)
        for mode, allowed in _ALLOWED_BY_MODE.items():
            overlap = hard & set(allowed)
            assert not overlap, (
                f"mode {mode.value} allows hard-blocked classes: "
                f"{sorted(overlap)}"
            )


class TestPersistenceRoundTrip:
    async def test_write_then_read(self, tmp_path, monkeypatch):
        """Write a mode through the helper, then read it back. The
        persistence file is a small JSON document with mode +
        last_changed_at."""

        import app.api.v1.autonomy_mode as mod

        target = tmp_path / ".autonomy_mode.json"
        monkeypatch.setattr(mod, "_AUTONOMY_FILE", target)

        mod._write_persisted(mod.AutonomyMode.PROPOSE_ACTIONS)

        assert target.exists()
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["mode"] == "propose_actions"
        assert isinstance(payload["last_changed_at"], str)

        recovered, ts = mod._current_mode()
        assert recovered == mod.AutonomyMode.PROPOSE_ACTIONS
        assert isinstance(ts, str)

    async def test_corrupt_file_falls_back_to_default(self, tmp_path, monkeypatch):
        import app.api.v1.autonomy_mode as mod

        target = tmp_path / ".autonomy_mode.json"
        target.write_text("not-json", encoding="utf-8")
        monkeypatch.setattr(mod, "_AUTONOMY_FILE", target)

        mode, ts = mod._current_mode()
        assert mode == mod._DEFAULT_MODE
        assert ts is None


class TestNoSecretSurface:
    async def test_response_model_has_no_secret_fields(self):
        """The AutonomyState response model must not expose a token,
        api_key, secret, password, or env-var field. Any of those
        would mean the operator surface accidentally leaked a value
        from disk or env."""
        from app.api.v1.autonomy_mode import AutonomyState

        forbidden_substrings = ("token", "secret", "password", "api_key", "env")
        for field_name in AutonomyState.model_fields:
            lowered = field_name.lower()
            for needle in forbidden_substrings:
                assert needle not in lowered, (
                    f"AutonomyState exposes forbidden field name: {field_name}"
                )


class TestPersistenceFileGitIgnored:
    """The persistence file lives at backend/.autonomy_mode.json and
    must be in backend/.gitignore so a future commit can never
    accidentally publish the mode state."""

    async def test_in_gitignore(self):
        backend_root = Path(__file__).resolve().parents[1]
        gitignore = backend_root / ".gitignore"
        assert gitignore.exists(), "backend/.gitignore must exist"
        content = gitignore.read_text(encoding="utf-8")
        assert ".autonomy_mode.json" in content
