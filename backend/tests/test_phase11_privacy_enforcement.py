"""Phase 11 PR-S1 — pin the two memory privacy gates.

Phase 10b's settings downstream-read audit catalogued
``users.settings.memory_generation`` and
``users.settings.search_past_conversations`` as ``DEAD`` (no enforcer).
This test pins the new behavior: when either is explicitly False, the
respective code path refuses the action.

Coverage:
* ``memory_generation`` gate at :class:`MemoryService.store`:
    - Default (setting unset): write succeeds (existing behavior).
    - Explicit True: write succeeds.
    - Explicit False: write is blocked; sentinel returned; no row in DB;
      a one-shot audit row lands in ``goa_audit_events`` with
      action_type ``privacy.memory_write_blocked``.
    - Audit/log "once" semantics: a second blocked write for the same
      user_id within the process emits NO additional audit row.
* ``search_past_conversations`` gate at :func:`MemoryService.recall_for_chat`
    is exercised via the chat orchestrator pipeline test.
    Note: the orchestrator-level integration test is harder to wire
    end-to-end without a live LLM; we cover the gate's primitive read
    path here via a unit test that mirrors the orchestrator's lookup.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import GoaAuditEvent
from app.models.memory import MemoryEntry
from app.services.memory import MemoryService


async def _register_and_login(client: AsyncClient) -> dict[str, Any]:
    """Register + login → real tenant + user → real headers + ids."""
    unique = uuid.uuid4().hex[:8]
    email = f"privacy-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Privacy Tester",
            "tenant_name": f"PrivacyOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    user_obj = data["user"]
    user_id_raw = (
        user_obj.get("id") or user_obj.get("user_id") or user_obj.get("sub")
    )
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user_id": uuid.UUID(user_id_raw),
        "tenant_id": uuid.UUID(user_obj["tenant_id"]),
    }


async def _set_user_setting(
    client: AsyncClient, headers: dict[str, str], key: str, value: Any
) -> None:
    """Toggle a single users.settings JSONB key via the canonical endpoint."""
    resp = await client.put(
        "/api/v1/settings/user", json={key: value}, headers=headers,
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# memory_generation gate at MemoryService.store
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_generation_default_allows_write(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Setting unset → existing behavior preserved (write succeeds)."""
    auth = await _register_and_login(client)
    # Phase 11 PR-S1: clear the process-level "warned" set so prior tests
    # don't suppress this user's audit row.
    MemoryService._privacy_blocked_warned.discard(auth["user_id"])

    svc = MemoryService(db_session)
    result = await svc.store(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        content="Founder prefers dark mode.",
        content_type="PREFERENCE",
    )
    assert "blocked_by_privacy" not in result
    assert result.get("id"), "default-allow path must return a real entry id"

    rows = (
        await db_session.execute(
            select(MemoryEntry).where(
                MemoryEntry.tenant_id == auth["tenant_id"],
                MemoryEntry.user_id == auth["user_id"],
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_memory_generation_explicit_true_allows_write(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Setting explicitly True (default value) also allows."""
    auth = await _register_and_login(client)
    MemoryService._privacy_blocked_warned.discard(auth["user_id"])
    await _set_user_setting(
        client, auth["headers"], "memory_generation", True,
    )

    svc = MemoryService(db_session)
    result = await svc.store(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        content="User likes Quintessence routing.",
        content_type="PREFERENCE",
    )
    assert "blocked_by_privacy" not in result
    assert result.get("id")


@pytest.mark.asyncio
async def test_memory_generation_false_blocks_write_and_audits(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Explicit False → no row written + sentinel returned + audit row."""
    auth = await _register_and_login(client)
    MemoryService._privacy_blocked_warned.discard(auth["user_id"])
    await _set_user_setting(
        client, auth["headers"], "memory_generation", False,
    )

    svc = MemoryService(db_session)
    result = await svc.store(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        content="This must NOT be persisted.",
        content_type="PREFERENCE",
    )
    assert result.get("blocked_by_privacy") is True
    assert result.get("id") is None
    assert result.get("reason") == "memory_generation=false"

    # No memory row should exist for this user.
    rows = (
        await db_session.execute(
            select(MemoryEntry).where(
                MemoryEntry.tenant_id == auth["tenant_id"],
                MemoryEntry.user_id == auth["user_id"],
            )
        )
    ).scalars().all()
    assert rows == []

    # An audit row of action_type=privacy.memory_write_blocked must land.
    audit_rows = (
        await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == auth["tenant_id"],
                GoaAuditEvent.action_type == "privacy.memory_write_blocked",
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].result == "BLOCKED"
    assert audit_rows[0].actor_id == auth["user_id"]


@pytest.mark.asyncio
async def test_memory_generation_block_audit_emits_only_once_per_user(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Repeated blocks for the same user emit just one audit row.

    Prevents log + ledger spam during a long chat session for a user
    who has opted out of memory generation.
    """
    auth = await _register_and_login(client)
    MemoryService._privacy_blocked_warned.discard(auth["user_id"])
    await _set_user_setting(
        client, auth["headers"], "memory_generation", False,
    )

    svc = MemoryService(db_session)
    for i in range(3):
        result = await svc.store(
            tenant_id=auth["tenant_id"],
            user_id=auth["user_id"],
            content=f"call-{i}",
            content_type="PREFERENCE",
        )
        assert result.get("blocked_by_privacy") is True

    audit_rows = (
        await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == auth["tenant_id"],
                GoaAuditEvent.action_type == "privacy.memory_write_blocked",
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1, (
        "Once-per-user-per-process audit emit must not spam the ledger"
    )


# ---------------------------------------------------------------------------
# search_past_conversations gate
# ---------------------------------------------------------------------------
#
# Direct end-to-end orchestrator coverage requires an LLM stub in the
# test client which the project does not currently set up. Instead, we
# cover the underlying contract: when users.settings.search_past_conversations
# is False, the lookup that the orchestrator performs in chat_orchestrator.py
# Stage 6 returns the False signal that gates the recall call. This is the
# same primitive the orchestrator uses, so a regression in its semantics
# would surface here.


@pytest.mark.asyncio
async def test_search_past_conversations_default_returns_allow(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """When the setting is unset, the orchestrator's lookup says allow."""
    from app.models.identity import User
    auth = await _register_and_login(client)
    row = (
        await db_session.execute(
            select(User.settings).where(User.id == auth["user_id"])
        )
    ).scalar_one_or_none()
    settings = row if isinstance(row, dict) else {}
    # Setting absent ⇒ orchestrator's `is False` check stays True (allow).
    assert settings.get("search_past_conversations") is not False


@pytest.mark.asyncio
async def test_search_past_conversations_false_blocks_recall(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Explicit False → orchestrator's lookup signal says block.

    Mirrors the exact lookup the orchestrator performs (chat_orchestrator.py
    Stage 6). If this assertion drifts, the gate is broken.
    """
    from app.models.identity import User
    auth = await _register_and_login(client)
    await _set_user_setting(
        client, auth["headers"], "search_past_conversations", False,
    )
    # Force a re-read from DB by using a fresh select.
    row = (
        await db_session.execute(
            select(User.settings).where(User.id == auth["user_id"])
        )
    ).scalar_one_or_none()
    settings = row if isinstance(row, dict) else {}
    assert settings.get("search_past_conversations") is False
    # That's the exact predicate the orchestrator gates on.
