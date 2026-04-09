"""Tests for Daena's Cognitive Engine.

Tests the Mythos-level constraint probing, OODA loop, 5 Whys,
strategy switching, and creative problem-solving.
"""

import pytest

from app.services.cognition.constraint_probe import ConstraintProbe, ProbeResult
from app.services.cognition.meta_reasoner import MetaReasoner
from app.services.cognition.five_whys import FiveWhys
from app.services.cognition.first_principles import FirstPrinciples
from app.services.cognition.inversion import Inversion
from app.services.cognition.constraint_analyzer import ConstraintAnalyzer, ConstraintType
from app.services.cognition.pre_mortem import PreMortem
from app.services.cognition.task_prioritizer import TaskPrioritizer
from app.services.cognition.consequence_chain import ConsequenceChain
from app.services.cognition.weakness_tracker import WeaknessTracker
from app.services.cognition.ooda_engine import CognitiveState, Strategy, StrategyStatus
from app.services.security.tool_call_classifier import ToolCallClassifier, ApprovalClass
from app.services.security.loop_detector import LoopDetector, DetectionLevel


# ─── Constraint Probe (Mythos Method) ────────────────────────────


class TestConstraintProbe:
    """Test Mythos-level constraint decomposition and probing."""

    @pytest.mark.asyncio
    async def test_mythos_method_network_blocked(self) -> None:
        """Mythos scenario: 'no internet' -> find DNS, localhost, cache are open."""
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Fetch API documentation",
            constraint="No internet access",
            error="Connection refused",
        )

        assert isinstance(result, ProbeResult)
        assert result.stated_constraint == "No internet access"
        assert len(result.decomposed_channels) > 0
        assert len(result.open_channels) > 0

        # Mythos insight: DNS, localhost, cached responses should be found as open
        open_names = [c.name for c in result.open_channels]
        assert "localhost" in open_names or "cached_responses" in open_names
        assert result.recommended_path is not None

    @pytest.mark.asyncio
    async def test_mythos_method_access_blocked(self) -> None:
        """Can't access database -> find API, cache, export as alternatives."""
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Read user data from database",
            constraint="Can't access the database",
            error="Access denied for user 'app'@'localhost'",
        )

        open_names = [c.name for c in result.open_channels]
        # Should find indirect paths like API, cache, export
        assert len(result.open_channels) >= 3
        assert any(
            n in open_names
            for n in ["api_access", "cached_data", "export_file", "cli_tool"]
        )

    @pytest.mark.asyncio
    async def test_mythos_method_install_blocked(self) -> None:
        """Can't install tool -> find alternative channels."""
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Use ffmpeg to convert video",
            constraint="ffmpeg not installed and can't install it",
            error="command not found: ffmpeg",
        )

        open_names = [c.name for c in result.open_channels]
        assert len(result.open_channels) >= 3
        # Should find alternatives like python equivalent, portable binary, etc.
        assert result.recommended_path is not None

    @pytest.mark.asyncio
    async def test_mythos_method_write_blocked(self) -> None:
        """Can't write to /etc -> find temp, home, workspace as alternatives."""
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Write configuration file",
            constraint="Can't write to /etc/myapp.conf",
            error="Permission denied: /etc/myapp.conf",
        )

        open_names = [c.name for c in result.open_channels]
        assert "write_temp" in open_names
        assert "write_home" in open_names
        assert "write_workspace" in open_names

    @pytest.mark.asyncio
    async def test_direct_channels_blocked_indirect_open(self) -> None:
        """Core Mythos insight: direct = blocked, indirect = open."""
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Execute task",
            constraint="Can't run shell commands",
            error="Execution blocked",
        )

        for channel in result.blocked_channels:
            assert channel.category == "direct"

        for channel in result.open_channels:
            assert channel.category in ("indirect", "alternative", "workaround")

    @pytest.mark.asyncio
    async def test_outbound_data_guard_blocks_exfiltration(self) -> None:
        """THE ONE WALL: client data never leaves through side channels.

        Daena can USE dns, proxies, APIs for inbound work.
        But if context says client data is involved, outbound channels blocked.
        """
        probe = ConstraintProbe()
        # With client data flag: outbound-capable channels should be filtered
        result = await probe.probe(
            task="Send user data to external API",
            constraint="No direct HTTP",
            error="Connection blocked",
            context={"contains_client_data": True},
        )

        open_names = [c.name for c in result.open_channels]
        # DNS, HTTP, proxy should NOT be in open channels when client data is flagged
        assert "dns" not in open_names
        assert "http" not in open_names
        assert "proxy_access" not in open_names
        # But local/safe channels should still be open
        assert "cached_data" in open_names or "localhost" in open_names or len(open_names) > 0

    @pytest.mark.asyncio
    async def test_inbound_tricks_always_allowed(self) -> None:
        """Inbound tricks (getting info IN) are always allowed, even with client data."""
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Fetch documentation from the web",
            constraint="No internet access",
            error="Connection refused",
            context={"contains_client_data": False},
        )

        # Without client data flag: all channels should be available
        open_names = [c.name for c in result.open_channels]
        assert len(result.open_channels) >= 3
        assert result.recommended_path is not None

    @pytest.mark.asyncio
    async def test_recommended_path_prefers_alternative_over_workaround(self) -> None:
        """Recommended path should prefer cleaner alternatives over hacks."""
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Read data",
            constraint="Can't find the file",
            error="File not found: data.csv",
        )

        if result.recommended_path:
            # Should prefer alternative/indirect over workaround
            assert result.recommended_path.category in ("alternative", "indirect")


