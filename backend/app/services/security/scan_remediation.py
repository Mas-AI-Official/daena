"""Scan finding -> remediation Task + Workstream wiring (PR-SCAN-WS-01).

Closes the PR-4 debt: the operator can read the remediation text on a
finding card, but the report itself does not produce trackable work.
This module creates a Task (existing autopilot queue) plus a Workstream
shell (PR-5 source_type=SCAN) that links back to the originating scan
report and finding so the operator can pause / redirect / archive the
remediation work the same way they manage any other Workstream.

Design notes
------------
- The function ``create_remediation`` is the single entry point. The
  HTTP endpoint in ``api/v1/security_dashboard.py`` is a thin wrapper
  around it; tests exercise the function directly so they do not need
  to spin up the FastAPI app.
- Idempotency is implemented as a per-tenant linear scan of Workstreams
  with ``source_type=SCAN`` filtered by ``artifact_refs.scan_report_ids``
  containing ``scan_id`` and ``artifact_refs.finding_ids`` containing
  ``finding_id``. This is O(N) per call but N is the number of scan-
  sourced workstreams per tenant, which is small. A future PR can add a
  composite (scan_id, finding_id) index column if scale demands.
- ``source_ref_id`` on the Workstream is left NULL because scan job ids
  are workflow-generated strings, not UUIDs. The link travels via
  ``artifact_refs`` instead. The frontend resolves the deep-link.
- The audit trail is a single AuditService.log_decision call after
  successful creation; the audit_event id is then attached to the
  workstream via WorkstreamService.attach_audit_event_ref so the
  detail drawer's "View N audit events" link reaches it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.organization import Department
from app.models.workstream import Workstream, WorkstreamSourceType
from app.services.audit import AuditService
from app.services.execution_service import ExecutionService
from app.services.security.report_tiers import SecurityFinding
from app.services.workstream_service import StartParams, WorkstreamService

logger = get_logger(__name__)


class ScanNotFoundError(LookupError):
    """Raised when the scan_id cannot be resolved (or belongs to another tenant).

    Cross-tenant access is mapped to NotFound (not Forbidden) on purpose
    so the API surface does not leak which scan ids exist for other
    tenants.
    """


class FindingNotFoundError(LookupError):
    """Raised when the finding_id cannot be resolved within a scan."""


class ScanIncompleteError(ValueError):
    """Raised when the scan exists but is not yet COMPLETE."""


class NoActiveDepartmentError(ValueError):
    """Raised when the tenant has no active department to own the workstream."""


@dataclass(slots=True)
class RemediationResult:
    """Stable shape returned to the API layer + tests.

    ``idempotent`` is True when the call returned an existing Workstream
    (the second-or-later create-remediation invocation for the same
    scan_id + finding_id pair). The frontend uses this to pick toast
    copy ("Created" vs "Already tracked").
    """

    task_id: uuid.UUID | None
    workstream_id: uuid.UUID
    scan_id: str
    finding_id: str
    finding_title: str
    severity: str
    idempotent: bool


def resolve_finding(
    findings: list[SecurityFinding], finding_id: str,
) -> SecurityFinding | None:
    """Look up a finding by stable id, or by ``idx-N`` positional fallback.

    The ``SecurityFinding.id`` field defaults to empty in some scanner
    paths, so the frontend may pass an index-based id like ``"idx-3"``
    when the real id is missing. This resolver supports both forms.
    Returns None when no match.
    """
    if finding_id.startswith("idx-"):
        try:
            idx = int(finding_id[4:])
        except ValueError:
            return None
        if 0 <= idx < len(findings):
            return findings[idx]
        return None
    for f in findings:
        if f.id and f.id == finding_id:
            return f
    return None


async def find_existing_remediation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    scan_id: str,
    finding_id: str,
) -> Workstream | None:
    """Linear-scan SCAN-sourced workstreams for a matching (scan, finding) pair.

    Cheap because the SCAN-sourced subset stays small. A future
    optimization (composite column / functional index) is documented in
    the PR-SCAN-WS-01 report under "remaining debt".
    """
    stmt = select(Workstream).where(
        Workstream.tenant_id == tenant_id,
        Workstream.source_type == WorkstreamSourceType.SCAN,
        Workstream.archived_at.is_(None),
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    for ws in rows:
        refs = ws.artifact_refs or {}
        scan_ids = refs.get("scan_report_ids") or []
        finding_ids = refs.get("finding_ids") or []
        if scan_id in scan_ids and finding_id in finding_ids:
            return ws
    return None


async def resolve_department(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    requested_id: uuid.UUID | None,
) -> uuid.UUID:
    """Pick the workstream's owner department.

    Validates ``requested_id`` against the tenant when supplied;
    otherwise falls back to the tenant's first active department by
    sunflower index. Raises ``NoActiveDepartmentError`` when no active
    department exists -- the operator must seed before creating
    remediations.
    """
    if requested_id is not None:
        stmt = select(Department).where(
            Department.id == requested_id,
            Department.tenant_id == tenant_id,
            Department.is_active.is_(True),
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NoActiveDepartmentError(
                f"Requested department {requested_id} is not active for "
                f"tenant {tenant_id}",
            )
        return row.id

    stmt = (
        select(Department)
        .where(
            Department.tenant_id == tenant_id,
            Department.is_active.is_(True),
        )
        .order_by(Department.sunflower_index.asc())
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NoActiveDepartmentError(
            f"Tenant {tenant_id} has no active department; seed before "
            f"creating remediations",
        )
    return row.id


def build_task_description(
    finding: SecurityFinding, *, scan_id: str, finding_id: str,
) -> tuple[str, str]:
    """Derive (task_name, task_description) from the finding.

    The name is short ("Remediate: <title>") so the Tasks list stays
    scannable. The description carries severity, location, source scan
    id, finding id, the remediation guidance, and the suggested fix
    code when present. Operator reads this in TasksPage; the same text
    becomes the Workstream's ``next_step_text`` (truncated to 500).
    """
    name = f"Remediate: {finding.title}"[:200]
    parts: list[str] = []
    if finding.location:
        parts.append(f"Location: {finding.location}")
    parts.append(f"Severity: {finding.severity.value}")
    parts.append(f"Source scan: {scan_id}")
    parts.append(f"Finding id: {finding_id}")
    if finding.source_tool:
        parts.append(f"Detected by: {finding.source_tool}")
    if finding.cve_references:
        parts.append("CVE refs: " + ", ".join(finding.cve_references))
    if finding.remediation:
        parts.append("")
        parts.append("Remediation guidance:")
        parts.append(finding.remediation)
    if finding.fix_code:
        parts.append("")
        parts.append("Suggested fix code:")
        parts.append(finding.fix_code)
    description = "\n".join(parts)
    return name, description


async def create_remediation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    scan_id: str,
    finding_id: str,
    findings: list[SecurityFinding],
    department_id: uuid.UUID | None = None,
) -> RemediationResult:
    """Create a remediation Task + Workstream for a scan finding.

    Idempotent: a second invocation with the same (scan_id, finding_id)
    returns the existing Workstream without creating duplicates. The
    initial Task id is preserved across retries because we read it from
    the existing Workstream's ``artifact_refs.task_ids``.

    The caller (HTTP endpoint) is responsible for verifying that
    ``scan_id`` belongs to the calling tenant BEFORE invoking this
    function -- this module does not own scan ownership lookup because
    the scan store lives in ``ScanWorkflow`` (a singleton with its own
    in-memory state) which is not appropriate to import from a service
    layer that tests want to instantiate without a workflow.

    Raises:
        FindingNotFoundError: when ``finding_id`` does not resolve in
            the supplied findings list.
        NoActiveDepartmentError: when the tenant has no active
            department to own the workstream.
    """
    finding = resolve_finding(findings, finding_id)
    if finding is None:
        raise FindingNotFoundError(
            f"Finding {finding_id!r} not found in scan {scan_id!r}",
        )

    # 1. Idempotency: return the existing remediation Workstream if any.
    existing = await find_existing_remediation(
        db, tenant_id=tenant_id, scan_id=scan_id, finding_id=finding_id,
    )
    if existing is not None:
        task_ids = (existing.artifact_refs or {}).get("task_ids") or []
        existing_task_id = uuid.UUID(task_ids[0]) if task_ids else None
        return RemediationResult(
            task_id=existing_task_id,
            workstream_id=existing.id,
            scan_id=scan_id,
            finding_id=finding_id,
            finding_title=finding.title,
            severity=finding.severity.value,
            idempotent=True,
        )

    # 2. Resolve department (raises NoActiveDepartmentError when missing).
    dept_id = await resolve_department(
        db, tenant_id=tenant_id, requested_id=department_id,
    )

    # 3. Create the Task via the existing autopilot queue path. We do
    # NOT use also_create_workstream=True because we are about to create
    # our own Workstream with source_type=SCAN below; the auto-spawn
    # would mis-tag it as source_type=TASK.
    name, description = build_task_description(
        finding, scan_id=scan_id, finding_id=finding_id,
    )
    exec_svc = ExecutionService(db)
    task_dict = await exec_svc.create_task(
        name=name,
        description=description,
        user_id=user_id,
        tenant_id=tenant_id,
        also_create_workstream=False,
    )
    task_id = uuid.UUID(task_dict["id"])

    # 4. Create the Workstream shell with source_type=SCAN. The
    # next_step_text seeds the operator's first action; we truncate the
    # remediation guidance so it fits the column.
    next_step = (
        finding.remediation[:500] if finding.remediation
        else "Apply remediation guidance from the source scan finding"
    )
    ws_svc = WorkstreamService(db)
    ws = await ws_svc.start(
        StartParams(
            tenant_id=tenant_id,
            user_id=user_id,
            department_id=dept_id,
            goal=name,
            next_step_text=next_step,
            initial_context={
                "spawned_from": "scan_finding",
                "scan_id": scan_id,
                "finding_id": finding_id,
                "severity": finding.severity.value,
                "task_id": str(task_id),
            },
            source_type=WorkstreamSourceType.SCAN,
            # source_ref_id intentionally None: scan_id is a workflow-
            # generated string, not a UUID. The link travels via the
            # artifact_refs dict below.
            source_ref_id=None,
        ),
    )

    # 5. Wire the artifact reference graph. emit_event=False on the
    # scan/finding refs because they were already implied by source_type;
    # the task ref does emit so the operator sees it land on the timeline.
    await ws_svc.attach_artifact_ref(
        ws.id, tenant_id=tenant_id,
        kind="scan_report_ids", ref_id=scan_id, emit_event=False,
    )
    await ws_svc.attach_artifact_ref(
        ws.id, tenant_id=tenant_id,
        kind="finding_ids", ref_id=finding_id, emit_event=False,
    )
    await ws_svc.attach_artifact_ref(
        ws.id, tenant_id=tenant_id,
        kind="task_ids", ref_id=str(task_id), emit_event=True,
    )

    # 6. Audit trail. Use action_type "scan.remediation_workstream_created"
    # so the audit page can filter for spine-level remediation provenance.
    audit = AuditService(db)
    try:
        audit_event = await audit.log_decision(
            tenant_id=tenant_id,
            actor_id=user_id,
            actor_type="USER",
            action_type="scan.remediation_workstream_created",
            action_params={
                "scan_id": scan_id,
                "finding_id": finding_id,
                "finding_title": finding.title,
                "severity": finding.severity.value,
                "task_id": str(task_id),
                "workstream_id": str(ws.id),
            },
            result="ALLOWED",
            risk_level="LOW",
            governance_tier=1,
        )
        if audit_event and audit_event.get("id"):
            await ws_svc.attach_audit_event_ref(
                ws.id, tenant_id=tenant_id,
                audit_event_id=str(audit_event["id"]),
            )
    except Exception as exc:  # noqa: BLE001
        # Audit failure must NOT block remediation creation. The
        # workstream + task are the contract; audit is the observability
        # layer.
        logger.warning(
            "scan.remediation.audit_failed",
            scan_id=scan_id,
            finding_id=finding_id,
            error=str(exc),
        )

    logger.info(
        "scan.remediation.created",
        tenant_id=str(tenant_id),
        scan_id=scan_id,
        finding_id=finding_id,
        task_id=str(task_id),
        workstream_id=str(ws.id),
        severity=finding.severity.value,
    )

    return RemediationResult(
        task_id=task_id,
        workstream_id=ws.id,
        scan_id=scan_id,
        finding_id=finding_id,
        finding_title=finding.title,
        severity=finding.severity.value,
        idempotent=False,
    )


def serialize_result(result: RemediationResult) -> dict[str, Any]:
    """Stable JSON shape consumed by the frontend ``CreateRemediationButton``."""
    return {
        "task_id": str(result.task_id) if result.task_id else None,
        "workstream_id": str(result.workstream_id),
        "scan_id": result.scan_id,
        "finding_id": result.finding_id,
        "finding_title": result.finding_title,
        "severity": result.severity,
        "idempotent": result.idempotent,
    }
