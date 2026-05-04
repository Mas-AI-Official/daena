"""PR-CONN-GOOGLE-ACCOUNT-PROFILES (Sprint-4 PR-3, 2026-05-03) tests.

Pins the founder's "no mixing identities" rule:

  * Single CONNECTED instance per (tenant, user, provider) -> dispatches
    silently as before (back-compat).
  * 2+ CONNECTED instances + NO _owner_email hint -> blocks with
    needs_connection / oauth_account_profile_required.
  * 2+ CONNECTED instances + matching _owner_email hint -> dispatches
    against that instance.
  * 2+ CONNECTED instances + non-matching _owner_email hint -> blocks
    with needs_connection / oauth_account_profile_no_match.
  * Hint with mixed case / surrounding whitespace is normalized.

ZERO real google.com network -- mocks via OAuthInvoker._do_get seam.
"""

from __future__ import annotations

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
        name=f"Profile {tenant_id.hex[:6]}",
        slug=f"profile-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@profile.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="FOUNDER", email_verified=True,
    ))
    await db_session.flush()
    return tenant_id, user_id


async def _ensure_gmail_connector(db_session) -> Connector:
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
    return connector


def _make_instance(
    *, tenant_id: UUID, user_id: UUID, connector_id: UUID,
    owner_email: str | None, status: str = "CONNECTED",
    use_jsonb_fallback: bool = False,
) -> ConnectorInstance:
    """Build a ConnectorInstance for tests. By default, owner_email
    populates the dedicated column (the PR-3 schema change). Pass
    use_jsonb_fallback=True to populate credentials._owner_email
    instead, exercising the back-compat path for instances created
    before the column existed."""
    creds: dict[str, Any] = {
        "access_token": f"ya29.fake.{uuid.uuid4().hex[:8]}",
        "refresh_token": f"1//0g.fake.{uuid.uuid4().hex[:8]}",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    column_value = None
    if owner_email is not None:
        if use_jsonb_fallback:
            creds["_owner_email"] = owner_email
        else:
            column_value = owner_email
    return ConnectorInstance(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        connector_id=connector_id,
        user_id=user_id,
        status=status,
        credentials=creds,
        owner_email=column_value,
    )


@pytest.fixture
async def callable_gmail_v2_row(
    db_session, seeded_tenant_user: tuple[UUID, UUID],
) -> ConnectionV2:
    """V2 row matching app-gmail catalog matches_v2_slug=oauth-gmail."""
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


def _gmail_synthetic_entry() -> SkillToolMapping:
    """Synthetic mcp_tool oauth entry that matches OAUTH_METHOD_ALLOWLIST.
    Used so we can call _execute_real_oauth directly."""
    return SkillToolMapping(
        plugin_id="app-gmail",
        skill_id="summarize_unread",
        backend_surface="oauth",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="messages.list_unread",
        required_inputs=(),
        reads_summary="Synthetic test entry.",
    )


# ──────────────────────────────────────────────────────────────────
# 1. _find_oauth_instance contract
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_zero_instances_returns_none(
    db_session, seeded_tenant_user,
):
    tenant_id, user_id = seeded_tenant_user
    executor = SkillExecutor(db_session)
    inst, code = await executor._find_oauth_instance(
        tenant_id=tenant_id, user_id=user_id, provider="gmail",
    )
    assert inst is None
    assert code is None


@pytest.mark.asyncio
async def test_find_single_instance_returns_it_no_hint(
    db_session, seeded_tenant_user,
):
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    inst = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="masoud.masoori@mas-ai.co",
    )
    db_session.add(inst)
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result, code = await executor._find_oauth_instance(
        tenant_id=tenant_id, user_id=user_id, provider="gmail",
    )
    assert result is not None
    assert result.id == inst.id
    assert code is None


@pytest.mark.asyncio
async def test_find_multi_instance_no_hint_returns_ambiguous(
    db_session, seeded_tenant_user,
):
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    inst_a = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="masoud.masoori@mas-ai.co",
    )
    inst_b = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="daena@mas-ai.co",
    )
    db_session.add_all([inst_a, inst_b])
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result, code = await executor._find_oauth_instance(
        tenant_id=tenant_id, user_id=user_id, provider="gmail",
    )
    assert result is None
    assert code == "ambiguous_account_profile"


