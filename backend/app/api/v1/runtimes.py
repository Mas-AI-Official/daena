"""Runtime adapter endpoints for the ConnectionsPage.

Exposes runtime registry state, subscription status, auth
requirements, test connection, and primary mind selection.

Stabilization 2026-04-29: this module's `GET /` endpoint used to
synchronously probe every API provider's `/models` endpoint on each
request (~3.5s on a clean run, multi-second when one provider is
slow). Plus it ran lazy `discover_all + check_health_all +
check_subscriptions_all` on first hit if the registry was empty,
blocking the very first /connections page load while startup
backgrounded scans had not finished.

Both are fixed:
  * Per-tenant 30s in-memory cache for the assembled response.
  * `asyncio.gather` over provider model probes (not sequential).
  * `warming` flag returned instead of blocking when registry
    `_installed_cache` is empty -- frontend polls.
  * Per-provider failure detail (`last_error_at`, `last_error_msg`)
    so the UI can show "Gemini /models timed out 14s ago" instead of
    a generic spinner.
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import CurrentUser, get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# ── Per-tenant response cache ──
#
# The response payload (registry snapshot + api providers + models) is
# expensive to compute and identical for every user in a tenant during
# a 30s window. We bucket by tenant_id; the cache value is the full
# JSON-serializable dict that `list_runtimes` returns plus a stamp.
#
# 30s is the same TTL ModelRegistry._MODEL_CACHE_TTL_SECONDS uses, so
# pulling the model catalog through this layer doesn't out-stale the
# inner cache.
_RUNTIMES_CACHE_TTL_SECONDS = 30.0
_runtimes_cache: dict[str, tuple[float, dict]] = {}


def _invalidate_runtimes_cache(tenant_id: str | None = None) -> None:
    """Clear the per-tenant runtimes cache.

    Called after any state-changing endpoint (set primary, disconnect,
    rediscover) so the next /runtimes hit returns fresh data.
    """
    if tenant_id is None:
        _runtimes_cache.clear()
    else:
        _runtimes_cache.pop(tenant_id, None)


# ── Per-provider failure cache ──
#
# Each provider's `list_models()` can hang on a slow third-party API.
# We remember the last error per provider so the UI can show a useful
# message instead of "Connected (0 models)" or a generic spinner.
_provider_error_cache: dict[str, dict] = {}


def _record_provider_error(provider: str, message: str) -> None:
    _provider_error_cache[provider] = {
        "last_error_at": time.time(),
        "last_error_msg": message[:200],
    }


def _clear_provider_error(provider: str) -> None:
    _provider_error_cache.pop(provider, None)


@router.get("")
async def list_runtimes(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """List all registered runtimes with status and subscription info.

    Returns immediately with `warming: true` if the runtime registry
    has not finished its background scan yet (no synchronous discovery
    on the request path). Includes the user's persisted primary_runtime
    selection. Per-tenant 30s cache.
    """
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.core.events import get_runtime_registry
    from app.models.identity import User

    tenant_id = str(user.tenant_id)

    # ── Cache hit fast path ──
    cached = _runtimes_cache.get(tenant_id)
    if cached is not None:
        ts, payload = cached
        if (time.monotonic() - ts) < _RUNTIMES_CACHE_TTL_SECONDS:
            return {"success": True, "data": payload, "cache_hit": True}

    registry = get_runtime_registry()

    # ── Warming gate ──
    # Previous behavior: if registry empty, do `discover_all + check_health_all
    # + check_subscriptions_all` synchronously -- could hang for many seconds.
    # New behavior: return `warming: true` and let the frontend poll. The
    # background scan from main.py lifespan deferred phase will populate
    # the registry; our /runtimes 30s cache rebuilds when it does.
    is_warming = not any(registry._installed_cache.values())

    # Read user's persisted primary_runtime from settings JSONB
    primary_runtime = "claude_code"  # default
    try:
        async with async_session_factory() as db:
            stmt = select(User).where(User.id == user.id)
            result = await db.execute(stmt)
            db_user = result.scalar_one_or_none()
            if db_user and db_user.settings:
                primary_runtime = db_user.settings.get("primary_runtime", "claude_code")
    except Exception as exc:
        logger.debug("runtimes.primary_runtime_lookup_failed", error=str(exc))

    data = registry.to_dict()
    data["primary_runtime"] = primary_runtime
    data["warming"] = is_warming

    # Cloud mode detection: True when Ollama is not reachable or no local
    # runtimes installed.
    from app.core.config import get_settings

    settings = get_settings()
    ollama_url = (settings.ollama_base_url or "").strip()
    no_local_runtimes = not any(registry._installed_cache.values())
    data["cloud_mode"] = not bool(ollama_url) or no_local_runtimes

    # ── API providers with configured keys + parallel model enumeration ──
    from app.core.constants import ModelProvider

    provider_map = [
        ("groq_api_key", "Groq", "Groq Cloud", ModelProvider.GROQ),
        ("gemini_api_key", "Gemini", "Google Gemini", ModelProvider.GEMINI),
        ("anthropic_api_key", "Anthropic", "Anthropic Claude", ModelProvider.ANTHROPIC),
        ("openai_api_key", "OpenAI", "OpenAI", ModelProvider.OPENAI),
        ("openrouter_api_key", "OpenRouter", "OpenRouter", ModelProvider.OPENROUTER),
        ("together_api_key", "Together", "Together AI", ModelProvider.TOGETHER),
        ("perplexity_api_key", "Perplexity", "Perplexity AI", ModelProvider.PERPLEXITY),
    ]
    model_registry = getattr(request.app.state, "model_registry", None)

    # Build the list of providers that actually have credentials, then
    # gather their list_models() calls in parallel. Was previously a
    # sequential for-loop -- 7 providers x ~500ms = 3.5s blocking. Now
    # the slowest provider sets the response time, not the sum.
    enabled_providers: list[tuple[str, str, str, object]] = []
    for attr, provider, display_name, p_enum in provider_map:
        key_value = (getattr(settings, attr, "") or "").strip()
        if not key_value:
            continue
        prov = model_registry.get_provider(p_enum) if model_registry else None
        enabled_providers.append((provider, display_name, attr, prov))

    async def _safe_list_models(provider: str, prov: object | None) -> list[dict]:
        """Run prov.list_models() with a 5s ceiling; cache failures."""
        if prov is None:
            return []
        try:
            models = await asyncio.wait_for(prov.list_models(), timeout=5.0)
        except asyncio.TimeoutError:
            _record_provider_error(provider, "list_models() timed out (5s)")
            logger.warning("runtimes.models_timeout", provider=provider)
            return []
        except Exception as exc:
            _record_provider_error(provider, f"{type(exc).__name__}: {exc}")
            logger.warning(
                "runtimes.models_enum_failed",
                provider=provider,
                error=str(exc),
            )
            return []
        _clear_provider_error(provider)
        return [
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "context_window": m.context_window,
                "supports_vision": m.supports_vision,
                "supports_tools": m.supports_tools,
                "tags": list(m.tags),
                "cost_per_1m_input": m.cost_per_1m_input,
                "cost_per_1m_output": m.cost_per_1m_output,
            }
            for m in models
        ]

    # Parallel fan-out. Note: these are httpx calls per provider, NOT
    # shared DB sessions, so this gather is safe (see Phase 2 audit).
    model_lists = await asyncio.gather(
        *[_safe_list_models(provider, prov) for provider, _, _, prov in enabled_providers],
        return_exceptions=False,
    )

    api_providers = []
    for (provider, display_name, _attr, _prov), models_payload in zip(
        enabled_providers, model_lists
    ):
        provider_entry: dict = {
            "provider": provider,
            "status": "connected" if not _provider_error_cache.get(provider) else "degraded",
            "display_name": display_name,
            "models": models_payload,
            "model_count": len(models_payload),
        }
        # Surface the failure reason inline so the UI can render
        # "Gemini /models timed out 14s ago" instead of a stuck spinner.
        err = _provider_error_cache.get(provider)
        if err:
            provider_entry["last_error_at"] = err["last_error_at"]
            provider_entry["last_error_msg"] = err["last_error_msg"]
        api_providers.append(provider_entry)
    data["api_providers"] = api_providers

    # ── Cache the assembled payload ──
    _runtimes_cache[tenant_id] = (time.monotonic(), data)

    return {"success": True, "data": data, "cache_hit": False}


# Static paths MUST come before /{runtime_id} to avoid path param capture
@router.post("/discover")
async def rediscover_runtimes(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Force re-discovery of all runtimes (installed, health, subscriptions)."""
    from app.core.events import get_runtime_registry

    registry = get_runtime_registry()
    installed = await registry.discover_all()
    health = await registry.check_health_all()
    registry._subscription_cache.clear()
    await registry.check_subscriptions_all()

    # Invalidate the per-tenant runtimes cache so the next /runtimes
    # GET picks up the freshly-scanned state.
    _invalidate_runtimes_cache()

    return {
        "success": True,
        "data": {
            "installed": {k: v for k, v in installed.items() if v},
            "health": {k: v.value for k, v in health.items()},
            "registry": registry.to_dict(),
        },
    }


