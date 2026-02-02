"""
Runtime security state for Guardian / Incident response.

- Lockdown: founder panel or Guardian can set runtime lockdown; settings.security_lockdown_mode
  is the env-based default; is_lockdown_active() returns env OR runtime override.
"""

import os
from typing import Optional

# Runtime override: when set by founder lockdown endpoint, takes precedence until cleared
_runtime_lockdown: Optional[bool] = None


def is_lockdown_active() -> bool:
    """True if system is in lockdown (env SECURITY_LOCKDOWN_MODE=1 or runtime set)."""
    global _runtime_lockdown
    if _runtime_lockdown is not None:
        return _runtime_lockdown
    v = os.getenv("SECURITY_LOCKDOWN_MODE", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def set_lockdown(active: bool) -> None:
    """Set runtime lockdown (e.g. from founder panel /system/emergency/lockdown)."""
    global _runtime_lockdown
    _runtime_lockdown = active


def clear_lockdown_override() -> None:
    """Clear runtime override so only env SECURITY_LOCKDOWN_MODE applies."""
    global _runtime_lockdown
    _runtime_lockdown = None
