"""Tests for WeaknessTracker durable snapshot + per-tenant factory.

Contract under test (Rule 17: fail open, visibly; never lose the signal
silently):
    - Default no-arg constructor stays PURE IN-MEMORY (test_cognitive_engine
      compatibility) and never touches disk.
    - storage_path constructor rehydrates on init and snapshots on record().
    - Corrupt snapshot -> warn + fresh start, never raises, next record()
      heals the file.
    - Error log capped at 20 per key, in memory and in the snapshot.
    - get_weakness_tracker: per-tenant singleton + per-tenant file;
      tenant None -> shared memory-only instance, no file ever (leak guard).
    - build_weakness_note: relevance-filtered orientation note.
"""

from __future__ import annotations

import json
from uuid import UUID

import pytest

from app.services.cognition import weakness_tracker as wt
from app.services.cognition.weakness_tracker import (
    WeaknessTracker,
    build_weakness_note,
    get_weakness_tracker,
)

TENANT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def wt_dir(monkeypatch, tmp_path):
    """Redirect snapshots to a per-test dir and reset the factory registry."""
    snap_dir = tmp_path / "wt_snapshots"
    monkeypatch.setattr(wt, "_TRACKERS", {})
    monkeypatch.setattr(wt, "_storage_dir", lambda: snap_dir)
    return snap_dir


async def _record_failures(
    tracker: WeaknessTracker,
    problem_type: str = "deployment",
    n: int = 3,
    error: str = "timeout",
    strategy: str = "direct_execution",
) -> None:
    for _ in range(n):
        await tracker.record(
            problem_type=problem_type,
            strategy=strategy,
            tools_used=[],
            success=False,
            error=error,
        )


class TestDurableSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_survives_restart(self, wt_dir) -> None:
        path = wt_dir / "weakness-test.json"
        t1 = WeaknessTracker(storage_path=path)
        await _record_failures(t1, n=3, error="timeout")

        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"] == 1

        # Fresh instance on the same path = simulated process restart.
        t2 = WeaknessTracker(storage_path=path)
        weaknesses = await t2.get_weaknesses()
        pt = [w for w in weaknesses if w.category == "problem_type"]
        assert pt and pt[0].name == "deployment"
        assert pt[0].failure_rate == 1.0
        assert "timeout" in pt[0].common_errors[0]

    @pytest.mark.asyncio
    async def test_default_constructor_writes_nothing(self, wt_dir) -> None:
        t = WeaknessTracker()
        await _record_failures(t, n=3)
        assert not wt_dir.exists() or not list(wt_dir.iterdir())

    @pytest.mark.asyncio
    async def test_corrupt_snapshot_fails_open_and_heals(self, wt_dir) -> None:
        path = wt_dir / "weakness-corrupt.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not valid json", encoding="utf-8")

        t = WeaknessTracker(storage_path=path)  # must not raise
        assert t.get_summary()["problem_types"] == {}

        await _record_failures(t, n=1)
        data = json.loads(path.read_text(encoding="utf-8"))  # file healed
        assert data["problem_types"]["deployment"]["failures"] == 1

    @pytest.mark.asyncio
    async def test_error_log_capped_at_20(self, wt_dir) -> None:
        path = wt_dir / "weakness-cap.json"
        t = WeaknessTracker(storage_path=path)
        for i in range(30):
            await t.record(
                problem_type="deployment",
                strategy="s",
                tools_used=[],
                success=False,
                error=f"err-{i}",
            )

        assert len(t._error_log["pt_deployment"]) == 20
        assert t._error_log["pt_deployment"][0] == "err-10"  # oldest evicted
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data["errors"]["pt_deployment"]) == 20


class TestFactory:
    @pytest.mark.asyncio
    async def test_per_tenant_singleton_and_files(self, wt_dir) -> None:
        ta = get_weakness_tracker(TENANT_A)
        assert get_weakness_tracker(TENANT_A) is ta
        tb = get_weakness_tracker(TENANT_B)
        assert tb is not ta

        await _record_failures(ta, n=1)
        await _record_failures(tb, n=1)
        assert (wt_dir / f"weakness-{TENANT_A.hex}.json").exists()
        assert (wt_dir / f"weakness-{TENANT_B.hex}.json").exists()

    @pytest.mark.asyncio
    async def test_none_tenant_memory_only_no_files(self, wt_dir) -> None:
        t = get_weakness_tracker(None)
        assert get_weakness_tracker(None) is t
        await _record_failures(t, n=3)
        assert not wt_dir.exists() or not list(wt_dir.iterdir())

    @pytest.mark.asyncio
    async def test_factory_rehydrates_after_restart(self, wt_dir) -> None:
        t1 = get_weakness_tracker(TENANT_A)
        await _record_failures(t1, n=3, error="timeout")

        wt._TRACKERS.clear()  # simulated process restart

        t2 = get_weakness_tracker(TENANT_A)
        assert t2 is not t1
        weaknesses = await t2.get_weaknesses()
        assert any(
            w.category == "problem_type" and w.name == "deployment"
            for w in weaknesses
        )


class TestBuildWeaknessNote:
    @pytest.mark.asyncio
    async def test_note_for_weak_problem_type(self, wt_dir) -> None:
        t = WeaknessTracker()
        # Distinct strategies keep each below min_attempts so only the
        # problem_type dimension turns weak.
        for i in range(3):
            await t.record(
                problem_type="deployment",
                strategy=f"s{i}",
                tools_used=[],
                success=False,
                error="timeout",
            )

        note = await build_weakness_note(t, "deployment")
        assert "KNOWN WEAKNESSES" in note
        assert "deployment" in note
        assert "Suggestion:" in note

        # Foreign problem type -> excluded (no strategy weakness exists).
        assert await build_weakness_note(t, "debugging") == ""

    @pytest.mark.asyncio
    async def test_note_empty_tracker(self, wt_dir) -> None:
        assert await build_weakness_note(WeaknessTracker(), "deployment") == ""
