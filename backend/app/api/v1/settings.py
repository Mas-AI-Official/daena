"""User settings endpoints: developer mode toggle and preferences.

Thin router — reads/writes system configuration flags
that affect platform behavior (archive vs hard-delete, etc.).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter()


# ── Budget settings -> UserQuota sync (DECISION-003, 2026-06-01) ──

# The SettingsBilling UI uses these three over-budget action values.
# The per-user enforcement model (UserQuota.overage_action, read by
# CostGuard.preflight_check) uses a slightly different vocabulary. This
# map is the single source of truth for the translation.
#   warn     -> warn          (log + best-effort notification, never blocks)
#   fallback -> fallback_free (route the request to a free local model)
#   block    -> block         (raise BudgetExceededError; refuse the call)
_OVER_BUDGET_ACTION_MAP: dict[str, str] = {
    "warn": "warn",
    "fallback": "fallback_free",
    "block": "block",
}


async def _sync_budget_to_user_quota(
    db: "AsyncSession",
    *,
    user_id,
    tenant_id,
    role: str,
    monthly_budget: int | None,
    over_budget_action: str | None,
) -> None:
    """Mirror the SettingsBilling budget controls into the user's
    UserQuota row so the existing CostGuard enforcement honors them.

    Idempotent upsert: creates the UserQuota row with plan defaults if it
    does not exist yet (reusing CostGuard's lazy-provision path), then
    overwrites only the fields the user explicitly set. Never raises into
    the settings save (best-effort): a budget-sync failure must not block
    the user from saving an unrelated preference.
    """
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    try:
        from app.services.cost_guard import CostGuard

        guard = CostGuard(db)
        # Reuse the lazy-provision so a brand-new user gets a row with the
        # correct plan-tier defaults before we overlay their choices.
        quota = await guard._get_or_create_user_quota(tenant_id, user_id)

        if monthly_budget is not None:
            # The UI sends an integer dollar amount; the column is Numeric.
            quota.monthly_credit_usd = float(monthly_budget)
        if over_budget_action is not None:
            mapped = _OVER_BUDGET_ACTION_MAP.get(over_budget_action)
            if mapped is not None:
                quota.overage_action = mapped

        await db.flush()
        logger.info(
            "settings.budget_synced_to_quota",
            user_id=str(user_id),
            role=role,
            monthly_budget=monthly_budget,
            over_budget_action=over_budget_action,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "settings.budget_sync_failed",
            user_id=str(user_id),
            error=str(exc),
        )


# ── Schemas ────────────────────────────────────────────────────────


class DeveloperModeResponse(BaseModel):
    """Current developer mode state."""
    developer_mode: bool
    description: str = (
        "When off (default), all deletes are archived to .archive/ for safety. "
        "When on, actual file deletion is allowed."
    )


class DeveloperModeUpdate(BaseModel):
    """Toggle developer mode."""
    enabled: bool


class SettingsOverview(BaseModel):
    """Public settings summary (no secrets)."""
    app_name: str
    app_env: str
    developer_mode: bool
    enable_web3: bool
    enable_daenabot: bool


class OAuthCredentialsPayload(BaseModel):
    """Body of POST /settings/oauth-credentials.

    Accepted from the Connections > Setup modal so operators can paste
    their own OAuth client IDs without editing .env or restarting.
    Values are written to the runtime override store (gitignored JSON
    at backend/.daena_oauth_overrides.json, chmod 0600 on POSIX).
    """
    connector_id: str = Field(..., description="Connector id, e.g. google, github, notion")
    client_id_field: str = Field(..., description="Settings field name, e.g. google_client_id")
    client_id: str = Field(..., min_length=4)
    client_secret_field: str = Field(..., description="e.g. google_client_secret")
    client_secret: str = Field(..., min_length=4)


class OAuthCredentialsResult(BaseModel):
    """Result after a successful credentials save."""
    saved: bool
    connector_id: str
    fields_saved: list[str]


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/")
async def get_settings_overview(
    _user: CurrentUser = Depends(get_current_user),
) -> SettingsOverview:
    """Return public application settings."""
    s = get_settings()
    return SettingsOverview(
        app_name=s.app_name,
        app_env=s.app_env,
        developer_mode=s.developer_mode,
        enable_web3=s.enable_web3,
        enable_daenabot=s.enable_daenabot,
    )


@router.get("/developer-mode")
async def get_developer_mode(
    _user: CurrentUser = Depends(get_current_user),
) -> DeveloperModeResponse:
    """Check whether developer mode is on or off."""
    return DeveloperModeResponse(developer_mode=get_settings().developer_mode)


@router.patch("/developer-mode")
async def toggle_developer_mode(
    body: DeveloperModeUpdate,
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> DeveloperModeResponse:
    """Toggle developer mode (ADMIN+ only).

    When developer_mode=False (default), all delete operations archive
    files to .archive/ instead of permanently removing them.
    When developer_mode=True, actual deletion is allowed.
    """
    settings = get_settings()
    settings.developer_mode = body.enabled
    return DeveloperModeResponse(developer_mode=settings.developer_mode)


# ── User preferences ──────────────────────────────────────────────


class UserPreferencesResponse(BaseModel):
    """User preferences readable by the frontend."""
    model_config = ConfigDict(extra="allow")

    display_name: str
    email: str
    role: str
    preferred_model: str | None = None
    anti_slop_mode: bool = True
    # UI preferences (persisted across reload)
    dark_mode: bool = True
    conversational_mode: bool = True
    sidebar_collapsed: bool = False
    default_chat_mode: str = "CMD"
    default_routing_mode: str = "STANDARD"
    default_governance_mode: str = "GOVERNED"
    default_governance_slider: str = "GOVERNED"  # Deprecated: mirrors default_governance_mode
    default_runtime: str = "auto"


# Keys stored in User.settings JSONB for UI preferences
_UI_PREF_KEYS = (
    "dark_mode", "conversational_mode", "sidebar_collapsed",
    "default_chat_mode", "default_routing_mode", "default_governance_mode", "default_governance_slider", "default_runtime",
    "local_first_routing", "cost_aware_routing",
    "autopilot_active", "persist_thinking", "auto_read_responses",
    "debug_mode", "verbose_logging",
    "monthly_budget", "over_budget_action",
    # Privacy
    "memory_generation", "search_past_conversations", "storage_local",
    "improve_from_usage", "location_metadata",
    # Notifications
    "notif_desktop", "notif_task_complete", "notif_budget_alert",
    "notif_heartbeat", "notif_gov_reject", "notif_runtime_disconnect",
    "notif_sound", "notif_email", "notif_daily_digest",
    # Developer
    "developer_mode",
    # Billing
    "budget_alert_threshold",
)

_UI_PREF_DEFAULTS: dict[str, object] = {
    "dark_mode": True,
    "conversational_mode": True,
    "sidebar_collapsed": False,
    "default_chat_mode": "CMD",
    "default_routing_mode": "STANDARD",
    "default_governance_mode": "GOVERNED",
    "default_governance_slider": "GOVERNED",  # Deprecated: mirrors default_governance_mode
    "default_runtime": "auto",
    "local_first_routing": True,
    "cost_aware_routing": True,
    "autopilot_active": False,
    "persist_thinking": True,
    "auto_read_responses": False,
    "debug_mode": False,
    "verbose_logging": False,
    "monthly_budget": 25,
    "over_budget_action": "fallback",
    # Privacy
    "memory_generation": True,
    "search_past_conversations": True,
    "storage_local": True,
    "improve_from_usage": False,
    "location_metadata": False,
    # Notifications
    "notif_desktop": True,
    "notif_task_complete": True,
    "notif_budget_alert": True,
    "notif_heartbeat": True,
    "notif_gov_reject": True,
    "notif_runtime_disconnect": True,
    "notif_sound": False,
    "notif_email": False,
    "notif_daily_digest": False,
    # Developer
    "developer_mode": False,
    # Billing
    "budget_alert_threshold": 80,
}


class UserPreferencesUpdate(BaseModel):
    """Fields the user can update."""
    display_name: str | None = Field(None, min_length=1, max_length=200)
    preferred_model: str | None = Field(
        None,
        max_length=200,
        description="Default model ID for chat routing (e.g. claude-sonnet-4-20250514)",
    )
    anti_slop_mode: bool | None = Field(
        None,
        description="Enable anti-AI-pattern writing rules (default: ON)",
    )
    # UI preferences
    dark_mode: bool | None = None
    conversational_mode: bool | None = None
    sidebar_collapsed: bool | None = None
    default_chat_mode: str | None = Field(None, pattern="^(CMD|EXE)$")
    default_routing_mode: str | None = Field(None, pattern="^(STANDARD|COUNCIL|QUINTESSENCE)$")
    default_governance_mode: str | None = Field(None, pattern="^(UNLEASHED|BALANCED|GOVERNED)$")
    default_governance_slider: str | None = Field(
        None,
        pattern="^(YOLO|LIGHT|STANDARD|STRICT|PARANOID|UNLEASHED|BALANCED|GOVERNED)$",
        description="Deprecated: use default_governance_mode instead. Accepts both old and new values.",
    )
    default_runtime: str | None = None
    local_first_routing: bool | None = None
    cost_aware_routing: bool | None = None
    autopilot_active: bool | None = None
    persist_thinking: bool | None = None
    auto_read_responses: bool | None = None
    debug_mode: bool | None = None
    verbose_logging: bool | None = None
    monthly_budget: int | None = Field(None, ge=0)
    over_budget_action: str | None = Field(None, pattern="^(warn|fallback|block)$")
    # Privacy
    memory_generation: bool | None = None
    search_past_conversations: bool | None = None
    storage_local: bool | None = None
    improve_from_usage: bool | None = None
    location_metadata: bool | None = None
    # Notifications
    notif_desktop: bool | None = None
    notif_task_complete: bool | None = None
    notif_budget_alert: bool | None = None
    notif_heartbeat: bool | None = None
    notif_gov_reject: bool | None = None
    notif_runtime_disconnect: bool | None = None
    notif_sound: bool | None = None
    notif_email: bool | None = None
    notif_daily_digest: bool | None = None
    # Developer
    developer_mode: bool | None = None
    # Billing
    budget_alert_threshold: int | None = Field(None, ge=0, le=100)


@router.get("/user")
async def get_user_preferences(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the current user's editable preferences."""
    # Fetch preferred_model from the User.settings JSONB column
    from sqlalchemy import select

    from app.models.identity import User

    stmt = select(User).where(User.id == user.id)
    result = await db.execute(stmt)
    db_user = result.scalar_one_or_none()

    # Handle both ORM object and dict (from mocks)
    if db_user is not None and hasattr(db_user, "settings"):
        user_settings = db_user.settings or {}
        db_display_name = db_user.display_name
        db_email = db_user.email
    else:
        user_settings = db_user if isinstance(db_user, dict) else {}
        db_display_name = user.display_name
        db_email = user.email

    preferred_model = user_settings.get("preferred_model") if isinstance(user_settings, dict) else None
    anti_slop_mode = user_settings.get("anti_slop_mode", True) if isinstance(user_settings, dict) else True

    # Extract UI preferences from settings JSONB
    ui_prefs = {k: user_settings.get(k, _UI_PREF_DEFAULTS[k]) if isinstance(user_settings, dict) else _UI_PREF_DEFAULTS[k] for k in _UI_PREF_KEYS}

    prefs = UserPreferencesResponse(
        display_name=db_display_name or user.display_name or "",
        email=db_email or user.email or "",
        role=user.role,
        preferred_model=preferred_model,
        anti_slop_mode=anti_slop_mode,
        **ui_prefs,
    )
    return {"success": True, "data": prefs.model_dump()}


# PR-GOV-01: Field-level Founder guard.
#
# Hard Law 8 (hard_laws.py:83-91) requires governance mode toggles to
# go through the FOUNDER role. PUT /settings/user previously had no
# role check, so any authenticated user could flip default_governance_mode
# from GOVERNED to UNLEASHED via the API. This set defends the relevant
# fields at the impl layer (not the endpoint layer) so non-Founders can
# still update their normal preferences (theme, notifications, display
# name) on the same endpoint.
#
# default_routing_mode is included because COUNCIL/QUINTESSENCE multiply
# LLM cost per request; cost preflight enforces tenant ceilings at chat
# time, but the *default* should not be self-elevated by non-Founders.
SENSITIVE_PREF_FIELDS: frozenset[str] = frozenset({
    "default_governance_mode",
    "default_governance_slider",  # deprecated; mirrors default_governance_mode
    "default_routing_mode",       # Council/Quintessence cost multiplier
})


def _check_governance_field_permissions(
    body: UserPreferencesUpdate,
    user: CurrentUser,
) -> list[str]:
    """Return sorted list of sensitive field names a non-Founder is trying
    to set. Empty list means the request passes the role check.

    FOUNDER always bypasses (per Hard Law 4: Founder Override). All other
    roles -- including ADMIN -- are gated on these fields.
    """
    if user.role == "FOUNDER":
        return []
    rejected: list[str] = []
    for field in SENSITIVE_PREF_FIELDS:
        if getattr(body, field, None) is not None:
            rejected.append(field)
    return sorted(rejected)


@router.put("/user")
async def update_user_preferences(
    body: UserPreferencesUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update user preferences (display name, preferred model, etc.)."""
    import logging as _logging
    _log = _logging.getLogger("settings.debug")
    try:
        prefs = await _update_user_preferences_impl(body, user, db)
        return {"success": True, "data": prefs.model_dump()}
    except HTTPException:
        # Field-level guard rejection -- already logged via audit ledger.
        # Re-raise without the noisy stacktrace from the generic except.
        raise
    except Exception as exc:
        _log.exception("settings PUT failed: %s", exc)
        raise


async def _update_user_preferences_impl(
    body: UserPreferencesUpdate,
    user: CurrentUser,
    db: AsyncSession,
) -> UserPreferencesResponse:
    from sqlalchemy import select

    from app.models.identity import User

    # PR-GOV-01: Field-level Founder guard runs FIRST, before any DB write.
    # All-or-nothing reject: if any sensitive field is in the payload and
    # the actor is not FOUNDER, fail the entire request. Do not partially
    # apply the non-sensitive fields (avoids ambiguity about what the
    # client thinks landed).
    rejected_fields = _check_governance_field_permissions(body, user)
    if rejected_fields:
        # Audit the attempt before raising. Field NAMES are logged but
        # attempted VALUES are NOT (a malicious payload value could
        # itself be a probe vector or contain PII).
        try:
            from app.services.audit import AuditService
            audit = AuditService(db)
            await audit.log_decision(
                tenant_id=user.tenant_id,
                actor_id=user.id,
                actor_type="USER",
                action_type="GOVERNANCE_PREF_UPDATE_REJECTED",
                action_params={
                    "attempted_fields": rejected_fields,
                    "user_role": user.role,
                },
                result="BLOCKED",
                risk_level="HIGH",
                governance_tier=4,
            )
        except Exception:
            # Audit failure must NOT silently allow the request through.
            # We still raise the 403 below. The audit miss is logged
            # locally so an operator can reconcile.
            import logging
            logging.getLogger("settings.guard").exception(
                "audit log failed during governance guard rejection "
                "(rejection still enforced)"
            )
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FOUNDER_ROLE_REQUIRED",
                    "message": (
                        "These preference fields can only be changed by "
                        "the Founder. Hard Law 8 governs governance mode "
                        "and routing-mode defaults."
                    ),
                    "rejected_fields": rejected_fields,
                }
            },
        )

    # Load the full User row so we can update display_name and settings
    stmt = select(User).where(User.id == user.id)
    result = await db.execute(stmt)
    db_user = result.scalar_one_or_none()

    if db_user is not None:
        if body.display_name is not None:
            db_user.display_name = body.display_name

        # Merge all settings into the JSONB column
        current_settings = dict(db_user.settings) if db_user.settings else {}

        if body.preferred_model is not None:
            current_settings["preferred_model"] = body.preferred_model
        if body.anti_slop_mode is not None:
            current_settings["anti_slop_mode"] = body.anti_slop_mode

        # UI preferences
        for key in _UI_PREF_KEYS:
            val = getattr(body, key, None)
            if val is not None:
                current_settings[key] = val

        db_user.settings = current_settings
        # Signal SQLAlchemy that JSONB column changed (SQLite doesn't
        # auto-detect in-place JSONB mutations via change tracking)
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(db_user, "settings")
        await db.flush()

        # DECISION-003 (2026-06-01): sync the budget controls into the
        # per-user UserQuota row so the existing CostGuard enforcement
        # (which runs on every chat) actually honors them. Only fields
        # explicitly present in this PUT are synced, so a user who never
        # touches these keeps their plan-default quota (a FOUNDER stays
        # uncapped). This is the write path; CostGuard is the read/enforce
        # path and is left untouched.
        if body.monthly_budget is not None or body.over_budget_action is not None:
            await _sync_budget_to_user_quota(
                db,
                user_id=user.id,
                tenant_id=user.tenant_id,
                role=user.role,
                monthly_budget=body.monthly_budget,
                over_budget_action=body.over_budget_action,
            )

        user_settings = current_settings  # Use the dict we just wrote, not the ORM reload
        preferred_model = user_settings.get("preferred_model") if isinstance(user_settings, dict) else None
        anti_slop_mode = user_settings.get("anti_slop_mode", True) if isinstance(user_settings, dict) else True
    else:
        preferred_model = None
        anti_slop_mode = True
        user_settings = {}

    # Extract UI preferences
    ui_prefs = {k: user_settings.get(k, _UI_PREF_DEFAULTS[k]) if isinstance(user_settings, dict) else _UI_PREF_DEFAULTS[k] for k in _UI_PREF_KEYS}

    # Use db_user's display_name (updated or existing), falling back to
    # the JWT token's value, then empty string.  Previous code used
    # body.display_name which is None when the frontend only sends a
    # single UI preference key -- causing a 500 because the response
    # model requires a str, not None.
    _display_name = (
        (db_user.display_name if db_user is not None else None)
        or body.display_name
        or user.display_name
        or ""
    )
    _email = (
        (db_user.email if db_user is not None else None)
        or user.email
        or ""
    )

    return UserPreferencesResponse(
        display_name=_display_name,
        email=_email,
        role=user.role,
        preferred_model=preferred_model,
        anti_slop_mode=anti_slop_mode,
        **ui_prefs,
    )


@router.get("/user/export")
async def export_user_data(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Export user profile/settings payload as JSON data."""
    prefs = await get_user_preferences(user=user, db=db)
    # get_user_preferences returns a plain dict (not a Pydantic
    # model); pass it through directly.
    return {
        "success": True,
        "data": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user": prefs,
        },
    }


@router.post("/user/delete-request")
async def request_user_data_deletion(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a user-initiated account/data deletion request."""
    from sqlalchemy import select

    from app.models.identity import User

    requested_at = datetime.now(timezone.utc).isoformat()

    stmt = select(User).where(User.id == user.id)
    result = await db.execute(stmt)
    db_user = result.scalar_one_or_none()
    if db_user is not None:
        current_settings = dict(db_user.settings) if db_user.settings else {}
        current_settings["pending_delete_requested_at"] = requested_at
        db_user.settings = current_settings
        await db.flush()

    return {
        "success": True,
        "data": {
            "requested": True,
            "requested_at": requested_at,
        },
    }


@router.post("/oauth-credentials", response_model=OAuthCredentialsResult)
async def save_oauth_credentials(
    payload: OAuthCredentialsPayload,
    user: CurrentUser = Depends(get_current_user),
) -> OAuthCredentialsResult:
    """Persist OAuth client credentials for a connector.

    Session 10: called by the inline setup modal on Connections when a
    user clicks "Connect with Google" but the broker credentials are
    missing. Writes to the runtime override store so the next call to
    GET /connectors/{id}/oauth/authorize succeeds without a restart.
    """
    from app.services.integrations.oauth_credentials_store import set_overrides

    await set_overrides({
        payload.client_id_field: payload.client_id,
        payload.client_secret_field: payload.client_secret,
    })
    return OAuthCredentialsResult(
        saved=True,
        connector_id=payload.connector_id,
        fields_saved=[payload.client_id_field, payload.client_secret_field],
    )
