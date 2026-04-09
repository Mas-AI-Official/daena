"""Tests for MissionIntelligence -- the autonomous mission brain."""

from __future__ import annotations

import json
import os
import pytest
import tempfile
from unittest.mock import patch

from app.services.security.mission_intelligence import (
    AttractionSimulator,
    AttackPath,
    ChainFollower,
    CreativePathGenerator,
    EdgeType,
    EngagementController,
    EngagementLevel,
    GoalBackwardPlanner,
    GraphEdge,
    GraphNode,
    MissionController,
    MissionGraph,
    NodeType,
    OpSecShield,
    PlanStep,
    ProximityMapper,
    TraceManager,
)


# ---------------------------------------------------------------------------
# MissionGraph tests
# ---------------------------------------------------------------------------

class TestMissionGraph:
    """Test the living knowledge graph."""

    def test_create_graph(self):
        graph = MissionGraph()
        assert graph.mission_id
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_add_node(self):
        graph = MissionGraph()
        node = GraphNode(
            node_type=NodeType.ENTITY,
            label="target.com",
            data={"domain": "target.com"},
        )
        result = graph.add_node(node)
        assert result.id == node.id
        assert len(graph.nodes) == 1
        assert graph.nodes[node.id].label == "target.com"

    def test_add_edge(self):
        graph = MissionGraph()
        n1 = GraphNode(node_type=NodeType.ENTITY, label="A")
        n2 = GraphNode(node_type=NodeType.ENDPOINT, label="B")
        graph.add_node(n1)
        graph.add_node(n2)

        edge = GraphEdge(
            source_id=n1.id,
            target_id=n2.id,
            edge_type=EdgeType.LEADS_TO,
        )
        graph.add_edge(edge)
        assert len(graph.edges) == 1
        assert n2.id in graph._adjacency[n1.id]
        assert n1.id in graph._reverse_adjacency[n2.id]

    def test_mark_dead_end(self):
        graph = MissionGraph()
        node = GraphNode(node_type=NodeType.ENDPOINT, label="blocked.com")
        graph.add_node(node)

        graph.mark_dead_end(node.id, "403 Forbidden")
        assert "dead_end" in graph.nodes[node.id].tags
        assert graph.nodes[node.id].data["dead_end_reason"] == "403 Forbidden"
        # Dead end node should also be added
        assert len(graph.nodes) == 2

    def test_find_unexplored(self):
        graph = MissionGraph()
        n1 = GraphNode(node_type=NodeType.ENTITY, label="explored", explored=True)
        n2 = GraphNode(node_type=NodeType.ENTITY, label="unexplored", explored=False)
        n3 = GraphNode(node_type=NodeType.DEAD_END, label="dead end")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)

        unexplored = graph.find_unexplored()
        assert len(unexplored) == 1
        assert unexplored[0].label == "unexplored"

    def test_find_unexplored_sorts_by_depth(self):
        graph = MissionGraph()
        n1 = GraphNode(node_type=NodeType.ENTITY, label="deep", depth=5)
        n2 = GraphNode(node_type=NodeType.ENTITY, label="shallow", depth=1)
        n3 = GraphNode(node_type=NodeType.ENTITY, label="medium", depth=3)
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)

        unexplored = graph.find_unexplored()
        assert unexplored[0].label == "shallow"
        assert unexplored[1].label == "medium"
        assert unexplored[2].label == "deep"

    def test_get_chain(self):
        graph = MissionGraph()
        n1 = GraphNode(id="a", node_type=NodeType.ENTITY, label="start")
        n2 = GraphNode(id="b", node_type=NodeType.ENDPOINT, label="middle")
        n3 = GraphNode(id="c", node_type=NodeType.GOAL, label="goal")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)
        graph.add_edge(GraphEdge(source_id="a", target_id="b", edge_type=EdgeType.LEADS_TO))
        graph.add_edge(GraphEdge(source_id="b", target_id="c", edge_type=EdgeType.LEADS_TO))

        chain = graph.get_chain("a", "c")
        assert len(chain) == 3
        assert chain[0].label == "start"
        assert chain[2].label == "goal"

    def test_get_chain_no_path(self):
        graph = MissionGraph()
        n1 = GraphNode(id="a", node_type=NodeType.ENTITY, label="isolated1")
        n2 = GraphNode(id="b", node_type=NodeType.ENTITY, label="isolated2")
        graph.add_node(n1)
        graph.add_node(n2)

        chain = graph.get_chain("a", "b")
        assert len(chain) == 0

    def test_find_paths_to_goal(self):
        graph = MissionGraph()
        n1 = GraphNode(id="entry", node_type=NodeType.ENTITY, label="entry")
        n2 = GraphNode(id="mid", node_type=NodeType.ENDPOINT, label="mid")
        n3 = GraphNode(id="goal", node_type=NodeType.GOAL, label="goal")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)
        graph.add_edge(GraphEdge(source_id="entry", target_id="mid", edge_type=EdgeType.LEADS_TO))
        graph.add_edge(GraphEdge(source_id="mid", target_id="goal", edge_type=EdgeType.LEADS_TO))

        paths = graph.find_paths_to_goal("goal")
        assert len(paths) >= 1
        assert paths[0][0] == "entry"
        assert paths[0][-1] == "goal"

    def test_get_statistics(self):
        graph = MissionGraph()
        graph.add_node(GraphNode(node_type=NodeType.ENTITY, label="A"))
        graph.add_node(GraphNode(node_type=NodeType.ENDPOINT, label="B"))
        graph.add_node(GraphNode(node_type=NodeType.ENTITY, label="C", explored=True))

        stats = graph.get_statistics()
        assert stats["total_nodes"] == 3
        assert stats["explored_nodes"] == 1
        assert stats["node_types"]["entity"] == 2
        assert stats["node_types"]["endpoint"] == 1

    def test_export_visual(self):
        graph = MissionGraph()
        n1 = GraphNode(node_type=NodeType.ENTITY, label="A")
        n2 = GraphNode(node_type=NodeType.ENDPOINT, label="B")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge(GraphEdge(source_id=n1.id, target_id=n2.id, edge_type=EdgeType.LEADS_TO))

        visual = graph.export_visual()
        assert len(visual["nodes"]) == 2
        assert len(visual["edges"]) == 1
        assert "statistics" in visual

    def test_save_and_load(self, tmp_path):
        """Test graph persistence across sessions."""
        with patch.dict(os.environ, {"DAENA_VAR": str(tmp_path)}):
            # Create and save
            graph = MissionGraph(mission_id="test_persist")
            n1 = GraphNode(node_type=NodeType.ENTITY, label="survivor")
            n2 = GraphNode(node_type=NodeType.GOAL, label="the goal")
            graph.add_node(n1)
            graph.add_node(n2)
            graph.add_edge(GraphEdge(
                source_id=n1.id,
                target_id=n2.id,
                edge_type=EdgeType.LEADS_TO,
            ))
            filepath = graph.save()
            assert os.path.exists(filepath)

            # Load and verify
            loaded = MissionGraph.load("test_persist")
            assert len(loaded.nodes) == 2
            assert len(loaded.edges) == 1
            assert any(n.label == "survivor" for n in loaded.nodes.values())
            assert any(n.label == "the goal" for n in loaded.nodes.values())


