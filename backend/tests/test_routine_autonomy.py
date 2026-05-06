"""Sprint-18 PR-4 -- routine autonomy scheduler skeleton contract.

Pins:
  1. RoutineKind values are exactly the 6 Sprint-18 allowed kinds.
  2. register_routine refuses unknown kind.
  3. pause / resume per-routine works.
  4. global pause blocks all run-once calls.
  5. Unknown routine_id returns UNKNOWN_ROUTINE outcome.
  6. Handler not registered returns HANDLER_NOT_REGISTERED.
  7. Handler that raises returns HANDLER_RAISED + does NOT propagate.
  8. Successful handler updates last_run_at + last_outcome.
  9. Module surface exposes NO callable named send / submit / post /
     pay / apply / commit -- scheduler is forbidden from these.
 10. run_once NEVER raises.
 11. State file is gitignored.
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services import routine_autonomy as mod

    monkeypatch.setattr(mod, "_STATE_FILE", tmp_path / ".routine_autonomy.json")
    mod._HANDLERS.clear()
    yield


class TestKindEnum:
    async def test_six_kinds_locked(self, isolated_state):
        from app.services.routine_autonomy import (
            RoutineKind, ROUTINE_KIND_VALUES,
        )

        assert ROUTINE_KIND_VALUES == frozenset({
            "opportunity_discovery",
            "business_workstream_proposal",
            "local_draft_action_creation",
            "self_diagnostic",
            "readiness_check",
            "repair_workstream_proposal",
        })
        # No SEND / SUBMIT / POST / PAY / APPLY / COMMIT kinds
        for k in RoutineKind:
            for forbidden in ("send", "submit", "post", "pay", "apply", "commit"):
                assert forbidden not in k.value


class TestRegister:
    async def test_register_known_kind(self, isolated_state):
        from app.services.routine_autonomy import register_routine

        r = register_routine(
            kind="opportunity_discovery",
            name="Daily competitor scan",
            description="Read-only research; produces local notes only.",
        )
        assert r.id
        assert r.kind == "opportunity_discovery"
        assert r.paused is False

    async def test_unknown_kind_refused(self, isolated_state):
        from app.services.routine_autonomy import register_routine

        with pytest.raises(ValueError):
            register_routine(
                kind="external_send_money_now",
                name="bad",
            )


class TestPauseResume:
    async def test_pause_and_resume_per_routine(self, isolated_state):
        from app.services.routine_autonomy import (
            register_routine, pause_routine, resume_routine,
        )

        r = register_routine(kind="self_diagnostic", name="x")
        paused = pause_routine(r.id)
        assert paused is not None
        assert paused.paused is True

        resumed = resume_routine(r.id)
        assert resumed is not None
        assert resumed.paused is False

    async def test_pause_unknown_returns_none(self, isolated_state):
        from app.services.routine_autonomy import pause_routine
        assert pause_routine("nonexistent") is None

    async def test_global_pause_resume(self, isolated_state):
        from app.services.routine_autonomy import (
            pause_all, resume_all, is_global_paused,
        )

        assert is_global_paused() is False
        pause_all()
        assert is_global_paused() is True
        resume_all()
        assert is_global_paused() is False


class TestRunOnce:
    async def test_unknown_routine_returns_unknown(self, isolated_state):
        from app.services.routine_autonomy import (
            run_once, RoutineOutcome,
        )
        result = await run_once("does-not-exist")
        assert result.outcome == RoutineOutcome.UNKNOWN_ROUTINE

    async def test_global_paused_blocks(self, isolated_state):
        from app.services.routine_autonomy import (
            register_routine, pause_all, run_once, RoutineOutcome,
        )
        r = register_routine(kind="self_diagnostic", name="x")
        pause_all()
        result = await run_once(r.id)
        assert result.outcome == RoutineOutcome.GLOBAL_PAUSED

    async def test_paused_routine_blocked(self, isolated_state):
        from app.services.routine_autonomy import (
            register_routine, pause_routine, run_once, RoutineOutcome,
        )
        r = register_routine(kind="self_diagnostic", name="x")
        pause_routine(r.id)
        result = await run_once(r.id)
        assert result.outcome == RoutineOutcome.PAUSED

    async def test_handler_not_registered(self, isolated_state):
        from app.services.routine_autonomy import (
            register_routine, run_once, RoutineOutcome,
        )
        r = register_routine(kind="self_diagnostic", name="x")
        result = await run_once(r.id)
        assert result.outcome == RoutineOutcome.HANDLER_NOT_REGISTERED

    async def test_successful_handler(self, isolated_state):
        from app.services.routine_autonomy import (
            register_routine, register_handler, run_once,
            RoutineOutcome, get_routine,
        )

        async def my_handler(**kwargs):
            return (["artifact-1", "artifact-2"], "ran ok")

        register_handler("self_diagnostic", my_handler)
        r = register_routine(kind="self_diagnostic", name="x")
        result = await run_once(r.id)

        assert result.outcome == RoutineOutcome.OK
        assert result.artifacts_created == ["artifact-1", "artifact-2"]
        assert result.detail == "ran ok"

        # State updated
        updated = get_routine(r.id)
        assert updated is not None
        assert updated.last_run_at is not None
        assert updated.last_outcome == "ok"

    async def test_handler_raises_does_not_propagate(self, isolated_state):
        from app.services.routine_autonomy import (
            register_routine, register_handler, run_once, RoutineOutcome,
        )

        async def bad_handler(**kwargs):
            raise RuntimeError("boom")

        register_handler("self_diagnostic", bad_handler)
        r = register_routine(kind="self_diagnostic", name="x")
        result = await run_once(r.id)

        assert result.outcome == RoutineOutcome.HANDLER_RAISED
        assert result.detail == "boom"

    async def test_run_once_never_raises_for_any_input(self, isolated_state):
        """Hand the function bizarre routine ids; it returns a typed
        result, never propagates."""
        from app.services.routine_autonomy import run_once

        for bad_id in ("", "x" * 1000, "nul\x00", "../../etc/passwd"):
            result = await run_once(bad_id)
            assert result.routine_id == bad_id
            # Outcome is either UNKNOWN_ROUTINE or another typed outcome
            # -- never an unhandled raise.


class TestForbiddenSurfaceAbsent:
    async def test_module_has_no_send_submit_post_pay_apply_commit(self):
        """Walk the public module surface. The scheduler is
        forbidden from external action verbs."""
        from app.services import routine_autonomy as mod

        forbidden = {
            "send", "submit", "post", "pay", "apply", "commit",
            "execute_send", "execute_submit", "execute_post",
            "execute_pay", "execute_apply", "execute_commit",
            "git_commit", "git_push", "push",
        }
        for name in dir(mod):
            if name.startswith("_"):
                continue
            assert name.lower() not in forbidden, (
                f"routine_autonomy exposes forbidden callable: {name}"
            )


class TestGitignored:
    async def test_state_file_in_gitignore(self):
        backend_root = Path(__file__).resolve().parents[1]
        gitignore = (backend_root / ".gitignore").read_text(encoding="utf-8")
        assert ".routine_autonomy.json" in gitignore
