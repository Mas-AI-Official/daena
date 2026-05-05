"""PR-1 (Sprint-11): IntegrationRouter phase-2 read-only gate + owner_email pin.

Covers:
    1. Phase-2 flag blocks every write tool wholesale, regardless of
       per-tool ConnectorPermission state.
    2. Phase-2 gate fires *before* the connection lookup, so a missing
       account doesn't mask the write-block.
    3. Audit row is written on the block (action_type=
       integration.tool_invocation, outcome=blocked, blocked_reason=
       write_disabled_phase2).
    4. owner_email mismatch -> NotConnectedError, no client invoked.
    5. owner_email match -> dispatched.
    6. WRITE_TOOLS stays in lockstep with the client TOOLS dicts (no
       drift: every write tool listed is real, no read tool is
       accidentally listed as write).
    7. Read tool with phase-2 ON still works.
    8. The HTTP API surface (/integrations/execute) accepts an
       owner_email field.

Tests use the conftest db_session + test_tenant_id + test_user_id, and
patch the GmailClient instance method execute_tool to skip the network.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.constants import ConnectorStatus, PermissionLevel
from app.models.connections import Connector, ConnectorInstance, ConnectorPermission
from app.models.identity import Tenant, User
from app.services.audit import AuditService
from app.services.integrations.gmail_client import GmailClient
from app.services.integrations.calendar_client import CalendarClient
from app.services.integrations.notion_client import NotionClient
from app.services.integrations.integration_router import (
    ALL_TOOLS,
    IntegrationRouter,
    NotConnectedError,
    PermissionDeniedError,
    PROVIDER_REGISTRY,
    WRITE_TOOLS,
    _is_write_tool,
)


FOUNDER_EMAIL = "masoud.masoori@mas-ai.co"
AGENT_EMAIL = "daena@mas-ai.co"


# ── Static / structural assertions ────────────────────────────────────


class TestWriteToolsRegistry:
    """The WRITE_TOOLS map must stay in sync with each client's TOOLS dict."""

    def test_every_write_tool_exists_in_client_tools(self):
        """No phantom write tools listed in WRITE_TOOLS."""
        for provider, write_set in WRITE_TOOLS.items():
            client = PROVIDER_REGISTRY[provider]
            for tool_name in write_set:
                assert tool_name in client.TOOLS, (
                    f"WRITE_TOOLS lists {provider}.{tool_name} but "
                    f"{client.__name__}.TOOLS does not -- fix the registry."
                )

    def test_known_write_tools_listed(self):
        """Sanity: the writes we know about are gated."""
        assert "send_email" in WRITE_TOOLS["gmail"]
        assert "create_draft" in WRITE_TOOLS["gmail"]
        assert "create_event" in WRITE_TOOLS["google-calendar"]
        assert "update_event" in WRITE_TOOLS["google-calendar"]
        assert "create_page" in WRITE_TOOLS["notion"]

    def test_known_read_tools_not_in_write_set(self):
        """Sanity: reads must not be flagged as writes."""
        assert "search_emails" not in WRITE_TOOLS["gmail"]
        assert "read_email" not in WRITE_TOOLS["gmail"]
        assert "list_events" not in WRITE_TOOLS["google-calendar"]
        assert "find_free_time" not in WRITE_TOOLS["google-calendar"]
        assert "search_pages" not in WRITE_TOOLS["notion"]
        assert "read_page" not in WRITE_TOOLS["notion"]

    def test_calendar_alias_mirrors_google_calendar(self):
        """The 'calendar' alias must protect the same set as 'google-calendar'."""
        assert WRITE_TOOLS["calendar"] == WRITE_TOOLS["google-calendar"]

    def test_is_write_tool_helper(self):
        assert _is_write_tool("gmail", "send_email") is True
        assert _is_write_tool("gmail", "search_emails") is False
        assert _is_write_tool("notion", "create_page") is True
        assert _is_write_tool("notion", "search_pages") is False
        # Unknown provider returns False (defense in depth)
        assert _is_write_tool("unknown", "anything") is False


# ── DB-backed gate behavior ──────────────────────────────────────────


