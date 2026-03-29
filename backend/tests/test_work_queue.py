"""Tests for overnight work queue."""

from __future__ import annotations

import pytest

from app.services.heartbeat.work_queue import (
    QueueTask,
    QueueTaskPriority,
    QueueTaskStatus,
    WorkQueue,
)


class TestQueueTask:
    def test_create_task(self):
        t = QueueTask(task_id="t1", title="Test", prompt="Do something")
        assert t.status == QueueTaskStatus.PENDING
        assert t.priority == QueueTaskPriority.P2_MEDIUM

    def test_to_dict(self):
        t = QueueTask(task_id="t1", title="Test", prompt="Do something")
        d = t.to_dict()
        assert d["task_id"] == "t1"
        assert d["status"] == "pending"
        assert d["priority"] == 2

    def test_long_prompt_truncated_in_dict(self):
        t = QueueTask(task_id="t1", title="Test", prompt="x" * 300)
        d = t.to_dict()
        assert len(d["prompt"]) < 300
        assert d["prompt"].endswith("...")


class TestWorkQueue:
    def test_add_and_get_all(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="Task 1", prompt="Do 1"))
        q.add(QueueTask(task_id="t2", title="Task 2", prompt="Do 2"))
        assert len(q.get_all()) == 2

    def test_remove(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="Task 1", prompt="Do 1"))
        assert q.remove("t1") is True
        assert q.remove("t1") is False
        assert len(q.get_all()) == 0

    def test_get_next_by_priority(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="low", title="Low", prompt="", priority=QueueTaskPriority.P3_LOW))
        q.add(QueueTask(task_id="high", title="High", prompt="", priority=QueueTaskPriority.P0_CRITICAL))
        q.add(QueueTask(task_id="med", title="Med", prompt="", priority=QueueTaskPriority.P2_MEDIUM))
        nxt = q.get_next()
        assert nxt is not None
        assert nxt.task_id == "high"

    def test_get_next_respects_dependencies(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="First", prompt=""))
        q.add(QueueTask(
            task_id="t2", title="Second", prompt="",
            priority=QueueTaskPriority.P0_CRITICAL,
            depends_on=["t1"],
        ))
        # t2 has higher priority but depends on t1
        nxt = q.get_next()
        assert nxt.task_id == "t1"

    def test_get_next_after_dependency_completed(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="First", prompt=""))
        q.add(QueueTask(
            task_id="t2", title="Second", prompt="",
            depends_on=["t1"],
        ))
        q.mark_completed("t1", "Done")
        nxt = q.get_next()
        assert nxt.task_id == "t2"

    def test_get_next_empty_queue(self):
        q = WorkQueue()
        assert q.get_next() is None

    def test_get_next_all_completed(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="Task", prompt=""))
        q.mark_completed("t1", "Done")
        assert q.get_next() is None

    def test_mark_in_progress(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="Task", prompt=""))
        q.mark_in_progress("t1")
        tasks = q.get_all()
        assert tasks[0]["status"] == "in_progress"
        assert tasks[0]["started_at"] is not None

    def test_mark_completed(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="Task", prompt=""))
        q.mark_completed("t1", "All done", cost=0.05)
        tasks = q.get_all()
        assert tasks[0]["status"] == "completed"
        assert tasks[0]["result_summary"] == "All done"
        assert tasks[0]["cost_usd"] == 0.05

    def test_mark_failed(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="Task", prompt=""))
        q.mark_failed("t1", "Timeout")
        tasks = q.get_all()
        assert tasks[0]["status"] == "failed"
        assert tasks[0]["error"] == "Timeout"

    def test_get_summary(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="Task 1", prompt=""))
        q.add(QueueTask(task_id="t2", title="Task 2", prompt=""))
        q.mark_completed("t1", "Done", cost=0.10)
        summary = q.get_summary()
        assert summary["total"] == 2
        assert summary["by_status"]["completed"] == 1
        assert summary["by_status"]["pending"] == 1
        assert summary["total_cost_usd"] == 0.10

    def test_generate_briefing(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="t1", title="Done Task", prompt=""))
        q.add(QueueTask(task_id="t2", title="Failed Task", prompt=""))
        q.add(QueueTask(task_id="t3", title="Pending Task", prompt=""))
        q.mark_completed("t1", "Success", cost=0.05)
        q.mark_failed("t2", "Timeout error")
        briefing = q.generate_briefing()
        assert "Morning Briefing" in briefing
        assert "Completed: 1" in briefing
        assert "Failed: 1" in briefing
        assert "Remaining: 1" in briefing
        assert "Done Task" in briefing
        assert "Failed Task" in briefing

    def test_overnight_default(self):
        q = WorkQueue.overnight_default()
        tasks = q.get_all()
        assert len(tasks) == 6
        # First task should be NVIDIA (P0)
        assert tasks[0]["task_id"] == "nvidia_inception"
        assert tasks[0]["priority"] == 0

    def test_sorted_by_priority(self):
        q = WorkQueue()
        q.add(QueueTask(task_id="low", title="Low", prompt="", priority=QueueTaskPriority.P3_LOW))
        q.add(QueueTask(task_id="crit", title="Critical", prompt="", priority=QueueTaskPriority.P0_CRITICAL))
        tasks = q.get_all()
        assert tasks[0]["task_id"] == "crit"
        assert tasks[1]["task_id"] == "low"
