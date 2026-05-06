"""Google OAuth Live Readiness Test -- Sprint-16 PR-3 (2026-05-06).

Read-only liveness probe for the three Google providers Phase 3
cares about: Gmail, Calendar, Drive.

Goes beyond "ConnectorInstance row exists" -- actually hits Google
with the lightest-possible read call and classifies the result
into a stable status enum:

  connected            HTTP 2xx
  expired              HTTP 401 (token expired or revoked)
  insufficient_scope   HTTP 403 with scope-shaped error body
  failed               anything else (network error, unexpected HTTP)

The endpoint NEVER returns user data. The probes are picked so
their bodies are essentially metadata-only:

  Gmail     /gmail/v1/users/me/profile         -> emailAddress + counts
  Calendar  /calendar/v3/calendars/primary     -> calendar metadata
  Drive     /drive/v3/about?fields=user/emailAddress -> email only

Even the metadata returned is THROWN AWAY -- the endpoint surfaces
only the status enum + an opaque reason string.
"""

from __future__ import annotations

from typing import Literal

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


GoogleReadinessProvider = Literal["gmail", "calendar", "drive"]
GoogleReadinessStatus = Literal[
    "connected",
    "expired",
    "insufficient_scope",
    "failed",
    "not_connected",
]


# Lightest-possible read endpoints per provider. Each returns a
# small JSON payload with no message bodies / file contents / event
# bodies. The readiness endpoint THROWS the payload away; only the
# HTTP status matters here.
_PROBE_URLS: dict[str, str] = {
    "gmail": "https://gmail.googleapis.com/gmail/v1/users/me/profile",
    "calendar": "https://www.googleapis.com/calendar/v3/calendars/primary",
    "drive": "https://www.googleapis.com/drive/v3/about?fields=user/emailAddress",
}


def _classify_response(
    *, status_code: int, body_text: str,
) -> GoogleReadinessStatus:
    """Map an HTTP status + body to a readiness enum.

    Logic:
      - 2xx                                       -> connected
      - 401                                       -> expired
      - 403 + body mentions scope / insufficient  -> insufficient_scope
      - 403 (other reason)                        -> failed
      - anything else                              -> failed
    """
    if 200 <= status_code < 300:
        return "connected"
    if status_code == 401:
        return "expired"
    if status_code == 403:
        lowered = (body_text or "").lower()
        if "scope" in lowered or "insufficient" in lowered:
            return "insufficient_scope"
        return "failed"
    return "failed"


async def probe_google_provider(
    *, provider: str, access_token: str, timeout: float = 8.0,
) -> dict[str, str]:
    """Run one probe. Returns ``{"provider", "status", "reason"}``.

    Never returns user data. ``reason`` is opaque -- the operator
    sees the status enum first; reason is for the operator's eyes
    only when debugging.
    """
    if provider not in _PROBE_URLS:
        return {
            "provider": provider,
            "status": "failed",
            "reason": f"unknown provider {provider!r}",
        }
    if not access_token:
        return {
            "provider": provider,
            "status": "not_connected",
            "reason": "no access_token on ConnectorInstance",
        }

    url = _PROBE_URLS[provider]
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        return {
            "provider": provider,
            "status": "failed",
            "reason": "timeout",
        }
    except httpx.RequestError as exc:
        return {
            "provider": provider,
            "status": "failed",
            "reason": f"network: {type(exc).__name__}",
        }

    status = _classify_response(
        status_code=resp.status_code, body_text=resp.text or "",
    )
    # Throw the payload away. The reason is the HTTP status code
    # only, never the body.
    reason = f"http {resp.status_code}"
    if status == "insufficient_scope":
        reason = "missing scope (re-authorize the connection)"
    elif status == "expired":
        reason = "access token expired or revoked (re-connect)"
    return {
        "provider": provider,
        "status": status,
        "reason": reason,
        "next_action": _next_action_for_status(status),
    }


# Sprint-20 PR-1 (2026-05-06): operator-facing one-liner per status,
# rendered next to the status pill. Never user data; pure mapping.
_NEXT_ACTIONS: dict[str, str] = {
    "connected": "Ready.",
    "expired": "Disconnect and reconnect this account.",
    "insufficient_scope": (
        "Reconnect and grant the missing scope on the consent screen."
    ),
    "failed": "Retry; if the failure persists, reconnect this account.",
    "not_connected": "Connect this account from the Apps panel.",
}


def _next_action_for_status(status: str) -> str:
    return _NEXT_ACTIONS.get(status, "Reconnect this account.")
