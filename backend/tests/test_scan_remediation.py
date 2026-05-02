"""PR-SCAN-WS-01 contract tests for scan finding -> remediation wiring.

Pinned behavior:

* ``create_remediation`` creates one Task and one Workstream linked to
  the source scan via ``source_type=SCAN`` + ``artifact_refs.scan_report_ids``
  + ``artifact_refs.finding_ids`` + ``artifact_refs.task_ids``.
* The Workstream's audit_event_refs grows by exactly one entry on
  successful creation (audit failure must not block creation).
* Idempotency: calling create_remediation twice with the same
  (scan_id, finding_id) returns the existing Workstream (and existing
  Task id) with ``idempotent=True`` -- no duplicate rows.
* Finding resolution supports both stable ``finding.id`` and the
  positional ``"idx-N"`` fallback used when id is empty.
* Tenant isolation: a Workstream that exists for tenant A under the
  same (scan_id, finding_id) pair does NOT short-circuit a real
  creation for tenant B.
* Missing-finding raises ``FindingNotFoundError``; tenant with zero
  active departments raises ``NoActiveDepartmentError``.
* ``build_task_description`` carries severity + location + remediation
  + fix_code into the Task body so the operator gets actionable text in
  the Tasks queue without needing to follow back to the scan report.

Mirrors the existing ``test_workstream_spine_skeleton.py`` fixture
style: ``db_session`` + ``_seed`` helper. No external services. No
sleeps.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Tenant, User
from app.models.organization import Department
from app.models.workstream import WorkstreamSourceType
from app.services.security.report_tiers import FindingSeverity, SecurityFinding
from app.services.security.scan_remediation import (
    FindingNotFoundError,
    NoActiveDepartmentError,
    build_task_description,
    create_remediation,
    find_existing_remediation,
    resolve_finding,
    serialize_result,
)
from app.services.workstream_service import WorkstreamService


# ── Helpers ───────────────────────────────────────────────────────────


async def _seed(
    db: AsyncSession, *, slug: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed tenant + user + dept; return (tenant_id, user_id, dept_id)."""
    s = slug or uuid.uuid4().hex[:8]
    t = Tenant(id=uuid.uuid4(), name=f"scanws-tenant-{s}", slug=f"scanws-{s}")
    db.add(t)
    await db.flush()
    u = User(
        id=uuid.uuid4(),
        tenant_id=t.id,
        email=f"scanws-{s}@example.com",
        password_hash="x",
        role="FOUNDER",
    )
    db.add(u)
    await db.flush()
    d = Department(
        id=uuid.uuid4(),
        tenant_id=t.id,
        name=f"Engineering ({s})",
        description="scanws-test",
        sunflower_index=0,
        cell_id=f"hex_0_{s}",
        config={},
        is_active=True,
    )
    db.add(d)
    await db.flush()
    await db.commit()
    return t.id, u.id, d.id


def _sample_findings() -> list[SecurityFinding]:
    """Three findings spanning stable-id, empty-id, and high severity."""
    return [
        SecurityFinding(
            id="finding-stable-1",
            title="SQL injection in /login",
            severity=FindingSeverity.CRITICAL,
            location="app/routes/auth.py:42",
            description="Username concatenated into raw SQL.",
            explanation="Authenticated bypass risk.",
            remediation="Use parameterized queries via SQLAlchemy text() bindparams.",
            fix_code="db.execute(text('SELECT * FROM users WHERE name = :n'), {'n': name})",
            source_tool="bandit",
            cve_references=["CWE-89"],
        ),
        SecurityFinding(
            id="",  # empty id -- exercises the idx-N fallback
            title="Hard-coded API key",
            severity=FindingSeverity.HIGH,
            location="config/secrets.py:8",
            description="OpenAI key embedded in source.",
            remediation="Move to environment variable read at startup.",
            source_tool="gitleaks",
        ),
        SecurityFinding(
            id="finding-stable-3",
            title="Verbose 500 stacktrace exposed",
            severity=FindingSeverity.LOW,
            location="app/main.py:104",
            description="Default debug=True leaks internals.",
            remediation="Set debug=False in production config.",
        ),
    ]


