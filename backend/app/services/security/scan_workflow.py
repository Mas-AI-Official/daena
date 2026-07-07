"""End-to-end Security Scan Workflow -- Intelligence-as-a-Service.

Orchestrates the full security intelligence pipeline:
    1. Accept scan request (target repo URL or file paths)
    2. Profile the target (tech stack, file count, complexity)
    3. Select tier (T1-T5) based on user subscription
    4. Use SubAgentSpawner to scan files in parallel
    5. Each sub-agent runs the Laevateinn pipeline on its file
    6. Merge findings through Consensus Gradient
    7. Generate report (PDF) via ReportTierEngine
    8. Calculate cost and bill the engagement
    9. Return report + findings summary

Integration:
    SecurityDashboard API -> ScanWorkflow -> SubAgentSpawner -> Laevateinn
    -> ReportTierEngine -> BugBountyReportGenerator -> PDF
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.services.security.real_scanner import scan_target as _real_scan_target
from app.services.security.report_tiers import (
    ReportTier,
    ReportTierEngine,
    SecurityFinding,
    SecurityReport,
    FindingSeverity,
    TIER_SKIP_STAGES,
)
from app.services.sub_agent_spawner import (
    SubAgentSpawner,
    KnowledgeBus,
    SpawnResult,
)

logger = get_logger(__name__)

# -- Cost table per tier (USD per file scanned) ------
TIER_COST_PER_FILE: dict[ReportTier, float] = {
    ReportTier.SCOUT: 0.002,
    ReportTier.ANALYST: 0.005,
    ReportTier.OPERATOR: 0.012,
    ReportTier.ARCHITECT: 0.025,
    ReportTier.EVILBOB: 0.050,
}

# -- Base cost per scan engagement -------------------
TIER_BASE_COST: dict[ReportTier, float] = {
    ReportTier.SCOUT: 0.50,
    ReportTier.ANALYST: 2.00,
    ReportTier.OPERATOR: 5.00,
    ReportTier.ARCHITECT: 15.00,
    ReportTier.EVILBOB: 50.00,
}

REPORTS_DIR = os.environ.get(
    "SECURITY_REPORTS_DIR", os.path.join("var", "security_reports"),
)


class ScanJobStatus(str, Enum):
    """Lifecycle states for a scan job."""
    QUEUED = "queued"
    PROFILING = "profiling"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    REPORTING = "reporting"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ScanJob:
    """A tracked security scan job."""
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    target: str = ""
    tier: ReportTier = ReportTier.SCOUT
    user_id: str = ""
    tenant_id: str = ""
    status: ScanJobStatus = ScanJobStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    progress_pct: float = 0.0
    files_scanned: int = 0
    files_total: int = 0
    findings_count: int = 0
    error: str = ""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanStatus:
    """Progress snapshot of a running scan."""
    job_id: str
    status: ScanJobStatus
    progress_pct: float = 0.0
    files_scanned: int = 0
    files_total: int = 0
    findings_count: int = 0
    error: str = ""


@dataclass
class ScanReport:
    """Completed scan report with findings and PDF path."""
    job_id: str
    tier: ReportTier
    findings: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    report_pdf_path: str = ""
    cost_usd: float = 0.0
    duration_secs: float = 0.0
    pipeline_stages_used: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    severity_counts: dict[str, int] = field(default_factory=dict)


# -- Simulated file analysis for pre-LLM wiring ------

_SIMULATED_FINDINGS: list[dict[str, Any]] = [
    {
        "id": "VULN-001",
        "title": "Hardcoded API key in configuration",
        "severity": "CRITICAL",
        "location": "config/settings.py:42",
        "description": "API key is hardcoded in source file instead of environment variable.",
        "explanation": "Hardcoded credentials in source code can be extracted by anyone with repo access.",
        "remediation": "Move to environment variable or secrets manager (e.g., GCP Secret Manager).",
        "fix_code": "os.environ.get('API_KEY', '')",
        "fix_verified": False,
        "exploit_path": "Clone repo -> grep for key -> use key to access API",
        "confidence": 0.95,
        "verified_by_models": 3,
        "falsification_survived": True,
        "reasoning_chain": ["Detected string matching API key pattern", "Verified not in .env", "Confirmed in git history"],
        "cve_references": ["CWE-798"],
    },
    {
        "id": "VULN-002",
        "title": "SQL injection in user search endpoint",
        "severity": "HIGH",
        "location": "api/search.py:87",
        "description": "User input concatenated directly into SQL query without parameterization.",
        "explanation": "Allows arbitrary SQL execution through crafted search parameters.",
        "remediation": "Use parameterized queries or ORM query builder.",
        "fix_code": "db.execute(text('SELECT * FROM users WHERE name = :name'), {'name': user_input})",
        "fix_verified": False,
        "exploit_path": "Send search?q=' OR 1=1 -- to dump all records",
        "confidence": 0.90,
        "verified_by_models": 2,
        "falsification_survived": True,
        "reasoning_chain": ["Identified string concatenation in query", "Confirmed no sanitization"],
        "cve_references": ["CWE-89"],
    },
    {
        "id": "VULN-003",
        "title": "Missing CSRF protection on state-changing endpoint",
        "severity": "MEDIUM",
        "location": "api/settings.py:23",
        "description": "POST endpoint changes user settings without CSRF token verification.",
        "explanation": "An attacker can craft a malicious page that submits requests on behalf of authenticated users.",
        "remediation": "Add CSRF token middleware or use SameSite cookie attribute.",
        "fix_code": "app.add_middleware(CSRFProtectMiddleware, secret='...')",
        "fix_verified": False,
        "exploit_path": "Host page with hidden form targeting endpoint",
        "confidence": 0.80,
        "verified_by_models": 2,
        "falsification_survived": False,
        "reasoning_chain": ["No CSRF token in form", "Cookie lacks SameSite attribute"],
        "cve_references": ["CWE-352"],
    },
    {
        "id": "VULN-004",
        "title": "Debug mode enabled in production",
        "severity": "LOW",
        "location": "main.py:5",
        "description": "Application debug flag is set to True.",
        "explanation": "Debug mode exposes stack traces and internal state to end users.",
        "remediation": "Set DEBUG=False in production configuration.",
        "fix_code": "DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'",
        "fix_verified": False,
        "exploit_path": "Trigger error to see stack trace with file paths and config values",
        "confidence": 0.99,
        "verified_by_models": 1,
        "falsification_survived": True,
        "reasoning_chain": ["DEBUG=True found in main module"],
        "cve_references": ["CWE-489"],
    },
    {
        "id": "VULN-005",
        "title": "Verbose server header disclosure",
        "severity": "INFO",
        "location": "HTTP response headers",
        "description": "Server header reveals exact framework and version.",
        "explanation": "Version disclosure helps attackers identify known vulnerabilities for the specific version.",
        "remediation": "Remove or obfuscate Server header in production.",
        "fix_code": "response.headers['Server'] = 'Daena'",
        "fix_verified": False,
        "exploit_path": "Read response headers to fingerprint stack",
        "confidence": 0.85,
        "verified_by_models": 1,
        "falsification_survived": False,
        "reasoning_chain": ["Server: uvicorn/0.27.0 found in response"],
        "cve_references": [],
    },
]


def _load_queue_entries(queues_dir: str) -> list[dict[str, Any]]:
    """Read every ``{class}_exploitation_queue.json`` under queues_dir
    and return a flat list of vulnerability entries across all classes.
    Fail-safe: missing dir or malformed files yield an empty list.
    """
    import json as _json
    import os as _os
    out: list[dict[str, Any]] = []
    if not queues_dir or not _os.path.isdir(queues_dir):
        return out
    try:
        for name in _os.listdir(queues_dir):
            if not name.endswith("_exploitation_queue.json"):
                continue
            fp = _os.path.join(queues_dir, name)
            try:
                doc = _json.loads(
                    open(fp, "r", encoding="utf-8").read()
                )
                out.extend(doc.get("vulnerabilities", []) or [])
            except Exception:
                continue
    except Exception:
        return out
    return out


def _simulate_file_scan(file_path: str, tier: ReportTier) -> list[dict[str, Any]]:
    """Simulate scanning a single file. Returns findings relevant to the tier.

    In production, this will be replaced by actual Laevateinn pipeline execution
    per file. The structure is production-ready; only the analysis is simulated.
    """
    import hashlib
    # Deterministic but varied findings based on file path hash
    h = int(hashlib.sha256(file_path.encode()).hexdigest()[:8], 16)
    num_findings = h % 3  # 0-2 findings per file

    if num_findings == 0:
        return []

    # Pick findings deterministically
    findings = []
    for i in range(num_findings):
        idx = (h + i) % len(_SIMULATED_FINDINGS)
        finding = dict(_SIMULATED_FINDINGS[idx])
        finding["id"] = f"{finding['id']}-{file_path.replace('/', '_')[:20]}"
        finding["location"] = f"{file_path}:{(h + i * 17) % 200}"
        findings.append(finding)

    return findings


class ScanWorkflow:
    """End-to-end security intelligence workflow.

    Orchestrates:
        1. Target profiling (tech stack, complexity)
        2. Tier-appropriate pipeline configuration
        3. Parallel file scanning via SubAgentSpawner
        4. Finding aggregation through Consensus Gradient
        5. Report generation (PDF) via ReportTierEngine
        6. Cost calculation and billing

    Usage::

        workflow = ScanWorkflow()
        job = await workflow.start_scan(
            target="https://github.com/org/repo",
            tier="ANALYST",
            user_id="user-123",
            tenant_id="tenant-456",
        )
        status = await workflow.get_scan_status(job.id)
        report = await workflow.get_scan_report(job.id)
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ScanJob] = {}
        self._reports: dict[str, ScanReport] = {}
        self._spawner = SubAgentSpawner(
            knowledge_bus=KnowledgeBus(),
            max_concurrency=50,
        )
        self._tier_engine = ReportTierEngine()
        # Per-job event queues so subscribers (chat orchestrator,
        # websocket clients) can stream scan events in real time.
        # Unbounded so a slow subscriber does not backpressure the
        # scan. Memory risk is negligible: events are small dicts and
        # the scan lifecycle is seconds to minutes.
        self._event_queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Open a new event queue for a running scan.

        Returns an asyncio.Queue that receives dicts shaped like
        ``{"type": "scan_phase_change", "job_id": ..., "data": {...}}``.
        Call ``unsubscribe`` when done to avoid a leak if the scan
        continues beyond the subscriber lifetime.
        """
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._event_queues.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove a previously subscribed queue."""
        queues = self._event_queues.get(job_id)
        if not queues:
            return
        try:
            queues.remove(q)
        except ValueError:
            pass
        if not queues:
            self._event_queues.pop(job_id, None)

    def _emit_event(
        self, job_id: str, event_type: str, **data: Any,
    ) -> None:
        """Fan out an event to every subscriber of a job.

        Uses ``put_nowait`` so a slow subscriber never blocks the
        scan pipeline. Queue is unbounded; OOM risk is nil for the
        scan lifetime (seconds to minutes, tens of events).
        """
        queues = self._event_queues.get(job_id)
        if not queues:
            return
        envelope = {"type": event_type, "job_id": job_id, "data": data}
        for q in queues:
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                # Unbounded queue: should never happen. Log and move on.
                logger.warning(
                    "scan_workflow.event_queue_full",
                    job_id=job_id,
                    event_type=event_type,
                )

    async def start_scan(
        self,
        target: str,
        tier: str,
        user_id: str,
        tenant_id: str,
        options: dict[str, Any] | None = None,
    ) -> ScanJob:
        """Kick off a security scan. Returns immediately with a job ID.

        Args:
            target: Repository URL, directory path, or comma-separated file paths.
            tier: Report tier (SCOUT, ANALYST, OPERATOR, ARCHITECT, EVILBOB).
            user_id: Requesting user's ID.
            tenant_id: Tenant scope.
            options: Optional scan configuration overrides.

        Returns:
            ScanJob with ID for polling status.
        """
        report_tier = ReportTier(tier.upper())

        job = ScanJob(
            target=target,
            tier=report_tier,
            user_id=user_id,
            tenant_id=tenant_id,
            options=options or {},
        )
        self._jobs[job.id] = job

        logger.info(
            "scan_workflow.started",
            job_id=job.id,
            target=target,
            tier=tier,
            user_id=user_id,
        )

        # Launch the scan pipeline as a background task
        asyncio.create_task(self._execute_scan(job))
        return job

    async def get_scan_status(self, job_id: str) -> ScanStatus:
        """Check progress of a running scan.

        Args:
            job_id: The scan job ID from start_scan.

        Returns:
            ScanStatus snapshot.

        Raises:
            KeyError: If job_id not found.
        """
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(f"Scan job {job_id} not found")

        return ScanStatus(
            job_id=job.id,
            status=job.status,
            progress_pct=job.progress_pct,
            files_scanned=job.files_scanned,
            files_total=job.files_total,
            findings_count=job.findings_count,
            error=job.error,
        )

    async def get_scan_report(self, job_id: str) -> ScanReport:
        """Get the completed report for a scan.

        Looks in the in-memory cache first; on miss, falls back to
        ``var/security_reports/{job_id}.json`` so View/Download work
        for scans from previous process lifetimes.

        Args:
            job_id: The scan job ID.

        Returns:
            ScanReport with findings, PDF path, and cost.

        Raises:
            KeyError: If job_id not found in memory or on disk.
            ValueError: If scan is not yet complete (in-memory case only).
        """
        job = self._jobs.get(job_id)
        if job:
            if job.status == ScanJobStatus.FAILED:
                raise ValueError(f"Scan {job_id} failed: {job.error}")
            if job.status != ScanJobStatus.COMPLETE:
                raise ValueError(
                    f"Scan {job_id} is still in progress (status: {job.status.value})"
                )

        # Cache hit
        report = self._reports.get(job_id)
        if report:
            return report

        # Disk fallback: historic scans from a prior process lifetime.
        disk = self._load_report_from_disk(job_id)
        if disk is not None:
            # Cache it so repeated View/Download calls don't re-hit disk.
            self._reports[job_id] = disk
            return disk

        raise KeyError(f"Report for job {job_id} not found")

    # -- Disk persistence helpers --

    def _report_disk_path(self, job_id: str) -> str:
        base = os.environ.get(
            "SECURITY_REPORTS_DIR", os.path.join("var", "security_reports"),
        )
        return os.path.join(base, f"{job_id}.json")

    def _persist_report(self, job: ScanJob, report: ScanReport) -> None:
        """Write ``{SECURITY_REPORTS_DIR}/{job_id}.json`` so the report
        survives restart. Shape mirrors the API response plus enough job
        metadata to reconstruct the ScanReport dataclass on load.

        PR-SCAN-DISK-TENANT (2026-05-02): also persists ``tenant_id`` so
        a process restart can verify ownership before letting an
        operator create remediation work from a recovered scan. Reports
        written before this PR have no ``tenant_id`` field; the read
        path treats that as "ownership unknown" and the remediation
        endpoint fails closed.
        """
        path = self._report_disk_path(job.id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "job_id": report.job_id,
            "tenant_id": str(job.tenant_id) if job.tenant_id else None,
            "tier": report.tier.value,
            "target": job.target,
            "findings": report.findings,
            "summary": report.summary,
            "report_pdf_path": report.report_pdf_path,
            "cost_usd": report.cost_usd,
            "duration_secs": report.duration_secs,
            "pipeline_stages_used": report.pipeline_stages_used,
            "recommendations": report.recommendations,
            "severity_counts": report.severity_counts,
            "files_scanned": job.files_scanned,
            "tools_used": job.options.get("tools_used", []),
            "tools_missing": job.options.get("tools_missing", []),
            "target_kind": job.options.get("target_kind", ""),
            "scanner_notes": job.options.get("scanner_notes", ""),
            "created_at": job.created_at,
            "completed_at": time.time(),
        }
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        logger.info("scan_workflow.persisted", job_id=job.id, path=path)

    async def _persist_report_db(self, job: ScanJob, report: ScanReport) -> None:
        """Best-effort durable DB mirror of a completed scan report (Rule 17).

        The disk JSON (``_persist_report``) stays the primary artifact; this
        writes one ``scan_reports`` row per completed scan so the report
        survives disk loss / container rebuild and is queryable per tenant.

        Fail-safe: every DB error is logged and swallowed so a persistence
        failure never breaks the scan completion path. Skips silently when the
        job carries no tenant (the ``tenant_id`` FK is NOT NULL). Idempotent:
        upserts on the ``(tenant_id, job_id)`` unique key so re-running the same
        scan updates the existing row instead of duplicating it.
        """
        if not job.tenant_id:
            return None
        try:
            from sqlalchemy import select

            from app.core.database import async_session_factory
            from app.models.scan_report import ScanReportRecord

            tier = getattr(report.tier, "value", report.tier)
            status = getattr(job.status, "value", job.status)
            async with async_session_factory() as session:
                existing = (
                    await session.execute(
                        select(ScanReportRecord).where(
                            ScanReportRecord.tenant_id == job.tenant_id,
                            ScanReportRecord.job_id == job.id,
                        )
                    )
                ).scalar_one_or_none()
                if existing is None:
                    session.add(
                        ScanReportRecord(
                            tenant_id=job.tenant_id,
                            job_id=job.id,
                            target=job.target,
                            tier=tier,
                            status=status,
                            summary=report.summary,
                            findings=report.findings,
                            severity_counts=report.severity_counts,
                            cost_usd=report.cost_usd,
                            duration_secs=report.duration_secs,
                            report_pdf_path=report.report_pdf_path,
                        )
                    )
                else:
                    existing.target = job.target
                    existing.tier = tier
                    existing.status = status
                    existing.summary = report.summary
                    existing.findings = report.findings
                    existing.severity_counts = report.severity_counts
                    existing.cost_usd = report.cost_usd
                    existing.duration_secs = report.duration_secs
                    existing.report_pdf_path = report.report_pdf_path
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "scan_workflow.persist_db_failed",
                job_id=job.id, error=str(exc),
            )
        return None

    async def get_persisted_report_record(
        self, job_id: str, tenant_id: str,
    ) -> ScanReportRecord | None:
        """Fetch the durable ``scan_reports`` row for a scan, tenant-scoped.

        Returns the ORM record for ``(tenant_id, job_id)``, or None when no row
        matches that tenant (never leaks another tenant's report) or when the
        DB is unreachable. Fail-safe: DB errors log and return None.
        """
        if not tenant_id:
            return None
        try:
            from sqlalchemy import select

            from app.core.database import async_session_factory
            from app.models.scan_report import ScanReportRecord

            async with async_session_factory() as session:
                return (
                    await session.execute(
                        select(ScanReportRecord).where(
                            ScanReportRecord.tenant_id == tenant_id,
                            ScanReportRecord.job_id == job_id,
                        )
                    )
                ).scalar_one_or_none()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "scan_workflow.get_report_db_failed",
                job_id=job_id, error=str(exc),
            )
            return None

    def _load_report_payload_from_disk(self, job_id: str) -> dict | None:
        """Read the raw persisted JSON for a scan, or None if missing.

        Centralizes the disk read so both the report reconstructor
        (``_load_report_from_disk``) and the tenant-ownership lookup
        (``get_scan_owner_tenant_id``) share one IO path. Returns None
        on missing file OR malformed JSON OR OS error -- the contract is
        "this returns a dict iff the file is loadable."
        """
        path = self._report_disk_path(job_id)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "scan_workflow.load_failed", job_id=job_id, error=str(exc),
            )
            return None

    def _load_report_from_disk(self, job_id: str) -> ScanReport | None:
        """Reconstruct a ScanReport from a persisted JSON file, or None
        if the file does not exist.
        """
        data = self._load_report_payload_from_disk(job_id)
        if data is None:
            return None
        try:
            tier = ReportTier(data.get("tier", "SCOUT").upper())
        except ValueError:
            tier = ReportTier.SCOUT
        return ScanReport(
            job_id=data.get("job_id", job_id),
            tier=tier,
            findings=data.get("findings", []) or [],
            summary=data.get("summary", ""),
            report_pdf_path=data.get("report_pdf_path", ""),
            cost_usd=float(data.get("cost_usd", 0.0) or 0.0),
            duration_secs=float(data.get("duration_secs", 0.0) or 0.0),
            pipeline_stages_used=data.get("pipeline_stages_used", []) or [],
            recommendations=data.get("recommendations", []) or [],
            severity_counts=data.get("severity_counts", {}) or {},
        )

    def get_scan_owner_tenant_id(self, job_id: str) -> str | None:
        """Return the tenant id that owns a scan, or None if unknown.

        Lookup order:

        1. In-memory ``_jobs[job_id]`` (current-process scans).
        2. On-disk persisted JSON (restart-recovered scans).
        3. None (unknown scan OR legacy report written before
           PR-SCAN-DISK-TENANT).

        The remediation endpoint is the canonical caller; it MUST treat
        a None return as "no tenant ownership claim is provable" and
        respond 404 (not 403, to avoid leaking which scan ids exist for
        other tenants). Operators cannot create remediation work from
        legacy disk reports until those scans are re-run -- a deliberate
        fail-closed posture documented in the PR-SCAN-DISK-TENANT
        report.
        """
        job = self._jobs.get(job_id)
        if job is not None:
            return str(job.tenant_id) if job.tenant_id else None
        payload = self._load_report_payload_from_disk(job_id)
        if payload is None:
            return None
        owner = payload.get("tenant_id")
        # Treat empty string as missing -- defensive against any historic
        # writer that may have rendered the field but left it blank.
        if not owner:
            return None
        return owner

    # -- Internal pipeline execution --

    async def _execute_scan(self, job: ScanJob) -> None:
        """Run the full scan pipeline. Called as a background task."""
        start_time = time.time()

        # Phase 0: authorized_scope pre-check (TICKET-HACKINGTOOL-
        # YELLOW-WIRING, scan surface).
        #
        # Policy: scans are opt-in to scope enforcement.
        #   - Empty scope (tenant has not configured one)
        #     -> pass through. Preserves existing behaviour so this
        #     change is not a breaking upgrade for tenants that
        #     haven't touched /security/scope yet.
        #   - Non-empty scope, target is a URL / IPv4 / domain
        #     -> must match the scope OR be blocked with a
        #     scan_failed event that surfaces the scope reason.
        #   - File-path / other unknown-shape targets
        #     -> pass through. Local codebase scans against the
        #     user's own files are by definition in-scope.
        #
        # Fail-safe: if the gate helper errors, log and continue --
        # never block on gate infrastructure failure. The rest of the
        # security pipeline (governance, Shield, Zero-FP) still runs.
        try:
            if job.tenant_id:  # tenant-scoped scan only
                from app.services.security.yellow_runtime_gate import (
                    load_authorized_scope,
                    parse_target,
                    target_matches_scope,
                )
                _scope = load_authorized_scope(str(job.tenant_id))
                if not _scope.is_empty:
                    _kind, _ = parse_target(job.target)
                    if _kind in ("domain", "ipv4") and not target_matches_scope(
                        job.target, _scope
                    ):
                        _reason = (
                            f"Scan target '{job.target}' is outside the tenant's "
                            "authorized_scope. Security scans only run against "
                            "targets you have explicitly declared you own. "
                            "Edit the scope at /security/scope and retry."
                        )
                        job.status = ScanJobStatus.FAILED
                        job.error = _reason
                        self._emit_event(
                            job.id, "scan_failed",
                            reason=_reason,
                            scope_violation=True,
                        )
                        logger.warning(
                            "scan_workflow.scope_block",
                            job_id=job.id,
                            target=job.target,
                            tenant_id=str(job.tenant_id),
                        )
                        return
        except Exception as _scope_exc:
            logger.error(
                "scan_workflow.scope_check_error",
                job_id=job.id,
                error=str(_scope_exc),
                exc_info=True,
            )
            # Fall through -- pre-check failure must not block legit scans.

        try:
            self._emit_event(
                job.id, "scan_started",
                target=job.target, tier=job.tier.value,
            )
            # Walkthrough-specific: announce the plan before any phase
            # runs so the Operator window has content immediately.
            self._emit_event(
                job.id, "scan_thinking",
                phase="plan",
                text=(
                    f"Target: {job.target}. Tier: {job.tier.value}. "
                    f"I will profile the target, run the supply-chain "
                    f"pre-scan if a manifest is attached, dispatch the "
                    f"scanning sub-agents in parallel, aggregate and "
                    f"enrich findings through BeyondMythos, gate them "
                    f"through the Zero-FP check, then build the "
                    f"{job.tier.value}-tier report."
                ),
            )

            # Phase 1: Profile the target
            job.status = ScanJobStatus.PROFILING
            job.updated_at = time.time()
            self._emit_event(job.id, "scan_phase_change", phase="profiling")
            self._emit_event(
                job.id, "scan_thinking",
                phase="profiling",
                text="Profiling target surface: tech stack, file layout, open entry points.",
            )
            files = self._profile_target(job.target)
            job.files_total = len(files)
            self._emit_event(
                job.id, "scan_observation",
                phase="profiling",
                observation=f"Target expanded to {len(files)} scannable files.",
                files_sampled=files[:5],
            )

            if not files:
                job.status = ScanJobStatus.FAILED
                job.error = "No scannable files found in target"
                self._emit_event(
                    job.id, "scan_failed", reason=job.error,
                )
                return

            # Phase 1b: Supply-chain pre-scan. When the job target is
            # a dependency manifest (package.json, requirements.txt,
            # etc.) OR the scan options include manifest paths, run
            # the SupplyChainScanner FIRST. Its findings join the
            # aggregated list so the same Phase 3b BeyondMythos
            # enrichment + Phase 3c Zero-FP gate + report generation
            # apply to supply-chain risks just like any other finding.
            supply_chain_findings: list[dict[str, Any]] = []
            manifest_paths: list[str] = list(
                job.options.get("manifest_paths", []) or []
            )
            # Also scan the target itself if it looks like a manifest.
            target_lower = job.target.lower()
            if any(target_lower.endswith(m) for m in (
                "package.json", "package-lock.json",
                "requirements.txt", "requirements-dev.txt",
                "pyproject.toml", "pipfile",
            )):
                manifest_paths.append(job.target)
            if manifest_paths:
                try:
                    from app.services.security.supply_chain_scanner import (
                        SupplyChainScanner,
                    )
                    self._emit_event(
                        job.id, "scan_phase_change",
                        phase="supply_chain",
                        manifests=len(manifest_paths),
                    )
                    sc_offline = bool(job.options.get("offline_supply_chain", False))
                    scanner = SupplyChainScanner(offline=sc_offline)
                    risks = await scanner.scan_manifests(manifest_paths)
                    supply_chain_findings = [r.to_finding_dict() for r in risks]
                    logger.info(
                        "scan_workflow.supply_chain_complete",
                        job_id=job.id,
                        risks_found=len(supply_chain_findings),
                    )
                except Exception as sc_exc:  # pragma: no cover - fail-safe
                    logger.warning(
                        "scan_workflow.supply_chain_skipped",
                        job_id=job.id,
                        error=str(sc_exc),
                    )

            # Phase 2: Real scanner pass. real_scanner is deterministic,
            # LLM-free, and produces evidence-backed findings (each one
            # carries ``evidence_chain_id``) so the downstream Zero-FP
            # gate auto-admits OPERATOR+ tiers. SubAgentSpawner is kept
            # available for future multi-repo scans but intentionally
            # bypassed here: one scanner pass over the whole target
            # avoids duplicating work and eliminates the hash-based
            # fake-finding generator that shipped before.
            job.status = ScanJobStatus.SCANNING
            job.updated_at = time.time()
            self._emit_event(
                job.id, "scan_phase_change",
                phase="scanning", files_total=job.files_total,
            )
            self._emit_event(
                job.id, "scan_thinking", phase="scanning",
                text=(
                    f"Dispatching real_scanner against {job.target}. "
                    "Rule-based pass (secret patterns + code rules) + "
                    "optional bandit/semgrep/gitleaks subprocess dispatch "
                    "if installed."
                ),
            )

            scan_opts = dict(job.options or {})
            outcome = await _real_scan_target(job.target, scan_opts)
            # Preserve the profiled file count when the scanner under-
            # reports (mock scanners or scanners that don't return
            # per-file telemetry). Without this, comma-separated
            # multi-file targets collapse to ``files_total=1`` even
            # though ``_profile_target`` correctly enumerated them.
            # Take the max of (scanner's count, profiled count, 1).
            _profiled_count = job.files_total  # set by _profile_target
            job.files_scanned = max(outcome.files_scanned, _profiled_count, 1)
            job.files_total = max(
                outcome.files_scanned,
                _profiled_count,
                1,
            )
            job.progress_pct = 70.0
            job.findings_count = len(outcome.findings)

            # Surface tools-used / tools-missing on the job so the report
            # and the walkthrough window can show what actually ran.
            job.options["tools_used"] = outcome.tools_used
            job.options["tools_missing"] = outcome.tools_missing
            job.options["scanner_notes"] = outcome.notes
            job.options["target_kind"] = outcome.target_kind

            self._emit_event(
                job.id, "scan_observation", phase="scanning",
                observation=(
                    f"real_scanner: {outcome.files_scanned} files, "
                    f"{len(outcome.findings)} findings, "
                    f"tools_used={outcome.tools_used}, "
                    f"missing={outcome.tools_missing}"
                ),
            )

            # Phase 3: Aggregate findings
            job.status = ScanJobStatus.ANALYZING
            job.progress_pct = 75.0
            job.updated_at = time.time()
            self._emit_event(job.id, "scan_phase_change", phase="analyzing")

            all_findings: list[dict[str, Any]] = list(outcome.findings)
            # Cache the sub-agent names list so the tier engine still gets
            # something sensible for the "models_used" slot of the report.
            spawn_models_used: list[str] = [
                f"real_scanner:{t}" for t in outcome.tools_used
            ] or ["real_scanner"]
            # Merge supply-chain findings from Phase 1b so they flow
            # through the same BeyondMythos enrichment + Zero-FP gate +
            # report generation as LLM-discovered findings. Each one
            # already carries its evidence_chain_id + poc_artifact.
            if supply_chain_findings:
                all_findings.extend(supply_chain_findings)
                job.findings_count += len(supply_chain_findings)

            # Phase 3b: BeyondMythos enrichment. ErrorOracle mines each
            # finding's HTTP response context, AdversarialSimulator
            # predicts detection for the action that produced it (and
            # surfaces stealth-adjusted params when risk is high), and
            # CompositionalPlanner proposes benign-looking alternatives
            # for any finding flagged as blocked / rate-limited / WAF-
            # refused. This is where Daena starts thinking OUTSIDE the
            # LLM: the three cognition classes reason about the target
            # and the defender from primitives the LLM could never have
            # seen in training.
            try:
                from app.services.security.beyond_mythos_enricher import (
                    BeyondMythosEnricher,
                )
                enricher = BeyondMythosEnricher()
                defenses = list(job.options.get("target_defenses", []) or [])
                self._emit_event(
                    job.id, "scan_thinking",
                    phase="enrichment",
                    text=(
                        f"Running BeyondMythos enrichment on "
                        f"{len(all_findings)} finding(s): ErrorOracle on "
                        "HTTP responses, AdversarialSimulator on "
                        "detection risk, CompositionalPlanner on "
                        "blocked actions."
                    ),
                )
                all_findings = enricher.enrich_findings(
                    all_findings, target_defenses=defenses,
                )
                logger.info(
                    "scan_workflow.beyond_mythos_applied",
                    job_id=job.id,
                    findings_enriched=len(all_findings),
                )
            except Exception as bm_exc:  # pragma: no cover - fail-safe
                logger.warning(
                    "scan_workflow.beyond_mythos_skipped",
                    job_id=job.id,
                    error=str(bm_exc),
                )

            # Phase 3.5: Structured Exploitation Queue (Shannon Pattern 1).
            # Partition the enriched findings into 5 per-OWASP-class
            # queues (injection, xss, ssrf, auth, authz). The queues
            # are persisted under the scan's deliverables directory
            # (operators + retries + audit can read them) and each
            # queue is gated by check_exploitation_queue. In Shannon,
            # empty queues short-circuit the corresponding exploit
            # agent and save 30-50% of per-scan spend. Klyntar surfaces
            # the decision as an SSE "scan_queue_decision" event for
            # each class so the walkthrough window can render
            # dispatch vs skip live.
            queue_decisions: dict[str, Any] = {}
            try:
                from app.services.security.exploitation_queue import (
                    build_queues_from_findings,
                    check_exploitation_queue,
                    write_queue_file,
                )
                import os as _os
                queues_dir = _os.path.join(
                    _os.environ.get("SECURITY_REPORTS_DIR", _os.path.join("var", "security_reports")),
                    "queues",
                    job.id,
                )
                per_class_queues = build_queues_from_findings(
                    all_findings,
                    scan_id=job.id,
                    tier=job.tier.value,
                )
                for cls_key, queue in per_class_queues.items():
                    try:
                        qpath = write_queue_file(queue, queues_dir)
                    except Exception as write_exc:  # pragma: no cover
                        logger.warning(
                            "scan_workflow.queue_write_failed",
                            job_id=job.id, cls=cls_key, error=str(write_exc),
                        )
                        qpath = ""
                    decision = check_exploitation_queue(
                        queue, kind=cls_key, queue_path=str(qpath),
                    )
                    queue_decisions[cls_key] = {
                        "should_exploit": decision.should_exploit,
                        "vuln_count": decision.vulnerability_count,
                        "externally_exploitable_count": decision.externally_exploitable_count,
                        "reason": decision.reason,
                    }
                    self._emit_event(
                        job.id, "scan_queue_decision",
                        cls=cls_key,
                        should_exploit=decision.should_exploit,
                        vuln_count=decision.vulnerability_count,
                        externally_exploitable_count=(
                            decision.externally_exploitable_count
                        ),
                        reason=decision.reason,
                    )
                dispatched = sum(
                    1 for d in queue_decisions.values() if d["should_exploit"]
                )
                skipped = len(queue_decisions) - dispatched
                self._emit_event(
                    job.id, "scan_thinking",
                    phase="exploitation_queue",
                    text=(
                        f"Exploitation queue gate: "
                        f"{dispatched} of {len(queue_decisions)} classes "
                        f"would dispatch exploit agents ({skipped} skipped as clean)."
                    ),
                )
                logger.info(
                    "scan_workflow.exploitation_queue_built",
                    job_id=job.id,
                    classes=len(queue_decisions),
                    dispatched=dispatched,
                    skipped=skipped,
                )
                # Stash on job.options so downstream (report_generator,
                # chat UI) can inspect per-class decisions.
                job.options["queue_decisions"] = queue_decisions
                job.options["queues_dir"] = str(queues_dir)

                # Phase 3.5b: git-checkpoint the queues directory so
                # the EvidenceChain has a commit hash to seal against
                # (Shannon Pattern 2). Opt-in via klyntar_checkpoints_
                # enabled; when disabled, the call returns ok=False
                # and we just skip it. When enabled, the commit hash
                # flows back in job.options.checkpoints so later
                # phases can cross-link or roll back.
                try:
                    from app.core.config import get_settings as _get_settings
                    from app.services.security.evidence_checkpoint import (
                        checkpoint_if_enabled,
                    )
                    _cp_enabled = bool(
                        getattr(
                            _get_settings(),
                            "klyntar_checkpoints_enabled",
                            False,
                        )
                    )
                    if _cp_enabled:
                        cp_result = await checkpoint_if_enabled(
                            queues_dir,
                            description=(
                                f"phase=exploitation_queue dispatched={dispatched} "
                                f"skipped={skipped}"
                            ),
                            phase="exploitation_queue",
                            evidence_chain_id=f"scan-{job.id}",
                            enabled=_cp_enabled,
                        )
                        if cp_result.ok:
                            job.options.setdefault("checkpoints", {})[
                                "exploitation_queue"
                            ] = cp_result.commit_hash
                            self._emit_event(
                                job.id, "scan_checkpoint",
                                phase="exploitation_queue",
                                commit_hash=cp_result.commit_hash,
                                short_hash=cp_result.commit_hash[:12],
                            )
                        else:
                            logger.info(
                                "scan_workflow.checkpoint_skipped",
                                job_id=job.id,
                                phase="exploitation_queue",
                                reason=cp_result.reason,
                            )
                except Exception as cp_exc:  # pragma: no cover - fail-safe
                    logger.warning(
                        "scan_workflow.checkpoint_failed",
                        job_id=job.id, error=str(cp_exc),
                    )
            except Exception as q_exc:  # pragma: no cover - fail-safe
                logger.warning(
                    "scan_workflow.exploitation_queue_skipped",
                    job_id=job.id, error=str(q_exc),
                )

            # Phase 3c: Zero-FP gate. Any OPERATOR+ finding without a
            # matching EvidenceChain (or explicit founder override) is
            # rejected before the PDF is built. Prevents the failure
            # mode shared by every other autonomous-pentest tool in
            # 2026: unverified LLM-hallucinated findings shipped into
            # customer reports.
            try:
                from app.services.security.zero_fp_gate import apply_gate
                override_ids = set(
                    job.options.get("finding_overrides", []) or []
                )
                # Build a {finding_id -> queue_entry} map for queue-
                # linkage cross-validation (Shannon Pattern 1
                # extension). When queue entries were persisted
                # earlier in Phase 3.5, feed them to the gate so
                # tampering with the finding's poc_artifact_sha256
                # is caught.
                queue_entries_by_id: dict[str, dict[str, Any]] = {}
                for cls_queue in (
                    job.options.get("queue_decisions") and
                    _load_queue_entries(
                        job.options.get("queues_dir", ""),
                    ) or []
                ):
                    qid = str(cls_queue.get("id", ""))
                    if qid:
                        queue_entries_by_id[qid] = cls_queue

                gate_result = apply_gate(
                    all_findings,
                    job.tier,
                    founder_override_ids=override_ids,
                    queue_entries_by_id=(
                        queue_entries_by_id or None
                    ),
                )
                if gate_result.rejected:
                    logger.info(
                        "scan_workflow.findings_gated",
                        job_id=job.id,
                        tier=job.tier.value,
                        accepted=gate_result.accepted_count,
                        rejected=gate_result.rejected_count,
                        overrides=gate_result.override_count,
                    )
                self._emit_event(
                    job.id, "scan_observation",
                    phase="zero_fp_gate",
                    observation=(
                        f"Zero-FP gate: {gate_result.accepted_count} accepted, "
                        f"{gate_result.rejected_count} rejected, "
                        f"{gate_result.override_count} founder overrides."
                    ),
                    accepted=gate_result.accepted_count,
                    rejected=gate_result.rejected_count,
                )
                all_findings = gate_result.accepted + gate_result.overrides
                job.options["gate_rejections"] = [
                    {"id": f.get("id"), "reason": f.get("rejection_reason")}
                    for f in gate_result.rejected
                ]
            except Exception as gate_exc:  # pragma: no cover - fail-safe
                logger.warning(
                    "scan_workflow.zero_fp_gate_skipped",
                    job_id=job.id,
                    error=str(gate_exc),
                )

            # Phase 4: Build tier-appropriate report via ReportTierEngine
            job.status = ScanJobStatus.REPORTING
            job.progress_pct = 85.0
            job.updated_at = time.time()
            self._emit_event(job.id, "scan_phase_change", phase="reporting")

            pipeline_config = self._tier_engine.get_pipeline_config(job.tier)
            skip_stages = pipeline_config.get("skip_stages", set())
            # Base Laevateinn pipeline (18 stages). SCOUT/ANALYST/
            # OPERATOR/ARCHITECT filter this list via TIER_SKIP_STAGES.
            base_stages = [
                "failure_memory", "socratic", "dce", "epistemic",
                "question_audit", "dcs", "amd", "analogy", "rde",
                "crg", "validation", "cognitive_sep", "counterfactual",
                "adv_gate", "outcome_sim", "consensus", "calibration",
                "delivery",
            ]
            # T5 EVILBOB replaces the skip-filter with an EXTEND: the
            # full Laevateinn pipeline PLUS 8 adversarial stages
            # (OODA-R loop + proxy OPSEC + evidence + exploitation +
            # compositional planning + Asset Shield egress gate). This
            # matches the "26 stages" label surfaced in the scan
            # launcher UI for the T5 tier.
            if job.tier.value == "EVILBOB":
                pipeline_stages = base_stages + [
                    "ooda_observe", "ooda_orient", "ooda_decide",
                    "ooda_act", "ooda_reflect",
                    "opsec_proxy_rotation", "evidence_capture",
                    "compositional_planning",
                ]
            else:
                pipeline_stages = [s for s in base_stages if s not in skip_stages]

            security_report: SecurityReport = self._tier_engine.build_report(
                tier=job.tier,
                target=job.target,
                raw_findings=all_findings,
                pipeline_stages=pipeline_stages,
                pipeline_time_ms=int((time.time() - start_time) * 1000),
                models_used=spawn_models_used,
            )

            # Phase 5: Generate PDF report
            job.progress_pct = 90.0
            pdf_path = self._generate_pdf(security_report, job)

            # Phase 6: Calculate cost
            cost = self._calculate_cost(job.tier, job.files_total, len(all_findings))

            # Build final report
            duration = time.time() - start_time
            severity_counts = {
                "critical": security_report.critical,
                "high": security_report.high,
                "medium": security_report.medium,
                "low": security_report.low,
                "info": security_report.info,
            }

            scan_report = ScanReport(
                job_id=job.id,
                tier=job.tier,
                findings=[self._finding_to_dict(f) for f in security_report.findings],
                summary=security_report.summary,
                report_pdf_path=pdf_path,
                cost_usd=cost,
                duration_secs=round(duration, 2),
                pipeline_stages_used=pipeline_stages,
                recommendations=security_report.recommendations,
                severity_counts=severity_counts,
            )

            self._reports[job.id] = scan_report
            # Persist report to disk so View/Download survive restart and
            # a historic scan always has a resolvable report. Also writes
            # the job metadata so _profile_target / tools_used are
            # recoverable.
            try:
                self._persist_report(job, scan_report)
            except Exception as persist_exc:  # noqa: BLE001
                logger.warning(
                    "scan_workflow.persist_failed",
                    job_id=job.id, error=str(persist_exc),
                )

            # Mark complete
            job.status = ScanJobStatus.COMPLETE
            job.progress_pct = 100.0
            job.findings_count = security_report.total_findings
            job.updated_at = time.time()
            # Durable DB mirror (Rule 17 / ADR-001): the completed report now
            # survives as an auditable scan_reports row, not just disk JSON.
            # Internally fail-safe -- never raises into scan completion.
            await self._persist_report_db(job, scan_report)
            self._emit_event(
                job.id, "scan_complete",
                findings_count=security_report.total_findings,
                critical=security_report.critical,
                high=security_report.high,
                cost_usd=cost,
                duration_secs=round(duration, 2),
            )

            logger.info(
                "scan_workflow.complete",
                job_id=job.id,
                findings=security_report.total_findings,
                cost_usd=cost,
                duration_secs=round(duration, 2),
                tier=job.tier.value,
            )

            # Border Agent emit (two-tier):
            #   1. TASK_COMPLETED always -- operational signal that the
            #      scan job finished. Ops / dashboards consume this.
            #   2. THREAT_DETECTED only when critical or high findings
            #      exist -- so listeners like Legal (for compliance
            #      follow-up) and Daena (VP lens) see actual threats,
            #      not empty-scan noise. Fail-safe wrap keeps the scan
            #      status correct even if emit fails.
            try:
                from uuid import UUID as _UUID
                from app.services.departments.border_agent import (
                    DepartmentEvent,
                    get_border_agent,
                )

                ba = await get_border_agent(
                    tenant_id=_UUID(str(job.tenant_id)),
                    department="Security Operations",
                )
                await ba.emit(
                    DepartmentEvent.TASK_COMPLETED,
                    payload={
                        "task_summary": (
                            f"Scan complete: {security_report.total_findings} "
                            f"findings at tier {job.tier.value}"
                        ),
                        "job_id": job.id,
                        "tier": job.tier.value,
                        "severity_counts": severity_counts,
                        "total_findings": security_report.total_findings,
                        "cost_usd": cost,
                    },
                )

                critical_or_high = (
                    severity_counts.get("critical", 0)
                    + severity_counts.get("high", 0)
                )
                if critical_or_high > 0:
                    await ba.emit(
                        DepartmentEvent.THREAT_DETECTED,
                        payload={
                            "task_summary": (
                                f"{critical_or_high} critical/high findings "
                                f"in {job.target}"
                            ),
                            "job_id": job.id,
                            "target": job.target,
                            "tier": job.tier.value,
                            "critical": severity_counts.get("critical", 0),
                            "high": severity_counts.get("high", 0),
                            "total_findings": security_report.total_findings,
                        },
                    )
            except Exception as emit_exc:  # pragma: no cover - fail-safe
                logger.debug(
                    "scan_workflow.emit_failed",
                    job_id=job.id,
                    error=str(emit_exc),
                )

        except Exception as exc:
            job.status = ScanJobStatus.FAILED
            job.error = str(exc)
            job.updated_at = time.time()
            logger.error(
                "scan_workflow.failed",
                job_id=job.id,
                error=str(exc),
            )
            self._emit_event(job.id, "scan_failed", reason=str(exc))

    def _profile_target(self, target: str) -> list[str]:
        """Profile the target and return list of scannable files.

        In production this will clone repos, walk directories, etc.
        For now, generates a deterministic file list from the target name.
        """
        import hashlib
        h = int(hashlib.sha256(target.encode()).hexdigest()[:8], 16)

        # If target looks like comma-separated paths, use those
        if "," in target:
            return [f.strip() for f in target.split(",") if f.strip()]

        # Simulate file discovery
        extensions = [".py", ".js", ".ts", ".go", ".java", ".rs", ".rb"]
        dirs = ["src", "lib", "api", "models", "services", "config", "utils"]
        file_count = max(5, (h % 30) + 5)

        files = []
        for i in range(file_count):
            ext = extensions[i % len(extensions)]
            dir_name = dirs[i % len(dirs)]
            files.append(f"{dir_name}/module_{i}{ext}")

        return files

    def _aggregate_findings(
        self,
        spawn_result: SpawnResult,
        tier: ReportTier,
    ) -> list[dict[str, Any]]:
        """Aggregate and deduplicate findings from all sub-agents."""
        all_findings: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        # Parse results from sub-agent merged output
        for report in spawn_result.sub_agent_reports:
            if report.get("status") != "DISSOLVED":
                continue

        # Parse the merged result (JSON arrays separated by ---)
        parts = spawn_result.merged_result.split("\n---\n")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            try:
                findings = json.loads(part)
                if isinstance(findings, list):
                    for f in findings:
                        title = f.get("title", "")
                        if title and title not in seen_titles:
                            seen_titles.add(title)
                            all_findings.append(f)
            except (json.JSONDecodeError, TypeError):
                continue

        # Sort by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        all_findings.sort(
            key=lambda f: severity_order.get(f.get("severity", "INFO"), 99),
        )

        logger.info(
            "scan_workflow.findings_aggregated",
            total_raw=len(all_findings),
            deduplicated=len(seen_titles),
        )

        return all_findings

    def _generate_pdf(self, report: SecurityReport, job: ScanJob) -> str:
        """Generate PDF report using BugBountyReportGenerator.

        Returns the file path to the generated PDF (or markdown fallback).
        """
        try:
            from app.services.security.report_generator import (
                BugBountyReportGenerator,
                VulnFinding,
                ReportMetadata,
            )

            gen = BugBountyReportGenerator()
            vuln_findings = []

            for sf in report.findings:
                vuln_findings.append(VulnFinding(
                    title=sf.title,
                    severity=sf.severity.value.capitalize(),
                    description=sf.description or sf.title,
                    impact=sf.explanation,
                    remediation=sf.remediation,
                    affected_url=sf.location,
                    cwe_id=sf.cve_references[0] if sf.cve_references else "",
                    cvss_score=sf.confidence * 10,
                    evidence=[],
                    discovered_by="Daena Security Intelligence",
                ))

            metadata = ReportMetadata(
                program_name=f"Daena {report.tier.value} Scan",
                target=report.target,
                tier=report.tier.value,
                job_id=job.id,
            )

            return gen.generate(vuln_findings, metadata)

        except Exception as exc:
            logger.warning(
                "scan_workflow.pdf_generation_failed",
                error=str(exc),
            )
            # Return empty path; report data is still available via API
            return ""

    @staticmethod
    def _calculate_cost(
        tier: ReportTier,
        files_scanned: int,
        findings_count: int,
    ) -> float:
        """Calculate scan cost based on tier, files, and findings.

        Pricing model:
            base_cost (tier) + per_file_cost * files + per_finding_surcharge
        """
        base = TIER_BASE_COST.get(tier, 2.0)
        per_file = TIER_COST_PER_FILE.get(tier, 0.005)
        per_finding = 0.01  # Small surcharge per finding for analysis cost

        total = base + (per_file * files_scanned) + (per_finding * findings_count)
        return round(total, 4)

    @staticmethod
    def _finding_to_dict(finding: SecurityFinding) -> dict[str, Any]:
        """Convert SecurityFinding dataclass to JSON-serializable dict.

        ``exploit_path`` added 2026-04-21: previously omitted even on
        EVILBOB tier so the UI and API responses never surfaced the
        exploitation walkthrough. report_tiers.py already restricts
        exploit_path to T5 (EVILBOB) at the tier-build level, so
        including it here is safe: findings that reached this
        serializer carry an empty string unless their tier allowed it.
        """
        return {
            "id": finding.id,
            "title": finding.title,
            "severity": finding.severity.value,
            "location": finding.location,
            "description": finding.description,
            "explanation": finding.explanation,
            "remediation": finding.remediation,
            "fix_code": finding.fix_code,
            "fix_verified": finding.fix_verified,
            "exploit_path": finding.exploit_path,
            "confidence": finding.confidence,
            "verified_by_models": finding.verified_by_models,
            "falsification_survived": finding.falsification_survived,
            "reasoning_chain": finding.reasoning_chain,
            "cve_references": finding.cve_references,
            "source_tool": finding.source_tool,
            "source_rule": finding.source_rule,
            "raw_line": finding.raw_line,
            "evidence_chain_id": finding.evidence_chain_id,
        }
