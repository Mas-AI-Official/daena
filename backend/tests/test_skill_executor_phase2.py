"""Phase 2 read-only skill executor tests.

PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY (2026-05-03).

Pins the safety contract:
  * Allowlisted (plugin, skill) pairs return status="planned"
    (NOT "executed" -- Phase 2 spine never fires real tools).
  * Non-allowlisted pairs return status="blocked" with
    reason="not_in_phase2_allowlist".
  * Write skills that exist in the Phase 1 frontend registry
    (draft_reply, update_page, schedule_meeting,
    reconcile_subscriptions, capture_screenshot, fill_form_safe,
    open_page, run_smoke_test) MUST NOT appear in the Phase 2
    allowlist at all.
  * safe_query stays plan-only (per founder rule 16) -- not in
    the Phase 2 allowlist.
  * Plugin-not-callable returns status="needs_connection".
  * Missing required_inputs returns status="needs_inputs" with the
    list of missing field NAMES (never values).
  * Every accepted/blocked attempt writes a parent
    plugin.skill_invocation audit row.
  * No operator_inputs values appear in the audit trail or response.
  * Module-load invariant: every PHASE2_ALLOWLIST entry has
    read_only=True (re-checked by the executor at execute-time).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.models.identity import Tenant, User
from app.services.connection_v2.skill_executor import (
    PHASE2_ALLOWLIST,
    SkillExecutor,
    get_allowlist_entry,
    is_allowlisted,
    list_allowlist_for_api,
)


@pytest.fixture
async def seeded_tenant_user(
    db_session: AsyncSession,
) -> tuple[UUID, UUID]:
    """Insert a unique tenant + user so the audit FK on actor_id is
    satisfiable. Mirrors the pattern from test_audit_service_unit.py.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name=f"Phase2 Test {tenant_id.hex[:6]}",
        slug=f"phase2-test-{tenant_id.hex[:8]}",
    )
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@phase2.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="FOUNDER",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return tenant_id, user_id


# Skills that MUST NOT appear in the Phase 2 allowlist. Mirrors the
# founder's "Explicitly blocked in Phase 2" list. Failure here means a
# write skill snuck through and a future PR could turn it executable.
EXPLICITLY_BLOCKED_PAIRS: tuple[tuple[str, str], ...] = (
    # Slack write/draft surfaces -- founder rule 7 (no auto-send)
    ("mcp-slack", "draft_reply"),
    ("mcp-slack", "extract_tasks"),
    # Notion writes
    ("mcp-notion", "update_page"),
    # Calendar writes (creates event + sends invites)
    ("app-google-calendar", "schedule_meeting"),
    # Stripe writes
    ("mcp-stripe", "reconcile_subscriptions"),
    # Sentry writes
    ("mcp-sentry", "create_bug_task"),
    # safe_query -- intentional plan-only forever (founder rule 16)
    ("mcp-postgres", "safe_query"),
    ("mcp-sqlite", "safe_query"),
    ("mcp-mongodb", "safe_query"),
    ("mcp-supabase", "safe_query"),
    ("mcp-neon", "safe_query"),
    # Browser actions -- gated by Phase 3 browser action governance
    ("mcp-playwright", "open_page"),
    ("mcp-playwright", "fill_form_safe"),
    ("mcp-playwright", "capture_screenshot"),
    ("mcp-playwright", "run_smoke_test"),
    ("mcp-chrome-devtools", "capture_screenshot"),
    # Gmail draft / send surfaces
    ("app-gmail", "draft_reply"),
)


# ──────────────────────────────────────────────────────────────────
# Allowlist invariants (no DB needed)
# ──────────────────────────────────────────────────────────────────


def test_every_allowlist_entry_is_read_only():
    """Module-load invariant: every entry MUST declare read_only=True.
    Re-checked here so a future maintainer cannot bypass the
    import-time assertion via direct dict mutation."""
    for entry in PHASE2_ALLOWLIST:
        assert entry.read_only is True, (
            f"Phase 2 allowlist entry {entry.plugin_id}:{entry.skill_id} "
            f"has read_only=False. This is a Phase 3+ skill -- remove it."
        )


def test_every_allowlist_entry_is_planned_only():
    """Phase 2 ships PLANNED ONLY. No entry may declare execution_mode
    of 'mcp_tool' until follow-up PRs verify each integration
    end-to-end. This test fails the moment someone tries to flip it."""
    for entry in PHASE2_ALLOWLIST:
        assert entry.execution_mode == "planned_only", (
            f"Phase 2 entry {entry.plugin_id}:{entry.skill_id} has "
            f"execution_mode={entry.execution_mode!r}. Phase 2 ships "
            f"planned_only for ALL entries -- promotion happens in "
            f"separate per-integration PRs after safety verification."
        )


