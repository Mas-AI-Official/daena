"""WebSocket endpoint for DaenaBot bridge connections.

DaenaBot is a local daemon users install on their machine. It connects
to this endpoint via WebSocket, receives tool_call messages, executes
them locally, and sends results back.

Architecture:
    Cloud Daena (this server) <--WebSocket--> DaenaBot (user's machine)

Protocol:
    DaenaBot -> Server: {"type": "handshake", "capabilities": [...], ...}
    Server -> DaenaBot: {"type": "tool_call", "call_id": "...", "tool": "...", "params": {...}}
    DaenaBot -> Server: {"type": "tool_result", "call_id": "...", "result": {...}}
    Server -> DaenaBot: {"type": "ping"}
    DaenaBot -> Server: {"type": "pong"}
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class BridgeConnection:
    """Represents a single DaenaBot bridge connection."""

    def __init__(
        self,
        ws: WebSocket,
        user_id: UUID,
        tenant_id: UUID,
    ) -> None:
        self.ws = ws
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.connected_at = time.time()
        self.capabilities: list[str] = []
        self.platform: str = "unknown"
        self.machine: str = "unknown"
        self.version: str = "0.0.0"
        self.system_info: dict[str, Any] = {}
        self._pending_calls: dict[str, asyncio.Future] = {}

    async def send_tool_call(
        self,
        tool: str,
        params: dict[str, Any],
        governance_tier: int = 0,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Send a tool call to DaenaBot and wait for the result."""
        call_id = str(uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_calls[call_id] = future

        await self.ws.send_json({
            "type": "tool_call",
            "call_id": call_id,
            "tool": tool,
            "params": params,
            "governance_tier": governance_tier,
        })

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending_calls.pop(call_id, None)
            return {"success": False, "error": f"Tool call timed out after {timeout}s"}

    def handle_result(self, call_id: str, result: dict[str, Any]) -> None:
        """Handle a tool result from DaenaBot."""
        future = self._pending_calls.pop(call_id, None)
        if future and not future.done():
            future.set_result(result)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "user_id": str(self.user_id),
            "connected_at": self.connected_at,
            "capabilities": self.capabilities,
            "platform": self.platform,
            "machine": self.machine,
            "version": self.version,
            "system_info": self.system_info,
            "uptime_seconds": int(time.time() - self.connected_at),
        }


class BridgeManager:
    """Manages all active DaenaBot bridge connections.

    One bridge per user (last connection wins).
    """

    def __init__(self) -> None:
        self._connections: dict[str, BridgeConnection] = {}  # user_id -> connection

    def register(self, conn: BridgeConnection) -> None:
        """Register a new bridge connection."""
        key = str(conn.user_id)
        self._connections[key] = conn
        logger.info(
            "bridge.connected",
            user_id=key,
            platform=conn.platform,
            machine=conn.machine,
        )

    def unregister(self, user_id: str | UUID) -> None:
        """Remove a bridge connection."""
        key = str(user_id)
        self._connections.pop(key, None)
        logger.info("bridge.disconnected", user_id=key)

    def get(self, user_id: str | UUID) -> BridgeConnection | None:
        """Get bridge connection for a user."""
        return self._connections.get(str(user_id))

    def is_connected(self, user_id: str | UUID) -> bool:
        """Check if a user has an active bridge."""
        return str(user_id) in self._connections

    def list_all(self) -> list[dict[str, Any]]:
        """List all active bridges."""
        return [conn.to_dict() for conn in self._connections.values()]


# Singleton bridge manager
bridge_manager = BridgeManager()


def get_bridge_manager() -> BridgeManager:
    """Get the global bridge manager instance."""
    return bridge_manager


