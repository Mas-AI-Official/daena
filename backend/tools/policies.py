"""
Tool policies (safe-by-default).

No new crypto. No auth required in local mode. Enforce:
- domain allowlist (for web tools)
- timeouts
- per-agent/department rate limiting
- redaction of secrets
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from backend.config.settings import settings


class PolicyError(ValueError):
    pass


def redact(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if any(s in lk for s in ["password", "passwd", "secret", "token", "api_key", "apikey", "authorization"]):
                out[k] = "***REDACTED***"
            else:
                out[k] = redact(v)
        return out
    return str(obj)


def check_allowed_url(url: str) -> None:
    if not url:
        raise PolicyError("url is required")
    try:
        parsed = urlparse(url)
    except Exception:
        raise PolicyError("invalid url")
    if parsed.scheme not in ("http", "https"):
        raise PolicyError("only http/https urls are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise PolicyError("url hostname missing")

    if settings.automation_safe_mode:
        allowed = {d.strip().lower() for d in (settings.automation_allowed_domains or []) if str(d).strip()}
        if allowed and host not in allowed:
            raise PolicyError(f"domain not allowed: {host}")


@dataclass
class RateLimiter:
    per_min: int
    _events: Dict[str, List[float]] = None

    def __post_init__(self):
        self.per_min = max(1, int(self.per_min))
        self._events = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - 60.0
        lst = self._events.get(key, [])
        lst = [t for t in lst if t >= window_start]
        if len(lst) >= self.per_min:
            self._events[key] = lst
            return False
        lst.append(now)
        self._events[key] = lst
        return True


rate_limiter = RateLimiter(settings.automation_rate_limit_per_min)











