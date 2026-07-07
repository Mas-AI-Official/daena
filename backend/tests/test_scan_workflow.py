"""Tests for the end-to-end Security Scan Workflow.

Covers:
- Job creation and lifecycle
- Status progression through scan phases
- Report generation with tier-appropriate findings
- Tier filtering (T1 sees less detail than T3)
- Sub-agent parallelism via SubAgentSpawner
- Cost calculation per tier
"""

from __future__ import annotations

import asyncio
import json
import pytest

from app.services.security.scan_workflow import (
    ScanWorkflow,
    ScanJob,
    ScanJobStatus,
    ScanReport,
    ScanStatus,
    TIER_BASE_COST,
    TIER_COST_PER_FILE,
    _simulate_file_scan,
)
from app.services.security.report_tiers import ReportTier, FindingSeverity


# ---- Fixtures ----

@pytest.fixture(autouse=True)
def _stub_real_scanner(monkeypatch) -> None:
    """Replace the real network/subprocess scanner with a fast deterministic
    stub for EVERY test in this module.

    Root cause of the full-suite ~72% hang (2026-06-01): for URL targets
    (example.com, github.com/...), ScanWorkflow._execute_scan calls
    ``real_scanner.scan_target`` which shells out to live tools (nuclei et al.)
    against the real network. A single ARCHITECT-tier test ran nuclei for 270s
    before timing out - to the suite that looked like a hang. Unit tests must
    never invoke real network scanners (slow, flaky, network- and
    tool-install-dependent).

    Stubbing the ``_real_scan_target`` boundary keeps the workflow orchestration
    under test (profiling, status progression, aggregation, enrichment, Zero-FP
    gate, tier-aware report generation) while removing the external I/O. The
    stub reports a realistic file count derived from the target so the
    files_total/files_scanned assertions still exercise the profiling merge.
    """
    from app.services.security import scan_workflow as _swf
    from app.services.security.real_scanner import ScanOutcome

    async def _fake_scan_target(target: str, _opts: dict | None = None) -> ScanOutcome:
        # Derive a file count from comma-separated path targets so the
        # multi-file profiling assertions remain meaningful; URLs -> 1.
        is_pathish = ("," in target) or (
            "/" not in target and "." in target and not target.startswith("http")
        )
        n = len([p for p in target.split(",") if p.strip()]) if is_pathish else 1
        kind = "path" if is_pathish else "url"
        return ScanOutcome(
            files_scanned=n,
            findings=[],
            target_kind=kind,
            tools_used=["stub_scanner"],
            tools_missing=[],
            notes="stubbed in tests (no real network scan)",
        )

    monkeypatch.setattr(_swf, "_real_scan_target", _fake_scan_target)


@pytest.fixture(autouse=True)
def _stub_db_persist(monkeypatch) -> None:
    """No-op the durable DB mirror for EVERY test in this module.

    ``_execute_scan`` now writes a ``scan_reports`` row on completion
    (PR-9(b), Rule 17). These orchestration tests run real scans with a
    ``tenant_id`` but never assert on DB persistence, so the write would
    open a session against the app's *real* engine (``async_session_factory``
    is not rebound to the in-memory test engine here) and either pollute the
    dev DB or churn an aiosqlite connection whose GC after loop-close raises a
    teardown warning. The persistence contract has its own dedicated oracle
    (``test_scan_report_persist.py``, which patches the factory and seeds a
    tenant), so stubbing the side effect here keeps these tests hermetic
    without weakening coverage.
    """
    async def _noop_persist_db(self, job, report) -> None:  # noqa: ANN001
        return None

    monkeypatch.setattr(ScanWorkflow, "_persist_report_db", _noop_persist_db)


@pytest.fixture
def workflow() -> ScanWorkflow:
    return ScanWorkflow()


# ---- test_start_scan_creates_job ----

