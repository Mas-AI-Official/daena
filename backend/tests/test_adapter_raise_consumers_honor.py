"""BUILD-NOW #3 gate: adapters raise, consumers honor.

Locks the honesty contract (ADR-001) from
Doc/best_version_20260708/master.md #3: adapters raise
RuntimeExecutionError instead of yielding error text as stream content,
and every consumer converts the raise into an explicit failed/error
status. Zero paths record status=="success" with error text.

RED anchor: before the fix, ClaudeCodeAdapter yielded
"[Claude Code error: ...]" and CodexAdapter yielded "[Codex error: ...]"
as normal stream chunks -- the adapter-raise tests here fail on that
old behavior.
"""

from types import SimpleNamespace

import pytest

from app.services.providers.claude_cli import _looks_like_cli_auth_error
from app.services.runtimes.adapters import codex as codex_module
from app.services.runtimes.adapters.claude_code import ClaudeCodeAdapter
from app.services.runtimes.adapters.codex import CodexAdapter
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeExecutionError,
    RuntimeStatus,
)
from app.services.runtimes.registry import RuntimeRegistry
from app.services.swarm.executor import SwarmExecutor
from app.services.swarm.planner import SubTask

AUTH_MSG = "Not logged in -- Please run /login"


# -- Helpers -----------------------------------------------------------


class RaisingAdapter(BaseRuntimeAdapter):
    """Healthy-looking adapter whose execute always raises."""

    def __init__(self, runtime_id: str = "claude_code"):
        super().__init__(runtime_id, f"Raising ({runtime_id})")

    async def check_installed(self) -> bool:
        return True

    async def check_health(self) -> RuntimeStatus:
        return RuntimeStatus.ONLINE

    async def get_capabilities(self) -> RuntimeCapability:
        return RuntimeCapability(code_generation=5.0, simple_chat=5.0)

    async def execute(self, task, context):
        if False:  # pragma: no cover -- never yields
            yield ""
        raise RuntimeExecutionError(
            runtime_id=self.runtime_id, message=AUTH_MSG,
        )

    async def cancel(self, session_id) -> bool:
        return True

    def get_auth_requirements(self):
        return {"type": "none"}


class _FakeSessionManager:
    """Stands in for ClaudeCodeAdapter._session_manager."""

    def __init__(self, result):
        self._result = result

    async def send(self, *args, **kwargs):
        return self._result

    def get(self, session_id):
        return None


async def _collect(agen, sink: list):
    """Drain an async generator into ``sink`` (survives a mid-raise)."""
    async for chunk in agen:
        sink.append(chunk)


# -- Adapters raise ----------------------------------------------------


class TestClaudeCodeAdapterRaises:
    @pytest.mark.asyncio
    async def test_error_result_raises_and_yields_nothing(self):
        adapter = ClaudeCodeAdapter()
        adapter._session_manager = _FakeSessionManager(
            SimpleNamespace(
                is_error=True,
                result_text=AUTH_MSG,
                cost_usd=0.0,
                duration_ms=0,
            )
        )
        chunks: list[str] = []
        with pytest.raises(RuntimeExecutionError) as excinfo:
            await _collect(
                adapter.execute("say hi", {"session_id": "s1"}), chunks,
            )
        assert chunks == []  # old behavior yielded "[Claude Code error: ...]"
        assert excinfo.value.runtime_id == "claude_code"
        assert "Not logged in" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_success_path_unchanged(self):
        adapter = ClaudeCodeAdapter()
        adapter._session_manager = _FakeSessionManager(
            SimpleNamespace(
                is_error=False,
                result_text="hello world",
                cost_usd=0.0,
                duration_ms=0,
            )
        )
        chunks: list[str] = []
        await _collect(
            adapter.execute("say hi", {"session_id": "s1"}), chunks,
        )
        assert chunks == ["hello world"]


