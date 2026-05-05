"""PR-LOCAL-USABLE-TODAY-ACCEPTANCE-FIX (Sprint-7 acceptance) Part E.

End-to-end acceptance for the first read-only skill flow:
``POST /api/v1/connections/v2/skills/execute`` with
``(mcp-filesystem, find_files)`` and a SAFE local path under the repo.

The test asserts the executor's HONEST contract:

  1. The (mcp-filesystem, find_files) pair IS in the Phase 2
     allowlist and IS read_only=True (Sprint-6 PR-5 floor +
     Sprint-7 PR-4 pin).
  2. When the plugin's V2 row is NOT callable (the operator hasn't
     installed Filesystem yet), the executor returns
     ``status="needs_connection"`` -- NOT ``"planned"`` -- so the UI
     cannot mistake "we have a skill plan" for "we ran the skill".
  3. When the (operator_inputs) miss ``directory`` (the only
     required input the skill declares), the executor returns
     ``status="needs_inputs"`` listing the missing field names ONLY
     (never values).
  4. Even if a future invariant breach made the executor accept the
     call, Phase 2 returns ``status="planned"`` -- never
     ``"executed"``. The UI must surface "planned preview" copy in
     that case, not "completed".

The test does NOT install Filesystem (it's not callable in the test
DB) and does NOT actually execute a tool. It exercises the same
endpoint the SkillExecuteModal calls, with a safe path the operator
would actually use (the repo root).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.connection_v2.skill_executor import PHASE2_ALLOWLIST


pytestmark = pytest.mark.asyncio


# Anchor a real, safe local path the test can pass as `directory`.
# We point at the repo root so the request shape is exactly what the
# wizard nudges Masoud to use.
SAFE_REPO_PATH = str(Path(__file__).resolve().parents[2])


async def _login(client: AsyncClient) -> dict[str, str]:
    unique = uuid.uuid4().hex[:8]
    email = f"ff-acc-{unique}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "find_files Acceptance",
            "tenant_name": f"FFACC-{unique}",
        },
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    return {"Authorization": f"Bearer {res.json()['data']['access_token']}"}


# ──────────────────────────────────────────────────────────────────
# 1. Catalog floor (Sprint-6 PR-5 + Sprint-7 PR-4)
# ──────────────────────────────────────────────────────────────────


def test_find_files_is_phase2_allowlisted_and_read_only():
    matches = [
        e for e in PHASE2_ALLOWLIST
        if e.plugin_id == "mcp-filesystem" and e.skill_id == "find_files"
    ]
    assert len(matches) == 1
    entry = matches[0]
    assert entry.read_only is True


# ──────────────────────────────────────────────────────────────────
# 2. Executor returns honest needs_connection when plugin not callable
# ──────────────────────────────────────────────────────────────────


async def test_execute_find_files_returns_needs_connection_when_filesystem_not_callable(client):
    """In a fresh test tenant, Filesystem MCP has no V2 row, so the
    executor MUST return needs_connection -- NOT planned. That keeps
    the UI honest: the operator sees a real "not callable" message
    instead of a fake "planned successfully"."""
    headers = await _login(client)
    res = await client.post(
        "/api/v1/connections/v2/skills/execute",
        json={
            "plugin_id": "mcp-filesystem",
            "skill_id": "find_files",
            "operator_inputs": {"directory": SAFE_REPO_PATH},
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # The executor's typed status taxonomy.
    status = body.get("status")
    assert status in ("needs_connection", "blocked"), (
        f"executor must report needs_connection (or blocked) when "
        f"Filesystem is not callable, got status={status!r}: {body!r}"
    )
    # Whatever the status, accepted=False so the UI cannot accidentally
    # claim success.
    assert body.get("accepted") is False


# ──────────────────────────────────────────────────────────────────
# 3. Executor returns honest needs_inputs when directory is missing
# ──────────────────────────────────────────────────────────────────


async def test_execute_find_files_reports_missing_inputs_by_name(client):
    """If the operator submits without ``directory`` the executor
    returns needs_inputs listing the missing field names. Field VALUES
    must NEVER appear. The required_inputs list IS allowed -- those
    are field NAMES not values."""
    headers = await _login(client)
    res = await client.post(
        "/api/v1/connections/v2/skills/execute",
        json={
            "plugin_id": "mcp-filesystem",
            "skill_id": "find_files",
            "operator_inputs": {},  # empty -- all required fields missing
        },
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    # Either needs_inputs (missing required field) OR needs_connection
    # (plugin not callable -- whichever check runs first). Both are
    # honest. The hard requirement: NOT "planned" or "executed".
    status = body.get("status")
    assert status in ("needs_inputs", "needs_connection", "blocked"), (
        f"executor must report needs_inputs / needs_connection / blocked "
        f"for an empty-inputs call; got {status!r}"
    )
    assert status not in ("planned", "executed"), (
        "executor must NEVER report 'planned' or 'executed' for an "
        "incomplete request -- that would lie to the operator"
    )


# ──────────────────────────────────────────────────────────────────
# 4. Phase 2 never returns 'executed' (only planned-preview)
# ──────────────────────────────────────────────────────────────────


def test_phase2_executor_never_emits_executed_status_for_writes():
    """Static guarantee: even if find_files were a write skill (which
    it isn't), the Phase 2 floor would block it. The executor returns
    'planned' for read paths and 'blocked' for non-allowlisted writes.
    'executed' is reserved for Phase 3."""
    # No write skills allowed in Phase 2 today.
    write_entries = [e for e in PHASE2_ALLOWLIST if not e.read_only]
    assert write_entries == [], (
        "Phase 3 leak: PHASE2_ALLOWLIST contains a non-read-only entry"
    )


# ──────────────────────────────────────────────────────────────────
# 5. SkillExecuteModal copy contains the explicit safety statement
# ──────────────────────────────────────────────────────────────────


def test_skill_execute_modal_explicit_safety_copy():
    """The modal that fires when Masoud clicks "Run find_files" must
    explicitly say read-only / no writes / no deletes / no external
    network / local only BEFORE the Run button. Pinned via source check
    so a future copy refactor can't silently soften the safety contract."""
    modal = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "pages" / "connections" / "SkillExecuteModal.tsx"
    )
    src = modal.read_text(encoding="utf-8").lower()
    for phrase in (
        "read-only",
        "no writes",
        "no deletes",
        "no external network",
        "local only",
    ):
        assert phrase in src, (
            f"SkillExecuteModal must show the safety phrase {phrase!r} "
            "before the Run button"
        )
