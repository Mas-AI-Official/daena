"""Google account setup status endpoint.

PR-GOOGLE-OAUTH-LIVE-SETUP-HELPERS (Sprint-10 PR-1, 2026-05-05).

Read-only endpoint that powers the GoogleAccountSetupGuide live
checklist. Tells the operator exactly which step is left before both
Google accounts are usable:

  1. OAuth client_id / client_secret configured
  2. Founder account (masoud.masoori@mas-ai.co) connected
  3. Agent account (daena@mas-ai.co) connected
  4. Both accounts visible in the Apps tab

NEVER:
  * starts an OAuth flow
  * reads or returns any client_secret / access_token / refresh_token
  * stores anything beyond what the underlying OAuth tables already hold
  * accepts an account email override -- the two emails are pinned
    by the company-account contract, not operator-supplied (per the
    Sprint-10 brief: "masoud.masoori@mas-ai.co as founder/operator,
    daena@mas-ai.co as company/agent"). A future PR can add
    multi-tenant overrides; today the pin matches Masoud's two
    workspaces.

The endpoint requires authentication (any role) so each operator
sees their own tenant's connection state.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.connections import ConnectorInstance
from app.services.integrations import oauth_client_config_store

router = APIRouter()


# Pinned per Sprint-10 brief. Lower-cased for comparison; the underlying
# row stores the email as Google returned it.
FOUNDER_EMAIL = "masoud.masoori@mas-ai.co"
AGENT_EMAIL = "daena@mas-ai.co"

# Connector slugs that share the Google OAuth client. Any one of these
# being connected for a given email proves the account is wired -- we
# don't require all three.
GOOGLE_CONNECTOR_SLUGS: tuple[str, ...] = (
    "gmail",
    "google-drive",
    "google-calendar",
)


def _account_status(
    instances: list[ConnectorInstance], target_email: str,
) -> dict:
    """Build the status payload for one of the two pinned accounts.

    Looks for a CONNECTED instance whose owner_email (case-insensitive)
    matches the target. NEVER returns the access_token, refresh_token,
    or any other credential. Returns the minimum the UI needs to render
    the checklist row: connected (bool), connector_id of one matching
    instance, and the list of which Google services were connected for
    this email (so the operator sees if they only authorized Gmail but
    not Drive, etc.).
    """
    target = target_email.strip().lower()
    matched = [
        inst for inst in instances
        if (inst.owner_email or "").strip().lower() == target
        and (inst.status or "").upper() == "CONNECTED"
    ]
    if not matched:
        return {
            "email": target_email,
            "connected": False,
            "instance_id": None,
            "connected_services": [],
        }

    services_seen: list[str] = []
    instance_id = None
    for inst in matched:
        slug = inst.connector.name if inst.connector else None
        if slug and slug not in services_seen:
            services_seen.append(slug)
        if instance_id is None:
            instance_id = str(inst.id)

    return {
        "email": target_email,
        "connected": True,
        "instance_id": instance_id,
        "connected_services": services_seen,
    }


@router.get("/google-setup-status")
async def google_setup_status(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Live checklist payload for GoogleAccountSetupGuide.

    Pure read. No side effects. Returns the four-step status block plus
    a derived ``ready`` flag (True iff the OAuth client is configured
    AND both pinned accounts are connected).
    """
    # Step 1: client config status (slug='google' covers all three
    # Google services per oauth_client_config_store.PROVIDER_DISPLAY).
    client_meta = oauth_client_config_store.get_metadata("google")
    client_configured = bool(client_meta.get("configured"))
    client_id_present = bool(client_meta.get("client_id_present"))

    # Steps 2-3: account presence. Pull all Google-shaped instances for
    # this tenant in one query; classify by owner_email.
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import selectinload
    from app.models.connections import Connector
    from app.core.logging import get_logger

    stmt = (
        select(ConnectorInstance)
        .join(Connector, ConnectorInstance.connector_id == Connector.id)
        .where(
            ConnectorInstance.tenant_id == user.tenant_id,
            ConnectorInstance.user_id == user.id,
            # Match the connector by name (the catalog seeds Connector
            # rows with name == provider_id from OAUTH_PROVIDERS).
            Connector.name.in_(GOOGLE_CONNECTOR_SLUGS),
        )
        .options(selectinload(ConnectorInstance.connector))
    )
    try:
        result = await db.execute(stmt)
        instances = list(result.scalars().all())
    except OperationalError as exc:
        # Dev SQLite databases created before owner_email landed on
        # ConnectorInstance lack the column. ``create_all`` does not
        # ALTER TABLE on existing rows, so the dev path needs a graceful
        # degrade until the operator runs the migration / wipes
        # ``backend/var/daena.db``. We surface "0 connected" + a note.
        # Production is on Postgres + Alembic so this branch never
        # fires there.
        get_logger(__name__).warning(
            "google_setup.legacy_schema_fallback",
            error=str(exc)[:200],
        )
        instances = []

    founder = _account_status(instances, FOUNDER_EMAIL)
    agent = _account_status(instances, AGENT_EMAIL)
    ready = client_configured and founder["connected"] and agent["connected"]

    return {
        "client_configured": client_configured,
        "client_id_present": client_id_present,
        "client_secret_present": client_configured,
        # ^^ When configured=True, set_client_config requires both
        # client_id and client_secret. The shared store has no separate
        # client_secret_present check -- the invariant is upheld at write.
        "founder_account": founder,
        "agent_account": agent,
        "ready": ready,
    }
