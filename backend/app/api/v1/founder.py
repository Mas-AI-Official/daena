"""Founder-only runtime diagnostics and routing policy management."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.core.config import get_settings
from app.core.constants import ChatMode, GovernanceMode, GovernanceSlider, RoutingMode
from app.core.database import get_db
from app.models.governance import RoutingPolicy
from app.schemas.founder import RoutingPolicyUpdate, RoutingPreviewRequest
from app.services.audit import AuditService
from app.services.model_router import ModelRouter
from app.services.query_understanding import QueryInput, QueryUnderstandingService

router = APIRouter()


async def get_audit_service(
    db: AsyncSession = Depends(get_db),
) -> AuditService:
    """Create AuditService per request."""
    return AuditService(db)


def get_model_registry(request: Request):
    """Get the process model registry from FastAPI app state."""
    registry = getattr(request.app.state, "model_registry", None)
    if registry is None:
        raise HTTPException(status_code=503, detail="Model registry is not ready")
    return registry


def _serialize_candidate(candidate: Any) -> dict[str, Any]:
    return {
        "model_id": candidate.model_id,
        "provider": candidate.provider.value,
        "score": round(candidate.score, 4),
        "context_window": candidate.context_window,
        "cost_per_1m_input": candidate.cost_per_1m_input,
        "cost_per_1m_output": candidate.cost_per_1m_output,
        "tags": list(candidate.tags),
        "diagnostics": dict(candidate.diagnostics),
    }


def _normalize_route_event(event: dict[str, Any]) -> dict[str, Any]:
    params = event.get("action_params") or {}
    requested_mode = (
        params.get("requested_routing_mode")
        or params.get("requested_mode")
        or "STANDARD"
    )
    applied_mode = (
        params.get("applied_routing_mode")
        or params.get("applied_mode")
        or "STANDARD"
    )
    model = params.get("model")
    provider = params.get("provider")
    routing_source = params.get("routing_source") or params.get("selection_source")
    top_candidates = params.get("top_candidates")
    if not isinstance(top_candidates, list):
        top_candidates = []

    return {
        "id": event.get("id"),
        "created_at": event.get("created_at"),
        "result": event.get("result"),
        "risk_level": event.get("risk_level"),
        "governance_tier": event.get("governance_tier"),
        "session_id": event.get("session_id"),
        "intent": params.get("intent"),
        "model": model,
        "provider": provider,
        "requested_mode": requested_mode,
        "applied_mode": applied_mode,
        "routing_source": routing_source,
        "selection_reason": params.get("selection_reason"),
        "mode_reason": params.get("mode_reason"),
        "provider_strategy": params.get("provider_strategy"),
        "providers_considered": params.get("providers_considered") or [],
        "latency_ms": params.get("latency_ms"),
        "user_message": params.get("user_message"),
        "top_candidates": top_candidates,
    }


def _summarize_routes(routes: list[dict[str, Any]]) -> dict[str, Any]:
    requested_modes = Counter()
    applied_modes = Counter()
    providers = Counter()
    routing_sources = Counter()
    intents = Counter()
    fallback_count = 0
    downgraded_count = 0

    for route in routes:
        requested = str(route.get("requested_mode") or "STANDARD")
        applied = str(route.get("applied_mode") or "STANDARD")
        provider = route.get("provider")
        routing_source = route.get("routing_source")
        intent = route.get("intent")

        requested_modes[requested] += 1
        applied_modes[applied] += 1
        if provider:
            providers[str(provider)] += 1
        if routing_source:
            routing_sources[str(routing_source)] += 1
        if intent:
            intents[str(intent)] += 1
        if route.get("mode_reason"):
            fallback_count += 1
        if requested != applied:
            downgraded_count += 1

    total = len(routes)
    return {
        "total_routes": total,
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_count / total, 4) if total else 0.0,
        "downgraded_mode_count": downgraded_count,
        "by_requested_mode": dict(requested_modes),
        "by_applied_mode": dict(applied_modes),
        "by_provider": dict(providers),
        "by_source": dict(routing_sources),
        "by_intent": dict(intents),
    }


@router.get("/routing/telemetry")
async def get_routing_telemetry(
    request: Request,
    limit: int = Query(12, ge=1, le=50),
    _user: CurrentUser = Depends(require_role("FOUNDER")),
    audit: AuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    """Founder-only routing/runtime telemetry from live Repo B truth sources."""
    settings = get_settings()
    registry = get_model_registry(request)
    registry_snapshot = await registry.snapshot(force_refresh=False)
    audit_result = await audit.get_audit_trail(
        tenant_id=_user.tenant_id,
        page=1,
        page_size=limit,
        action_type="LLM_CALL",
    )
    recent_routes = [
        _normalize_route_event(item)
        for item in audit_result["data"]
    ]

    return {
        "success": True,
        "data": {
            "runtime": settings.runtime_diagnostics(),
            "registry": registry_snapshot,
            "recent_routes": recent_routes,
            "trace_summary": _summarize_routes(recent_routes),
            "audit_pagination": audit_result["pagination"],
        },
    }


@router.post("/routing/preview")
async def preview_routing(
    body: RoutingPreviewRequest,
    request: Request,
    _user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Preview query understanding and routing without calling any LLM."""
    registry = get_model_registry(request)
    qu_service = QueryUnderstandingService()
    # Convert governance_mode (which may be a legacy slider value) to
    # GovernanceSlider for the QueryInput -- the downstream QU service
    # still accepts GovernanceSlider and converts internally.
    _gov_raw = body.governance_mode or "BALANCED"
    try:
        _gov_mode = GovernanceMode(_gov_raw)
    except ValueError:
        try:
            _gov_mode = GovernanceSlider(_gov_raw).to_governance_mode()
        except ValueError:
            _gov_mode = GovernanceMode.BALANCED
    qu_result = qu_service.analyze(
        QueryInput(
            raw_message=body.message,
            user_id=str(_user.id),
            tenant_id=str(_user.tenant_id),
            execution_mode=ChatMode(body.chat_mode),
            governance_mode=_gov_mode,
        )
    )

    router_service = ModelRouter(registry)
    requested_mode = RoutingMode(body.routing_mode) if body.routing_mode else None
    preview_source = "think_mode" if body.think_mode else "standard_preview"
    if body.think_mode:
        decision = router_service.route(
            qu_result,
            requested_mode=RoutingMode.STANDARD,
            preferred_tags=["reasoning", "analysis", "large"],
            metadata={
                "selection_source": preview_source,
                "requested_session_mode": (
                    requested_mode.value if requested_mode else qu_result.suggested_mode.value
                ),
                "mode_reason": (
                    "Think mode previews the best installed reasoning-capable model "
                    "without forcing a missing override."
                ),
            },
        )
    else:
        decision = router_service.route(
            qu_result,
            requested_mode=requested_mode,
            metadata={"selection_source": preview_source},
        )

    return {
        "success": True,
        "data": {
            "preview_source": preview_source,
            "query_understanding": {
                "intent": qu_result.intent.value,
                "confidence": qu_result.confidence,
                "complexity_score": qu_result.complexity_score,
                "complexity_label": qu_result.complexity_label.value,
                "risk_level": qu_result.risk_level.value,
                "governance_tier": qu_result.governance_tier,
                "suggested_mode": qu_result.suggested_mode.value,
                "suggested_providers": [p.value for p in qu_result.suggested_providers],
                "ambiguity_signals": qu_result.ambiguity_signals,
                "clarifying_question": qu_result.clarifying_question,
                "processing_time_ms": qu_result.processing_time_ms,
            },
            "routing": {
                "requested_mode": decision.metadata.get("requested_mode"),
                "applied_mode": decision.mode.value,
                "primary": _serialize_candidate(decision.primary),
                "fallback_chain": [
                    _serialize_candidate(candidate)
                    for candidate in decision.fallback_chain
                ],
                "council_models": [
                    _serialize_candidate(candidate)
                    for candidate in decision.council_models
                ],
                "selection_reason": decision.metadata.get("selection_reason"),
                "mode_reason": decision.metadata.get("mode_reason"),
                "provider_strategy": decision.metadata.get("provider_strategy"),
                "providers_considered": decision.metadata.get("providers_considered"),
                "top_candidates": decision.metadata.get("top_candidates", []),
                "routing_time_ms": decision.routing_time_ms,
            },
        },
    }


