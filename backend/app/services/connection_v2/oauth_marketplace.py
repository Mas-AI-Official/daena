"""Bridge: V2 marketplace OAuth catalog -> existing ConnectorOAuthService.

PR-CONN-OAUTH-CONNECT (2026-05-02). Lets the Plugins marketplace start
an OAuth Connect flow for ``kind=oauth_app`` catalog entries by reusing
ALL of the existing OAuth machinery:

  * client_id / client_secret resolution (env -> oauth_credentials_store
    runtime overrides) lives in ``oauth_service._get_credential``.
  * Auth-URL construction + state token + scope set lives in
    ``ConnectorOAuthService.generate_auth_url``.
  * Code-for-token exchange + identity fetch + AES-encrypted token
    storage lives in ``connector_oauth.oauth_callback`` (V1 endpoint).
  * The ONLY new pieces are:
      1. Catalog-id -> provider-id mapping (strip ``app-`` prefix).
      2. ``_v2_marketplace=True`` flag injected into the in-memory state
         store so the existing callback also imports a V2 row after the
         V1 ConnectorInstance is updated.
      3. ``oauth_app_slug_for(provider)`` -- canonical V2 slug
         (``oauth-<provider>``).

Hard rules honored (founder):
  * NEVER returns secrets in the start payload (auth URL contains
    client_id, which is a public identifier; we still log NAMES only).
  * NEVER duplicates token storage. The V2 row carries
    ``vault_ref = str(connector_instance.id)`` -- the actual
    AES-encrypted blob lives on V1's ``ConnectorInstance.credentials``,
    same place V1 used. Probes follow the vault_ref to read it.
  * NEVER lies about callable. The V2 row's ``authenticated`` flag is
    set when tokens land. ``callable=true`` requires the OAuth probe
    to succeed (token present + not expired + optional userinfo).
  * NEVER auto-installs anything. The flow is: user clicks Connect,
    consent screen opens, user grants, callback writes tokens.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.services.integrations.oauth_service import (
    OAUTH_PROVIDERS,
    ConnectorOAuthService,
    OAuthConfigError,
)

logger = get_logger(__name__)


# Catalog IDs always start with ``app-`` (see marketplace_catalog.py).
# Map by stripping that prefix; the OAUTH_PROVIDERS table keys are the
# bare provider id (gmail, github, figma, slack, canva,
# google-calendar, google-drive).
_CATALOG_PREFIX = "app-"


# Failure-reason prefixes for the start endpoint. Frontend matches on
# these without parsing free-form text.
FAIL_UNSUPPORTED_PROVIDER = "unsupported_provider"
FAIL_CONFIGURE_REQUIRED = "configure_required"
FAIL_REDIRECT_MISCONFIGURED = "redirect_misconfigured"
FAIL_ENTRY_NOT_OAUTH = "entry_not_oauth"


def provider_id_for(catalog_entry_id: str) -> str | None:
    """Map a catalog entry id (``app-gmail``) to its OAuth provider id.

    Returns None when the catalog id does not start with ``app-`` OR
    when the resolved provider is not in OAUTH_PROVIDERS (e.g.
    ``app-notion-oauth`` is in the catalog as coming-soon but has no
    OAuth service entry yet, so the start endpoint refuses).
    """
    raw = (catalog_entry_id or "").strip()
    if not raw.startswith(_CATALOG_PREFIX):
        return None
    candidate = raw[len(_CATALOG_PREFIX):]
    # Notion / Stripe / Cloudflare / Sentry land in the catalog as
    # ``app-<provider>-oauth`` -- strip the trailing -oauth so the lookup
    # works once they ARE wired into oauth_service.
    if candidate.endswith("-oauth"):
        candidate = candidate[: -len("-oauth")]
    if candidate not in OAUTH_PROVIDERS:
        return None
    return candidate


def supported_provider_ids() -> tuple[str, ...]:
    """Tuple of provider ids the marketplace flow knows how to start."""
    return tuple(sorted(OAUTH_PROVIDERS.keys()))


def oauth_app_slug_for(provider_id: str) -> str:
    """Canonical V2 slug for an OAuth provider.

    Mirrors ``seeders.oauth_app_slug`` so a Connect flow imports the
    SAME row a future discovery refresh would create (no duplicates).
    """
    from app.services.connection_v2.seeders import oauth_app_slug

    return oauth_app_slug(provider_id)


@dataclass(frozen=True)
class StartReport:
    """Outcome of generating an OAuth start URL.

    ``authorization_url`` is the consent page the operator opens. It
    contains the public ``client_id`` and the public ``redirect_uri``
    -- both are by-design public values in OAuth 2.0. The opaque
    ``state`` is the CSRF token the callback uses to validate the
    redirect.
    """

    success: bool
    provider: str | None
    authorization_url: str | None
    redirect_uri: str | None
    scopes: tuple[str, ...]
    state_ref: str | None
    failure_reason: str | None


def start_oauth_for_marketplace(
    *,
    db,
    catalog_entry_id: str,
    base_url: str,
    state_store: dict[str, dict],
    user_id,
    tenant_id,
) -> StartReport:
    """Generate an authorization URL + state for a marketplace OAuth entry.

    Reuses ``ConnectorOAuthService.generate_auth_url`` so the URL +
    scopes + extra_auth_params come from the SAME table V1 uses.
    Stores state with ``_v2_marketplace=True`` so the existing
    callback knows to also import a V2 row after the V1 token write.

    Args:
        db: AsyncSession (passed through to ConnectorOAuthService for
            consistency; not used by generate_auth_url itself).
        catalog_entry_id: e.g. ``"app-gmail"``.
        base_url: scheme+host of the request, used to build the
            absolute redirect_uri.
        state_store: the in-memory dict ``connector_oauth._oauth_states``.
            Inject as a parameter so tests can pass an isolated dict.
        user_id, tenant_id: identifiers stored alongside state for the
            callback to dereference.
    """
    provider = provider_id_for(catalog_entry_id)
    if provider is None:
        return StartReport(
            success=False, provider=None,
            authorization_url=None, redirect_uri=None,
            scopes=(), state_ref=None,
            failure_reason=(
                f"{FAIL_UNSUPPORTED_PROVIDER}: catalog entry "
                f"{catalog_entry_id!r} maps to no provider in "
                f"oauth_service.OAUTH_PROVIDERS (supported: "
                f"{', '.join(supported_provider_ids())})"
            ),
        )

    service = ConnectorOAuthService(db)
    redirect_uri = f"{base_url.rstrip('/')}/api/v1/connectors/oauth/callback"

    try:
        auth_url, state = service.generate_auth_url(
            provider=provider, redirect_uri=redirect_uri,
        )
    except OAuthConfigError as exc:
        # Operator hasn't pasted client_id / client_secret in Settings.
        # Frontend matches this prefix to render a Configure CTA.
        return StartReport(
            success=False, provider=provider,
            authorization_url=None, redirect_uri=redirect_uri,
            scopes=tuple(OAUTH_PROVIDERS[provider].scopes),
            state_ref=None,
            failure_reason=(
                f"{FAIL_CONFIGURE_REQUIRED}: {exc.missing_field} not set "
                f"-- paste your {provider} OAuth client credentials in "
                f"Account -> OAuth Client Config before starting Connect."
            ),
        )
    except ValueError as exc:
        return StartReport(
            success=False, provider=provider,
            authorization_url=None, redirect_uri=redirect_uri,
            scopes=tuple(OAUTH_PROVIDERS[provider].scopes),
            state_ref=None,
            failure_reason=f"{FAIL_REDIRECT_MISCONFIGURED}: {exc}",
        )

    # Stash state with the v2_marketplace flag so the existing callback
    # also imports a V2 row.
    state_store[state] = {
        "connector_id": provider,
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "redirect_uri": redirect_uri,
        "_v2_marketplace": True,
        "_catalog_entry_id": catalog_entry_id,
    }

    logger.info(
        "v2_oauth_marketplace.start",
        catalog_entry_id=catalog_entry_id,
        provider=provider,
        redirect_uri=redirect_uri,
        # Never log the auth_url itself -- it embeds the operator's
        # OAuth client_id (public, but not necessary in our log).
    )

    return StartReport(
        success=True, provider=provider,
        authorization_url=auth_url,
        redirect_uri=redirect_uri,
        scopes=tuple(OAUTH_PROVIDERS[provider].scopes),
        state_ref=state,
        failure_reason=None,
    )


async def import_v2_row_after_callback(
    *, db, tenant_id, provider: str, connector_instance_id, account_identity: str = "",
) -> tuple[str, str] | None:
    """Import / update the V2 oauth_app row after the V1 callback wrote tokens.

    Idempotent on (tenant_id, kind=oauth_app, slug=oauth-<provider>):
    re-running on an existing row updates auth state without
    duplicating.

    Returns (row_id, label) on success, or None when the registry import
    failed (caller logs but does NOT raise -- the OAuth callback already
    succeeded; failing the whole callback over a V2 import miss would
    be backward-incompatible with V1).

    The V2 row stores ``vault_ref = str(connector_instance_id)`` so the
    OAuth probe can dereference it back to the V1 ConnectorInstance
    where the AES-encrypted token blob lives. NO token material is
    duplicated into the V2 row's config.
    """
    try:
        from app.core.config import get_settings
        from app.core.vault_boot import load_kek_from_env
        from app.models.connection_v2 import AuthMethod, ConnectionKind
        from app.services.connection_v2.registry import ConnectionRegistryV2

        settings = get_settings()
        kek = load_kek_from_env(is_production=settings.is_production)
        reg = ConnectionRegistryV2(db, kek_seed=kek)

        slug = oauth_app_slug_for(provider)
        config = {
            "kind": "oauth_app",
            "client_id": "",  # never duplicated; lives in oauth_credentials_store
            "redirect_uri": f"v1:connector_instance:{connector_instance_id}",
            "scopes": list(OAUTH_PROVIDERS[provider].scopes),
            "_provider": provider,
            "_account_identity": account_identity,  # masked / handle ok; never the token
            "_v1_connector_instance_id": str(connector_instance_id),
            "_seeded_by": "v2_marketplace_oauth_callback",
        }
        config = {k: v for k, v in config.items() if v not in (None, "")}

        # vault_ref points at the V1 ConnectorInstance row that holds the
        # AES-encrypted token blob. NO duplication of secret material.
        result = await reg.import_connection(
            tenant_id=tenant_id,
            kind=ConnectionKind.OAUTH_APP,
            slug=slug,
            display_name=_display_name_for(provider),
            auth_method=AuthMethod.OAUTH_MANAGED,
            config=config,
        )
        # Stamp authenticated=true since the callback proved tokens
        # exist. The probe will independently verify expiration on next
        # poll; until then the truth ladder lifts to authenticated.
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        row = result.connection
        row.vault_ref = str(connector_instance_id)
        row.configured = True
        row.configured_at = now
        row.configured_failure_at = None
        row.configured_failure_reason = None
        row.authenticated = True
        row.authenticated_at = now
        row.authenticated_failure_at = None
        row.authenticated_failure_reason = None
        await db.flush()
        await db.commit()

        label = await reg.label_for(row)
        logger.info(
            "v2_oauth_marketplace.row_imported",
            provider=provider,
            row_id=str(row.id),
            slug=slug,
            label=label,
            account_identity_present=bool(account_identity),
        )
        return str(row.id), label
    except Exception as exc:  # noqa: BLE001 -- callback must not crash over V2 import
        logger.warning(
            "v2_oauth_marketplace.row_import_failed",
            provider=provider,
            error_type=type(exc).__name__,
        )
        return None


def _display_name_for(provider: str) -> str:
    """Friendly title for the V2 row (matches catalog display names)."""
    return {
        "gmail": "Gmail",
        "google-calendar": "Google Calendar",
        "google-drive": "Google Drive",
        "github": "GitHub",
        "figma": "Figma",
        "slack": "Slack",
        "canva": "Canva",
    }.get(provider, provider.replace("-", " ").title())


__all__ = [
    "FAIL_CONFIGURE_REQUIRED",
    "FAIL_ENTRY_NOT_OAUTH",
    "FAIL_REDIRECT_MISCONFIGURED",
    "FAIL_UNSUPPORTED_PROVIDER",
    "StartReport",
    "import_v2_row_after_callback",
    "oauth_app_slug_for",
    "provider_id_for",
    "start_oauth_for_marketplace",
    "supported_provider_ids",
]
