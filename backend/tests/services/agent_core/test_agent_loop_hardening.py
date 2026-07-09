"""BUILD-NOW #6 gate: AgentLoop._act hardening.

Locks three honesty/robustness contracts from
Doc/best_version_20260708/master.md #6:

1. Runtime selection is derived from the registry's actually-registered
   runtimes (fresh health probe), NOT a stale hardcoded list. The old
   list ``["claude_code", "codex", "ollama"]`` skipped the live local
   runtime (vllm) and still named deprecated ollama, so a task that
   could run on vllm dead-ended with "No runtime available".

2. A per-step timeout wraps ``adapter.execute``. The class defined
   ``STEP_TIMEOUT_SECONDS`` but never used it -- a hung runtime stalled
   the whole loop forever. A timeout is now an explicit failed step.

3. Empty output is a FAILURE, not a hollow success (Rule 17 / ADR-001).
   The old code returned ``success=True`` whenever no exception fired,
   even when the runtime produced nothing.

RED anchors (before the fix): test 1 gets "No runtime available";
tests 2 and 3 get ``success=True``.
"""

import asyncio

import pytest

from app.services.agent_core.agent_loop import (
    AgentLoop,
    AgentStep,
    ExecutionReceipt,
)
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeStatus,
)


# -- Test doubles ------------------------------------------------------


class _ScriptedAdapter(BaseRuntimeAdapter):
    """Healthy adapter that yields a fixed script, optionally after a sleep."""

    def __init__(self, runtime_id: str = "vllm", *, lines=None, sleep: float = 0.0):
        super().__init__(runtime_id, f"Scripted ({runtime_id})")
        self._lines = list(lines or [])
        self._sleep = sleep

    async def check_installed(self) -> bool:
        return True

    async def check_health(self) -> RuntimeStatus:
        return RuntimeStatus.ONLINE

    async def get_capabilities(self) -> RuntimeCapability:
        return RuntimeCapability(code_generation=5.0, simple_chat=5.0)

    async def execute(self, task, context):
        if self._sleep:
            await asyncio.sleep(self._sleep)
        for line in self._lines:
            yield line

    async def cancel(self, session_id) -> bool:
        return True

    def get_auth_requirements(self):
        return {"type": "none"}


class _FakeRegistry:
    """Registry double that exposes registered/online ids and fresh health."""

    def __init__(self, adapters: dict, online: set):
        self._adapters = adapters
        self._online = set(online)

    @property
    def registered_ids(self):
        return list(self._adapters.keys())

    @property
    def online_ids(self):
        return [rid for rid in self._adapters if rid in self._online]

    def get_adapter(self, runtime_id):
        return self._adapters.get(runtime_id)

    async def ensure_health_fresh(self, runtime_id):
        return (
            RuntimeStatus.ONLINE
            if runtime_id in self._online
            else RuntimeStatus.OFFLINE
        )


def _patch_registry(monkeypatch, registry) -> None:
    import app.core.events as events_module

    monkeypatch.setattr(
        events_module, "get_runtime_registry", lambda: registry,
    )


def _fresh_loop() -> AgentLoop:
    loop = AgentLoop()
    loop._receipt = ExecutionReceipt(task="test task")
    return loop


# -- 1. Selection from registered runtimes (vllm no longer skipped) ----


class TestRuntimeSelection:
    @pytest.mark.asyncio
    async def test_selects_vllm_when_it_is_the_only_online_runtime(
        self, monkeypatch,
    ):
        # vllm is registered + online; the deprecated hardcoded trio
        # (claude_code, codex, ollama) has no adapter at all. The old
        # code never probed vllm and dead-ended.
        registry = _FakeRegistry(
            {"vllm": _ScriptedAdapter("vllm", lines=["done: task complete"])},
            online={"vllm"},
        )
        _patch_registry(monkeypatch, registry)

        loop = _fresh_loop()
        result = await loop._act(AgentStep(step_id=1, description="do"), {})

        assert result.success is True
        assert result.runtime_used == "vllm"
        assert "task complete" in result.output

    @pytest.mark.asyncio
    async def test_priority_prefers_claude_over_vllm_when_both_online(
        self, monkeypatch,
    ):
        registry = _FakeRegistry(
            {
                "claude_code": _ScriptedAdapter("claude_code", lines=["cc out"]),
                "vllm": _ScriptedAdapter("vllm", lines=["vllm out"]),
            },
            online={"claude_code", "vllm"},
        )
        _patch_registry(monkeypatch, registry)

        loop = _fresh_loop()
        result = await loop._act(AgentStep(step_id=1, description="do"), {})

        assert result.success is True
        assert result.runtime_used == "claude_code"


# -- 2. Per-step timeout -----------------------------------------------


class TestPerStepTimeout:
    @pytest.mark.asyncio
    async def test_hung_runtime_times_out_as_explicit_failure(
        self, monkeypatch,
    ):
        # Adapter sleeps well past the (shortened) step timeout. Old code
        # had no wait_for, so it would block then report a hollow result.
        registry = _FakeRegistry(
            {"vllm": _ScriptedAdapter("vllm", lines=["late"], sleep=1.5)},
            online={"vllm"},
        )
        _patch_registry(monkeypatch, registry)

        loop = _fresh_loop()
        loop.STEP_TIMEOUT_SECONDS = 0.05  # instance override
        result = await loop._act(AgentStep(step_id=1, description="do"), {})

        assert result.success is False
        assert "timed out" in (result.error or "")
        assert result.runtime_used == "vllm"


# -- 3. Empty output is a failure, not a success -----------------------


class TestEmptyOutputIsFailure:
    @pytest.mark.asyncio
    async def test_no_output_is_reported_as_failure(self, monkeypatch):
        registry = _FakeRegistry(
            {"vllm": _ScriptedAdapter("vllm", lines=[])},
            online={"vllm"},
        )
        _patch_registry(monkeypatch, registry)

        loop = _fresh_loop()
        result = await loop._act(AgentStep(step_id=1, description="do"), {})

        assert result.success is False
        assert "no output" in (result.error or "")

    @pytest.mark.asyncio
    async def test_whitespace_only_output_is_reported_as_failure(
        self, monkeypatch,
    ):
        registry = _FakeRegistry(
            {"vllm": _ScriptedAdapter("vllm", lines=["   ", ""])},
            online={"vllm"},
        )
        _patch_registry(monkeypatch, registry)

        loop = _fresh_loop()
        result = await loop._act(AgentStep(step_id=1, description="do"), {})

        assert result.success is False
        assert "no output" in (result.error or "")

    @pytest.mark.asyncio
    async def test_non_empty_output_still_succeeds(self, monkeypatch):
        registry = _FakeRegistry(
            {"vllm": _ScriptedAdapter("vllm", lines=["real work happened"])},
            online={"vllm"},
        )
        _patch_registry(monkeypatch, registry)

        loop = _fresh_loop()
        result = await loop._act(AgentStep(step_id=1, description="do"), {})

        assert result.success is True
        assert "real work happened" in result.output