# ── Routing Policy ──


_DEFAULT_POLICY: dict[str, Any] = {
    "preferred_models": {},
    "provider_priority": [],
    "cost_ceiling": None,
    "blocked_models": [],
    "blocked_providers": [],
    "default_model": None,
    "enforce_local_only": False,
}


def _policy_to_dict(row: RoutingPolicy | None) -> dict[str, Any]:
    """Serialize a RoutingPolicy row, filling defaults for absent keys."""
    if row is None:
        return {**_DEFAULT_POLICY}
    merged = {**_DEFAULT_POLICY, **(row.policy or {})}
    merged["id"] = str(row.id)
    merged["updated_by"] = str(row.updated_by) if row.updated_by else None
    merged["updated_at"] = (
        row.updated_at.isoformat() if row.updated_at else None
    )
    return merged


@router.get("/routing/policy")
async def get_routing_policy(
    _user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the current founder routing policy for this tenant."""
    stmt = select(RoutingPolicy).where(
        RoutingPolicy.tenant_id == _user.tenant_id,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    return {"success": True, "data": _policy_to_dict(row)}


@router.put("/routing/policy")
async def update_routing_policy(
    body: RoutingPolicyUpdate,
    _user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create or replace the founder routing policy for this tenant."""
    stmt = select(RoutingPolicy).where(
        RoutingPolicy.tenant_id == _user.tenant_id,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    policy_data = body.model_dump(exclude_none=True)

    if row is None:
        row = RoutingPolicy(
            tenant_id=_user.tenant_id,
            updated_by=_user.id,
            policy=policy_data,
        )
        db.add(row)
    else:
        # Merge: existing fields stay unless explicitly overwritten
        merged = {**(row.policy or {}), **policy_data}
        row.policy = merged
        row.updated_by = _user.id

    await db.commit()
    await db.refresh(row)
    return {"success": True, "data": _policy_to_dict(row)}


@router.post("/routing/policy/reset")
async def reset_routing_policy(
    _user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reset routing policy to system defaults (delete custom policy)."""
    stmt = select(RoutingPolicy).where(
        RoutingPolicy.tenant_id == _user.tenant_id,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is not None:
        await db.delete(row)
        await db.commit()

    return {"success": True, "data": _DEFAULT_POLICY}


@router.get("/error-events")
async def list_error_events(
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_role("FOUNDER")),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Recent runtime error events for founder review (DEP-007 sink).

    FOUNDER-gated. Returns SAFE fields only -- the ErrorEvent sink never
    stores secrets, raw exception text, tokens, credentials, request
    bodies, or stack traces (the full traceback stays in the server logs,
    correlated by request_id). Newest first, capped.
    """
    from sqlalchemy import desc as _desc

    from app.models.error_event import ErrorEvent

    rows = (
        await db.execute(
            select(ErrorEvent).order_by(_desc(ErrorEvent.created_at)).limit(limit)
        )
    ).scalars().all()
    return {
        "success": True,
        "count": len(rows),
        "data": [
            {
                "id": str(e.id),
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "severity": e.severity,
                "source": e.source,
                "route": e.route,
                "method": e.method,
                "status_code": e.status_code,
                "error_code": e.error_code,
                "error_type": e.error_type,
                "safe_message": e.safe_message,
                "request_id": e.request_id,
                "run_id": e.run_id,
                "provider": e.provider,
                "tenant_id": str(e.tenant_id) if e.tenant_id else None,
                "user_id": str(e.user_id) if e.user_id else None,
            }
            for e in rows
        ],
    }


@router.get("/run-trace/{request_id}")
async def get_run_trace(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_role("FOUNDER")),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    """Ordered run-trace spans for one request_id (local tracing adopt).

    FOUNDER-gated. Returns the chronological span timeline for a single chat
    run -- the OpenAI-Agents-SDK-style view, served locally without any
    external telemetry SaaS. SAFE fields only: run_tracer never stores
    prompts, responses, system prompts, request bodies, credentials, tokens,
    or raw provider error text, and it strips secret-looking metadata keys +
    caps value sizes at write time. metadata_json is therefore safe to echo.
    """
    from app.models.run_trace_event import RunTraceEvent

    rid = (request_id or "").strip()[:64]
    rows = (
        await db.execute(
            select(RunTraceEvent)
            .where(RunTraceEvent.request_id == rid)
            .order_by(RunTraceEvent.created_at.asc(), RunTraceEvent.id.asc())
            .limit(limit)
        )
    ).scalars().all()
    return {
        "success": True,
        "request_id": rid,
        "count": len(rows),
        "data": [
            {
                "id": str(e.id),
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "event_type": e.event_type,
                "stage": e.stage,
                "status": e.status,
                "provider": e.provider,
                "model": e.model,
                "governance_mode": e.governance_mode,
                "safe_summary": e.safe_summary,
                "request_id": e.request_id,
                "run_id": e.run_id,
                "session_id": str(e.session_id) if e.session_id else None,
                "tenant_id": str(e.tenant_id) if e.tenant_id else None,
                "user_id": str(e.user_id) if e.user_id else None,
                "metadata": e.metadata_json,
            }
            for e in rows
        ],
    }