async def _get_or_create(db_session, model, *, defaults: dict | None = None, **lookup):
    """Idempotent helper -- the router commits inside the audit path,
    so the session-rollback fixture cannot fully isolate tests in this
    file. We look up by the lookup keys and create only when absent."""
    stmt = select(model)
    for k, v in lookup.items():
        stmt = stmt.where(getattr(model, k) == v)
    existing = (await db_session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    payload = {**lookup, **(defaults or {})}
    obj = model(**payload)
    db_session.add(obj)
    await db_session.flush()
    return obj


@pytest.fixture
async def gmail_setup(db_session, test_tenant_id, test_user_id):
    """Seed tenant + user + Gmail connector + two CONNECTED instances
    (founder + agent) so owner_email pinning can be exercised."""
    await _get_or_create(
        db_session, Tenant, id=test_tenant_id,
        defaults={"name": "Test Tenant", "slug": "test-tenant"},
    )
    await _get_or_create(
        db_session, User, id=test_user_id,
        defaults={
            "tenant_id": test_tenant_id,
            "email": "masoud@example.com",
            "password_hash": "x",
            "role": "FOUNDER",
            "is_active": True,
        },
    )
    connector = await _get_or_create(
        db_session, Connector, name="Gmail",
        defaults={
            "id": uuid.uuid4(),
            "auth_type": "oauth2",
            "config_schema": {},
            "tools": [],
        },
    )
    # Reset any leftover instances from previous tests in this file.
    existing = (await db_session.execute(
        select(ConnectorInstance)
        .where(ConnectorInstance.connector_id == connector.id)
        .where(ConnectorInstance.user_id == test_user_id)
    )).scalars().all()
    for inst in existing:
        await db_session.delete(inst)
    await db_session.flush()

    founder_instance = ConnectorInstance(
        id=uuid.uuid4(),
        tenant_id=test_tenant_id,
        connector_id=connector.id,
        user_id=test_user_id,
        status=ConnectorStatus.CONNECTED.value,
        credentials={"access_token": "founder-token"},
        owner_email=FOUNDER_EMAIL,
    )
    agent_instance = ConnectorInstance(
        id=uuid.uuid4(),
        tenant_id=test_tenant_id,
        connector_id=connector.id,
        user_id=test_user_id,
        status=ConnectorStatus.CONNECTED.value,
        credentials={"access_token": "agent-token"},
        owner_email=AGENT_EMAIL,
    )
    db_session.add_all([founder_instance, agent_instance])

    # ALWAYS_ALLOW the read tool so per-tool perm is not the gate under test.
    for inst in (founder_instance, agent_instance):
        db_session.add(ConnectorPermission(
            id=uuid.uuid4(),
            tenant_id=test_tenant_id,
            instance_id=inst.id,
            tool_name="search_emails",
            permission_level=PermissionLevel.ALWAYS_ALLOW.value,
        ))
        db_session.add(ConnectorPermission(
            id=uuid.uuid4(),
            tenant_id=test_tenant_id,
            instance_id=inst.id,
            tool_name="send_email",
            permission_level=PermissionLevel.ALWAYS_ALLOW.value,
        ))
    await db_session.flush()
    return {
        "tenant_id": test_tenant_id,
        "user_id": test_user_id,
        "connector": connector,
        "founder": founder_instance,
        "agent": agent_instance,
    }


class TestPhase2ReadOnlyGate:
    """Write tools are blocked while INTEGRATIONS_PHASE2_READONLY is on."""

    @pytest.mark.asyncio
    async def test_send_email_blocked_with_write_disabled_phase2(
        self, db_session, gmail_setup,
    ):
        # The flag defaults ON; assert that explicitly so the test is
        # decoupled from any future default change.
        settings = get_settings()
        assert settings.integrations_phase2_readonly is True

        router = IntegrationRouter(db_session)
        with pytest.raises(PermissionDeniedError) as exc_info:
            await router.execute(
                provider="gmail",
                tool_name="send_email",
                params={"to": "x@example.com", "subject": "x", "body": "x"},
                user_id=gmail_setup["user_id"],
                tenant_id=gmail_setup["tenant_id"],
                owner_email=FOUNDER_EMAIL,
            )
        assert "write_disabled_phase2" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_block_audit_row_recorded(
        self, db_session, gmail_setup,
    ):
        router = IntegrationRouter(db_session)
        with pytest.raises(PermissionDeniedError):
            await router.execute(
                provider="gmail",
                tool_name="send_email",
                params={},
                user_id=gmail_setup["user_id"],
                tenant_id=gmail_setup["tenant_id"],
                owner_email=FOUNDER_EMAIL,
            )

        audit = AuditService(db_session)
        trail = await audit.get_audit_trail(
            tenant_id=gmail_setup["tenant_id"],
            page_size=10,
        )
        events = trail["data"]
        relevant = [
            e for e in events
            if e["action_type"] == "integration.tool_invocation"
        ]
        assert len(relevant) >= 1
        params = relevant[0]["action_params"]
        assert params["provider"] == "gmail"
        assert params["tool_name"] == "send_email"
        assert params["outcome"] == "blocked"
        assert params["blocked_reason"] == "write_disabled_phase2"
        assert params["read_only"] is True
        assert params["is_write_tool"] is True

    @pytest.mark.asyncio
    async def test_create_event_blocked(self, db_session, gmail_setup):
        # Add a Calendar connector + connected instance with the same owner.
        cal_connector = await _get_or_create(
            db_session, Connector, name="Google Calendar",
            defaults={
                "id": uuid.uuid4(),
                "auth_type": "oauth2",
                "config_schema": {},
                "tools": [],
            },
        )
        # Idempotent: only create instance if absent
        existing = (await db_session.execute(
            select(ConnectorInstance)
            .where(ConnectorInstance.connector_id == cal_connector.id)
            .where(ConnectorInstance.user_id == gmail_setup["user_id"])
            .where(ConnectorInstance.owner_email == FOUNDER_EMAIL)
        )).scalar_one_or_none()
        if existing is None:
            cal_instance = ConnectorInstance(
                id=uuid.uuid4(),
                tenant_id=gmail_setup["tenant_id"],
                connector_id=cal_connector.id,
                user_id=gmail_setup["user_id"],
                status=ConnectorStatus.CONNECTED.value,
                credentials={"access_token": "cal-token"},
                owner_email=FOUNDER_EMAIL,
            )
            db_session.add(cal_instance)
            await db_session.flush()

        router = IntegrationRouter(db_session)
        with pytest.raises(PermissionDeniedError) as exc_info:
            await router.execute(
                provider="google-calendar",
                tool_name="create_event",
                params={"summary": "x", "start": "x", "end": "x"},
                user_id=gmail_setup["user_id"],
                tenant_id=gmail_setup["tenant_id"],
                owner_email=FOUNDER_EMAIL,
            )
        assert "write_disabled_phase2" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_page_blocked(self, db_session, gmail_setup):
        notion_connector = await _get_or_create(
            db_session, Connector, name="Notion",
            defaults={
                "id": uuid.uuid4(),
                "auth_type": "oauth2",
                "config_schema": {},
                "tools": [],
            },
        )
        existing = (await db_session.execute(
            select(ConnectorInstance)
            .where(ConnectorInstance.connector_id == notion_connector.id)
            .where(ConnectorInstance.user_id == gmail_setup["user_id"])
        )).scalar_one_or_none()
        if existing is None:
            notion_instance = ConnectorInstance(
                id=uuid.uuid4(),
                tenant_id=gmail_setup["tenant_id"],
                connector_id=notion_connector.id,
                user_id=gmail_setup["user_id"],
                status=ConnectorStatus.CONNECTED.value,
                credentials={"token": "notion-token"},
                owner_email=None,
            )
            db_session.add(notion_instance)
            await db_session.flush()

        router = IntegrationRouter(db_session)
        with pytest.raises(PermissionDeniedError) as exc_info:
            await router.execute(
                provider="notion",
                tool_name="create_page",
                params={"parent_id": "x", "title": "x"},
                user_id=gmail_setup["user_id"],
                tenant_id=gmail_setup["tenant_id"],
            )
        assert "write_disabled_phase2" in str(exc_info.value)


class TestOwnerEmailPin:
    """owner_email selects which connected instance dispatches the call."""

    @pytest.mark.asyncio
    async def test_owner_email_mismatch_raises_not_connected(
        self, db_session, gmail_setup,
    ):
        router = IntegrationRouter(db_session)
        with pytest.raises(NotConnectedError) as exc_info:
            await router.execute(
                provider="gmail",
                tool_name="search_emails",
                params={"query": "is:unread"},
                user_id=gmail_setup["user_id"],
                tenant_id=gmail_setup["tenant_id"],
                owner_email="someone-else@example.com",
            )
        assert "owner_email" in str(exc_info.value).lower() or "not connected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_no_owner_email_with_multiple_instances_raises(
        self, db_session, gmail_setup,
    ):
        """Two connected accounts + no pin -> ambiguous -> NotConnectedError."""
        router = IntegrationRouter(db_session)
        with pytest.raises(NotConnectedError) as exc_info:
            await router.execute(
                provider="gmail",
                tool_name="search_emails",
                params={"query": "x"},
                user_id=gmail_setup["user_id"],
                tenant_id=gmail_setup["tenant_id"],
                owner_email=None,
            )
        assert "owner_email_required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_owner_email_match_dispatches(self, db_session, gmail_setup):
        """Matching owner -> client.execute_tool called with the right credentials."""
        router = IntegrationRouter(db_session)

        with patch.object(
            GmailClient, "execute_tool",
            new=AsyncMock(return_value={"messages": [], "total": 0}),
        ) as mock_exec:
            result = await router.execute(
                provider="gmail",
                tool_name="search_emails",
                params={"query": "is:unread"},
                user_id=gmail_setup["user_id"],
                tenant_id=gmail_setup["tenant_id"],
                owner_email=FOUNDER_EMAIL,
            )

        assert result == {"messages": [], "total": 0}
        mock_exec.assert_awaited_once_with("search_emails", {"query": "is:unread"})


