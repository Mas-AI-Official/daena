"""Daena Security Dashboard API.

Provides real-time scan status, tool catalog, SHIELD activation state,
scan trace history, self-improvement metrics, and end-to-end scan workflow.

This is the backend for the /security/dashboard frontend page.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.security.scan_remediation import (
    FindingNotFoundError,
    NoActiveDepartmentError,
    create_remediation,
    serialize_result,
)
from app.services.security.yellow_runtime_gate import (
    load_authorized_scope,
    target_matches_scope,
)

logger = get_logger(__name__)

router = APIRouter()

# Singleton scan workflow instance (lazy-init to avoid import-time side effects)
_scan_workflow = None

_SECURITY_STATUS_CACHE_TTL_S = 15.0
_TOOLS_CACHE_TTL_S = 30.0
_tool_stats_cache: tuple[float, dict[str, Any]] | None = None
_tool_stats_refresh_task: asyncio.Task | None = None
_tools_cache: dict[tuple[str, str, bool], tuple[float, list[ToolInfo]]] = {}


def _get_workflow():
    """Lazy-init the ScanWorkflow singleton."""
    global _scan_workflow
    if _scan_workflow is None:
        from app.services.security.scan_workflow import ScanWorkflow
        _scan_workflow = ScanWorkflow()
    return _scan_workflow


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class DashboardStatus(BaseModel):
    evilbob_active: bool = False
    environment: str = ""
    activated_at: str = ""
    activated_by: str = ""
    capabilities: list[str] = []
    shield_status: dict[str, bool] = {}
    tool_stats: dict[str, Any] = {}
    scan_history: list[dict[str, Any]] = []
    self_improvement: dict[str, Any] = {}


class ToolInfo(BaseModel):
    name: str
    category: str
    description: str
    capabilities: list[str]
    installed: bool = False
    install_cmd: str = ""
    offensive_only: bool = False
    enabled: bool = True       # user toggle; False = Daena skips this tool
    install_state: str = "unknown"  # fresh/stale/pending/failed


def _invalidate_security_tool_cache() -> None:
    global _tool_stats_cache
    _tool_stats_cache = None
    _tools_cache.clear()


def _build_tool_stats_payload() -> dict[str, Any]:
    """Run the slow installed-tool inventory.

    This walks PATH for every known tool. It must not run inline on
    /security/status because Windows PATH probing has measured at 6-7s on
    Masoud's machine.
    """
    from app.services.security.tool_catalog import ToolCatalog

    catalog = ToolCatalog()
    started = time.monotonic()
    installed = catalog.get_installed()
    return {
        "total_known": catalog.total_tools,
        "total_installed": len(installed),
        "total_capabilities": catalog.total_capabilities,
        "categories": catalog.categories,
        "installed_names": [t.name for t in installed],
        "detection_state": "fresh",
        "refreshing": False,
        "last_checked": time.time(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def _cheap_tool_stats_payload(detection_state: str = "pending") -> dict[str, Any]:
    """Return catalog metadata without installed-tool probing."""
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        return {
            "total_known": catalog.total_tools,
            "total_installed": 0,
            "total_capabilities": catalog.total_capabilities,
            "categories": catalog.categories,
            "installed_names": [],
            "detection_state": detection_state,
            "refreshing": True,
            "last_checked": None,
            "duration_ms": 0,
        }
    except Exception as exc:
        logger.error("security_dashboard.tool_stats_catalog_failed", error=str(exc))
        return {
            "total_known": 0,
            "total_installed": 0,
            "total_capabilities": 0,
            "categories": [],
            "installed_names": [],
            "detection_state": "failed",
            "refreshing": False,
            "last_checked": None,
            "failure_reason": str(exc),
            "duration_ms": 0,
        }


async def _refresh_tool_stats_background() -> None:
    """Refresh installed-tool inventory without blocking request handlers."""
    global _tool_stats_cache
    started = time.monotonic()
    try:
        payload = await asyncio.to_thread(_build_tool_stats_payload)
    except Exception as exc:
        logger.error("security_dashboard.tool_stats_failed", error=str(exc))
        payload = _cheap_tool_stats_payload("failed")
        payload["failure_reason"] = str(exc)
        payload["refreshing"] = False
        payload["duration_ms"] = int((time.monotonic() - started) * 1000)

    _tool_stats_cache = (
        time.monotonic() + _SECURITY_STATUS_CACHE_TTL_S,
        payload,
    )
    _tools_cache.clear()


def _ensure_tool_stats_refresh() -> None:
    """Start one background inventory refresh if none is already running."""
    global _tool_stats_refresh_task
    if _tool_stats_refresh_task and not _tool_stats_refresh_task.done():
        return
    _tool_stats_refresh_task = asyncio.create_task(_refresh_tool_stats_background())


async def _get_tool_stats_cached() -> dict[str, Any]:
    """Return cached tool stats immediately and refresh stale data in background."""
    now = time.monotonic()
    if _tool_stats_cache and now < _tool_stats_cache[0]:
        return dict(_tool_stats_cache[1])

    _ensure_tool_stats_refresh()
    if _tool_stats_cache:
        stale = dict(_tool_stats_cache[1])
        stale["detection_state"] = "stale"
        stale["refreshing"] = True
        return stale
    return _cheap_tool_stats_payload("pending")


def _installed_tool_snapshot() -> tuple[set[str], str]:
    """Return installed names from the latest cache without probing PATH."""
    now = time.monotonic()
    if not _tool_stats_cache:
        return set(), "pending"

    expires_at, payload = _tool_stats_cache
    state = str(payload.get("detection_state") or "unknown")
    if now >= expires_at and state == "fresh":
        state = "stale"
    names = payload.get("installed_names") or []
    return {str(name) for name in names}, state


def _list_tools_cached(
    category: str = "",
    capability: str = "",
    installed_only: bool = False,
) -> list[ToolInfo]:
    key = (category, capability, installed_only)
    now = time.monotonic()
    cached = _tools_cache.get(key)
    if cached and now < cached[0]:
        return list(cached[1])

    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()

        if capability:
            tools = catalog.find_by_capability(capability)
        elif category:
            tools = catalog.find_by_category(category)
        else:
            tools = catalog.get_all()

        installed_names, install_state = _installed_tool_snapshot()
        if install_state in {"pending", "stale"}:
            try:
                _ensure_tool_stats_refresh()
            except RuntimeError:
                # list_tools can be called from a worker thread in tests.
                pass

        enabled_state = _load_tool_enabled()
        result: list[ToolInfo] = []
        for tool in tools:
            is_installed = tool.name in installed_names
            if installed_only and not is_installed:
                continue
            result.append(ToolInfo(
                name=tool.name,
                category=tool.category,
                description=tool.description,
                capabilities=tool.capabilities,
                installed=is_installed,
                install_cmd=tool.install_cmd,
                offensive_only=tool.offensive_only,
                enabled=enabled_state.get(tool.name, True),
                install_state=install_state,
            ))
    except Exception as exc:
        logger.error("security_dashboard.tools_failed", error=str(exc))
        result = []

    _tools_cache[key] = (now + _TOOLS_CACHE_TTL_S, result)
    return list(result)


# ---------------------------------------------------------------------------
# Per-tool enable/disable persistence
# ---------------------------------------------------------------------------
# Users toggle this to keep a tool installed but tell Daena not to
# dispatch it on scans. State persists to ``var/tool_enabled.json`` so
# it survives restart. Default: every tool is enabled; the file only
# records explicit overrides.

_TOOL_STATE_PATH = os.path.join(
    os.environ.get("DAENA_VAR", "var"), "tool_enabled.json",
)


def _load_tool_enabled() -> dict[str, bool]:
    if not os.path.isfile(_TOOL_STATE_PATH):
        return {}
    try:
        with open(_TOOL_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): bool(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_tool_enabled(state: dict[str, bool]) -> None:
    os.makedirs(os.path.dirname(_TOOL_STATE_PATH), exist_ok=True)
    tmp = _TOOL_STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, _TOOL_STATE_PATH)


def is_tool_enabled(name: str) -> bool:
    """Public helper consumed by real_scanner / scan_workflow to skip
    explicitly-disabled tools. Missing key = enabled by default.
    """
    return _load_tool_enabled().get(name, True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=DashboardStatus)
async def get_dashboard_status() -> DashboardStatus:
    """Full dashboard status: mode, shields, tools, history, self-improvement."""
    # Mode status
    try:
        from app.services.security.evilbob_mode import get_state
        state = get_state()
        evilbob_active = state.active
        environment = state.environment
        activated_at = state.activated_at
        activated_by = state.activated_by
        capabilities = state.capabilities
    except Exception:
        evilbob_active = False
        environment = "unknown"
        activated_at = ""
        activated_by = ""
        capabilities = []

    # SHIELD activation status
    try:
        from app.services.department_prompts import get_offensive_shield_status
        shield_status = get_offensive_shield_status()
    except Exception:
        shield_status = {}

    # Scan-history JSON reads are filesystem-bound. Tool inventory returns
    # cached/stale data immediately and refreshes PATH probing in the
    # background, so /security/status stays responsive on first navigation.
    tool_stats, scan_history, self_improvement = await asyncio.gather(
        _get_tool_stats_cached(),
        asyncio.to_thread(_load_scan_history, 20),
        asyncio.to_thread(_get_self_improvement_metrics),
    )

    return DashboardStatus(
        evilbob_active=evilbob_active,
        environment=environment,
        activated_at=activated_at,
        activated_by=activated_by,
        capabilities=capabilities,
        shield_status=shield_status,
        tool_stats=tool_stats,
        scan_history=scan_history,
        self_improvement=self_improvement,
    )


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools(
    category: str = "",
    capability: str = "",
    installed_only: bool = False,
) -> list[ToolInfo]:
    """List security tools from the catalog with optional filters."""
    installed_names, install_state = _installed_tool_snapshot()
    if not installed_names and install_state in {"pending", "stale"}:
        _ensure_tool_stats_refresh()
    return await asyncio.to_thread(
        _list_tools_cached,
        category,
        capability,
        installed_only,
    )


@router.get("/tools/recommend")
async def recommend_tools(
    target_type: str = "web_application",
    waf: str = "",
) -> list[ToolInfo]:
    """Get tool recommendations for a target type."""
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tools = catalog.recommend_for_target(target_type, waf)
        return [
            ToolInfo(
                name=t.name,
                category=t.category,
                description=t.description,
                capabilities=t.capabilities,
                installed=catalog.is_installed(t.name),
                install_cmd=t.install_cmd,
                offensive_only=t.offensive_only,
            )
            for t in tools
        ]
    except Exception as exc:
        logger.error("security_dashboard.recommend_failed", error=str(exc))
        return []


@router.get("/scans")
async def list_scans(
    limit: int = 50,
    archived: bool = False,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List recent scan traces.

    Phase 10b: ``archived=true`` flips the loader to read from the
    ``.archive/`` folder so the founder can recover scans that were
    soft-archived via ``DELETE /scans/{id}`` (the default action).
    Without this flag the previous behavior is preserved (active list
    only). Closes the "archive makes reports disappear with no recovery
    surface" gap from the Phase 9B matrix.

    Auth (K-2, 2026-06-01): now requires a valid bearer access token.
    Previously this endpoint was unauthenticated, enumerating every
    scan ever run with target paths, severity counts, findings totals,
    and cost - a direct information-disclosure surface.

    Ownership (K-3, 2026-06-01): the result is filtered to scans owned
    by the caller's tenant. Legacy scans on disk without a persisted
    tenant_id (pre-PR-SCAN-DISK-TENANT) are dropped fail-closed so this
    list cannot be used to enumerate other tenants' scan history. To
    surface those, re-run the scan (which writes the new tenant_id).

    K-3 fix (2026-06-01): filter on the ``tenant_id`` that
    ``_load_scan_history`` reads from each report payload, NOT on
    ``get_scan_owner_tenant_id`` - the latter only consults the LIVE
    reports dir, so for ``archived=true`` it returned None for every
    archived report and hid the whole archive even from its owner.
    Reading tenant_id from the same payload the loader already parsed
    works uniformly for live AND archived scans.
    """
    caller_tenant = str(user.tenant_id)
    raw = _load_scan_history(limit, archived=archived)
    # Filter to scans owned by the caller's tenant. _load_scan_history
    # surfaces ``tenant_id`` from each report payload (None for legacy
    # pre-tenant reports + legacy adversarial traces, which fail closed).
    return [
        row for row in raw
        if row.get("scan_id") and row.get("tenant_id") == caller_tenant
    ]


