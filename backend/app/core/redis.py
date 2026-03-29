"""Redis client for caching and pub/sub.

Provides a singleton Redis connection used for:
- JWT blacklist (short-lived token revocation)
- Rate limiting counters
- Model health cache
- Real-time event pub/sub

Performance: if Redis is unavailable at startup, all subsequent
check_redis_health() calls return False instantly (no retry).
The flag resets every 60 seconds so recovery is detected.
"""

from __future__ import annotations

import asyncio
import time
from functools import lru_cache

import redis.asyncio as redis

from app.core.config import get_settings

# Fast-fail flag: once Redis is confirmed down, skip pings for 60s.
_redis_available: bool | None = None
_redis_last_check: float = 0.0
_REDIS_CHECK_INTERVAL = 60.0  # seconds between re-probes


@lru_cache
def get_redis_client() -> redis.Redis:
    """Get or create the singleton Redis client.

    Returns:
        Async Redis client connected to configured URL.
    """
    settings = get_settings()
    return redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )


async def check_redis_health() -> bool:
    """Ping Redis to verify connectivity.

    Uses a fast-fail cache: if Redis was down recently, returns
    False instantly without attempting a connection.  Re-probes
    every 60 seconds to detect recovery.

    Returns:
        True if Redis responds to PING.
    """
    global _redis_available, _redis_last_check  # noqa: PLW0603

    now = time.monotonic()
    if _redis_available is not None and (now - _redis_last_check) < _REDIS_CHECK_INTERVAL:
        return _redis_available

    try:
        client = get_redis_client()
        result = await asyncio.wait_for(client.ping(), timeout=0.5)
        _redis_available = bool(result)
    except (redis.RedisError, TimeoutError, OSError):
        _redis_available = False

    _redis_last_check = now
    return _redis_available