class TestReadToolStillWorks:
    """A read tool with the gate ON proceeds normally."""

    @pytest.mark.asyncio
    async def test_search_emails_succeeds_under_phase2(
        self, db_session, gmail_setup,
    ):
        router = IntegrationRouter(db_session)
        with patch.object(
            GmailClient, "execute_tool",
            new=AsyncMock(return_value={"messages": [{"id": "m1"}], "total": 1}),
        ):
            result = await router.execute(
                provider="gmail",
                tool_name="search_emails",
                params={"query": "in:inbox"},
                user_id=gmail_setup["user_id"],
                tenant_id=gmail_setup["tenant_id"],
                owner_email=AGENT_EMAIL,
            )
        assert result["total"] == 1


class TestApiSurface:
    """The HTTP layer exposes owner_email on the request body."""

    @pytest.mark.asyncio
    async def test_integrations_execute_accepts_owner_email(
        self, client, auth_headers,
    ):
        # The endpoint accepts the field even when the user has no
        # connections; the call returns an error_type, not 422.
        resp = await client.post(
            "/api/v1/integrations/execute",
            headers=auth_headers,
            json={
                "provider": "gmail",
                "tool_name": "send_email",
                "params": {},
                "owner_email": FOUNDER_EMAIL,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # write_disabled_phase2 fires before the connection lookup, so the
        # response is permission_denied, not not_connected.
        assert body["success"] is False
        assert body["error_type"] == "permission_denied"
        assert "write_disabled_phase2" in body["error"]

    @pytest.mark.asyncio
    async def test_integrations_qualified_accepts_owner_email(
        self, client, auth_headers,
    ):
        resp = await client.post(
            "/api/v1/integrations/execute/qualified",
            headers=auth_headers,
            json={
                "tool": "gmail.send_email",
                "params": {},
                "owner_email": AGENT_EMAIL,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error_type"] == "permission_denied"

    @pytest.mark.asyncio
    async def test_no_send_endpoint_added(self, client, auth_headers):
        """Sprint-11 hard rule: no new endpoint that submits/sends/posts."""
        # /integrations/send should NOT exist (only /execute, which gates)
        resp = await client.post(
            "/api/v1/integrations/send",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 404