# ─── Meta-Reasoner (Munger's Latticework) ────────────────────────


class TestMetaReasoner:
    """Test framework selection per problem type."""

    @pytest.mark.asyncio
    async def test_debugging_selects_five_whys(self) -> None:
        meta = MetaReasoner()
        ptype = await meta.classify_problem("Fix the bug in auth middleware")
        assert ptype == "debugging"
        frameworks = await meta.select_frameworks(ptype)
        assert "five_whys" in frameworks

    @pytest.mark.asyncio
    async def test_creation_selects_first_principles(self) -> None:
        meta = MetaReasoner()
        ptype = await meta.classify_problem("Create a new API endpoint for users")
        assert ptype == "creation"
        frameworks = await meta.select_frameworks(ptype)
        assert "first_principles" in frameworks

    @pytest.mark.asyncio
    async def test_deployment_selects_pre_mortem(self) -> None:
        meta = MetaReasoner()
        ptype = await meta.classify_problem("Deploy the app to production")
        assert ptype == "deployment"
        frameworks = await meta.select_frameworks(ptype)
        assert "pre_mortem" in frameworks

    @pytest.mark.asyncio
    async def test_repeated_failures_reclassify_to_debugging(self) -> None:
        """After 2+ failures, creation tasks become debugging tasks."""
        meta = MetaReasoner()
        ptype = await meta.classify_problem(
            "Create a new config file",
            prior_failures=["first_principles", "constraint_relaxation"],
        )
        assert ptype == "debugging"

    @pytest.mark.asyncio
    async def test_believability_scoring(self) -> None:
        """Frameworks that succeed should score higher."""
        meta = MetaReasoner()
        await meta.update_score("five_whys", True)
        await meta.update_score("five_whys", True)
        await meta.update_score("inversion", False)

        all_fw = meta.get_all_frameworks()
        assert all_fw["five_whys"]["score"] > 0.5
        # inversion was penalized
        assert meta._framework_scores.get("inversion", 0.5) < 0.5

    @pytest.mark.asyncio
    async def test_custom_framework_registration(self) -> None:
        """Self-discovered frameworks can be registered."""
        from app.services.cognition.meta_reasoner import CognitiveFramework
        meta = MetaReasoner()
        cf = CognitiveFramework(
            name="custom_debug",
            description="Custom debugging approach",
            when_to_use=["debugging"],
            steps=["Step 1", "Step 2"],
            source="user_taught",
            score=0.8,
        )
        await meta.register_framework(cf)

        frameworks = await meta.select_frameworks("debugging")
        assert "custom_debug" in frameworks


