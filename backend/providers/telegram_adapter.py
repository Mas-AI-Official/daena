"""
Telegram provider adapter.
Credentials: TELEGRAM_BOT_TOKEN from env. Webhook: verify secret_token if set.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any, Dict, Optional

from backend.providers.base import (
    ProviderBase,
    ProviderStatus,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramAdapter(ProviderBase):
    def __init__(self, provider_id: str, credentials: Dict[str, Any]):
        super().__init__(provider_id, credentials)
        self._connected = False
        self._bot_username: Optional[str] = None

    async def connect(self) -> None:
        token = (self.credentials.get("bot_token") or "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{TELEGRAM_API}/bot{token}/getMe")
            if r.status_code != 200:
                raise ValueError(f"Telegram auth failed: {r.status_code} {r.text[:200]}")
            data = r.json()
            if not data.get("ok"):
                raise ValueError(f"Telegram getMe not ok: {data}")
            self._bot_username = (data.get("result") or {}).get("username")
            self._connected = True
        logger.info("Telegram adapter connected (bot=@%s)", self._bot_username or "")

    async def disconnect(self) -> None:
        self._connected = False
        self._bot_username = None

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider_id=self.provider_id,
            connected=self._connected,
            details={"bot_username": self._bot_username},
        )

    async def send_message(self, msg: OutboundMessage) -> Dict[str, Any]:
        token = (self.credentials.get("bot_token") or "").strip()
        if not token:
            return {"success": False, "error": "TELEGRAM_BOT_TOKEN not set"}
        import httpx
        params = {"chat_id": msg.channel_id, "text": msg.text[:4096]}
        if msg.reply_to_id:
            params["reply_to_message_id"] = msg.reply_to_id
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{TELEGRAM_API}/bot{token}/sendMessage", params=params)
            if r.status_code != 200:
                return {"success": False, "error": f"{r.status_code} {r.text[:300]}"}
            data = r.json()
            if not data.get("ok"):
                return {"success": False, "error": str(data.get("description", data))}
            result = data.get("result") or {}
            return {"success": True, "message_id": result.get("message_id")}

    def receive_message(self, payload: Dict[str, Any]) -> Optional[InboundMessage]:
        # Telegram webhook: { "update_id": N, "message": { "chat": {...}, "from": {...}, "text": "..." } }
        msg = payload.get("message")
        if not msg or "text" not in msg:
            return None
        chat = msg.get("chat") or {}
        from_user = msg.get("from") or {}
        return InboundMessage(
            provider_id=self.provider_id,
            channel_id=str(chat.get("id", "")),
            user_id=str(from_user.get("id", "")),
            user_name=from_user.get("username") or from_user.get("first_name"),
            text=(msg.get("text") or "").strip(),
            raw=payload,
            message_id=str(msg.get("message_id", "")),
        )

    def verify_webhook(self, payload: bytes, headers: Dict[str, str]) -> bool:
        # Telegram: optional secret_token in header X-Telegram-Bot-Api-Secret-Token
        secret = self.credentials.get("webhook_secret_token") or ""
        if not secret:
            return True  # no secret configured = accept
        got = (headers.get("x-telegram-bot-api-secret-token") or headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
        return hmac.compare_digest(got, secret) if got else False
