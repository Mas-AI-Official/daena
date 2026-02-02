"""
Provider API: list, config, connect, disconnect, test, webhooks.
Provider messages never call tools directly; they create ToolRequests via Execution Layer.
Default: all providers disabled until onboarded.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.providers.base import InboundMessage, OutboundMessage
from backend.providers.config import (
    get_provider_config,
    get_provider_settings,
    update_provider_settings,
    is_provider_enabled,
    get_allowed_tools,
    reload_provider_config,
)
from backend.providers.registry import get_provider_registry, get_adapter, list_provider_ids
from backend.services.provider_tool_request import (
    create_tool_request_from_message,
    submit_tool_request,
    ProviderToolRequest,
)

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])
logger = logging.getLogger(__name__)


class ProviderConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    allowed_tools: Optional[list[str]] = None
    standing_instructions: Optional[str] = None


class TestMessageRequest(BaseModel):
    channel_id: str
    text: str = "Daena provider test"


@router.get("")
async def list_providers() -> Dict[str, Any]:
    """List providers with status (no secrets)."""
    return get_provider_registry()


@router.get("/config")
async def get_config() -> Dict[str, Any]:
    """Get provider config: enabled, allowed_tools, standing_instructions (no tokens)."""
    cfg = get_provider_config()
    out = {"providers": {}}
    for pid, p in (cfg.get("providers") or {}).items():
        out["providers"][pid] = {
            "enabled": p.get("enabled", False),
            "allowed_tools": list(p.get("allowed_tools") or []),
            "standing_instructions": (p.get("standing_instructions") or "")[:500],
        }
    return out


@router.post("/config")
async def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update provider config per provider. Body: { provider_id: { enabled?, allowed_tools?, standing_instructions? } }."""
    for pid, v in updates.items():
        if pid not in list_provider_ids():
            continue
        u = v if isinstance(v, dict) else (getattr(v, "model_dump", lambda: v)() if hasattr(v, "model_dump") else {})
        update_provider_settings(
            pid,
            enabled=u.get("enabled") if "enabled" in u else None,
            allowed_tools=u.get("allowed_tools") if "allowed_tools" in u else None,
            standing_instructions=u.get("standing_instructions") if "standing_instructions" in u else None,
        )
    reload_provider_config()
    return get_provider_config()


@router.post("/{provider_id}/connect")
async def connect_provider(provider_id: str) -> Dict[str, Any]:
    """Connect provider (validates token from env)."""
    if provider_id not in list_provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    try:
        adapter = get_adapter(provider_id)
        await adapter.connect()
        return {"success": True, "provider_id": provider_id, "status": adapter.status().__dict__}
    except Exception as e:
        logger.exception("Provider connect failed: %s", provider_id)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{provider_id}/disconnect")
async def disconnect_provider(provider_id: str) -> Dict[str, Any]:
    """Disconnect provider."""
    if provider_id not in list_provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    try:
        adapter = get_adapter(provider_id)
        await adapter.disconnect()
        return {"success": True, "provider_id": provider_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{provider_id}/status")
async def provider_status(provider_id: str) -> Dict[str, Any]:
    """Get provider connection status."""
    if provider_id not in list_provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    adapter = get_adapter(provider_id)
    s = adapter.status()
    return {"provider_id": provider_id, "connected": s.connected, "error": s.error, "details": s.details}


@router.post("/{provider_id}/test")
async def test_provider(provider_id: str, req: TestMessageRequest) -> Dict[str, Any]:
    """Send a test message (send only; no receive loop in API)."""
    if provider_id not in list_provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    try:
        adapter = get_adapter(provider_id)
        if not adapter.status().connected:
            await adapter.connect()
        out = await adapter.send_message(
            OutboundMessage(channel_id=req.channel_id, text=req.text)
        )
        return {"success": out.get("success", False), "result": out}
    except Exception as e:
        logger.exception("Provider test failed: %s", provider_id)
        raise HTTPException(status_code=400, detail=str(e))


# --- Webhooks: receive inbound messages -> create ToolRequest -> Execution Layer ---

async def _handle_inbound(msg: InboundMessage) -> Dict[str, Any]:
    """Create ToolRequest from message and submit to Execution Layer."""
    req = create_tool_request_from_message(msg)
    if not req:
        return {"handled": False, "reason": "no_tool_intent_or_disabled"}
    result = await submit_tool_request(req)
    return {"handled": True, "tool_request": req.tool_name, "result": result}


@router.post("/webhook/discord")
async def webhook_discord(request: Request) -> Dict[str, Any]:
    """Discord webhook: verify (optional), parse message, create ToolRequest, run through Execution Layer."""
    import json
    try:
        body = await request.body()
        payload = json.loads(body.decode()) if body else {}
        adapter = get_adapter("discord")
        if not adapter.verify_webhook(body, dict(request.headers)):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        msg = adapter.receive_message(payload)
        if not msg:
            return {"handled": False, "reason": "not_a_message"}
        return await _handle_inbound(msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Discord webhook error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/telegram")
async def webhook_telegram(request: Request) -> Dict[str, Any]:
    """Telegram webhook: verify (optional), parse message, create ToolRequest, run through Execution Layer."""
    try:
        body = await request.body()
        import json
        payload = json.loads(body.decode()) if body else {}
        adapter = get_adapter("telegram")
        if not adapter.verify_webhook(body, dict(request.headers)):
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
        msg = adapter.receive_message(payload)
        if not msg:
            return {"handled": False, "reason": "not_a_message"}
        return await _handle_inbound(msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Telegram webhook error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))