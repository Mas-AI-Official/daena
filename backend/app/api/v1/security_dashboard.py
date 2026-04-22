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
    enabled: bool = True       # user toggle; False = Daena skips this tool


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

        enabled_state = _load_tool_enabled()
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
                enabled=enabled_state.get(tool.name, True),
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
    """Download the report file for a completed scan.

    The URL keeps its ``/pdf`` suffix for backward compatibility, but
    the response media type follows the actual file extension: PDF
    when reportlab was available at generation time, markdown when it
    fell back. This matches what actually landed on disk so browsers
    pick the right viewer.
    """
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


@router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str, hard: bool = False) -> dict[str, Any]:
    """Archive (default) or hard-delete a scan's trace + report.

    CLAUDE.md rule 2: archive by default; dev mode must pass ``hard=true``
    to actually unlink. Returns which artifacts were moved and where.
    """
    trace = _scan_trace_path(scan_id)
    report = _scan_report_path(scan_id)
    if not os.path.isfile(trace) and not os.path.isfile(report):
        raise HTTPException(
            status_code=404,
            detail=f"Scan {scan_id} has no trace or report on disk",
        )
    return _archive_scan(scan_id, hard=hard)


@router.delete("/scans")
async def delete_all_scans(hard: bool = False) -> dict[str, Any]:
    """Bulk archive (default) every scan in history. ``hard=true`` hard-
    deletes. Scoped to the scan_traces + security_reports directories
    owned by this process. Returns counts + per-scan status.
    """
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

    results = [_archive_scan(sid, hard=hard) for sid in sorted(scan_ids)]
    return {
        "processed": len(results),
        "hard": hard,
        "results": results,
    }


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
    logger.info(
        "security_dashboard.tool_toggled",
        tool=name, enabled=body.enabled,
    )
    return {"tool": name, "enabled": state[name]}


@router.post("/tools/install/{name}")
async def install_tool(name: str) -> dict[str, Any]:
    """Install a single tool by name. Runs the ``install_cmd`` from the
    catalog via subprocess. On success, triggers the post-install
    rule-pack hook (nuclei templates, trivy DB, etc.) so the tool is
    immediately useful on the next scan.
    """
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


@router.post("/tools/install-all")
async def install_all_tools(
    category: str = "",
    offensive_only: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Kick off a bulk install. Returns immediately with a ``job_id`` the
    UI polls via ``/tools/install-all/status/{job_id}``.

    ``dry_run=true`` returns the planned commands without spawning anything.
    Prereq-missing tools (e.g. ``go install`` on a host without Go) are
    flagged as ``skipped`` rather than wasting an install attempt.
    """
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
        "current": job["current"],
        "recent": job["results"][-10:],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_scan_history(limit: int = 20) -> list[dict[str, Any]]:
    """Load scan summaries from both scan_traces/ (legacy) and
    security_reports/ (persisted reports from the real-scan workflow).
    Dedupes on scan_id. Orders newest first. Honors ``limit``.
    """
    trace_dir = os.path.join(os.environ.get("DAENA_VAR", "var"), "scan_traces")
    reports_dir = os.environ.get(
        "SECURITY_REPORTS_DIR", os.path.join("var", "security_reports"),
    )

    by_id: dict[str, dict[str, Any]] = {}

    # Legacy scan traces (adversarial scan engine output)
    if os.path.isdir(trace_dir):
        for trace_file in sorted(os.listdir(trace_dir), reverse=True):
            if not trace_file.endswith(".json"):
                continue
            trace_path = os.path.join(trace_dir, trace_file)
            try:
                with open(trace_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            sid = data.get("scan_id", trace_file.replace(".json", ""))
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
            }

    # Persisted real-scan reports
    if os.path.isdir(reports_dir):
        for name in sorted(os.listdir(reports_dir), reverse=True):
            if not name.endswith(".json") or name.startswith("."):
                continue
            path = os.path.join(reports_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            sid = data.get("job_id", name.replace(".json", ""))
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