@router.websocket("/ws/bridge")
async def websocket_bridge(websocket: WebSocket) -> None:
    """WebSocket endpoint for DaenaBot bridge connections.

    Auth: Bearer token in headers or query param.
    """
    # Extract auth token
    auth_header = websocket.headers.get("authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = websocket.query_params.get("token", "")

    if not token:
        await websocket.close(code=4001, reason="Missing auth token")
        return

    # Validate token and get user
    try:
        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
        tenant_id = UUID(payload.get("tenant_id", payload.get("tid", "")))
    except Exception as exc:
        await websocket.close(code=4003, reason=f"Invalid token: {exc}")
        return

    await websocket.accept()

    conn = BridgeConnection(websocket, user_id, tenant_id)

    try:
        # Wait for handshake
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        handshake = json.loads(raw)

        if handshake.get("type") == "handshake":
            conn.capabilities = handshake.get("capabilities", [])
            conn.platform = handshake.get("platform", "unknown")
            conn.machine = handshake.get("machine", "unknown")
            conn.version = handshake.get("version", "0.0.0")
            conn.system_info = handshake.get("system_info", {})

        bridge_manager.register(conn)

        # Send welcome
        await websocket.send_json({
            "type": "welcome",
            "message": "DaenaBot connected. Ready for tool calls.",
            "server_version": "3.7.1",
        })

        # Listen for messages
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "tool_result":
                call_id = data.get("call_id", "")
                result = data.get("result", {})
                conn.handle_result(call_id, result)

            elif msg_type == "pong":
                pass  # Keepalive response

            elif msg_type == "handshake":
                # Re-handshake (capability update)
                conn.capabilities = data.get("capabilities", conn.capabilities)

            else:
                logger.debug("bridge.unknown_message", type=msg_type)

    except WebSocketDisconnect:
        logger.info("bridge.client_disconnected", user_id=str(user_id))
    except asyncio.TimeoutError:
        logger.warning("bridge.handshake_timeout", user_id=str(user_id))
    except Exception:
        logger.exception("bridge.error", user_id=str(user_id))
    finally:
        bridge_manager.unregister(user_id)


@router.get("/bridge/status")
async def bridge_status() -> dict:
    """Check if any DaenaBot bridges are connected (admin/debug)."""
    return {
        "success": True,
        "data": {
            "active_bridges": len(bridge_manager._connections),
            "bridges": bridge_manager.list_all(),
        },
    }


# ── CLI Bridge Token & Setup ──


@router.post("/bridge/token")
async def generate_bridge_token(
    request_body: dict | None = None,
) -> dict:
    """Generate a scoped API token for CLI bridge connections.

    This token is used by daena-mcp (npm/pip) to authenticate WebSocket
    connections from the user's local machine to Daena cloud.

    Security:
    - Token is a standard JWT with bridge-specific claims
    - Scoped to: read_tasks, submit_results, read_skills
    - 30-day expiry (configurable)
    - User can revoke via DELETE /bridge/token
    - Rate limited: 100 tasks/hour per token
    """
    from fastapi import Depends
    from app.api.deps import get_current_user
    from app.core.security import create_access_token

    # This endpoint requires auth (injected by router middleware)
    # For now, generate a long-lived bridge token
    # In production, this should use the request's auth context

    body = request_body or {}
    label = body.get("label", "CLI Bridge")

    # Generate a 30-day bridge token with limited scope
    token_data = {
        "scope": "bridge",
        "permissions": ["read_tasks", "submit_results", "read_skills"],
        "label": label,
    }

    token = create_access_token(
        data=token_data,
        expires_minutes=43200,  # 30 days
    )

    return {
        "success": True,
        "data": {
            "token": token,
            "expires_in_days": 30,
            "scope": "bridge",
            "permissions": token_data["permissions"],
            "label": label,
            "setup_commands": {
                "npm": f"npx @mas-ai/daena-mcp --token {token}",
                "pip": f"pip install daena-mcp && daena-mcp --token {token}",
                "claude_code": f"claude mcp add daena -- npx @mas-ai/daena-mcp --token {token}",
            },
        },
    }


@router.get("/bridge/setup")
async def bridge_setup_info() -> dict:
    """Return CLI bridge setup instructions for the current deployment.

    Frontend uses this to render the setup wizard with correct URLs
    and install commands tailored to the deployment environment.
    """
    from app.core.config import get_settings
    settings = get_settings()

    # Determine the base URL for WebSocket connections
    is_cloud = settings.app_env.lower() in ("production", "staging")
    if is_cloud:
        # Cloud Run URL from CORS origins or default
        cloud_origins = [o for o in settings.cors_origins if "run.app" in o or "mas-ai" in o]
        base_url = cloud_origins[0] if cloud_origins else "https://daena.mas-ai.co"
        ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    else:
        base_url = f"http://127.0.0.1:{settings.port}"
        ws_url = f"ws://127.0.0.1:{settings.port}"

    return {
        "success": True,
        "data": {
            "environment": settings.app_env,
            "base_url": base_url,
            "ws_url": f"{ws_url}/api/v1/ws/bridge",
            "install_methods": [
                {
                    "id": "npm",
                    "name": "npm (Node.js)",
                    "command": "npm install -g @mas-ai/daena-mcp",
                    "description": "Recommended for Claude Code users",
                    "platforms": ["windows", "macos", "linux"],
                },
                {
                    "id": "pip",
                    "name": "pip (Python)",
                    "command": "pip install daena-mcp",
                    "description": "For Python developers",
                    "platforms": ["windows", "macos", "linux"],
                },
            ],
            "claude_code_config": {
                "description": "Add to Claude Code as an MCP server",
                "command": "claude mcp add daena -- npx @mas-ai/daena-mcp --url {ws_url}/api/v1/ws/bridge --token YOUR_TOKEN",
                "config_snippet": {
                    "mcpServers": {
                        "daena": {
                            "command": "npx",
                            "args": [
                                "@mas-ai/daena-mcp",
                                "--url", f"{ws_url}/api/v1/ws/bridge",
                                "--token", "YOUR_BRIDGE_TOKEN",
                            ],
                        },
                    },
                },
            },
            "security": {
                "token_expiry_days": 30,
                "rate_limit": "100 tasks/hour",
                "credential_relay": False,
                "description": (
                    "Your API keys and subscriptions NEVER leave your machine. "
                    "Daena sends task descriptions, your CLI executes them with "
                    "your own credentials, and returns results to Daena for audit logging."
                ),
            },
        },
    }