@pytest.mark.asyncio
async def test_find_multi_instance_with_matching_hint_dispatches(
    db_session, seeded_tenant_user,
):
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    inst_a = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="masoud.masoori@mas-ai.co",
    )
    inst_b = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="daena@mas-ai.co",
    )
    db_session.add_all([inst_a, inst_b])
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result, code = await executor._find_oauth_instance(
        tenant_id=tenant_id, user_id=user_id, provider="gmail",
        owner_email_hint="daena@mas-ai.co",
    )
    assert result is not None
    assert result.id == inst_b.id
    assert code is None


@pytest.mark.asyncio
async def test_find_multi_instance_hint_normalizes_case_and_whitespace(
    db_session, seeded_tenant_user,
):
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    inst_a = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="masoud.masoori@mas-ai.co",
    )
    inst_b = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="DAENA@mas-ai.co",  # stored uppercase
    )
    db_session.add_all([inst_a, inst_b])
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result, code = await executor._find_oauth_instance(
        tenant_id=tenant_id, user_id=user_id, provider="gmail",
        owner_email_hint="  daena@MAS-AI.co  ",  # padded + mixed case
    )
    assert result is not None
    assert result.id == inst_b.id


@pytest.mark.asyncio
async def test_find_multi_instance_with_unmatched_hint_returns_no_match(
    db_session, seeded_tenant_user,
):
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    inst_a = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="masoud.masoori@mas-ai.co",
    )
    inst_b = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="daena@mas-ai.co",
    )
    db_session.add_all([inst_a, inst_b])
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result, code = await executor._find_oauth_instance(
        tenant_id=tenant_id, user_id=user_id, provider="gmail",
        owner_email_hint="someone-else@example.com",
    )
    assert result is None
    assert code == "owner_email_no_match"


@pytest.mark.asyncio
async def test_find_uses_jsonb_fallback_for_legacy_instances(
    db_session, seeded_tenant_user,
):
    """Instances created BEFORE the owner_email column existed carry
    the email in credentials._owner_email. Executor must read both
    column AND fallback so legacy rows still route correctly."""
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    inst_legacy = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="masoud.masoori@mas-ai.co",
        use_jsonb_fallback=True,  # email in credentials, NOT column
    )
    inst_new = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="daena@mas-ai.co",
        # Default: column populated.
    )
    db_session.add_all([inst_legacy, inst_new])
    await db_session.flush()

    executor = SkillExecutor(db_session)
    # Hint matches the legacy (JSONB-fallback) row.
    result, code = await executor._find_oauth_instance(
        tenant_id=tenant_id, user_id=user_id, provider="gmail",
        owner_email_hint="masoud.masoori@mas-ai.co",
    )
    assert result is not None
    assert result.id == inst_legacy.id
    assert code is None


@pytest.mark.asyncio
async def test_find_disconnected_instance_does_not_count(
    db_session, seeded_tenant_user,
):
    """A DISCONNECTED instance should NOT contribute to ambiguity."""
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    inst_connected = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="masoud.masoori@mas-ai.co",
    )
    inst_disconnected = _make_instance(
        tenant_id=tenant_id, user_id=user_id, connector_id=connector.id,
        owner_email="daena@mas-ai.co",
        status="DISCONNECTED",
    )
    db_session.add_all([inst_connected, inst_disconnected])
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result, code = await executor._find_oauth_instance(
        tenant_id=tenant_id, user_id=user_id, provider="gmail",
    )
    # Only the CONNECTED one counts -> single instance -> use it.
    assert result is not None
    assert result.id == inst_connected.id


# ──────────────────────────────────────────────────────────────────
# 2. _execute_real_oauth surfacing of ambiguity
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_executor_surfaces_account_profile_required(
    db_session, callable_gmail_v2_row, seeded_tenant_user, monkeypatch,
):
    """Two connected Gmail accounts + no operator hint -> the executor
    returns needs_connection / oauth_account_profile_required AND the
    audit row carries oauth_account_ambiguity."""
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    db_session.add_all([
        _make_instance(
            tenant_id=tenant_id, user_id=user_id,
            connector_id=connector.id,
            owner_email="masoud.masoori@mas-ai.co",
        ),
        _make_instance(
            tenant_id=tenant_id, user_id=user_id,
            connector_id=connector.id,
            owner_email="daena@mas-ai.co",
        ),
    ])
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_synthetic_entry(),
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={},  # no _owner_email hint
    )
    assert result.status == "needs_connection"
    assert result.blocked_reason == "oauth_account_profile_required"
    assert "Multiple gmail accounts" in result.summary

    # Audit row carries the ambiguity reason.
    from app.models.governance import GoaAuditEvent
    audit = (await db_session.execute(
        select(GoaAuditEvent).where(GoaAuditEvent.id == UUID(result.audit_event_id))
    )).scalar_one()
    assert audit.action_params.get("oauth_account_ambiguity") == \
        "multiple_connected_no_hint"
    assert audit.action_params.get("oauth_provider") == "gmail"


