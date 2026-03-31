"""Connector OAuth API: authorization flow for Gmail, Calendar, etc.

Endpoints:
    GET  /connectors/{connector_id}/oauth/authorize  -- Get consent URL
    GET  /connectors/oauth/callback                  -- Handle Google redirect
    POST /connectors/{instance_id}/oauth/refresh      -- Manual token refresh
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.services.integrations.oauth_service import ConnectorOAuthService

logger = get_logger(__name__)

router = APIRouter(prefix="/connectors", tags=["connector-oauth"])

# In-memory state store (production: use Redis or DB)
_oauth_states: dict[str, dict] = {}


@router.get("/{connector_id}/oauth/authorize")
async def authorize(
    connector_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Generate OAuth consent URL for a connector.

    Returns the URL the frontend should redirect/open for the user
    to grant access to Gmail, Calendar, etc.
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
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )

    # Store state for validation on callback
    _oauth_states[state] = {
        "connector_id": connector_id,
        "user_id": str(user["id"]),
        "tenant_id": str(user["tenant_id"]),
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
    """Handle OAuth callback from Google.

    Google redirects here after the user grants consent.
    Exchanges the auth code for tokens and stores them.
    Returns an HTML page that closes the popup/tab.
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
        # Exchange code for tokens
        tokens = await service.exchange_code(code, redirect_uri)

        # Find or create connector instance
        from sqlalchemy import select
        from app.models.connections import ConnectorInstance

        stmt = select(ConnectorInstance).where(
            ConnectorInstance.connector_id == connector_id,
            ConnectorInstance.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance:
            # Update existing instance
            instance.credentials = tokens
            instance.status = "connected"
            await db.commit()
        else:
            # Create new instance
            instance = ConnectorInstance(
                connector_id=connector_id,
                tenant_id=tenant_id,
                display_name=f"{connector_id} (OAuth)",
                credentials=tokens,
                status="connected",
            )
            db.add(instance)
            await db.commit()

        logger.info(
            "connector_oauth.connected",
            connector_id=connector_id,
            user_id=str(user_id),
        )

        # Return HTML that communicates success to the opener window
        return HTMLResponse(content=f"""
        <html>
        <head><title>Daena - Connected</title></head>
        <body style="background:#0F1419;color:#D4A843;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="text-align:center;">
                <h2>Connected to {connector_id}</h2>
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
        logger.error("connector_oauth.callback_failed", error=str(exc))
        return HTMLResponse(
            content=f"""
            <html>
            <body style="background:#0F1419;color:#ff6b6b;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="text-align:center;">
                    <h2>Connection Failed</h2>
                    <p>{str(exc)}</p>
                    <p style="color:#999;">Please close this window and try again.</p>
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
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Manually refresh OAuth tokens for a connector instance."""
    from sqlalchemy import select
    from app.models.connections import ConnectorInstance

    stmt = select(ConnectorInstance).where(
        ConnectorInstance.id == instance_id,
        ConnectorInstance.tenant_id == user["tenant_id"],
    )
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()

    if not instance:
        return JSONResponse(status_code=404, content={"error": "Instance not found"})

    credentials = instance.credentials or {}
    refresh_token = credentials.get("refresh_token")
    if not refresh_token:
        return JSONResponse(status_code=400, content={"error": "No refresh token available"})

    service = ConnectorOAuthService(db)
    try:
        new_tokens = await service.refresh_token(refresh_token)
        credentials["access_token"] = new_tokens["access_token"]
        credentials["expires_at"] = new_tokens["expires_at"]
        instance.credentials = credentials
        await db.commit()

        return JSONResponse(content={
            "status": "refreshed",
            "expires_at": new_tokens["expires_at"],
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
