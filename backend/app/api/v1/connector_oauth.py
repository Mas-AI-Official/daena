"""Connector OAuth API: multi-provider authorization flow.

Supports: Google (Gmail, Calendar, Drive), GitHub, Figma, Slack, Canva.

Endpoints:
    GET  /connectors/{connector_id}/oauth/authorize  -- Get consent URL
    GET  /connectors/oauth/callback                  -- Handle provider redirect
    POST /connectors/{instance_id}/oauth/refresh      -- Manual token refresh
    GET  /connectors/oauth/providers                  -- List supported providers
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.logging import get_logger
from app.services.integrations.oauth_service import (
    ConnectorOAuthService,
    OAuthConfigError,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/connectors", tags=["connector-oauth"])

# In-memory state store (production: use Redis or DB)
_oauth_states: dict[str, dict] = {}

_PROVIDER_TO_CONNECTOR_NAME = {
    "gmail": "Gmail",
    "google-calendar": "Google Calendar",
    "google-drive": "Google Drive",
    "github": "GitHub",
    "figma": "Figma",
    "slack": "Slack",
    "canva": "Canva",
}


def _normalize_owner_email(identity: str | None) -> str | None:
    """Normalize a fetched account identity for storage in
    ``ConnectorInstance.owner_email``.

    PR-CONN-GOOGLE-ACCOUNT-PROFILES-CAPTURE (Sprint-5 PR-1, 2026-05-03):
    Sprint-4 PR-3 added the column but left it null. This Sprint-5 PR
    auto-populates it from the provider's userinfo endpoint after
    successful token exchange so the operator never has to
    hand-pick which Google account a ConnectorInstance maps to.

    Rules (all enforced by tests):
      * Lowercased + whitespace-stripped (case-insensitive matching).
      * 254-char cap (RFC 5321 SMTP local+domain limit) -- column is
        ``String(254)`` so over-long values would otherwise raise on
        insert. We truncate defensively rather than crash the OAuth
        callback over a provider returning a weird payload.
      * Empty / whitespace-only / falsy -> ``None`` so SQL NULL
        semantics still let multi-NULL rows coexist (matches the
        Sprint-4 PR-3 test pin).
      * NEVER returns the access token, refresh token, or any
        substring that smells token-shaped. The function only sees
        the identity string fetched by ``fetch_account_identity``,
        which is provider userinfo response (email / handle), not
        token material -- defense-in-depth for the executor's audit
        layer.
    """
    if not identity:
        return None
    normalized = identity.strip().lower()
    if not normalized:
        return None
    return normalized[:254]


@router.get("/oauth/providers")
async def list_providers(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """List all supported OAuth providers and their configuration status."""
    service = ConnectorOAuthService(db)
    return JSONResponse(content={"data": service.get_supported_providers()})


@router.get("/{connector_id}/oauth/authorize")
async def authorize(
    connector_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Generate OAuth consent URL for a connector.

    Returns the URL the frontend should redirect/open for the user
    to grant access to the service.
    """
    service = ConnectorOAuthService(db)

    # Build redirect URI (callback endpoint on this server)
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/connectors/oauth/callback"

    try:
        auth_url, state = service.generate_auth_url(
            provider=connector_id,
            redirect_uri=redirect_uri,
        )
    except OAuthConfigError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": str(exc),
                "error_type": "oauth_not_configured",
                "provider": exc.provider,
                "missing_field": exc.missing_field,
                "help": (
                    "Set the required environment variable in your .env file or "
                    "Cloud Run secrets. See Settings > Developer for details."
                ),
            },
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )

    # Store state for validation on callback
    _oauth_states[state] = {
        "connector_id": connector_id,
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "redirect_uri": redirect_uri,
    }

    return JSONResponse(content={
        "authorization_url": auth_url,
        "state": state,
    })


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Handle OAuth callback from any provider.

    Provider redirects here after the user grants consent.
    Exchanges the auth code for tokens and stores them.
    Returns an HTML page that communicates success/failure to the opener window.
    """
    # Validate state
    state_data = _oauth_states.pop(state, None)
    if not state_data:
        return HTMLResponse(
            content="<html><body><h2>OAuth Error</h2><p>Invalid or expired state. Please try again.</p></body></html>",
            status_code=400,
        )

    connector_id = state_data["connector_id"]
    user_id = UUID(state_data["user_id"])
    tenant_id = UUID(state_data["tenant_id"])
    redirect_uri = state_data["redirect_uri"]

    service = ConnectorOAuthService(db)

    try:
        # Exchange code for tokens (pass provider for endpoint resolution)
        tokens = await service.exchange_code(code, redirect_uri, provider=connector_id)

        # Session 11: fetch the identity (email / handle) of the account
        # the user JUST picked on the provider's consent screen. Stored
        # alongside tokens in credentials JSONB so the UI can display
        # "Connected as masoud.masoori@mas-ai.co" instead of opaque
        # "Connected". Fire-and-forget: if userinfo fails we still save
        # the connection since OAuth itself succeeded.
        access_token = tokens.get("access_token", "")
        account_identity = ""
        if access_token:
            try:
                account_identity = await service.fetch_account_identity(
                    access_token, provider=connector_id,
                )
            except Exception as exc:
                logger.warning(
                    "connector_oauth.identity_fetch_swallowed",
                    error=str(exc), connector_id=connector_id,
                )
        if account_identity:
            tokens = {**tokens, "account_identity": account_identity}

        # PR-CONN-GOOGLE-ACCOUNT-PROFILES-CAPTURE (Sprint-5 PR-1):
        # normalize the fetched identity for the indexed top-level
        # column. None -> column stays NULL, account picker UI must
        # fall back to manual selection (covered by Sprint-4 PR-3
        # _find_oauth_instance ambiguity gate).
        normalized_owner_email = _normalize_owner_email(account_identity)

        # Find or create the catalog-backed connector instance.
        #
        # Previous code compared ConnectorInstance.connector_id (UUID)
        # directly to the provider slug string ("google-drive") and then
        # tried to create fields that do not exist on ConnectorInstance.
        # That meant OAuth could succeed at the provider and still not
        # wire Daena's installed connector. Resolve provider slug ->
        # Connector row first, then promote the user's instance.
        from sqlalchemy import select
        from app.core.constants import ConnectorStatus
        from app.core.vault import encrypt_dict
        from app.models.connections import Connector, ConnectorInstance

        connector_name = _PROVIDER_TO_CONNECTOR_NAME.get(
            connector_id,
            connector_id.replace("-", " ").title(),
        )
        connector = (
            await db.execute(select(Connector).where(Connector.name == connector_name))
        ).scalar_one_or_none()
        if connector is None:
            raise ValueError(f"Connector catalog row not found for OAuth provider: {connector_id}")

        # PR-CONN-GOOGLE-ACCOUNT-PROFILES-CAPTURE (Sprint-5 PR-1):
        # match on (tenant, connector, user, owner_email) so two
        # Google accounts under the same operator user get separate
        # rows. The Sprint-4 PR-3 unique constraint already permits
        # this; the lookup must mirror it or we'd UPDATE the wrong
        # row when the operator adds a second account.
        stmt = select(ConnectorInstance).where(
            ConnectorInstance.connector_id == connector.id,
            ConnectorInstance.tenant_id == tenant_id,
            ConnectorInstance.user_id == user_id,
            ConnectorInstance.owner_email == normalized_owner_email,
        )
        result = await db.execute(stmt)
        instance = result.scalar_one_or_none()
        encrypted_tokens = encrypt_dict(tokens)

        if instance:
            instance.credentials = encrypted_tokens
            instance.status = ConnectorStatus.CONNECTED.value
            await db.commit()
        else:
            instance = ConnectorInstance(
                connector_id=connector.id,
                tenant_id=tenant_id,
                user_id=user_id,
                credentials=encrypted_tokens,
                status=ConnectorStatus.CONNECTED.value,
                owner_email=normalized_owner_email,
            )
            db.add(instance)
            await db.commit()

        logger.info(
            "connector_oauth.connected",
            connector_id=connector_id,
            user_id=str(user_id),
            account_identity=account_identity or "(not fetched)",
        )

        # PR-CONN-OAUTH-CONNECT (2026-05-02): when this callback was
        # initiated from the V2 marketplace start endpoint, ALSO import
        # a V2 oauth_app row so the Plugins grid surface reflects the
        # new connection without waiting for the next discovery refresh.
        # The V2 row carries vault_ref = str(instance.id) so the
        # OAuthAppProbe can dereference back to THIS encrypted blob --
        # never duplicates token storage.
        if state_data.get("_v2_marketplace"):
            try:
                from app.services.connection_v2.oauth_marketplace import (
                    import_v2_row_after_callback,
                )
                await import_v2_row_after_callback(
                    db=db,
                    tenant_id=tenant_id,
                    provider=connector_id,
                    connector_instance_id=instance.id,
                    account_identity=account_identity,
                )
            except Exception as v2_exc:  # noqa: BLE001 -- callback success > V2 nicety
                logger.warning(
                    "connector_oauth.v2_marketplace_import_failed",
                    error=str(v2_exc),
                    connector_id=connector_id,
                )

        # Display name for the success page
        display_name = connector_id.replace("-", " ").title()

        # Return HTML that communicates success to the opener window
        return HTMLResponse(content=f"""
        <html>
        <head><title>Daena - Connected</title></head>
        <body style="background:#0F1419;color:#D4A843;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="text-align:center;">
                <h2>Connected to {display_name}</h2>
                <p style="color:#2DD4BF;">OAuth tokens saved. You can close this window.</p>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{type: 'oauth_success', connector: '{connector_id}'}}, '*');
                        setTimeout(() => window.close(), 2000);
                    }}
                </script>
            </div>
        </body>
        </html>
        """)

    except Exception as exc:
        logger.error("connector_oauth.callback_failed", error=str(exc), connector=connector_id)
        safe_error = str(exc).replace("'", "\\'").replace('"', '\\"')
        return HTMLResponse(
            content=f"""
            <html>
            <body style="background:#0F1419;color:#ff6b6b;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="text-align:center;">
                    <h2>Connection Failed</h2>
                    <p>{safe_error}</p>
                    <p style="color:#999;">Please close this window and try again.</p>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{type: 'oauth_error', connector: '{connector_id}', error: '{safe_error}'}}, '*');
                        }}
                    </script>
                </div>
            </body>
            </html>
            """,
            status_code=500,
        )


@router.post("/{instance_id}/oauth/refresh")
async def refresh_tokens(
    instance_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Manually refresh OAuth tokens for a connector instance."""
    from sqlalchemy import select
    from app.models.connections import ConnectorInstance

    stmt = select(ConnectorInstance).where(
        ConnectorInstance.id == instance_id,
        ConnectorInstance.tenant_id == user.tenant_id,
    )
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()

    if not instance:
        return JSONResponse(status_code=404, content={"error": "Instance not found"})

    from app.core.vault import decrypt_dict, encrypt_dict

    credentials = instance.credentials or {}
    if isinstance(credentials, str):
        credentials = decrypt_dict(credentials)
    refresh_tok = credentials.get("refresh_token")
    provider = credentials.get("provider", "gmail")

    if not refresh_tok:
        return JSONResponse(status_code=400, content={"error": "No refresh token available"})

    service = ConnectorOAuthService(db)
    try:
        new_tokens = await service.refresh_token(refresh_tok, provider=provider)
        credentials["access_token"] = new_tokens["access_token"]
        credentials["expires_at"] = new_tokens["expires_at"]
        instance.credentials = encrypt_dict(credentials)
        await db.commit()

        return JSONResponse(content={
            "status": "refreshed",
            "expires_at": new_tokens["expires_at"],
        })
    except Exception as exc:
        # Mark as expired if refresh fails
        from app.core.constants import ConnectorStatus

        instance.status = ConnectorStatus.NEEDS_REAUTH.value
        await db.commit()
        return JSONResponse(status_code=500, content={"error": str(exc)})