# ---------------------------------------------------------------------------
# GoalBackwardPlanner tests
# ---------------------------------------------------------------------------

class TestGoalBackwardPlanner:
    """Test goal-backward planning."""

    @pytest.mark.asyncio
    async def test_plan_from_goal_generates_paths(self):
        graph = MissionGraph()
        planner = GoalBackwardPlanner(graph)

        with patch("app.services.security.mission_intelligence.GoalBackwardPlanner._generate_backward_chain") as mock:
            mock.return_value = [
                PlanStep(description="Step 1", module="osint_engine", method="people_intelligence"),
                PlanStep(description="Step 2", module="cognitive_scan_engine", method="full_scan"),
            ]

            paths = await planner.plan_from_goal(
                goal="Prove access to database",
                target="example.com",
                engagement_level=EngagementLevel.PENTEST,
            )

            # Should generate paths for technical, social, supply_chain
            assert len(paths) == 3
            assert all(isinstance(p, AttackPath) for p in paths)

    @pytest.mark.asyncio
    async def test_red_team_adds_insider_physical_paths(self):
        graph = MissionGraph()
        planner = GoalBackwardPlanner(graph)

        paths = await planner.plan_from_goal(
            goal="Transfer $0.01",
            target="corp.com",
            engagement_level=EngagementLevel.RED_TEAM,
        )

        path_types = {p.path_type for p in paths}
        assert "technical" in path_types
        assert "social" in path_types
        assert "supply_chain" in path_types
        assert "insider" in path_types
        assert "physical" in path_types

    @pytest.mark.asyncio
    async def test_adversary_level_adds_cleanup(self):
        graph = MissionGraph()
        planner = GoalBackwardPlanner(graph)

        paths = await planner.plan_from_goal(
            goal="Exfiltrate sample data",
            target="target.io",
            engagement_level=EngagementLevel.ADVERSARY,
        )

        # At least one path should have cleanup step
        for path in paths:
            step_descriptions = [s.description for s in path.steps]
            has_cleanup = any("clean" in d.lower() or "trace" in d.lower() for d in step_descriptions)
            has_opsec = any("opsec" in d.lower() for d in step_descriptions)
            if has_cleanup or has_opsec:
                break
        else:
            pytest.fail("ADVERSARY level should include cleanup/opsec steps")

    def test_detection_risk_calculation(self):
        graph = MissionGraph()
        planner = GoalBackwardPlanner(graph)

        steps = [
            PlanStep(detection_risk="low"),
            PlanStep(detection_risk="low"),
            PlanStep(detection_risk="low"),
        ]
        risk = planner._calculate_detection_risk(steps)
        assert 0.0 < risk < 1.0

        # Higher risk steps = higher cumulative risk
        high_steps = [
            PlanStep(detection_risk="high"),
            PlanStep(detection_risk="high"),
        ]
        high_risk = planner._calculate_detection_risk(high_steps)
        assert high_risk > risk

    def test_feasibility_estimation(self):
        graph = MissionGraph()
        planner = GoalBackwardPlanner(graph)

        easy_steps = [PlanStep(detection_risk="none")]
        hard_steps = [PlanStep(detection_risk="critical")]

        easy_feasibility = planner._estimate_feasibility(easy_steps)
        hard_feasibility = planner._estimate_feasibility(hard_steps)

        assert easy_feasibility > hard_feasibility
        assert 0.0 <= easy_feasibility <= 1.0
        assert 0.0 <= hard_feasibility <= 1.0