@router.get("/scans/{scan_id}")
async def get_scan_detail(
    scan_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Get full detail of a specific scan trace.

    Auth (K-2): authenticated. Ownership (K-3, 2026-06-01): the caller's
    tenant must own this scan. Cross-tenant access is mapped to 404
    (not 403) so this endpoint cannot be used to probe which scan ids
    exist for other tenants. Legacy scans on disk without a tenant_id
    field fail-closed (404) - same posture as the create_remediation
    route documented in PR-SCAN-DISK-TENANT.
    """
    workflow = _get_workflow()
    owner_tenant_id = workflow.get_scan_owner_tenant_id(scan_id)
    if owner_tenant_id is None or owner_tenant_id != str(user.tenant_id):
        raise HTTPException(status_code=404, detail=f"Scan trace {scan_id} not found")
    trace_dir = os.path.join(os.environ.get("DAENA_VAR", "var"), "scan_traces")
    trace_path = os.path.join(trace_dir, f"{scan_id}.json")
    if not os.path.isfile(trace_path):
        raise HTTPException(status_code=404, detail=f"Scan trace {scan_id} not found")
    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/shields")
async def get_shield_details() -> dict[str, Any]:
    """Get detailed SHIELD activation status for each department."""
    try:
        from app.services.security.evilbob_mode import is_active
        from app.services.department_prompts import (
            get_offensive_shield_status,
            _OFFENSIVE_SHIELD_PROMPTS,
        )

        active = is_active()
        status = get_offensive_shield_status()

        details = {}
        for dept, is_offensive in status.items():
            details[dept] = {
                "mode": "offensive" if is_offensive else "defensive",
                "active": is_offensive,
                "role_summary": (
                    _OFFENSIVE_SHIELD_PROMPTS.get(dept, "")[:150] + "..."
                    if is_offensive
                    else "Standard defensive security review"
                ),
            }

        return {
            "evilbob_active": active,
            "departments": details,
            "total_offensive": sum(1 for v in status.values() if v),
            "total_departments": len(status),
        }
    except Exception as exc:
        logger.error("security_dashboard.shields_failed", error=str(exc))
        return {"evilbob_active": False, "departments": {}}


# ---------------------------------------------------------------------------
# Scan Workflow Endpoints (IaaS -- Intelligence-as-a-Service)
# ---------------------------------------------------------------------------

class ScanStartRequest(BaseModel):
    target: str                     # Repo URL, directory, or comma-separated paths
    tier: str = "ANALYST"           # SCOUT, ANALYST, OPERATOR, ARCHITECT, EVILBOB
    options: dict[str, Any] = {}    # Optional scan overrides


class ScanJobResponse(BaseModel):
    job_id: str
    target: str
    tier: str
    status: str
    created_at: float
    progress_pct: float = 0.0
    findings_count: int = 0


class ScanStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_pct: float = 0.0
    files_scanned: int = 0
    files_total: int = 0
    findings_count: int = 0
    error: str = ""


class ScanReportResponse(BaseModel):
    job_id: str
    tier: str
    findings: list[dict[str, Any]] = []
    summary: str = ""
    report_pdf_path: str = ""
    cost_usd: float = 0.0
    duration_secs: float = 0.0
    pipeline_stages_used: list[str] = []
    recommendations: list[str] = []
    severity_counts: dict[str, int] = {}


@router.post("/scans/start", response_model=ScanJobResponse)
async def start_scan(
    body: ScanStartRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ScanJobResponse:
    """Start a new security scan.

    Phase 10 commit-1 hardening: enforces the authorized-scope gate at the
    REST boundary BEFORE dispatch. Previously the gate ran inside
    ``scan_workflow.py`` Phase 0 (after job-create), so callers received
    HTTP 200 + a job_id for out-of-scope targets and the rejection
    surfaced only as an internal job-state transition. The REST boundary
    is the security boundary.

    Kicks off the full intelligence pipeline:
    profiling -> parallel scanning -> analysis -> report generation.
    """
    user_id = user.id
    tenant_id = user.tenant_id

    scope = load_authorized_scope(tenant_id)
    if not target_matches_scope(body.target, scope):
        logger.warning(
            "security.scan.scope_blocked",
            user_id=user_id,
            tenant_id=tenant_id,
            target=body.target,
            tier=body.tier,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "target_not_in_scope",
                "target": body.target,
                "hint": "Add this target to /security/scope before scanning.",
            },
        )

    workflow = _get_workflow()
    try:
        job = await workflow.start_scan(
            target=body.target,
            tier=body.tier,
            user_id=user_id,
            tenant_id=tenant_id,
            options=body.options,
        )
        return ScanJobResponse(
            job_id=job.id,
            target=job.target,
            tier=job.tier.value,
            status=job.status.value,
            created_at=job.created_at,
            progress_pct=job.progress_pct,
            findings_count=job.findings_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("scan_start_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/scans/{job_id}/status", response_model=ScanStatusResponse)
async def get_scan_status(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ScanStatusResponse:
    """Poll scan progress. Returns current status and completion percentage.

    Ownership (K-3): the caller's tenant must own this scan; cross-tenant
    access is mapped to 404 to avoid id-existence probing.
    """
    workflow = _get_workflow()
    owner_tenant_id = workflow.get_scan_owner_tenant_id(job_id)
    if owner_tenant_id is None or owner_tenant_id != str(user.tenant_id):
        raise HTTPException(status_code=404, detail=f"Scan job {job_id} not found")

    try:
        status = await workflow.get_scan_status(job_id)
        return ScanStatusResponse(
            job_id=status.job_id,
            status=status.status.value,
            progress_pct=status.progress_pct,
            files_scanned=status.files_scanned,
            files_total=status.files_total,
            findings_count=status.findings_count,
            error=status.error,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Scan job {job_id} not found")


@router.get("/scans/{job_id}/report", response_model=ScanReportResponse)
async def get_scan_report(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ScanReportResponse:
    """Get the completed scan report with findings, cost, and summary.

    Ownership (K-3): caller's tenant must own this scan; 404 on miss.
    """
    workflow = _get_workflow()
    owner_tenant_id = workflow.get_scan_owner_tenant_id(job_id)
    if owner_tenant_id is None or owner_tenant_id != str(user.tenant_id):
        raise HTTPException(status_code=404, detail=f"Scan job {job_id} not found")

    try:
        report = await workflow.get_scan_report(job_id)
        return ScanReportResponse(
            job_id=report.job_id,
            tier=report.tier.value,
            findings=report.findings,
            summary=report.summary,
            report_pdf_path=report.report_pdf_path,
            cost_usd=report.cost_usd,
            duration_secs=report.duration_secs,
            pipeline_stages_used=report.pipeline_stages_used,
            recommendations=report.recommendations,
            severity_counts=report.severity_counts,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Scan job {job_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/scans/{job_id}/report/pdf")
async def download_scan_report_pdf(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> FileResponse:
    """Download the report file for a completed scan.

    The URL keeps its ``/pdf`` suffix for backward compatibility, but
    the response media type follows the actual file extension: PDF
    when reportlab was available at generation time, markdown when it
    fell back. This matches what actually landed on disk so browsers
    pick the right viewer.

    Ownership (K-3): caller's tenant must own this scan; 404 on miss.
    """
    workflow = _get_workflow()
    owner_tenant_id = workflow.get_scan_owner_tenant_id(job_id)
    if owner_tenant_id is None or owner_tenant_id != str(user.tenant_id):
        raise HTTPException(status_code=404, detail=f"Scan job {job_id} not found")

    try:
        report = await workflow.get_scan_report(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Scan job {job_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if not report.report_pdf_path or not os.path.isfile(report.report_pdf_path):
        raise HTTPException(
            status_code=404,
            detail=(
                "Report file not available. Report data is still "
                "accessible via /report (JSON)."
            ),
        )

    filename = os.path.basename(report.report_pdf_path)
    ext = os.path.splitext(filename)[1].lower()
    media_type = {
        ".pdf": "application/pdf",
        ".md": "text/markdown; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }.get(ext, "application/octet-stream")
    return FileResponse(
        path=report.report_pdf_path,
        filename=filename,
        media_type=media_type,
    )


# ---------------------------------------------------------------------------
# OPSEC stealth status
# ---------------------------------------------------------------------------

# Singleton OpsecManager for status reporting. The live scan path creates its
# own per-engagement instance; this singleton only exposes aggregate state to
# the UI so the founder can see stealth-stack health at a glance.
_opsec_manager = None


def _get_opsec_manager():
    """Lazy-init the OpsecManager singleton.

    OPSEC MODULE IS BACKGROUND PATH ONLY. This wrapper is safe because the
    status endpoint only reads counters; it never initiates requests.
    """
    global _opsec_manager
    if _opsec_manager is None:
        from app.services.security.opsec import OpsecManager
        _opsec_manager = OpsecManager()
    return _opsec_manager


@router.get("/scans/{job_id}/events")
async def stream_scan_events(
    job_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Server-sent events for a scan job.

    Yields events emitted by ScanWorkflow: scan_started,
    scan_phase_change (one per phase transition), scan_complete,
    scan_failed. The chat UI subscribes to this endpoint when it
    receives a scan_dispatched event in the main chat SSE so the
    inline ScanProgressCard updates live.

    Connection closes when the scan terminates (complete or failed)
    or when the client disconnects.

    Auth: requires a valid bearer access token (K-1 hardening,
    2026-06-01). Prior versions of this route were unauthenticated,
    which meant anyone who could guess a job_id could stream live
    scan reasoning, findings, and exploit decisions. Native browser
    EventSource cannot send custom headers, so frontend consumers
    use the fetch-based ``useResilientSSE`` hook which forwards
    ``Authorization: Bearer <token>`` from localStorage. Job-level
    tenant ownership is intentionally NOT enforced here yet (see
    KLYNTAR_SECURITY_MODULE_AUDIT.md "Next sprint - tenant scoping"
    section); the workflow object is currently process-global and
    not tenant-keyed at the workflow lifecycle level, so the right place
    to scope it more deeply is in ScanWorkflow itself, paired with a
    job-to-tenant migration.

    Ownership (K-3, 2026-06-01): the caller's tenant must own this scan.
    Cross-tenant access is mapped to 404 (not 403) to avoid leaking which
    scan ids exist for other tenants.
    """
    workflow = _get_workflow()
    owner_tenant_id = workflow.get_scan_owner_tenant_id(job_id)
    if owner_tenant_id is None or owner_tenant_id != str(user.tenant_id):
        raise HTTPException(status_code=404, detail=f"Scan {job_id} not found")

    try:
        # Confirm the job exists before opening the stream.
        await workflow.get_scan_status(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Scan {job_id} not found")

    async def _event_stream():
        q = workflow.subscribe(job_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    envelope = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Heartbeat so proxies do not close idle SSE.
                    yield ": heartbeat\n\n"
                    continue

                data = json.dumps(envelope)
                yield f"event: {envelope['type']}\ndata: {data}\n\n"

                if envelope["type"] in ("scan_complete", "scan_failed"):
                    break
        finally:
            workflow.unsubscribe(job_id, q)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/opsec/status")
async def get_opsec_status() -> dict[str, Any]:
    """Stealth-stack status for the /security page OPSEC panel.

    Exposes: fingerprint rotation count, active browser profile name,
    total requests with jitter applied, cumulative delay, evidence-vault
    count, whether we've detected being fingerprinted ourselves,
    and module availability of tor / proxychains from the tool catalog.
    """
    try:
        from app.services.security.evilbob_mode import is_active
        evilbob_active = is_active()
    except Exception:
        evilbob_active = False

    # OPSEC manager status. Read-only -- never triggers network activity.
    profile_name = ""
    rotation_count = 0
    request_count = 0
    total_delay_ms = 0
    evidence_count = 0
    fingerprinting_seen = False
    try:
        opsec = _get_opsec_manager()
        profile = opsec.fingerprints.get_profile()
        profile_name = profile.get("name", "") or profile.get("user_agent", "")[:40]
        rotation_count = opsec.fingerprints.rotation_count
        request_count = opsec.timing.request_count
        total_delay_ms = opsec.timing.total_delay_ms
        evidence_count = opsec.vault.evidence_count
        fingerprinting_seen = opsec._fingerprinting_detected  # noqa: SLF001
    except Exception as exc:
        logger.error("security_dashboard.opsec_status_failed", error=str(exc))

    # Stealth-adjacent tools from the catalog: do we actually have tor + proxychains?
    stealth_tools: dict[str, bool] = {}
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        for tool_name in ("tor", "proxychains", "playwright", "mitmproxy"):
            stealth_tools[tool_name] = catalog.is_installed(tool_name)
    except Exception:
        pass

    return {
        "gated": not evilbob_active,
        "evilbob_active": evilbob_active,
        "fingerprint_profile": profile_name,
        "fingerprint_rotations": rotation_count,
        "request_count": request_count,
        "timing_delay_ms": total_delay_ms,
        "evidence_vault_count": evidence_count,
        "fingerprinting_detected": fingerprinting_seen,
        "stealth_tools_installed": stealth_tools,
        "note": (
            "Browser/evidence controls are background-path only. This endpoint "
            "exposes status; it never initiates network requests."
        ),
    }


# ---------------------------------------------------------------------------
# Delete / archive endpoints (CLAUDE.md rule 2: archive, don't hard-delete)
# ---------------------------------------------------------------------------

def _scan_trace_path(scan_id: str) -> str:
    trace_dir = os.path.join(os.environ.get("DAENA_VAR", "var"), "scan_traces")
    return os.path.join(trace_dir, f"{scan_id}.json")


def _scan_report_path(scan_id: str) -> str:
    base = os.environ.get(
        "SECURITY_REPORTS_DIR", os.path.join("var", "security_reports"),
    )
    return os.path.join(base, f"{scan_id}.json")


def _archive_dir() -> str:
    base = os.environ.get(
        "SECURITY_REPORTS_DIR", os.path.join("var", "security_reports"),
    )
    return os.path.join(base, ".archive")


def _archive_scan(scan_id: str, *, hard: bool = False) -> dict[str, Any]:
    """Move a scan's trace + report JSON into the archive. When ``hard``
    is True, actually delete. Governed by dev mode on the caller side per
    CLAUDE.md rule 2.
    """
    archive = _archive_dir()
    os.makedirs(archive, exist_ok=True)

    moved: list[str] = []
    for label, src in (
        ("trace", _scan_trace_path(scan_id)),
        ("report", _scan_report_path(scan_id)),
    ):
        if not os.path.isfile(src):
            continue
        if hard:
            try:
                os.unlink(src)
                moved.append(f"{label}:deleted")
            except OSError as exc:
                logger.warning("security_dashboard.hard_delete_failed", scan=scan_id, err=str(exc))
        else:
            dest = os.path.join(
                archive, f"{scan_id}.{label}.{int(asyncio.get_event_loop().time())}.json",
            )
            try:
                os.replace(src, dest)
                moved.append(f"{label}:{os.path.basename(dest)}")
            except OSError as exc:
                logger.warning(
                    "security_dashboard.archive_failed",
                    scan=scan_id, err=str(exc),
                )

    # Drop from the workflow singleton cache so future queries don't hit stale data.
    try:
        workflow = _get_workflow()
        workflow._jobs.pop(scan_id, None)      # noqa: SLF001
        workflow._reports.pop(scan_id, None)   # noqa: SLF001
    except Exception:
        pass

    return {
        "scan_id": scan_id,
        "archived": not hard,
        "deleted": hard,
        "artifacts": moved,
    }


@router.post("/scans/{scan_id}/rerun")
async def rerun_scan(
    scan_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ScanJobResponse:
    """Re-run a scan with the same target + tier as the original.

    Phase 2.7 (2026-04-25): added so the user can repeat a scan from
    the Recent Scans list without re-typing the target. Loads the
    original trace JSON, extracts target + tier, and dispatches a new
    scan via the same workflow as ``start_scan``. Returns a fresh
    job_id; the original scan record is left untouched in history.

    Critical safety note that's also surfaced in the UX disclaimer:
    this endpoint reads the ORIGINAL scan record (a JSON file in
    ``var/security_reports/``) and starts a NEW scan. It does NOT
    modify or delete any actual files on disk.

    Auth (K-2, 2026-06-01): now requires a valid bearer access token.
    Previously this endpoint was unauthenticated, which meant any
    network-reachable caller could trigger expensive LLM-driven scans
    on the founder's machine (cost amplification / DoS).

    Ownership (K-3, 2026-06-01): the caller's tenant must own the
    ORIGINAL scan being rerun, and the NEW scan is attributed to the
    caller (not "system" / "default" as it was previously - that was a
    tenant-bypass bug that mis-attributed every rerun to a fake tenant).
    """
    workflow = _get_workflow()
    owner_tenant_id = workflow.get_scan_owner_tenant_id(scan_id)
    if owner_tenant_id is None or owner_tenant_id != str(user.tenant_id):
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    import json
    trace_path = _scan_trace_path(scan_id)
    report_path = _scan_report_path(scan_id)
    raw: dict[str, Any] | None = None
    if os.path.isfile(trace_path):
        try:
            raw = json.loads(open(trace_path, encoding="utf-8").read())
        except Exception as exc:
            logger.warning("rerun_scan.trace_read_failed", error=str(exc))
    if not raw and os.path.isfile(report_path):
        try:
            raw = json.loads(open(report_path, encoding="utf-8").read())
        except Exception as exc:
            logger.warning("rerun_scan.report_read_failed", error=str(exc))
    if not raw:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    target = raw.get("target") or raw.get("scan_target")
    tier = raw.get("tier") or raw.get("scan_tier") or "SCOUT"
    if not target:
        raise HTTPException(
            status_code=400,
            detail="Original scan record missing 'target' field; cannot rerun.",
        )

    # K-3 fix: the NEW scan inherits the calling user's identity instead
    # of being attributed to "system" / "default" (which broke tenant
    # isolation and caused rerun-spawned scans to never appear in the
    # caller's history).
    user_id = str(user.id)
    tenant_id = str(user.tenant_id)
    try:
        job = await workflow.start_scan(
            target=str(target),
            tier=str(tier),
            user_id=user_id,
            tenant_id=tenant_id,
            options=raw.get("options") or {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("rerun_scan.start_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info(
        "rerun_scan.started",
        original_scan_id=scan_id,
        new_job_id=job.id,
        target=target,
        tier=tier,
    )
    return ScanJobResponse(
        job_id=job.id,
        target=job.target,
        tier=job.tier.value,
        status=job.status.value,
        created_at=job.created_at,
        progress_pct=job.progress_pct,
        findings_count=job.findings_count,
    )


@router.delete("/scans/{scan_id}")
async def delete_scan(
    scan_id: str,
    hard: bool = False,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Archive (default) or hard-delete a scan's trace + report.

    CLAUDE.md rule 2: archive by default; dev mode must pass ``hard=true``
    to actually unlink. Returns which artifacts were moved and where.

    Auth (K-2, 2026-06-01): now requires a valid bearer access token.
    Previously this endpoint was unauthenticated, allowing any
    network-reachable caller to archive or hard-delete any scan.

    Ownership (K-3, 2026-06-01): the caller's tenant must own this scan.
    Cross-tenant deletes are blocked with 404 (id-existence not leaked).
    """
    workflow = _get_workflow()
    owner_tenant_id = workflow.get_scan_owner_tenant_id(scan_id)
    if owner_tenant_id is None or owner_tenant_id != str(user.tenant_id):
        raise HTTPException(
            status_code=404,
            detail=f"Scan {scan_id} has no trace or report on disk",
        )
    trace = _scan_trace_path(scan_id)
    report = _scan_report_path(scan_id)
    if not os.path.isfile(trace) and not os.path.isfile(report):
        raise HTTPException(
            status_code=404,
            detail=f"Scan {scan_id} has no trace or report on disk",
        )
    return _archive_scan(scan_id, hard=hard)


@router.delete("/scans")
async def delete_all_scans(
    hard: bool = False,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Bulk archive (default) every scan in history. ``hard=true`` hard-
    deletes. Scoped to the scan_traces + security_reports directories
    owned by this process. Returns counts + per-scan status.

    Auth (K-2, 2026-06-01): now requires a valid bearer access token.
    Previously this BULK destructive endpoint was unauthenticated,
    meaning any network-reachable caller could archive (or with
    ``hard=true``, irrecoverably delete) every scan in history.

    Ownership (K-3, 2026-06-01): only scans owned by the caller's
    tenant are archived/deleted. Legacy scans on disk without a
    persisted tenant_id (pre-PR-SCAN-DISK-TENANT) are skipped
    fail-closed so this endpoint cannot be used to wipe other tenants'
    data. The response counts include both processed and skipped so
    the caller has an honest report of what happened.
    """
    workflow = _get_workflow()
    caller_tenant = str(user.tenant_id)

    trace_dir = os.path.join(os.environ.get("DAENA_VAR", "var"), "scan_traces")
    base = os.environ.get("SECURITY_REPORTS_DIR", os.path.join("var", "security_reports"))
    scan_ids: set[str] = set()
    if os.path.isdir(trace_dir):
        for name in os.listdir(trace_dir):
            if name.endswith(".json"):
                scan_ids.add(name[:-5])
    if os.path.isdir(base):
        for name in os.listdir(base):
            if name.endswith(".json"):
                scan_ids.add(name[:-5])

    owned: list[str] = []
    skipped_cross_tenant = 0
    skipped_legacy_no_tenant = 0
    for sid in sorted(scan_ids):
        owner = workflow.get_scan_owner_tenant_id(sid)
        if owner is None:
            skipped_legacy_no_tenant += 1
            continue
        if owner != caller_tenant:
            skipped_cross_tenant += 1
            continue
        owned.append(sid)

    results = [_archive_scan(sid, hard=hard) for sid in owned]
    return {
        "processed": len(results),
        "skipped_cross_tenant": skipped_cross_tenant,
        "skipped_legacy_no_tenant": skipped_legacy_no_tenant,
        "hard": hard,
        "results": results,
    }


# ---------------------------------------------------------------------------
# PR-SCAN-WS-01: scan finding -> remediation Task + Workstream
# ---------------------------------------------------------------------------


class CreateRemediationRequest(BaseModel):
    """Optional inputs for the create-remediation endpoint."""

    department_id: UUID | None = None


@router.post("/scans/{scan_id}/findings/{finding_id}/create-remediation")
async def create_remediation_from_finding(
    scan_id: str,
    finding_id: str,
    body: CreateRemediationRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a remediation Task + Workstream for a single scan finding.

    Closes the PR-4 debt: scan reports surface remediation guidance
    text but cannot turn it into trackable work. This endpoint accepts
    a (scan_id, finding_id) pair, creates a Task in the autopilot queue
    AND a Workstream shell linked back to the scan via PR-5
    artifact_refs. Idempotent: a second call with the same pair returns
    the existing Workstream rather than duplicating.

    Path params:
        scan_id: The ScanWorkflow job id (workflow-generated string).
        finding_id: Either the SecurityFinding.id (when populated) or
            the positional fallback ``"idx-N"`` for findings whose id
            is empty.

    Returns the standard ``{success, data}`` envelope. ``data`` carries
    ``task_id``, ``workstream_id``, the finding metadata, and an
    ``idempotent`` boolean for the frontend toast copy.
    """
    workflow = _get_workflow()

    # 1. Verify the scan belongs to the calling tenant.
    #
    # PR-SCAN-DISK-TENANT (2026-05-02): the lookup now consults
    # in-memory ``_jobs`` first and falls back to the on-disk
    # persisted ``tenant_id``, so a scan that survived a process
    # restart can still be remediated by its owner. Legacy reports
    # written before this PR have no ``tenant_id`` field; the helper
    # returns None for those and we 404 -- fail-closed -- so a
    # restart-recovered scan from before the upgrade cannot be
    # remediated until it is re-run.
    #
    # Cross-tenant access is mapped to 404 (not 403) so the endpoint
    # does not leak which scan ids exist for other tenants.
    owner_tenant_id = workflow.get_scan_owner_tenant_id(scan_id)
    if owner_tenant_id is None or owner_tenant_id != str(user.tenant_id):
        raise HTTPException(
            status_code=404,
            detail=f"Scan {scan_id} not found",
        )

    # 2. Fetch the report (handles in-memory cache + disk fallback).
    try:
        report = await workflow.get_scan_report(scan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 3. Hand off to the service layer (also testable directly).
    requested_dept = body.department_id if body is not None else None
    try:
        result = await create_remediation(
            db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            scan_id=scan_id,
            finding_id=finding_id,
            findings=report.findings,
            department_id=requested_dept,
        )
    except FindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoActiveDepartmentError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "NO_ACTIVE_DEPARTMENT",
                    "message": str(exc),
                },
            },
        ) from exc

    return {"success": True, "data": serialize_result(result)}


# ---------------------------------------------------------------------------
# Tool installation endpoints
# ---------------------------------------------------------------------------

class ToolEnableRequest(BaseModel):
    enabled: bool


@router.post("/tools/{name}/enable")
async def set_tool_enabled(name: str, body: ToolEnableRequest) -> dict[str, Any]:
    """Toggle whether Daena dispatches this tool on scans. The tool
    stays installed on disk; only Daena's orchestration skips it. State
    persists to ``var/tool_enabled.json``.
    """
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tool catalog unavailable: {exc}")

    if not catalog.get(name):
        raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")

    state = _load_tool_enabled()
    state[name] = bool(body.enabled)
    _save_tool_enabled(state)
    _invalidate_security_tool_cache()
    logger.info(
        "security_dashboard.tool_toggled",
        tool=name, enabled=body.enabled,
    )
    return {"tool": name, "enabled": state[name]}


@router.post("/tools/install/{name}")
async def install_tool(name: str, confirm: str = "") -> dict[str, Any]:
    """Install a single tool by name. Runs the ``install_cmd`` from the
    catalog via subprocess. On success, triggers the post-install
    rule-pack hook (nuclei templates, trivy DB, etc.) so the tool is
    immediately useful on the next scan.
    """
    _require_security_tool_install_confirmation(confirm)

    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tool catalog unavailable: {exc}")

    tool = catalog.get(name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")

    result = await catalog.auto_install(name)
    installed_after = catalog.is_installed(name)
    _invalidate_security_tool_cache()
    post_install = {"ran": False}
    if installed_after and name in _POST_INSTALL_HOOKS:
        loop = asyncio.get_running_loop()
        post_install = await loop.run_in_executor(
            None, _run_post_install_hook, name,
        )
    return {
        "tool": name,
        **result,
        "installed_after": installed_after,
        "post_install": post_install,
    }


@router.post("/tools/{name}/fetch-rules")
async def fetch_tool_rules(name: str) -> dict[str, Any]:
    """Manually re-fetch the rule pack for a tool that has one (nuclei
    templates, trivy CVE DB). Useful to pick up upstream updates without
    reinstalling the binary. No-op + 200 OK when the tool has no hook.
    """
    if name not in _POST_INSTALL_HOOKS:
        return {
            "tool": name,
            "ran": False,
            "reason": "tool has no rule-pack hook",
        }
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _run_post_install_hook, name)
    return {"tool": name, **result}


# ---------------------------------------------------------------------------
# Bulk install -- background job pattern.
#
# Installing 46 tools serially takes several minutes; a synchronous HTTP
# call blows through axios's 30s timeout. Instead: kick off an asyncio
# task, return a job_id immediately, let the UI poll
# ``/tools/install-all/status/{job_id}`` every 2s for progress.
# ---------------------------------------------------------------------------

import asyncio
import shutil
import subprocess
import uuid as _uuid

# Prefixes that require a toolchain to be present. If it's missing, skip
# the install immediately instead of letting shell=True shell spew a
# "command not recognized" error and count as a 1s wasted attempt.
_INSTALL_PREFIX_CHECKS: dict[str, str] = {
    "go install": "go",
    "sudo apt": "apt",          # always missing on Windows
    "apt-get": "apt-get",
    "gem install": "gem",
    "cargo install": "cargo",
    "brew install": "brew",
    "choco install": "choco",
    "winget install": "winget",
}
_SECURITY_TOOL_INSTALL_CONFIRMATION = "install-security-tool"


def _require_security_tool_install_confirmation(confirm: str) -> None:
    if confirm != _SECURITY_TOOL_INSTALL_CONFIRMATION:
        raise HTTPException(
            status_code=409,
            detail=(
                "Installing security tools runs local package-manager or shell "
                "commands. Retry with explicit confirmation."
            ),
        )

# Post-install hooks: for tools that ship binary without their rule
# pack, run a one-shot fetch command so the scanner has something to
# dispatch against on the next scan. Auto-triggered after a successful
# install in ``_run_install_job``.
#
# * ``nuclei`` ships with zero templates; ``-update-templates`` clones
#   the 8,000+ community YAML set (projectdiscovery/nuclei-templates).
# * ``trivy`` downloads the Aqua CVE DB on first use, but cold-fetching
#   during install removes a 30s lag on the first real scan.
# * ``semgrep`` pulls registry rules lazily on ``--config=auto``; no
#   pre-fetch needed.
_POST_INSTALL_HOOKS: dict[str, str] = {
    "nuclei": "nuclei -update-templates -silent",
    "trivy": "trivy image --download-db-only --quiet",
}


def _run_post_install_hook(name: str) -> dict[str, Any]:
    """Run the one-shot rule-pack fetch for a just-installed tool.

    Returns ``{"ran": bool, "ok": bool, "error": str}``. Fail-safe:
    any exception returns ran=True, ok=False so the outer install
    still counts as a success for the tool itself.
    """
    cmd = _POST_INSTALL_HOOKS.get(name)
    if not cmd:
        return {"ran": False, "ok": True, "error": ""}
    logger.info("tool_post_install.running", tool=name, cmd=cmd)
    try:
        # Same shell=True pattern as auto_install; cmd is a hardcoded
        # map value, never user input. Bandit B602 false positive.
        result = subprocess.run(  # nosec B602
            cmd, shell=True, capture_output=True, text=True,
            timeout=600,
        )
        ok = result.returncode == 0
        if ok:
            logger.info("tool_post_install.ok", tool=name)
        else:
            logger.warning(
                "tool_post_install.failed",
                tool=name, stderr=(result.stderr or "")[:300],
            )
        return {
            "ran": True,
            "ok": ok,
            "error": "" if ok else (result.stderr or "")[:300],
        }
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("tool_post_install.exception", tool=name, error=str(exc))
        return {"ran": True, "ok": False, "error": str(exc)[:300]}

_install_jobs: dict[str, dict[str, Any]] = {}


def _prereq_for(install_cmd: str) -> tuple[str, str] | None:
    """Return (prefix, binary) when a command starts with a prefix whose
    tool isn't on PATH. Used to fail fast instead of running the shell.
    """
    lower = install_cmd.lower().lstrip()
    for prefix, binary in _INSTALL_PREFIX_CHECKS.items():
        if lower.startswith(prefix):
            if shutil.which(binary) is None:
                return prefix, binary
    return None


async def _run_install_job(job_id: str, plan: list[dict[str, Any]]) -> None:
    """Background driver: iterate plan, update ``_install_jobs[job_id]``
    after each install so the status endpoint can report progress.
    """
    job = _install_jobs[job_id]
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = f"Tool catalog unavailable: {exc}"
        return

    for entry in plan:
        if job.get("cancel_requested"):
            job["status"] = "cancelled"
            job["current"] = ""
            job["completed_at"] = asyncio.get_event_loop().time()
            _invalidate_security_tool_cache()
            return

        name = entry["name"]
        cmd = entry["install_cmd"]
        job["current"] = name
        missing = _prereq_for(cmd)
        if missing:
            job["results"].append({
                "name": name,
                "success": False,
                "skipped": True,
                "reason": (
                    f"Prerequisite ``{missing[1]}`` not on PATH; "
                    f"install it first (see README) or use a different "
                    f"install path for this tool."
                ),
            })
            job["skipped"] += 1
        else:
            try:
                # ``auto_install`` uses subprocess.run (blocking). Run it
                # in a thread so the async event loop stays responsive
                # and other HTTP requests (including the status poll
                # this job's UI is hitting every 2s) don't stall while
                # a 60-second choco install runs.
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(
                    None,
                    lambda: asyncio.run(catalog.auto_install(name)),
                )
                ok = bool(res.get("success"))
                # Rule-pack post-install hook (nuclei templates, trivy DB).
                # Runs once per install; fail is non-fatal to the install.
                hook_result = {"ran": False}
                if ok and name in _POST_INSTALL_HOOKS:
                    hook_result = await loop.run_in_executor(
                        None, _run_post_install_hook, name,
                    )
                job["results"].append({
                    "name": name,
                    "success": ok,
                    "error": res.get("error", "") or res.get("stderr", "")[:300],
                    "post_install": hook_result,
                })
                if ok:
                    job["succeeded"] += 1
                else:
                    job["failed"] += 1
            except Exception as exc:  # noqa: BLE001
                job["results"].append({
                    "name": name,
                    "success": False,
                    "error": str(exc)[:300],
                })
                job["failed"] += 1
        job["done"] = len(job["results"])
    job["status"] = "complete"
    job["current"] = ""
    job["completed_at"] = asyncio.get_event_loop().time()
    _invalidate_security_tool_cache()


@router.post("/tools/install-all")
async def install_all_tools(
    category: str = "",
    offensive_only: bool = False,
    dry_run: bool = False,
    confirm: str = "",
) -> dict[str, Any]:
    """Kick off a bulk install. Returns immediately with a ``job_id`` the
    UI polls via ``/tools/install-all/status/{job_id}``.

    ``dry_run=true`` returns the planned commands without spawning anything.
    Prereq-missing tools (e.g. ``go install`` on a host without Go) are
    flagged as ``skipped`` rather than wasting an install attempt.
    """
    if not dry_run:
        _require_security_tool_install_confirmation(confirm)

    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tool catalog unavailable: {exc}")

    plan: list[dict[str, Any]] = []
    prereq_missing: list[str] = []
    for tool in catalog.get_missing():
        if category and tool.category != category:
            continue
        if offensive_only and not tool.offensive_only:
            continue
        entry = {
            "name": tool.name,
            "category": tool.category,
            "install_cmd": tool.install_cmd,
        }
        miss = _prereq_for(tool.install_cmd)
        if miss:
            prereq_missing.append(f"{tool.name} (needs {miss[1]})")
        plan.append(entry)

    if dry_run:
        return {
            "dry_run": True,
            "planned": len(plan),
            "prereq_missing": prereq_missing,
            "tools": plan,
        }

    job_id = _uuid.uuid4().hex[:12]
    _install_jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "total": len(plan),
        "done": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "cancel_requested": False,
        "current": "",
        "results": [],
        "started_at": asyncio.get_event_loop().time(),
    }
    # Fire the background task and return immediately. The task lives on
    # the event loop; when done it flips status to "complete". No UI
    # wait -- poll endpoint reports progress.
    asyncio.create_task(_run_install_job(job_id, plan))
    return {
        "job_id": job_id,
        "status": "running",
        "total": len(plan),
        "prereq_missing": prereq_missing,
        "poll_url": f"/api/v1/security/tools/install-all/status/{job_id}",
    }


@router.get("/tools/install-all/status/{job_id}")
async def install_all_status(job_id: str) -> dict[str, Any]:
    """Poll progress for a bulk-install job. Returns counters + the
    current tool being installed + the last 10 result rows so the UI
    can render a live log without asking for the full list.
    """
    job = _install_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Install job {job_id} not found")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "total": job["total"],
        "done": job["done"],
        "succeeded": job["succeeded"],
        "failed": job["failed"],
        "skipped": job["skipped"],
        "cancel_requested": bool(job.get("cancel_requested")),
        "current": job["current"],
        "recent": job["results"][-10:],
    }


@router.post("/tools/install-all/cancel/{job_id}")
async def cancel_install_all(job_id: str) -> dict[str, Any]:
    """Request cancellation of a background install job.

    Cancellation is cooperative: an active subprocess is allowed to finish, then
    the runner stops before the next tool.
    """
    job = _install_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Install job {job_id} not found")
    job["cancel_requested"] = True
    if job.get("status") == "running":
        job["status"] = "cancelling"
    return {
        "job_id": job_id,
        "status": job["status"],
        "cancel_requested": True,
        "current": job.get("current", ""),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_scan_history(
    limit: int = 20, *, archived: bool = False,
) -> list[dict[str, Any]]:
    """Load scan summaries from both scan_traces/ (legacy) and
    security_reports/ (persisted reports from the real-scan workflow).
    Dedupes on scan_id. Orders newest first. Honors ``limit``.

    Phase 10b: when ``archived=True`` the loader points at the
    ``security_reports/.archive`` sibling folder. Scans there have
    filenames of the shape ``<scan_id>.<label>.<ts>.json`` produced by
    :func:`_archive_scan`; the scan_id encoded inside the JSON payload
    is the source of truth, the filename is just a path hint.
    """
    trace_dir = Path(os.environ.get("DAENA_VAR", "var")) / "scan_traces"
    reports_root = Path(
        os.environ.get("SECURITY_REPORTS_DIR", os.path.join("var", "security_reports")),
    )
    if archived:
        # Archive lives only under the reports root. Legacy traces are
        # archived alongside reports (see ``_archive_scan``), so we
        # point both loaders at the same archive folder. The legacy
        # loader simply finds nothing if no traces are there.
        reports_dir = reports_root / ".archive"
        trace_dir = reports_root / ".archive"
    else:
        reports_dir = reports_root
    max_candidates = max(limit * 4, 100)

    def _recent_json_files(directory: Path) -> list[Path]:
        if not directory.is_dir():
            return []
        try:
            files = [
                p for p in directory.iterdir()
                if p.is_file() and p.suffix == ".json" and not p.name.startswith(".")
            ]
        except OSError:
            return []

        def _mtime(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except OSError:
                return 0.0

        files.sort(key=_mtime, reverse=True)
        return files[:max_candidates]

    by_id: dict[str, dict[str, Any]] = {}

    # Legacy scan traces (adversarial scan engine output)
    for trace_path in _recent_json_files(trace_dir):
        try:
            data = json.loads(trace_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        sid = data.get("scan_id", trace_path.stem)
        by_id[sid] = {
            "scan_id": sid,
            "target": data.get("target", ""),
            "target_type": data.get("target_type", ""),
            "total_findings": data.get("total_findings", 0),
            "cycles_used": data.get("cycles_used", 0),
            "strategies_tried": data.get("strategies_tried", []),
            "offensive_mode": data.get("offensive_mode", False),
            "exploits_succeeded": data.get("exploits_succeeded", 0),
            "waf_detected": data.get("waf_detected", ""),
            "tier": data.get("tier", ""),
            "status": "complete",
            "source": "scan_trace",
            "timestamp": data.get("timestamp", ""),
            "created_at": data.get("created_at", ""),
            "finding_count": data.get("total_findings", 0),
            # K-3: surface tenant_id (legacy traces predate it -> None,
            # which fail-closes in the list_scans ownership filter).
            "tenant_id": data.get("tenant_id"),
        }

    # Persisted real-scan reports
    for report_path in _recent_json_files(reports_dir):
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        sid = data.get("job_id", report_path.stem)
        findings = data.get("findings", []) or []
        severities = [f.get("severity", "INFO") for f in findings]
        by_id[sid] = {
            **by_id.get(sid, {}),
            "scan_id": sid,
            "target": data.get("target", ""),
            "target_type": data.get("target_kind", ""),
            "tier": data.get("tier", ""),
            "total_findings": len(findings),
            "finding_count": len(findings),
            "status": "complete",
            "source": "persisted_report",
            "created_at": data.get("created_at", 0),
            "completed_at": data.get("completed_at", 0),
            "tools_used": data.get("tools_used", []),
            "tools_missing": data.get("tools_missing", []),
            "cost_usd": data.get("cost_usd", 0.0),
            "duration_secs": data.get("duration_secs", 0.0),
            "severity_counts": {
                s: severities.count(s)
                for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
            },
            # K-3: tenant_id drives the list_scans ownership filter. Works
            # for both live and archived reports (this loader reads the
            # right dir per the ``archived`` flag). Reports written before
            # PR-SCAN-DISK-TENANT have no tenant_id -> None -> fail-closed.
            "tenant_id": data.get("tenant_id"),
        }

    history = list(by_id.values())
    history.sort(
        key=lambda h: (
            h.get("completed_at") or h.get("created_at") or 0
        ),
        reverse=True,
    )
    return history[:limit]


def _get_self_improvement_metrics() -> dict[str, Any]:
    """Get metrics about the self-improvement loop."""
    trace_dir = os.path.join(os.environ.get("DAENA_VAR", "var"), "scan_traces")
    if not os.path.isdir(trace_dir):
        return {"total_traces": 0, "upgrades_triggered": 0}

    total = len(os.listdir(trace_dir))
    upgrades = total // 10  # Every 10 scans triggers an upgrade check

    return {
        "total_traces": total,
        "upgrades_triggered": upgrades,
        "next_upgrade_at": ((total // 10) + 1) * 10,
        "traces_until_next": ((total // 10) + 1) * 10 - total,
    }
