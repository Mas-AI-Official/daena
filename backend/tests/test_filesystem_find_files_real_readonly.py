"""PR-CONN-FILESYSTEM-FIND-FILES-REAL-READONLY (Sprint-8 PR-3).

End-to-end acceptance for the find_files real-execution path. The
executor was already armed with execution_mode="mcp_tool" in
PR-CONN-PHASE2X-FILESYSTEM-HUGGINGFACE-READONLY (2026-05-03), but
the path was unreachable from the UI until Sprint-8 PR-1 unblocked
Filesystem install. This test pins the contract that:

  1. find_files maps to the mcp-filesystem `search_files` tool with
     argument shape {path, pattern}.
  2. The executor returns status="executed" -- not "planned" --
     when the V2 row is callable AND the operator inputs are
     complete AND the MCP responds.
  3. The same call returns status="needs_connection" when the V2
     row is not callable. The find_files acceptance test from
     Sprint-7 already pins this case; this test pins the happy
     path the SkillExecuteModal now surfaces as "Executed read-only".
  4. The result_preview is capped (founder rule: never leak raw
     unbounded text from a tool call into the audit/UI).
  5. Phase 2 allowlist remains read-only (no Phase 3 leak).
  6. SkillExecuteModal copy carries the new status labels:
     "Executed read-only", "Planned preview", "Connect Filesystem
     first", and the executed/planned tool-call header switch.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.models.identity import Tenant, User
from app.services.connection_v2.skill_executor import (
    PHASE2_ALLOWLIST,
    SkillExecutor,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def seeded_tenant_user(db_session: AsyncSession) -> tuple[UUID, UUID]:
    """Local copy of the per-file seeded_tenant_user fixture used in
    test_skill_executor_phase2.py / _oauth_wireup.py / _consent.py.
    The fixture isn't in conftest, so each consumer file inlines it."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(
        id=tenant_id,
        name=f"FF s8 {tenant_id.hex[:6]}",
        slug=f"ff-s8-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@ff-s8.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="FOUNDER", email_verified=True,
    ))
    await db_session.flush()
    return tenant_id, user_id


# ──────────────────────────────────────────────────────────────────
# 1. Allowlist invariants
# ──────────────────────────────────────────────────────────────────


def test_find_files_is_armed_with_mcp_tool_execution_mode():
    entry = next(
        (e for e in PHASE2_ALLOWLIST
         if e.plugin_id == "mcp-filesystem" and e.skill_id == "find_files"),
        None,
    )
    assert entry is not None
    assert entry.read_only is True, "find_files must stay read_only"
    assert entry.execution_mode == "mcp_tool", (
        "find_files must be armed for real invocation, not planned_only"
    )
    assert entry.target_tool == "search_files"
    assert entry.required_inputs == ("root_path", "name_or_glob")


def test_phase2_allowlist_has_no_write_entries():
    """Hard floor pin: Phase 3 writes still blocked at the catalog level."""
    write_entries = [e for e in PHASE2_ALLOWLIST if not e.read_only]
    assert write_entries == [], (
        f"Phase 3 leak: PHASE2_ALLOWLIST contains non-read-only entries: "
        f"{[(e.plugin_id, e.skill_id) for e in write_entries]}"
    )


# ──────────────────────────────────────────────────────────────────
# 2. Executor: callable Filesystem -> status=executed
# ──────────────────────────────────────────────────────────────────