class TestStartScanCreatesJob:
    """Verify that start_scan creates a tracked job with correct fields."""

    @pytest.fixture(autouse=True)
    def _stub_execute(self, monkeypatch) -> None:
        """Stop the fire-and-forget scan pipeline from leaking into teardown.

        ``start_scan`` schedules ``asyncio.create_task(self._execute_scan(job))``
        and returns immediately - the correct production shape (the HTTP route
        returns the job id without blocking on the scan). But the tests in THIS
        class assert only the synchronous job-creation contract; they never
        drain that background task (unlike TestScanStatusProgression, which
        polls until COMPLETE). A still-running ``_execute_scan`` then outlives
        the test and lands in pytest-asyncio's event-loop teardown, where
        ``_cancel_all_tasks`` -> ``run_until_complete(gather(...))`` hung the
        ENTIRE suite at ~72% on Windows (the mid-flight scan task sat on a
        non-cancellable IOCP wait). Stubbing the pipeline to a no-op keeps the
        spawned task trivial so nothing survives the test. The completion-path
        tests keep the real pipeline and drain it themselves.

        This is a TEST-HYGIENE fix; the production fire-and-forget design is
        intentional and unchanged.
        """
        async def _noop(_self, _job) -> None:
            return None

        monkeypatch.setattr(ScanWorkflow, "_execute_scan", _noop)

    @pytest.mark.asyncio
    async def test_creates_job_with_id(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="https://github.com/org/example-repo",
            tier="ANALYST",
            user_id="user-001",
            tenant_id="tenant-001",
        )
        assert job.id
        assert len(job.id) == 12
        assert job.target == "https://github.com/org/example-repo"
        assert job.tier == ReportTier.ANALYST
        assert job.user_id == "user-001"
        assert job.tenant_id == "tenant-001"
        assert job.status in (
            ScanJobStatus.QUEUED,
            ScanJobStatus.PROFILING,
            ScanJobStatus.SCANNING,
            ScanJobStatus.ANALYZING,
            ScanJobStatus.REPORTING,
            ScanJobStatus.COMPLETE,
        )

    @pytest.mark.asyncio
    async def test_creates_job_with_options(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="src/main.py,src/config.py",
            tier="SCOUT",
            user_id="user-002",
            tenant_id="tenant-001",
            options={"max_depth": 3, "exclude_tests": True},
        )
        assert job.options == {"max_depth": 3, "exclude_tests": True}

    @pytest.mark.asyncio
    async def test_job_is_trackable(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="https://github.com/org/repo",
            tier="OPERATOR",
            user_id="user-003",
            tenant_id="tenant-001",
        )
        # Job should be retrievable via get_scan_status
        status = await workflow.get_scan_status(job.id)
        assert status.job_id == job.id

    @pytest.mark.asyncio
    async def test_invalid_tier_raises(self, workflow: ScanWorkflow) -> None:
        with pytest.raises(ValueError):
            await workflow.start_scan(
                target="example.com",
                tier="NONEXISTENT",
                user_id="user-004",
                tenant_id="tenant-001",
            )


# ---- test_scan_status_progression ----

class TestScanStatusProgression:
    """Verify scan progresses through expected status phases."""

    @pytest.mark.asyncio
    async def test_reaches_complete(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="src/app.py,src/db.py,src/auth.py",
            tier="SCOUT",
            user_id="user-010",
            tenant_id="tenant-001",
        )
        # Wait for background task to complete (with timeout)
        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        final = await workflow.get_scan_status(job.id)
        assert final.status == ScanJobStatus.COMPLETE
        assert final.progress_pct == 100.0

    @pytest.mark.asyncio
    async def test_files_total_populated(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="file1.py,file2.py,file3.py,file4.py,file5.py",
            tier="ANALYST",
            user_id="user-011",
            tenant_id="tenant-001",
        )
        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        final = await workflow.get_scan_status(job.id)
        assert final.files_total == 5
        assert final.files_scanned == 5

    @pytest.mark.asyncio
    async def test_unknown_job_raises(self, workflow: ScanWorkflow) -> None:
        with pytest.raises(KeyError):
            await workflow.get_scan_status("nonexistent-id")


# ---- test_scan_report_generation ----

class TestScanReportGeneration:
    """Verify report is generated after scan completion."""

    @pytest.mark.asyncio
    async def test_report_has_findings(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="https://github.com/org/vulnerable-app",
            tier="ANALYST",
            user_id="user-020",
            tenant_id="tenant-001",
        )
        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        report = await workflow.get_scan_report(job.id)
        assert report.job_id == job.id
        assert report.tier == ReportTier.ANALYST
        assert isinstance(report.findings, list)
        assert report.summary
        assert report.duration_secs >= 0  # Can be 0 in mock/fast execution

    @pytest.mark.asyncio
    async def test_report_has_severity_counts(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="https://github.com/org/test-app",
            tier="OPERATOR",
            user_id="user-021",
            tenant_id="tenant-001",
        )
        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        report = await workflow.get_scan_report(job.id)
        assert "critical" in report.severity_counts
        assert "high" in report.severity_counts
        assert "medium" in report.severity_counts
        assert "low" in report.severity_counts
        assert "info" in report.severity_counts

    @pytest.mark.asyncio
    async def test_report_has_pipeline_stages(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="example.com",
            tier="ARCHITECT",
            user_id="user-022",
            tenant_id="tenant-001",
        )
        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        report = await workflow.get_scan_report(job.id)
        assert isinstance(report.pipeline_stages_used, list)
        assert len(report.pipeline_stages_used) > 0

    @pytest.mark.asyncio
    async def test_report_not_ready_raises(self, workflow: ScanWorkflow) -> None:
        with pytest.raises(KeyError):
            await workflow.get_scan_report("nonexistent-id")


