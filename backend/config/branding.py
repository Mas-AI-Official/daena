"""
Single source of truth for bot display name.
Default: DaenaBot. Override via DAENABOT_DISPLAY_NAME (e.g. DanBot).
"""

import os
from typing import Optional

_DISPLAY_NAME: Optional[str] = None


def get_daena_bot_display_name() -> str:
    """Return the display name for our bot (DaenaBot / DanBot)."""
    global _DISPLAY_NAME
    if _DISPLAY_NAME is not None:
        return _DISPLAY_NAME
    raw = os.environ.get("DAENABOT_DISPLAY_NAME", "").strip()
    if raw:
        _DISPLAY_NAME = raw
    else:
        _DISPLAY_NAME = "DaenaBot"
    return _DISPLAY_NAME


def set_daena_bot_display_name(name: str) -> None:
    """Override display name (e.g. for tests)."""
    global _DISPLAY_NAME
    _DISPLAY_NAME = name or "DaenaBot"