# ── resolve_finding ───────────────────────────────────────────────────


def test_resolve_finding_by_stable_id() -> None:
    """resolve_finding finds by SecurityFinding.id when populated."""
    findings = _sample_findings()
    out = resolve_finding(findings, "finding-stable-1")
    assert out is not None
    assert out.title.startswith("SQL injection")


def test_resolve_finding_by_idx_when_id_empty() -> None:
    """The positional fallback ``idx-N`` covers findings with empty id."""
    findings = _sample_findings()
    out = resolve_finding(findings, "idx-1")
    assert out is not None
    assert out.title == "Hard-coded API key"


def test_resolve_finding_returns_none_for_unknown() -> None:
    """Unknown id (not stable, not idx-N) returns None."""
    findings = _sample_findings()
    assert resolve_finding(findings, "definitely-not-a-finding") is None
    assert resolve_finding(findings, "idx-99") is None
    assert resolve_finding(findings, "idx-not-a-number") is None


# ── build_task_description ────────────────────────────────────────────


def test_build_task_description_includes_severity_and_remediation() -> None:
    """Task body must carry severity, location, scan id, finding id, and
    the remediation guidance so the operator can act from the Tasks
    queue without round-tripping to the scan report.
    """
    findings = _sample_findings()
    finding = findings[0]
    name, desc = build_task_description(
        finding, scan_id="scan-1", finding_id=finding.id,
    )
    assert name.startswith("Remediate:")
    assert "SQL injection" in name
    assert "CRITICAL" in desc
    assert "app/routes/auth.py:42" in desc
    assert "scan-1" in desc
    assert finding.id in desc
    assert "parameterized queries" in desc
    assert "bindparams" in desc


def test_build_task_description_handles_minimal_finding() -> None:
    """A finding with only title + severity still produces a non-empty body."""
    finding = SecurityFinding(
        id="x", title="bare finding", severity=FindingSeverity.INFO,
    )
    name, desc = build_task_description(
        finding, scan_id="scan-1", finding_id="x",
    )
    assert name == "Remediate: bare finding"
    # Severity + scan id + finding id always rendered.
    assert "INFO" in desc
    assert "scan-1" in desc
    assert "x" in desc


# ── create_remediation: happy path ────────────────────────────────────


@pytest.mark.asyncio
async def test_create_remediation_creates_task_and_workstream(
    db_session: AsyncSession,
) -> None:
    """End-to-end: one finding -> one task + one workstream, both linked."""
    tid, uid, did = await _seed(db_session)
    findings = _sample_findings()
    result = await create_remediation(
        db_session,
        tenant_id=tid,
        user_id=uid,
        scan_id="scan-abc",
        finding_id="finding-stable-1",
        findings=findings,
        department_id=did,
    )
    assert result.workstream_id is not None
    assert result.task_id is not None
    assert result.finding_title.startswith("SQL injection")
    assert result.severity == "CRITICAL"
    assert result.idempotent is False


@pytest.mark.asyncio
async def test_create_remediation_uses_scan_source_type(
    db_session: AsyncSession,
) -> None:
    """The created Workstream must carry source_type=SCAN.

    PR-5 contract: source_ref_id is None because scan_id is a workflow-
    generated string, not a UUID. The link travels via artifact_refs.
    """
    tid, uid, did = await _seed(db_session)
    findings = _sample_findings()
    result = await create_remediation(
        db_session,
        tenant_id=tid,
        user_id=uid,
        scan_id="scan-abc",
        finding_id="finding-stable-1",
        findings=findings,
        department_id=did,
    )
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(result.workstream_id, tenant_id=tid)
    assert ws.source_type == WorkstreamSourceType.SCAN
    assert ws.source_ref_id is None


