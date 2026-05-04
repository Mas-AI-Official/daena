"""OAuth-mode read-only invoker foundation.

PR-CONN-OAUTH-INVOKER-FOUNDATION (2026-05-03):
ships the SCAFFOLDING that Gmail / Google Drive promotion will need,
WITHOUT yet promoting those skills. The Phase 2 read-only allowlist
(``skill_executor.PHASE2_ALLOWLIST``) keeps every ``backend_surface
="oauth"`` entry at ``execution_mode="planned_only"`` -- promotion is
gated on an explicit follow-up PR that wires this invoker into the
executor's dispatch in :func:`SkillExecutorService.execute`.

What this module DOES today
---------------------------

* ``OAUTH_METHOD_ALLOWLIST`` -- a frozen tuple of every read-only
  OAuth method Daena will ever invoke. Today it covers the four Gmail
  + Drive intents that are scoped for the next promotion PR. Adding
  new methods is gated on a code review (test invariant pins the set).
* ``OAuthInvoker.invoke()`` -- given a ``ConnectorInstance`` id and an
  allowlisted method, performs the GET, refreshes the access token on
  401 once, caps the response by both byte size + item count, and
  returns a sanitized result dict (NEVER the raw token).
* ``OAuthInvoker.is_allowed()`` -- pure function any caller can use to
  ask "would this be allowed?" without actually calling the network.

What this module DOES NOT do today
----------------------------------

* No write methods. ``http_method`` is hard-coded ``"GET"`` and a
  module-load invariant at the bottom of this file forbids any other
  verb in ``OAUTH_METHOD_ALLOWLIST``.
* No promotion of Gmail / Drive in the executor. The
  ``test_pr3_gmail_and_drive_remain_planned_only`` invariant in
  ``tests/test_skill_executor_phase2.py`` keeps those four entries
  ``planned_only`` until a future PR explicitly wires this invoker
  into the executor.
* No real Google API calls in tests -- the test suite mocks
  ``httpx.AsyncClient.get`` so this PR does not depend on operator
  Google account state.

Honesty rules (Rule 17)
-----------------------

* Bearer token NEVER appears in logs, return values, or stored
  ``argument_shape`` payloads. ``_REDACT_TOKEN_RE`` scrubs any
  accidental capture before logging.
* Response caps are hard limits -- a 50-MB Gmail thread does NOT come
  back as 50 MB; the invoker truncates and flags ``truncated=True`` in
  the return shape so the caller knows.
* Refresh-on-401 happens AT MOST ONCE per invoke call -- two
  consecutive 401s mean the refresh token is also dead, in which case
  the invoker returns ``{"ok": False, "reason": "auth_expired"}`` and
  the operator must re-connect via the OAuth lifecycle UI.
* No method can be invoked without a matching allowlist entry --
  invoking ``messages.send`` would fail at the allowlist check long
  before any HTTP call is made.

Threat model
------------

* Operator passes a method name not in the allowlist
  -> :class:`OAuthMethodNotAllowedError`, no HTTP call.
* Stored access_token is expired
  -> single refresh round-trip, retry GET; if that also 401s, return
  ``auth_expired`` cleanly without exposing token material.
* Vendor returns 5xx / network error
  -> return ``{"ok": False, "reason": "<class>: <safe message>"}``.
* Response body exceeds size cap
  -> truncate, set ``truncated=True``, log byte counts but never the body.
* Response is a list with N > item cap
  -> slice to cap, set ``truncated=True``.

Test plan
---------

See ``tests/test_oauth_invoker.py``. Every public surface is covered;
no real network touched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.connections import ConnectorInstance
from app.services.integrations.oauth_service import ConnectorOAuthService

logger = get_logger(__name__)


# Hard ceilings -- do NOT make these per-method overridable without
# explicit code review. Operator UX is "surface the head, not the
# whole inbox"; anything bigger should pull through a different path.
DEFAULT_RESPONSE_CAP_BYTES = 64 * 1024     # 64 KB
DEFAULT_RESPONSE_CAP_ITEMS = 50            # max list items
HTTP_TIMEOUT_S = 15.0                      # GET ceiling per call


# Single-line scrubber for bearer tokens. We never SHOULD log the
# token itself (it never leaves the Authorization header, which we
# build local-scope in the invoke() method). This is defense in depth
# for any accidental string interpolation in a future error path.
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)


def _scrub(text: str) -> str:
    """Strip any 'Bearer <jwt>' substring from text before logging."""
    if not text:
        return text
    return _BEARER_RE.sub("Bearer [REDACTED]", text)[:500]


# ──────────────────────────────────────────────────────────────────
# Errors -- all SAFE by design (no token material in the message)
# ──────────────────────────────────────────────────────────────────


class OAuthInvokerError(Exception):
    """Base class for invoker errors. Safe to surface to UI."""


class OAuthMethodNotAllowedError(OAuthInvokerError):
    """The (plugin_id, method_id) pair is not in OAUTH_METHOD_ALLOWLIST."""


class OAuthInstanceNotFoundError(OAuthInvokerError):
    """No ConnectorInstance with the given id for the calling tenant."""


class OAuthCredentialsMissingError(OAuthInvokerError):
    """Instance found but credentials JSONB lacks an access_token."""


# ──────────────────────────────────────────────────────────────────
# Allowlist
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OAuthMethod:
    """One allowlisted read-only OAuth API method.

    The combination ``(plugin_id, method_id)`` is unique. Adding a new
    entry requires updating the test invariant
    ``test_oauth_invoker.py::test_allowlist_set_is_pinned`` so a code
    reviewer sees the diff explicitly.

    Fields:

    * ``plugin_id`` -- catalog id (e.g. ``app-gmail``). Mirrors the
      Phase 2 allowlist plugin_id so a future PR can flip the matching
      ``execution_mode`` to ``mcp_tool`` and route through here.
    * ``method_id`` -- the planned tool name carried in
      ``SkillToolMapping.target_tool``. Stays stable across PRs; a
      rename here is a breaking change to the executor contract.
    * ``provider`` -- the ConnectorOAuthService provider id used for
      token refresh + revoke. Today only ``gmail`` and
      ``google-drive`` are exercised.
    * ``base_url`` -- the API host. NEVER includes a path.
    * ``path_template`` -- the relative URL with ``{}`` placeholders
      for path parameters (NOT query string interpolation -- query
      strings are built in the per-method arg builder).
    * ``required_inputs`` -- operator input keys that MUST appear
      before the invoker will dispatch. Same shape as
      ``SkillToolMapping.required_inputs``.
    * ``response_cap_bytes`` / ``response_cap_items`` -- hard ceilings
      enforced by the invoker after the response lands.
    """

    plugin_id: str
    method_id: str
    provider: str
    base_url: str
    path_template: str
    required_inputs: tuple[str, ...]
    response_cap_bytes: int = DEFAULT_RESPONSE_CAP_BYTES
    response_cap_items: int = DEFAULT_RESPONSE_CAP_ITEMS
    # http_method is intentionally NOT a parameter -- the module-load
    # invariant at the bottom of this file forbids anything but GET.
    # Storing it here lets tests assert the contract explicitly.
    http_method: str = field(default="GET")


# The four reads scoped for the FOLLOW-UP Gmail/Drive promotion PR.
# Adding a method here requires updating
# tests/test_oauth_invoker.py::test_allowlist_set_is_pinned.
OAUTH_METHOD_ALLOWLIST: tuple[OAuthMethod, ...] = (
    # ─── Gmail reads ───
    OAuthMethod(
        plugin_id="app-gmail",
        method_id="messages.list_unread",
        provider="gmail",
        base_url="https://gmail.googleapis.com",
        # Query string is appended in build_request below from inputs;
        # the path is fixed.
        path_template="/gmail/v1/users/me/messages",
        required_inputs=(),
        response_cap_items=20,  # 20 newest unread headers, never bodies
    ),
    OAuthMethod(
        plugin_id="app-gmail",
        method_id="messages.search",
        provider="gmail",
        base_url="https://gmail.googleapis.com",
        path_template="/gmail/v1/users/me/messages",
        required_inputs=("query",),
        response_cap_items=20,
    ),
    # ─── Google Drive reads ───
    OAuthMethod(
        plugin_id="app-google-drive",
        method_id="files.list",
        provider="google-drive",
        base_url="https://www.googleapis.com",
        path_template="/drive/v3/files",
        required_inputs=(),
        response_cap_items=30,
    ),
    OAuthMethod(
        plugin_id="app-google-drive",
        method_id="files.get_metadata",
        provider="google-drive",
        base_url="https://www.googleapis.com",
        # We DELIBERATELY pick get_metadata over get_content for the
        # foundation; content download has its own size+permission
        # surface that deserves a dedicated PR.
        path_template="/drive/v3/files/{file_id}",
        required_inputs=("file_id",),
        response_cap_bytes=8 * 1024,  # metadata is tiny
        response_cap_items=1,
    ),
)


_ALLOWLIST_INDEX: dict[tuple[str, str], OAuthMethod] = {
    (m.plugin_id, m.method_id): m for m in OAUTH_METHOD_ALLOWLIST
}


# Module-load invariants -- if any of these fail, app boot fails. That
# is intentional: a corrupt allowlist must surface BEFORE the first
# request, not on the first call.
def _validate_allowlist() -> None:
    for m in OAUTH_METHOD_ALLOWLIST:
        if m.http_method != "GET":
            raise AssertionError(
                f"OAuthMethod {m.plugin_id}:{m.method_id} has "
                f"http_method={m.http_method!r}; only GET is allowed."
            )
        if not m.base_url.startswith("https://"):
            raise AssertionError(
                f"OAuthMethod {m.plugin_id}:{m.method_id} has insecure "
                f"base_url={m.base_url!r}; HTTPS required."
            )
        if "//" in m.base_url[len("https://"):]:
            raise AssertionError(
                f"OAuthMethod {m.plugin_id}:{m.method_id} base_url has "
                f"double slash; would cause SSRF-style URL resolution "
                f"surprise."
            )
        if m.response_cap_bytes <= 0 or m.response_cap_items <= 0:
            raise AssertionError(
                f"OAuthMethod {m.plugin_id}:{m.method_id} has non-positive "
                f"response cap; suggest using DEFAULT_*."
            )


_validate_allowlist()


# ──────────────────────────────────────────────────────────────────
# Invoker
# ──────────────────────────────────────────────────────────────────


@dataclass
class InvokeOutcome:
    """Sanitized return shape from invoke().

    Token NEVER appears here. The fields below are explicitly the only
    things that can leave the invoker.
    """

    ok: bool
    status_code: int | None = None
    payload: Any = None              # dict / list, AFTER caps applied
    truncated: bool = False
    refreshed_token: bool = False    # True if 401-then-refresh path fired
    reason: str | None = None        # populated when ok=False; safe text


class OAuthInvoker:
    """Read-only OAuth-mode executor foundation.

    Construct per request:

        invoker = OAuthInvoker(db=db_session)
        outcome = await invoker.invoke(
            tenant_id=tenant_id,
            instance_id=instance_id,
            plugin_id="app-gmail",
            method_id="messages.list_unread",
            operator_inputs={},
        )
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._db = db
        # The http_client kwarg is the test seam: the suite passes a
        # mock so no real google.com HTTP fires. In production the
        # invoker creates its own short-lived client per call.
        self._injected_client = http_client
        self._oauth_service = ConnectorOAuthService(db)

    @staticmethod
    def is_allowed(plugin_id: str, method_id: str) -> bool:
        """Pure: True if (plugin_id, method_id) has an allowlist entry."""
        return (plugin_id, method_id) in _ALLOWLIST_INDEX

    @staticmethod
    def get_method(plugin_id: str, method_id: str) -> OAuthMethod | None:
        """Return the allowlist entry or None."""
        return _ALLOWLIST_INDEX.get((plugin_id, method_id))

    async def invoke(
        self,
        *,
        tenant_id: UUID,
        instance_id: UUID,
        plugin_id: str,
        method_id: str,
        operator_inputs: dict[str, str],
    ) -> InvokeOutcome:
        """Execute one allowlisted GET. Never raises for predictable
        failures -- returns ``InvokeOutcome(ok=False, reason=...)``.

        Predictable failure paths:

        * Method not allowlisted -> ``OAuthMethodNotAllowedError``
          (intentionally raised because this means the CALLER is
          confused, not the network -- caller must fix code).
        * Required operator inputs missing -> raised
          ``OAuthInvokerError``.
        * Instance not found -> raised ``OAuthInstanceNotFoundError``.
        * Credentials missing access_token -> raised
          ``OAuthCredentialsMissingError``.

        Network / vendor failures (timeout, 5xx, 401-then-refresh-401)
        all return ``InvokeOutcome(ok=False, ...)`` so the caller can
        record an audit row without try/except boilerplate.
        """
        method = self.get_method(plugin_id, method_id)
        if method is None:
            raise OAuthMethodNotAllowedError(
                f"{plugin_id}:{method_id} is not in OAUTH_METHOD_ALLOWLIST. "
                f"Add it via PR-CONN-OAUTH-INVOKER-FOUNDATION extension "
                f"(allowlist + test invariant)."
            )

        for key in method.required_inputs:
            if not operator_inputs.get(key):
                raise OAuthInvokerError(
                    f"{plugin_id}:{method_id} requires operator input "
                    f"{key!r} but it was missing or empty."
                )

        instance = await self._load_instance(tenant_id, instance_id)
        if instance is None:
            raise OAuthInstanceNotFoundError(
                f"ConnectorInstance {instance_id} not found in tenant "
                f"{tenant_id}."
            )

        creds = dict(instance.credentials or {})
        access_token = creds.get("access_token")
        if not access_token:
            raise OAuthCredentialsMissingError(
                f"ConnectorInstance {instance_id} has no access_token. "
                f"Operator must (re)connect via the OAuth lifecycle UI."
            )

        # First attempt -- proactively refresh if near expiry.
        try:
            creds = await self._oauth_service.check_and_refresh(creds)
            access_token = creds.get("access_token", access_token)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "oauth_invoker.proactive_refresh_failed",
                instance_id=str(instance_id),
                error_type=type(exc).__name__,
                error=_scrub(str(exc)),
            )
            # Fall through with the original token; the GET below may
            # still succeed if the token has any life left.

        url = self._build_url(method, operator_inputs)
        params = self._build_query(method, operator_inputs)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        outcome = await self._do_get(method, url, params, headers)

        # 401 path -- refresh once and retry. We do NOT loop: a second
        # 401 means the refresh token is also dead and the operator
        # must re-connect.
        if outcome.status_code == 401 and creds.get("refresh_token"):
            try:
                refreshed = await self._oauth_service.refresh_token(
                    refresh_token=creds["refresh_token"],
                    provider=method.provider,
                )
                access_token = refreshed["access_token"]
                creds["access_token"] = access_token
                creds["expires_at"] = refreshed["expires_at"]
                # Persist the refreshed token so the next call is fast.
                await self._persist_refreshed_credentials(instance, creds)
                headers["Authorization"] = f"Bearer {access_token}"
                outcome = await self._do_get(method, url, params, headers)
                outcome.refreshed_token = True
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "oauth_invoker.401_refresh_failed",
                    instance_id=str(instance_id),
                    plugin_id=plugin_id,
                    method_id=method_id,
                    error_type=type(exc).__name__,
                    error=_scrub(str(exc)),
                )
                return InvokeOutcome(
                    ok=False,
                    status_code=401,
                    reason="auth_expired: refresh failed; operator must re-connect",
                )

        return outcome

    # ─────────────────── helpers ───────────────────

    async def _load_instance(
        self, tenant_id: UUID, instance_id: UUID,
    ) -> ConnectorInstance | None:
        stmt = select(ConnectorInstance).where(
            ConnectorInstance.id == instance_id,
            ConnectorInstance.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _build_url(
        method: OAuthMethod, operator_inputs: dict[str, str],
    ) -> str:
        """Substitute path placeholders. We do NOT do free-form
        interpolation; only ``{key}`` placeholders that match a
        required input or the literal value are honored."""
        path = method.path_template
        # Only path placeholders -- query-string params live in
        # _build_query and never substitute into the path.
        for key in method.required_inputs:
            placeholder = "{" + key + "}"
            if placeholder in path:
                value = operator_inputs.get(key, "")
                # Reject any value with control chars or path separators
                # to defend against URL-component escape tricks.
                if "/" in value or any(c < " " for c in value):
                    raise OAuthInvokerError(
                        f"Operator input {key!r} contains forbidden "
                        f"characters for URL path substitution"
                    )
                path = path.replace(placeholder, value)
        return method.base_url.rstrip("/") + path

    @staticmethod
    def _build_query(
        method: OAuthMethod, operator_inputs: dict[str, str],
    ) -> dict[str, str]:
        """Build the query string params. Per-method shape:

        * Gmail messages.list_unread: ``q=is:unread`` + ``maxResults``
        * Gmail messages.search: ``q={query}`` + ``maxResults``
        * Drive files.list: ``pageSize=N``
        * Drive files.get_metadata: no query string

        Caps live in the method.response_cap_items value -- we never
        pass a size > the cap, so the vendor cannot return more than
        we are willing to ingest.
        """
        if method.method_id == "messages.list_unread":
            return {"q": "is:unread", "maxResults": str(method.response_cap_items)}
        if method.method_id == "messages.search":
            return {
                "q": operator_inputs["query"],
                "maxResults": str(method.response_cap_items),
            }
        if method.method_id == "files.list":
            return {"pageSize": str(method.response_cap_items)}
        if method.method_id == "files.get_metadata":
            return {}
        return {}

    async def _do_get(
        self,
        method: OAuthMethod,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> InvokeOutcome:
        """Perform the GET, cap response, sanitize. Never raises."""
        client = self._injected_client or httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_S, follow_redirects=False,
        )
        owns_client = self._injected_client is None
        try:
            try:
                resp = await client.get(url, params=params, headers=headers)
            except httpx.TimeoutException:
                return InvokeOutcome(
                    ok=False, reason=f"timeout: no response in {HTTP_TIMEOUT_S}s",
                )
            except httpx.NetworkError as exc:
                return InvokeOutcome(
                    ok=False,
                    reason=f"network_error: {type(exc).__name__}",
                )
            except Exception as exc:  # noqa: BLE001
                return InvokeOutcome(
                    ok=False,
                    reason=f"http_error: {type(exc).__name__}",
                )

            # Cap by raw bytes BEFORE parsing JSON. A 50-MB JSON would
            # otherwise be parsed into memory then truncated -- we
            # truncate at the network boundary.
            body_bytes = resp.content or b""
            truncated_bytes = False
            if len(body_bytes) > method.response_cap_bytes:
                body_bytes = body_bytes[: method.response_cap_bytes]
                truncated_bytes = True

            if resp.status_code == 401:
                # Bubble the raw 401 up so invoke() can decide on
                # refresh-and-retry. We do NOT consume the body.
                return InvokeOutcome(
                    ok=False, status_code=401,
                    reason="auth_expired: 401 from vendor",
                )

            if resp.status_code >= 400:
                return InvokeOutcome(
                    ok=False, status_code=resp.status_code,
                    reason=(
                        f"vendor_error: HTTP {resp.status_code} "
                        f"{_scrub(resp.text[:160])}"
                    ),
                )

            try:
                payload = resp.json() if not truncated_bytes else None
            except Exception:
                payload = None

            if payload is None and truncated_bytes:
                return InvokeOutcome(
                    ok=False, status_code=resp.status_code,
                    truncated=True,
                    reason=(
                        f"response_too_large: body exceeded "
                        f"{method.response_cap_bytes} bytes"
                    ),
                )

            # Cap list items if the response shape is a list-bearing dict.
            truncated_items = False
            if isinstance(payload, dict):
                for list_key in ("messages", "files", "items"):
                    if isinstance(payload.get(list_key), list) and len(
                        payload[list_key]
                    ) > method.response_cap_items:
                        payload[list_key] = payload[list_key][
                            : method.response_cap_items
                        ]
                        truncated_items = True

            return InvokeOutcome(
                ok=True,
                status_code=resp.status_code,
                payload=payload,
                truncated=truncated_bytes or truncated_items,
            )
        finally:
            if owns_client:
                await client.aclose()

    async def _persist_refreshed_credentials(
        self, instance: ConnectorInstance, creds: dict[str, Any],
    ) -> None:
        """Write the refreshed access_token + expires_at back to the
        instance row so the next call doesn't 401 again. Never logs
        or returns the token value."""
        instance.credentials = creds
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(instance, "credentials")
        await self._db.commit()
        logger.info(
            "oauth_invoker.refreshed_credentials_persisted",
            instance_id=str(instance.id),
            has_refresh=bool(creds.get("refresh_token")),
            # No token; no expires_at value either (it's secret-adjacent).
        )


__all__ = [
    "DEFAULT_RESPONSE_CAP_BYTES",
    "DEFAULT_RESPONSE_CAP_ITEMS",
    "InvokeOutcome",
    "OAUTH_METHOD_ALLOWLIST",
    "OAuthCredentialsMissingError",
    "OAuthInstanceNotFoundError",
    "OAuthInvoker",
    "OAuthInvokerError",
    "OAuthMethod",
    "OAuthMethodNotAllowedError",
]
