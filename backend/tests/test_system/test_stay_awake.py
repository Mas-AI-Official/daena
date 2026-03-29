"""Tests for Stay-Awake System."""

from __future__ import annotations

import time
import pytest

from app.services.system.stay_awake import (
    AwakeMode,
    AwakeStatus,
    StayAwakeConfig,
    StayAwakeService,
)


@pytest.fixture
def svc() -> StayAwakeService:
    return StayAwakeService(StayAwakeConfig(
        mode=AwakeMode.TASK,
        cooldown_seconds=1,  # fast cooldown for tests
        max_awake_minutes=1,  # 1 min safety cap for tests
    ))


class TestTaskMode:
    def test_task_start_activates(self, svc: StayAwakeService):
        svc.on_task_start("task-1")
        assert svc.get_status().awake is True
        assert svc.get_status().active_tasks == 1

    def test_task_end_starts_cooldown(self, svc: StayAwakeService):
        svc.on_task_start("task-1")
        svc.on_task_end("task-1")
        # Still awake during cooldown
        assert svc.get_status().awake is True
        assert svc.get_status().active_tasks == 0

    def test_cooldown_releases(self, svc: StayAwakeService):
        svc.on_task_start("task-1")
        svc.on_task_end("task-1")
        time.sleep(1.5)  # wait for 1s cooldown
        assert svc.get_status().awake is False

    def test_multiple_tasks_stay_awake(self, svc: StayAwakeService):
        svc.on_task_start("task-1")
        svc.on_task_start("task-2")
        svc.on_task_end("task-1")
        # task-2 still running
        assert svc.get_status().awake is True
        assert svc.get_status().active_tasks == 1

    def test_all_tasks_complete_immediate_release(self, svc: StayAwakeService):
        svc.on_task_start("task-1")
        svc.on_task_start("task-2")
        svc.on_all_tasks_complete()
        assert svc.get_status().awake is False
        assert svc.get_status().active_tasks == 0


class TestSafetyCap:
    def test_safety_cap_enforced(self):
        svc = StayAwakeService(StayAwakeConfig(
            mode=AwakeMode.TASK,
            max_awake_minutes=0.02,  # ~1.2 seconds
        ))
        svc.on_task_start("task-1")
        assert svc.get_status().awake is True
        time.sleep(2)
        assert svc.get_status().awake is False


class TestManualControl:
    def test_start_stop(self, svc: StayAwakeService):
        assert svc.start_keep_awake() is True
        assert svc.get_status().awake is True
        assert svc.stop_keep_awake() is True
        assert svc.get_status().awake is False

    def test_double_start_returns_false(self, svc: StayAwakeService):
        svc.start_keep_awake()
        assert svc.start_keep_awake() is False

    def test_double_stop_returns_false(self, svc: StayAwakeService):
        assert svc.stop_keep_awake() is False


class TestNotification:
    def test_notify_on_sleep(self, svc: StayAwakeService):
        notifications: list[str] = []
        svc.set_notify_callback(lambda msg: notifications.append(msg))
        svc.start_keep_awake()
        svc.stop_keep_awake()
        assert len(notifications) == 1
        assert "sleep" in notifications[0].lower()


class TestScheduledMode:
    def test_scheduled_check(self):
        import datetime
        now = datetime.datetime.now()
        svc = StayAwakeService(StayAwakeConfig(
            mode=AwakeMode.SCHEDULED,
            scheduled_start_hour=0,
            scheduled_end_hour=24,
        ))
        assert svc.check_scheduled() is True

    def test_outside_schedule(self):
        svc = StayAwakeService(StayAwakeConfig(
            mode=AwakeMode.SCHEDULED,
            scheduled_start_hour=25,  # impossible hour
            scheduled_end_hour=26,
        ))
        assert svc.check_scheduled() is False


class TestStatus:
    def test_initial_status(self, svc: StayAwakeService):
        status = svc.get_status()
        assert isinstance(status, AwakeStatus)
        assert status.awake is False
        assert status.active_tasks == 0
        assert status.minutes_remaining == 0.0