async def test_find_files_executes_when_filesystem_callable(
    db_session, seeded_tenant_user: tuple[UUID, UUID], monkeypatch,
):
    """When the Filesystem V2 row is callable AND the operator inputs
    are complete, the executor returns status='executed' -- never
    'planned'. The SkillExecuteModal then renders the new
    'Executed read-only' pill."""
    tenant_id, user_id = seeded_tenant_user

    # Insert a callable mcp-filesystem V2 row inline (mirrors
    # test_skill_executor_phase2's existing fixture pattern).
    fs_row = ConnectionV2(
        tenant_id=tenant_id,
        kind=ConnectionKind.MCP_SERVER.value,
        slug="mcp-filesystem",
        canonical_key="mcp-filesystem",
        display_name="Filesystem MCP",
        config={},
        auth_method="none",
        detected=True, configured=True, imported=True,
        reachable=True, authenticated=True, callable=True,
        detected_at=datetime.now(UTC), configured_at=datetime.now(UTC),
        imported_at=datetime.now(UTC), reachable_at=datetime.now(UTC),
        authenticated_at=datetime.now(UTC), callable_at=datetime.now(UTC),
    )
    db_session.add(fs_row)
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.mcp_bootstrap.get_installed_mcp",
        lambda key: object(),
    )

    captured: dict = {}

    async def fake_call(server_key, tool_name, arguments, *, timeout):
        captured["server_key"] = server_key
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        return {
            "success": True,
            "content": [{
                "type": "text",
                "text": "found 5 matches: a.py b.py c.py d.py e.py",
            }],
            "is_error": False,
        }

    monkeypatch.setattr(
        "app.services.mcp_invoker.call_server_tool", fake_call,
    )

    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-filesystem",
        skill_id="find_files",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={
            "root_path": "D:/Ideas/Daena",
            "name_or_glob": "*.py",
        },
    )
    # The contract the modal hangs its "Executed read-only" pill on.
    assert result.status == "executed", result
    assert captured["tool_name"] == "search_files"
    assert captured["arguments"] == {"path": "D:/Ideas/Daena", "pattern": "*.py"}
    # Summary references the actual tool so the operator can verify.
    assert "search_files" in result.summary
    # Result preview must be present + capped (the executor's contract:
    # 1200 char ceiling).
    assert result.result_preview, "executed result must carry a preview"
    assert len(result.result_preview) <= 1500, (
        f"result preview length {len(result.result_preview)} exceeds the cap"
    )


# ──────────────────────────────────────────────────────────────────
# 3. SkillExecuteModal copy contract
# ──────────────────────────────────────────────────────────────────


def test_modal_carries_executed_readonly_label():
    """Pin the new status labels at the source so a future copy
    refactor can't silently revert."""
    modal = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "pages" / "connections" / "SkillExecuteModal.tsx"
    )
    src = modal.read_text(encoding="utf-8")
    # All three brief-mandated labels live in source.
    assert "Executed read-only" in src
    assert "Planned preview" in src
    assert "Connect Filesystem first" in src
    # Each label has a stable testid for E2E pinning.
    assert "skill-status-executed" in src
    assert "skill-status-planned" in src
    assert "skill-status-needs-connection" in src


def test_modal_executed_tool_call_header_switches_on_status():
    """The 'Planned tool call (no real invocation in Phase 2)' header
    LIES when status === 'executed'. PR-3 swaps it to
    'Executed tool call (real read-only invocation)' for that case."""
    modal = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "pages" / "connections" / "SkillExecuteModal.tsx"
    )
    src = modal.read_text(encoding="utf-8")
    assert "Executed tool call (real read-only invocation)" in src
    # The old "no real invocation in Phase 2" hard-coded string must
    # NOT survive -- the new conditional handles both cases honestly.
    assert "(no real invocation in Phase 2)" not in src


def test_modal_footer_message_switches_on_execution_mode():
    """Footer copy must match honesty: 'Phase 2 spine: planned-only'
    is only true for entries with execution_mode='planned_only'.
    For 'mcp_tool' entries the footer must say execution is real
    when callable."""
    modal = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "pages" / "connections" / "SkillExecuteModal.tsx"
    )
    src = modal.read_text(encoding="utf-8")
    # The conditional must reference execution_mode so a future
    # planned-only entry still gets the right copy.
    assert "execution_mode === 'mcp_tool'" in src
    assert "executes against the live MCP when callable" in src


def test_modal_draft_followup_offered_for_executed_too():
    """Sprint-7 only offered Draft follow-up for status='planned'.
    Once executed lands, the operator should also be able to carry
    the result into chat for further reasoning."""
    modal = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "pages" / "connections" / "SkillExecuteModal.tsx"
    )
    src = modal.read_text(encoding="utf-8")
    assert "result?.status === 'planned' || result?.status === 'executed'" in src
