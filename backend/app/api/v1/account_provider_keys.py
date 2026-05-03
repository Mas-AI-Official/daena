"""Account-scoped provider API-key management.

PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT (2026-05-03): the operator pastes
LLM provider API keys (Anthropic / OpenAI / Gemini / Groq / Perplexity /
OpenRouter / Together) into the Account page or the Connections
"Configure" deep-link drawer. This module handles persistence
(``provider_keys_store``) AND live application via the existing
``DynamicModelService`` (``/api/v1/dynamic-models/provision``), so the
marketplace card flips from Configure to Test the moment Save
completes.

Honesty rules (per project Rule 17):
* GET endpoints NEVER return key values. Shape: ``{configured: bool,
  last_updated: iso8601, ...display metadata}``.
* POST validates the key by calling the existing dynamic-models health
  check; only then persists to the store. A bad key produces a clear
  failure_reason and the store is NOT touched.
* DELETE removes from the store AND removes the provider from the
  live registry (so Test stops working until re-saved).
* Save returns the post-save provider status (configured + model count
  + health) so the frontend can refresh the marketplace card without
  a separate round-trip. NEVER returns the saved value.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_role
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.dynamic_model_service import (
    CONNECTOR_PROVIDER_MAP,
    DynamicModelService,
)
from app.services.integrations.provider_keys_store import (
    PROVIDER_DISPLAY,
    SLUG_TO_FIELD,
    clear_override,
    list_provider_status,
    set_override,
)

logger = get_logger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────────────────────────
# Request / response schemas
# ──────────────────────────────────────────────────────────────────


class SaveKeyRequest(BaseModel):
    """Body for POST /account/provider-keys/{slug}.

    ``api_key`` is the raw value the operator pastes. It NEVER appears
    in any response (the response shape strips it). The field is
    intentionally not echoed back even on validation failure.
    """

    api_key: str = Field(..., min_length=1)
    test_after_save: bool = Field(
        default=True,
        description=(
            "When true (default), validate the key via the provider's "
            "health check BEFORE persisting. A failed health check "
            "returns 422 and the store is NOT touched."
        ),
    )


class ProviderKeyStatus(BaseModel):
    """Display-safe status row. Never carries the value."""

    slug: str
    settings_field: str
    display_name: str
    marketplace_id: str
    key_hint: str
    configured: bool
    last_updated: str  # iso8601 or ""


class SaveKeyResponse(BaseModel):
    """Post-save provider status. Never carries the value."""

    success: bool
    slug: str
    configured: bool
    health: str
    models_discovered: int = 0
    failure_reason: str | None = None
    last_updated: str | None = None


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _get_dynamic_model_service(request: Request) -> DynamicModelService:
    return DynamicModelService(request.app.state.model_registry)


def _slug_to_provider_name(slug: str) -> str | None:
    """Map URL slug -> CONNECTOR_PROVIDER_MAP key.

    URL slugs in PROVIDER_DISPLAY mirror DynamicModelService's
    CONNECTOR_PROVIDER_MAP keys exactly (anthropic, openai, gemini,
    groq, perplexity, openrouter, together). The one mismatch is
    ``gemini`` (here) vs. ``google_gemini`` (DynamicModelService);
    handle that here so neither side has to know about the other.
    """
    if slug not in PROVIDER_DISPLAY:
        return None
    if slug == "gemini":
        return "google_gemini"
    return slug


# ──────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ProviderKeyStatus])
async def list_provider_keys(
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> list[dict[str, Any]]:
    """List every supported provider with display-safe configured state.

    NEVER returns key values. Use this to render the Account page
    Provider Keys section.
    """
    return list_provider_status()


@router.post("/{slug}", response_model=SaveKeyResponse)
async def save_provider_key(
    slug: str,
    body: SaveKeyRequest,
    request: Request,
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> SaveKeyResponse:
    """Save (and optionally validate) a provider API key.

    Flow:
      1. Validate slug is known + map to DynamicModelService's
         provider_name vocabulary.
      2. If ``test_after_save`` (default True):
           * Call DynamicModelService.provision_provider which runs
             the provider's health check and registers the provider
             in the live ModelRegistry.
           * If health check fails, return 422 WITHOUT touching the
             store. The user sees a clear reason.
      3. Persist via ``provider_keys_store.set_override``.
      4. Return display-safe status (configured + health + model count).

    The raw key is NEVER persisted to logs (length-only) and NEVER
    echoed back in the response.
    """
    if slug not in PROVIDER_DISPLAY:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider slug {slug!r}",
        )

    field = SLUG_TO_FIELD[slug]
    provider_name = _slug_to_provider_name(slug)
    if provider_name is None:
        raise HTTPException(status_code=404, detail="Unmapped provider")

    # Step 1 + 2: validate via the existing dynamic-models flow.
    # This injects the key into settings and runs a real health check.
    # We ALWAYS invoke provision (whether test_after_save or not) so the
    # live ModelRegistry sees the new key without a restart.
    #
    # Workaround for DynamicModelService.provision_provider's
    # "already-registered" branch: it skips re-instantiation when the
    # provider slot is already populated (from .env at startup). That
    # means a NEW key the operator just pasted would never be tested
    # nor reach settings -- the old .env key would silently keep
    # serving. Force a clean slate by removing the provider first when
    # it's already there. The provision call below will then run the
    # full instantiate-and-validate path.
    svc = _get_dynamic_model_service(request)
    from app.services.dynamic_model_service import CONNECTOR_PROVIDER_MAP
    provider_enum = CONNECTOR_PROVIDER_MAP.get(provider_name)
    if (
        provider_enum is not None
        and provider_enum in svc._registry._providers
    ):
        await svc.remove_provider(provider_name)

    result = await svc.provision_provider(
        provider_name=provider_name,
        api_key=body.api_key,
    )

    # Stricter gate than dynamic_models: require HEALTHY (not just
    # not-UNAVAILABLE). Several providers (Anthropic, OpenAI, Groq)
    # respond to /v1/models with 401 on a bad key, which the underlying
    # health_check classifies as DEGRADED -- i.e. "API responded but
    # something's off." For a save flow where the operator just pasted
    # a key, "DEGRADED" is the same as "key didn't work" -- accepting
    # it would silently persist a bad key. HEALTHY = 200 from /v1/models
    # = the key authenticated. That's the contract we want.
    health_ok = result.success and result.health == "HEALTHY"

    if body.test_after_save and not health_ok:
        # Bad key -- DO NOT persist. Reset the in-memory settings
        # attribute back to whatever was there before (if anything).
        # The dynamic_model_service's setattr leaves the bad key in
        # settings on failure; clear it so subsequent calls don't
        # see a phantom override.
        try:
            settings = get_settings()
            # If we had a previous stored value, restore it; else clear.
            from app.services.integrations.provider_keys_store import (
                get_override,
            )
            previous = get_override(field)
            setattr(settings, field, previous)
        except Exception:
            pass
        # Friendlier message for the DEGRADED case (auth failed but API
        # was reachable) so the operator knows it's a key problem, not
        # a connectivity problem.
        if result.success and result.health != "HEALTHY":
            reason = (
                f"{provider_name} responded but the key was not accepted "
                f"(health={result.health}). Double-check the key value."
            )
        else:
            reason = result.error or "Provider health check failed."
        return SaveKeyResponse(
            success=False,
            slug=slug,
            configured=False,
            health=result.health,
            failure_reason=reason,
        )

    # Step 3: persist. Even if test_after_save was False, we already
    # injected via provision so the in-memory state matches the file.
    await set_override(field, body.api_key)

    # Step 4: status.
    # Re-read metadata so last_updated reflects the just-completed
    # write rather than a stale cache value.
    from app.services.integrations.provider_keys_store import get_metadata
    meta = get_metadata(field)

    logger.info(
        "account_provider_keys.saved",
        slug=slug,
        models_discovered=result.models_discovered,
        health=result.health,
        # NEVER log the key value or any prefix of it.
    )

    return SaveKeyResponse(
        success=True,
        slug=slug,
        configured=True,
        health=result.health,
        models_discovered=result.models_discovered,
        failure_reason=None,
        last_updated=str(meta.get("last_updated", "")),
    )


@router.delete("/{slug}")
async def delete_provider_key(
    slug: str,
    request: Request,
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """Clear a provider key from the store AND the live registry.

    After this call:
      * provider_keys_store reports configured=False
      * settings.<field> is reset to empty
      * The provider is removed from ModelRegistry (no more model
        selection via that provider until re-saved)
      * The marketplace card flips back to Configure
    """
    if slug not in PROVIDER_DISPLAY:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider slug {slug!r}",
        )

    field = SLUG_TO_FIELD[slug]
    provider_name = _slug_to_provider_name(slug)

    removed_from_store = await clear_override(field)

    # Reset the in-memory settings attribute too. Without this, the
    # provider stays registered until restart even though the file is
    # cleared.
    try:
        settings = get_settings()
        setattr(settings, field, "")
    except Exception:
        logger.exception(
            "account_provider_keys.settings_reset_failed", slug=slug,
        )

    removed_from_registry = False
    if provider_name and provider_name in CONNECTOR_PROVIDER_MAP:
        svc = _get_dynamic_model_service(request)
        removed_from_registry = await svc.remove_provider(provider_name)

    logger.info(
        "account_provider_keys.cleared",
        slug=slug,
        removed_from_store=removed_from_store,
        removed_from_registry=removed_from_registry,
    )

    return {
        "success": True,
        "slug": slug,
        "removed_from_store": removed_from_store,
        "removed_from_registry": removed_from_registry,
    }
