"""
DaenaBot Hands status checker for awareness prompts and capabilities.
Use from chat/stream and system prompts so Daena answers "YES I have access" with live status.
"""
import os
import asyncio
import logging

logger = logging.getLogger(__name__)


async def check_hands_status(timeout_sec: float = 2.0) -> str:
    """Check if DaenaBot Hands gateway is reachable. Returns 'connected', 'offline', or 'not_configured'."""
    try:
        from backend.core.capabilities import _check_hands_gateway
        result = await _check_hands_gateway(timeout_sec)
        if result.get("connected"):
            return "connected"
        if result.get("error"):
            return "offline"
        return "not_configured"
    except Exception as e:
        logger.debug("DaenaBot Hands check failed: %s", e)
        return "offline"


def check_hands_status_sync(timeout_sec: float = 2.0) -> str:
    """Sync version for non-async contexts (e.g. sync LLM prompt builders)."""
    try:
        return asyncio.get_event_loop().run_until_complete(check_hands_status(timeout_sec))
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(check_hands_status(timeout_sec))
            finally:
                loop.close()
        except Exception:
            return "offline"
    except Exception:
        return "offline"
