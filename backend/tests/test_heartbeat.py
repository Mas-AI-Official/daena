"""Tests for heartbeat daemon, checks, config, and cron scheduler."""

from __future__ import annotations

import asyncio
from datetime import datetime, time

import pytest

from app.services.heartbeat.heartbeat_checks import (
    ActionPriority,
    HeartbeatCheckResult,
    check_file,
    check_git_status,
    check_runtime_health,
)
from app.services.heartbeat.heartbeat_config import (
    AutopilotLevel,
    CheckType,
    HeartbeatCheck,
    HeartbeatConfig,
    HeartbeatState,
)
from app.services.heartbeat.heartbeat_daemon import HeartbeatDaemon
from app.services.heartbeat.cron_scheduler import CronFrequency, CronJob, CronScheduler


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
        job = CronJob(
            job_id="test",
            name="Test",
            frequency=CronFrequency.DAILY,
            run_at=time(3, 0),  # 3 AM -- unlikely to be current time in tests
        )
        now = datetime.now()
        if now.hour != 3:  # Skip if actually 3 AM
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
