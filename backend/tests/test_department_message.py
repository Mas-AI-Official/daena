"""Tests for inter-department messaging.

Pin the contract:
* Send creates a SENT message with expires_at respected
* Inbox returns only messages addressed to the department; auto-acks
* Outbox returns only messages FROM the department
* Answer flips to ANSWERED and backfills acknowledged_at if needed
* Cannot re-answer a terminal (ANSWERED / EXPIRED) message
* Cannot send from_department == to_department (no self-loops)
* expire_overdue sweeps only SENT + ACKNOWLEDGED past their TTL
* Tenant isolation: tenant A's messages do not appear in tenant B's inbox
* REST endpoints mirror the service semantics + require auth
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.department_message import DepartmentMessage
from app.services.department_message_service import DepartmentMessageService


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    from app.models.identity import Tenant
    tenant = Tenant(
        id=test_tenant_id, name="Test Tenant",
        slug="test-tenant", settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    yield tenant


@pytest.fixture
async def service(db_session, seeded_tenant):
    return DepartmentMessageService(db_session)


# ── Send ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_creates_sent_message_with_expiry(
    service, test_tenant_id,
) -> None:
    msg = await service.send(
        tenant_id=test_tenant_id,
        from_department="Marketing",
        to_department="Legal & Compliance",
        subject="Review Q2 campaign claims",
        body="Please review the attached draft for regulatory risk.",
        context_ref="chat:session-42",
        ttl_seconds=600,
    )
    assert msg.status == "SENT"
    assert msg.from_department == "Marketing"
    assert msg.to_department == "Legal & Compliance"
    assert msg.expires_at is not None
    assert msg.answer is None
    assert msg.acknowledged_at is None


@pytest.mark.asyncio
async def test_send_rejects_self_loop(service, test_tenant_id) -> None:
    with pytest.raises(ValueError, match="must differ"):
        await service.send(
            tenant_id=test_tenant_id,
            from_department="Marketing",
            to_department="Marketing",
            subject="x", body="y",
        )


# ── Inbox ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_inbox_returns_only_open_by_default(
    service, test_tenant_id,
) -> None:
    await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S1", body="B1",
    )
    msg2 = await service.send(
        tenant_id=test_tenant_id, from_department="Engineering",
        to_department="Legal & Compliance", subject="S2", body="B2",
    )
    await service.answer(message_id=msg2.id, body="OK")

    inbox = await service.list_inbox(
        tenant_id=test_tenant_id, department="Legal & Compliance",
    )
    assert len(inbox) == 1
    assert inbox[0].subject == "S1"


@pytest.mark.asyncio
async def test_inbox_includes_closed_when_asked(
    service, test_tenant_id,
) -> None:
    msg = await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S", body="B",
    )
    await service.answer(message_id=msg.id, body="OK")
    inbox = await service.list_inbox(
        tenant_id=test_tenant_id,
        department="Legal & Compliance",
        include_closed=True,
    )
    assert len(inbox) == 1
    assert inbox[0].status == "ANSWERED"


@pytest.mark.asyncio
async def test_inbox_auto_acknowledges(
    service, test_tenant_id, db_session,
) -> None:
    """Reading the inbox flips SENT -> ACKNOWLEDGED so the sender
    can see its message was received."""
    sent = await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S", body="B",
    )
    await service.list_inbox(
        tenant_id=test_tenant_id, department="Legal & Compliance",
    )

    stmt = select(DepartmentMessage).where(DepartmentMessage.id == sent.id)
    refreshed = (await db_session.execute(stmt)).scalar_one()
    assert refreshed.status == "ACKNOWLEDGED"
    assert refreshed.acknowledged_at is not None


@pytest.mark.asyncio
async def test_inbox_auto_acknowledge_can_be_disabled(
    service, test_tenant_id, db_session,
) -> None:
    """Audit queries should not cause side-effects."""
    sent = await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S", body="B",
    )
    await service.list_inbox(
        tenant_id=test_tenant_id,
        department="Legal & Compliance",
        auto_acknowledge=False,
    )
    stmt = select(DepartmentMessage).where(DepartmentMessage.id == sent.id)
    refreshed = (await db_session.execute(stmt)).scalar_one()
    assert refreshed.status == "SENT"
    assert refreshed.acknowledged_at is None


# ── Outbox ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outbox_returns_sent_messages(
    service, test_tenant_id,
) -> None:
    await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S1", body="B1",
    )
    await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Finance", subject="S2", body="B2",
    )
    outbox = await service.list_outbox(
        tenant_id=test_tenant_id, department="Marketing",
    )
    assert len(outbox) == 2


# ── Answer ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_answer_flips_to_answered(service, test_tenant_id) -> None:
    sent = await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S", body="B",
    )
    msg = await service.answer(message_id=sent.id, body="Replace claim X with Y")
    assert msg.status == "ANSWERED"
    assert msg.answer == "Replace claim X with Y"
    assert msg.answered_at is not None
    # If no prior acknowledge, backfilled on answer
    assert msg.acknowledged_at is not None


@pytest.mark.asyncio
async def test_cannot_rewrite_already_answered(
    service, test_tenant_id,
) -> None:
    sent = await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S", body="B",
    )
    await service.answer(message_id=sent.id, body="first answer")
    with pytest.raises(ValueError, match="terminal state"):
        await service.answer(message_id=sent.id, body="second")


@pytest.mark.asyncio
async def test_answer_unknown_id_raises(service) -> None:
    with pytest.raises(ValueError, match="not found"):
        await service.answer(
            message_id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
            body="x",
        )


# ── Expiry ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expire_overdue_flips_sent_past_ttl(
    service, test_tenant_id, db_session,
) -> None:
    # Directly insert a message with past-expiry so we don't have to
    # sleep. Tests should be fast.
    msg = DepartmentMessage(
        tenant_id=test_tenant_id,
        from_department="Marketing",
        to_department="Legal & Compliance",
        subject="Urgent", body="ship?", status="SENT",
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add(msg)
    await db_session.flush()

    count = await service.expire_overdue(tenant_id=test_tenant_id)
    assert count == 1

    stmt = select(DepartmentMessage).where(DepartmentMessage.id == msg.id)
    refreshed = (await db_session.execute(stmt)).scalar_one()
    assert refreshed.status == "EXPIRED"


@pytest.mark.asyncio
async def test_expire_overdue_leaves_answered_alone(
    service, test_tenant_id, db_session,
) -> None:
    """Only SENT and ACKNOWLEDGED can expire; ANSWERED must persist."""
    sent = await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S", body="B",
        ttl_seconds=1,  # tiny
    )
    await service.answer(message_id=sent.id, body="OK")
    # Now force expiry check with manipulated time
    stmt = select(DepartmentMessage).where(DepartmentMessage.id == sent.id)
    row = (await db_session.execute(stmt)).scalar_one()
    row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.flush()

    await service.expire_overdue(tenant_id=test_tenant_id)
    refreshed = (await db_session.execute(stmt)).scalar_one()
    assert refreshed.status == "ANSWERED"


# ── wait_for_answer ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wait_for_answer_returns_none_on_timeout(
    service, test_tenant_id,
) -> None:
    sent = await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S", body="B",
    )
    result = await service.wait_for_answer(
        message_id=sent.id, timeout_seconds=1, poll_interval_seconds=0.1,
    )
    assert result is None


@pytest.mark.asyncio
async def test_wait_for_answer_returns_answered_immediately(
    service, test_tenant_id,
) -> None:
    sent = await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="S", body="B",
    )
    await service.answer(message_id=sent.id, body="OK")
    result = await service.wait_for_answer(
        message_id=sent.id, timeout_seconds=5, poll_interval_seconds=0.1,
    )
    assert result is not None
    assert result.status == "ANSWERED"


# ── Tenant isolation ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_tenants_are_isolated(
    service, test_tenant_id, db_session,
) -> None:
    from app.models.identity import Tenant

    other_tenant_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    db_session.add(Tenant(
        id=other_tenant_id, name="Other", slug="other", settings={},
    ))
    await db_session.flush()

    await service.send(
        tenant_id=test_tenant_id, from_department="Marketing",
        to_department="Legal & Compliance", subject="Ours", body="B",
    )
    inbox_other = await service.list_inbox(
        tenant_id=other_tenant_id, department="Legal & Compliance",
    )
    assert inbox_other == []


# ── REST endpoints ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/department-messages",
        json={
            "from_department": "Marketing", "to_department": "Legal",
            "subject": "s", "body": "b",
        },
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_api_send_inbox_answer_roundtrip(
    client: AsyncClient, auth_headers: dict[str, str], seeded_tenant,
) -> None:
    # Send
    send_res = await client.post(
        "/api/v1/department-messages",
        headers=auth_headers,
        json={
            "from_department": "Marketing",
            "to_department": "Legal & Compliance",
            "subject": "Q2 claims",
            "body": "Please review the draft",
            "context_ref": "chat:session-abc",
        },
    )
    assert send_res.status_code == 201
    msg_id = send_res.json()["id"]

    # Inbox
    inbox_res = await client.get(
        "/api/v1/department-messages/inbox?department=Legal%20%26%20Compliance",
        headers=auth_headers,
    )
    assert inbox_res.status_code == 200
    assert len(inbox_res.json()) == 1
    # Auto-ack happened on list
    assert inbox_res.json()[0]["status"] == "ACKNOWLEDGED"

    # Answer
    ans_res = await client.post(
        f"/api/v1/department-messages/{msg_id}/answer",
        headers=auth_headers,
        json={"body": "Replace claim X with claim Y for defensibility"},
    )
    assert ans_res.status_code == 200
    assert ans_res.json()["status"] == "ANSWERED"

    # Outbox now shows closed if asked
    outbox_res = await client.get(
        "/api/v1/department-messages/outbox?department=Marketing&include_closed=true",
        headers=auth_headers,
    )
    assert outbox_res.status_code == 200
    assert outbox_res.json()[0]["status"] == "ANSWERED"


@pytest.mark.asyncio
async def test_api_self_loop_returns_422(
    client: AsyncClient, auth_headers: dict[str, str], seeded_tenant,
) -> None:
    res = await client.post(
        "/api/v1/department-messages",
        headers=auth_headers,
        json={
            "from_department": "Marketing",
            "to_department": "Marketing",
            "subject": "x", "body": "y",
        },
    )
    assert res.status_code == 422
