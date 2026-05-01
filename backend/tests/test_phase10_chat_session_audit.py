"""Phase 10 commit-4 — verify chat-session mutations land in the audit ledger.

Pre-Phase-10, ``PATCH /api/v1/chat/sessions/{id}`` and ``DELETE
/api/v1/chat/sessions/{id}`` wrote to ``chat_sessions`` cleanly but
emitted **zero** audit rows — a Rule-17 honesty violation surfaced by
the matrix audit (Phase 9B).

This test pins the new behaviour: every session metadata mutation
appends an entry to the tamper-evident ``goa_audit_events`` ledger,
with a distinctive ``action_type`` (renamed / archived / unarchived /
deleted) so the founder can reconstruct who-did-what.

The audit emit is best-effort by design — if the audit write fails,
the user mutation still succeeds. We do not test the failure path here
(that's covered by the AuditService unit tests).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.chat import ChatSession
from app.models.governance import GoaAuditEvent


async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"chataudit-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Chat Audit Tester",
            "tenant_name": f"ChatAuditOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    user_obj = data["user"]
    # Auth response shape varies in tests; user-id key may be ``id`` or ``sub``
    user_id_raw = user_obj.get("id") or user_obj.get("user_id") or user_obj.get("sub")
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user_id": uuid.UUID(user_id_raw) if user_id_raw else None,
        "tenant_id": uuid.UUID(user_obj["tenant_id"]),
    }


@pytest.mark.asyncio
async def test_chat_session_rename_writes_audit_row(
    client: AsyncClient, db_session
) -> None:
    """A rename must append a ``chat_session.renamed`` ledger entry."""
    auth = await _register_and_login(client)
    create = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "before"},
        headers=auth["headers"],
    )
    assert create.status_code in (200, 201), create.text
    session_id = create.json()["data"]["id"]

    rename = await client.patch(
        f"/api/v1/chat/sessions/{session_id}",
        json={"title": "after rename"},
        headers=auth["headers"],
    )
    assert rename.status_code == 200, rename.text

    rows = (
        await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == auth["tenant_id"],
                GoaAuditEvent.action_type == "chat_session.renamed",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    if auth["user_id"] is not None:
        assert rows[0].actor_id == auth["user_id"]


@pytest.mark.asyncio
async def test_chat_session_archive_unarchive_writes_distinct_audit_rows(
    client: AsyncClient, db_session
) -> None:
    """Archive vs un-archive must emit distinct action types."""
    auth = await _register_and_login(client)
    create = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "archive-test"},
        headers=auth["headers"],
    )
    session_id = create.json()["data"]["id"]

    arch = await client.patch(
        f"/api/v1/chat/sessions/{session_id}",
        json={"is_archived": True},
        headers=auth["headers"],
    )
    assert arch.status_code == 200
    unarch = await client.patch(
        f"/api/v1/chat/sessions/{session_id}",
        json={"is_archived": False},
        headers=auth["headers"],
    )
    assert unarch.status_code == 200

    archived_rows = (
        await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == auth["tenant_id"],
                GoaAuditEvent.action_type == "chat_session.archived",
            )
        )
    ).scalars().all()
    unarchived_rows = (
        await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == auth["tenant_id"],
                GoaAuditEvent.action_type == "chat_session.unarchived",
            )
        )
    ).scalars().all()
    assert len(archived_rows) == 1, "archive must emit a distinct ledger entry"
    assert len(unarchived_rows) == 1, "unarchive must emit a distinct ledger entry"


@pytest.mark.asyncio
async def test_chat_session_delete_writes_audit_row(
    client: AsyncClient, db_session
) -> None:
    """Soft-delete must append a ``chat_session.deleted`` ledger entry."""
    auth = await _register_and_login(client)
    create = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "delete-test"},
        headers=auth["headers"],
    )
    session_id = create.json()["data"]["id"]

    delete = await client.delete(
        f"/api/v1/chat/sessions/{session_id}",
        headers=auth["headers"],
    )
    assert delete.status_code == 200

    rows = (
        await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == auth["tenant_id"],
                GoaAuditEvent.action_type == "chat_session.deleted",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    if auth["user_id"] is not None:
        assert rows[0].actor_id == auth["user_id"]
    # Session row should still exist (soft-delete via is_archived=True per
    # ChatService.delete_session contract).
    session_rows = (
        await db_session.execute(
            select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
        )
    ).scalars().all()
    assert len(session_rows) == 1
    assert session_rows[0].is_archived is True
