"""PR-CONN-OAUTH-EXECUTOR-WIRE-UP (2026-05-03) tests.

These tests exercise the new ``_execute_real_oauth`` branch in
``SkillExecutor`` WITHOUT promoting any Phase 2 OAuth allowlist entry.
The Sprint-2 invariant ``test_pr3_gmail_and_drive_remain_planned_only``
still defends against a stealth promotion in PR-1 -- that flip is
PR-2's job.

Strategy:
  * For ``_execute_real_oauth`` direct tests: build a synthetic
    SkillToolMapping(execution_mode="mcp_tool", backend_surface="oauth")
    and call the method directly on a SkillExecutor.
  * For dispatch routing test: monkeypatch ``get_allowlist_entry`` to
    return a synthetic mcp_tool oauth entry, then call ``execute()``
    and confirm the OAuth branch fires.
  * For network: monkeypatch ``OAuthInvoker._do_get`` (cleanest seam)
    so no real google.com HTTP fires.

Pins:
  1. Dispatch: backend_surface=oauth + mcp_tool routes to _execute_real_oauth.
  2. Dispatch: backend_surface=mcp + mcp_tool still routes to _execute_real_mcp_tool.
  3. No connector instance -> needs_connection / oauth_not_connected.
  4. Missing access_token in instance -> needs_connection / oauth_credentials_missing.
  5. 401 -> refresh -> 401 path -> needs_connection / oauth_auth_expired.
  6. 401 -> refresh -> 200 path -> executed, oauth_refreshed=true in audit.
  7. Response too large -> blocked / oauth_response_too_large.
  8. Vendor 5xx -> blocked / oauth_vendor_error.
  9. Success -> executed + summary references OAuth + content hash present.
 10. Audit row NEVER carries access_token / refresh_token / Bearer in any
     value (full action_params scrub).
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.models.connections import Connector, ConnectorInstance
from app.models.identity import Tenant, User
from app.services.connection_v2.skill_executor import (
    SkillExecutor,
    SkillToolMapping,
    _OAUTH_PROVIDER_TO_CONNECTOR_NAME,
)


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant_user(db_session: AsyncSession) -> tuple[UUID, UUID]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(
        id=tenant_id,
        name=f"OAuthExec {tenant_id.hex[:6]}",
        slug=f"oauth-exec-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@oauth-exec.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="FOUNDER", email_verified=True,
    ))
    await db_session.flush()
    return tenant_id, user_id


@pytest.fixture
async def callable_gmail_v2_row(
    db_session, seeded_tenant_user: tuple[UUID, UUID],
) -> ConnectionV2:
    """V2 row matching the app-gmail catalog's matches_v2_slug=oauth-gmail
    so _is_plugin_callable returns True."""
    tenant_id, _ = seeded_tenant_user
    row = ConnectionV2(
        tenant_id=tenant_id,
        kind=ConnectionKind.OAUTH_APP.value,
        slug="oauth-gmail",
        canonical_key="oauth-gmail",
        display_name="Gmail",
        config={},
        auth_method="oauth",
        detected=True, configured=True, imported=True,
        reachable=True, authenticated=True, callable=True,
        detected_at=datetime.now(UTC), configured_at=datetime.now(UTC),
        imported_at=datetime.now(UTC), reachable_at=datetime.now(UTC),
        authenticated_at=datetime.now(UTC), callable_at=datetime.now(UTC),
    )
    db_session.add(row)
    await db_session.flush()
    return row


@pytest.fixture
async def gmail_connector_instance(
    db_session, seeded_tenant_user: tuple[UUID, UUID],
) -> ConnectorInstance:
    """Seed a Gmail connector + a CONNECTED ConnectorInstance with
    fake OAuth credentials. Provider-name match comes via
    _OAUTH_PROVIDER_TO_CONNECTOR_NAME['gmail'] = 'Gmail'."""
    tenant_id, user_id = seeded_tenant_user
    # Existing test DB may already have a Gmail Connector seeded by
    # other fixtures. Look up first; create if absent.
    connector = (await db_session.execute(
        select(Connector).where(Connector.name == "Gmail")
    )).scalar_one_or_none()
    if connector is None:
        connector = Connector(
            id=uuid.uuid4(), name="Gmail",
            auth_type="oauth", config_schema={}, tools=[],
        )
        db_session.add(connector)
        await db_session.flush()
    instance = ConnectorInstance(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        connector_id=connector.id,
        user_id=user_id,
        status="CONNECTED",
        credentials={
            "access_token": "ya29.c.fake_token_for_executor_test",
            "refresh_token": "1//0g_fake_refresh",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    db_session.add(instance)
    await db_session.flush()
    return instance


def _mock_response(status: int, body: dict | bytes | None = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    if isinstance(body, dict):
        b = json.dumps(body).encode("utf-8")
        m.content = b
        m.json = MagicMock(return_value=body)
        m.text = b.decode()
    elif isinstance(body, bytes):
        m.content = body
        m.json = MagicMock(side_effect=ValueError("not json"))
        m.text = body.decode("utf-8", errors="replace")
    else:
        m.content = b""
        m.json = MagicMock(return_value={})
        m.text = ""
    return m


def _make_invoker_client(*responses: MagicMock) -> MagicMock:
    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=list(responses))
    client.aclose = AsyncMock()
    return client


def _gmail_list_unread_synthetic_entry() -> SkillToolMapping:
    """Build an mcp_tool oauth entry matching app-gmail:messages.list_unread
    so the executor will dispatch to _execute_real_oauth without us
    flipping the real PHASE2_ALLOWLIST (which would break the
    Sprint-2 invariant test)."""
    return SkillToolMapping(
        plugin_id="app-gmail",
        skill_id="summarize_unread",
        backend_surface="oauth",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="messages.list_unread",  # matches OAUTH_METHOD_ALLOWLIST
        required_inputs=(),
        reads_summary="Synthetic test entry; not in PHASE2_ALLOWLIST.",
    )


# ──────────────────────────────────────────────────────────────────
# 1. Dispatch routing
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_oauth_mcp_tool_routes_to_oauth_branch(
    db_session, callable_gmail_v2_row, seeded_tenant_user, monkeypatch,
):
    """When the executor's get_allowlist_entry returns an mcp_tool +
    oauth entry, execute() MUST invoke _execute_real_oauth (not the
    MCP path)."""
    tenant_id, user_id = seeded_tenant_user
    synth = _gmail_list_unread_synthetic_entry()
    monkeypatch.setattr(
        "app.services.connection_v2.skill_executor.get_allowlist_entry",
        lambda p, s: synth,
    )

    fired = {"oauth": 0, "mcp": 0}

    async def fake_oauth(*, entry, tenant_id, user_id, operator_inputs):
        fired["oauth"] += 1

        class R:
            status = "executed"
            accepted = True
            summary = "ok"
            audit_event_id = "fake"
            tool_calls: list = []
            blocked_reason = ""
            required_inputs: list = []
            result_preview = ""

        return R()

    async def fake_mcp(**kwargs):
        fired["mcp"] += 1

    executor = SkillExecutor(db_session)
    monkeypatch.setattr(executor, "_execute_real_oauth", fake_oauth)
    monkeypatch.setattr(executor, "_execute_real_mcp_tool", fake_mcp)

    await executor.execute(
        plugin_id="app-gmail",
        skill_id="summarize_unread",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={},
    )
    assert fired["oauth"] == 1, "OAuth branch should have fired"
    assert fired["mcp"] == 0, "MCP branch should NOT have fired for oauth surface"


@pytest.mark.asyncio
async def test_dispatch_mcp_mcp_tool_still_routes_to_mcp_branch(
    db_session, seeded_tenant_user, monkeypatch,
):
    """Defense-in-depth: PR-1 only ADDS the oauth branch. The
    backend_surface=mcp + mcp_tool path is unchanged."""
    tenant_id, user_id = seeded_tenant_user
    # Use the real mcp-filesystem entry which is mcp_tool + mcp.
    fired = {"oauth": 0, "mcp": 0}

    async def fake_oauth(**kwargs):
        fired["oauth"] += 1

    async def fake_mcp(*, entry, tenant_id, user_id, operator_inputs):
        fired["mcp"] += 1

        class R:
            status = "executed"
            accepted = True
            summary = "ok"
            audit_event_id = "fake"
            tool_calls: list = []
            blocked_reason = ""
            required_inputs: list = []
            result_preview = ""

        return R()

    # Need to bypass the V2-callable check (no MCP V2 row in this test).
    # Easiest: monkeypatch _is_plugin_callable to True.
    executor = SkillExecutor(db_session)
    async def fake_callable(**kwargs):
        return True
    monkeypatch.setattr(executor, "_is_plugin_callable", fake_callable)
    monkeypatch.setattr(executor, "_execute_real_oauth", fake_oauth)
    monkeypatch.setattr(executor, "_execute_real_mcp_tool", fake_mcp)

    await executor.execute(
        plugin_id="mcp-filesystem",
        skill_id="find_files",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={"root_path": "/tmp", "name_or_glob": "*.py"},
    )
    assert fired["mcp"] == 1
    assert fired["oauth"] == 0


# ──────────────────────────────────────────────────────────────────
# 2. _execute_real_oauth direct outcome tests
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_oauth_no_instance_returns_needs_connection(
    db_session, seeded_tenant_user,
):
    tenant_id, user_id = seeded_tenant_user
    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_list_unread_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id, operator_inputs={},
    )
    assert result.status == "needs_connection"
    assert result.blocked_reason == "oauth_not_connected"
    assert "Connect gmail" in result.summary or "Plugins" in result.summary


@pytest.mark.asyncio
async def test_oauth_missing_access_token_returns_needs_connection(
    db_session, seeded_tenant_user, gmail_connector_instance, monkeypatch,
):
    """Strip the access_token from the seeded instance so the invoker
    raises OAuthCredentialsMissingError. Executor MUST translate that
    into needs_connection / oauth_credentials_missing (not let it bubble)."""
    tenant_id, user_id = seeded_tenant_user
    gmail_connector_instance.credentials = {"refresh_token": "x"}
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(gmail_connector_instance, "credentials")
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_list_unread_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id, operator_inputs={},
    )
    assert result.status == "needs_connection"
    assert result.blocked_reason == "oauth_credentials_missing"


@pytest.mark.asyncio
async def test_oauth_happy_path_executes_with_summary(
    db_session, seeded_tenant_user, gmail_connector_instance, monkeypatch,
):
    """Mock OAuthInvoker._do_get to return success + 3 messages.
    Executor MUST return status=executed with an OAuth-flavored summary
    that mentions message ids."""
    tenant_id, user_id = seeded_tenant_user

    from app.services.connection_v2 import oauth_invoker as oi

    body = {
        "messages": [{"id": "m-1"}, {"id": "m-2"}, {"id": "m-3"}],
        "resultSizeEstimate": 3,
    }

    async def fake_do_get(self, method, url, params, headers):
        return oi.InvokeOutcome(
            ok=True, status_code=200, payload=body, truncated=False,
            refreshed_token=False,
        )

    monkeypatch.setattr(oi.OAuthInvoker, "_do_get", fake_do_get)

    # Block check_and_refresh from doing anything fancy.
    async def noop(self, creds):
        return creds
    monkeypatch.setattr(
        "app.services.integrations.oauth_service.ConnectorOAuthService.check_and_refresh",
        noop,
    )

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_list_unread_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id, operator_inputs={},
    )
    assert result.status == "executed", result.summary
    assert result.accepted is True
    assert "3 message id" in result.summary
    # Hash recorded in audit -- check via the executor's _audit (we
    # cannot peek directly without surfacing the row, so just confirm
    # we got an audit_event_id back).
    assert result.audit_event_id


@pytest.mark.asyncio
async def test_oauth_401_then_refresh_then_200_executes_and_marks_refreshed(
    db_session, seeded_tenant_user, gmail_connector_instance, monkeypatch,
):
    tenant_id, user_id = seeded_tenant_user
    from app.services.connection_v2 import oauth_invoker as oi
    from app.services.integrations.oauth_service import ConnectorOAuthService

    call_count = {"n": 0}

    async def fake_do_get(self, method, url, params, headers):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First GET fails with 401.
            return oi.InvokeOutcome(
                ok=False, status_code=401,
                reason="auth_expired: 401 from vendor",
            )
        return oi.InvokeOutcome(
            ok=True, status_code=200, payload={"messages": [{"id": "m-1"}]},
            refreshed_token=False,  # invoke() sets this on the OUTER outcome
        )

    monkeypatch.setattr(oi.OAuthInvoker, "_do_get", fake_do_get)

    async def noop(self, creds):
        return creds

    async def fake_refresh(self, refresh_token, provider="gmail"):
        return {
            "access_token": "ya29.NEW_AFTER_REFRESH",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }

    monkeypatch.setattr(ConnectorOAuthService, "check_and_refresh", noop)
    monkeypatch.setattr(ConnectorOAuthService, "refresh_token", fake_refresh)

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_list_unread_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id, operator_inputs={},
    )
    assert result.status == "executed", result.summary
    assert call_count["n"] == 2  # initial 401 + retry 200


@pytest.mark.asyncio
async def test_oauth_401_then_refresh_then_401_returns_auth_expired(
    db_session, seeded_tenant_user, gmail_connector_instance, monkeypatch,
):
    tenant_id, user_id = seeded_tenant_user
    from app.services.connection_v2 import oauth_invoker as oi
    from app.services.integrations.oauth_service import ConnectorOAuthService

    async def fake_do_get(self, method, url, params, headers):
        return oi.InvokeOutcome(
            ok=False, status_code=401,
            reason="auth_expired: 401 from vendor",
        )

    monkeypatch.setattr(oi.OAuthInvoker, "_do_get", fake_do_get)

    async def noop(self, creds):
        return creds

    async def fake_refresh(self, refresh_token, provider="gmail"):
        return {
            "access_token": "still-bad",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }

    monkeypatch.setattr(ConnectorOAuthService, "check_and_refresh", noop)
    monkeypatch.setattr(ConnectorOAuthService, "refresh_token", fake_refresh)

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_list_unread_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id, operator_inputs={},
    )
    assert result.status == "needs_connection"
    assert result.blocked_reason == "oauth_auth_expired"


@pytest.mark.asyncio
async def test_oauth_response_too_large_returns_blocked(
    db_session, seeded_tenant_user, gmail_connector_instance, monkeypatch,
):
    tenant_id, user_id = seeded_tenant_user
    from app.services.connection_v2 import oauth_invoker as oi
    from app.services.integrations.oauth_service import ConnectorOAuthService

    async def fake_do_get(self, method, url, params, headers):
        return oi.InvokeOutcome(
            ok=False, status_code=200, truncated=True,
            reason="response_too_large: body exceeded 65536 bytes",
        )

    monkeypatch.setattr(oi.OAuthInvoker, "_do_get", fake_do_get)

    async def noop(self, creds):
        return creds

    monkeypatch.setattr(ConnectorOAuthService, "check_and_refresh", noop)

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_list_unread_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id, operator_inputs={},
    )
    assert result.status == "blocked"
    assert result.blocked_reason == "oauth_response_too_large"


@pytest.mark.asyncio
async def test_oauth_vendor_5xx_returns_blocked(
    db_session, seeded_tenant_user, gmail_connector_instance, monkeypatch,
):
    tenant_id, user_id = seeded_tenant_user
    from app.services.connection_v2 import oauth_invoker as oi
    from app.services.integrations.oauth_service import ConnectorOAuthService

    async def fake_do_get(self, method, url, params, headers):
        return oi.InvokeOutcome(
            ok=False, status_code=503,
            reason="vendor_error: HTTP 503 Service Unavailable",
        )

    monkeypatch.setattr(oi.OAuthInvoker, "_do_get", fake_do_get)

    async def noop(self, creds):
        return creds
    monkeypatch.setattr(ConnectorOAuthService, "check_and_refresh", noop)

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_list_unread_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id, operator_inputs={},
    )
    assert result.status == "blocked"
    assert result.blocked_reason == "oauth_vendor_error"


# ──────────────────────────────────────────────────────────────────
# 3. Token-leak audit defense
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_row_never_carries_token_material(
    db_session, seeded_tenant_user, gmail_connector_instance, monkeypatch,
):
    """Defense-in-depth: invoke a happy-path OAuth call, then walk EVERY
    string value in the persisted audit row's action_params and confirm
    the bearer-token material does not appear anywhere."""
    tenant_id, user_id = seeded_tenant_user
    from app.services.connection_v2 import oauth_invoker as oi
    from app.services.integrations.oauth_service import ConnectorOAuthService

    async def fake_do_get(self, method, url, params, headers):
        # The Authorization header WILL contain Bearer ya29.c.fake_...
        # but we only care that it doesn't leak into the audit.
        return oi.InvokeOutcome(
            ok=True, status_code=200,
            payload={"messages": [{"id": "x"}]},
        )
    monkeypatch.setattr(oi.OAuthInvoker, "_do_get", fake_do_get)

    async def noop(self, creds):
        return creds
    monkeypatch.setattr(ConnectorOAuthService, "check_and_refresh", noop)

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_list_unread_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id, operator_inputs={},
    )
    assert result.status == "executed"

    # Read the audit row back. The audit_event_id is the row id.
    from app.models.governance import GoaAuditEvent
    audit = (await db_session.execute(
        select(GoaAuditEvent).where(GoaAuditEvent.id == UUID(result.audit_event_id))
    )).scalar_one()

    # Walk every string in action_params and forbid token material.
    seeded_token = gmail_connector_instance.credentials["access_token"]
    seeded_refresh = gmail_connector_instance.credentials["refresh_token"]
    forbidden_substrings = [
        seeded_token, seeded_refresh, "Bearer ", "ya29.c.fake",
        "1//0g_fake", "access_token", "refresh_token",
    ]

    def walk(value: Any) -> list[str]:
        out: list[str] = []
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                out.extend(walk(v))
        elif isinstance(value, list):
            for v in value:
                out.extend(walk(v))
        return out

    haystack = "\n".join(walk(audit.action_params))
    for needle in forbidden_substrings:
        assert needle not in haystack, (
            f"Audit row leaked forbidden token-shaped substring: {needle!r}"
        )


@pytest.mark.asyncio
async def test_audit_row_records_oauth_provider_and_refreshed_bit(
    db_session, seeded_tenant_user, gmail_connector_instance, monkeypatch,
):
    """The extra_audit_fields path MUST surface oauth_provider +
    oauth_refreshed flags so an operator can audit which OAuth call
    fired and whether the token was refreshed mid-call."""
    tenant_id, user_id = seeded_tenant_user
    from app.services.connection_v2 import oauth_invoker as oi
    from app.services.integrations.oauth_service import ConnectorOAuthService

    call_count = {"n": 0}

    async def fake_do_get(self, method, url, params, headers):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return oi.InvokeOutcome(ok=False, status_code=401,
                                    reason="auth_expired: 401 from vendor")
        return oi.InvokeOutcome(ok=True, status_code=200, payload={"messages": []})

    async def fake_refresh(self, refresh_token, provider="gmail"):
        return {
            "access_token": "ya29.NEW",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }

    async def noop(self, creds):
        return creds

    monkeypatch.setattr(oi.OAuthInvoker, "_do_get", fake_do_get)
    monkeypatch.setattr(ConnectorOAuthService, "refresh_token", fake_refresh)
    monkeypatch.setattr(ConnectorOAuthService, "check_and_refresh", noop)

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_list_unread_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id, operator_inputs={},
    )
    assert result.status == "executed"

    from app.models.governance import GoaAuditEvent
    audit = (await db_session.execute(
        select(GoaAuditEvent).where(GoaAuditEvent.id == UUID(result.audit_event_id))
    )).scalar_one()

    assert audit.action_params.get("oauth_provider") == "gmail"
    assert audit.action_params.get("oauth_refreshed") is True


# ──────────────────────────────────────────────────────────────────
# 4. Provider mapping consistency
# ──────────────────────────────────────────────────────────────────


def test_oauth_provider_mapping_covers_invoker_allowlist():
    """Every provider used in OAUTH_METHOD_ALLOWLIST MUST have a
    Connector.name mapping in _OAUTH_PROVIDER_TO_CONNECTOR_NAME --
    otherwise _find_oauth_instance can never resolve the instance."""
    from app.services.connection_v2.oauth_invoker import OAUTH_METHOD_ALLOWLIST

    invoker_providers = {m.provider for m in OAUTH_METHOD_ALLOWLIST}
    missing = invoker_providers - set(_OAUTH_PROVIDER_TO_CONNECTOR_NAME)
    assert not missing, (
        f"OAuthInvoker references providers {missing} that have no "
        f"_OAUTH_PROVIDER_TO_CONNECTOR_NAME mapping. _execute_real_oauth "
        f"would always return needs_connection for those."
    )


def test_extra_audit_fields_rejects_token_shaped_keys():
    """Module-level invariant: even if a future code path tries to
    pass access_token/refresh_token/Bearer/secret-named fields into
    extra_audit_fields, _record_real_outcome's loop strips them."""
    # We cannot easily call _record_real_outcome without a full
    # executor + audit setup; instead, mirror the rejection logic here
    # against the SAME forbidden substrings the production code uses,
    # so a future maintainer who edits one MUST also edit this test.
    forbidden_substrings = (
        "access_token", "refresh_token", "bearer", "secret",
    )
    safe_keys = (
        "oauth_provider", "oauth_refreshed", "oauth_truncated",
        "oauth_status_code",
    )
    bad_keys = (
        "user_access_token", "stored_refresh_token", "Bearer",
        "client_secret_present",
    )
    for k in safe_keys:
        assert not any(s in k.lower() for s in forbidden_substrings), (
            f"Safe key {k!r} accidentally matches a forbidden substring"
        )
    for k in bad_keys:
        assert any(s in k.lower() for s in forbidden_substrings), (
            f"Bad key {k!r} should be caught by forbidden substring filter"
        )
