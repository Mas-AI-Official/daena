"""Regression: bulk-install background job must retain a strong task ref.

Owns the fire-and-forget retention contract for the security dashboard's
``/tools/install-all`` endpoint. ``asyncio`` only keeps a *weak* reference to
tasks created via ``create_task``; a bare ``asyncio.create_task(...)`` whose
handle is dropped can be garbage-collected mid-run (the documented repo hazard,
see ``app.services.dept_knowledge_ingest._INFLIGHT``). ``_schedule_install_job``
fixes this by holding the task in a module-level set and self-cleaning in the
done callback.

The oracle here is the retention *mechanism*, not the (nondeterministic) GC
event: assert the task is tracked while running and removed once complete.
Reverting the fix removes ``_install_inflight`` / ``_schedule_install_job``
entirely, so this test fails to even resolve the symbols -- RED by construction.
"""

from __future__ import annotations

import asyncio

import pytest

from app.api.v1 import security_dashboard as sd


class TestInstallJobTaskRetention:
    @pytest.mark.asyncio
    async def test_schedule_retains_running_task_then_self_cleans(self, monkeypatch):
        sd._install_inflight.clear()

        started = asyncio.Event()
        release = asyncio.Event()

        async def _fake_run_install_job(job_id: str, plan: list) -> None:
            started.set()
            await release.wait()

        # _schedule_install_job resolves _run_install_job as a module global at
        # call time, so patching the module attribute redirects it here.
        monkeypatch.setattr(sd, "_run_install_job", _fake_run_install_job)

        try:
            task = sd._schedule_install_job("job-retention-test", [])

            # Strong ref retained immediately at schedule time.
            assert task in sd._install_inflight
            assert len(sd._install_inflight) == 1

            # ...and still retained while the job is actually running.
            await asyncio.wait_for(started.wait(), timeout=1.0)
            assert task in sd._install_inflight

            # Let the job finish; the done callback must discard the ref.
            release.set()
            await asyncio.wait_for(task, timeout=1.0)

            # The done callback runs via loop.call_soon; yield until it fires.
            for _ in range(10):
                if task not in sd._install_inflight:
                    break
                await asyncio.sleep(0)

            assert task not in sd._install_inflight, "done callback must discard the task"
            assert len(sd._install_inflight) == 0
        finally:
            sd._install_inflight.clear()