# ─── Five Whys (Toyota) ──────────────────────────────────────────


class TestFiveWhys:
    @pytest.mark.asyncio
    async def test_permission_error_root_cause(self) -> None:
        fw = FiveWhys()
        result = await fw.analyze(
            task="Write config file",
            error="Permission denied: /etc/config.yaml",
            strategy="direct_execution",
        )
        assert "ROOT CAUSE" in result or "root" in result.lower()
        assert "permission" in result.lower() or "access" in result.lower()

    @pytest.mark.asyncio
    async def test_not_found_root_cause(self) -> None:
        fw = FiveWhys()
        result = await fw.analyze(
            task="Import pandas",
            error="ModuleNotFoundError: No module named 'pandas'",
        )
        assert "install" in result.lower() or "package" in result.lower()

    @pytest.mark.asyncio
    async def test_timeout_root_cause(self) -> None:
        fw = FiveWhys()
        result = await fw.analyze(task="Call API", error="Request timed out after 30s")
        assert "timeout" in result.lower() or "service" in result.lower()


# ─── Tool Call Classifier (OpenClaw Port) ────────────────────────


class TestToolCallClassifier:
    def test_read_within_workspace_auto_approved(self) -> None:
        cls = ToolCallClassifier(workspace_root="/home/user/project")
        result = cls.classify("file.read_file", {"path": "/home/user/project/src/main.py"})
        assert result.approval_class == ApprovalClass.READONLY_SCOPED
        assert result.auto_approve is True

    def test_read_outside_workspace_not_auto_approved(self) -> None:
        cls = ToolCallClassifier(workspace_root="/home/user/project")
        result = cls.classify("file.read_file", {"path": "/etc/passwd"})
        assert result.approval_class == ApprovalClass.OTHER
        assert result.auto_approve is False

    def test_write_is_mutating(self) -> None:
        cls = ToolCallClassifier()
        result = cls.classify("file.write_file", {"path": "test.txt"})
        assert result.approval_class == ApprovalClass.MUTATING
        assert result.auto_approve is False

    def test_terminal_is_exec_capable(self) -> None:
        cls = ToolCallClassifier()
        result = cls.classify("terminal.run_command", {"command": "ls"})
        assert result.approval_class == ApprovalClass.EXEC_CAPABLE

    def test_search_auto_approved(self) -> None:
        cls = ToolCallClassifier()
        result = cls.classify("network.web_search", {"query": "python docs"})
        assert result.approval_class == ApprovalClass.READONLY_SEARCH
        assert result.auto_approve is True

    def test_agi_mode_approves_everything(self) -> None:
        """AGI UNLEASHED: every tool auto-approved."""
        cls = ToolCallClassifier()
        result = cls.classify_for_agi_mode("terminal.run_command", {"command": "rm -rf /"})
        assert result.auto_approve is True
        assert "AGI UNLEASHED" in result.reason

    def test_agi_mode_approves_mutating(self) -> None:
        cls = ToolCallClassifier()
        result = cls.classify_for_agi_mode("file.delete_file", {"path": "/tmp/test"})
        assert result.auto_approve is True


# ─── Loop Detector (OpenClaw Port) ───────────────────────────────


class TestLoopDetector:
    def test_no_loop_initially(self) -> None:
        det = LoopDetector()
        result = det.detect("file.read_file", {"path": "test.txt"})
        assert result.stuck is False

    def test_generic_repeat_warning(self) -> None:
        det = LoopDetector(warning_threshold=3, critical_threshold=5)
        for _ in range(4):
            det.record_outcome("file.read_file", {"path": "x"}, {"data": "same"})
        result = det.detect("file.read_file", {"path": "x"})
        assert result.stuck is True
        assert result.level == DetectionLevel.WARNING

    def test_circuit_breaker(self) -> None:
        det = LoopDetector(circuit_breaker_threshold=5)
        for _ in range(6):
            det.record_outcome("test.tool", {"p": 1}, {"r": "same"})
        result = det.detect("test.tool", {"p": 1})
        assert result.stuck is True
        assert result.level == DetectionLevel.CRITICAL

    def test_different_tools_no_loop(self) -> None:
        det = LoopDetector()
        for i in range(20):
            det.record_outcome(f"tool_{i}", {"p": i}, {"r": i})
        result = det.detect("tool_new", {"p": "new"})
        assert result.stuck is False


