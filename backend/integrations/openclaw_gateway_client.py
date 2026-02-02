"""
OpenClaw Gateway client: WebSocket connection with auth via connect.params.auth.token.
Bind to 127.0.0.1 only; do not expose to LAN.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Optional: use websockets if available
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


def _default_url() -> str:
    """Prefer DAENABOT_HANDS_URL; fallback OPENCLAW_GATEWAY_URL. Safe default: 127.0.0.1 only."""
    try:
        from backend.config.settings import env_first
        return env_first("DAENABOT_HANDS_URL", "OPENCLAW_GATEWAY_URL", default="ws://127.0.0.1:18789/ws") or "ws://127.0.0.1:18789/ws"
    except Exception:
        import os
        return os.environ.get("DAENABOT_HANDS_URL") or os.environ.get("OPENCLAW_GATEWAY_URL") or "ws://127.0.0.1:18789/ws"


def _default_token() -> Optional[str]:
    """Prefer DAENABOT_HANDS_TOKEN; fallback OPENCLAW_GATEWAY_TOKEN."""
    try:
        from backend.config.settings import env_first
        return env_first("DAENABOT_HANDS_TOKEN", "OPENCLAW_GATEWAY_TOKEN", default=None)
    except Exception:
        import os
        return os.environ.get("DAENABOT_HANDS_TOKEN") or os.environ.get("OPENCLAW_GATEWAY_TOKEN") or None


class OpenClawGatewayClient:
    """
    Connect to OpenClaw Gateway over WebSocket.
    Auth: handshake uses connect.params.auth.token (not querystring).
    """

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        timeout_sec: float = 30.0,
    ):
        self.url = (url or _default_url()).strip()
        self.token = (token or _default_token()) or ""
        self.timeout_sec = timeout_sec
        self._ws = None
        self._connected = False
        self._authenticated = False

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._connected

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    async def connect(self) -> bool:
        """Connect and authenticate using connect.params.auth.token."""
        if not HAS_WEBSOCKETS:
            logger.warning("websockets not installed; OpenClaw Gateway client disabled")
            return False
        if self._ws is not None:
            await self.disconnect()
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ),
                timeout=self.timeout_sec,
            )
            self._connected = True
            # OpenClaw docs: auth during handshake via connect.params.auth.token
            if self.token:
                connect_msg = {
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "connect",
                    "params": {
                        "auth": {"token": self.token},
                    },
                }
                await self._ws.send(json.dumps(connect_msg))
                raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
                resp = json.loads(raw)
                if resp.get("result") or not resp.get("error"):
                    self._authenticated = True
                else:
                    logger.warning("OpenClaw Gateway auth failed: %s", resp.get("error"))
            else:
                self._authenticated = False
            return self._authenticated or not self.token
        except asyncio.TimeoutError:
            logger.warning("OpenClaw Gateway connect timeout: %s", self.url)
            return False
        except Exception as e:
            logger.warning("OpenClaw Gateway connect failed: %s", e)
            return False

    async def disconnect(self) -> None:
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._connected = False
        self._authenticated = False

    async def execute_tool(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool action. Returns { correlation_id, success, result?, error? }.
        """
        correlation_id = str(uuid.uuid4())
        if not self._ws or not self._connected:
            return {
                "correlation_id": correlation_id,
                "success": False,
                "error": "Not connected to OpenClaw Gateway",
            }
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": correlation_id,
                "method": "execute",
                "params": action,
            }
            await self._ws.send(json.dumps(payload))
            raw = await asyncio.wait_for(self._ws.recv(), timeout=self.timeout_sec)
            resp = json.loads(raw)
            if "error" in resp:
                return {
                    "correlation_id": correlation_id,
                    "success": False,
                    "error": resp["error"].get("message", str(resp["error"])),
                    "result": None,
                }
            return {
                "correlation_id": correlation_id,
                "success": True,
                "result": resp.get("result"),
                "error": None,
            }
        except asyncio.TimeoutError:
            return {
                "correlation_id": correlation_id,
                "success": False,
                "error": "Execution timeout",
                "result": None,
            }
        except Exception as e:
            return {
                "correlation_id": correlation_id,
                "success": False,
                "error": str(e),
                "result": None,
            }


# Singleton for app use
_gateway_client: Optional[OpenClawGatewayClient] = None


def get_openclaw_client() -> OpenClawGatewayClient:
    global _gateway_client
    if _gateway_client is None:
        try:
            from backend.config.settings import settings
            _gateway_client = OpenClawGatewayClient(
                url=getattr(settings, "daenabot_hands_url", None) or _default_url(),
                token=getattr(settings, "daenabot_hands_token", None) or _default_token(),
            )
        except Exception:
            _gateway_client = OpenClawGatewayClient()
    return _gateway_client
