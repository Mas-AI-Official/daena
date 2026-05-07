"""Connector Install API: unified install dialog for the Connections page.

This module provides the data + flow control behind the Codex-style
install dialog. One dialog, three auth flows under the hood:

  - ``oauth_managed``       Daena owns the OAuth client (existing flow,
                            Google / GitHub / Figma / Slack / Canva).
  - ``mcp_remote_oauth``    Remote MCP OAuth via provider metadata,
                            dynamic client registration, PKCE, local
                            callback, token exchange, and encrypted
                            token persistence. Falls back to token form
                            if the provider cannot complete discovery
                            or registration.
  - ``api_token``           User supplies a bearer token via a form
                            (HuggingFace, Vercel, Netlify, etc.).

Endpoints:
    GET  /connectors/catalog              -- enriched catalog for the dialog
    GET  /connectors/{slug}/install/info  -- single connector install card
    POST /connectors/{slug}/install/start -- begin install flow
    POST /connectors/{slug}/install/complete -- finalize api_token submit

The OAuth callback is reused from connector_oauth.py.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from html import escape
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlencode, urljoin
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.constants import ConnectorStatus
from app.core.logging import get_logger
from app.core.vault import encrypt_dict
from app.models.connections import Connector, ConnectorInstance

logger = get_logger(__name__)

router = APIRouter(prefix="/connectors", tags=["connector-install"])

# ---------------------------------------------------------------------------
# Catalog loading. Cached at module import time. The scrape script writes
# to this path; backend re-reads on next process boot. Honest persistence
# per ADR-001: no in-memory mutation that diverges from disk.
# ---------------------------------------------------------------------------

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "config" / "connector_catalog.json"
_MCP_OAUTH_STATES: dict[str, dict[str, Any]] = {}
_MCP_OAUTH_STATE_TTL_SECONDS = 600


def _load_catalog() -> dict[str, Any]:
    if not _CATALOG_PATH.exists():
        return {"version": "missing", "connectors": []}
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def _find_connector(slug: str) -> dict[str, Any] | None:
    catalog = _load_catalog()
    for c in catalog.get("connectors", []):
        if c.get("slug") == slug:
            return c
    return None


def _connector_fields_from_catalog(entry: dict[str, Any]) -> dict[str, Any]:
    """Project a rich catalog entry into the DB Connector schema."""
    return {
        "description": entry.get("description"),
        "auth_type": (entry.get("auth_type") or "none").strip(),
        "config_schema": entry.get("config_schema") or {},
        "tools": entry.get("tools") or [],
        "icon_url": entry.get("icon_url"),
        "category": entry.get("category"),
    }


def _auth_method(connector: dict[str, Any]) -> str:
    """Resolve install flow from v2 auth metadata with v1 auth_type fallback."""
    auth = connector.get("auth")
    if isinstance(auth, dict) and auth.get("method"):
        return str(auth["method"]).strip().lower()

    auth_type = str(connector.get("auth_type") or "").strip().lower()
    if auth_type in {"none", "no_auth", "no-auth"}:
        return "none"
    if auth_type in {"oauth", "oauth2", "oauth_managed"}:
        return "oauth_managed"
    if auth_type in {"api_key", "api-key", "token", "bearer_token", "bearer-token"}:
        return "api_token"
    return "api_token"


# ---------------------------------------------------------------------------
# Catalog endpoints
# ---------------------------------------------------------------------------


@router.get("/catalog")
async def get_catalog(
    user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Return the full enriched catalog for the Connections page."""
    return JSONResponse(content=_load_catalog())


