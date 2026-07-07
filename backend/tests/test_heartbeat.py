"""Tests for heartbeat daemon, checks, config, and cron scheduler."""

from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime, time
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.heartbeat.heartbeat_checks import (
    ActionPriority,
    HeartbeatCheckResult,
    check_file,
    check_git_status,
    check_github_issues,
    check_runtime_health,
    generate_daily_report,
)
from app.services.heartbeat.heartbeat_config import (
    AutopilotLevel,
    CheckType,
    HeartbeatCheck,
    HeartbeatConfig,
    HeartbeatState,
)
from app.services.heartbeat.heartbeat_daemon import HeartbeatDaemon
from app.services.heartbeat.cron_scheduler import (
    CronFrequency,
    CronJob,
    CronScheduler,
    get_cron_scheduler,
    reset_cron_scheduler_singleton,
)


# ── Config tests ──

class TestHeartbeatConfig:
    def test_default_config(self):
        cfg = HeartbeatConfig.default()
        assert cfg.interval_minutes == 30
        assert cfg.autopilot_level == AutopilotLevel.ON
        assert cfg.state == HeartbeatState.STOPPED
        assert len(cfg.checks) >= 5

    def test_to_dict(self):
        cfg = HeartbeatConfig.default()
        d = cfg.to_dict()
        assert d["interval_minutes"] == 30
        assert d["autopilot_level"] == "on"
        assert d["state"] == "stopped"
        assert isinstance(d["checks"], list)

    def test_active_hours_normal(self):
        cfg = HeartbeatConfig(active_start=time(7, 0), active_end=time(23, 0))
        # This test just verifies the method doesn't crash
        result = cfg.is_within_active_hours()
        assert isinstance(result, bool)

    def test_cost_guards(self):
        cfg = HeartbeatConfig.default()
        assert cfg.max_cost_per_cycle_usd == 0.10
        assert cfg.max_cost_per_day_usd == 2.00

    def test_reflection_questions(self):
        cfg = HeartbeatConfig.default()
        assert len(cfg.reflection_questions) == 3
        assert "ROI" in cfg.reflection_questions[1]


# ── Check tests ──

class TestHeartbeatChecks:
    @pytest.mark.asyncio
    async def test_check_runtime_health(self):
        result = await check_runtime_health()
        assert isinstance(result, HeartbeatCheckResult)
        assert result.check_type == "runtime_health"
        assert result.status in ("ok", "warning", "error")

    @pytest.mark.asyncio
    async def test_check_file_nonexistent(self):
        result = await check_file("/nonexistent/path/foo.md", "test")
        assert result.status == "warning"
        assert "not found" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_check_file_existing(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("- [ ] Task 1\n- [x] Task 2\n- [ ] Task 3\n")
        result = await check_file(str(f), "tasks")
        assert result.status == "action_needed"
        assert result.details["pending"] == 2
        assert result.details["completed"] == 1

    @pytest.mark.asyncio
    async def test_check_git_status(self):
        result = await check_git_status()
        assert isinstance(result, HeartbeatCheckResult)
        assert result.check_type == "git_status"
        assert result.status in ("ok", "action_needed", "error")


def _fake_completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr,
    )


