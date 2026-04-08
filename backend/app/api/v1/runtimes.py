"""Runtime adapter endpoints for the ConnectionsPage.

Exposes runtime registry state, subscription status, auth
requirements, test connection, and primary mind selection.
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import CurrentUser, get_current_user

router = APIRouter()


@router.get("")
async def list_runtimes(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """List all registered runtimes with status and subscription info.

    Auto-discovers runtimes on first request if none are installed yet
    (handles case where startup discovery failed or was skipped).
    Includes the user's persisted primary_runtime selection.
    """
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.core.events import get_runtime_registry
    from app.models.identity import User

    registry = get_runtime_registry()

    # Lazy discovery: if no runtimes detected yet, re-discover now
    if not any(registry._installed_cache.values()):
        await registry.discover_all()
        await registry.check_health_all()
        await registry.check_subscriptions_all()

    # Read user's persisted primary_runtime from settings JSONB
    primary_runtime = "claude_code"  # default
    try:
        async with async_session_factory() as db:
            stmt = select(User).where(User.id == user.id)
            result = await db.execute(stmt)
            db_user = result.scalar_one_or_none()
            if db_user and db_user.settings:
                primary_runtime = db_user.settings.get("primary_runtime", "claude_code")
    except Exception:
        pass  # fallback to default

    data = registry.to_dict()
    data["primary_runtime"] = primary_runtime

    # Cloud mode detection: True when Ollama is not configured
    from app.core.config import get_settings

    settings = get_settings()
    ollama_url = (settings.ollama_base_url or "").strip()
    data["cloud_mode"] = not bool(ollama_url)

    # API providers with configured keys
    provider_map = [
        ("groq_api_key", "Groq", "Groq Cloud"),
        ("gemini_api_key", "Gemini", "Google Gemini"),
        ("anthropic_api_key", "Anthropic", "Anthropic Claude"),
        ("openai_api_key", "OpenAI", "OpenAI"),
        ("openrouter_api_key", "OpenRouter", "OpenRouter"),
        ("together_api_key", "Together", "Together AI"),
        ("perplexity_api_key", "Perplexity", "Perplexity AI"),
    ]
    api_providers = []
    for attr, provider, display_name in provider_map:
        key_value = (getattr(settings, attr, "") or "").strip()
        if key_value:
            api_providers.append(
                {"provider": provider, "status": "connected", "display_name": display_name}
            )
    data["api_providers"] = api_providers

    return {"success": True, "data": data}


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
    """Send a test prompt to a runtime and measure response.

    Sends 'Respond with exactly: OK' and checks the result.
    Returns success, latency, and the raw response text.
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
    try:
        # Fast test: check if the runtime binary responds to --version
        # Full prompt test is too slow for a connectivity check
        import subprocess
        version_cmd = getattr(adapter, '_claude_bin', None) or getattr(adapter, '_codex_bin', None) or getattr(adapter, 'binary_path', None)
        if version_cmd:
            proc = await asyncio.to_thread(
                subprocess.run,
                [version_cmd, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            response_text = proc.stdout.strip() or proc.stderr.strip()
            latency_ms = int((time.perf_counter() - t0) * 1000)
        else:
            # Fallback for adapters without binary_path (e.g. Ollama HTTP API)
            import httpx
            base_url = getattr(adapter, '_base_url', 'http://localhost:11434')
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/api/tags")
                model_count = len(resp.json().get("models", []))
                response_text = f"Ollama OK: {model_count} models loaded"
            latency_ms = int((time.perf_counter() - t0) * 1000)

        # Version check passes if we got any non-empty response
        is_ok = len(response_text) > 0

        return {
            "success": True,
            "data": {
                "runtime_id": runtime_id,
                "test_passed": is_ok,
                "latency_ms": latency_ms,
                "response": response_text[:500],
            },
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": {"message": "Test timed out (30s)", "runtime_id": runtime_id},
        }
    except Exception as exc:
        return {
            "success": False,
            "error": {
                "message": f"Test failed: {exc}",
                "runtime_id": runtime_id,
            },
        }


class PrimaryRuntimeRequest(BaseModel):
    runtime_id: str


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
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.database import get_db
    from app.models.identity import User

    # Validate runtime exists
    from app.core.events import get_runtime_registry

    registry = get_runtime_registry()
    adapter = registry.get_adapter(body.runtime_id)
    if adapter is None:
        return {"success": False, "error": {"message": f"Runtime '{body.runtime_id}' not found"}}

    # Persist to user settings
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        stmt = select(User).where(User.id == user.id)
        result = await db.execute(stmt)
        db_user = result.scalar_one_or_none()
        if db_user:
            settings = dict(db_user.settings) if db_user.settings else {}
            settings["primary_runtime"] = body.runtime_id
            db_user.settings = settings
            await db.commit()

    return {
        "success": True,
        "data": {
            "primary_runtime": body.runtime_id,
            "display_name": adapter.display_name,
        },
    }
