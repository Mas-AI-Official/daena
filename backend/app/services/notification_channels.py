"""Notification delivery channels -- the seam between in-app rows and devices.

Phase 4 item 12 (G6, 2026-07-02). NotificationService.emit writes the
in-app DB row (source of truth), then mirrors push-worthy notifications
through the channel returned by ``get_push_channel()``. Contract:

* ONE-WAY. Channels only deliver outward alerts. They never receive
  commands, never trigger tool execution, never write to the DB.
* FAIL-OPEN for the in-app path. A channel error must never break or
  delay ``emit`` -- ``deliver`` returns a ChannelResult, it never raises.
* OFF BY DEFAULT. WebPushChannel.available() is False unless the
  founder flips ``push_alerts_enabled`` AND provisions VAPID keys AND
  installs ``pywebpush``. Real-world reach is built now, switched off
  until explicitly enabled (autonomy gate).
* NO HARD DEPENDENCY. ``pywebpush`` is lazy-imported inside deliver /
  available so the backend boots without it installed.
* Gmail / outward email stays approval-gated in TRUST_FORBIDDEN_TOOLS.
  This module is NOT a bypass for it and must never grow a send-email
  channel without going through that gate.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ChannelResult:
    """Outcome of one delivery attempt to one device.

    gone=True means the push service says the endpoint no longer
    exists (HTTP 404/410) -- the caller should revoke the subscription
    so we stop paying for dead sends.
    """

    ok: bool
    gone: bool = False
    detail: str = ""


class WebPushChannel:
    """Web Push (VAPID, RFC 8030/8292) delivery via pywebpush.

    ``webpush()`` is synchronous (requests-based), so deliver runs it
    in a worker thread with ``asyncio.to_thread`` to keep the event
    loop free. Payload is a compact JSON the service worker renders.
    """

    name = "web_push"

    def available(self) -> bool:
        """True only when the founder has fully enabled the channel."""
        s = get_settings()
        if not s.push_alerts_enabled:
            return False
        if not (s.vapid_private_key and s.vapid_public_key and s.vapid_subject):
            return False
        try:
            import pywebpush  # noqa: F401  -- lazy availability probe
        except ImportError:
            return False
        return True

    async def deliver(self, *, subscription: dict, payload: dict) -> ChannelResult:
        """Send one push message to one subscription. Never raises."""
        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            return ChannelResult(ok=False, detail="pywebpush not installed")

        s = get_settings()

        def _send() -> None:
            webpush(
                subscription_info=subscription,
                data=json.dumps(payload),
                vapid_private_key=s.vapid_private_key,
                vapid_claims={"sub": s.vapid_subject},
            )

        try:
            await asyncio.to_thread(_send)
            return ChannelResult(ok=True)
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                return ChannelResult(
                    ok=False, gone=True, detail=f"endpoint gone ({status})",
                )
            return ChannelResult(ok=False, detail=f"webpush failed: {exc}")
        except Exception as exc:  # noqa: BLE001 -- fail-open by contract
            return ChannelResult(ok=False, detail=f"unexpected: {exc}")


# --- Channel registry / test seam -------------------------------------
#
# Tests inject a fake with set_push_channel(fake) and restore with
# set_push_channel(None). Production code only ever calls
# get_push_channel() and never caches the result across requests.

_default_channel = WebPushChannel()
_channel_override: WebPushChannel | None = None


def get_push_channel() -> WebPushChannel:
    """Return the active push channel (test override wins)."""
    return _channel_override if _channel_override is not None else _default_channel


def set_push_channel(channel: WebPushChannel | None) -> None:
    """Install a channel override (tests) or clear it with None."""
    global _channel_override
    _channel_override = channel
