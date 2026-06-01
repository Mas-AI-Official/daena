"""System self-diagnostic endpoint.

PR-DAENA-SELF-DIAGNOSTIC-RUNTIME-AWARENESS (Sprint-6 PR-7, 2026-05-04).

Single read-only endpoint that aggregates the operator-visible
"is everything OK?" picture so Daena can speak to her own runtime
state in chat without dumping individual subsystem checks.

What the endpoint returns
-------------------------

A structured diagnostic with:

  * ``overall_status``: ``healthy`` / ``warning`` / ``blocked``
    -- conservative aggregator, the worst sub-status wins.
  * ``timestamp``: ISO-8601 UTC.
  * ``checks``: per-subsystem dict (each carries ``status`` +
    ``detail`` only -- no secrets, no env values, no token state).
  * ``recommended_actions``: ordered list of plain-English strings.
    Deterministic given the same checks payload (fixture-friendly).

Honesty rules
-------------

* Absolutely no secret read or print. Every check verifies presence
  via ``getattr(settings, "...")`` and emits only the boolean
  presence bit -- the actual value never leaves the process.
* Frontend reachable check is a localhost-only HTTP HEAD with a
  short timeout. If it fails (frontend stopped, port renumbered),
  the field is just ``reachable=False`` -- not an error that
  poisons the whole diagnostic.
* No automatic fix actions. Per the Sprint-6 brief, this PR makes
  Daena AWARE of her runtime state but never modifies system
  settings, kills processes, or runs migrations on the operator's
  behalf. Recommended actions are advisory text the operator (or
  a future approval-gated automation) acts on.
"""

from __future__ import annotations

import asyncio
import time as _time
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.config import get_settings
from app.core.db_concurrent import gather_with_sessions
from app.core.logging import get_logger
from app.services.connection_v2.marketplace_service import MarketplaceService


logger = get_logger(__name__)
router = APIRouter()


# ── Sprint-12A PR-1/2: runtime + router readiness ────────────────────


