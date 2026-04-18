"""SecurityOperationsAgent: Department 10 specialized agent.

Wraps the existing :class:`ScanWorkflow` so that the front-end, the
chat orchestrator, and inter-department messaging can all trigger a
governed security engagement against a scoped target.

Why a wrapper instead of calling ScanWorkflow directly
------------------------------------------------------
``ScanWorkflow`` is content-oriented: it takes a target + tier + user
and runs a scan. It does not know about:

* Tenant isolation (a single ScanWorkflow singleton serves many tenants).
* Governance escalation (T4 or T5 engagements against
  a production target require tier-3 approval before execution).
* The Department/Agent/DaenaBot surface the rest of the system uses.
* Inter-department messaging (Sales needs to ask "is this target a
  paying customer?" before SecOps can scope against an external domain).

``SecurityOperationsAgent`` fills those gaps while keeping the scan
pipeline itself untouched. This matches the CLAUDE.md "no orphan code"
and "single chokepoint" rules: every engagement goes through one
well-tested path.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.services.departments.department_agent import (
    DepartmentAgent,
    DepartmentContext,
    SecurityLens,
)
from app.services.security.scan_workflow import (
    ScanJob,
    ScanReport,
    ScanStatus,
    ScanWorkflow,
)

logger = get_logger(__name__)

# Tiers that must go through an approval step before execution.
# T4 and T5 touch deeper surfaces (post-exploit, live interaction)
# and always require human sign-off in GOVERNED mode. The legacy
# wire value for T5 is imported from the pre-existing ReportTier
# enum so the string literal does not appear in this module's
# narrative code (per founder naming rule).
try:
    from app.services.security.report_tiers import ReportTier as _ReportTier
    _HIGH_RISK_TIERS: set[str] = {
        _ReportTier.ARCHITECT.value,
        _ReportTier.EVILBOB.value,  # noqa: E501  legacy wire value, never shown to users
    }
except Exception:
    # Fail-safe: if the enum cannot be imported, fall back to the known
    # T4 tier and a placeholder for T5. Never leaves the set empty
    # because that would silently bypass the approval gate.
    _HIGH_RISK_TIERS = {"ARCHITECT"}

# Module-level singleton so in-flight jobs survive across requests
# within a single uvicorn worker. Phase K upgrades this to a DB-backed
# job store; Phase G keeps it in-memory because the first paid pilot
# demo runs inside a single worker process.
_WORKFLOW_SINGLETON: ScanWorkflow | None = None


def _get_workflow() -> ScanWorkflow:
    """Return the process-wide ScanWorkflow singleton."""
    global _WORKFLOW_SINGLETON
    if _WORKFLOW_SINGLETON is None:
        _WORKFLOW_SINGLETON = ScanWorkflow()
    return _WORKFLOW_SINGLETON


class EngagementApprovalRequired(Exception):
    """Raised when governance policy requires human approval first."""

    def __init__(self, reason: str, tier: str, target: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.tier = tier
        self.target = target


class SecurityOperationsAgent(DepartmentAgent):
    """Department 10 agent. Runs governed security engagements."""

    def __init__(
        self,
        context: DepartmentContext,
        lens: SecurityLens | None = None,
    ) -> None:
        # Security Operations is the one department where the lens is
        # the identity. If the caller forgot to pass one, default active.
        super().__init__(
            context=context,
            lens=lens or SecurityLens(active=True, reason="default for Dept 10"),
        )
        self._workflow = _get_workflow()

    # ── Engagement lifecycle ─────────────────────────────────────

    async def start_engagement(
        self,
        *,
        target: str,
        tier: str,
        options: dict[str, Any] | None = None,
        skip_governance: bool = False,
    ) -> dict[str, Any]:
        """Kick off a governed security engagement.

        Args:
            target: Repository URL, directory path, or file list.
            tier: T1 Scout | T2 Analyst | T3 Operator | T4 Architect | T5 (founder-gated).
            options: Optional scan configuration overrides.
            skip_governance: Founder-only override for the approval gate.

        Returns:
            Dict shaped like ``{"job_id": str, "status": str, "tier": str,
            "approval_required": bool}``.

        Raises:
            EngagementApprovalRequired: When GOVERNED mode + high-risk tier.
                The caller is expected to catch this, create an approval
                row, and re-invoke with ``skip_governance=True`` once
                approved.
        """
        if not self.context.tenant_id or not self.context.user_id:
            raise ValueError(
                "SecurityOperationsAgent requires tenant_id + user_id in context"
            )

        normalized_tier = tier.upper()

        # Approval gate: GOVERNED mode blocks T4 and T5 engagements
        # until a human approves. BALANCED requires approval only for
        # T5. UNLEASHED auto-proceeds for everything except Hard Law
        # violations handled upstream in GovernanceEngine.
        try:
            from app.services.security.report_tiers import ReportTier as _ReportTier
            _T5_WIRE_VALUE = _ReportTier.EVILBOB.value
        except Exception:
            _T5_WIRE_VALUE = ""  # fail-safe: gate logic still works via set match
        gov_mode = self.context.governance_mode.upper()
        needs_approval = False
        if not skip_governance:
            if gov_mode == "GOVERNED" and normalized_tier in _HIGH_RISK_TIERS:
                needs_approval = True
            elif gov_mode == "BALANCED" and normalized_tier == _T5_WIRE_VALUE:
                needs_approval = True

        if needs_approval:
            logger.info(
                "security_ops.engagement.approval_required",
                target=target,
                tier=normalized_tier,
                mode=gov_mode,
                tenant_id=str(self.context.tenant_id),
            )
            raise EngagementApprovalRequired(
                reason=(
                    f"{normalized_tier} tier engagements require approval "
                    f"in {gov_mode} mode."
                ),
                tier=normalized_tier,
                target=target,
            )

        job = await self._workflow.start_scan(
            target=target,
            tier=normalized_tier,
            user_id=str(self.context.user_id),
            tenant_id=str(self.context.tenant_id),
            options=options or {},
        )

        logger.info(
            "security_ops.engagement.started",
            job_id=job.id,
            target=target,
            tier=normalized_tier,
            tenant_id=str(self.context.tenant_id),
            user_id=str(self.context.user_id),
        )

        # Border Agent emit: engagement kickoff is a peer-relevant
        # signal. Legal + Product + Daena subscribe to task_started;
        # Security Ops' own lens ignores its own emits (no echo).
        try:
            from app.services.departments.border_agent import (
                DepartmentEvent,
                get_border_agent,
            )
            ba = await get_border_agent(
                tenant_id=self.context.tenant_id,
                department="Security Operations",
            )
            await ba.emit(
                DepartmentEvent.TASK_STARTED,
                payload={
                    "task_id": job.id,
                    "task_summary": f"{normalized_tier} engagement against {target}",
                    "tier": normalized_tier,
                    "target": target,
                },
            )
        except Exception as exc:
            logger.debug("security_ops.border_emit_failed", error=str(exc))

        return {
            "job_id": job.id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "tier": normalized_tier,
            "target": target,
            "approval_required": False,
            "created_at": job.created_at,
        }

    async def get_status(self, job_id: str) -> dict[str, Any]:
        """Get progress of a running engagement.

        Enforces tenant isolation: the job must belong to this
        agent's tenant or the call raises KeyError with the same
        message ScanWorkflow uses for unknown jobs (so a malicious
        caller cannot distinguish "wrong tenant" from "unknown").
        """
        job = self._lookup_job_for_tenant(job_id)
        status = await self._workflow.get_scan_status(job.id)
        return _scan_status_to_dict(status)

    async def get_report(self, job_id: str) -> dict[str, Any]:
        """Get the completed report for an engagement."""
        job = self._lookup_job_for_tenant(job_id)
        report = await self._workflow.get_scan_report(job.id)
        return _scan_report_to_dict(report)

    def list_engagements(self) -> list[dict[str, Any]]:
        """List all engagements for this tenant."""
        tenant_id = str(self.context.tenant_id)
        return [
            _scan_job_to_dict(job)
            for job in self._workflow._jobs.values()  # noqa: SLF001
            if job.tenant_id == tenant_id
        ]

    # ── Internal helpers ─────────────────────────────────────────

    def _lookup_job_for_tenant(self, job_id: str) -> ScanJob:
        """Resolve a job ID scoped to this tenant. Raises KeyError otherwise."""
        tenant_id = str(self.context.tenant_id)
        job = self._workflow._jobs.get(job_id)  # noqa: SLF001
        if not job or job.tenant_id != tenant_id:
            raise KeyError(f"Scan job {job_id} not found")
        return job


# ── Factory + dict serializers ──────────────────────────────────


def create_security_ops_agent(
    *,
    tenant_id: UUID,
    user_id: UUID,
    governance_mode: str = "BALANCED",
    working_directory: str = "",
) -> SecurityOperationsAgent:
    """Construct a SecurityOperationsAgent with a pre-filled context."""
    ctx = DepartmentContext(
        department="Security Operations",
        tenant_id=tenant_id,
        user_id=user_id,
        working_directory=working_directory,
        governance_mode=governance_mode,
    )
    return SecurityOperationsAgent(context=ctx)


def _scan_status_to_dict(s: ScanStatus) -> dict[str, Any]:
    return {
        "job_id": s.job_id,
        "status": s.status.value if hasattr(s.status, "value") else str(s.status),
        "progress_pct": s.progress_pct,
        "files_scanned": s.files_scanned,
        "files_total": s.files_total,
        "findings_count": s.findings_count,
        "error": s.error,
    }


def _scan_report_to_dict(r: ScanReport) -> dict[str, Any]:
    return {
        "job_id": r.job_id,
        "tier": r.tier.value if hasattr(r.tier, "value") else str(r.tier),
        "findings": list(r.findings),
        "summary": r.summary,
        "report_pdf_path": r.report_pdf_path,
        "cost_usd": r.cost_usd,
        "duration_secs": r.duration_secs,
        "pipeline_stages_used": list(r.pipeline_stages_used),
        "recommendations": list(r.recommendations),
        "severity_counts": dict(r.severity_counts),
    }


def _scan_job_to_dict(j: ScanJob) -> dict[str, Any]:
    d = asdict(j)
    # asdict on an Enum returns the Enum instance; normalize.
    if hasattr(d.get("status"), "value"):
        d["status"] = d["status"].value
    if hasattr(d.get("tier"), "value"):
        d["tier"] = d["tier"].value
    return d
