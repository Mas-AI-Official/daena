"""
Provider registry: get adapter by id, list providers. Credentials from env only.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from backend.providers.base import ProviderBase, ProviderStatus
from backend.providers.config import get_provider_config, get_provider_settings
from backend.providers.discord_adapter import DiscordAdapter
from backend.providers.telegram_adapter import TelegramAdapter


def _credentials_for(provider_id: str) -> Dict[str, Any]:
    """Load credentials from env only. Never from config file."""
    out = {}
    if provider_id == "discord":
        token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
        if token:
            out["bot_token"] = token
    elif provider_id == "telegram":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if token:
            out["bot_token"] = token
        secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET_TOKEN", "").strip()
        if secret:
            out["webhook_secret_token"] = secret
    return out


def get_adapter(provider_id: str) -> ProviderBase:
    if provider_id == "discord":
        return DiscordAdapter(provider_id, _credentials_for(provider_id))
    if provider_id == "telegram":
        return TelegramAdapter(provider_id, _credentials_for(provider_id))
    raise ValueError(f"Unknown provider: {provider_id}")


def list_provider_ids() -> List[str]:
    return list(get_provider_config().get("providers", {}).keys())


def get_provider_registry() -> Dict[str, Any]:
    """Return list of providers with status (no secrets)."""
    result = []
    for pid in list_provider_ids():
        settings = get_provider_settings(pid)
        try:
            adapter = get_adapter(pid)
            status = adapter.status()
            result.append({
                "provider_id": pid,
                "enabled": settings.get("enabled", False),
                "connected": status.connected,
                "error": status.error,
                "allowed_tools": settings.get("allowed_tools", []),
                "standing_instructions_preview": (settings.get("standing_instructions") or "")[:100],
            })
        except Exception as e:
            result.append({
                "provider_id": pid,
                "enabled": settings.get("enabled", False),
                "connected": False,
                "error": str(e),
                "allowed_tools": settings.get("allowed_tools", []),
                "standing_instructions_preview": "",
            })
    return {"providers": result}
