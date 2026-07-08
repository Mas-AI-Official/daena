"""Tests for POST /execution/tasks/{id}/run (TICKET-TASKS-RUN-01).

Before this ticket, PENDING tasks never executed because there was no
worker. /run kicks off an async background runner. Delegated tasks
(``checkpoint_data.delegation``) dispatch the real executor;
non-delegated tasks have NO executor wired, and the runner refuses to
fabricate completion (ADR-001 / Rule 17): they land FAILED with the
reason recorded, never a fake COMPLETED with a fake result.

Locks the contract:
    * /run on a PENDING task flips it to RUNNING synchronously.
    * /run on a RUNNING task returns 400 (no double-dispatch).
    * /run on FAILED / CANCELLED is accepted (enables retry + re-submit).
    * DETERMINISTIC GATE: a task with no executor is NEVER COMPLETED;
      it terminates FAILED with progress untouched and result None.
"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Task
from tests.test_execution import _register_and_login  # reuse helper


async def _create_task(
    client: AsyncClient, headers: dict[str, str], name: str,
) -> str:
    resp = await client.post(
        "/api/v1/execution/tasks",
        json={"name": name, "description": "smoke test"},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def _wait_terminal(
    client: AsyncClient, headers: dict[str, str],
    task_id: str, max_wait_s: float = 6.0,
) -> dict:
    """Poll GET /tasks/{id} until the background runner leaves RUNNING."""
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/api/v1/execution/tasks/{task_id}", headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        if data["status"] != "RUNNING":
            return data
        await asyncio.sleep(0.05)
    pytest.fail(f"Task {task_id} still RUNNING after {max_wait_s}s")


@pytest.mark.asyncio
async def test_run_task_flips_to_running(client: AsyncClient) -> None:
    """POST /tasks/{id}/run returns the task with status=RUNNING."""
    auth = await _register_and_login(client)
    task_id = await _create_task(client, auth["headers"], "Runnable task")

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

    # Drain the background runner: leaving it mid-write past teardown
    # invalidates the shared in-memory SQLite connection for later tests.
    await _wait_terminal(client, auth["headers"], task_id)


@pytest.mark.asyncio
async def test_no_executor_task_is_never_completed(
    client: AsyncClient,
) -> None:
    """DETERMINISTIC GATE: a non-delegated task has no executor, so the
    runner must land it FAILED with the reason recorded -- fabricating
    COMPLETED/progress=100/result here is a lie in the completion
    signal (ADR-001 / Rule 17)."""
    auth = await _register_and_login(client)
    task_id = await _create_task(
        client, auth["headers"], "No-executor honesty gate",
    )
    resp = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text

    data = await _wait_terminal(client, auth["headers"], task_id)
    assert data["status"] == "FAILED", (
        f"no-executor task must land FAILED, got {data['status']}"
    )
    assert data["status"] != "COMPLETED"
    assert data["progress"] != 100, "progress must not be fabricated"
    assert data["result"] is None, "honest failure must not fake a result"
    assert "no executor" in (data["error"] or "").lower()


@pytest.mark.asyncio
async def test_run_rejects_already_running(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """POST /run on a RUNNING task must return 400 (no double-dispatch).

    The RUNNING state is forced directly in the DB: the PATCH surface
    only allows PAUSED/CANCELLED, and racing the (now fast-failing)
    background runner would make this test flaky.
    """
    auth = await _register_and_login(client)
    task_id = await _create_task(client, auth["headers"], "Double-run guard")

    row = (
        await db_session.execute(
            select(Task).where(Task.id == uuid.UUID(task_id))
        )
    ).scalar_one()
    row.status = "RUNNING"
    await db_session.commit()

    second = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    # ValidationError -> 422 by default via the app exception handler.
    assert second.status_code in (400, 409, 422), second.text
    body = second.json()
    assert body["success"] is False
    assert "RUNNING" in body["error"]["message"]


@pytest.mark.asyncio
async def test_run_accepts_failed_task(client: AsyncClient) -> None:
    """Retry: FAILED tasks must be runnable again.

    FAILED is reached the real way -- running a no-executor task fails
    honestly -- so this pins that the honest failure stays retryable.
    """
    auth = await _register_and_login(client)
    task_id = await _create_task(client, auth["headers"], "Retry-after-fail")

    await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    first = await _wait_terminal(client, auth["headers"], task_id)
    assert first["status"] == "FAILED"

    resp = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "RUNNING"

    # Still no executor: the retry must also terminate honestly.
    retry = await _wait_terminal(client, auth["headers"], task_id)
    assert retry["status"] == "FAILED"


@pytest.mark.asyncio
async def test_run_accepts_cancelled_task(client: AsyncClient) -> None:
    """CANCELLED tasks must be runnable again (re-submit)."""
    auth = await _register_and_login(client)
    task_id = await _create_task(client, auth["headers"], "Re-submit")

    patch_resp = await client.patch(
        f"/api/v1/execution/tasks/{task_id}",
        json={"status": "CANCELLED"},
        headers=auth["headers"],
    )
    assert patch_resp.status_code == 200, patch_resp.text

    resp = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run",
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "RUNNING"

    # Drain the background runner so it does not bleed into other tests.
    await _wait_terminal(client, auth["headers"], task_id)