@router.get("/{slug}/install/info")
async def install_info(
    slug: str,
    user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Return the dialog payload for a single connector."""
    connector = _find_connector(slug)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector '{slug}' not found")
    return JSONResponse(content=connector)


# ---------------------------------------------------------------------------
# Install start (per auth method)
# ---------------------------------------------------------------------------


class InstallStartRequest(BaseModel):
    redirect_after: str | None = None  # frontend URL to bounce back to


@router.post("/{slug}/install/start")
async def install_start(
    slug: str,
    body: InstallStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Initiate the install flow.

    Returns one of three shapes depending on the connector's
    ``auth.method``:

    - oauth_managed / mcp_remote_oauth:
        ``{"method": "...", "authorization_url": "...", "popup": True}``
    - api_token:
        ``{"method": "api_token", "form": {...}, "popup": False}``
    - none:
        ``{"method": "none", "popup": False, "connected": True}``
    """
    connector = _find_connector(slug)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector '{slug}' not found")

    method = _auth_method(connector)

    if method == "oauth_managed":
        return await _start_oauth_managed(slug, request, db, user)
    if method == "mcp_remote_oauth":
        return await _start_mcp_remote_oauth(slug, connector, request, db, user)
    if method == "api_token":
        return _start_api_token(slug, connector)
    if method == "none":
        return await _start_none(slug, connector, db, user)

    raise HTTPException(status_code=400, detail=f"Unknown auth method: {method}")


async def _start_oauth_managed(
    slug: str,
    request: Request,
    db: AsyncSession,
    user: CurrentUser,
) -> JSONResponse:
    """Delegate to the existing connector_oauth flow."""
    from app.services.integrations.oauth_service import (
        ConnectorOAuthService,
        OAuthConfigError,
    )
    from app.api.v1.connector_oauth import _oauth_states

    service = ConnectorOAuthService(db)
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/connectors/oauth/callback"

    try:
        auth_url, state = service.generate_auth_url(provider=slug, redirect_uri=redirect_uri)
    except OAuthConfigError as exc:
        connector = _find_connector(slug) or {}
        auth = connector.get("auth", {})
        if auth.get("token_settings_url") or auth.get("validate_endpoint"):
            return JSONResponse(content=_api_token_payload(
                slug,
                connector,
                help_override=(
                    f"Managed OAuth is not configured ({exc.missing_field}). "
                    "Using token fallback instead of pretending OAuth is ready."
                ),
            ))
        return JSONResponse(
            status_code=422,
            content={
                "method": "oauth_managed",
                "error_type": "oauth_not_configured",
                "missing_field": exc.missing_field,
                "help": "Set the required OAuth client_id / client_secret env vars and restart Daena.",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _oauth_states[state] = {
        "connector_id": slug,
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "redirect_uri": redirect_uri,
    }

    return JSONResponse(content={
        "method": "oauth_managed",
        "authorization_url": auth_url,
        "state": state,
        "popup": True,
    })


async def _start_mcp_remote_oauth(
    slug: str,
    connector: dict[str, Any],
    request: Request,
    db: AsyncSession,
    user: CurrentUser,
) -> JSONResponse:
    """Begin OAuth against a remote MCP server.

    This is the MCP Remote OAuth path used by providers like Cloudflare:
    discover OAuth metadata, dynamically register a localhost callback
    client, create PKCE parameters, return the provider authorization URL,
    and persist the callback state for the code exchange endpoint.
    """
    auth = connector.get("auth", {})
    mcp_url = auth.get("mcp_url") or next(
        iter(connector.get("mcp_servers", {}).values()), {}
    ).get("url", "")

    if not mcp_url:
        raise HTTPException(
            status_code=422,
            detail=f"Connector '{slug}' is missing mcp_url for mcp_remote_oauth.",
        )

    metadata = await _discover_mcp_oauth_metadata(mcp_url)
    if not metadata or not metadata.get("authorization_endpoint"):
        return _mcp_oauth_token_fallback(
            slug,
            connector,
            "MCP remote OAuth metadata was not discovered.",
        )
    if not metadata.get("token_endpoint"):
        return _mcp_oauth_token_fallback(
            slug,
            connector,
            "MCP remote OAuth metadata does not declare a token endpoint.",
        )
    if not metadata.get("registration_endpoint"):
        return _mcp_oauth_token_fallback(
            slug,
            connector,
            "MCP remote OAuth metadata does not declare dynamic client registration.",
        )

    protected_resource = await _discover_mcp_protected_resource(mcp_url)
    resource = (
        protected_resource.get("resource")
        if isinstance(protected_resource, dict)
        else None
    )
    redirect_uri = f"{str(request.base_url).rstrip('/')}/api/v1/connectors/mcp-oauth/callback"

    try:
        client_info = await _register_mcp_oauth_client(
            registration_endpoint=metadata["registration_endpoint"],
            redirect_uri=redirect_uri,
            connector=connector,
            scopes=auth.get("scopes"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "connector_install.mcp_oauth_registration_failed",
            slug=slug,
            mcp_url=mcp_url,
            error=str(exc),
        )
        return _mcp_oauth_token_fallback(
            slug,
            connector,
            f"MCP remote OAuth registration failed: {exc}",
        )

    code_verifier, code_challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    expires_at = time.time() + _MCP_OAUTH_STATE_TTL_SECONDS
    _MCP_OAUTH_STATES[state] = {
        "slug": slug,
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "mcp_url": mcp_url,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "client_info": client_info,
        "token_endpoint": metadata["token_endpoint"],
        "resource": resource,
        "expires_at": expires_at,
    }

    auth_params = {
        "response_type": "code",
        "client_id": client_info["client_id"],
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    scope = _scope_string(auth.get("scopes")) or client_info.get("scope")
    if scope:
        auth_params["scope"] = scope
    if resource:
        auth_params["resource"] = resource

    authorization_url = f"{metadata['authorization_endpoint']}?{urlencode(auth_params)}"
    logger.info(
        "connector_install.mcp_oauth_started",
        slug=slug,
        mcp_url=mcp_url,
        redirect_uri=redirect_uri,
        has_resource=bool(resource),
    )
    return JSONResponse(content={
        "method": "mcp_remote_oauth",
        "authorization_url": authorization_url,
        "state": state,
        "popup": True,
    })


async def _discover_mcp_oauth_metadata(mcp_url: str) -> dict[str, Any] | None:
    """Probe an MCP server for OAuth metadata.

    Modern MCP servers expose an OAuth 2.0 metadata document at
    ``/.well-known/oauth-authorization-server``. We try that path first.
    If it fails we return None and the caller falls back to api_token.
    """
    try:
        from urllib.parse import urljoin

        well_known = urljoin(mcp_url, "/.well-known/oauth-authorization-server")
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(well_known)
            if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
                return resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("connector_install.mcp_metadata_probe_failed", error=str(exc), url=mcp_url)
    return None


async def _discover_mcp_protected_resource(mcp_url: str) -> dict[str, Any] | None:
    """Read MCP protected resource metadata when the server exposes it."""
    try:
        well_known = urljoin(mcp_url, "/.well-known/oauth-protected-resource")
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(well_known)
            if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
                return resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("connector_install.mcp_prm_probe_failed", error=str(exc), url=mcp_url)
    return None


async def _register_mcp_oauth_client(
    *,
    registration_endpoint: str,
    redirect_uri: str,
    connector: dict[str, Any],
    scopes: Any,
) -> dict[str, Any]:
    """Register Daena as a dynamic OAuth client for a remote MCP server."""
    iface = connector.get("interface", {})
    payload: dict[str, Any] = {
        "client_name": f"Daena - {iface.get('displayName') or connector.get('name') or connector.get('slug')}",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    scope = _scope_string(scopes)
    if scope:
        payload["scope"] = scope
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            registration_endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"registration returned {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if not data.get("client_id"):
            raise RuntimeError("registration response did not include client_id")
        return data


def _scope_string(scopes: Any) -> str:
    if not scopes:
        return ""
    if isinstance(scopes, str):
        return scopes
    if isinstance(scopes, list):
        return " ".join(str(s) for s in scopes if s)
    return str(scopes)


def _generate_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(96)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def _mcp_oauth_token_fallback(
    slug: str,
    connector: dict[str, Any],
    reason: str,
) -> JSONResponse:
    fallback_reason = f"{reason} Using token fallback instead of pretending OAuth is connected."
    logger.info(
        "connector_install.mcp_oauth_using_token_fallback",
        slug=slug,
        reason=reason,
    )
    auth = connector.get("auth", {})
    return JSONResponse(content={
        "method": "api_token",
        "form": {
            "help": fallback_reason,
            "fields": [
                {
                    "key": "bearer_token",
                    "label": "Bearer token",
                    "type": "password",
                    "help": auth.get("token_help") or "Paste a bearer token from the provider dashboard.",
                },
            ],
            "settings_url": auth.get("token_settings_url"),
        },
        "popup": False,
        "fallback_reason": fallback_reason,
    })


@router.get("/mcp-oauth/callback")
async def mcp_oauth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Handle remote MCP OAuth provider redirects and persist tokens."""
    if not state:
        return _mcp_oauth_html(
            slug="unknown",
            success=False,
            message="Missing OAuth state. Start the connector install again.",
            status_code=400,
        )

    pending = _MCP_OAUTH_STATES.pop(state, None)
    if not pending:
        return _mcp_oauth_html(
            slug="unknown",
            success=False,
            message="Invalid or expired OAuth state. Start the connector install again.",
            status_code=400,
        )

    slug = pending["slug"]
    if time.time() > float(pending.get("expires_at", 0)):
        return _mcp_oauth_html(
            slug=slug,
            success=False,
            message="OAuth state expired. Start the connector install again.",
            status_code=400,
        )
    if error:
        message = error_description or error
        return _mcp_oauth_html(
            slug=slug,
            success=False,
            message=f"Provider rejected the OAuth request: {message}",
            status_code=400,
        )
    if not code:
        return _mcp_oauth_html(
            slug=slug,
            success=False,
            message="Provider did not return an authorization code.",
            status_code=400,
        )

    try:
        token_payload = await _exchange_mcp_oauth_code(code=code, pending=pending)
        credentials = {
            **token_payload,
            "provider": slug,
            "auth_method": "mcp_remote_oauth",
            "mcp_url": pending["mcp_url"],
            "client_info": pending["client_info"],
            "connected_at": int(time.time()),
        }
        user_ref = SimpleNamespace(
            id=UUID(pending["user_id"]),
            tenant_id=UUID(pending["tenant_id"]),
        )
        await _ensure_instance(slug, credentials, db, user_ref)
        logger.info(
            "connector_install.mcp_oauth_connected",
            slug=slug,
            mcp_url=pending["mcp_url"],
        )
        return _mcp_oauth_html(
            slug=slug,
            success=True,
            message=f"{slug.replace('-', ' ').title()} OAuth tokens saved.",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "connector_install.mcp_oauth_callback_failed",
            slug=slug,
            error=str(exc),
        )
        return _mcp_oauth_html(
            slug=slug,
            success=False,
            message=f"Token exchange failed: {exc}",
            status_code=500,
        )


async def _exchange_mcp_oauth_code(
    *,
    code: str,
    pending: dict[str, Any],
) -> dict[str, Any]:
    """Exchange a remote MCP OAuth code for provider tokens."""
    client_info = pending["client_info"]
    token_data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": pending["redirect_uri"],
        "client_id": client_info["client_id"],
        "code_verifier": pending["code_verifier"],
    }
    if pending.get("resource"):
        token_data["resource"] = str(pending["resource"])

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    auth_method = client_info.get("token_endpoint_auth_method", "none")
    client_secret = client_info.get("client_secret")
    if auth_method == "client_secret_post" and client_secret:
        token_data["client_secret"] = client_secret
    elif auth_method == "client_secret_basic" and client_secret:
        raw = f"{client_info['client_id']}:{client_secret}".encode("utf-8")
        headers["Authorization"] = f"Basic {base64.b64encode(raw).decode('ascii')}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            pending["token_endpoint"],
            data=token_data,
            headers=headers,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"{resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        if not data.get("access_token"):
            raise RuntimeError("token response did not include access_token")
        return data


def _mcp_oauth_html(
    *,
    slug: str,
    success: bool,
    message: str,
    status_code: int = 200,
) -> HTMLResponse:
    """Return popup HTML that reports MCP OAuth result to the opener."""
    msg = escape(message)
    color = "#2DD4BF" if success else "#ff6b6b"
    title = "Connected" if success else "Connection Failed"
    payload = {
        "type": "oauth_success" if success else "oauth_error",
        "connector": slug,
    }
    if not success:
        payload["error"] = message
    script_payload = json.dumps(payload)
    close_script = "setTimeout(() => window.close(), 2000);" if success else ""
    return HTMLResponse(
        content=f"""
        <html>
        <head><title>Daena - MCP OAuth</title></head>
        <body style="background:#0F1419;color:{color};font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="text-align:center;max-width:640px;padding:24px;">
                <h2>{title}</h2>
                <p>{msg}</p>
                <p style="color:#9CA3AF;">You can close this window.</p>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({script_payload}, '*');
                        {close_script}
                    }}
                </script>
            </div>
        </body>
        </html>
        """,
        status_code=status_code,
    )


def _start_api_token(slug: str, connector: dict[str, Any]) -> JSONResponse:
    """Return a form spec for the dialog to render."""
    return JSONResponse(content=_api_token_payload(slug, connector))


def _api_token_payload(
    slug: str,
    connector: dict[str, Any],
    help_override: str | None = None,
) -> dict[str, Any]:
    """Build a token-form response for a connector."""
    auth = connector.get("auth", {})
    iface = connector.get("interface", {})

    # Cloudinary, Stripe, etc. may need multiple fields. Honor the
    # field_layout list when present.
    layout = auth.get("field_layout", ["bearer_token"])
    fields = []
    for key in layout:
        fields.append({
            "key": key,
            "label": _humanize_field_key(key),
            "type": "password" if "secret" in key or "token" in key or "key" in key else "text",
            "required": True,
        })

    return {
        "method": "api_token",
        "form": {
            "fields": fields,
            "settings_url": auth.get("token_settings_url"),
            "help": help_override
            or auth.get("token_help")
            or f"Paste a {iface.get('displayName', slug)} API token.",
        },
        "popup": False,
    }


def _humanize_field_key(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").title()


async def _start_none(
    slug: str,
    connector: dict[str, Any],
    db: AsyncSession,
    user: CurrentUser,
) -> JSONResponse:
    """No-auth catalog rows are skills, not app connections.

    Older code marked these as CONNECTED immediately, which produced
    fake installs for entries like "Build macOS Apps" on a Windows
    runtime. Keep this backend-side guard even though the UI now hides
    the button.
    """
    raise HTTPException(
        status_code=409,
        detail=(
            "This catalog row is a skill pack only. It has no OAuth flow, "
            "token setup, MCP server, or callable Daena backend adapter."
        ),
    )


# ---------------------------------------------------------------------------
# Install complete (api_token path)
# ---------------------------------------------------------------------------


class InstallCompleteRequest(BaseModel):
    credentials: dict[str, str]


@router.post("/{slug}/install/complete")
async def install_complete(
    slug: str,
    body: InstallCompleteRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Finalize an api_token install.

    The frontend POSTs the user-entered credentials. We validate them
    against the provider's known endpoint when a validate_endpoint is
    declared, then encrypt and persist.
    """
    connector = _find_connector(slug)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector '{slug}' not found")

    auth = connector.get("auth", {})

    # Optional validation against the provider.
    validate_url = auth.get("validate_endpoint")
    if validate_url and body.credentials.get("bearer_token"):
        ok, account_identity = await _validate_token(
            validate_url, body.credentials["bearer_token"], slug,
        )
        if not ok:
            raise HTTPException(status_code=401, detail="Token rejected by provider")
        # Stash the account identity for the UI banner ("Connected as X").
        if account_identity:
            body.credentials = {**body.credentials, "account_identity": account_identity}

    instance = await _ensure_instance(slug, body.credentials, db, user)
    if not instance:
        raise HTTPException(status_code=500, detail="Failed to persist connector")

    return JSONResponse(content={
        "status": "connected",
        "instance_id": str(instance.id),
        "account_identity": body.credentials.get("account_identity"),
    })


async def _validate_token(
    url: str, token: str, slug: str,
) -> tuple[bool, str | None]:
    """Hit the provider's read-only endpoint to confirm the token works."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code >= 400:
                return False, None
            data = resp.json() if "json" in resp.headers.get("content-type", "") else {}
            # Best-effort identity extraction. Provider-specific keys.
            identity = (
                data.get("email")
                or data.get("login")
                or data.get("username")
                or data.get("name")
                or data.get("user", {}).get("email")
            )
            return True, identity
    except Exception as exc:  # noqa: BLE001
        logger.warning("connector_install.token_validate_failed", slug=slug, error=str(exc))
        return False, None


async def _ensure_instance(
    slug: str,
    credentials: dict[str, Any],
    db: AsyncSession,
    user: CurrentUser,
) -> ConnectorInstance | None:
    """Find or create the ConnectorInstance for this user + slug.

    The Connector model is keyed by ``name`` (not slug), so we resolve
    slug -> name through the catalog first.
    """
    catalog_entry = _find_connector(slug)
    if not catalog_entry:
        logger.error("connector_install.catalog_entry_missing", slug=slug)
        return None
    connector_name = catalog_entry["name"]

    connector_row = (
        await db.execute(
            select(Connector).where(Connector.name == connector_name)
        )
    ).scalar_one_or_none()
    if not connector_row:
        connector_row = Connector(
            name=connector_name,
            **_connector_fields_from_catalog(catalog_entry),
        )
        db.add(connector_row)
        await db.flush()
        logger.info(
            "connector_install.connector_row_created_from_catalog",
            slug=slug,
            name=connector_name,
        )

    encrypted = encrypt_dict(credentials) if credentials else None

    existing = (
        await db.execute(
            select(ConnectorInstance).where(
                ConnectorInstance.connector_id == connector_row.id,
                ConnectorInstance.tenant_id == user.tenant_id,
                ConnectorInstance.user_id == user.id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.credentials = encrypted
        existing.status = ConnectorStatus.CONNECTED.value
        await db.commit()
        return existing

    instance = ConnectorInstance(
        connector_id=connector_row.id,
        tenant_id=user.tenant_id,
        user_id=user.id,
        credentials=encrypted,
        status=ConnectorStatus.CONNECTED.value,
    )
    db.add(instance)
    await db.commit()
    return instance