@pytest.mark.asyncio
async def test_create_remediation_links_artifact_refs(
    db_session: AsyncSession,
) -> None:
    """artifact_refs must carry scan_report_ids + finding_ids + task_ids."""
    tid, uid, did = await _seed(db_session)
    findings = _sample_findings()
    result = await create_remediation(
        db_session,
        tenant_id=tid,
        user_id=uid,
        scan_id="scan-xyz",
        finding_id="finding-stable-1",
        findings=findings,
        department_id=did,
    )
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(result.workstream_id, tenant_id=tid)
    refs = ws.artifact_refs or {}
    assert refs.get("scan_report_ids") == ["scan-xyz"]
    assert refs.get("finding_ids") == ["finding-stable-1"]
    assert refs.get("task_ids") == [str(result.task_id)]


@pytest.mark.asyncio
async def test_create_remediation_attaches_audit_event_ref(
    db_session: AsyncSession,
) -> None:
    """audit_event_refs must grow by exactly one entry on creation."""
    tid, uid, did = await _seed(db_session)
    findings = _sample_findings()
    result = await create_remediation(
        db_session,
        tenant_id=tid,
        user_id=uid,
        scan_id="scan-aud",
        finding_id="finding-stable-1",
        findings=findings,
        department_id=did,
    )
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(result.workstream_id, tenant_id=tid)
    # Hash-chained AuditService writes the row + returns id; we attached it.
    assert len(ws.audit_event_refs or []) == 1


@pytest.mark.asyncio
async def test_create_remediation_resolves_by_idx_when_id_empty(
    db_session: AsyncSession,
) -> None:
    """The empty-id finding (index 1 in _sample_findings) is reachable via
    the idx-N fallback. Result records that finding's title + severity.
    """
    tid, uid, did = await _seed(db_session)
    findings = _sample_findings()
    result = await create_remediation(
        db_session,
        tenant_id=tid,
        user_id=uid,
        scan_id="scan-idx",
        finding_id="idx-1",
        findings=findings,
        department_id=did,
    )
    assert result.finding_title == "Hard-coded API key"
    assert result.severity == "HIGH"
    assert result.finding_id == "idx-1"


# ── Idempotency ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_remediation_is_idempotent(
    db_session: AsyncSession,
) -> None:
    """Second call with the same (scan_id, finding_id) returns the existing
    Workstream and Task -- no duplicates created.
    """
    tid, uid, did = await _seed(db_session)
    findings = _sample_findings()
    first = await create_remediation(
        db_session,
        tenant_id=tid, user_id=uid,
        scan_id="scan-dup", finding_id="finding-stable-1",
        findings=findings, department_id=did,
    )
    second = await create_remediation(
        db_session,
        tenant_id=tid, user_id=uid,
        scan_id="scan-dup", finding_id="finding-stable-1",
        findings=findings, department_id=did,
    )
    assert second.workstream_id == first.workstream_id
    assert second.task_id == first.task_id
    assert second.idempotent is True
    assert first.idempotent is False


@pytest.mark.asyncio
async def test_find_existing_remediation_misses_other_finding(
    db_session: AsyncSession,
) -> None:
    """find_existing_remediation must not match a different finding id
    even when the scan_id is the same. Otherwise creating remediation
    for a second finding from the same scan would silently dedupe.
    """
    tid, uid, did = await _seed(db_session)
    findings = _sample_findings()
    await create_remediation(
        db_session,
        tenant_id=tid, user_id=uid,
        scan_id="scan-multi", finding_id="finding-stable-1",
        findings=findings, department_id=did,
    )
    # Different finding id from same scan -- should not match.
    miss = await find_existing_remediation(
        db_session, tenant_id=tid,
        scan_id="scan-multi", finding_id="finding-stable-3",
    )
    assert miss is None


# ── Tenant isolation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_remediation_tenant_isolation(
    db_session: AsyncSession,
) -> None:
    """A Workstream existing for tenant A under (scan_id, finding_id)
    does NOT short-circuit creation for tenant B with the same pair.
    """
    tid_a, uid_a, did_a = await _seed(db_session, slug="tA")
    tid_b, uid_b, did_b = await _seed(db_session, slug="tB")
    findings = _sample_findings()
    a = await create_remediation(
        db_session,
        tenant_id=tid_a, user_id=uid_a,
        scan_id="scan-shared", finding_id="finding-stable-1",
        findings=findings, department_id=did_a,
    )
    b = await create_remediation(
        db_session,
        tenant_id=tid_b, user_id=uid_b,
        scan_id="scan-shared", finding_id="finding-stable-1",
        findings=findings, department_id=did_b,
    )
    # Two distinct workstreams.
    assert a.workstream_id != b.workstream_id
    assert b.idempotent is False


