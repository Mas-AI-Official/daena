"""Account-scoped OAuth client config management.

PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS (2026-05-03): the operator pastes
OAuth client_id + client_secret for a provider (Google / GitHub / Slack /
Figma / Canva) into the Account page. This persists via
``oauth_client_config_store`` (which writes through to the underlying
``oauth_credentials_store`` that ``oauth_service`` already reads).

Honesty rules (project Rule 17):
  * GET endpoints NEVER return secret values. Shape: ``{configured:
    bool, client_id_present: bool, last_updated: iso8601, ...display}``.
  * POST validates slug allowlist BEFORE touching the store.
  * DELETE clears BOTH client_id and client_secret atomically.
  * No endpoint logs the values, only their lengths.

Effect chain (per founder rule 1):
  Operator types client_id + client_secret in /account#oauth-clients
   -> POST /account/oauth-clients/{slug}
   -> oauth_client_config_store.set_client_config
   -> oauth_credentials_store.set_overrides (atomic write of both fields)
   -> response carries display-safe metadata only
   -> frontend dispatches daena:retry-pending
   -> useMarketplace re-fetches cards
   -> OAuth-backed card flips Configure -> Connect (no token yet)

This PR does NOT start the OAuth flow automatically. The operator
clicks Connect on the card next, which opens OAuthConnectDrawer and
hits the existing /api/v1/connections/v2/marketplace/oauth/start
endpoint. Two-step UX so a wrong client_id doesn't open a popup
that immediately errors.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_role
from app.core.logging import get_logger
from app.services.integrations.oauth_client_config_store import (
    PROVIDER_DISPLAY,
    clear_client_config,
    get_metadata,
    list_provider_status,
    set_client_config,
)

logger = get_logger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────────────────────────
# Request / response schemas (display-safe; no secret echo)
# ──────────────────────────────────────────────────────────────────


class SaveClientConfigRequest(BaseModel):
    """Body for POST /account/oauth-clients/{slug}.

    Both fields are required. Empty values are refused -- partial
    saves are useless because OAuth start needs both.
    """

    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)


class OAuthClientStatus(BaseModel):
    """Display-safe status row. Never carries the values."""

    slug: str
    display_name: str
    client_id_field: str
    client_secret_field: str
    provider_ids: list[str]
    console_url: str
    client_id_hint: str
    configured: bool
    client_id_present: bool
    last_updated: str  # iso8601 or ""


class SaveClientConfigResponse(BaseModel):
    """Post-save metadata. Never carries the values."""

    success: bool
    slug: str
    configured: bool
    client_id_present: bool
    last_updated: str


# ──────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────


@router.get("", response_model=list[OAuthClientStatus])
async def list_oauth_clients(
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> list[dict[str, object]]:
    """List every supported OAuth provider with display-safe configured
    state. NEVER returns client_id or client_secret values.

    Use this to render the Account page OAuth Clients section.
    """
    return list_provider_status()


@router.post("/{slug}", response_model=SaveClientConfigResponse)
async def save_oauth_client(
    slug: str,
    body: SaveClientConfigRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> SaveClientConfigResponse:
    """Save an OAuth client_id + client_secret for ``slug``.

    Flow:
      1. Validate slug against PROVIDER_DISPLAY allowlist.
      2. Persist via oauth_client_config_store (atomic bulk write).
      3. Return display-safe metadata so the frontend can flip the
         marketplace card without a refetch.

    The raw values are NEVER persisted to logs (length only) and
    NEVER echoed back in the response.
    """
    if slug not in PROVIDER_DISPLAY:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown OAuth provider slug {slug!r}",
        )

    try:
        meta = await set_client_config(
            slug=slug,
            client_id=body.client_id,
            client_secret=body.client_secret,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    logger.info(
        "account_oauth_clients.saved",
        slug=slug,
        # NEVER log the values or any prefix of them.
    )

    return SaveClientConfigResponse(
        success=True,
        slug=slug,
        configured=bool(meta.get("configured", False)),
        client_id_present=bool(meta.get("client_id_present", False)),
        last_updated=str(meta.get("last_updated", "")),
    )


@router.delete("/{slug}")
async def delete_oauth_client(
    slug: str,
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """Clear an OAuth client config for ``slug``.

    After this call:
      * configured is False, client_id_present is False
      * Marketplace cards for the slug's provider_ids flip back to
        Configure (the OAuthConnectDrawer Connect path will return
        configure_required from the start endpoint).
      * Existing OAuth tokens in ConnectorInstance.credentials are
        UNTOUCHED -- they still work until they expire / are refreshed.
        This preserves operator agency: clearing the client config is
        an "I want to rotate the OAuth app" operation, not a
        "disconnect everyone" operation.
    """
    if slug not in PROVIDER_DISPLAY:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown OAuth provider slug {slug!r}",
        )

    removed_any = await clear_client_config(slug)

    logger.info(
        "account_oauth_clients.cleared",
        slug=slug,
        removed_any=removed_any,
    )

    meta = get_metadata(slug)
    return {
        "success": True,
        "slug": slug,
        "removed_any": removed_any,
        "configured": bool(meta.get("configured", False)),
        "client_id_present": bool(meta.get("client_id_present", False)),
    }