class TestHeartbeatObservability:
    """Rule 17 / ADR-001: a masked check failure must surface, never read as clean."""

    @pytest.mark.asyncio
    async def test_github_issues_ok_when_empty(self):
        with patch(
            "app.services.heartbeat.heartbeat_checks._run_sync",
            return_value=_fake_completed(returncode=0, stdout="[]"),
        ):
            result = await check_github_issues()
        assert result.status == "ok"
        assert result.details["check_failed"] is False
        assert result.summary == "No open bugs"

    @pytest.mark.asyncio
    async def test_github_issues_warns_on_nonzero_rc(self):
        """gh failing must NOT be reported as 'No open bugs' (empty-as-clean)."""
        with patch(
            "app.services.heartbeat.heartbeat_checks._run_sync",
            return_value=_fake_completed(returncode=1, stderr="gh: not authenticated"),
        ):
            result = await check_github_issues()
        assert result.status == "warning"
        assert result.details["check_failed"] is True
        assert "No open bugs" not in result.summary

    @pytest.mark.asyncio
    async def test_github_issues_warns_on_unparseable_output(self):
        """A JSON parse failure must surface, not silently read as a clean count."""
        with patch(
            "app.services.heartbeat.heartbeat_checks._run_sync",
            return_value=_fake_completed(returncode=0, stdout="not json <<<"),
        ):
            result = await check_github_issues()
        assert result.status == "warning"
        assert result.details["check_failed"] is True
        assert "unparseable" in result.summary

    @pytest.mark.asyncio
    async def test_github_issues_action_needed_when_bugs(self):
        with patch(
            "app.services.heartbeat.heartbeat_checks._run_sync",
            return_value=_fake_completed(
                returncode=0,
                stdout='[{"number": 7, "title": "boom", "createdAt": "2026-06-18"}]',
            ),
        ):
            result = await check_github_issues()
        assert result.status == "action_needed"
        assert result.details["check_failed"] is False
        assert "1 open bugs" in result.summary

    @pytest.mark.asyncio
    async def test_daily_report_shows_github_unavailable_on_failure(self, tmp_path):
        """A gh failure must not silently drop the GitHub section from the report."""
        with patch(
            "app.services.heartbeat.heartbeat_checks._run_sync",
            side_effect=RuntimeError("gh exploded"),
        ):
            result = await generate_daily_report(report_dir=str(tmp_path))
        assert result.status == "ok"
        content = Path(result.details["path"]).read_text(encoding="utf-8")
        assert "## Open GitHub Issues" in content
        assert "(github unavailable)" in content

    @pytest.mark.asyncio
    async def test_daily_report_logs_degraded_sections(self, tmp_path, capsys):
        """git/test/ollama probe failures must be visible to a log monitor, not
        only as a marker in a report a human may never open (Rule 17)."""
        with patch(
            "app.services.heartbeat.heartbeat_checks._run_sync",
            side_effect=RuntimeError("probe exploded"),
        ):
            result = await generate_daily_report(report_dir=str(tmp_path))
        assert result.status == "ok"
        content = Path(result.details["path"]).read_text(encoding="utf-8")
        # control flow preserved: every degraded section still writes its marker
        assert "(git log unavailable)" in content
        assert "Error running tests:" in content
        assert "(ollama unavailable)" in content
        # the fix: each degraded section is now also visible to a log monitor
        log_stream = "".join(capsys.readouterr())
        assert "heartbeat.daily_report_git_unavailable" in log_stream
        assert "heartbeat.daily_report_tests_unavailable" in log_stream
        assert "heartbeat.daily_report_ollama_unavailable" in log_stream


# ── Daemon tests ──

class TestHeartbeatDaemon:
    def test_singleton(self):
        d1 = HeartbeatDaemon.get_instance()
        d2 = HeartbeatDaemon.get_instance()
        assert d1 is d2
        # Reset for other tests
        HeartbeatDaemon._instance = None

    def test_get_status(self):
        daemon = HeartbeatDaemon()
        status = daemon.get_status()
        assert status["state"] == "stopped"
        assert status["interval_minutes"] == 30
        assert status["cycle_count"] == 0

    def test_configure(self):
        daemon = HeartbeatDaemon()
        daemon.configure({"interval_minutes": 10, "autopilot_level": "agi"})
        assert daemon.config.interval_minutes == 10
        assert daemon.config.autopilot_level == AutopilotLevel.AGI

    @pytest.mark.asyncio
    async def test_run_once(self):
        daemon = HeartbeatDaemon()
        cycle = await daemon.run_once()
        assert cycle.cycle_id == 1
        assert cycle.completed_at is not None
        assert len(cycle.results) > 0

    @pytest.mark.asyncio
    async def test_start_stop(self):
        daemon = HeartbeatDaemon()
        await daemon.start()
        assert daemon.config.state == HeartbeatState.RUNNING
        await daemon.stop()
        assert daemon.config.state == HeartbeatState.STOPPED

    @pytest.mark.asyncio
    async def test_pause_resume(self):
        daemon = HeartbeatDaemon()
        await daemon.start()
        await daemon.pause()
        assert daemon.config.state == HeartbeatState.PAUSED
        await daemon.resume()
        assert daemon.config.state == HeartbeatState.RUNNING
        await daemon.stop()

    def test_history_empty(self):
        daemon = HeartbeatDaemon()
        assert daemon.get_history() == []

    @pytest.mark.asyncio
    async def test_history_after_cycle(self):
        daemon = HeartbeatDaemon()
        await daemon.run_once()
        history = daemon.get_history()
        assert len(history) == 1
        assert history[0]["cycle_id"] == 1

    @pytest.mark.asyncio
    async def test_daily_cost_limit(self):
        daemon = HeartbeatDaemon()
        daemon.config.max_cost_per_day_usd = 0.0
        daemon.config.daily_cost_accumulated = 1.0
        cycle = await daemon.run_once()
        assert cycle.error is not None
        assert "cost limit" in cycle.error.lower()

    def test_should_auto_execute_off(self):
        daemon = HeartbeatDaemon()
        daemon.config.autopilot_level = AutopilotLevel.OFF
        assert daemon._should_auto_execute(ActionPriority.LOW) is False
        assert daemon._should_auto_execute(ActionPriority.CRITICAL) is False

    def test_should_auto_execute_on(self):
        daemon = HeartbeatDaemon()
        daemon.config.autopilot_level = AutopilotLevel.ON
        assert daemon._should_auto_execute(ActionPriority.LOW) is True
        assert daemon._should_auto_execute(ActionPriority.HIGH) is True
        assert daemon._should_auto_execute(ActionPriority.CRITICAL) is False

    def test_should_auto_execute_agi(self):
        daemon = HeartbeatDaemon()
        daemon.config.autopilot_level = AutopilotLevel.AGI
        assert daemon._should_auto_execute(ActionPriority.CRITICAL) is True