# ── Error paths ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_remediation_unknown_finding_raises(
    db_session: AsyncSession,
) -> None:
    """Unknown finding id raises FindingNotFoundError (HTTP layer maps to 404)."""
    tid, uid, did = await _seed(db_session)
    findings = _sample_findings()
    with pytest.raises(FindingNotFoundError):
        await create_remediation(
            db_session,
            tenant_id=tid, user_id=uid,
            scan_id="scan-1", finding_id="not-a-finding",
            findings=findings, department_id=did,
        )


@pytest.mark.asyncio
async def test_create_remediation_no_active_dept_raises(
    db_session: AsyncSession,
) -> None:
    """Tenant with no active departments triggers NoActiveDepartmentError
    (HTTP layer maps to 422). Seed a tenant + user but NO department.
    """
    s = uuid.uuid4().hex[:8]
    t = Tenant(id=uuid.uuid4(), name=f"empty-{s}", slug=f"empty-{s}")
    db_session.add(t)
    await db_session.flush()
    u = User(
        id=uuid.uuid4(),
        tenant_id=t.id,
        email=f"empty-{s}@example.com",
        password_hash="x",
        role="FOUNDER",
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.commit()
    findings = _sample_findings()
    with pytest.raises(NoActiveDepartmentError):
        await create_remediation(
            db_session,
            tenant_id=t.id, user_id=u.id,
            scan_id="scan-1", finding_id="finding-stable-1",
            findings=findings,
            department_id=None,  # forces the fallback path
        )


@pytest.mark.asyncio
async def test_create_remediation_invalid_dept_id_raises(
    db_session: AsyncSession,
) -> None:
    """An explicit department_id that does not belong to the tenant is
    rejected (NoActiveDepartmentError -> HTTP 422), not silently
    fallback-replaced. This prevents cross-tenant department leakage.
    """
    tid_a, uid_a, _ = await _seed(db_session, slug="invA")
    _, _, did_b = await _seed(db_session, slug="invB")  # B's dept id
    findings = _sample_findings()
    with pytest.raises(NoActiveDepartmentError):
        await create_remediation(
            db_session,
            tenant_id=tid_a, user_id=uid_a,
            scan_id="scan-1", finding_id="finding-stable-1",
            findings=findings,
            department_id=did_b,  # belongs to a different tenant
        )


# ── Serialization ─────────────────────────────────────────────────────


def test_serialize_result_shape() -> None:
    """The serialized dict must match the documented frontend contract."""
    from app.services.security.scan_remediation import RemediationResult
    out = serialize_result(
        RemediationResult(
            task_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            workstream_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            scan_id="scan-1",
            finding_id="finding-1",
            finding_title="t",
            severity="HIGH",
            idempotent=True,
        ),
    )
    assert out["task_id"] == "11111111-1111-1111-1111-111111111111"
    assert out["workstream_id"] == "22222222-2222-2222-2222-222222222222"
    assert out["scan_id"] == "scan-1"
    assert out["finding_id"] == "finding-1"
    assert out["finding_title"] == "t"
    assert out["severity"] == "HIGH"
    assert out["idempotent"] is True


def test_serialize_result_handles_null_task_id() -> None:
    """task_id may be None when an idempotent hit found a workstream
    whose artifact_refs.task_ids list was empty (legacy data).
    """
    from app.services.security.scan_remediation import RemediationResult
    out = serialize_result(
        RemediationResult(
            task_id=None,
            workstream_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            scan_id="scan-1",
            finding_id="finding-1",
            finding_title="t",
            severity="HIGH",
            idempotent=True,
        ),
    )
    assert out["task_id"] is None
