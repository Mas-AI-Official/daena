"""Tests for ChatService and chat endpoints.

Integration tests: register → login → create session → send message → list.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ── Helpers ──


async def _register_and_login(client: AsyncClient) -> dict:
    """Register a user and login, returning access token + user data."""
    import uuid

    unique = uuid.uuid4().hex[:8]
    email = f"chat-{unique}@example.com"

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Chat Tester",
            "tenant_name": f"ChatOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
    }


# ── Session CRUD ──


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient) -> None:
    """POST /chat/sessions creates a session with correct defaults."""
    auth = await _register_and_login(client)

    response = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Test Session"},
        headers=auth["headers"],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["title"] == "Test Session"
    assert body["data"]["mode"] == "CMD"
    assert body["data"]["routing_mode"] == "STANDARD"
    assert body["data"]["governance_slider"] == "BALANCED"
    assert body["data"]["is_archived"] is False
    assert body["data"]["message_count"] == 0


@pytest.mark.asyncio
async def test_create_session_with_custom_mode(client: AsyncClient) -> None:
    """Session respects non-default mode and routing_mode."""
    auth = await _register_and_login(client)

    response = await client.post(
        "/api/v1/chat/sessions",
        json={
            "title": "EXE Session",
            "mode": "EXE",
            "routing_mode": "COUNCIL",
            "governance_mode": "GOVERNED",
        },
        headers=auth["headers"],
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["mode"] == "EXE"
    assert data["routing_mode"] == "COUNCIL"
    assert data["governance_slider"] == "GOVERNED"


@pytest.mark.asyncio
async def test_list_sessions_empty(client: AsyncClient) -> None:
    """List sessions returns empty when no sessions exist."""
    auth = await _register_and_login(client)

    response = await client.get(
        "/api/v1/chat/sessions",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_list_sessions_returns_created(client: AsyncClient) -> None:
    """List sessions returns previously created sessions."""
    auth = await _register_and_login(client)

    # Create 2 sessions
    await client.post(
        "/api/v1/chat/sessions",
        json={"title": "First"},
        headers=auth["headers"],
    )
    await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Second"},
        headers=auth["headers"],
    )

    response = await client.get(
        "/api/v1/chat/sessions",
        headers=auth["headers"],
    )
    body = response.json()
    assert body["pagination"]["total"] == 2
    # Ordered by created_at desc — newest first
    titles = [s["title"] for s in body["data"]]
    assert "First" in titles
    assert "Second" in titles


@pytest.mark.asyncio
async def test_get_session_by_id(client: AsyncClient) -> None:
    """GET /chat/sessions/{id} returns the correct session."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Fetch Me"},
        headers=auth["headers"],
    )
    session_id = create_resp.json()["data"]["id"]

    response = await client.get(
        f"/api/v1/chat/sessions/{session_id}",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Fetch Me"


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient) -> None:
    """GET nonexistent session returns 404."""
    auth = await _register_and_login(client)

    response = await client.get(
        "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000099",
        headers=auth["headers"],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_session(client: AsyncClient) -> None:
    """PATCH /chat/sessions/{id} updates specified fields only."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Original"},
        headers=auth["headers"],
    )
    session_id = create_resp.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/chat/sessions/{session_id}",
        json={"title": "Updated Title", "is_archived": True},
        headers=auth["headers"],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Updated Title"
    assert data["is_archived"] is True
    assert data["mode"] == "CMD"  # Unchanged


# ── Messages ──


@pytest.mark.asyncio
async def test_send_and_retrieve_message(client: AsyncClient) -> None:
    """POST + GET messages round-trips correctly.

    send_message persists USER message then generates ASSISTANT reply
    (Ollama fallback returns an error message when Ollama is offline).
    Response shape: {"user_message": {...}, "assistant_message": {...}}.
    """
    auth = await _register_and_login(client)

    # Create session
    create_resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Message Test"},
        headers=auth["headers"],
    )
    session_id = create_resp.json()["data"]["id"]

    # Send message — returns both user + assistant messages
    msg_resp = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"role": "USER", "content": "Hello Daena!"},
        headers=auth["headers"],
    )
    assert msg_resp.status_code == 201
    msg_data = msg_resp.json()["data"]
    assert msg_data["user_message"]["role"] == "USER"
    assert msg_data["user_message"]["content"] == "Hello Daena!"
    assert msg_data["assistant_message"]["role"] == "ASSISTANT"

    # Retrieve messages — should have 2 (USER + ASSISTANT fallback)
    list_resp = await client.get(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=auth["headers"],
    )
    assert list_resp.status_code == 200
    messages = list_resp.json()["data"]
    assert len(messages) == 2
    assert messages[0]["content"] == "Hello Daena!"


@pytest.mark.asyncio
async def test_message_count_increments(client: AsyncClient) -> None:
    """Session's message_count reflects actual messages.

    Each send_message call produces 2 persisted messages:
    1 USER + 1 ASSISTANT (real reply or Ollama-offline fallback).
    So 3 sends → 6 total messages.
    """
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Counter Test"},
        headers=auth["headers"],
    )
    session_id = create_resp.json()["data"]["id"]

    # Send 3 user messages (each also generates an assistant reply)
    for i in range(3):
        await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": f"Message {i}"},
            headers=auth["headers"],
        )

    # 3 user + 3 assistant = 6 total messages
    session_resp = await client.get(
        f"/api/v1/chat/sessions/{session_id}",
        headers=auth["headers"],
    )
    assert session_resp.json()["data"]["message_count"] == 6


@pytest.mark.asyncio
async def test_send_message_to_nonexistent_session(client: AsyncClient) -> None:
    """Sending to a nonexistent session returns 404."""
    auth = await _register_and_login(client)

    response = await client.post(
        "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000099/messages",
        json={"content": "Orphaned message"},
        headers=auth["headers"],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_archived_sessions_excluded_by_default(client: AsyncClient) -> None:
    """Archived sessions don't appear in default listing."""
    auth = await _register_and_login(client)

    # Create and archive a session
    create_resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Archived"},
        headers=auth["headers"],
    )
    session_id = create_resp.json()["data"]["id"]
    await client.patch(
        f"/api/v1/chat/sessions/{session_id}",
        json={"is_archived": True},
        headers=auth["headers"],
    )

    # Default listing excludes archived
    list_resp = await client.get(
        "/api/v1/chat/sessions",
        headers=auth["headers"],
    )
    assert list_resp.json()["pagination"]["total"] == 0

    # With include_archived=true, it appears
    list_resp2 = await client.get(
        "/api/v1/chat/sessions?include_archived=true",
        headers=auth["headers"],
    )
    assert list_resp2.json()["pagination"]["total"] == 1