class TestCodexAdapterRaises:
    def _adapter(self) -> CodexAdapter:
        adapter = CodexAdapter()
        adapter._codex_bin = "codex"  # independent of local install state
        return adapter

    @pytest.mark.asyncio
    async def test_timeout_raises(self, monkeypatch):
        import subprocess

        def _timeout(cmd, cwd, timeout):
            raise subprocess.TimeoutExpired(cmd="codex", timeout=300)

        monkeypatch.setattr(codex_module, "_run_cmd", _timeout)
        adapter = self._adapter()
        chunks: list[str] = []
        with pytest.raises(RuntimeExecutionError) as excinfo:
            await _collect(adapter.execute("say hi", {}), chunks)
        assert chunks == []
        assert excinfo.value.runtime_id == "codex"
        assert "timed out" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_generic_error_raises(self, monkeypatch):
        def _boom(cmd, cwd, timeout):
            raise OSError("codex binary vanished")

        monkeypatch.setattr(codex_module, "_run_cmd", _boom)
        adapter = self._adapter()
        chunks: list[str] = []
        with pytest.raises(RuntimeExecutionError) as excinfo:
            await _collect(adapter.execute("say hi", {}), chunks)
        assert chunks == []  # old behavior yielded "[Codex error: ...]"
        assert "codex binary vanished" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_stderr_never_yielded(self, monkeypatch):
        # QA finding F-0011: the CLI banner on stderr carries
        # workdir/model/provider/session-id strings -- backend logs only,
        # never the SSE stream.
        def _ok_with_banner(cmd, cwd, timeout):
            return SimpleNamespace(
                stdout="real output\n",
                stderr="workdir: D:/secret | model: gpt | session-id: abc\n",
                returncode=0,
            )

        monkeypatch.setattr(codex_module, "_run_cmd", _ok_with_banner)
        adapter = self._adapter()
        chunks: list[str] = []
        await _collect(adapter.execute("say hi", {}), chunks)
        assert chunks == ["real output"]
        assert all("workdir" not in c and "session-id" not in c for c in chunks)


# -- Consumers honor ---------------------------------------------------


class TestExecutorMarksFailed:
    @pytest.mark.asyncio
    async def test_subtask_failed_on_adapter_raise(self):
        registry = RuntimeRegistry()
        registry.register(RaisingAdapter("claude_code"))
        await registry.discover_all()
        await registry.check_health_all()

        executor = SwarmExecutor(registry)
        subtask = SubTask(
            description="do thing",
            task_type="code_generation",
            assigned_runtime="claude_code",
        )
        receipt = await executor.execute_single(subtask)

        assert subtask.status == "failed"
        assert receipt.status == "error"
        assert receipt.status != "success"
        assert "Not logged in" in (receipt.error_detail or "")


class TestAgentLoopMarksFailed:
    @pytest.mark.asyncio
    async def test_act_returns_success_false_on_adapter_raise(
        self, monkeypatch,
    ):
        from app.services.agent_core.agent_loop import (
            AgentLoop,
            AgentStep,
            ExecutionReceipt,
        )

        raising = RaisingAdapter("claude_code")

        class _FakeRegistry:
            def get_adapter(self, runtime_id):
                return raising if runtime_id == "claude_code" else None

            async def ensure_health_fresh(self, runtime_id):
                return RuntimeStatus.ONLINE

        import app.core.events as events_module

        monkeypatch.setattr(
            events_module, "get_runtime_registry", lambda: _FakeRegistry(),
        )

        loop = AgentLoop()
        loop._receipt = ExecutionReceipt(task="test task")
        step = AgentStep(step_id=1, description="do thing")

        result = await loop._act(step, {})

        assert result.success is False
        assert "Not logged in" in (result.error or "")


class TestRegistryFallbackHonors:
    @pytest.mark.asyncio
    async def test_execute_with_fallback_reports_failure(self):
        registry = RuntimeRegistry()
        registry.register(RaisingAdapter("vllm"))
        await registry.discover_all()

        result = await registry.execute_with_fallback("say hi")

        assert result["success"] is False


# -- Auth detection survives the raise conversion ----------------------


class TestAuthMarkersSurvive:
    def test_auth_error_text_survives_raise_conversion(self):
        # chat_orchestrator's failover branch runs
        # _looks_like_cli_auth_error(str(exc)) -- str() must carry the
        # underlying message verbatim so content markers still match.
        exc = RuntimeExecutionError(
            runtime_id="claude_code", message=AUTH_MSG,
        )
        assert _looks_like_cli_auth_error(str(exc)) is True
