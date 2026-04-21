"""Daena Security Dashboard API.

Provides real-time scan status, tool catalog, SHIELD activation state,
scan trace history, self-improvement metrics, and end-to-end scan workflow.

This is the backend for the /security/dashboard frontend page.
"""

from __future__ import annotations

import json
import os
from typing import Any

import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Singleton scan workflow instance (lazy-init to avoid import-time side effects)
_scan_workflow = None


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

    # Tool catalog stats
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        installed = catalog.get_installed()
        tool_stats = {
            "total_known": catalog.total_tools,
            "total_installed": len(installed),
            "total_capabilities": catalog.total_capabilities,
            "categories": catalog.categories,
            "installed_names": [t.name for t in installed],
        }
    except Exception:
        tool_stats = {"total_known": 0, "total_installed": 0}

    # Scan history (last 20 traces)
    scan_history = _load_scan_history(20)

    # Self-improvement metrics
    self_improvement = _get_self_improvement_metrics()

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
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()

        if capability:
            tools = catalog.find_by_capability(capability)
        elif category:
            tools = catalog.find_by_category(category)
        else:
            tools = catalog.get_all()

        result = []
        for tool in tools:
            is_installed = catalog.is_installed(tool.name)
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
            ))
        return result
    except Exception as exc:
        logger.error("security_dashboard.tools_failed", error=str(exc))
        return []


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
async def list_scans(limit: int = 50) -> list[dict[str, Any]]:
    """List recent scan traces."""
    return _load_scan_history(limit)


@router.get("/scans/{scan_id}")
async def get_scan_detail(scan_id: str) -> dict[str, Any]:
    """Get full detail of a specific scan trace."""
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
async def start_scan(body: ScanStartRequest) -> ScanJobResponse:
    """Start a new security scan.

    Kicks off the full intelligence pipeline:
    profiling -> parallel scanning -> analysis -> report generation.
    Returns immediately with a job ID for polling.
    """
    workflow = _get_workflow()

    # Default user/tenant for now; will be injected from auth middleware
    user_id = "system"
    tenant_id = "default"

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
async def get_scan_status(job_id: str) -> ScanStatusResponse:
    """Poll scan progress. Returns current status and completion percentage."""
    workflow = _get_workflow()

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
async def get_scan_report(job_id: str) -> ScanReportResponse:
    """Get the completed scan report with findings, cost, and summary."""
    workflow = _get_workflow()

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
async def download_scan_report_pdf(job_id: str) -> FileResponse:
    """Download the PDF report for a completed scan."""
    workflow = _get_workflow()

    try:
        report = await workflow.get_scan_report(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Scan job {job_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if not report.report_pdf_path or not os.path.isfile(report.report_pdf_path):
        raise HTTPException(
            status_code=404,
            detail="PDF report not available. Report data is accessible via /report endpoint.",
        )

    filename = os.path.basename(report.report_pdf_path)
    return FileResponse(
        path=report.report_pdf_path,
        filename=filename,
        media_type="application/pdf",
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
    job_id: str, request: Request,
) -> StreamingResponse:
    """Server-sent events for a scan job.

    Yields events emitted by ScanWorkflow: scan_started,
    scan_phase_change (one per phase transition), scan_complete,
    scan_failed. The chat UI subscribes to this endpoint when it
    receives a scan_dispatched event in the main chat SSE so the
    inline ScanProgressCard updates live.

    Connection closes when the scan terminates (complete or failed)
    or when the client disconnects.
    """
    workflow = _get_workflow()

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
            "OPSEC is background-path only. This endpoint exposes status; "
            "it never initiates network requests."
        ),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_scan_history(limit: int = 20) -> list[dict[str, Any]]:
    """Load scan trace summaries from var/scan_traces/."""
    trace_dir = os.path.join(os.environ.get("DAENA_VAR", "var"), "scan_traces")
    if not os.path.isdir(trace_dir):
        return []

    traces = sorted(os.listdir(trace_dir), reverse=True)[:limit]
    history = []
    for trace_file in traces:
        trace_path = os.path.join(trace_dir, trace_file)
        try:
            with open(trace_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            history.append({
                "scan_id": data.get("scan_id", trace_file.replace(".json", "")),
                "target": data.get("target", ""),
                "target_type": data.get("target_type", ""),
                "total_findings": data.get("total_findings", 0),
                "cycles_used": data.get("cycles_used", 0),
                "strategies_tried": data.get("strategies_tried", []),
                "offensive_mode": data.get("offensive_mode", False),
                "exploits_succeeded": data.get("exploits_succeeded", 0),
                "waf_detected": data.get("waf_detected", ""),
            })
        except (json.JSONDecodeError, OSError):
            continue

    return history


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
