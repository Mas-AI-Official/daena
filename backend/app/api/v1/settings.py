"""User settings endpoints: developer mode toggle and preferences.

Thin router — reads/writes system configuration flags
that affect platform behavior (archive vs hard-delete, etc.).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter()


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
    default_governance_slider: str = "STANDARD"
    default_runtime: str = "auto"


# Keys stored in User.settings JSONB for UI preferences
_UI_PREF_KEYS = (
    "dark_mode", "conversational_mode", "sidebar_collapsed",
    "default_chat_mode", "default_routing_mode", "default_governance_slider", "default_runtime",
    "local_first_routing", "cost_aware_routing",
    "autopilot_active", "persist_thinking", "deep_research", "auto_read_responses",
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
    "default_governance_slider": "STANDARD",
    "default_runtime": "auto",
    "local_first_routing": True,
    "cost_aware_routing": True,
    "autopilot_active": False,
    "persist_thinking": True,
    "deep_research": False,
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
    default_governance_slider: str | None = Field(None, pattern="^(YOLO|LIGHT|STANDARD|STRICT|PARANOID)$")
    default_runtime: str | None = None
    local_first_routing: bool | None = None
    cost_aware_routing: bool | None = None
    autopilot_active: bool | None = None
    persist_thinking: bool | None = None
    deep_research: bool | None = None
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

    return {
        "success": True,
        "data": {
            "display_name": db_display_name,
            "email": db_email,
            "role": user.role,
            "preferred_model": preferred_model,
            "anti_slop_mode": anti_slop_mode,
            **ui_prefs,
        },
    }


@router.put("/user")
async def update_user_preferences(
    body: UserPreferencesUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update user preferences (display name, preferred model, etc.)."""
    from sqlalchemy import select

    from app.models.identity import User

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
        await db.flush()

        user_settings = db_user.settings or {}
        preferred_model = user_settings.get("preferred_model") if isinstance(user_settings, dict) else None
        anti_slop_mode = user_settings.get("anti_slop_mode", True) if isinstance(user_settings, dict) else True
    else:
        preferred_model = None
        anti_slop_mode = True
        user_settings = {}

    # Extract UI preferences
    ui_prefs = {k: user_settings.get(k, _UI_PREF_DEFAULTS[k]) if isinstance(user_settings, dict) else _UI_PREF_DEFAULTS[k] for k in _UI_PREF_KEYS}

    return {
        "success": True,
        "data": {
            "display_name": body.display_name or user.display_name,
            "email": user.email,
            "role": user.role,
            "preferred_model": preferred_model,
            "anti_slop_mode": anti_slop_mode,
            **ui_prefs,
        },
    }


@router.get("/user/export")
async def export_user_data(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Export user profile/settings payload as JSON data."""
    prefs = await get_user_preferences(user=user, db=db)
    return {
        "success": True,
        "data": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user": prefs.get("data", {}),
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