@router.get("/runtime-readiness")
async def runtime_readiness(
    refresh: bool = False,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the readiness inventory + router summary.

    Aggregates ``runtime_truth_registry`` items (CLIs, local LLM
    endpoints, API providers) with the operational overlay
    (cost_class, recommended_role, readiness_state). NEVER returns
    secret values.

    Query param:
        refresh: when true, re-discover items first. Default false
            so the endpoint stays cheap.
    """
    from app.services.runtime_readiness import get_runtime_readiness
    return {"success": True, "data": await get_runtime_readiness(refresh=refresh)}


@router.get("/router-readiness")
async def router_readiness(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return only the router_summary slice -- 'who would Daena pick
    for each role right now'. Lightweight surface for chat / status
    pills that don't need the full inventory."""
    from app.services.runtime_readiness import get_runtime_readiness
    full = await get_runtime_readiness(refresh=False)
    return {"success": True, "data": full.get("router_summary")}


@router.get("/router-policy")
async def router_policy(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the static router policy matrix (no I/O).

    Lets the UI render "where would Daena route X" without first
    refreshing the truth registry.
    """
    from app.services.runtime_readiness import get_router_policy
    return {"success": True, "data": get_router_policy()}


@router.get("/qe-readiness")
async def qe_readiness(
    refresh: bool = False,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the QE/Council slot assignment.

    Five reviewer slots: local_reasoner, code_reviewer, web_grounder,
    risk_reviewer, final_synthesizer. Each slot resolves to a ready
    runtime (or 'unfilled' with rationale). Mode is full / degraded /
    unavailable per the readiness ladder.
    """
    from app.services.runtime_readiness import get_qe_readiness
    return {"success": True, "data": await get_qe_readiness(refresh=refresh)}


# ── Sprint-MORNING PR-4: ecosystem morning-readiness aggregator ──────


@router.get("/morning-readiness")
async def morning_readiness(
    refresh: bool = False,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Aggregate the "ready for VP work?" view across CLIs, local LLMs,
    API providers, and detected MCPs.

    Pure read-only. NEVER returns secret values -- only presence flags
    (booleans) for env-var names. The endpoint is the single backend
    surface MorningReadinessPanel reads to render its summary; no other
    round-trips required.

    Buckets:
      * cli_runtimes  -- Claude / Codex / Gemini / etc.
      * local_llms    -- Ollama, llama-server, vLLM
      * api_providers -- OpenAI, Anthropic, Gemini, Groq, Perplexity, etc.
      * detected_mcps -- MCPs already configured in OTHER CLIs that
                        Daena could one-click import.
    """
    from app.services.runtime_readiness import get_runtime_readiness

    runtime = await get_runtime_readiness(refresh=refresh)
    items: list[dict[str, object]] = list(runtime.get("items") or [])

    def _by_kind(kind: str) -> list[dict[str, object]]:
        return [i for i in items if i.get("kind") == kind]

    def _ready_count(rows: list[dict[str, object]]) -> int:
        return sum(
            1 for r in rows
            if r.get("readiness_state") == "ready"
        )

    cli_rows = _by_kind("cli_runtime")
    llm_rows = _by_kind("local_llm")
    api_rows = _by_kind("api_provider")

    # Detected MCPs (best-effort: never raise if scanner fails).
    # NEVER expose env values -- only server name + source CLI + command.
    detected_items: list[dict[str, object]] = []
    detected_total = 0
    detected_error: str | None = None
    try:
        from app.services.mcp_sync.detector import CLIMCPDetector
        merged = await CLIMCPDetector().discover_all()
        detected_total = len(merged)
        for m in merged[:20]:
            detected_items.append({
                "name": m.name,
                "from_cli": m.source_cli,
                "command": m.command,
                # env intentionally redacted -- env values may carry tokens
            })
    except Exception as exc:  # noqa: BLE001 -- best-effort
        detected_error = str(exc)[:200]

    # Compose blockers (operator-actionable).
    blockers: list[str] = []
    if _ready_count(llm_rows) == 0 and _ready_count(cli_rows) == 0:
        blockers.append(
            "No local LLM and no CLI runtime detected. Start "
            "llama-server / Ollama, or install Claude / Codex / Gemini CLI.",
        )
    if _ready_count(llm_rows) == 0:
        blockers.append("No local LLM reachable. Free-tier work falls back to CLI subscription.")
    if not any(_env_present_for(api) for api in api_rows):
        blockers.append("No paid API key configured. Daena runs free-tier only.")

    summary = {
        "cli_runtimes": _summarize(cli_rows),
        "local_llms": _summarize(llm_rows),
        "api_providers": _summarize(api_rows),
        "detected_mcps": {
            "total": detected_total,
            "items": detected_items,
            "scan_error": detected_error,
        },
        "blockers": blockers,
        # Sprint-MORNING PR-5: per-row fixes the operator can copy or
        # click. Daena proposes; never auto-runs an OS install. Every
        # action is either a string command (for the operator to paste
        # into a terminal) or a deep link to a settings page.
        "autofix_proposals": _build_autofix_proposals(
            cli_rows, llm_rows, api_rows,
        ),
        "ready_for_morning_work": (
            len(blockers) == 0
            or _ready_count(cli_rows) > 0
            or _ready_count(llm_rows) > 0
        ),
    }
    return {"success": True, "data": summary}


def _build_autofix_proposals(
    cli_rows: list[dict[str, object]],
    llm_rows: list[dict[str, object]],
    api_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Map readiness state to operator-actionable proposals.

    Each proposal carries:
      * ``id`` -- stable id for dedupe + UI key
      * ``title`` -- short headline
      * ``rationale`` -- one-line "why this would help"
      * ``copy_command`` -- string the operator can paste, or null
      * ``deep_link`` -- frontend route, or null
      * ``severity`` -- info / warn / blocker

    Daena proposes; never auto-executes. The frontend renders a copy
    button or a router link, never an "auto-run" button.
    """
    proposals: list[dict[str, object]] = []

    # Local LLM offline -> propose start commands (informational; the
    # operator chooses which one runs).
    for llm in llm_rows:
        state = llm.get("readiness_state")
        item_id = str(llm.get("id") or "")
        if state == "ready":
            continue
        if "ollama" in item_id:
            proposals.append({
                "id": f"start_{item_id}",
                "title": f"Start {llm.get('display_name')}",
                "rationale": "Free local main brain. No subscription needed.",
                "copy_command": "ollama serve",
                "deep_link": None,
                "severity": "warn",
            })
        if "llama" in item_id or "vllm" in item_id:
            proposals.append({
                "id": f"start_{item_id}",
                "title": f"Start {llm.get('display_name')}",
                "rationale": "Local OpenAI-compatible LLM. Free, faster than CLI runtimes for short prompts.",
                "copy_command": (
                    "powershell -ExecutionPolicy Bypass "
                    "-File backend/start-llama-server.ps1 -Model qwen3-8b"
                ),
                "deep_link": None,
                "severity": "warn",
            })

    # CLI runtime offline -> install/login hint (text only, no auto-install).
    for cli in cli_rows:
        state = cli.get("readiness_state")
        item_id = str(cli.get("id") or "")
        if state == "ready":
            continue
        if "claude" in item_id:
            proposals.append({
                "id": f"install_{item_id}",
                "title": "Install or authenticate Claude Code CLI",
                "rationale": "Subscription brain; native MCP / browser tools.",
                "copy_command": "npm install -g @anthropic-ai/claude-code && claude login",
                "deep_link": None,
                "severity": "info",
            })
        if "codex" in item_id:
            proposals.append({
                "id": f"install_{item_id}",
                "title": "Install or authenticate Codex CLI",
                "rationale": "Subscription brain; strong on tight algorithmic / async tasks.",
                "copy_command": "npm install -g @openai/codex && codex login",
                "deep_link": None,
                "severity": "info",
            })
        if "gemini" in item_id:
            proposals.append({
                "id": f"install_{item_id}",
                "title": "Install or authenticate Gemini CLI",
                "rationale": "Subscription brain; large context window.",
                "copy_command": "npm install -g @google/gemini-cli && gemini login",
                "deep_link": None,
                "severity": "info",
            })

    # API key not configured -> deep-link to Connections (no copy command;
    # secret entry happens in the UI via vault).
    for api in api_rows:
        state = api.get("readiness_state")
        configured = bool(api.get("configured"))
        if state == "ready" or configured:
            continue
        proposals.append({
            "id": f"set_key_{api.get('id')}",
            "title": f"Add {api.get('display_name')} API key",
            "rationale": (
                "Optional: enables metered fallback when local + CLI brains aren't enough. "
                "Daena will only call paid APIs when allow_metered=true is set per-call."
            ),
            "copy_command": None,
            "deep_link": "/settings/connections",
            "severity": "info",
        })

    # Configured-untested provider -> propose a test (text only; we don't
    # fire the call).
    for api in api_rows:
        if api.get("readiness_state") == "configured_untested":
            proposals.append({
                "id": f"test_{api.get('id')}",
                "title": f"Test {api.get('display_name')} reachability",
                "rationale": "Provider key is set but Daena hasn't verified the connection yet.",
                "copy_command": None,
                "deep_link": "/settings/models-runtimes",
                "severity": "info",
            })

    return proposals


def _summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    """One-bucket summary: id list with readiness_state + cost_class."""
    return {
        "total": len(rows),
        "ready": sum(
            1 for r in rows
            if r.get("readiness_state") == "ready"
        ),
        "items": [
            {
                "id": r.get("id"),
                "display_name": r.get("display_name") or r.get("id"),
                "readiness_state": r.get("readiness_state"),
                "cost_class": r.get("cost_class"),
                "detected": bool(r.get("detected")),
                "configured": bool(r.get("configured")),
                "callable": bool(r.get("callable")),
                "endpoint": r.get("endpoint"),
                "next_action": r.get("safe_failure_reason"),
            }
            for r in rows
        ],
    }


def _env_present_for(api: dict[str, object]) -> bool:
    """True iff the API row is reported configured (env var present).

    Reads the runtime_readiness "configured" boolean -- never reads the
    secret itself.
    """
    return bool(api.get("configured"))


# Stable status taxonomy. The worst status anywhere in `checks` becomes
# overall_status (warning > healthy; blocked > warning).
STATUS_HEALTHY = "healthy"
STATUS_WARNING = "warning"
STATUS_BLOCKED = "blocked"

_STATUS_RANK = {
    STATUS_HEALTHY: 0,
    STATUS_WARNING: 1,
    STATUS_BLOCKED: 2,
}


def _worst(*statuses: str) -> str:
    """Return the most severe status in the input list."""
    if not statuses:
        return STATUS_HEALTHY
    return max(statuses, key=lambda s: _STATUS_RANK.get(s, 0))


# ──────────────────────────────────────────────────────────────────
# Sub-checks
# ──────────────────────────────────────────────────────────────────


async def _check_backend() -> dict[str, Any]:
    """Trivially healthy if the function executes -- the FastAPI
    router can only run if the process is up. Captured so the
    payload always has a backend entry."""
    return {
        "status": STATUS_HEALTHY,
        "detail": "backend process responsive",
    }


async def _check_database(db: AsyncSession) -> dict[str, Any]:
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        return {"status": STATUS_HEALTHY, "detail": "select 1 ok"}
    except Exception as exc:
        return {
            "status": STATUS_BLOCKED,
            "detail": f"db_query_failed: {type(exc).__name__}",
        }


async def _check_migration_head(db: AsyncSession) -> dict[str, Any]:
    """Read alembic_version.version_num. Absent table = migrations
    haven't been initialized; surfaced as warning (dev SQLite via
    create_all is fine but not ideal)."""
    try:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        row = result.scalar_one_or_none()
        if row is None:
            return {
                "status": STATUS_WARNING,
                "detail": "alembic_version table empty",
            }
        return {
            "status": STATUS_HEALTHY,
            "detail": "head present",
            "current": str(row),
        }
    except Exception as exc:
        # Table absent on dev SQLite via create_all path -- not a
        # blocker, just an indicator that migrations haven't been
        # explicitly run.
        return {
            "status": STATUS_WARNING,
            "detail": (
                f"alembic_version unreadable: {type(exc).__name__} "
                "(typical on dev SQLite via create_all)"
            ),
        }


async def _check_frontend_reachable() -> dict[str, Any]:
    """HEAD localhost:5173 with a short timeout. Frontend is
    optional from the backend's POV; reachable=False is informational
    not an error."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.request(
                "GET", "http://127.0.0.1:5173/",
            )
            ok = 200 <= resp.status_code < 500
            return {
                "status": STATUS_HEALTHY if ok else STATUS_WARNING,
                "detail": (
                    f"vite responded {resp.status_code}" if ok
                    else f"vite responded {resp.status_code} (unexpected)"
                ),
                "reachable": ok,
            }
    except Exception:
        return {
            "status": STATUS_WARNING,
            "detail": "vite not reachable on 127.0.0.1:5173",
            "reachable": False,
        }


async def _check_local_models() -> dict[str, Any]:
    """Probe the two configured local model endpoints (Ollama +
    llama-server / vLLM). Either being down is a warning, not a
    blocker -- Daena routes around them via cloud providers."""
    settings = get_settings()
    ollama_url = getattr(settings, "ollama_base_url", None)
    vllm_url = getattr(settings, "vllm_base_url", None)
    ollama_enabled = getattr(settings, "ollama_enabled", False)

    async def _probe(url: str | None, path: str) -> bool:
        if not url:
            return False
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(url.rstrip("/") + path)
                return 200 <= resp.status_code < 500
        except Exception:
            return False

    ollama_up = await _probe(ollama_url, "/api/tags") if ollama_enabled else False
    vllm_up = await _probe(vllm_url, "/models")

    if not ollama_enabled and not vllm_up:
        # User has disabled Ollama and no llama-server is up -- routes
        # will fall through to cloud providers, which is fine. Surface
        # as warning so the operator knows nothing local is online.
        return {
            "status": STATUS_WARNING,
            "detail": "ollama disabled, llama-server unreachable",
            "ollama_enabled": ollama_enabled,
            "ollama_up": False,
            "vllm_up": vllm_up,
        }
    if ollama_enabled and not ollama_up and not vllm_up:
        return {
            "status": STATUS_WARNING,
            "detail": "both ollama and vllm probes failed",
            "ollama_enabled": ollama_enabled,
            "ollama_up": False,
            "vllm_up": False,
        }
    return {
        "status": STATUS_HEALTHY,
        "detail": "at least one local endpoint responding",
        "ollama_enabled": ollama_enabled,
        "ollama_up": ollama_up,
        "vllm_up": vllm_up,
    }


async def _check_connector_callability(
    db: AsyncSession, tenant_id,
) -> dict[str, Any]:
    """Reuse the PR-2 marketplace diagnostic. Slimmer surface so
    the self-diagnostic stays under a couple hundred lines of JSON."""
    try:
        svc = MarketplaceService(db, tenant_id=tenant_id)
        summary = await svc.diagnostic_summary()
        totals = summary.get("totals", {})
        callable_count = totals.get("callable", 0)
        catalog = totals.get("catalog", 0)
        blocked = totals.get("blocked", 0)
        # 0 callable is the dominant local-laptop state; still useful
        # info but not a "blocked" status (Daena is fully usable for
        # chat without callable connectors).
        status = STATUS_HEALTHY if callable_count > 0 else STATUS_WARNING
        # Top blocker reason for the recommendations.
        top_blockers = summary.get("top_blockers", [])
        top_reason = top_blockers[0]["reason"] if top_blockers else None
        return {
            "status": status,
            "detail": f"{callable_count}/{catalog} callable; {blocked} blocked",
            "callable": callable_count,
            "catalog": catalog,
            "blocked": blocked,
            "top_blocker_reason": top_reason,
        }
    except Exception as exc:
        return {
            "status": STATUS_WARNING,
            "detail": f"diagnostic_summary failed: {type(exc).__name__}",
        }


def _recommended_actions(checks: dict[str, dict[str, Any]]) -> list[str]:
    """Deterministic list of next-step strings derived from the
    checks payload. Order: most actionable first.

    The text NEVER includes secret values. Each string is a
    recommendation the operator (or a future approval-gated
    automation) can act on.
    """
    out: list[str] = []
    db = checks.get("database") or {}
    if db.get("status") == STATUS_BLOCKED:
        out.append(
            "Database is unreachable. Check the .env DATABASE_URL "
            "and verify the service is running."
        )

    migration = checks.get("migration_head") or {}
    if migration.get("status") == STATUS_WARNING:
        out.append(
            "Run `alembic upgrade head` to bring the migration chain "
            "up to date (or seed the alembic_version table on a "
            "fresh dev SQLite if you want explicit version tracking)."
        )

    frontend = checks.get("frontend") or {}
    if not frontend.get("reachable", True):
        out.append(
            "Frontend is not reachable on http://127.0.0.1:5173. "
            "Run `scripts\\start-frontend-dev.bat` to start Vite."
        )

    local = checks.get("local_models") or {}
    if local.get("status") == STATUS_WARNING:
        if not local.get("ollama_enabled") and not local.get("vllm_up"):
            out.append(
                "No local LLM endpoint is online. Start "
                "llama-server.exe with a GGUF in MODELS_ROOT/gguf/, or "
                "set OLLAMA_ENABLED=true and start Ollama."
            )
        elif local.get("ollama_enabled") and not local.get("ollama_up"):
            out.append(
                "Ollama is enabled but its /api/tags probe failed. "
                "Confirm `ollama serve` is running."
            )

    callability = checks.get("connector_callability") or {}
    if callability.get("status") == STATUS_WARNING:
        catalog = callability.get("catalog", 0)
        callable_count = callability.get("callable", 0)
        if catalog > 0 and callable_count == 0:
            top = callability.get("top_blocker_reason") or "missing setup"
            out.append(
                f"{catalog} connectors in catalog, 0 callable. Top blocker: "
                f"{top}. Open Connections > Plugins to install or connect one."
            )

    if not out:
        out.append(
            "All checks pass. Daena's local runtime is healthy."
        )
    return out


# ──────────────────────────────────────────────────────────────────
# HTTP endpoint
# ──────────────────────────────────────────────────────────────────


@router.get("/self-diagnostic")
async def system_self_diagnostic(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return Daena's self-diagnostic snapshot.

    Auth-required (the diagnostic surfaces tenant-scoped connector
    counts via the marketplace summary). Read-only -- never modifies
    settings, never kills processes, never runs migrations.
    """
    started = _time.monotonic()

    checks = {}
    # Run the checks concurrently to keep the endpoint snappy (~1.5s
    # timeout each, but several can race).
    #
    # 2026-06-01: the network-only probes (no DB) race directly via
    # asyncio.gather. The DB-backed checks MUST NOT share the request
    # ``db`` session concurrently -- a single AsyncSession is not
    # concurrency-safe and raises InvalidRequestError ("this session is
    # provisioning a new connection; concurrent operations are not
    # permitted") under load. They each get their OWN fresh session via
    # gather_with_sessions. All three are read-only, so a separate
    # session per check is correct and side-effect-free.
    backend, frontend, local_models = await asyncio.gather(
        _check_backend(),
        _check_frontend_reachable(),
        _check_local_models(),
    )
    database, migration, callability = await gather_with_sessions(
        lambda s: _check_database(s),
        lambda s: _check_migration_head(s),
        lambda s: _check_connector_callability(s, user.tenant_id),
    )
    checks["backend"] = backend
    checks["database"] = database
    checks["migration_head"] = migration
    checks["frontend"] = frontend
    checks["local_models"] = local_models
    checks["connector_callability"] = callability

    overall = _worst(*[c["status"] for c in checks.values()])

    payload = {
        "data": {
            "overall_status": overall,
            "timestamp": datetime.now(UTC).isoformat(),
            "elapsed_ms": int((_time.monotonic() - started) * 1000),
            "checks": checks,
            "recommended_actions": _recommended_actions(checks),
            # Standing safety statement so any UI that surfaces this
            # never has to fabricate the boundary.
            "boundary_notice": (
                "Daena diagnoses local runtime state but does not "
                "modify OS / cloud / secrets without explicit "
                "operator approval."
            ),
        },
    }
    return JSONResponse(content=payload)


__all__ = ["router"]