# ---------------------------------------------------------------------------
# ChainFollower tests
# ---------------------------------------------------------------------------

class TestChainFollower:
    """Test autonomous chain following."""

    @pytest.mark.asyncio
    async def test_forward_follow_entity(self):
        graph = MissionGraph()
        entity = GraphNode(node_type=NodeType.ENTITY, label="target.com")
        goal = GraphNode(node_type=NodeType.GOAL, label="the goal")
        graph.add_node(entity)
        graph.add_node(goal)

        follower = ChainFollower(graph)
        discovered = await follower.follow(entity.id, goal.id, direction="forward")

        # Should discover endpoints and personas
        assert len(discovered) > 0
        assert entity.explored  # Should be marked explored

    @pytest.mark.asyncio
    async def test_inversion_follow(self):
        graph = MissionGraph()
        entity = GraphNode(node_type=NodeType.ENTITY, label="hardened-target.com")
        goal = GraphNode(node_type=NodeType.GOAL, label="get access")
        graph.add_node(entity)
        graph.add_node(goal)

        follower = ChainFollower(graph)
        discovered = await follower.follow(entity.id, goal.id, direction="inversion")

        # Should discover inversion technique nodes
        assert len(discovered) > 0
        inversion_nodes = [n for n in discovered if n.node_type == NodeType.TECHNIQUE]
        assert len(inversion_nodes) > 0
        assert "inversion" in inversion_nodes[0].data.get("reasoning", "")

    @pytest.mark.asyncio
    async def test_handle_dead_end_finds_alternative(self):
        graph = MissionGraph()
        goal = GraphNode(id="goal", node_type=NodeType.GOAL, label="goal")
        path_a = GraphNode(id="a", node_type=NodeType.ENDPOINT, label="blocked path", depth=2)
        path_b = GraphNode(id="b", node_type=NodeType.ENDPOINT, label="alternative", depth=2)
        graph.add_node(goal)
        graph.add_node(path_a)
        graph.add_node(path_b)

        follower = ChainFollower(graph)
        next_id = await follower.handle_dead_end("a", "goal", "403 Forbidden")

        # Should find path_b as alternative
        assert next_id == "b"
        assert "dead_end" in graph.nodes["a"].tags

    @pytest.mark.asyncio
    async def test_handle_dead_end_returns_empty_when_truly_stuck(self):
        graph = MissionGraph()
        # All nodes explored and dead-ended -- nowhere left to go
        n1 = GraphNode(id="a", node_type=NodeType.ENDPOINT, label="path a", explored=True)
        n1.tags.append("dead_end")
        n2 = GraphNode(id="b", node_type=NodeType.ENDPOINT, label="path b", explored=True)
        n2.tags.append("dead_end")
        graph.add_node(n1)
        graph.add_node(n2)

        follower = ChainFollower(graph)
        next_id = await follower.handle_dead_end("a", "nonexistent_goal", "completely stuck")
        assert next_id == ""

    def test_statistics(self):
        graph = MissionGraph()
        follower = ChainFollower(graph)
        stats = follower.get_statistics()
        assert stats["total_follows"] == 0
        assert stats["dead_ends"] == 0
        assert stats["pivots"] == 0


# ---------------------------------------------------------------------------
# MissionController tests
# ---------------------------------------------------------------------------

