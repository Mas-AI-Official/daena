"""Verify ``ToolUseLoop._execute_tool`` runs every call through the permission guard.

``ExecutionService.execute_tool`` already has permission-resolver wiring
(see ``test_permission_dispatch_integration.py``). The Stage 8.5 agentic
path, however, bypasses ``ExecutionService`` entirely: the LLM emits a
``tool_call`` block that ``ChatOrchestrator`` hands directly to
``ToolUseLoop._execute_tool``.

Without a guard at that call site, a BLOCKed or ASKed tool would still
run whenever the LLM decided to invoke it. These tests pin the fix.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.constants import GovernanceMode
from app.models.governance import GoaRequest, PendingApproval
from app.models.identity import Tenant, User
from app.services.tool_use_loop import ToolUseLoop


# ── Helpers ────────────────────────────────────────────────────────


async def _seed_tenant_user(db) -> tuple[uuid.UUID, uuid.UUID]:
    tenant = Tenant(
        id=uuid.uuid4(),
        name="ToolLoopGuardOrg",
        slug=f"tlg-{uuid.uuid4().hex[:6]}",
    )
    db.add(tenant)
    await db.flush()
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"tlg-{uuid.uuid4().hex[:6]}@example.com",
        display_name="ToolLoop Guard Tester",
        password_hash="unused",
        role="OPERATOR",
    )
    db.add(user)
    await db.flush()
    return tenant.id, user.id


# ── Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_block_pref_refuses_without_dispatch(db_session) -> None:
    """BLOCK pref at the tool-loop level returns REFUSE, never dispatches."""
    tenant_id, user_id = await _seed_tenant_user(db_session)
    loop = ToolUseLoop(
        db_session,
        user_id,
        tenant_id,
        agi_mode=False,
        governance_mode=GovernanceMode.GOVERNED,
        extension_permissions={
            "filesystem": {"tools": {"file.read_file": "BLOCK"}},
        },
    )

    result = await loop._execute_tool(
        "file.read_file",
        {"path": "secret.txt"},
    )

    assert result["success"] is False
    assert result.get("governance") == "REFUSE"
    # BLOCK is the user's direct decision. It MUST NOT queue an
    # approval row because a human already decided.
    pending = (
        await db_session.execute(
            select(PendingApproval).where(PendingApproval.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_ask_pref_creates_approval_row(db_session) -> None:
    """ASK_EACH_TIME pref writes a GoaRequest + PendingApproval pair."""
    tenant_id, user_id = await _seed_tenant_user(db_session)
    loop = ToolUseLoop(
        db_session,
        user_id,
        tenant_id,
        agi_mode=False,
        governance_mode=GovernanceMode.GOVERNED,
        extension_permissions={
            "filesystem": {"tools": {"file.read_file": "ASK_EACH_TIME"}},
        },
    )

    result = await loop._execute_tool(
        "file.read_file",
        {"path": "notes.md"},
    )

    assert result["success"] is False
    assert result.get("governance") == "REQUEST_INPUT"
    assert "pending_approval" in result
    assert result["pending_approval"]["tool"] == "file.read_file"

    # Pair of rows MUST exist -- otherwise /governance/approvals is empty.
    pending = (
        await db_session.execute(
            select(PendingApproval).where(PendingApproval.tenant_id == tenant_id)
        )
    ).scalars().all()
    goa = (
        await db_session.execute(
            select(GoaRequest).where(GoaRequest.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert len(pending) == 1
    assert len(goa) == 1
    assert pending[0].request_id == goa[0].id


@pytest.mark.asyncio
async def test_unleashed_with_agi_mode_autoproceeds_low_risk(db_session) -> None:
    """UNLEASHED + AGI + no per-tool pref -> the guard lets the tool run.

    We do not actually assert the downstream dispatch succeeds (network,
    filesystem state etc. would matter). We only assert the guard did
    NOT refuse and did NOT queue approval. The dispatcher running the
    actual tool is exercised by other tests.
    """
    tenant_id, user_id = await _seed_tenant_user(db_session)
    loop = ToolUseLoop(
        db_session,
        user_id,
        tenant_id,
        agi_mode=True,
        governance_mode=GovernanceMode.UNLEASHED,
        extension_permissions=None,
    )

    result = await loop._execute_tool(
        "file.read_file",
        {"path": "/tmp/definitely-does-not-exist-xyz.txt"},
    )

    # Either the dispatcher ran (success True) or it failed for
    # dispatcher reasons (FileNotFoundError etc.), but it MUST NOT
    # have been blocked by governance. That is the invariant.
    assert result.get("governance") != "REFUSE"
    assert result.get("governance") != "REQUEST_INPUT"
    pending = (
        await db_session.execute(
            select(PendingApproval).where(PendingApproval.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_governed_high_risk_forces_approval_even_without_pref(
    db_session,
) -> None:
    """GOVERNED mode + high-risk tool queues approval regardless of prefs."""
    tenant_id, user_id = await _seed_tenant_user(db_session)
    loop = ToolUseLoop(
        db_session,
        user_id,
        tenant_id,
        agi_mode=False,
        governance_mode=GovernanceMode.GOVERNED,
        extension_permissions=None,
    )

    # terminal.execute_command is high-risk in the classifier; GOVERNED
    # mode escalates it to tier 3+.
    result = await loop._execute_tool(
        "terminal.execute_command",
        {"command": "echo hello"},
    )

    assert result["success"] is False
    # Either REQUEST_INPUT (gated) or REFUSE (if classifier pushed to
    # critical). Both are acceptable; the invariant is that the tool
    # did NOT run silently.
    assert result.get("governance") in ("REQUEST_INPUT", "REFUSE")
    # At least one approval row should exist for REQUEST_INPUT.
    if result.get("governance") == "REQUEST_INPUT":
        pending = (
            await db_session.execute(
                select(PendingApproval).where(PendingApproval.tenant_id == tenant_id)
            )
        ).scalars().all()
        assert len(pending) >= 1
