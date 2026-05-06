"""Sprint-18 PR-5 -- trust-aware VP chat commands contract.

Pins:
  1. The 6 patterns recognize their canonical phrases.
  2. Unrelated text returns matched=False.
  3. Empty / non-string input returns matched=False (no raise).
  4. "what can you do without asking me" returns the auto-approved
     rows ONLY if the founder has actually granted a tier.
  5. "what still needs approval" includes all forbidden tools.
  6. "pause autonomy" mutates global_paused.
  7. "resume research-only autonomy" un-pauses but does NOT change
     trust tiers.
  8. NO command in this module reaches send / submit / post / pay /
     apply / commit dispatch surfaces.
  9. The summary string is deterministic, not LLM-generated.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services import (
        routine_autonomy, trust_ladder, trust_policy,
    )

    monkeypatch.setattr(
        trust_ladder, "_LADDER_FILE", tmp_path / ".trust_ladder.json",
    )
    monkeypatch.setattr(
        trust_policy, "_POLICY_FILE", tmp_path / ".trust_policy.json",
    )
    monkeypatch.setattr(
        routine_autonomy, "_STATE_FILE",
        tmp_path / ".routine_autonomy.json",
    )
    routine_autonomy._HANDLERS.clear()
    yield


class TestPatternMatch:
    @pytest.mark.parametrize("text,expected", [
        ("what can you do without asking me", "what_without_approval"),
        ("What CAN You Do Without Asking?", "what_without_approval"),
        ("what still needs approval", "what_needs_approval"),
        ("show trusted routines", "show_trusted_routines"),
        ("show routines", "show_trusted_routines"),
        ("pause autonomy", "pause_autonomy"),
        ("Pause All Autonomy", "pause_autonomy"),
        ("resume research-only autonomy", "resume_research_only_autonomy"),
        ("resume autonomy", "resume_research_only_autonomy"),
        ("why didn't you execute this", "why_not_executed"),
        ("why did you not execute", "why_not_executed"),
    ])
    async def test_recognized_phrase(self, isolated_state, text, expected):
        from app.services.trust_chat_commands import parse_and_run
        result = parse_and_run(text)
        assert result.matched is True
        assert result.command == expected

    async def test_unrelated_text_no_match(self, isolated_state):
        from app.services.trust_chat_commands import parse_and_run
        result = parse_and_run("hi how are you doing")
        assert result.matched is False
        assert result.command is None

    @pytest.mark.parametrize("bad", ["", None, 123, "   "])
    async def test_empty_or_non_string_no_match(self, isolated_state, bad):
        from app.services.trust_chat_commands import parse_and_run
        result = parse_and_run(bad)
        assert result.matched is False


class TestWhatWithoutApproval:
    async def test_empty_when_no_tiers_granted(self, isolated_state):
        from app.services.trust_chat_commands import parse_and_run
        result = parse_and_run("what can you do without asking me")
        assert result.matched is True
        assert result.structured["auto_approved"] == []

    async def test_lists_only_granted_tiers(self, isolated_state):
        from app.services.trust_chat_commands import parse_and_run
        from app.services.trust_policy import (
            TrustTier, set_max_auto_tier,
        )

        set_max_auto_tier(
            tool_id="gmail.create_draft",
            template_class="some-class",
            tier=TrustTier.AUTO_APPROVE_LOW_RISK,
            requested_by_user_id="founder",
            is_founder=True,
            confirmation_phrase=(
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.create_draft"
            ),
        )
        result = parse_and_run("what can you do without asking me")
        rows = result.structured["auto_approved"]
        assert len(rows) == 1
        assert rows[0]["tool_id"] == "gmail.create_draft"


class TestWhatNeedsApproval:
    async def test_includes_all_forbidden(self, isolated_state):
        from app.services.trust_chat_commands import parse_and_run
        result = parse_and_run("what still needs approval")
        gated = result.structured["always_gated"]
        assert "gmail.send_existing_draft" in gated
        assert "local.file_change_proposal.apply" in gated
        assert "local.git_commit_approved_patch" in gated


class TestPauseAndResume:
    async def test_pause_then_resume(self, isolated_state):
        from app.services import routine_autonomy
        from app.services.trust_chat_commands import parse_and_run

        # Pause
        result = parse_and_run("pause autonomy")
        assert result.matched is True
        assert routine_autonomy.is_global_paused() is True

        # Resume
        result = parse_and_run("resume research-only autonomy")
        assert result.matched is True
        assert routine_autonomy.is_global_paused() is False

    async def test_resume_does_not_change_trust_tiers(
        self, isolated_state,
    ):
        """The 'research-only' label means: routines run, but they
        STILL cannot auto-approve. Verify resuming doesn't somehow
        change tier policy."""
        from app.services import trust_policy
        from app.services.trust_chat_commands import parse_and_run

        before = list(trust_policy.list_policies())
        parse_and_run("pause autonomy")
        parse_and_run("resume research-only autonomy")
        after = list(trust_policy.list_policies())
        assert len(before) == len(after)


class TestNoForbiddenSurfaceReached:
    async def test_no_command_can_dispatch_send_or_apply(
        self, isolated_state,
    ):
        """Walk every command output. None of them should contain
        a key suggesting an external action fired."""
        from app.services.trust_chat_commands import parse_and_run

        for phrase in (
            "what can you do without asking me",
            "what still needs approval",
            "show trusted routines",
            "pause autonomy",
            "resume research-only autonomy",
            "why did you not execute this",
        ):
            r = parse_and_run(phrase)
            structured_str = str(r.structured).lower()
            assert "sent" not in structured_str
            assert "applied_at" not in structured_str
            assert "commit_sha" not in structured_str


class TestDeterministicSummary:
    async def test_summary_does_not_contain_random_punctuation(
        self, isolated_state,
    ):
        """LLM output usually contains exclamation marks, em-dashes,
        ellipses, or speculative qualifiers. Deterministic summary
        should not."""
        from app.services.trust_chat_commands import parse_and_run

        for phrase in (
            "what can you do without asking me",
            "what still needs approval",
            "show trusted routines",
            "pause autonomy",
            "resume research-only autonomy",
        ):
            r = parse_and_run(phrase)
            assert "!" not in r.summary
            assert "..." not in r.summary
            # No "I think" / "maybe" / "should" hedging
            assert "i think" not in r.summary.lower()
            assert "maybe" not in r.summary.lower()
