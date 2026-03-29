"""Tests for Mobile Command Interface -- API endpoints."""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient


async def _auth(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"mob-{unique}@test.com",
            "password": "SecurePass123!",
            "display_name": "Mobile Tester",
            "tenant_name": f"MobOrg-{unique}",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": f"mob-{unique}@test.com", "password": "SecurePass123!"},
    )
    data = resp.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}}


class TestMobileCommand:
    @pytest.mark.asyncio
    async def test_send_command(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.post(
            "/api/v1/mobile/command",
            json={"command": "Check system status", "priority": "P1"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert data["priority"] == "P1"

    @pytest.mark.asyncio
    async def test_command_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/mobile/command",
            json={"command": "test"},
        )
        assert resp.status_code == 401 or resp.status_code == 403


class TestMobileStatus:
    @pytest.mark.asyncio
    async def test_get_status(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.get(
            "/api/v1/mobile/status",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "online" in data["summary"].lower() or "tools" in data["summary"].lower()


class TestMobileApproval:
    @pytest.mark.asyncio
    async def test_approve_gate(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.post(
            "/api/v1/mobile/approve/gate-123",
            json={"decision": "approve"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert "approve" in resp.json()["summary"].lower()

    @pytest.mark.asyncio
    async def test_reject_gate(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.post(
            "/api/v1/mobile/approve/gate-456",
            json={"decision": "reject"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert "reject" in resp.json()["summary"].lower()

    @pytest.mark.asyncio
    async def test_invalid_decision(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.post(
            "/api/v1/mobile/approve/gate-789",
            json={"decision": "maybe"},
            headers=auth["headers"],
        )
        assert resp.status_code == 400


class TestMobileQuickActions:
    @pytest.mark.asyncio
    async def test_status_action(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.post(
            "/api/v1/mobile/quick-actions",
            json={"action": "status"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert "online" in resp.json()["summary"].lower()

    @pytest.mark.asyncio
    async def test_kill_action(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.post(
            "/api/v1/mobile/quick-actions",
            json={"action": "kill"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["priority"] == "P0"

    @pytest.mark.asyncio
    async def test_pause_action(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.post(
            "/api/v1/mobile/quick-actions",
            json={"action": "pause"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_action(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.post(
            "/api/v1/mobile/quick-actions",
            json={"action": "dance"},
            headers=auth["headers"],
        )
        assert resp.status_code == 400


class TestMobileSession:
    @pytest.mark.asyncio
    async def test_get_session(self, client: AsyncClient):
        auth = await _auth(client)
        sid = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/mobile/session/{sid}",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid

    @pytest.mark.asyncio
    async def test_invalid_session_id(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.get(
            "/api/v1/mobile/session/not-a-uuid",
            headers=auth["headers"],
        )
        assert resp.status_code == 400


class TestMobileNotifications:
    @pytest.mark.asyncio
    async def test_get_notifications(self, client: AsyncClient):
        auth = await _auth(client)
        resp = await client.get(
            "/api/v1/mobile/notifications",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
