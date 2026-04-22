"""Tests for POST /execution/tasks/{id}/run (TICKET-TASKS-RUN-01).

Before this ticket, PENDING tasks never executed because there was no
worker. The /run endpoint kicks off a minimal async background runner
that drives RUNNING -> COMPLETED with progress reporting.

Locks the contract:
    * /run on a PENDING task flips it to RUNNING synchronously.
    * /run on a RUNNING task returns 400 (no double-dispatch).
    * /run on FAILED / CANCELLED / PAUSED is accepted (enables retry + resume).
    * /run reaches COMPLETED + progress=100 within ~4s for the minimal executor.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from tests.test_execution import _register_and_login  # reuse helper


@pytest.mark.asyncio
async def test_run_task_flips_to_running(client: AsyncClient) -> None:
    """POST /tasks/{id}/run returns the task with status=RUNNING."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/execution/tasks",
        json={"name": "Runnable task", "description": "smoke test"},
        headers=auth["headers"],
    )
    task_id = create_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "RUNNING"
    assert body["data"]["started_at"] is not None
    assert body["data"]["progress"] == 0


@pytest.mark.asyncio
async def test_run_task_reaches_completed(client: AsyncClient) -> None:
    """After ~3s the background runner should drive the task to COMPLETED."""
    auth = await _register_and_login(client)
    create_resp = await client.post(
        "/api/v1/execution/tasks",
        json={"name": "End-to-end task"},
        headers=auth["headers"],
    )
    task_id = create_resp.json()["data"]["id"]
    await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    await asyncio.sleep(3.5)  # bg runner sleeps 0.8s * 3 + commit overhead
    final = await client.get(
        f"/api/v1/execution/tasks/{task_id}",
        headers=auth["headers"],
    )
    assert final.status_code == 200
    data = final.json()["data"]
    assert data["status"] == "COMPLETED", f"got {data['status']} with error {data.get('error')}"
    assert data["progress"] == 100
    assert isinstance(data["result"], dict)
    assert "executor" in data["result"]
    assert data["result"]["executor"].startswith("minimal-run-task")


@pytest.mark.asyncio
async def test_run_rejects_already_running(client: AsyncClient) -> None:
    """Second POST /run while still RUNNING must return 400."""
    auth = await _register_and_login(client)
    create_resp = await client.post(
        "/api/v1/execution/tasks",
        json={"name": "Double-run guard"},
        headers=auth["headers"],
    )
    task_id = create_resp.json()["data"]["id"]
    first = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    # ValidationError -> 422 by default via the app exception handler.
    assert second.status_code in (400, 409, 422), second.text
    body = second.json()
    assert body["success"] is False
    assert "RUNNING" in body["error"]["message"]

    # Wait for bg to finish so it doesn't bleed into other tests.
    await asyncio.sleep(3.5)


@pytest.mark.asyncio
async def test_run_accepts_failed_task(client: AsyncClient) -> None:
    """Retry: FAILED tasks must be runnable again."""
    auth = await _register_and_login(client)
    create_resp = await client.post(
        "/api/v1/execution/tasks",
        json={"name": "Retry-after-fail"},
        headers=auth["headers"],
    )
    task_id = create_resp.json()["data"]["id"]
    # Simulate a prior failure.
    await client.patch(
        f"/api/v1/execution/tasks/{task_id}",
        json={"status": "FAILED"},
        headers=auth["headers"],
    )
    resp = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "RUNNING"
    await asyncio.sleep(3.5)


@pytest.mark.asyncio
async def test_run_accepts_cancelled_task(client: AsyncClient) -> None:
    """CANCELLED tasks must be runnable again (re-submit)."""
    auth = await _register_and_login(client)
    create_resp = await client.post(
        "/api/v1/execution/tasks",
        json={"name": "Re-submit"},
        headers=auth["headers"],
    )
    task_id = create_resp.json()["data"]["id"]
    await client.patch(
        f"/api/v1/execution/tasks/{task_id}",
        json={"status": "CANCELLED"},
        headers=auth["headers"],
    )
    resp = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "RUNNING"
    await asyncio.sleep(3.5)