# ── Cron tests ──

class TestCronScheduler:
    def test_create_with_defaults(self):
        scheduler = CronScheduler.with_defaults()
        jobs = scheduler.get_jobs()
        assert len(jobs) == 2
        assert any(j["job_id"] == "morning_briefing" for j in jobs)
        assert any(j["job_id"] == "weekly_review" for j in jobs)

    def test_api_uses_process_wide_scheduler_singleton(self):
        from app.api.v1 import heartbeat as heartbeat_api

        reset_cron_scheduler_singleton()
        try:
            scheduler = get_cron_scheduler()
            assert heartbeat_api._get_scheduler() is scheduler
        finally:
            reset_cron_scheduler_singleton()

    def test_add_remove_job(self):
        scheduler = CronScheduler()
        job = CronJob(
            job_id="test",
            name="Test Job",
            frequency=CronFrequency.DAILY,
            run_at=time(12, 0),
        )
        scheduler.add_job(job)
        assert len(scheduler.get_jobs()) == 1
        assert scheduler.remove_job("test") is True
        assert len(scheduler.get_jobs()) == 0

    def test_job_is_due_never_run(self):
        job = CronJob(
            job_id="test",
            name="Test",
            frequency=CronFrequency.DAILY,
            run_at=datetime.now().time(),
        )
        assert job.is_due() is True

    def test_job_is_due_already_ran_today(self):
        job = CronJob(
            job_id="test",
            name="Test",
            frequency=CronFrequency.DAILY,
            run_at=datetime.now().time(),
            last_run=datetime.now(),
        )
        assert job.is_due() is False

    def test_job_not_due_wrong_time(self):
        # Pick run_at 6 hours offset from now so the +/-5 min window
        # in is_due() never overlaps the wall clock. The previous
        # implementation hardcoded 3 AM and only skipped when
        # now.hour == 3, but is_due() uses a +/-5 min window so
        # 02:55-03:05 also matches. This caused a flake at 02:59
        # during the 2026-04-29 audit-repair run.
        now = datetime.now()
        offset_hour = (now.hour + 6) % 24
        job = CronJob(
            job_id="test",
            name="Test",
            frequency=CronFrequency.DAILY,
            run_at=time(offset_hour, now.minute),
        )
        assert job.is_due() is False

    def test_weekly_job_wrong_day(self):
        job = CronJob(
            job_id="test",
            name="Test",
            frequency=CronFrequency.WEEKLY,
            run_at=datetime.now().time(),
            day_of_week=(datetime.now().weekday() + 1) % 7,  # Tomorrow
        )
        assert job.is_due() is False

    @pytest.mark.asyncio
    async def test_check_and_run(self):
        scheduler = CronScheduler()
        job = CronJob(
            job_id="test",
            name="Test",
            frequency=CronFrequency.DAILY,
            run_at=datetime.now().time(),
            enabled=True,
        )
        scheduler.add_job(job)
        executed = await scheduler.check_and_run()
        assert "test" in executed

    def test_job_to_dict(self):
        job = CronJob(
            job_id="test",
            name="Test Job",
            frequency=CronFrequency.DAILY,
            run_at=time(9, 0),
        )
        d = job.to_dict()
        assert d["job_id"] == "test"
        assert d["frequency"] == "daily"
        assert d["run_at"] == "09:00:00"