@router.get("/{runtime_id}")
async def get_runtime(
    runtime_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get detailed info for a single runtime."""
    from app.core.events import get_runtime_registry

    registry = get_runtime_registry()
    adapter = registry.get_adapter(runtime_id)
    if adapter is None:
        return {"success": False, "error": {"message": f"Runtime '{runtime_id}' not found"}}

    caps = await registry.get_capabilities(runtime_id)
    sub_auth = await registry.check_subscription(runtime_id)

    return {
        "success": True,
        "data": {
            "runtime_id": runtime_id,
            "display_name": adapter.display_name,
            "installed": registry._installed_cache.get(runtime_id, False),
            "status": registry.get_health(runtime_id).value,
            "capabilities": caps.to_dict(),
            "auth_requirements": adapter.get_auth_requirements(),
            "subscription": sub_auth.to_dict() if sub_auth else None,
        },
    }


@router.post("/{runtime_id}/refresh-auth")
async def refresh_runtime_auth(
    runtime_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Force re-check subscription status for a runtime."""
    from app.core.events import get_runtime_registry

    registry = get_runtime_registry()
    adapter = registry.get_adapter(runtime_id)
    if adapter is None:
        return {"success": False, "error": {"message": f"Runtime '{runtime_id}' not found"}}

    # Clear cache and re-check
    registry._subscription_cache.pop(runtime_id, None)
    sub_auth = await registry.check_subscription(runtime_id)
    _invalidate_runtimes_cache()

    return {
        "success": True,
        "data": {
            "runtime_id": runtime_id,
            "subscription": sub_auth.to_dict() if sub_auth else None,
        },
    }


@router.post("/{runtime_id}/test")
async def test_runtime_connection(
    runtime_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Two-stage runtime health check: binary reachable AND auth valid.

    Previous behaviour was a `--version` probe only. That returned OK
    for a runtime whose binary works but whose token is expired, so the
    UI claimed "Test passed" while real chat hit 401. Now we run BOTH:
      1. Binary probe (--version or HTTP /api/tags for Ollama)
      2. check_subscription() — confirms the runtime is actually
         authenticated and ready to answer LLM requests.
    test_passed is the AND of both. The response surfaces individual
    statuses so the UI can show "Binary OK but not logged in" instead
    of a misleading green check.
    """
    from app.core.events import get_runtime_registry

    registry = get_runtime_registry()
    adapter = registry.get_adapter(runtime_id)
    if adapter is None:
        return {"success": False, "error": {"message": f"Runtime '{runtime_id}' not found"}}

    if not registry._installed_cache.get(runtime_id, False):
        return {
            "success": False,
            "error": {"message": f"Runtime '{runtime_id}' is not installed"},
        }

    t0 = time.perf_counter()
    binary_ok = False
    binary_response = ""
    auth_ok = False
    auth_detail = ""

    # ── Stage 1: binary probe ──
    try:
        import subprocess
        version_cmd = getattr(adapter, '_claude_bin', None) or getattr(adapter, '_codex_bin', None) or getattr(adapter, 'binary_path', None)
        if version_cmd:
            proc = await asyncio.to_thread(
                subprocess.run,
                [version_cmd, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            binary_response = (proc.stdout.strip() or proc.stderr.strip())[:500]
            binary_ok = len(binary_response) > 0
        else:
            # Ollama HTTP path
            import httpx
            base_url = getattr(adapter, '_base_url', 'http://localhost:11434')
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/api/tags")
                model_count = len(resp.json().get("models", []))
                binary_response = f"Ollama HTTP OK: {model_count} models loaded"
                binary_ok = model_count >= 0
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": {"message": "Binary probe timed out (10s)", "runtime_id": runtime_id},
        }
    except Exception as exc:
        binary_response = f"Binary probe failed: {exc}"
        binary_ok = False

    # ── Stage 2: auth probe (the one that catches "logged out but binary works") ──
    try:
        sub = await asyncio.wait_for(adapter.check_subscription(), timeout=10.0)
        auth_ok = bool(getattr(sub, "is_authenticated", False))
        plan = getattr(sub, "plan_name", None)
        auth_detail = (
            f"Authenticated as {plan}" if auth_ok and plan
            else "Authenticated" if auth_ok
            else "Not authenticated — run the runtime's login command"
        )
    except asyncio.TimeoutError:
        auth_detail = "Auth probe timed out (10s)"
    except Exception as exc:
        auth_detail = f"Auth probe failed: {exc}"

    latency_ms = int((time.perf_counter() - t0) * 1000)
    test_passed = binary_ok and auth_ok

    return {
        "success": True,
        "data": {
            "runtime_id": runtime_id,
            "test_passed": test_passed,
            "binary_ok": binary_ok,
            "auth_ok": auth_ok,
            "latency_ms": latency_ms,
            "response": binary_response,
            "auth_detail": auth_detail,
            # Actionable user-facing summary
            "summary": (
                "All systems go" if test_passed
                else "Logged out — run the runtime's login command" if binary_ok and not auth_ok
                else "Binary unreachable" if not binary_ok
                else "Unknown failure"
            ),
        },
    }


class PrimaryRuntimeRequest(BaseModel):
    runtime_id: str
    # Phase 5 PR 2: when V2 flag is on, only callable runtimes can be
    # selected as Main Brain. Founder can opt-in to experimental override
    # to pin a non-callable runtime (recorded in audit log).
    experimental_override: bool = False


@router.put("/primary")
async def set_primary_runtime(
    body: PrimaryRuntimeRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Set the primary runtime (mind) for this user.

    The primary runtime handles EXE mode tasks, Council synthesis,
    and complex reasoning. Persisted in user settings JSONB.
    """
    from sqlalchemy import select

    from app.models.identity import User

    # Validate runtime/provider exists.
    #
    # Runtime IDs (claude_code, codex, gemini_cli, ollama) are handled by
    # RuntimeRegistry adapters. API provider values (OPENAI, PERPLEXITY,
    # ANTHROPIC, GEMINI, GROQ, etc.) are already understood by ModelRouter
    # as Primary Mind boosts, but this endpoint used to reject them because
    # it only checked adapters. That made the UI unable to select GPT or
    # Perplexity as Main Brain even though the execution loop knew how to
    # honor that value.
    from app.core.events import get_runtime_registry
    from app.core.config import get_settings
    from app.core.constants import ModelProvider

    registry = get_runtime_registry()
    adapter = registry.get_adapter(body.runtime_id)
    display_name = adapter.display_name if adapter else body.runtime_id
    provider_value: str | None = None

    # Phase 5 PR 2: V2 callable gate.
    #
    # When USE_CONNECTION_REGISTRY_V2 is on, refuse to pin a runtime
    # whose V2 row is not callable=True UNLESS the request opts in
    # via experimental_override=True. The override is logged below
    # so the audit trail captures who pinned a non-callable brain.
    from app.services.connection_v2.legacy_bridge import is_v2_enabled

    callable_check_skipped_reason: str | None = None
    if is_v2_enabled() and adapter is not None:
        from app.core.database import async_session_factory as _async_factory
        from app.models.connection_v2 import (
            ConnectionKind as _Kind,
            ConnectionV2 as _CV2,
        )
        from sqlalchemy import select as _select

        async with _async_factory() as _db:
            v2_row = (await _db.execute(
                _select(_CV2).where(
                    _CV2.tenant_id == user.tenant_id,
                    _CV2.kind == _Kind.CLI_RUNTIME.value,
                    _CV2.slug == body.runtime_id,
                )
            )).scalar_one_or_none()
        if v2_row is None:
            # No V2 row for this runtime yet -- allow but tag.
            callable_check_skipped_reason = (
                "no V2 row yet (legacy probe path; will be checked on next "
                "real probe via ConnectionRegistryV2)"
            )
        elif not v2_row.callable and not body.experimental_override:
            # Refuse the selection.
            from app.core.logging import get_logger
            _l = get_logger(__name__)
            _l.warning(
                "runtimes.primary_refused_not_callable",
                runtime_id=body.runtime_id,
                tenant_id=str(user.tenant_id),
                user_id=str(user.id),
                v2_label="not_callable",
            )
            return {
                "success": False,
                "error": {
                    "message": (
                        f"{display_name} cannot be set as Main Brain because "
                        f"its last probe did not prove callable. Run a probe "
                        f"first, or pass experimental_override=true to pin "
                        f"anyway (logged)."
                    ),
                    "code": "runtime_not_callable",
                    "v2_callable": False,
                    "v2_truth": {
                        "detected": v2_row.detected,
                        "configured": v2_row.configured,
                        "imported": v2_row.imported,
                        "reachable": v2_row.reachable,
                        "authenticated": v2_row.authenticated,
                        "callable": v2_row.callable,
                    },
                },
            }
        elif not v2_row.callable and body.experimental_override:
            # Founder override accepted -- audit this loudly.
            from app.core.logging import get_logger
            _l = get_logger(__name__)
            _l.warning(
                "runtimes.primary_override_not_callable",
                runtime_id=body.runtime_id,
                tenant_id=str(user.tenant_id),
                user_id=str(user.id),
                role=getattr(user, "role", "unknown"),
                v2_label="not_callable_overridden",
            )

    if adapter is None:
        normalized = body.runtime_id.strip().upper()
        try:
            provider = ModelProvider(normalized)
        except ValueError:
            return {
                "success": False,
                "error": {"message": f"Runtime/provider '{body.runtime_id}' not found"},
            }

        provider_key_attrs = {
            ModelProvider.GROQ: "groq_api_key",
            ModelProvider.GEMINI: "gemini_api_key",
            ModelProvider.ANTHROPIC: "anthropic_api_key",
            ModelProvider.OPENAI: "openai_api_key",
            ModelProvider.OPENROUTER: "openrouter_api_key",
            ModelProvider.TOGETHER: "together_api_key",
            ModelProvider.PERPLEXITY: "perplexity_api_key",
            ModelProvider.OLLAMA: "ollama_base_url",
            ModelProvider.VLLM: "vllm_base_url",
        }
        settings_obj = get_settings()
        configured_value = getattr(settings_obj, provider_key_attrs.get(provider, ""), "")
        if (
            provider not in (ModelProvider.OLLAMA, ModelProvider.VLLM)
            and not (configured_value or "").strip()
        ):
            return {
                "success": False,
                "error": {
                    "message": (
                        f"{provider.value} is not configured. Add its key in Settings > Models "
                        "before selecting it as Main Brain."
                    )
                },
            }
        provider_value = provider.value
        display_name = provider.value.title()

    # Persist to user settings
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        stmt = select(User).where(User.id == user.id)
        result = await db.execute(stmt)
        db_user = result.scalar_one_or_none()
        if db_user is None:
            return {
                "success": False,
                "error": {"message": "User row not found; Main Brain was not saved"},
            }
        settings = dict(db_user.settings) if db_user.settings else {}
        selected_runtime = provider_value or body.runtime_id
        settings["primary_runtime"] = selected_runtime
        db_user.settings = settings
        await db.commit()

        verify_result = await db.execute(stmt)
        verified_user = verify_result.scalar_one_or_none()
        verified_runtime = (verified_user.settings or {}).get("primary_runtime") if verified_user else None
        if verified_runtime != selected_runtime:
            return {
                "success": False,
                "error": {"message": "Main Brain write verification failed"},
            }

    _invalidate_runtimes_cache(str(user.tenant_id))

    return {
        "success": True,
        "data": {
            "primary_runtime": provider_value or body.runtime_id,
            "display_name": display_name,
            "callable_check_skipped_reason": callable_check_skipped_reason,
            "experimental_override_used": (
                body.experimental_override and adapter is not None
            ),
        },
    }


@router.post("/{runtime_id}/disconnect")
async def disconnect_runtime(
    runtime_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Mark a runtime as disconnected + auto-promote a new primary if needed.

    Previously this only flipped an in-memory cache, which left the
    orchestrator still pointing at a dead primary. Now we ALSO check if
    the disconnected runtime was the user's primary; if so, we promote
    the first remaining authenticated runtime so the next chat works.
    """
    from app.core.events import get_runtime_registry
    from app.core.database import async_session_factory
    from app.core.logging import get_logger
    from app.models.identity import User
    from sqlalchemy import select

    logger = get_logger(__name__)

    registry = get_runtime_registry()
    adapter = registry.get_adapter(runtime_id)
    if adapter is None:
        return {"success": False, "error": {"message": f"Runtime '{runtime_id}' not found"}}

    # Clear cached install/auth state so UI shows disconnected immediately.
    registry._installed_cache[runtime_id] = False
    registry._auth_cache.pop(runtime_id, None)

    # Auto-promote next healthy runtime to primary if we just killed it.
    promoted: str | None = None
    async with async_session_factory() as db:
        stmt = select(User).where(User.id == user.id)
        result = await db.execute(stmt)
        db_user = result.scalar_one_or_none()
        if db_user and db_user.settings:
            current_primary = db_user.settings.get("primary_runtime")
            if current_primary == runtime_id:
                # Walk the standard preference order looking for the first
                # runtime that is still installed AND authenticated.
                for candidate in ("claude_code", "codex", "gemini_cli", "grok_cli", "ollama"):
                    if candidate == runtime_id:
                        continue
                    if not registry._installed_cache.get(candidate, False):
                        continue
                    cand_adapter = registry.get_adapter(candidate)
                    if cand_adapter is None:
                        continue
                    try:
                        sub = await asyncio.wait_for(
                            cand_adapter.check_subscription(),
                            timeout=5.0,
                        )
                        if getattr(sub, "is_authenticated", False):
                            promoted = candidate
                            break
                    except Exception:
                        continue
                if promoted:
                    settings = dict(db_user.settings)
                    settings["primary_runtime"] = promoted
                    db_user.settings = settings
                    await db.commit()
                    logger.info(
                        "runtimes.primary_auto_promoted",
                        from_runtime=runtime_id,
                        to_runtime=promoted,
                        user_id=str(user.id),
                    )

    _invalidate_runtimes_cache(str(user.tenant_id))

    return {
        "success": True,
        "data": {
            "runtime_id": runtime_id,
            "status": "disconnected",
            "primary_promoted_to": promoted,
        },
    }
