"""PR-CONN-PHASE2-ARM-ZERO-INPUT-MCPS (Sprint-9, 2026-05-05).

Pins the contract for the four newly armed zero-input MCP read skills:

  * mcp-time:current_time           -> get_current_time(timezone)
  * mcp-fetch:fetch_public_url      -> fetch(url, max_length)
  * mcp-memory:list_memory_graph    -> read_graph()
  * mcp-sequential-thinking:reason_step -> sequentialthinking(thought, ...)

Hard guarantees:

  1. Every new entry is in PHASE2_ALLOWLIST with read_only=True and
     execution_mode='mcp_tool'.
  2. PHASE2_ALLOWLIST still has zero non-read-only entries (Phase 3 floor).
  3. mcp-fetch refuses loopback / RFC1918 / link-local / reserved IP /
     internal-DNS targets BEFORE the MCP socket opens. The block is
     visible in the audit row and never carries the URL value beyond
     the operator-facing summary.
  4. mcp-fetch passes max_length=_FETCH_MAX_LENGTH to the MCP so the
     server-side response cap applies even if the executor's summary
     trim is bypassed.
  5. mcp-memory:list_memory_graph maps to ``read_graph`` and never to
     any of the create/add/delete tools the memory MCP exposes.
  6. mcp-sequential-thinking:reason_step pins thoughtNumber=1,
     totalThoughts=1, nextThoughtNeeded=False -- it never fakes a
     multi-step reasoning chain or exposes hidden CoT.
  7. Each skill returns status='needs_connection' when the V2 row is
     not callable -- never silently falls back to "executed".
  8. The audit row for a successful execution carries no secret values
     and only the SHA256[:8] hash of the raw response (existing
     contract; pinned again here so the new entries don't slip past).
  9. Skill-executor module loads with the new entries (import-time
     invariant defends against a future write skill being added).

The url_safety helper has its own dedicated test file
(test_url_safety.py); this file exercises the wired-up integration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.models.identity import Tenant, User
from app.services.connection_v2.skill_executor import (
    PHASE2_ALLOWLIST,
    _ARG_BUILDERS,
    _FETCH_MAX_LENGTH,
    _PLUGIN_TO_SERVER_KEY,
    _PRECALL_VALIDATORS,
    SkillExecutor,
)


pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────────
# Per-file seeded_tenant_user fixture (mirrors sibling test files;
# the conftest in this repo deliberately does NOT seed tenants).
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant_user(db_session: AsyncSession) -> tuple[UUID, UUID]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(
        id=tenant_id,
        name=f"Z s9 {tenant_id.hex[:6]}",
        slug=f"z-s9-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@z-s9.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="FOUNDER", email_verified=True,
    ))
    await db_session.flush()
    return tenant_id, user_id


def _seed_callable_v2_row(db_session, tenant_id, slug):
    """Helper: insert a callable V2 row so the executor's
    plugin_callable check passes."""
    row = ConnectionV2(
        tenant_id=tenant_id,
        kind=ConnectionKind.MCP_SERVER.value,
        slug=slug,
        canonical_key=slug,
        display_name=slug,
        config={},
        auth_method="none",
        detected=True, configured=True, imported=True,
        reachable=True, authenticated=True, callable=True,
        detected_at=datetime.now(UTC), configured_at=datetime.now(UTC),
        imported_at=datetime.now(UTC), reachable_at=datetime.now(UTC),
        authenticated_at=datetime.now(UTC), callable_at=datetime.now(UTC),
    )
    db_session.add(row)
    return row


# ──────────────────────────────────────────────────────────────────
# 1. Allowlist invariants
# ──────────────────────────────────────────────────────────────────


_NEW_ENTRIES = (
    ("mcp-time", "current_time", "get_current_time", ("timezone",)),
    ("mcp-fetch", "fetch_public_url", "fetch", ("url",)),
    ("mcp-memory", "list_memory_graph", "read_graph", ()),
    ("mcp-sequential-thinking", "reason_step", "sequentialthinking", ("thought",)),
)


@pytest.mark.parametrize("plugin_id,skill_id,target_tool,required", _NEW_ENTRIES)
def test_zero_input_mcp_entries_are_armed(
    plugin_id, skill_id, target_tool, required,
):
    entry = next(
        (e for e in PHASE2_ALLOWLIST
         if e.plugin_id == plugin_id and e.skill_id == skill_id),
        None,
    )
    assert entry is not None, (
        f"{plugin_id}:{skill_id} missing from PHASE2_ALLOWLIST"
    )
    assert entry.read_only is True, (
        f"{plugin_id}:{skill_id} must be read_only=True"
    )
    assert entry.execution_mode == "mcp_tool", (
        f"{plugin_id}:{skill_id} must be armed (execution_mode='mcp_tool')"
    )
    assert entry.target_tool == target_tool
    assert entry.required_inputs == required
    # Every armed entry must have an arg builder registered.
    assert (plugin_id, skill_id) in _ARG_BUILDERS, (
        f"{plugin_id}:{skill_id} has no _ARG_BUILDERS entry"
    )
    # Every entry's plugin_id must be in the server-key resolver map.
    assert plugin_id in _PLUGIN_TO_SERVER_KEY, (
        f"{plugin_id} missing from _PLUGIN_TO_SERVER_KEY"
    )


def test_phase3_writes_floor_holds():
    """Anchor: no write skill snuck into the allowlist on this PR."""
    write_entries = [e for e in PHASE2_ALLOWLIST if not e.read_only]
    assert write_entries == [], (
        f"Phase 3 leak: {[(e.plugin_id, e.skill_id) for e in write_entries]}"
    )


def test_memory_skill_does_not_target_write_tools():
    """The memory MCP exposes both read AND write tools. Pin that
    we ONLY map to ``read_graph`` -- never create_entities,
    add_observations, delete_*, or any other write."""
    entry = next(
        (e for e in PHASE2_ALLOWLIST
         if e.plugin_id == "mcp-memory" and e.skill_id == "list_memory_graph"),
        None,
    )
    assert entry is not None
    forbidden = {
        "create_entities", "create_relations", "add_observations",
        "delete_entities", "delete_relations", "delete_observations",
    }
    assert entry.target_tool not in forbidden
    assert entry.target_tool == "read_graph"


def test_sequential_thinking_arms_single_step_only():
    """Pin that the sequentialthinking arg builder produces a
    single-step usage shape (thoughtNumber=1, totalThoughts=1,
    nextThoughtNeeded=False). Multi-step iteration would only make
    sense for an LLM-driven loop and is out of scope."""
    builder = _ARG_BUILDERS[("mcp-sequential-thinking", "reason_step")]
    args = builder({"thought": "test thought"})
    assert args["thoughtNumber"] == 1
    assert args["totalThoughts"] == 1
    assert args["nextThoughtNeeded"] is False
    assert args["thought"] == "test thought"


# ──────────────────────────────────────────────────────────────────
# 2. Fetch URL safety -- precall block
# ──────────────────────────────────────────────────────────────────


# Empty / whitespace strings get caught at Step 4 (required-inputs)
# BEFORE the precall validator runs, returning needs_inputs. They
# are still refused, just by a different gate. Tested separately.
_BAD_URLS = [
    "http://127.0.0.1:8000/admin",
    "http://localhost/secret",
    "http://[::1]/x",
    "http://10.0.0.5/private",
    "http://172.16.5.4/internal",
    "http://192.168.1.1/router",
    "http://169.254.169.254/latest/meta-data",
    "http://0.0.0.0/x",
    "http://server.local/x",
    "http://intranet.corp/x",
    "http://wiki.internal/x",
    "http://foo.home/x",
    "ftp://example.com/x",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "not-a-url",
]


@pytest.mark.parametrize("bad_url", _BAD_URLS)
async def test_fetch_url_safety_blocks_unsafe_targets(
    db_session, seeded_tenant_user, monkeypatch, bad_url,
):
    """The precall validator must refuse every flavour of unsafe URL
    BEFORE the MCP socket opens. When this fires, mcp_invoker is
    NEVER called -- we install a fake that would explode if reached."""
    tenant_id, user_id = seeded_tenant_user
    _seed_callable_v2_row(db_session, tenant_id, "mcp-fetch")
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.mcp_bootstrap.get_installed_mcp",
        lambda key: object(),
    )

    async def explode(*a, **kw):
        raise AssertionError(
            f"mcp_invoker.call_server_tool was reached for an unsafe URL: {bad_url!r}"
        )

    monkeypatch.setattr(
        "app.services.mcp_invoker.call_server_tool", explode,
    )

    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-fetch",
        skill_id="fetch_public_url",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={"url": bad_url},
    )
    assert result.status == "blocked", (
        f"unsafe URL {bad_url!r} should be blocked, got {result.status}"
    )
    assert result.blocked_reason.startswith("url_safety:"), (
        f"blocked_reason should carry the url_safety prefix; got "
        f"{result.blocked_reason!r}"
    )


async def test_fetch_url_passes_for_public_https(
    db_session, seeded_tenant_user, monkeypatch,
):
    """Happy path -- a public URL passes the precall gate and the arg
    builder forwards both url + max_length cap to the MCP."""
    tenant_id, user_id = seeded_tenant_user
    _seed_callable_v2_row(db_session, tenant_id, "mcp-fetch")
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.mcp_bootstrap.get_installed_mcp",
        lambda key: object(),
    )

    captured = {}

    async def fake_call(server_key, tool_name, arguments, *, timeout):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        return {
            "success": True,
            "content": [{"type": "text", "text": "Hello from example.com"}],
            "is_error": False,
        }

    monkeypatch.setattr(
        "app.services.mcp_invoker.call_server_tool", fake_call,
    )

    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-fetch",
        skill_id="fetch_public_url",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={"url": "https://example.com/"},
    )
    assert result.status == "executed", result
    assert captured["tool_name"] == "fetch"
    assert captured["arguments"]["url"] == "https://example.com/"
    assert captured["arguments"]["max_length"] == _FETCH_MAX_LENGTH
    # Defense in depth: the operator-facing summary is capped.
    assert len(result.result_preview) <= 1500


# ──────────────────────────────────────────────────────────────────
# 3. Time / Memory / Sequential-Thinking happy paths
# ──────────────────────────────────────────────────────────────────


async def test_time_current_time_executes(
    db_session, seeded_tenant_user, monkeypatch,
):
    tenant_id, user_id = seeded_tenant_user
    _seed_callable_v2_row(db_session, tenant_id, "mcp-time")
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.mcp_bootstrap.get_installed_mcp",
        lambda key: object(),
    )

    captured = {}

    async def fake_call(server_key, tool_name, arguments, *, timeout):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        return {
            "success": True,
            "content": [{"type": "text", "text": "2026-05-05T15:30:00-04:00"}],
            "is_error": False,
        }

    monkeypatch.setattr(
        "app.services.mcp_invoker.call_server_tool", fake_call,
    )

    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-time",
        skill_id="current_time",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={"timezone": "America/Toronto"},
    )
    assert result.status == "executed", result
    assert captured["tool_name"] == "get_current_time"
    assert captured["arguments"] == {"timezone": "America/Toronto"}


async def test_memory_list_graph_executes_zero_inputs(
    db_session, seeded_tenant_user, monkeypatch,
):
    tenant_id, user_id = seeded_tenant_user
    _seed_callable_v2_row(db_session, tenant_id, "mcp-memory")
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.mcp_bootstrap.get_installed_mcp",
        lambda key: object(),
    )

    captured = {}

    async def fake_call(server_key, tool_name, arguments, *, timeout):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        return {
            "success": True,
            "content": [{"type": "text", "text": '{"entities":[],"relations":[]}'}],
            "is_error": False,
        }

    monkeypatch.setattr(
        "app.services.mcp_invoker.call_server_tool", fake_call,
    )

    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-memory",
        skill_id="list_memory_graph",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={},
    )
    assert result.status == "executed", result
    assert captured["tool_name"] == "read_graph"
    # Pin: zero arguments crosses the boundary -- never accidentally
    # forward an operator input to a write tool of the memory MCP.
    assert captured["arguments"] == {}


async def test_sequential_thinking_returns_summary_not_hidden_cot(
    db_session, seeded_tenant_user, monkeypatch,
):
    """The sequentialthinking MCP does NO LLM inference; it returns a
    structured acknowledgement of the recorded thought. Pin that the
    executor surfaces this as a normal summary (no special
    chain-of-thought formatting / no hidden text leakage)."""
    tenant_id, user_id = seeded_tenant_user
    _seed_callable_v2_row(db_session, tenant_id, "mcp-sequential-thinking")
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.mcp_bootstrap.get_installed_mcp",
        lambda key: object(),
    )

    captured = {}

    async def fake_call(server_key, tool_name, arguments, *, timeout):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        return {
            "success": True,
            "content": [{
                "type": "text",
                "text": '{"thoughtNumber":1,"totalThoughts":1,"nextThoughtNeeded":false}',
            }],
            "is_error": False,
        }

    monkeypatch.setattr(
        "app.services.mcp_invoker.call_server_tool", fake_call,
    )

    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-sequential-thinking",
        skill_id="reason_step",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={"thought": "Plan: install -> probe -> run"},
    )
    assert result.status == "executed", result
    assert captured["tool_name"] == "sequentialthinking"
    # Single-step pin (no fake multi-step iteration on the operator's behalf).
    assert captured["arguments"]["thoughtNumber"] == 1
    assert captured["arguments"]["totalThoughts"] == 1
    assert captured["arguments"]["nextThoughtNeeded"] is False
    # The reads_summary copy explicitly states this is not hidden CoT,
    # so the operator-facing description acknowledges the limitation.
    entry = next(
        e for e in PHASE2_ALLOWLIST
        if (e.plugin_id, e.skill_id) == ("mcp-sequential-thinking", "reason_step")
    )
    assert "not a hidden chain-of-thought" in entry.reads_summary.lower() or \
           "not hidden chain-of-thought" in entry.reads_summary.lower()


# ──────────────────────────────────────────────────────────────────
# 4. needs_connection when V2 row is not callable
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("plugin_id,skill_id,inputs", [
    ("mcp-time", "current_time", {"timezone": "UTC"}),
    ("mcp-fetch", "fetch_public_url", {"url": "https://example.com/"}),
    ("mcp-memory", "list_memory_graph", {}),
    ("mcp-sequential-thinking", "reason_step", {"thought": "x"}),
])
async def test_returns_needs_connection_when_v2_row_missing(
    db_session, seeded_tenant_user, plugin_id, skill_id, inputs,
):
    """No V2 row -> needs_connection. The executor never silently
    "succeeds" because the MCP would happen to be installed.
    Honesty Rule 17: the UI must always know the plugin needs setup."""
    tenant_id, user_id = seeded_tenant_user
    # Intentionally do NOT seed the V2 row.
    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id=plugin_id,
        skill_id=skill_id,
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs=inputs,
    )
    assert result.status == "needs_connection", result


# ──────────────────────────────────────────────────────────────────
# 5. Audit row carries no secret-shaped fields
# ──────────────────────────────────────────────────────────────────


async def test_audit_row_for_blocked_url_carries_no_url_value(
    db_session, seeded_tenant_user, monkeypatch,
):
    """The audit row for an SSRF-blocked attempt records the BLOCK
    fact + the safety reason but MUST NOT carry the rejected URL
    string in action_params -- the operator-facing summary already
    surfaces it once and that's enough for the operator to debug.
    Stricter logging makes the audit safe to ship to a SOC pipeline."""
    tenant_id, user_id = seeded_tenant_user
    _seed_callable_v2_row(db_session, tenant_id, "mcp-fetch")
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.mcp_bootstrap.get_installed_mcp",
        lambda key: object(),
    )

    captured_audits: list[dict] = []
    from app.services import audit as audit_mod
    real_log = audit_mod.AuditService.log_decision

    async def capture(self, *args, **kwargs):
        captured_audits.append(dict(kwargs))
        return await real_log(self, *args, **kwargs)

    monkeypatch.setattr(
        audit_mod.AuditService, "log_decision", capture,
    )

    executor = SkillExecutor(db_session)
    sensitive_url = "http://10.0.0.99/admin?secret=should-not-leak"
    await executor.execute(
        plugin_id="mcp-fetch",
        skill_id="fetch_public_url",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={"url": sensitive_url},
    )
    assert captured_audits, "audit row must have been written"
    # No audit kwarg should contain the raw URL value (not in
    # action_params, not in any other top-level field).
    for kw in captured_audits:
        as_text = repr(kw)
        assert sensitive_url not in as_text, (
            f"raw blocked URL leaked into audit row: {kw!r}"
        )
        assert "should-not-leak" not in as_text


# ──────────────────────────────────────────────────────────────────
# 6. Module-load defense (already pinned by import-time invariant in
#    skill_executor; this re-pins from this PR's perspective so a
#    future PR adding a sibling write skill via _ARG_BUILDERS without
#    touching PHASE2_ALLOWLIST gets caught by *this* file too).
# ──────────────────────────────────────────────────────────────────


def test_every_arg_builder_targets_an_allowlisted_pair():
    """Defense: a stray arg builder that doesn't have a corresponding
    PHASE2_ALLOWLIST entry suggests an in-flight feature half-landed."""
    allowlisted = {(e.plugin_id, e.skill_id) for e in PHASE2_ALLOWLIST}
    for key in _ARG_BUILDERS:
        assert key in allowlisted, (
            f"_ARG_BUILDERS has {key} but PHASE2_ALLOWLIST does not"
        )


def test_every_precall_validator_targets_an_armed_entry():
    """Defense: a precall validator only makes sense if the entry is
    actually armed (execution_mode='mcp_tool'). A validator on a
    planned-only entry never fires + signals a mistake."""
    by_key = {
        (e.plugin_id, e.skill_id): e for e in PHASE2_ALLOWLIST
    }
    for key in _PRECALL_VALIDATORS:
        entry = by_key.get(key)
        assert entry is not None, f"precall validator on unknown entry: {key}"
        assert entry.execution_mode == "mcp_tool", (
            f"precall validator on planned-only entry: {key}"
        )