def test_every_allowlist_entry_has_required_inputs_declared():
    """Required inputs must be a non-empty tuple OR explicitly empty
    (some catalog skills like inspect_paper take a single optional id).
    We just enforce the field is declared (tuple type)."""
    for entry in PHASE2_ALLOWLIST:
        assert isinstance(entry.required_inputs, tuple)


def test_explicitly_blocked_skills_are_NOT_in_allowlist():
    """For each (plugin, skill) on the founder's explicit-block list,
    confirm is_allowlisted() returns False and get_allowlist_entry()
    returns None. Pins the contract per founder rule 14."""
    for plugin_id, skill_id in EXPLICITLY_BLOCKED_PAIRS:
        assert not is_allowlisted(plugin_id, skill_id), (
            f"Phase 2 allowlist contains explicitly-blocked skill "
            f"{plugin_id}:{skill_id}."
        )
        assert get_allowlist_entry(plugin_id, skill_id) is None


def test_allowlist_for_api_has_no_secret_fields():
    """The display-safe allowlist dump must not include any field
    that could carry a secret value. Allowed fields: plugin_id,
    skill_id, backend_surface, read_only, execution_mode,
    required_inputs, reads_summary."""
    expected_keys = {
        "plugin_id", "skill_id", "backend_surface", "read_only",
        "execution_mode", "required_inputs", "reads_summary",
    }
    for row in list_allowlist_for_api():
        assert set(row.keys()) == expected_keys


def test_starter_buckets_all_have_at_least_one_entry():
    """Founder's starter list: GitHub / Gmail / Drive / Slack / Sentry
    / HuggingFace / Filesystem / Databases. Each must contribute at
    least one allowlisted skill in this Phase 2 PR."""
    plugins = {entry.plugin_id for entry in PHASE2_ALLOWLIST}
    required_plugins = {
        "mcp-github", "app-gmail", "app-google-drive",
        "mcp-slack", "mcp-sentry", "mcp-huggingface",
        "mcp-filesystem",
    }
    missing = required_plugins - plugins
    assert not missing, f"Missing required Phase 2 plugins: {missing}"
    # At least one database describe_schema entry.
    db_describe = [
        entry for entry in PHASE2_ALLOWLIST
        if entry.skill_id in ("describe_schema", "describe_collections")
    ]
    assert len(db_describe) >= 1


# ──────────────────────────────────────────────────────────────────
# Executor behavior (DB needed)
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def callable_github_v2_row(
    db_session, seeded_tenant_user: tuple[UUID, UUID],
) -> ConnectionV2:
    """Insert a callable=true V2 row matching the mcp-github catalog
    entry's matches_v2_slug. Required so the executor's
    _is_plugin_callable check returns True. The tenant_id matches the
    seeded_tenant_user fixture so executor finds the row scoped to
    the same tenant the audit row will use."""
    tenant_id, _ = seeded_tenant_user
    row = ConnectionV2(
        tenant_id=tenant_id,
        kind=ConnectionKind.MCP_SERVER.value,
        slug="mcp-github",
        canonical_key="mcp-github",
        display_name="GitHub MCP",
        config={},
        auth_method="api_token",
        detected=True,
        configured=True,
        imported=True,
        reachable=True,
        authenticated=True,
        callable=True,
        detected_at=datetime.now(UTC),
        configured_at=datetime.now(UTC),
        imported_at=datetime.now(UTC),
        reachable_at=datetime.now(UTC),
        authenticated_at=datetime.now(UTC),
        callable_at=datetime.now(UTC),
    )
    db_session.add(row)
    await db_session.flush()
    return row


# Sentinel marker to scan response bodies for accidental leak of
# operator_inputs values into responses or audit trails.
SENTINEL_VALUE = "PHASE2-LEAK-CANARY-99887766"


@pytest.mark.asyncio
async def test_allowlisted_callable_skill_returns_planned(
    db_session, callable_github_v2_row, seeded_tenant_user: tuple[UUID, UUID],
):
    """Happy path: callable plugin + allowlisted skill + all required
    inputs supplied -> status=planned with full preview."""
    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-github",
        skill_id="summarize_repo",
        tenant_id=seeded_tenant_user[0],
        user_id=seeded_tenant_user[1],
        operator_inputs={
            "repo_owner": "anthropic",
            "repo_name": SENTINEL_VALUE,
        },
    )
    assert result.accepted is True
    assert result.status == "planned"
    assert result.audit_event_id  # non-empty
    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert tc.tool_name == "get_repository"
    assert tc.read_only is True
    assert tc.backend_surface == "mcp"
    # The argument shape declares each input as "operator-input"
    # (provenance), but NEVER carries the value itself.
    assert tc.argument_shape["repo_name"] == "operator-input"