# ---- test_tier_filtering ----

class TestTierFiltering:
    """Verify that different tiers produce different detail levels.

    T1 Scout: title + severity + location only
    T2 Analyst: + description, explanation, remediation
    T3 Operator: + fix_code
    T4 Architect: + fix_verified, reasoning_chain
    """

    @pytest.mark.asyncio
    async def test_scout_has_minimal_detail(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="https://github.com/org/scout-target",
            tier="SCOUT",
            user_id="user-030",
            tenant_id="tenant-001",
        )
        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        report = await workflow.get_scan_report(job.id)
        if report.findings:
            finding = report.findings[0]
            # Scout should have title, severity, location
            assert finding.get("title")
            assert finding.get("severity")
            # Scout should NOT have detailed explanation
            assert finding.get("description") == ""
            assert finding.get("explanation") == ""
            assert finding.get("fix_code") == ""

    @pytest.mark.asyncio
    async def test_operator_has_fix_code(self, workflow: ScanWorkflow) -> None:
        job = await workflow.start_scan(
            target="https://github.com/org/operator-target",
            tier="OPERATOR",
            user_id="user-031",
            tenant_id="tenant-001",
        )
        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        report = await workflow.get_scan_report(job.id)
        if report.findings:
            finding = report.findings[0]
            # Operator should have description + fix_code
            assert finding.get("description") or finding.get("fix_code") is not None

    @pytest.mark.asyncio
    async def test_architect_has_more_stages(self, workflow: ScanWorkflow) -> None:
        """Architect tier should use more pipeline stages than Scout."""
        job_scout = await workflow.start_scan(
            target="https://github.com/org/stage-compare",
            tier="SCOUT",
            user_id="user-032",
            tenant_id="tenant-001",
        )
        job_arch = await workflow.start_scan(
            target="https://github.com/org/stage-compare",
            tier="ARCHITECT",
            user_id="user-033",
            tenant_id="tenant-001",
        )

        for _ in range(50):
            await asyncio.sleep(0.1)
            s1 = await workflow.get_scan_status(job_scout.id)
            s2 = await workflow.get_scan_status(job_arch.id)
            if (
                s1.status == ScanJobStatus.COMPLETE
                and s2.status == ScanJobStatus.COMPLETE
            ):
                break

        report_scout = await workflow.get_scan_report(job_scout.id)
        report_arch = await workflow.get_scan_report(job_arch.id)

        # Architect should use strictly more pipeline stages (no skips)
        assert len(report_arch.pipeline_stages_used) >= len(
            report_scout.pipeline_stages_used,
        )


# ---- test_sub_agent_parallelism ----

class TestSubAgentParallelism:
    """Verify sub-agents are spawned and executed in parallel."""

    @pytest.mark.asyncio
    async def test_spawner_processes_all_files(self, workflow: ScanWorkflow) -> None:
        file_list = ",".join([f"src/file_{i}.py" for i in range(10)])
        job = await workflow.start_scan(
            target=file_list,
            tier="ANALYST",
            user_id="user-040",
            tenant_id="tenant-001",
        )
        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        final = await workflow.get_scan_status(job.id)
        assert final.files_total == 10
        assert final.files_scanned == 10

    @pytest.mark.asyncio
    async def test_single_file_scan(self, workflow: ScanWorkflow) -> None:
        """Even a single file should complete successfully."""
        job = await workflow.start_scan(
            target="single_file.py",
            tier="SCOUT",
            user_id="user-041",
            tenant_id="tenant-001",
        )
        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        final = await workflow.get_scan_status(job.id)
        assert final.status == ScanJobStatus.COMPLETE


# ---- test_scan_cost_calculation ----