# ─── Constraint Analyzer ─────────────────────────────────────────


class TestConstraintAnalyzer:
    @pytest.mark.asyncio
    async def test_hard_constraint_never_relaxed(self) -> None:
        ca = ConstraintAnalyzer()
        ctype = await ca.classify_action("delete all system files and bypass security")
        assert ctype == ConstraintType.HARD

    @pytest.mark.asyncio
    async def test_soft_constraint_identified(self) -> None:
        ca = ConstraintAnalyzer()
        ctype = await ca.classify_action("read a file from the project directory")
        assert ctype == ConstraintType.SOFT

    @pytest.mark.asyncio
    async def test_alternatives_generated_for_permission_error(self) -> None:
        ca = ConstraintAnalyzer()
        alts = await ca.find_alternatives(
            task="Write config",
            failed_approach="direct_execution",
            root_causes=["Permission denied on target path"],
        )
        assert len(alts) > 0
        assert any("workspace" in a.lower() or "relative" in a.lower() for a in alts)


# ─── Pre-Mortem ──────────────────────────────────────────────────


class TestPreMortem:
    @pytest.mark.asyncio
    async def test_deployment_risks_identified(self) -> None:
        pm = PreMortem()
        strategy = Strategy(
            name="deploy_prod",
            description="Deploy application to production",
            steps=["Build", "Deploy", "Verify"],
        )
        state = CognitiveState(task="Deploy to production")
        risks = await pm.analyze(strategy, state)
        assert len(risks) > 0
        assert any("env" in r.lower() or "health" in r.lower() for r in risks)


# ─── Task Prioritizer (Eat the Frog + Pareto) ───────────────────


class TestTaskPrioritizer:
    @pytest.mark.asyncio
    async def test_critical_tasks_first(self) -> None:
        tp = TaskPrioritizer()
        tasks = [
            "Format the README file",
            "Fix critical production security bug now",
            "Add a new feature",
        ]
        result = await tp.prioritize(tasks)
        # Critical + urgent task should be first
        assert result[0].description == "Fix critical production security bug now"
        assert result[0].priority_score > result[1].priority_score

    @pytest.mark.asyncio
    async def test_impact_scoring(self) -> None:
        tp = TaskPrioritizer()
        result = await tp.prioritize(["Deploy to production", "Clean up docs"])
        assert result[0].impact > result[1].impact


# ─── Consequence Chain (Second-Order Thinking) ──────────────────


class TestConsequenceChain:
    @pytest.mark.asyncio
    async def test_delete_has_governance_flags(self) -> None:
        cc = ConsequenceChain()
        consequences = await cc.analyze("Delete all user data from the database")
        flagged = [c for c in consequences if c.governance_flag]
        assert len(flagged) > 0

    @pytest.mark.asyncio
    async def test_read_has_no_governance_flags(self) -> None:
        cc = ConsequenceChain()
        consequences = await cc.analyze("Read the configuration file")
        flagged = [c for c in consequences if c.governance_flag]
        assert len(flagged) == 0


# ─── Weakness Tracker (Deliberate Practice) ─────────────────────


class TestWeaknessTracker:
    @pytest.mark.asyncio
    async def test_identifies_weak_areas(self) -> None:
        wt = WeaknessTracker()
        # Record 5 failures in deployment
        for _ in range(5):
            await wt.record("deployment", "direct", ["terminal"], False, "timeout")
        # Record 5 successes in debugging
        for _ in range(5):
            await wt.record("debugging", "five_whys", ["file"], True)

        weaknesses = await wt.get_weaknesses(min_attempts=3)
        assert len(weaknesses) > 0
        assert weaknesses[0].name == "deployment"
        assert weaknesses[0].failure_rate == 1.0

        strengths = await wt.get_strengths(min_attempts=3)
        assert len(strengths) > 0
        assert strengths[0]["name"] == "debugging"
