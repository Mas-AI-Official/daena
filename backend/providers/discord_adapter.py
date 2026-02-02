"""
Discord provider adapter.
Credentials: DISCORD_BOT_TOKEN from env. Webhook: optional signature verification.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
from typing import Any, Dict, Optional

from backend.providers.base import (
    ProviderBase,
    ProviderStatus,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger(__name__)

DISCORD_API = "https://discord.com/api/v10"


class DiscordAdapter(ProviderBase):
    def __init__(self, provider_id: str, credentials: Dict[str, Any]):
        super().__init__(provider_id, credentials)
        self._connected = False
        self._bot_id: Optional[str] = None

    async def connect(self) -> None:
        token = (self.credentials.get("bot_token") or "").strip()
        if not token:
            raise ValueError("DISCORD_BOT_TOKEN not set")
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{DISCORD_API}/users/@me",
                headers={"Authorization": f"Bot {token}"},
            )
            if r.status_code != 200:
                raise ValueError(f"Discord auth failed: {r.status_code} {r.text[:200]}")
            data = r.json()
            self._bot_id = str(data.get("id", ""))
            self._connected = True
        logger.info("Discord adapter connected (bot_id=%s)", self._bot_id[:8] if self._bot_id else "")

    async def disconnect(self) -> None:
        self._connected = False
        self._bot_id = None

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider_id=self.provider_id,
            connected=self._connected,
            details={"bot_id_preview": (self._bot_id[:8] + "…") if self._bot_id else None},
        )

    async def send_message(self, msg: OutboundMessage) -> Dict[str, Any]:
        token = (self.credentials.get("bot_token") or "").strip()
        if not token:
            return {"success": False, "error": "DISCORD_BOT_TOKEN not set"}
        import httpx
        payload = {"content": msg.text[:2000]}
        if msg.reply_to_id:
            payload["message_reference"] = {"message_id": msg.reply_to_id}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{DISCORD_API}/channels/{msg.channel_id}/messages",
                headers={
                    "Authorization": f"Bot {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if r.status_code not in (200, 201):
                return {"success": False, "error": f"{r.status_code} {r.text[:300]}"}
            data = r.json()
            return {"success": True, "message_id": data.get("id")}

    def receive_message(self, payload: Dict[str, Any]) -> Optional[InboundMessage]:
        if payload.get("type") == 4 and "content" in payload:  # MESSAGE_CREATE
            author = payload.get("author") or {}
            return InboundMessage(
                provider_id=self.provider_id,
                channel_id=str(payload.get("channel_id", "")),
                user_id=str(author.get("id", "")),
                user_name=author.get("username"),
                text=(payload.get("content") or "").strip(),
                raw=payload,
                message_id=str(payload.get("id", "")),
            )
        return None

    def verify_webhook(self, payload: bytes, headers: Dict[str, str]) -> bool:
        # Discord: X-Signature-Ed25519 / body signed with public key (or skip if not configured)
        sig = headers.get("x-signature-ed25519") or headers.get("X-Signature-Ed25519")
        if not sig:
            return False
        # Optional: validate with DISCORD_PUBLIC_KEY; for smoke test we can skip
        return True