class TestMissionController:
    """Test the autonomous mission brain."""

    @pytest.mark.asyncio
    async def test_start_mission_requires_evilbob(self):
        """Mission requires /3vilbob mode active."""
        controller = MissionController()

        with patch("app.services.security.evilbob_mode.is_active", return_value=False):
            status = await controller.start_mission(
                goal="test goal",
                target="test.com",
            )
            assert status.status == "failed"

    @pytest.mark.asyncio
    async def test_start_mission_creates_paths(self, tmp_path):
        """Successful mission start creates attack paths."""
        controller = MissionController()

        with patch("app.services.security.evilbob_mode.is_active", return_value=True), \
             patch("app.services.security.evilbob_mode.has_capability", return_value=True), \
             patch.dict(os.environ, {"DAENA_VAR": str(tmp_path)}):

            status = await controller.start_mission(
                goal="Prove database access",
                target="example.com",
                engagement_level=EngagementLevel.PENTEST,
            )

            assert status.status == "planned"
            assert status.paths_total >= 3  # At least technical, social, supply_chain
            assert status.nodes_discovered > 0
            assert status.mission_id

    @pytest.mark.asyncio
    async def test_get_paths_summary(self, tmp_path):
        controller = MissionController()

        with patch("app.services.security.evilbob_mode.is_active", return_value=True), \
             patch("app.services.security.evilbob_mode.has_capability", return_value=True), \
             patch.dict(os.environ, {"DAENA_VAR": str(tmp_path)}):

            await controller.start_mission(
                goal="Test",
                target="test.com",
                engagement_level=EngagementLevel.AUDIT,
            )

            summary = controller.get_paths_summary()
            assert len(summary) >= 3
            for path in summary:
                assert "type" in path
                assert "steps" in path
                assert "feasibility" in path
                assert "detection_risk" in path

    @pytest.mark.asyncio
    async def test_get_graph_visual(self, tmp_path):
        controller = MissionController()

        with patch("app.services.security.evilbob_mode.is_active", return_value=True), \
             patch("app.services.security.evilbob_mode.has_capability", return_value=True), \
             patch.dict(os.environ, {"DAENA_VAR": str(tmp_path)}):

            await controller.start_mission(
                goal="Visual test",
                target="vis.com",
            )

            visual = controller.get_graph_visual()
            assert "nodes" in visual
            assert "edges" in visual
            assert "statistics" in visual
            assert len(visual["nodes"]) > 0

    @pytest.mark.asyncio
    async def test_save_and_resume(self, tmp_path):
        """Test mission persistence -- resume where you left off."""
        with patch("app.services.security.evilbob_mode.is_active", return_value=True), \
             patch("app.services.security.evilbob_mode.has_capability", return_value=True), \
             patch.dict(os.environ, {"DAENA_VAR": str(tmp_path)}):

            # Start and save
            controller = MissionController()
            status = await controller.start_mission(
                goal="Persist test",
                target="persist.com",
                engagement_level=EngagementLevel.RED_TEAM,
            )
            mission_id = status.mission_id
            original_paths = len(controller.get_paths_summary())
            controller.save()

            # Resume
            resumed = MissionController.resume(mission_id)
            resumed_status = resumed.get_status()
            assert resumed_status.mission_id == mission_id
            assert resumed_status.goal == "Persist test"
            assert resumed_status.target == "persist.com"

    def test_no_active_mission_execute(self):
        """Execute without starting returns error."""
        import asyncio
        controller = MissionController()
        result = asyncio.get_event_loop().run_until_complete(
            controller.execute_next_step()
        )
        assert "error" in result

    def test_no_active_mission_visual(self):
        controller = MissionController()
        visual = controller.get_graph_visual()
        assert "error" in visual


# ---------------------------------------------------------------------------
# EngagementLevel tests
# ---------------------------------------------------------------------------

class TestEngagementLevel:
    """Test engagement level configuration."""

    def test_all_levels_exist(self):
        assert EngagementLevel.AUDIT.value == "audit"
        assert EngagementLevel.PENTEST.value == "pentest"
        assert EngagementLevel.RED_TEAM.value == "red_team"
        assert EngagementLevel.ADVERSARY.value == "adversary"

    def test_levels_are_ordered(self):
        levels = list(EngagementLevel)
        assert len(levels) == 4


# ---------------------------------------------------------------------------
# TraceManager tests
# ---------------------------------------------------------------------------

