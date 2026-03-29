"""Tests for the Runtime Adapter Layer (V2 Phase 1).

Covers:
- BaseRuntimeAdapter contract
- RuntimeRegistry (register, discover, health, select)
- SessionManager (create, cancel, timeout)
- CapabilityMatrix (intent mapping, scoring, ranking)
- CostEstimator (estimate, record, session totals)
- ModelRouter.route_runtime() integration
- All adapter capability declarations
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.query_understanding import IntentType
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    ExecutionReceipt,
    RuntimeCapability,
    RuntimeStatus,
)
from app.services.runtimes.capability_matrix import (
    composite_score,
    rank_runtimes,
    task_type_for_intent,
)
from app.services.runtimes.cost_estimator import CostEstimator
from app.services.runtimes.registry import (
    NoRuntimeAvailableError,
    RuntimeRegistry,
)
from app.services.runtimes.session_manager import SessionManager

# ── Fixture: Mock adapter ──────────────────────────────────────

class MockAdapter(BaseRuntimeAdapter):
    """Test adapter with configurable behavior."""

    def __init__(
        self,
        runtime_id: str = "mock",
        installed: bool = True,
        health: RuntimeStatus = RuntimeStatus.ONLINE,
        capabilities: RuntimeCapability | None = None,
    ):
        super().__init__(runtime_id, f"Mock ({runtime_id})")
        self._installed = installed
        self._health = health
        self._capabilities = capabilities or RuntimeCapability(
            complex_reasoning=5.0,
            code_generation=5.0,
            simple_chat=5.0,
        )

    async def check_installed(self) -> bool:
        return self._installed

    async def check_health(self) -> RuntimeStatus:
        return self._health

    async def get_capabilities(self) -> RuntimeCapability:
        return self._capabilities

    async def execute(self, task, context):
        yield "mock output line 1"
        yield "mock output line 2"

    async def cancel(self, session_id):
        return True

    def get_auth_requirements(self):
        return {"type": "none"}


# ── BaseRuntimeAdapter tests ──────────────────────────────────

class TestRuntimeCapability:
    def test_score_for_valid_field(self):
        caps = RuntimeCapability(code_generation=9.5, simple_chat=7.0)
        assert caps.score_for("code_generation") == 9.5
        assert caps.score_for("simple_chat") == 7.0

    def test_score_for_invalid_field(self):
        caps = RuntimeCapability()
        assert caps.score_for("nonexistent_field") == 0.0

    def test_to_dict(self):
        caps = RuntimeCapability(code_generation=9.0, cost_per_1k_tokens=0.015)
        d = caps.to_dict()
        assert d["code_generation"] == 9.0
        assert d["cost_per_1k_tokens"] == 0.015
        assert len(d) == 10  # all fields present


class TestExecutionReceipt:
    def test_to_dict_truncates_output(self):
        receipt = ExecutionReceipt(
            runtime_id="test",
            task_description="test task",
            assigned_reason="highest score",
            capability_score=9.0,
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-01T00:00:05",
            duration_ms=5000,
            token_count=100,
            estimated_cost_usd=0.005,
            status="success",
            output_summary="x" * 1000,
            governance_tier="tier_0",
        )
        d = receipt.to_dict()
        assert len(d["output_summary"]) == 500
        assert d["status"] == "success"
        assert d["runtime_id"] == "test"


# ── RuntimeRegistry tests ─────────────────────────────────────

class TestRuntimeRegistry:
    def test_register_and_list(self):
        registry = RuntimeRegistry()
        adapter = MockAdapter("test_rt")
        registry.register(adapter)
        assert "test_rt" in registry.registered_ids
        assert registry.get_adapter("test_rt") is adapter

    def test_unregister(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter("to_remove"))
        registry.unregister("to_remove")
        assert "to_remove" not in registry.registered_ids
        assert registry.get_adapter("to_remove") is None

    @pytest.mark.asyncio
    async def test_discover_all(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter("installed", installed=True))
        registry.register(MockAdapter("missing", installed=False))
        results = await registry.discover_all()
        assert results["installed"] is True
        assert results["missing"] is False

    @pytest.mark.asyncio
    async def test_check_health_all(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter("healthy", health=RuntimeStatus.ONLINE))
        registry.register(MockAdapter("sick", health=RuntimeStatus.ERROR))
        # Must discover first (sets installed cache)
        await registry.discover_all()
        results = await registry.check_health_all()
        assert results["healthy"] == RuntimeStatus.ONLINE
        assert results["sick"] == RuntimeStatus.ERROR

    @pytest.mark.asyncio
    async def test_select_runtime_auto(self):
        registry = RuntimeRegistry()
        # Register two runtimes with different strengths
        registry.register(MockAdapter(
            "coder", capabilities=RuntimeCapability(code_generation=9.0),
        ))
        registry.register(MockAdapter(
            "researcher", capabilities=RuntimeCapability(web_research=9.0),
        ))
        await registry.discover_all()
        await registry.check_health_all()

        best = await registry.select_runtime("code_generation")
        assert best == "coder"

        best = await registry.select_runtime("web_research")
        assert best == "researcher"

    @pytest.mark.asyncio
    async def test_select_runtime_user_preference(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter("preferred"))
        registry.register(MockAdapter("other", capabilities=RuntimeCapability(code_generation=10.0)))
        await registry.discover_all()
        await registry.check_health_all()

        best = await registry.select_runtime(
            "code_generation",
            user_preference="preferred",
        )
        assert best == "preferred"

    @pytest.mark.asyncio
    async def test_select_runtime_cost_ceiling(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter(
            "expensive",
            capabilities=RuntimeCapability(code_generation=10.0, cost_per_1k_tokens=0.1),
        ))
        registry.register(MockAdapter(
            "cheap",
            capabilities=RuntimeCapability(code_generation=5.0, cost_per_1k_tokens=0.001),
        ))
        await registry.discover_all()
        await registry.check_health_all()

        best = await registry.select_runtime("code_generation", cost_ceiling=0.01)
        assert best == "cheap"

    @pytest.mark.asyncio
    async def test_select_runtime_exclude(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter(
            "best", capabilities=RuntimeCapability(code_generation=10.0),
        ))
        registry.register(MockAdapter(
            "second", capabilities=RuntimeCapability(code_generation=5.0),
        ))
        await registry.discover_all()
        await registry.check_health_all()

        best = await registry.select_runtime("code_generation", exclude=["best"])
        assert best == "second"

    @pytest.mark.asyncio
    async def test_select_runtime_no_available_raises(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter("offline", health=RuntimeStatus.OFFLINE))
        await registry.discover_all()
        await registry.check_health_all()

        with pytest.raises(NoRuntimeAvailableError):
            await registry.select_runtime("code_generation")

    @pytest.mark.asyncio
    async def test_select_runtime_fallback_ollama(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter("ollama", health=RuntimeStatus.ONLINE))
        registry.register(MockAdapter("other", health=RuntimeStatus.OFFLINE))
        await registry.discover_all()
        await registry.check_health_all()

        # "other" is offline, ollama should be fallback
        best = await registry.select_runtime("code_generation", exclude=[])
        # ollama has 0 code_generation by default but is online
        # select_runtime should pick ollama as it's the only one online
        assert best == "ollama"

    @pytest.mark.asyncio
    async def test_get_capabilities_summary(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter(
            "test_rt",
            capabilities=RuntimeCapability(code_generation=9.0, simple_chat=7.0),
        ))
        await registry.discover_all()
        await registry.check_health_all()

        summary = await registry.get_capabilities_summary()
        assert "test_rt" in summary
        assert "code_generation=9.0" in summary

    def test_to_dict(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter("rt1"))
        d = registry.to_dict()
        assert d["total_count"] == 1
        assert len(d["runtimes"]) == 1
        assert d["runtimes"][0]["runtime_id"] == "rt1"

    @pytest.mark.asyncio
    async def test_online_ids(self):
        registry = RuntimeRegistry()
        registry.register(MockAdapter("on", health=RuntimeStatus.ONLINE))
        registry.register(MockAdapter("off", health=RuntimeStatus.OFFLINE))
        await registry.discover_all()
        await registry.check_health_all()
        assert "on" in registry.online_ids
        assert "off" not in registry.online_ids


# ── SessionManager tests ──────────────────────────────────────

class TestSessionManager:
    def test_create_session(self):
        mgr = SessionManager()
        session = mgr.create("s1", "rt1", "fix the bug")
        assert session.session_id == "s1"
        assert session.runtime_id == "rt1"
        assert mgr.active_count == 1

    def test_get_session(self):
        mgr = SessionManager()
        mgr.create("s1", "rt1", "task")
        assert mgr.get("s1") is not None
        assert mgr.get("nonexistent") is None

    def test_remove_session(self):
        mgr = SessionManager()
        mgr.create("s1", "rt1", "task")
        mgr.remove("s1")
        assert mgr.active_count == 0

    def test_active_for_runtime(self):
        mgr = SessionManager()
        mgr.create("s1", "rt1", "task1")
        mgr.create("s2", "rt1", "task2")
        mgr.create("s3", "rt2", "task3")
        assert mgr.active_for_runtime("rt1") == 2
        assert mgr.active_for_runtime("rt2") == 1

    def test_session_elapsed(self):
        mgr = SessionManager()
        session = mgr.create("s1", "rt1", "task")
        assert session.elapsed_ms >= 0

    def test_session_timeout(self):
        mgr = SessionManager()
        session = mgr.create("s1", "rt1", "task", timeout=0.001)
        # Force elapsed time by backdating start_time
        session.start_time = session.start_time - 1.0
        assert session.is_timed_out is True

    @pytest.mark.asyncio
    async def test_cancel_session(self):
        mgr = SessionManager()
        session = mgr.create("s1", "rt1", "task")
        # No process attached, cancel should still mark as cancelled
        result = await mgr.cancel("s1")
        assert result is True
        assert session.cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        mgr = SessionManager()
        result = await mgr.cancel("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_timed_out(self):
        mgr = SessionManager()
        s1 = mgr.create("s1", "rt1", "task", timeout=0.001)
        s1.start_time = s1.start_time - 1.0  # backdate to force timeout
        mgr.create("s2", "rt1", "task", timeout=9999.0)
        cancelled = await mgr.cleanup_timed_out()
        assert "s1" in cancelled
        assert "s2" not in cancelled

    def test_to_dict(self):
        mgr = SessionManager()
        mgr.create("s1", "rt1", "task")
        d = mgr.to_dict()
        assert d["active_sessions"] == 1
        assert len(d["sessions"]) == 1


# ── CapabilityMatrix tests ────────────────────────────────────

class TestCapabilityMatrix:
    def test_task_type_for_all_intents(self):
        """Every IntentType should have a mapping."""
        for intent in IntentType:
            result = task_type_for_intent(intent)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_coding_maps_to_code_generation(self):
        assert task_type_for_intent(IntentType.CODING) == "code_generation"

    def test_search_maps_to_web_research(self):
        assert task_type_for_intent(IntentType.SEARCH) == "web_research"

    def test_composite_score_primary_only(self):
        """Intent with no secondary tasks uses primary score only."""
        caps = {"simple_chat": 8.0}
        score = composite_score(caps, IntentType.SIMPLE)
        assert score == 8.0

    def test_composite_score_with_secondary(self):
        """Intent with secondary tasks blends primary + secondary."""
        caps = {
            "code_generation": 10.0,
            "code_editing": 8.0,
            "file_operations": 6.0,
        }
        score = composite_score(caps, IntentType.CODING)
        # primary: 10.0 * 0.65 = 6.5
        # secondary avg: (8.0 + 6.0) / 2 = 7.0 * 0.35 = 2.45
        # total: 8.95
        assert abs(score - 8.95) < 0.01

    def test_rank_runtimes(self):
        runtimes = {
            "best": {"code_generation": 10.0, "code_editing": 9.0, "file_operations": 8.0},
            "mid": {"code_generation": 5.0, "code_editing": 5.0, "file_operations": 5.0},
            "worst": {"code_generation": 1.0, "code_editing": 1.0, "file_operations": 1.0},
        }
        ranked = rank_runtimes(runtimes, IntentType.CODING)
        assert ranked[0][0] == "best"
        assert ranked[-1][0] == "worst"

    def test_rank_runtimes_cost_ceiling(self):
        runtimes = {
            "expensive": {"code_generation": 10.0, "cost_per_1k_tokens": 0.1},
            "cheap": {"code_generation": 5.0, "cost_per_1k_tokens": 0.001},
        }
        ranked = rank_runtimes(runtimes, IntentType.CODING, cost_ceiling=0.01)
        assert len(ranked) == 1
        assert ranked[0][0] == "cheap"


# ── CostEstimator tests ──────────────────────────────────────

class TestCostEstimator:
    def test_estimate_free_runtime(self):
        est = CostEstimator()
        result = est.estimate("ollama", 1000)
        assert result.estimated_cost_usd == 0.0
        assert result.is_free is True

    def test_estimate_paid_runtime(self):
        est = CostEstimator()
        result = est.estimate("claude_code", 10000)
        assert result.estimated_cost_usd > 0
        assert result.is_free is False
        assert result.runtime_id == "claude_code"

    def test_estimate_breakdown(self):
        est = CostEstimator()
        result = est.estimate("claude_code", 10000, input_ratio=0.3)
        assert "input_tokens" in result.breakdown
        assert "output_tokens" in result.breakdown
        assert result.breakdown["input_tokens"] == 3000
        assert result.breakdown["output_tokens"] == 7000

    def test_record_actual(self):
        est = CostEstimator()
        cost = est.record_actual("sess1", "claude_code", 1000, 2000)
        assert cost > 0
        assert est.session_total("sess1") == cost

    def test_session_total_accumulates(self):
        est = CostEstimator()
        est.record_actual("sess1", "claude_code", 1000, 1000)
        est.record_actual("sess1", "claude_code", 1000, 1000)
        total = est.session_total("sess1")
        single = est.record_actual("sess2", "claude_code", 1000, 1000)
        assert total == single * 2

    def test_update_pricing(self):
        est = CostEstimator()
        est.update_pricing("custom", {"input_per_1k": 0.01, "output_per_1k": 0.02})
        result = est.estimate("custom", 10000)
        assert result.estimated_cost_usd > 0

    def test_unknown_runtime_zero_cost(self):
        est = CostEstimator()
        result = est.estimate("unknown_runtime", 10000)
        assert result.estimated_cost_usd == 0.0


# ── Adapter capability declarations ───────────────────────────

class TestAdapterCapabilities:
    """Verify all adapters declare sensible capabilities."""

    @pytest.mark.asyncio
    async def test_claude_code_capabilities(self):
        from app.services.runtimes.adapters.claude_code import ClaudeCodeAdapter
        adapter = ClaudeCodeAdapter()
        caps = await adapter.get_capabilities()
        assert caps.complex_reasoning >= 9.0
        assert caps.code_generation >= 9.0
        assert caps.cost_per_1k_tokens > 0
        assert adapter.runtime_id == "claude_code"

    @pytest.mark.asyncio
    async def test_codex_capabilities(self):
        from app.services.runtimes.adapters.codex import CodexAdapter
        adapter = CodexAdapter()
        caps = await adapter.get_capabilities()
        assert caps.bulk_operations >= 9.0
        assert caps.code_generation >= 8.0
        assert adapter.runtime_id == "codex"

    @pytest.mark.asyncio
    async def test_gemini_cli_capabilities(self):
        from app.services.runtimes.adapters.gemini_cli import GeminiCLIAdapter
        adapter = GeminiCLIAdapter()
        caps = await adapter.get_capabilities()
        assert caps.web_research >= 9.0
        assert caps.cost_per_1k_tokens < 0.01  # very cheap
        assert adapter.runtime_id == "gemini_cli"

    @pytest.mark.asyncio
    async def test_grok_cli_capabilities(self):
        from app.services.runtimes.adapters.grok_cli import GrokCLIAdapter
        adapter = GrokCLIAdapter()
        caps = await adapter.get_capabilities()
        assert caps.web_research >= 8.0
        assert adapter.runtime_id == "grok_cli"

    @pytest.mark.asyncio
    async def test_ollama_capabilities(self):
        from app.services.runtimes.adapters.ollama_adapter import OllamaRuntimeAdapter
        with patch("app.services.runtimes.adapters.ollama_adapter.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ollama_base_url="http://localhost:11434")
            adapter = OllamaRuntimeAdapter()
        caps = await adapter.get_capabilities()
        assert caps.cost_per_1k_tokens == 0.0  # free
        assert caps.simple_chat >= 6.0
        assert adapter.runtime_id == "ollama"

    @pytest.mark.asyncio
    async def test_mcp_bridge_capabilities(self):
        from app.services.runtimes.adapters.mcp_bridge import MCPBridgeAdapter
        adapter = MCPBridgeAdapter("test_server", url="http://localhost:9999")
        caps = await adapter.get_capabilities()
        assert caps.file_operations >= 3.0
        assert adapter.runtime_id == "mcp_test_server"

    @pytest.mark.asyncio
    async def test_mcp_bridge_custom_capabilities(self):
        from app.services.runtimes.adapters.mcp_bridge import MCPBridgeAdapter
        custom = RuntimeCapability(file_operations=10.0)
        adapter = MCPBridgeAdapter("custom", url="http://localhost:9999", capabilities=custom)
        caps = await adapter.get_capabilities()
        assert caps.file_operations == 10.0


# ── ModelRouter.route_runtime() integration ───────────────────

class TestModelRouterRuntimeIntegration:
    """Test the V2 route_runtime() method on ModelRouter."""

    @pytest.mark.asyncio
    async def test_route_runtime_returns_none_without_registry(self):
        from app.services.model_router import ModelRouter
        router = ModelRouter(registry=MagicMock())  # no runtime_registry
        qu = MagicMock()
        qu.intent = IntentType.CODING
        result = await router.route_runtime(qu)
        assert result is None

    @pytest.mark.asyncio
    async def test_route_runtime_selects_best(self):
        from app.services.model_router import ModelRouter

        registry = RuntimeRegistry()
        registry.register(MockAdapter(
            "coder", capabilities=RuntimeCapability(code_generation=9.0),
        ))
        registry.register(MockAdapter(
            "chatter", capabilities=RuntimeCapability(simple_chat=9.0),
        ))
        await registry.discover_all()
        await registry.check_health_all()

        router = ModelRouter(
            registry=MagicMock(),
            runtime_registry=registry,
        )
        qu = MagicMock()
        qu.intent = IntentType.CODING

        result = await router.route_runtime(qu)
        assert result is not None
        assert result.runtime_id == "coder"
        assert result.capability_score == 9.0

    @pytest.mark.asyncio
    async def test_route_runtime_with_user_preference(self):
        from app.services.model_router import ModelRouter

        registry = RuntimeRegistry()
        registry.register(MockAdapter(
            "preferred", capabilities=RuntimeCapability(code_generation=1.0),
        ))
        registry.register(MockAdapter(
            "better", capabilities=RuntimeCapability(code_generation=10.0),
        ))
        await registry.discover_all()
        await registry.check_health_all()

        router = ModelRouter(registry=MagicMock(), runtime_registry=registry)
        qu = MagicMock()
        qu.intent = IntentType.CODING

        result = await router.route_runtime(qu, user_preferred_runtime="preferred")
        assert result is not None
        assert result.runtime_id == "preferred"

    @pytest.mark.asyncio
    async def test_route_runtime_fallback_populated(self):
        from app.services.model_router import ModelRouter

        registry = RuntimeRegistry()
        registry.register(MockAdapter(
            "primary", capabilities=RuntimeCapability(code_generation=10.0),
        ))
        registry.register(MockAdapter(
            "fallback", capabilities=RuntimeCapability(code_generation=5.0),
        ))
        await registry.discover_all()
        await registry.check_health_all()

        router = ModelRouter(registry=MagicMock(), runtime_registry=registry)
        qu = MagicMock()
        qu.intent = IntentType.CODING

        result = await router.route_runtime(qu)
        assert result is not None
        assert result.runtime_id == "primary"
        assert result.fallback_runtime_id == "fallback"


# ── Events integration ────────────────────────────────────────

class TestEventsIntegration:
    def test_get_runtime_registry_singleton(self):
        from app.core import events
        # Reset singleton for test isolation
        events._runtime_registry = None
        registry1 = events.get_runtime_registry()
        registry2 = events.get_runtime_registry()
        assert registry1 is registry2
        assert len(registry1.registered_ids) == 5  # 5 adapters
        # Cleanup
        events._runtime_registry = None

    def test_get_runtime_registry_has_all_adapters(self):
        from app.core import events
        events._runtime_registry = None
        registry = events.get_runtime_registry()
        ids = registry.registered_ids
        assert "claude_code" in ids
        assert "codex" in ids
        assert "gemini_cli" in ids
        assert "grok_cli" in ids
        assert "ollama" in ids
        events._runtime_registry = None
