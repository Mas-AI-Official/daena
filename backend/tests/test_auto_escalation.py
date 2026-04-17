"""Regression tests for the auto-EXE escalation behavior.

Pins the "Daena acts instead of suggesting" fix landed on 2026-04-16.
The previous behavior set ``exe_suggestion`` and required the user to
manually toggle EXE. The new behavior sets ``auto_escalate_exe=True``
when the intent is TOOL_USE, risk is manageable, and governance is not
GOVERNED -- the chat orchestrator then flips chat_mode to EXE for that
turn and dispatches the DaenaBot chain.
"""

from __future__ import annotations

from app.core.constants import ChatMode, GovernanceMode
from app.services.query_understanding import (
    QueryInput,
    QueryUnderstandingService,
    RiskLevel,
)


def _analyze(msg: str, mode: ChatMode, governance: GovernanceMode):
    service = QueryUnderstandingService()
    return service.analyze(
        QueryInput(
            raw_message=msg,
            execution_mode=mode,
            governance_mode=governance,
        )
    )


def test_auto_escalate_on_tool_use_in_cmd_with_balanced_governance() -> None:
    """Action intent in CMD + BALANCED -> auto-escalate to EXE."""
    result = _analyze(
        "delete the old cache directory under /tmp",
        ChatMode.CMD,
        GovernanceMode.BALANCED,
    )
    if result.intent.value == "TOOL_USE" and result.risk_level not in (
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ):
        assert result.auto_escalate_exe is True
        assert "auto-escalated" in (result.exe_suggestion or "").lower()


def test_governed_mode_blocks_auto_escalation() -> None:
    """GOVERNED mode must NEVER auto-escalate -- enterprise governance first."""
    result = _analyze(
        "install playwright and run the e2e tests",
        ChatMode.CMD,
        GovernanceMode.GOVERNED,
    )
    assert result.auto_escalate_exe is False


def test_simple_chat_does_not_escalate() -> None:
    """Conversational turns must never auto-escalate."""
    result = _analyze(
        "hi, how are you?",
        ChatMode.CMD,
        GovernanceMode.BALANCED,
    )
    assert result.auto_escalate_exe is False


def test_already_in_exe_mode_does_not_re_escalate() -> None:
    """When user is already in EXE, auto_escalate_exe must remain False."""
    result = _analyze(
        "run the database migration",
        ChatMode.EXE,
        GovernanceMode.BALANCED,
    )
    assert result.auto_escalate_exe is False


def test_high_risk_blocks_auto_escalation_even_in_balanced() -> None:
    """HIGH / CRITICAL risk blocks auto-escalation regardless of governance.

    The user must consent explicitly to irreversible or destructive actions
    even in BALANCED. Minimum floor -- governance-ready identity.
    """
    result = _analyze(
        "DROP TABLE users CASCADE on production",
        ChatMode.CMD,
        GovernanceMode.BALANCED,
    )
    if result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        assert result.auto_escalate_exe is False