class TestTraceManager:
    """Test trace cataloging and cleanup."""

    def test_record_trace(self):
        tm = TraceManager()
        trace = tm.record("log_entry", "target.com -> access.log", "HTTP GET /admin")
        assert trace.trace_type == "log_entry"
        assert len(tm.get_all_traces()) == 1

    def test_record_network(self):
        tm = TraceManager()
        trace = tm.record_network("target.com", "HTTPS", "TLS handshake")
        assert trace.trace_type == "network_connection"
        assert not trace.cleanable  # ISP logs can't be cleaned

    def test_record_file(self):
        tm = TraceManager()
        trace = tm.record_file("target.com", "/tmp/payload.sh", "Upload artifact")
        assert trace.cleanable

    def test_record_credential_use(self):
        tm = TraceManager()
        trace = tm.record_credential_use("target.com", "SSH key", "Used stolen key")
        assert not trace.cleanable  # Auth logs are permanent

    def test_get_cleanable_vs_permanent(self):
        tm = TraceManager()
        tm.record_file("t.com", "/tmp/x", "file")
        tm.record_network("t.com", "TCP", "connection")
        tm.record("log_entry", "t.com", "log", cleanable=True)

        cleanable = tm.get_cleanable_traces()
        permanent = tm.get_permanent_traces()
        assert len(cleanable) == 2  # file + log
        assert len(permanent) == 1  # network

    @pytest.mark.asyncio
    async def test_clean_all(self):
        tm = TraceManager()
        tm.record_file("t.com", "/tmp/x", "file")
        tm.record_network("t.com", "TCP", "connection")

        report = await tm.clean_all()
        assert report["cleaned"] == 1  # Only the file
        assert report["permanent"] == 1  # Network stays
        assert "forensic_challenge" in report

    def test_forensic_report(self):
        tm = TraceManager()
        tm.record("log_entry", "target", "test")
        report = tm.get_forensic_report()
        assert report["total_operations"] == 1
        assert len(report["traces"]) == 1


# ---------------------------------------------------------------------------
# EngagementController tests
# ---------------------------------------------------------------------------

class TestEngagementController:
    """Test capability matrix enforcement."""

    def test_audit_allows_osint(self):
        ec = EngagementController(EngagementLevel.AUDIT)
        assert ec.is_allowed("osint")
        assert ec.is_allowed("vulnerability_scan")

    def test_audit_blocks_exploitation(self):
        ec = EngagementController(EngagementLevel.AUDIT)
        assert not ec.is_allowed("exploitation")
        assert not ec.is_allowed("social_engineering")
        assert not ec.is_allowed("trace_cleanup")

    def test_pentest_allows_exploitation(self):
        ec = EngagementController(EngagementLevel.PENTEST)
        assert ec.is_allowed("exploitation")
        assert ec.is_allowed("exfiltration_proof")
        assert not ec.is_allowed("social_engineering")
        assert not ec.is_allowed("trace_cleanup")

    def test_red_team_allows_social_engineering(self):
        ec = EngagementController(EngagementLevel.RED_TEAM)
        assert ec.is_allowed("social_engineering")
        assert ec.is_allowed("attraction_honeypots")
        assert ec.is_allowed("creative_paths")
        assert not ec.is_allowed("trace_cleanup")

    def test_adversary_allows_everything(self):
        ec = EngagementController(EngagementLevel.ADVERSARY)
        for cap in ec.get_allowed_capabilities():
            assert ec.is_allowed(cap)
        assert ec.is_allowed("trace_cleanup")

    def test_enforce_logs_denial(self):
        ec = EngagementController(EngagementLevel.AUDIT)
        assert not ec.enforce("exploitation", "Trying to exploit")

    def test_override(self):
        ec = EngagementController(EngagementLevel.AUDIT)
        assert not ec.is_allowed("exploitation")
        ec.override("exploitation", True)
        assert ec.is_allowed("exploitation")

    def test_matrix_summary(self):
        ec = EngagementController(EngagementLevel.RED_TEAM)
        summary = ec.get_matrix_summary()
        assert summary["level"] == "red_team"
        assert "capabilities" in summary
        assert len(summary["capabilities"]) == 14


# ---------------------------------------------------------------------------
# OpSecShield tests
# ---------------------------------------------------------------------------

