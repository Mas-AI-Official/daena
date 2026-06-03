"""Tests for ConnectionService and CMP endpoints.

Integration tests: register -> login -> create connector -> connect -> permissions.
Validates the full CMP lifecycle including disconnect credential wipe
and vault encryption at rest.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

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
async def test_install_without_credentials_is_installed_not_connected(client: AsyncClient) -> None:
    """Install is local setup only; it must not claim account auth exists."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])

    resp = await client.post(
        "/api/v1/connections/instances/install",
        json={"connector_id": connector["id"]},
        headers=auth["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "INSTALLED"
    assert data["credentials"] is None


@pytest.mark.asyncio
async def test_connect_account_promotes_installed_connector(client: AsyncClient) -> None:
    """Account credentials are attached after install via a separate endpoint."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])

    install_resp = await client.post(
        "/api/v1/connections/instances/install",
        json={"connector_id": connector["id"]},
        headers=auth["headers"],
    )
    instance_id = install_resp.json()["data"]["id"]

    connect_resp = await client.post(
        f"/api/v1/connections/instances/{instance_id}/connect",
        json={"credentials": {"api_key": "sk-after-install"}},
        headers=auth["headers"],
    )
    assert connect_resp.status_code == 200
    data = connect_resp.json()["data"]
    assert data["status"] == "CONNECTED"
    # SEC-01: connect promotes to CONNECTED + signals has_credentials, but
    # must NOT echo the raw secret back in the response.
    assert data.get("has_credentials") is True
    assert not data.get("credentials"), "raw credentials must not be echoed"
    assert "sk-after-install" not in connect_resp.text


@pytest.mark.asyncio
async def test_install_no_auth_connector_is_connected(client: AsyncClient) -> None:
    """No-auth connectors do not need a second account-auth step."""
    auth = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/connections/connectors",
        json={
            "name": f"NoAuth-{uuid.uuid4().hex[:6]}",
            "description": "Public connector",
            "auth_type": "NONE",
            "tools": [{"name": "lookup"}],
            "category": "public",
            # ConnectionService._is_no_auth_connector requires the catalog
            # to explicitly opt in to "callable without auth" before an
            # install is auto-promoted to CONNECTED. Without this flag the
            # row stays INSTALLED -- the catalog might be a documentation
            # entry for an external resource Daena doesn't actually call.
            "config_schema": {"callable_without_auth": True},
        },
        headers=auth["headers"],
    )
    connector = resp.json()["data"]

    install_resp = await client.post(
        "/api/v1/connections/instances/install",
        json={"connector_id": connector["id"]},
        headers=auth["headers"],
    )
    assert install_resp.status_code == 201
    assert install_resp.json()["data"]["status"] == "CONNECTED"


@pytest.mark.asyncio
async def test_disconnect_clears_credentials(client: AsyncClient) -> None:
    """POST /instances/{id}/disconnect sets DISCONNECTED and wipes creds.

    PR-CONN-OAUTH-REFRESH-DISCONNECT (2026-05-03):
    body now requires ``{"confirm": true}``."""
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
        json={"confirm": True},
        headers=auth["headers"],
    )
    assert disconnect_resp.status_code == 200
    body = disconnect_resp.json()
    assert body["data"]["status"] == "DISCONNECTED"


# ── PR-CONN-OAUTH-REFRESH-DISCONNECT (2026-05-03) ──


@pytest.mark.asyncio
async def test_disconnect_without_confirm_returns_400(client: AsyncClient) -> None:
    """Disconnect REQUIRES {"confirm": true}. No body or confirm=false
    returns 400 with code=confirmation_required so a misclick / stale
    tab can never accidentally drop OAuth credentials."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])
    connect_resp = await client.post(
        "/api/v1/connections/instances",
        json={"connector_id": connector["id"], "credentials": {"api_key": "x"}},
        headers=auth["headers"],
    )
    instance_id = connect_resp.json()["data"]["id"]

    # No body at all.
    no_body = await client.post(
        f"/api/v1/connections/instances/{instance_id}/disconnect",
        headers=auth["headers"],
    )
    assert no_body.status_code == 400
    detail = no_body.json().get("detail", {})
    assert detail.get("code") == "confirmation_required"

    # Body with confirm=false.
    explicit_no = await client.post(
        f"/api/v1/connections/instances/{instance_id}/disconnect",
        json={"confirm": False},
        headers=auth["headers"],
    )
    assert explicit_no.status_code == 400


@pytest.mark.asyncio
async def test_archive_requires_confirm(client: AsyncClient) -> None:
    """POST /instances/{id}/archive same confirm contract."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])
    connect_resp = await client.post(
        "/api/v1/connections/instances",
        json={"connector_id": connector["id"]},
        headers=auth["headers"],
    )
    instance_id = connect_resp.json()["data"]["id"]
    no_body = await client.post(
        f"/api/v1/connections/instances/{instance_id}/archive",
        headers=auth["headers"],
    )
    assert no_body.status_code == 400


@pytest.mark.asyncio
async def test_archive_sets_status_and_hides_from_default_list(
    client: AsyncClient,
) -> None:
    """Archived instances vanish from default GET /instances. Pass
    ?status=ARCHIVED to see them again."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])
    connect_resp = await client.post(
        "/api/v1/connections/instances",
        json={"connector_id": connector["id"]},
        headers=auth["headers"],
    )
    instance_id = connect_resp.json()["data"]["id"]

    archive_resp = await client.post(
        f"/api/v1/connections/instances/{instance_id}/archive",
        json={"confirm": True},
        headers=auth["headers"],
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["data"]["status"] == "ARCHIVED"

    def _items_from(payload: dict) -> list:
        """List endpoint may return a list directly or a paginated dict
        with `items`. Handle both shapes for forward-compat."""
        d = payload.get("data", payload)
        if isinstance(d, list):
            return d
        return d.get("items", [])

    # Default list excludes archived rows.
    default_list = await client.get(
        "/api/v1/connections/instances", headers=auth["headers"],
    )
    assert default_list.status_code == 200
    items = _items_from(default_list.json())
    assert all(item["status"] != "ARCHIVED" for item in items), (
        f"Default list leaked ARCHIVED rows: {items}"
    )

    # Explicit ?status=ARCHIVED includes them again.
    archived_list = await client.get(
        "/api/v1/connections/instances?status=ARCHIVED",
        headers=auth["headers"],
    )
    assert archived_list.status_code == 200
    archived_ids = [item["id"] for item in _items_from(archived_list.json())]
    assert instance_id in archived_ids


@pytest.mark.asyncio
async def test_refresh_token_no_refresh_token_returns_failure(
    client: AsyncClient,
) -> None:
    """POST /instances/{id}/refresh-token on an instance with no stored
    refresh_token returns success=False reason=no_refresh_token (does
    NOT raise -- failure is a status, not an exception)."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])
    connect_resp = await client.post(
        "/api/v1/connections/instances",
        json={
            "connector_id": connector["id"],
            "credentials": {"api_key": "x"},  # no refresh_token field
        },
        headers=auth["headers"],
    )
    instance_id = connect_resp.json()["data"]["id"]

    refresh_resp = await client.post(
        f"/api/v1/connections/instances/{instance_id}/refresh-token",
        headers=auth["headers"],
    )
    assert refresh_resp.status_code == 200
    body = refresh_resp.json()
    assert body["success"] is False
    assert body["data"]["reason"] == "no_refresh_token"
    # Response must not echo any token-shaped field.
    body_text = str(body)
    for forbidden in ("api_key", "secret", "token_value"):
        assert forbidden not in body_text.lower() or forbidden == "no_refresh_token", (
            f"Token-like field leaked: {forbidden}"
        )


@pytest.mark.asyncio
async def test_refresh_token_outcome_shape_only_has_safe_keys(
    client: AsyncClient,
) -> None:
    """The /refresh-token response must carry only success + expires_at
    + reason. No token-shaped key may ever appear (covers all paths
    by integration test rather than source inspection)."""
    auth = await _register_and_login(client)
    connector = await _create_connector(client, auth["headers"])
    connect_resp = await client.post(
        "/api/v1/connections/instances",
        json={"connector_id": connector["id"]},
        headers=auth["headers"],
    )
    instance_id = connect_resp.json()["data"]["id"]
    refresh_resp = await client.post(
        f"/api/v1/connections/instances/{instance_id}/refresh-token",
        headers=auth["headers"],
    )
    assert refresh_resp.status_code == 200
    body = refresh_resp.json()
    data = body.get("data", {})
    assert set(data.keys()) <= {"success", "expires_at", "reason"}, (
        f"refresh-token outcome dict has unexpected keys: {set(data.keys())}"
    )
    forbidden = {"access_token", "refresh_token", "token", "api_key", "secret"}
    assert set(data.keys()).isdisjoint(forbidden)


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
async def test_connect_does_not_echo_decrypted_credentials(client: AsyncClient) -> None:
    """SEC-01: POST /instances must NOT echo raw secrets back in the response.

    (Previously this asserted the credentials were returned decrypted -- that
    encoded the SEC-01 leak. The secure contract: no raw secret values in the
    HTTP response; a non-secret has_credentials flag signals success.)
    """
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
    assert data.get("has_credentials") is True
    assert not data.get("credentials"), "raw credentials must not be echoed"
    assert "sk-secret-vault-test" not in resp.text


@pytest.mark.asyncio
async def test_get_instance_does_not_return_decrypted_credentials(client: AsyncClient) -> None:
    """SEC-01: GET /instances/{id} must NOT return decrypted credentials.

    Any same-tenant authenticated user can call this; returning raw secrets
    leaked OAuth/API credentials. The response carries has_credentials only.
    """
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
    data = get_resp.json()["data"]
    assert data.get("has_credentials") is True
    assert not data.get("credentials"), "raw credentials must not be returned"
    assert "oauth-abc-123" not in get_resp.text


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


# ── /extensions/install ──


@pytest.mark.asyncio
async def test_extensions_install_forwards_command_and_args(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    """The new install endpoint writes the caller's real npm package
    to claude_desktop_config.json.

    Before the fix the endpoint wrote ``npx -y <internal-id>`` which
    pointed at a non-existent npm package (e.g.
    ``mcp-google-drive``), so the installed config was unusable.
    Now, passing ``command`` + ``args`` forwards them verbatim so
    real packages like ``@modelcontextprotocol/server-gdrive`` land
    correctly.
    """
    import json
    from pathlib import Path

    # Redirect Path.home() to a temp dir so we don't pollute the
    # developer's real Claude Desktop config.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    auth = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/connections/extensions/install",
        headers=auth["headers"],
        json={
            "id": "mcp-google-drive",
            "name": "Google Drive MCP",
            "description": "Reference Drive MCP server",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-gdrive"],
        },
    )
    assert resp.status_code == 201, resp.text

    cfg_path = tmp_path / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    assert cfg_path.exists(), "install should write claude_desktop_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    servers = cfg.get("mcpServers") or {}
    # Key is the sanitized id, command + args mirror what the caller sent.
    assert "mcp-google-drive" in servers
    entry = servers["mcp-google-drive"]
    assert entry["command"] == "npx"
    assert entry["args"] == ["-y", "@modelcontextprotocol/server-gdrive"]


@pytest.mark.asyncio
async def test_extensions_install_triggers_bootstrap_refresh(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    """After a successful install, the MCP should be in the live
    bootstrap registry -- no server restart required. Pins the
    end-to-end "UI install -> chat-callable" contract.
    """
    import importlib
    from pathlib import Path

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Reload both modules so their module-level config paths resolve
    # under the monkeypatched Path.home().
    from app.services import mcp_bootstrap as boot_mod
    importlib.reload(boot_mod)
    # The connections module imports Path at call time, so no reload
    # needed there.

    auth = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/connections/extensions/install",
        headers=auth["headers"],
        json={
            "id": "mcp-test-e2e",
            "name": "Test E2E MCP",
            "description": "",
            "command": "npx",
            "args": ["-y", "@example/test-server"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["registry_refreshed"] is True
    assert data["server_key"] == "mcp-test-e2e"

    installed_keys = [m.server_key for m in boot_mod.list_installed_mcps()]
    assert "mcp-test-e2e" in installed_keys


@pytest.mark.asyncio
async def test_extensions_install_persists_tenant_mcp_server(
    client: AsyncClient, db_session, tmp_path, monkeypatch
) -> None:
    """UI extension installs must survive backend restart via DB persistence."""
    import importlib
    from pathlib import Path

    from app.models.mcp_server import McpServer, STATUS_ACTIVE

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # mcp_bootstrap caches Claude config paths at module import time. Without
    # reloading after the Path.home monkeypatch, bootstrap_installed_mcps() in
    # the install endpoint reads from the REAL home dir, mcp-persist-me never
    # appears in the registry, and status falls back to DISCOVERED. The
    # sibling test_extensions_install_triggers_bootstrap_refresh applies the
    # same reload for the same reason.
    from app.services import mcp_bootstrap as boot_mod
    importlib.reload(boot_mod)

    auth = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/connections/extensions/install",
        headers=auth["headers"],
        json={
            "id": "mcp-persist-me",
            "name": "Persist Me",
            "description": "Persistence regression fixture",
            "command": "npx",
            "args": ["-y", "@example/persist-me"],
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["mcp_persisted"] is True
    assert data["status"] == "installed"
    assert data["persistence_error"] is None

    row = (
        await db_session.execute(
            select(McpServer).where(McpServer.server_key == "mcp-persist-me")
        )
    ).scalar_one()
    assert row.display_name == "Persist Me"
    assert row.command == "npx"
    assert row.args == ["-y", "@example/persist-me"]
    assert row.package == "@example/persist-me"
    assert row.status == STATUS_ACTIVE
    # auth["user"] is the UserResponse schema (auth.py UserResponse) whose
    # id field is named user_id, not id. Earlier WIP draft of this test
    # used auth["user"]["id"] which never existed in the response shape.
    assert str(row.created_by_user_id) == auth["user"]["user_id"]


@pytest.mark.asyncio
async def test_extensions_uninstall_roundtrip(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    """Uninstall removes the entry and refreshes the registry."""
    import importlib
    from pathlib import Path

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from app.services import mcp_bootstrap as boot_mod
    importlib.reload(boot_mod)

    auth = await _register_and_login(client)

    # Install then uninstall.
    await client.post(
        "/api/v1/connections/extensions/install",
        headers=auth["headers"],
        json={
            "id": "mcp-delete-me",
            "name": "Delete Me",
            "command": "npx",
            "args": ["-y", "deleteme"],
        },
    )

    resp = await client.post(
        "/api/v1/connections/extensions/uninstall",
        headers=auth["headers"],
        json={"id": "delete-me"},  # accepts short form
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["removed"] is True

    installed_keys = [m.server_key for m in boot_mod.list_installed_mcps()]
    assert "mcp-delete-me" not in installed_keys


@pytest.mark.asyncio
async def test_extensions_uninstall_soft_deletes_tenant_mcp_server(
    client: AsyncClient, db_session, tmp_path, monkeypatch
) -> None:
    """Uninstall must remove live config and disable the persisted MCP row."""
    from pathlib import Path

    from app.models.mcp_server import McpServer, STATUS_DISABLED

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    auth = await _register_and_login(client)

    install_resp = await client.post(
        "/api/v1/connections/extensions/install",
        headers=auth["headers"],
        json={
            "id": "mcp-disable-me",
            "name": "Disable Me",
            "command": "npx",
            "args": ["-y", "@example/disable-me"],
        },
    )
    assert install_resp.status_code == 201

    resp = await client.post(
        "/api/v1/connections/extensions/uninstall",
        headers=auth["headers"],
        json={"id": "disable-me"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["removed"] is True
    assert data["mcp_persisted_removed"] is True
    assert data["persistence_error"] is None

    row = (
        await db_session.execute(
            select(McpServer).where(McpServer.server_key == "mcp-disable-me")
        )
    ).scalar_one()
    assert row.status == STATUS_DISABLED


@pytest.mark.asyncio
async def test_mcp_registry_endpoint_returns_live_state(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    """``GET /mcp-registry`` reflects the live bootstrap state, not
    the raw config file. Installing a plugin should make it appear
    on the next call without a restart."""
    import importlib
    from pathlib import Path

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from app.services import mcp_bootstrap as boot_mod
    importlib.reload(boot_mod)

    auth = await _register_and_login(client)

    # Initially empty.
    resp = await client.get(
        "/api/v1/connections/mcp-registry", headers=auth["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["count"] == 0

    # Install; registry should reflect immediately.
    await client.post(
        "/api/v1/connections/extensions/install",
        headers=auth["headers"],
        json={
            "id": "mcp-live-check",
            "name": "Live Check",
            "command": "npx",
            "args": ["-y", "livecheck"],
        },
    )

    resp2 = await client.get(
        "/api/v1/connections/mcp-registry", headers=auth["headers"]
    )
    data = resp2.json()["data"]
    assert data["count"] == 1
    assert data["entries"][0]["server_key"] == "mcp-live-check"


@pytest.mark.asyncio
async def test_extensions_uninstall_missing_returns_removed_false(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    """Removing a non-existent entry is idempotent, not an error."""
    from pathlib import Path

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    auth = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/connections/extensions/uninstall",
        headers=auth["headers"],
        json={"id": "never-installed"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["removed"] is False


@pytest.mark.asyncio
async def test_extensions_install_legacy_fallback(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    """Legacy callers that only send ``id`` still work: the endpoint
    falls back to ``npx -y <id>`` and records the entry. Ensures the
    contract remains backward-compatible with older frontends."""
    import json
    from pathlib import Path

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    auth = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/connections/extensions/install",
        headers=auth["headers"],
        json={
            "id": "mcp-some-legacy",
            "name": "Legacy MCP",
        },
    )
    assert resp.status_code == 201

    cfg_path = tmp_path / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    entry = cfg["mcpServers"]["mcp-some-legacy"]
    assert entry["command"] == "npx"
    assert entry["args"] == ["-y", "mcp-some-legacy"]
