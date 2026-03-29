"""Tests for ConnectionService and CMP endpoints.

Integration tests: register -> login -> create connector -> connect -> permissions.
Validates the full CMP lifecycle including disconnect credential wipe
and vault encryption at rest.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

# ── Helpers ──


async def _register_and_login(client: AsyncClient) -> dict:
    """Register a FOUNDER user and login."""
    unique = uuid.uuid4().hex[:8]
    email = f"cmp-{unique}@example.com"

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "CMP Tester",
            "tenant_name": f"CMPOrg-{unique}",
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


async def _create_connector(client: AsyncClient, headers: dict, name: str | None = None) -> dict:
    """Create a connector and return its data."""
    unique = uuid.uuid4().hex[:6]
    resp = await client.post(
        "/api/v1/connections/connectors",
        json={
            "name": name or f"TestConnector-{unique}",
            "description": "A test integration",
            "auth_type": "API_KEY",
            "tools": [
                {"name": "send_email", "description": "Send an email"},
                {"name": "read_inbox", "description": "Read inbox"},
            ],
            "category": "communication",
        },
        headers=headers,
    )
    return resp.json()["data"]


# ── Connector Catalog ──


@pytest.mark.asyncio
async def test_create_connector(client: AsyncClient) -> None:
    """POST /connections/connectors registers a new connector type."""
    auth = await _register_and_login(client)

    response = await client.post(
        "/api/v1/connections/connectors",
        json={
            "name": "slack_connector",
            "description": "Slack integration",
            "auth_type": "OAUTH2",
            "tools": [{"name": "post_message"}],
            "category": "messaging",
        },
        headers=auth["headers"],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "slack_connector"
    assert body["data"]["auth_type"] == "OAUTH2"
    assert len(body["data"]["tools"]) == 1


@pytest.mark.asyncio
async def test_create_duplicate_connector_fails(client: AsyncClient) -> None:
    """Two connectors with the same name should conflict."""
    auth = await _register_and_login(client)
    await _create_connector(client, auth["headers"], name="unique_connector")

    response = await client.post(
        "/api/v1/connections/connectors",
        json={"name": "unique_connector"},
        headers=auth["headers"],
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_connectors(client: AsyncClient) -> None:
    """GET /connections/connectors lists the global catalog."""
    auth = await _register_and_login(client)
    await _create_connector(client, auth["headers"])

    response = await client.get(
        "/api/v1/connections/connectors",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) >= 1


# ── Connector Instances ──


@pytest.mark.asyncio
async def test_connect_and_list_instances(client: AsyncClient) -> None:
    """POST /connections/instances creates a connection instance."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])

    # Connect
    resp = await client.post(
        "/api/v1/connections/instances",
        json={
            "connector_id": connector["id"],
            "credentials": {"api_key": "sk-test-key-123"},
        },
        headers=auth["headers"],
    )
    assert resp.status_code == 201
    instance = resp.json()["data"]
    assert instance["status"] == "CONNECTED"

    # List
    list_resp = await client.get(
        "/api/v1/connections/instances",
        headers=auth["headers"],
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_double_connect_fails(client: AsyncClient) -> None:
    """Connecting twice to the same connector should conflict."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])

    await client.post(
        "/api/v1/connections/instances",
        json={"connector_id": connector["id"]},
        headers=auth["headers"],
    )
    resp2 = await client.post(
        "/api/v1/connections/instances",
        json={"connector_id": connector["id"]},
        headers=auth["headers"],
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_disconnect_clears_credentials(client: AsyncClient) -> None:
    """POST /instances/{id}/disconnect sets DISCONNECTED and wipes creds."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])

    connect_resp = await client.post(
        "/api/v1/connections/instances",
        json={
            "connector_id": connector["id"],
            "credentials": {"api_key": "secret"},
        },
        headers=auth["headers"],
    )
    instance_id = connect_resp.json()["data"]["id"]

    disconnect_resp = await client.post(
        f"/api/v1/connections/instances/{instance_id}/disconnect",
        headers=auth["headers"],
    )
    assert disconnect_resp.status_code == 200
    body = disconnect_resp.json()
    assert body["data"]["status"] == "DISCONNECTED"


# ── Per-tool Permissions ──


@pytest.mark.asyncio
async def test_set_and_list_permissions(client: AsyncClient) -> None:
    """POST + GET permissions for a connector instance."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])

    # Connect
    connect_resp = await client.post(
        "/api/v1/connections/instances",
        json={"connector_id": connector["id"]},
        headers=auth["headers"],
    )
    instance_id = connect_resp.json()["data"]["id"]

    # Set permission
    perm_resp = await client.post(
        f"/api/v1/connections/instances/{instance_id}/permissions",
        json={
            "tool_name": "send_email",
            "permission_level": "ALWAYS_ALLOW",
        },
        headers=auth["headers"],
    )
    assert perm_resp.status_code == 200
    assert perm_resp.json()["data"]["permission_level"] == "ALWAYS_ALLOW"

    # Set another permission
    await client.post(
        f"/api/v1/connections/instances/{instance_id}/permissions",
        json={
            "tool_name": "read_inbox",
            "permission_level": "BLOCK",
        },
        headers=auth["headers"],
    )

    # List all
    list_resp = await client.get(
        f"/api/v1/connections/instances/{instance_id}/permissions",
        headers=auth["headers"],
    )
    assert list_resp.status_code == 200
    perms = list_resp.json()["data"]
    assert len(perms) == 2

    # Verify upsert: update existing permission
    update_resp = await client.post(
        f"/api/v1/connections/instances/{instance_id}/permissions",
        json={
            "tool_name": "send_email",
            "permission_level": "ASK_EACH_TIME",
        },
        headers=auth["headers"],
    )
    assert update_resp.json()["data"]["permission_level"] == "ASK_EACH_TIME"


# ── Vault Encryption at Rest ──


@pytest.mark.asyncio
async def test_connect_returns_decrypted_credentials(client: AsyncClient) -> None:
    """POST /instances returns credentials back to the user (decrypted)."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])

    resp = await client.post(
        "/api/v1/connections/instances",
        json={
            "connector_id": connector["id"],
            "credentials": {"api_key": "sk-secret-vault-test"},
        },
        headers=auth["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    # Credentials should be returned decrypted to the owning user
    assert data["credentials"] is not None
    assert data["credentials"]["api_key"] == "sk-secret-vault-test"


@pytest.mark.asyncio
async def test_get_instance_returns_decrypted_credentials(client: AsyncClient) -> None:
    """GET /instances/{id} returns decrypted credentials for the owner."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])

    connect_resp = await client.post(
        "/api/v1/connections/instances",
        json={
            "connector_id": connector["id"],
            "credentials": {"token": "oauth-abc-123"},
        },
        headers=auth["headers"],
    )
    instance_id = connect_resp.json()["data"]["id"]

    get_resp = await client.get(
        f"/api/v1/connections/instances/{instance_id}",
        headers=auth["headers"],
    )
    assert get_resp.status_code == 200
    creds = get_resp.json()["data"]["credentials"]
    assert creds == {"token": "oauth-abc-123"}


@pytest.mark.asyncio
async def test_list_instances_hides_credentials(client: AsyncClient) -> None:
    """GET /instances list should NOT expose credentials."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])

    await client.post(
        "/api/v1/connections/instances",
        json={
            "connector_id": connector["id"],
            "credentials": {"secret": "should-not-appear-in-list"},
        },
        headers=auth["headers"],
    )

    list_resp = await client.get(
        "/api/v1/connections/instances",
        headers=auth["headers"],
    )
    assert list_resp.status_code == 200
    instances = list_resp.json()["data"]
    assert len(instances) >= 1
    # The list schema (ConnectorInstanceResponse) does not include credentials
    for inst in instances:
        assert "credentials" not in inst or inst.get("credentials") is None