class TestOpSecShield:
    """Test the governance protecting Daena herself."""

    def test_activate_deactivate(self):
        shield = OpSecShield()
        assert not shield.is_active
        shield.activate()
        assert shield.is_active
        shield.deactivate()
        assert not shield.is_active

    def test_check_outbound_clean(self):
        shield = OpSecShield()
        shield.activate()
        result = shield.check_outbound_request(
            {"User-Agent": "Mozilla/5.0 Chrome/124", "Accept": "text/html"},
            "https://target.com",
        )
        assert result["passed"]

    def test_check_outbound_catches_python_ua(self):
        shield = OpSecShield()
        shield.activate()
        result = shield.check_outbound_request(
            {"User-Agent": "python-httpx/0.27"},
            "https://target.com",
        )
        assert not result["passed"]

    def test_check_outbound_catches_daena_header(self):
        shield = OpSecShield()
        shield.activate()
        result = shield.check_outbound_request(
            {"User-Agent": "Chrome/124", "X-Powered-By": "Daena Security"},
            "https://target.com",
        )
        assert not result["passed"]

    def test_check_no_data_leak_clean(self):
        shield = OpSecShield()
        result = shield.check_no_data_leak("This is normal exfiltrated data from target")
        assert result["passed"]

    def test_check_no_data_leak_catches_identity(self):
        shield = OpSecShield()
        for leak in ["daena", "mas-ai", "masoud", "evilbob", "sunflower-honeycomb", "philattice"]:
            result = shield.check_no_data_leak(f"Data contains {leak} reference")
            assert not result["passed"], f"Should catch '{leak}'"

    def test_check_evidence_storage_safe(self):
        shield = OpSecShield()
        result = shield.check_evidence_storage("evidence data", "var/vault/evidence.enc")
        assert result["passed"]

    def test_check_evidence_storage_unsafe(self):
        shield = OpSecShield()
        result = shield.check_evidence_storage("evidence data", "/home/user/desktop/evidence.txt")
        assert not result["passed"]

    def test_report(self):
        shield = OpSecShield()
        shield.activate()
        shield.check_outbound_request({"User-Agent": "Chrome"}, "https://x.com")
        shield.check_no_data_leak("clean data")
        report = shield.get_report()
        assert report["active"]
        assert report["checks_passed"] == 2
        assert report["integrity"] == "CLEAN"


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

class TestMissionIntegration:
    """Integration tests for the full mission flow."""

    @pytest.mark.asyncio
    async def test_full_mission_flow(self, tmp_path):
        """Test complete flow: start -> plan -> graph -> save -> resume."""
        with patch("app.services.security.evilbob_mode.is_active", return_value=True), \
             patch("app.services.security.evilbob_mode.has_capability", return_value=True), \
             patch.dict(os.environ, {"DAENA_VAR": str(tmp_path)}):

            # 1. Start mission
            controller = MissionController()
            status = await controller.start_mission(
                goal="Transfer $0.01 from treasury",
                target="clientcorp.com",
                engagement_level=EngagementLevel.ADVERSARY,
            )
            assert status.status == "planned"
            assert status.paths_total >= 5  # ADVERSARY gets all 5 path types

            # 2. Check graph has nodes
            visual = controller.get_graph_visual()
            assert len(visual["nodes"]) > 0

            # 3. Check paths have steps
            paths = controller.get_paths_summary()
            for path in paths:
                assert len(path["step_details"]) > 0

            # 4. Save
            saved_path = controller.save()
            assert saved_path

            # 5. Resume
            resumed = MissionController.resume(status.mission_id)
            assert resumed.get_status().goal == "Transfer $0.01 from treasury"
            assert resumed.get_status().engagement_level == EngagementLevel.ADVERSARY

    @pytest.mark.asyncio
    async def test_graph_grows_during_chain_follow(self, tmp_path):
        """Test that graph grows as chains are followed."""
        with patch.dict(os.environ, {"DAENA_VAR": str(tmp_path)}):
            graph = MissionGraph()
            entity = GraphNode(node_type=NodeType.ENTITY, label="corp.com")
            goal = GraphNode(node_type=NodeType.GOAL, label="goal")
            graph.add_node(entity)
            graph.add_node(goal)

            follower = ChainFollower(graph)
            initial_count = len(graph.nodes)

            # Follow forward -- should discover new nodes
            await follower.follow(entity.id, goal.id, "forward")
            assert len(graph.nodes) > initial_count

            # Follow inversion -- should discover technique nodes
            count_before_inversion = len(graph.nodes)
            await follower.follow(entity.id, goal.id, "inversion")
            assert len(graph.nodes) > count_before_inversion


# ---------------------------------------------------------------------------
# ProximityMapper tests
# ---------------------------------------------------------------------------