@pytest.mark.asyncio
async def test_allowlisted_callable_skill_does_not_leak_operator_inputs(
    db_session, callable_github_v2_row, seeded_tenant_user: tuple[UUID, UUID],
):
    """Tightest canary: SENTINEL_VALUE in operator_inputs MUST NOT
    appear anywhere in the result dict (response shape) or in the
    parent audit row's action_params JSON."""
    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-github",
        skill_id="summarize_repo",
        tenant_id=seeded_tenant_user[0],
        user_id=seeded_tenant_user[1],
        operator_inputs={
            "repo_owner": SENTINEL_VALUE,
            "repo_name": SENTINEL_VALUE,
        },
    )
    body_text = json.dumps(result.to_dict())
    assert SENTINEL_VALUE not in body_text, (
        "Operator input value leaked into response body."
    )

    # Audit row check.
    from sqlalchemy import select
    from app.models.governance import GoaAuditEvent
    rows = (
        await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == seeded_tenant_user[0],
                GoaAuditEvent.action_type == "plugin.skill_invocation",
            )
        )
    ).scalars().all()
    assert rows, "No audit row written for accepted skill invocation."
    for row in rows:
        params_text = json.dumps(row.action_params or {})
        assert SENTINEL_VALUE not in params_text, (
            f"Operator input value leaked into audit row {row.id}."
        )


@pytest.mark.asyncio
async def test_non_allowlisted_skill_blocked(
    db_session, seeded_tenant_user: tuple[UUID, UUID],
):
    """A skill not in PHASE2_ALLOWLIST returns status=blocked."""
    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-fake-plugin",
        skill_id="some_unknown_skill",
        tenant_id=seeded_tenant_user[0],
        user_id=seeded_tenant_user[1],
    )
    assert result.accepted is False
    assert result.status == "blocked"
    assert result.blocked_reason == "not_in_phase2_allowlist"
    # Audit row still written so the attempt is captured.
    assert result.audit_event_id


@pytest.mark.asyncio
async def test_write_skill_blocked(
    db_session, seeded_tenant_user: tuple[UUID, UUID],
):
    """Notion update_page is on the explicit-block list. Even though
    the catalog has it, the Phase 2 executor returns blocked."""
    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-notion",
        skill_id="update_page",
        tenant_id=seeded_tenant_user[0],
        user_id=seeded_tenant_user[1],
        operator_inputs={"page_id": "abc"},
    )
    assert result.accepted is False
    assert result.status == "blocked"


@pytest.mark.asyncio
async def test_browser_action_blocked(
    db_session, seeded_tenant_user: tuple[UUID, UUID],
):
    """Playwright open_page is a browser action -- blocked."""
    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-playwright",
        skill_id="open_page",
        tenant_id=seeded_tenant_user[0],
        user_id=seeded_tenant_user[1],
        operator_inputs={"url": "https://example.com"},
    )
    assert result.accepted is False
    assert result.status == "blocked"


@pytest.mark.asyncio
async def test_safe_query_remains_blocked_in_phase2(
    db_session, seeded_tenant_user: tuple[UUID, UUID],
):
    """safe_query (Postgres / SQLite / MongoDB / Supabase / Neon)
    stays plan-only forever per founder rule 16. Phase 2 must not
    accept it for execution."""
    for plugin_id in (
        "mcp-postgres", "mcp-sqlite", "mcp-mongodb",
        "mcp-supabase", "mcp-neon",
    ):
        executor = SkillExecutor(db_session)
        result = await executor.execute(
            plugin_id=plugin_id,
            skill_id="safe_query",
            tenant_id=seeded_tenant_user[0],
            user_id=seeded_tenant_user[1],
        )
        assert result.status == "blocked", (
            f"{plugin_id}:safe_query was not blocked in Phase 2."
        )


@pytest.mark.asyncio
async def test_missing_plugin_connection_returns_needs_connection(
    db_session, seeded_tenant_user: tuple[UUID, UUID],
):
    """Allowlisted skill but the plugin's V2 row is absent (not
    callable). Returns status=needs_connection."""
    # No callable_github_v2_row fixture -> no V2 row at all.
    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-github",
        skill_id="summarize_repo",
        tenant_id=seeded_tenant_user[0],
        user_id=seeded_tenant_user[1],
        operator_inputs={"repo_owner": "x", "repo_name": "y"},
    )
    assert result.accepted is False
    assert result.status == "needs_connection"


@pytest.mark.asyncio
async def test_missing_required_inputs_returns_needs_inputs(
    db_session, callable_github_v2_row, seeded_tenant_user: tuple[UUID, UUID],
):
    """All inputs missing -> status=needs_inputs with the missing
    field NAMES (never values)."""
    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-github",
        skill_id="summarize_repo",
        tenant_id=seeded_tenant_user[0],
        user_id=seeded_tenant_user[1],
        operator_inputs={},
    )
    assert result.status == "needs_inputs"
    assert set(result.required_inputs) == {"repo_owner", "repo_name"}
    assert result.audit_event_id  # still audited