@pytest.mark.asyncio
async def test_executor_dispatches_with_owner_email_hint(
    db_session, callable_gmail_v2_row, seeded_tenant_user, monkeypatch,
):
    """Two connected Gmail accounts + matching hint -> executor picks
    the right one and dispatches to the OAuth invoker against ITS
    credentials."""
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    inst_personal = _make_instance(
        tenant_id=tenant_id, user_id=user_id,
        connector_id=connector.id,
        owner_email="masoud.masoori@mas-ai.co",
    )
    inst_company = _make_instance(
        tenant_id=tenant_id, user_id=user_id,
        connector_id=connector.id,
        owner_email="daena@mas-ai.co",
    )
    db_session.add_all([inst_personal, inst_company])
    await db_session.flush()

    captured: dict[str, str] = {}

    from app.services.connection_v2 import oauth_invoker as oi
    from app.services.integrations.oauth_service import ConnectorOAuthService

    async def fake_do_get(self, method, url, params, headers):
        captured["auth_header"] = headers.get("Authorization", "")
        return oi.InvokeOutcome(
            ok=True, status_code=200, payload={"messages": [{"id": "x"}]},
        )

    async def noop(self, creds):
        return creds

    monkeypatch.setattr(oi.OAuthInvoker, "_do_get", fake_do_get)
    monkeypatch.setattr(ConnectorOAuthService, "check_and_refresh", noop)

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id,
        operator_inputs={"_owner_email": "daena@mas-ai.co"},
    )
    assert result.status == "executed", result.summary

    # The captured Authorization header MUST contain the COMPANY
    # account's access token, not the personal one.
    company_token = inst_company.credentials["access_token"]
    personal_token = inst_personal.credentials["access_token"]
    assert company_token in captured["auth_header"]
    assert personal_token not in captured["auth_header"]


@pytest.mark.asyncio
async def test_executor_surfaces_owner_email_no_match(
    db_session, callable_gmail_v2_row, seeded_tenant_user,
):
    """Two connected accounts + non-matching hint ->
    needs_connection / oauth_account_profile_no_match."""
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    db_session.add_all([
        _make_instance(
            tenant_id=tenant_id, user_id=user_id,
            connector_id=connector.id,
            owner_email="masoud.masoori@mas-ai.co",
        ),
        _make_instance(
            tenant_id=tenant_id, user_id=user_id,
            connector_id=connector.id,
            owner_email="daena@mas-ai.co",
        ),
    ])
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id,
        operator_inputs={"_owner_email": "ghost@nowhere.com"},
    )
    assert result.status == "needs_connection"
    assert result.blocked_reason == "oauth_account_profile_no_match"


# ──────────────────────────────────────────────────────────────────
# 3. Audit-row safety: account-profile fields don't leak tokens
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_account_profile_audit_fields_carry_no_token(
    db_session, callable_gmail_v2_row, seeded_tenant_user,
):
    """The new oauth_account_ambiguity audit field is leak-safe."""
    tenant_id, user_id = seeded_tenant_user
    connector = await _ensure_gmail_connector(db_session)
    db_session.add_all([
        _make_instance(
            tenant_id=tenant_id, user_id=user_id,
            connector_id=connector.id,
            owner_email="masoud.masoori@mas-ai.co",
        ),
        _make_instance(
            tenant_id=tenant_id, user_id=user_id,
            connector_id=connector.id,
            owner_email="daena@mas-ai.co",
        ),
    ])
    await db_session.flush()

    executor = SkillExecutor(db_session)
    result = await executor._execute_real_oauth(
        entry=_gmail_synthetic_entry(),
        tenant_id=tenant_id, user_id=user_id,
        operator_inputs={},
    )

    from app.models.governance import GoaAuditEvent
    audit = (await db_session.execute(
        select(GoaAuditEvent).where(GoaAuditEvent.id == UUID(result.audit_event_id))
    )).scalar_one()

    # Walk every string in action_params; none should contain access
    # token material.
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
    forbidden = ["ya29.fake.", "1//0g.fake.", "Bearer ", "access_token", "refresh_token"]
    for needle in forbidden:
        assert needle not in haystack, (
            f"Audit row leaked forbidden substring: {needle!r}"
        )

    # owner_email IS NOT secret-adjacent (it's a routing identifier),
    # so it MAY appear in the operator-facing summary or audit. The
    # forbidden list above is for token material only.