class TestProximityMapper:
    """Test the 'look AROUND the target' intelligence."""

    @pytest.mark.asyncio
    async def test_map_proximity_creates_rings(self):
        graph = MissionGraph()
        mapper = ProximityMapper(graph)

        rings = await mapper.map_proximity("spacex.com", "find CEO phone number")
        assert len(rings) == 6  # Rings 0-5
        assert rings[0].distance == 0
        assert rings[0].label.startswith("Target:")
        assert rings[5].distance == 5

    @pytest.mark.asyncio
    async def test_proximity_adds_nodes_to_graph(self):
        graph = MissionGraph()
        mapper = ProximityMapper(graph)
        initial_nodes = len(graph.nodes)

        await mapper.map_proximity("target.com", "goal")
        # Should add many nodes (target + all ring entities)
        assert len(graph.nodes) > initial_nodes + 20

    @pytest.mark.asyncio
    async def test_ring_difficulty_decreases_outward(self):
        graph = MissionGraph()
        mapper = ProximityMapper(graph)

        rings = await mapper.map_proximity("target.com", "goal")
        # Ring 0 (target) should be hardest, Ring 5 (public) should be easiest
        assert rings[0].access_difficulty > rings[5].access_difficulty

    @pytest.mark.asyncio
    async def test_ring_value_decreases_outward(self):
        graph = MissionGraph()
        mapper = ProximityMapper(graph)

        rings = await mapper.map_proximity("target.com", "goal")
        # Ring 0 (target) should have highest value, Ring 5 lowest
        assert rings[0].value_to_goal > rings[5].value_to_goal

    @pytest.mark.asyncio
    async def test_find_easiest_chain(self):
        graph = MissionGraph()
        mapper = ProximityMapper(graph)

        await mapper.map_proximity("target.com", "goal")
        chain = mapper.find_easiest_chain()
        assert len(chain) > 0
        # First item should have best value/difficulty ratio
        assert chain[0].distance > 0  # Not the target itself

    @pytest.mark.asyncio
    async def test_find_weakest_link(self):
        graph = MissionGraph()
        mapper = ProximityMapper(graph)

        await mapper.map_proximity("target.com", "goal")
        weak = mapper.find_weakest_link()
        assert weak is not None
        assert weak.distance > 0

    @pytest.mark.asyncio
    async def test_ring_summary(self):
        graph = MissionGraph()
        mapper = ProximityMapper(graph)

        await mapper.map_proximity("target.com", "goal")
        summary = mapper.get_ring_summary()
        assert len(summary) == 6
        for ring in summary:
            assert "ring" in ring
            assert "label" in ring
            assert "entity_types" in ring
            assert "access_difficulty" in ring


# ---------------------------------------------------------------------------
# AttractionSimulator tests
# ---------------------------------------------------------------------------

class TestAttractionSimulator:
    """Test the 'target comes to you' simulation."""

    @pytest.mark.asyncio
    async def test_generate_scenarios(self):
        graph = MissionGraph()
        sim = AttractionSimulator(graph)

        scenarios = await sim.generate_scenarios("target.com", "steal data")
        assert len(scenarios) == 5  # 5 attraction techniques
        techniques = {s.technique for s in scenarios}
        assert "watering_hole" in techniques
        assert "honeypot" in techniques
        assert "content_lure" in techniques
        assert "social_bait" in techniques
        assert "service_impersonation" in techniques

    @pytest.mark.asyncio
    async def test_scenarios_added_to_graph(self):
        graph = MissionGraph()
        sim = AttractionSimulator(graph)
        initial = len(graph.nodes)

        await sim.generate_scenarios("target.com", "goal")
        assert len(graph.nodes) > initial
        # Should have technique nodes
        technique_nodes = [n for n in graph.nodes.values() if n.node_type == NodeType.TECHNIQUE]
        assert len(technique_nodes) >= 5

    @pytest.mark.asyncio
    async def test_rank_scenarios(self):
        graph = MissionGraph()
        sim = AttractionSimulator(graph)

        await sim.generate_scenarios("target.com", "goal")
        ranked = sim.rank_scenarios()
        assert len(ranked) == 5
        # First should have highest score
        # Social bait typically ranks highest (high probability, low risk, faster)

    @pytest.mark.asyncio
    async def test_scenario_summary(self):
        graph = MissionGraph()
        sim = AttractionSimulator(graph)

        await sim.generate_scenarios("target.com", "goal")
        summary = sim.get_scenario_summary()
        assert len(summary) == 5
        for s in summary:
            assert "name" in s
            assert "technique" in s
            assert "success_probability" in s
            assert "what_we_capture" in s

    @pytest.mark.asyncio
    async def test_each_scenario_has_setup_steps(self):
        graph = MissionGraph()
        sim = AttractionSimulator(graph)

        scenarios = await sim.generate_scenarios("target.com", "goal")
        for s in scenarios:
            assert len(s.setup_steps) > 0
            assert s.legal_notes  # Every scenario must have legal notes
            assert s.what_we_capture  # Must define what we gain


# ---------------------------------------------------------------------------
# CreativePathGenerator tests
# ---------------------------------------------------------------------------