@pytest.mark.asyncio
async def test_partial_inputs_returns_only_missing_fields(
    db_session, callable_github_v2_row, seeded_tenant_user: tuple[UUID, UUID],
):
    """Operator supplies one of two required inputs. Missing list has
    only the missing one."""
    executor = SkillExecutor(db_session)
    result = await executor.execute(
        plugin_id="mcp-github",
        skill_id="summarize_repo",
        tenant_id=seeded_tenant_user[0],
        user_id=seeded_tenant_user[1],
        operator_inputs={"repo_owner": "anthropic"},
    )
    assert result.status == "needs_inputs"
    assert result.required_inputs == ["repo_name"]


@pytest.mark.asyncio
async def test_audit_row_records_outcome_and_no_secret_values(
    db_session, callable_github_v2_row, seeded_tenant_user: tuple[UUID, UUID],
):
    """Audit row carries action_type=plugin.skill_invocation and the
    allowlist_match + read_only + outcome fields. action_params NEVER
    contains operator_inputs values."""
    executor = SkillExecutor(db_session)
    await executor.execute(
        plugin_id="mcp-github",
        skill_id="triage_issues",
        tenant_id=seeded_tenant_user[0],
        user_id=seeded_tenant_user[1],
        operator_inputs={
            "repo_owner": SENTINEL_VALUE,
            "repo_name": SENTINEL_VALUE,
        },
    )

    from sqlalchemy import select
    from app.models.governance import GoaAuditEvent
    row = (
        await db_session.execute(
            select(GoaAuditEvent)
            .where(GoaAuditEvent.tenant_id == seeded_tenant_user[0])
            .where(GoaAuditEvent.action_type == "plugin.skill_invocation")
            .order_by(GoaAuditEvent.id.desc())
        )
    ).scalars().first()
    assert row is not None
    params = row.action_params or {}
    assert params.get("plugin_id") == "mcp-github"
    assert params.get("skill_id") == "triage_issues"
    assert params.get("phase") == "phase2_readonly"
    assert params.get("allowlist_match") is True
    assert params.get("read_only") is True
    assert params.get("outcome") == "planned"
    # Argument shape carries provenance NOT values.
    shape = params.get("argument_shape") or {}
    assert shape.get("repo_owner") == "operator-input"
    assert shape.get("repo_name") == "operator-input"
    # Final canary: dump and verify sentinel absent.
    assert SENTINEL_VALUE not in json.dumps(params)


# ──────────────────────────────────────────────────────────────────
# HTTP API surface
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_jwt_user(
    db_session: AsyncSession, test_tenant_id: UUID, test_user_id: UUID,
):
    """Seed the tenant + user that conftest.auth_headers's JWT references.
    Required because the executor writes an audit row whose actor_id FK
    points at the JWT's user_id -- without a real users row the insert
    fails on FK violation."""
    tenant = Tenant(
        id=test_tenant_id,
        name="JWT Tenant",
        slug=f"jwt-tenant-{test_tenant_id.hex[:6]}",
    )
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        id=test_user_id,
        tenant_id=test_tenant_id,
        email=f"jwt-{test_user_id.hex[:6]}@phase2.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="FOUNDER",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return tenant, user


@pytest.mark.asyncio
async def test_get_allowlist_endpoint_returns_phase2_metadata(
    client, auth_headers,
):
    res = await client.get(
        "/api/v1/connections/v2/skills/allowlist", headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["phase"] == "phase2_readonly"
    assert body["execution_mode_default"] == "planned_only"
    assert isinstance(body["entries"], list)
    assert len(body["entries"]) >= 15
    # Same display-safe shape contract.
    for row in body["entries"]:
        assert "execution_mode" in row
        assert row["read_only"] is True
        # No suspicious fields.
        assert not any(
            k in row for k in
            ("api_key", "secret", "token", "credentials", "client_secret")
        )


@pytest.mark.asyncio
async def test_execute_endpoint_blocks_non_allowlisted(
    client, auth_headers, seeded_jwt_user,
):
    res = await client.post(
        "/api/v1/connections/v2/skills/execute",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-fake",
            "skill_id": "delete_everything",
            "operator_inputs": {},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is False
    assert body["status"] == "blocked"


@pytest.mark.asyncio
async def test_execute_endpoint_requires_auth(client):
    res = await client.post(
        "/api/v1/connections/v2/skills/execute",
        json={
            "plugin_id": "mcp-github",
            "skill_id": "summarize_repo",
            "operator_inputs": {},
        },
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_allowlist_requires_auth(client):
    res = await client.get("/api/v1/connections/v2/skills/allowlist")
    assert res.status_code in (401, 403)
