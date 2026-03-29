"""Tests for ExecutionService and execution endpoints.

Integration tests: register → login → create EXE session → execute tool.
Validates CMD/EXE mode enforcement and task lifecycle.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

# ── Helpers ──


async def _register_and_login(client: AsyncClient) -> dict:
    """Register a user and login, returning access token + user data."""
    unique = uuid.uuid4().hex[:8]
    email = f"exec-{unique}@example.com"

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Exec Tester",
            "tenant_name": f"ExecOrg-{unique}",
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


async def _create_session(
    client: AsyncClient, headers: dict, mode: str = "CMD"
) -> str:
    """Create a chat session and return its ID."""
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Exec Test Session", "mode": mode},
        headers=headers,
    )
    return resp.json()["data"]["id"]


# ── CMD Mode Enforcement ──


@pytest.mark.asyncio
async def test_execute_tool_blocked_in_cmd_mode(client: AsyncClient) -> None:
    """Tool execution should fail in CMD mode with 422."""
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"], mode="CMD")

    response = await client.post(
        "/api/v1/execution/execute",
        json={
            "tool_name": "read_file",
            "params": {"path": "test.txt"},
            "session_id": session_id,
        },
        headers=auth["headers"],
    )
    # ValidationError maps to 422
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert "CMD" in body["error"]["message"] or "EXE" in body["error"]["message"]


# ── EXE Mode Execution ──


@pytest.mark.asyncio
async def test_execute_tool_in_exe_mode(client: AsyncClient) -> None:
    """Tool execution should succeed in EXE mode."""
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"], mode="EXE")

    response = await client.post(
        "/api/v1/execution/execute",
        json={
            "tool_name": "read_file",
            "params": {"path": "test.txt"},
            "session_id": session_id,
        },
        headers=auth["headers"],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["tool_name"] == "read_file"
    assert body["data"]["status"] == "COMPLETED"
    assert "governance" in body["data"]


@pytest.mark.asyncio
async def test_list_executions(client: AsyncClient) -> None:
    """GET /execution/executions/{session_id} returns execution history."""
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"], mode="EXE")

    # Execute a tool first
    await client.post(
        "/api/v1/execution/execute",
        json={
            "tool_name": "list_files",
            "params": {},
            "session_id": session_id,
        },
        headers=auth["headers"],
    )

    response = await client.get(
        f"/api/v1/execution/executions/{session_id}",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) >= 1


# ── Task Management ──


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient) -> None:
    """POST /execution/tasks creates a background task."""
    auth = await _register_and_login(client)

    response = await client.post(
        "/api/v1/execution/tasks",
        json={
            "name": "Generate quarterly report",
            "description": "Compile Q1 metrics and create PDF",
        },
        headers=auth["headers"],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "Generate quarterly report"
    assert body["data"]["status"] == "PENDING"
    assert body["data"]["progress"] == 0


@pytest.mark.asyncio
async def test_list_tasks(client: AsyncClient) -> None:
    """GET /execution/tasks returns user's tasks."""
    auth = await _register_and_login(client)

    # Create two tasks
    await client.post(
        "/api/v1/execution/tasks",
        json={"name": "Task Alpha"},
        headers=auth["headers"],
    )
    await client.post(
        "/api/v1/execution/tasks",
        json={"name": "Task Beta"},
        headers=auth["headers"],
    )

    response = await client.get(
        "/api/v1/execution/tasks",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) >= 2


@pytest.mark.asyncio
async def test_update_task_status(client: AsyncClient) -> None:
    """PATCH /execution/tasks/{id} can pause a task."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/execution/tasks",
        json={"name": "Pausable task"},
        headers=auth["headers"],
    )
    task_id = create_resp.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/execution/tasks/{task_id}",
        json={"status": "PAUSED"},
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "PAUSED"