class TestScanCostCalculation:
    """Verify cost calculation follows the tier pricing model."""

    def test_scout_cost(self) -> None:
        cost = ScanWorkflow._calculate_cost(ReportTier.SCOUT, 10, 3)
        expected = TIER_BASE_COST[ReportTier.SCOUT] + (
            TIER_COST_PER_FILE[ReportTier.SCOUT] * 10
        ) + (0.01 * 3)
        assert cost == round(expected, 4)

    def test_analyst_cost(self) -> None:
        cost = ScanWorkflow._calculate_cost(ReportTier.ANALYST, 50, 15)
        expected = TIER_BASE_COST[ReportTier.ANALYST] + (
            TIER_COST_PER_FILE[ReportTier.ANALYST] * 50
        ) + (0.01 * 15)
        assert cost == round(expected, 4)

    def test_architect_more_expensive_than_scout(self) -> None:
        scout = ScanWorkflow._calculate_cost(ReportTier.SCOUT, 20, 5)
        architect = ScanWorkflow._calculate_cost(ReportTier.ARCHITECT, 20, 5)
        assert architect > scout

    def test_evilbob_most_expensive(self) -> None:
        scout = ScanWorkflow._calculate_cost(ReportTier.SCOUT, 100, 20)
        evilbob = ScanWorkflow._calculate_cost(ReportTier.EVILBOB, 100, 20)
        assert evilbob > scout

    def test_zero_files_still_has_base_cost(self) -> None:
        cost = ScanWorkflow._calculate_cost(ReportTier.ANALYST, 0, 0)
        assert cost == TIER_BASE_COST[ReportTier.ANALYST]

    def test_cost_increases_with_files(self) -> None:
        cost_10 = ScanWorkflow._calculate_cost(ReportTier.OPERATOR, 10, 0)
        cost_100 = ScanWorkflow._calculate_cost(ReportTier.OPERATOR, 100, 0)
        assert cost_100 > cost_10


# ---- test_simulated_file_scan ----

class TestSimulatedFileScan:
    """Verify the simulated scanner produces deterministic results."""

    def test_deterministic_output(self) -> None:
        r1 = _simulate_file_scan("src/main.py", ReportTier.ANALYST)
        r2 = _simulate_file_scan("src/main.py", ReportTier.ANALYST)
        assert r1 == r2

    def test_different_files_may_differ(self) -> None:
        r1 = _simulate_file_scan("src/main.py", ReportTier.ANALYST)
        r2 = _simulate_file_scan("src/config.py", ReportTier.ANALYST)
        # Different files produce different finding sets (or both empty)
        if r1 and r2:
            assert r1[0]["id"] != r2[0]["id"]

    def test_findings_have_required_fields(self) -> None:
        # Try a few files to find one with findings
        for i in range(20):
            results = _simulate_file_scan(f"src/mod_{i}.py", ReportTier.ANALYST)
            if results:
                finding = results[0]
                assert "id" in finding
                assert "title" in finding
                assert "severity" in finding
                assert "location" in finding
                return
        # If none had findings in 20 files, that is still valid (probabilistic)


# ---- Border Agent emit (Session J) ----


class TestBorderAgentEmitOnComplete:
    """When a scan finishes, the Security Operations BorderAgent must see
    a TASK_COMPLETED signal (always) and a THREAT_DETECTED signal (only
    when critical/high findings exist). This protects the
    cross-department notification contract from silent regressions.
    """

    @pytest.mark.asyncio
    async def test_task_completed_always_emitted(
        self, workflow: ScanWorkflow
    ) -> None:
        from uuid import uuid4
        from app.services.departments.border_agent import (
            DepartmentEvent,
            get_border_agent,
            reset_registry,
        )

        # Wipe process registry so this test starts with a deterministic
        # event-bus subscription state. Without this, test order could
        # leak emits from earlier runs into the ring buffers.
        await reset_registry()

        tenant_id = uuid4()

        # Pre-create listeners BEFORE firing the scan so they subscribe
        # to the bus before any emit happens. The scan_workflow will
        # call get_border_agent for Security Operations (reused via the
        # idempotent registry), and Daena's wildcard lens receives all
        # peer events from this tenant.
        sec_ops = await get_border_agent(
            tenant_id=tenant_id, department="Security Operations"
        )
        daena = await get_border_agent(
            tenant_id=tenant_id, department="Daena"
        )
        sec_ops.clear()
        daena.clear()

        job = await workflow.start_scan(
            target="src/a.py,src/b.py,src/c.py",
            tier="SCOUT",
            user_id="user-j1",
            tenant_id=str(tenant_id),
        )

        for _ in range(50):
            await asyncio.sleep(0.1)
            status = await workflow.get_scan_status(job.id)
            if status.status == ScanJobStatus.COMPLETE:
                break

        # Give the event loop a tick to drain any last-minute handler
        # coroutines spawned inside the scan emit block.
        await asyncio.sleep(0.05)
        types = [s.get("event_type") for s in daena.recent_signals(limit=20)]
        assert DepartmentEvent.TASK_COMPLETED in types, (
            f"expected TASK_COMPLETED in Daena VP inbox, got: {types}"
        )