class TestCreativePathGenerator:
    """Test the 'think outside the box' reasoning."""

    @pytest.mark.asyncio
    async def test_generate_creative_paths(self):
        graph = MissionGraph()
        gen = CreativePathGenerator(graph)

        paths = await gen.generate_creative_paths(
            goal="get CEO phone number",
            target="spacex.com",
        )
        assert len(paths) == 7  # 7 creative lenses
        lenses = {p["lens"] for p in paths}
        assert "constraint_removal" in lenses
        assert "perspective_shift" in lenses
        assert "chain_of_trivials" in lenses
        assert "reverse_social_proof" in lenses

    @pytest.mark.asyncio
    async def test_creative_paths_add_graph_nodes(self):
        graph = MissionGraph()
        gen = CreativePathGenerator(graph)
        initial = len(graph.nodes)

        await gen.generate_creative_paths("goal", "target.com")
        assert len(graph.nodes) > initial
        creative_nodes = [n for n in graph.nodes.values() if "creative" in n.tags]
        assert len(creative_nodes) > 0

    @pytest.mark.asyncio
    async def test_each_lens_produces_steps(self):
        graph = MissionGraph()
        gen = CreativePathGenerator(graph)

        paths = await gen.generate_creative_paths("goal", "target.com")
        for path in paths:
            approach = path.get("approach", {})
            assert "steps" in approach
            assert "key_insight" in approach
            assert len(approach["steps"]) > 0

    @pytest.mark.asyncio
    async def test_creative_with_known_blockers(self):
        graph = MissionGraph()
        gen = CreativePathGenerator(graph)

        paths = await gen.generate_creative_paths(
            goal="access database",
            target="hardened.com",
            known_blockers=["WAF blocks all scans", "MFA on all accounts", "No public endpoints"],
        )
        # Should still generate paths despite blockers
        assert len(paths) == 7
        # Constraint removal lens should consider the blockers
        cr_path = next(p for p in paths if p["lens"] == "constraint_removal")
        assert len(cr_path["blockers_considered"]) == 3

    def test_creative_lenses_defined(self):
        assert len(CreativePathGenerator.CREATIVE_LENSES) == 7
        for name, prompt in CreativePathGenerator.CREATIVE_LENSES.items():
            assert len(prompt) > 50  # Each lens has substantial prompt


# ---------------------------------------------------------------------------
# Full Integration with new modules
# ---------------------------------------------------------------------------

class TestFullIntelligenceIntegration:
    """Test that all intelligence modules work together."""

    @pytest.mark.asyncio
    async def test_mission_includes_proximity_and_attraction(self, tmp_path):
        """Mission start should run all intelligence phases."""
        with patch("app.services.security.evilbob_mode.is_active", return_value=True), \
             patch("app.services.security.evilbob_mode.has_capability", return_value=True), \
             patch.dict(os.environ, {"DAENA_VAR": str(tmp_path)}):

            controller = MissionController()
            status = await controller.start_mission(
                goal="Prove full access",
                target="megacorp.com",
                engagement_level=EngagementLevel.ADVERSARY,
            )

            # Should have proximity data
            proximity = controller.get_proximity_map()
            assert len(proximity) == 6  # 6 rings

            # Should have attraction scenarios
            scenarios = controller.get_attraction_scenarios()
            assert len(scenarios) == 5

            # Should have creative paths
            creative = controller.get_creative_paths()
            assert len(creative) == 7

            # Should have weakest link analysis
            weak = controller.get_weakest_link()
            assert weak is not None

            # Graph should be massive (all modules contributing)
            visual = controller.get_graph_visual()
            # Template paths + proximity nodes + attraction nodes + creative nodes
            assert len(visual["nodes"]) > 50

    @pytest.mark.asyncio
    async def test_bodyguard_phone_scenario(self, tmp_path):
        """Test the Elon's bodyguard's phone scenario.

        Goal: find CEO's phone number.
        Approach: Don't go TO the CEO. Find who's AROUND the CEO.
        Ring 1 (bodyguard) has Ring 0 (CEO) info on their phone.
        """
        graph = MissionGraph()
        mapper = ProximityMapper(graph)

        rings = await mapper.map_proximity("spacex.com", "find CEO phone number")

        # Ring 0 is the CEO (hardest, highest value)
        assert rings[0].access_difficulty == 1.0
        assert rings[0].value_to_goal == 1.0

        # Ring 1 has security personnel (the bodyguard)
        ring1_types = [e["type"] for e in rings[1].entities]
        assert "security_personnel" in ring1_types

        # Ring 1 is easier than Ring 0 but still valuable
        assert rings[1].access_difficulty < rings[0].access_difficulty
        assert rings[1].value_to_goal > 0.9

        # The weakest link should NOT be Ring 0
        weak = mapper.find_weakest_link()
        assert weak is not None
        assert weak.distance > 0  # Not the target itself

        # The easiest chain starts from the outside
        chain = mapper.find_easiest_chain()
        assert chain[0].distance > 0