# ── API endpoint tests (via test client) ──

class TestHeartbeatAPI:
    """Tests for heartbeat API endpoints using the FastAPI test client."""

    @pytest.mark.asyncio
    async def test_heartbeat_status(self, client, auth_headers):
        resp = await client.get("/api/v1/heartbeat/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "state" in data["data"]

    @pytest.mark.asyncio
    async def test_heartbeat_config(self, client, auth_headers):
        resp = await client.get("/api/v1/heartbeat/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["interval_minutes"] == 30

    @pytest.mark.asyncio
    async def test_heartbeat_history(self, client, auth_headers):
        resp = await client.get("/api/v1/heartbeat/history", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_heartbeat_configure(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/heartbeat/configure",
            headers=auth_headers,
            json={"interval_minutes": 15},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["interval_minutes"] == 15

    @pytest.mark.asyncio
    async def test_cron_list(self, client, auth_headers):
        resp = await client.get("/api/v1/heartbeat/cron", headers=auth_headers)
        assert resp.status_code == 200


# ── PR-HB-DAEMON-WIRE (2026-05-02): lifecycle truth tests ──
#
# These tests pin the contract that the lifespan deferred init step
# (`_heartbeat_daemon` in `backend/app/main.py`) starts the daemon
# exactly once, that repeated calls do not orphan the loop task, and
# that status read-backs reflect real state across the start / pause
# / resume / stop transitions. The default-config tests pin the
# hardened check set so an auto-started daemon does not begin
# spending money or making external calls until the operator opts in.


class TestHeartbeatDaemonIdempotency:
    """Pins start() against duplicate-loop creation."""

    @pytest.mark.asyncio
    async def test_start_is_idempotent_against_repeated_calls(self):
        """Calling start() twice must keep one task and one loop."""
        daemon = HeartbeatDaemon()
        try:
            await daemon.start()
            first_task = daemon._task
            assert first_task is not None
            assert not first_task.done()
            assert daemon.config.state == HeartbeatState.RUNNING

            await daemon.start()  # idempotent re-call
            second_task = daemon._task
            assert second_task is first_task, (
                "Repeat start() must reuse the existing task; got a new one"
            )
            assert daemon.config.state == HeartbeatState.RUNNING
        finally:
            await daemon.stop()

    @pytest.mark.asyncio
    async def test_start_does_not_orphan_task_when_paused(self):
        """start() while PAUSED must not overwrite the live task.

        Pre-PR-HB-DAEMON-WIRE the guard checked only state == RUNNING,
        so calling start() while the daemon was PAUSED would set state
        back to RUNNING AND assign a fresh task to self._task,
        orphaning the original loop. The hardened guard keys on task
        aliveness, not state.
        """
        daemon = HeartbeatDaemon()
        try:
            await daemon.start()
            await daemon.pause()
            paused_task = daemon._task
            assert daemon.config.state == HeartbeatState.PAUSED

            await daemon.start()  # second start; must not orphan paused_task
            assert daemon._task is paused_task, (
                "start() while PAUSED orphaned the original loop task"
            )
            # State stays as it was; the guard short-circuits before
            # mutating state. Operator should call resume() to unpause.
            assert daemon.config.state == HeartbeatState.PAUSED
        finally:
            await daemon.stop()

    @pytest.mark.asyncio
    async def test_stop_after_start_clears_task_and_state(self):
        """stop() must cancel the task and report STOPPED via get_status()."""
        daemon = HeartbeatDaemon()
        await daemon.start()
        assert daemon._task is not None

        await daemon.stop()
        assert daemon._task is None
        assert daemon.config.state == HeartbeatState.STOPPED
        assert daemon.get_status()["state"] == "stopped"


class TestHeartbeatStatusTruth:
    """Pins get_status() truth across pause / resume / stop transitions."""

    @pytest.mark.asyncio
    async def test_status_after_start_is_running(self):
        daemon = HeartbeatDaemon()
        try:
            await daemon.start()
            assert daemon.get_status()["state"] == "running"
        finally:
            await daemon.stop()

    @pytest.mark.asyncio
    async def test_status_after_pause_is_paused(self):
        daemon = HeartbeatDaemon()
        try:
            await daemon.start()
            await daemon.pause()
            assert daemon.get_status()["state"] == "paused"
        finally:
            await daemon.stop()

    @pytest.mark.asyncio
    async def test_status_after_resume_is_running(self):
        daemon = HeartbeatDaemon()
        try:
            await daemon.start()
            await daemon.pause()
            await daemon.resume()
            assert daemon.get_status()["state"] == "running"
        finally:
            await daemon.stop()

    @pytest.mark.asyncio
    async def test_status_after_stop_is_stopped(self):
        daemon = HeartbeatDaemon()
        await daemon.start()
        await daemon.stop()
        assert daemon.get_status()["state"] == "stopped"


class TestHeartbeatDefaultsHardened:
    """Pins the default check set against accidental re-enabling.

    PR-HB-DAEMON-WIRE (2026-05-02) flipped the expensive / external
    checks to ``enabled=False`` so the auto-started daemon stays cheap
    and local. Re-enabling any of these by editing
    ``HeartbeatConfig.default()`` should fail this test loud and
    require an explicit founder-approved follow-up PR.
    """

    EXPECTED_DISABLED_BY_DEFAULT = {
        CheckType.QUEUE,
        CheckType.TEST_SUITE,
        CheckType.GITHUB_ISSUES,
        CheckType.OLLAMA_HEALTH,
        CheckType.OLLAMA_MODEL_UPDATES,
        CheckType.DAILY_REPORT,
        CheckType.DEPARTMENT_WORKFLOWS,
        CheckType.AUTONOMOUS_WORK,
    }

    EXPECTED_ENABLED_BY_DEFAULT = {
        CheckType.RUNTIME_HEALTH,
        CheckType.TASKS,
        CheckType.INBOX,
        CheckType.PROJECT_STATE,
        CheckType.GIT_STATUS,
        CheckType.FAILED_TASKS,
    }

    def test_default_config_disables_expensive_checks(self):
        cfg = HeartbeatConfig.default()
        by_type = {c.check_type: c for c in cfg.checks}
        for check_type in self.EXPECTED_DISABLED_BY_DEFAULT:
            assert check_type in by_type, (
                f"Default config missing {check_type.value}; "
                "did the check list shrink?"
            )
            assert by_type[check_type].enabled is False, (
                f"{check_type.value} must default to disabled per "
                "PR-HB-DAEMON-WIRE; flipping it on requires founder approval"
            )

    def test_default_config_keeps_cheap_local_checks_enabled(self):
        cfg = HeartbeatConfig.default()
        by_type = {c.check_type: c for c in cfg.checks}
        for check_type in self.EXPECTED_ENABLED_BY_DEFAULT:
            assert check_type in by_type, (
                f"Default config missing {check_type.value}"
            )
            assert by_type[check_type].enabled is True, (
                f"{check_type.value} should default to enabled "
                "(cheap local probe). If you intentionally disabled it, "
                "update EXPECTED_ENABLED_BY_DEFAULT."
            )


class TestHeartbeatLifespanWiring:
    """Smoke-tests the deferred init wiring in main.py.

    Reads the source rather than booting the full app to keep the
    test cheap. Existing FastAPI test client tests cover the full
    lifecycle integration; this just pins that the new step exists
    and uses the right symbol so a future refactor cannot silently
    drop the daemon start.
    """

    def test_main_lifespan_includes_heartbeat_daemon_step(self):
        from pathlib import Path

        main_path = (
            Path(__file__).resolve().parents[1] / "app" / "main.py"
        )
        source = main_path.read_text(encoding="utf-8")
        assert '_step("heartbeat_daemon"' in source, (
            "main.py lifespan deferred init must include a "
            'heartbeat_daemon step (look for `_step("heartbeat_daemon", ...)`)'
        )
        assert "HeartbeatDaemon.get_instance()" in source, (
            "Lifespan must call HeartbeatDaemon.get_instance() so the "
            "API endpoints + frontend share the same singleton"
        )
        assert "heartbeat_daemon_stopped" in source or "heartbeat_daemon_stop_skipped" in source, (
            "Shutdown handler must call daemon.stop() so a clean uvicorn "
            "shutdown drains the loop instead of orphaning the task"
        )
