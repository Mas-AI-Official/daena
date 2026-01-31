"""
Provider config: enabled, allowed_tools, standing_instructions per provider.
Stored in config/provider_config.json. Credentials NEVER stored here (env only).
Default: all providers disabled until onboarded.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "provider_config.json"

# Default: every provider disabled; no tools allowed until configured
_DEFAULT: Dict[str, Any] = {
    "providers": {
        "discord": {
            "enabled": False,
            "allowed_tools": [],
            "standing_instructions": "",
        },
        "telegram": {
            "enabled": False,
            "allowed_tools": [],
            "standing_instructions": "",
        },
    },
    "version": 1,
}


def _load() -> Dict[str, Any]:
    out = json.loads(json.dumps(_DEFAULT))
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            providers = data.get("providers") or {}
            for pid, pcfg in providers.items():
                if pid in out["providers"]:
                    out["providers"][pid]["enabled"] = pcfg.get("enabled", False)
                    out["providers"][pid]["allowed_tools"] = list(pcfg.get("allowed_tools") or [])
                    out["providers"][pid]["standing_instructions"] = str(
                        pcfg.get("standing_instructions") or ""
                    )
        except Exception as e:
            logger.warning("Provider config load failed: %s", e)
    return out


def _save(data: Dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


_cached: Dict[str, Any] | None = None


def get_provider_config() -> Dict[str, Any]:
    global _cached
    if _cached is None:
        _cached = _load()
    return _cached


def reload_provider_config() -> Dict[str, Any]:
    global _cached
    _cached = _load()
    return _cached


def get_provider_settings(provider_id: str) -> Dict[str, Any]:
    cfg = get_provider_config()
    return cfg.get("providers", {}).get(provider_id, {}).copy()


def is_provider_enabled(provider_id: str) -> bool:
    return get_provider_settings(provider_id).get("enabled", False)


def get_allowed_tools(provider_id: str) -> List[str]:
    return list(get_provider_settings(provider_id).get("allowed_tools") or [])


def get_standing_instructions(provider_id: str) -> str:
    return str(get_provider_settings(provider_id).get("standing_instructions") or "")


def update_provider_settings(
    provider_id: str,
    enabled: Optional[bool] = None,
    allowed_tools: Optional[List[str]] = None,
    standing_instructions: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = get_provider_config()
    providers = cfg.get("providers") or {}
    if provider_id not in providers:
        providers[provider_id] = {
            "enabled": False,
            "allowed_tools": [],
            "standing_instructions": "",
        }
    if enabled is not None:
        providers[provider_id]["enabled"] = enabled
    if allowed_tools is not None:
        providers[provider_id]["allowed_tools"] = list(allowed_tools)
    if standing_instructions is not None:
        providers[provider_id]["standing_instructions"] = str(standing_instructions)
    cfg["providers"] = providers
    _save(cfg)
    reload_provider_config()
    return get_provider_settings(provider_id)
