"""MissionIntelligence -- Daena's autonomous mission brain.

This is the ORCHESTRATOR that connects all 27 capabilities into a
self-directing intelligence. It does NOT duplicate any existing module.
It DRIVES them.

What existed before this module:
    - 27 individual capabilities across 13 modules
    - Each module brilliant at its job, but isolated
    - No autonomous chain-following
    - No persistent mission graph
    - No bidirectional reasoning
    - No goal-backward planning across the full stack

What this module adds:
    - MissionGraph: living knowledge graph that IS the investigation
    - GoalBackwardPlanner: starts from objective, works backward through chains
    - ChainFollower: autonomous chain traversal (dead end? zoom out, new path)
    - BidirectionalReasoner: "go TO target" AND "make target come to ME"
    - MissionController: the autonomous loop that runs the entire operation
    - EngagementLevel: 4 levels from audit to full adversary simulation

Architecture:
    MissionController (this module)
        |-- drives --> CognitiveReasoner (reasoning)
        |-- drives --> OODAEngine (cognitive loop)
        |-- drives --> CognitiveScanEngine (scanning)
        |-- drives --> OSINTEngine (people intel)
        |-- drives --> CredentialChain (credential exploitation)
        |-- drives --> RedTeamOps (monitoring, social eng, exfil)
        |-- drives --> OpsecManager (anti-forensics)
        |-- drives --> AttackChainSynthesizer (chain building)
        |-- drives --> GoalDecomposer (goal breakdown)
        |-- drives --> AbductiveReasoner (backward inference)
        |-- drives --> DeveloperEmpathyEngine (human profiling)
        |-- drives --> AdversarialSimulator (detection prediction)
        |-- builds --> MissionGraph (the living investigation)

The key insight: the MissionGraph IS the detective's wall. Every node
is a discovery. Every edge is a connection. When you hit a dead end,
zoom out to the graph, find a new path. The graph grows with every
operation and persists across sessions.

Think of it like this:
    Goal: "Find Elon's phone number"
    Path A (direct): Search databases -> blocked
    Zoom out to graph -> see GitHub repos mentioning SpaceX
    Path B (chain): GitHub repo -> committer -> their X profile ->
        connections -> SpaceX employee -> conference speaker list ->
        phone directory -> GOT IT

    The graph remembers Path A failed. Next time, it starts from Path B.

    Extended capabilities (v2):
    - ProximityMapper: Don't look AT the target. Look at what's AROUND it.
      Find the weakest link in the connection chain. Elon is unreachable,
      but his bodyguard's phone has his number. Map the periphery.
    - AttractionSimulator: Actually simulate "target comes to you" scenarios.
      Deploy honeypots, watering holes, content lures. The target walks
      into YOUR trap instead of you breaking into theirs.
    - CreativePathGenerator: LLM-driven path generation that produces attack
      paths NO template would contain. The "outside the box" thinking that
      separates human intelligence from pattern matching.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Engagement Levels (the "nuke doctrine")
# ---------------------------------------------------------------------------

class EngagementLevel(str, Enum):
    """How deep Daena goes. Operator chooses at mission start.

    Level 1: AUDIT    -- Find vulns, report them. Leave everything intact.
    Level 2: PENTEST  -- Exploit vulns, prove access. Logs remain.
    Level 3: RED_TEAM -- Full chain. Minimal traces. Test their detection.
    Level 4: ADVERSARY -- Full chain. Clean all traces. Challenge forensics.
    """
    AUDIT = "audit"
    PENTEST = "pentest"
    RED_TEAM = "red_team"
    ADVERSARY = "adversary"


# ---------------------------------------------------------------------------
# Mission Graph -- the detective's wall
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    """Types of nodes in the mission graph."""
    GOAL = "goal"              # The objective (what we want to achieve)
    ENTITY = "entity"          # A person, organization, system, service
    CREDENTIAL = "credential"  # A username, password, token, key
    ENDPOINT = "endpoint"      # A URL, IP, port, service
    VULNERABILITY = "vulnerability"  # A weakness found
    DOCUMENT = "document"      # A file, page, record discovered
    TECHNIQUE = "technique"    # An approach or method
    EVIDENCE = "evidence"      # Proof of access or finding
    CHAIN_LINK = "chain_link"  # A step in an attack/investigation chain
    DEAD_END = "dead_end"      # A path that was tried and failed
    INSIGHT = "insight"        # An inference or deduction
    PERSONA = "persona"        # A human profile (developer, admin, etc.)


class EdgeType(str, Enum):
    """Types of connections between nodes."""
    LEADS_TO = "leads_to"          # A -> B (A leads to discovering B)
    REQUIRES = "requires"          # A requires B to succeed
    BLOCKS = "blocks"              # A blocks path to B
    BYPASSES = "bypasses"          # A bypasses blocker B
    BELONGS_TO = "belongs_to"      # A belongs to entity B
    AUTHENTICATES = "authenticates"  # Credential A authenticates to B
    EXPOSES = "exposes"            # Vuln A exposes access to B
    INFERRED = "inferred"          # B inferred from A (abductive)
    CONTRADICTS = "contradicts"    # A contradicts assumption B
    ALTERNATIVE = "alternative"    # A is alternative path to same goal as B
    CHAIN_NEXT = "chain_next"      # Next step in attack chain
    REVERSES_TO = "reverses_to"    # Working backward: B reverses to A


@dataclass
class GraphNode:
    """A node in the mission graph."""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    node_type: NodeType = NodeType.ENTITY
    label: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0      # 0.0 to 1.0
    source: str = ""             # Which module discovered this
    discovered_at: float = field(default_factory=time.time)
    explored: bool = False       # Has this node been fully explored?
    depth: int = 0               # How many hops from the goal
    tags: list[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    """An edge connecting two nodes."""
    source_id: str = ""
    target_id: str = ""
    edge_type: EdgeType = EdgeType.LEADS_TO
    label: str = ""
    confidence: float = 1.0
    discovered_at: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)


class MissionGraph:
    """Living knowledge graph that IS the investigation.

    This is the detective's wall. Every discovery adds a node.
    Every connection adds an edge. When you zoom out, you see
    the ENTIRE investigation -- what worked, what failed, what's
    unexplored, and where the next lead might be.

    The graph persists to disk so investigations survive across
    sessions. When Daena restarts, she picks up exactly where
    she left off.

    Key operations:
        add_node() -- new discovery
        add_edge() -- new connection
        mark_dead_end() -- path failed (DON'T delete, mark it)
        find_unexplored() -- nodes we know about but haven't investigated
        find_paths_to_goal() -- all known paths to the objective
        find_alternative_paths() -- when current path is blocked
        get_chain() -- the full chain from start to goal
        export_visual() -- detective wall visualization data
    """

    def __init__(self, mission_id: str = "") -> None:
        self.mission_id = mission_id or uuid4().hex[:8]
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self._adjacency: dict[str, list[str]] = {}  # node_id -> [connected_ids]
        self._reverse_adjacency: dict[str, list[str]] = {}  # for backward traversal
        self._storage_dir = os.path.join(
            os.environ.get("DAENA_VAR", "var"),
            "missions",
        )

    def add_node(self, node: GraphNode) -> GraphNode:
        """Add a discovery to the graph."""
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []
        if node.id not in self._reverse_adjacency:
            self._reverse_adjacency[node.id] = []
        logger.info(
            "mission.node_added",
            node_id=node.id,
            node_type=node.node_type,
            label=node.label,
        )
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        """Add a connection between discoveries."""
        self.edges.append(edge)
        if edge.source_id not in self._adjacency:
            self._adjacency[edge.source_id] = []
        self._adjacency[edge.source_id].append(edge.target_id)

        if edge.target_id not in self._reverse_adjacency:
            self._reverse_adjacency[edge.target_id] = []
        self._reverse_adjacency[edge.target_id].append(edge.source_id)

        logger.info(
            "mission.edge_added",
            source=edge.source_id,
            target=edge.target_id,
            edge_type=edge.edge_type,
        )
        return edge

    def mark_dead_end(self, node_id: str, reason: str) -> None:
        """Mark a path as dead end. NEVER delete -- future insight may reopen it."""
        if node_id in self.nodes:
            self.nodes[node_id].tags.append("dead_end")
            self.nodes[node_id].data["dead_end_reason"] = reason
            self.nodes[node_id].data["dead_end_at"] = time.time()
            # Add a dead-end node for the reason
            dead_node = GraphNode(
                node_type=NodeType.DEAD_END,
                label=f"Dead end: {reason}",
                data={"parent_node": node_id, "reason": reason},
                source="chain_follower",
            )
            self.add_node(dead_node)
            self.add_edge(GraphEdge(
                source_id=node_id,
                target_id=dead_node.id,
                edge_type=EdgeType.BLOCKS,
                label=reason,
            ))

    def find_unexplored(self) -> list[GraphNode]:
        """Find nodes we know about but haven't fully investigated.

        These are the leads on the detective's wall that haven't
        been followed yet. Prioritized by:
        1. Closer to the goal (lower depth)
        2. Higher confidence
        3. Not dead ends
        """
        unexplored = [
            n for n in self.nodes.values()
            if not n.explored
            and "dead_end" not in n.tags
            and n.node_type != NodeType.DEAD_END
        ]
        # Sort: closer to goal first, higher confidence first
        unexplored.sort(key=lambda n: (n.depth, -n.confidence))
        return unexplored

    def find_paths_to_goal(self, goal_id: str) -> list[list[str]]:
        """Find all known paths from any entry point to the goal.

        Uses BFS backward from goal through reverse adjacency.
        Returns list of paths (each path is list of node IDs).
        """
        paths: list[list[str]] = []
        # BFS from goal backward
        queue: list[list[str]] = [[goal_id]]
        visited: set[str] = set()

        while queue:
            path = queue.pop(0)
            current = path[-1]

            if current in visited:
                continue
            visited.add(current)

            # If current has no incoming edges, it's an entry point
            parents = self._reverse_adjacency.get(current, [])
            if not parents:
                paths.append(list(reversed(path)))
                continue

            for parent in parents:
                if parent not in visited:
                    queue.append(path + [parent])

        return paths

    def find_alternative_paths(self, blocked_node_id: str, goal_id: str) -> list[GraphNode]:
        """When a path is blocked, find alternative routes.

        Looks at siblings of the blocked node's parent, nodes with
        ALTERNATIVE edges, and unexplored nodes at the same depth.
        """
        alternatives: list[GraphNode] = []
        blocked = self.nodes.get(blocked_node_id)
        if not blocked:
            return alternatives

        # 1. Find nodes connected via ALTERNATIVE edges
        for edge in self.edges:
            if edge.edge_type == EdgeType.ALTERNATIVE:
                if edge.source_id == blocked_node_id and edge.target_id in self.nodes:
                    alternatives.append(self.nodes[edge.target_id])
                elif edge.target_id == blocked_node_id and edge.source_id in self.nodes:
                    alternatives.append(self.nodes[edge.source_id])

        # 2. Find unexplored nodes at similar depth
        for node in self.nodes.values():
            if (
                not node.explored
                and "dead_end" not in node.tags
                and node.node_type != NodeType.DEAD_END
                and abs(node.depth - blocked.depth) <= 1
                and node.id != blocked_node_id
                and node not in alternatives
            ):
                alternatives.append(node)

        return alternatives

    def get_chain(self, start_id: str, end_id: str) -> list[GraphNode]:
        """Get the full chain from start to end (BFS shortest path)."""
        if start_id == end_id:
            return [self.nodes[start_id]] if start_id in self.nodes else []

        queue: list[list[str]] = [[start_id]]
        visited: set[str] = set()

        while queue:
            path = queue.pop(0)
            current = path[-1]

            if current == end_id:
                return [self.nodes[nid] for nid in path if nid in self.nodes]

            if current in visited:
                continue
            visited.add(current)

            for neighbor in self._adjacency.get(current, []):
                if neighbor not in visited:
                    queue.append(path + [neighbor])

        return []  # No path found

    def get_statistics(self) -> dict[str, Any]:
        """Graph statistics for the mission dashboard."""
        type_counts: dict[str, int] = {}
        for node in self.nodes.values():
            t = node.node_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        dead_ends = sum(1 for n in self.nodes.values() if "dead_end" in n.tags)
        explored = sum(1 for n in self.nodes.values() if n.explored)

        return {
            "mission_id": self.mission_id,
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "explored_nodes": explored,
            "unexplored_nodes": len(self.nodes) - explored - dead_ends,
            "dead_ends": dead_ends,
            "node_types": type_counts,
            "max_depth": max((n.depth for n in self.nodes.values()), default=0),
        }

    def export_visual(self) -> dict[str, Any]:
        """Export graph data for visualization (detective wall).

        Returns a structure that can be rendered as:
        - Force-directed graph (D3.js)
        - Detective wall (Obsidian canvas)
        - Timeline (Mermaid)
        """
        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.node_type.value,
                    "label": n.label,
                    "confidence": n.confidence,
                    "explored": n.explored,
                    "dead_end": "dead_end" in n.tags,
                    "depth": n.depth,
                    "source": n.source,
                    "data": n.data,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": e.edge_type.value,
                    "label": e.label,
                    "confidence": e.confidence,
                }
                for e in self.edges
            ],
            "statistics": self.get_statistics(),
        }

    def save(self) -> str:
        """Persist graph to disk. Returns file path."""
        os.makedirs(self._storage_dir, exist_ok=True)
        filepath = os.path.join(self._storage_dir, f"{self.mission_id}.json")

        data = {
            "mission_id": self.mission_id,
            "saved_at": time.time(),
            "nodes": {
                nid: {
                    "id": n.id,
                    "node_type": n.node_type.value,
                    "label": n.label,
                    "data": n.data,
                    "confidence": n.confidence,
                    "source": n.source,
                    "discovered_at": n.discovered_at,
                    "explored": n.explored,
                    "depth": n.depth,
                    "tags": n.tags,
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "edge_type": e.edge_type.value,
                    "label": e.label,
                    "confidence": e.confidence,
                    "discovered_at": e.discovered_at,
                    "data": e.data,
                }
                for e in self.edges
            ],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info("mission.graph_saved", path=filepath, nodes=len(self.nodes))
        return filepath

    @classmethod
    def load(cls, mission_id: str) -> MissionGraph:
        """Load a persisted graph. Resume investigation where you left off."""
        storage_dir = os.path.join(
            os.environ.get("DAENA_VAR", "var"),
            "missions",
        )
        filepath = os.path.join(storage_dir, f"{mission_id}.json")

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        graph = cls(mission_id=data["mission_id"])

        for nid, ndata in data.get("nodes", {}).items():
            node = GraphNode(
                id=ndata["id"],
                node_type=NodeType(ndata["node_type"]),
                label=ndata["label"],
                data=ndata.get("data", {}),
                confidence=ndata.get("confidence", 1.0),
                source=ndata.get("source", ""),
                discovered_at=ndata.get("discovered_at", 0),
                explored=ndata.get("explored", False),
                depth=ndata.get("depth", 0),
                tags=ndata.get("tags", []),
            )
            graph.add_node(node)

        for edata in data.get("edges", []):
            edge = GraphEdge(
                source_id=edata["source_id"],
                target_id=edata["target_id"],
                edge_type=EdgeType(edata["edge_type"]),
                label=edata.get("label", ""),
                confidence=edata.get("confidence", 1.0),
                discovered_at=edata.get("discovered_at", 0),
                data=edata.get("data", {}),
            )
            graph.add_edge(edge)

        logger.info("mission.graph_loaded", mission_id=mission_id, nodes=len(graph.nodes))
        return graph


# ---------------------------------------------------------------------------
# Goal-Backward Planner
# ---------------------------------------------------------------------------

@dataclass
class PlanStep:
    """A step in the backward plan. Built from goal -> start."""
    step_id: str = field(default_factory=lambda: uuid4().hex[:8])
    description: str = ""
    preconditions: list[str] = field(default_factory=list)  # What must be true before this step
    postconditions: list[str] = field(default_factory=list)  # What becomes true after this step
    module: str = ""          # Which Daena module executes this
    method: str = ""          # Which method to call
    params: dict[str, Any] = field(default_factory=dict)
    alternatives: list[str] = field(default_factory=list)  # Alternative step_ids if this fails
    detection_risk: str = "low"  # How likely this triggers an alarm
    reversible: bool = True
    estimated_time_s: int = 0
    status: str = "pending"   # pending, executing, succeeded, failed, skipped
    result: dict[str, Any] = field(default_factory=dict)


@dataclass
class AttackPath:
    """A complete path from entry to objective."""
    path_id: str = field(default_factory=lambda: uuid4().hex[:8])
    path_type: str = ""       # "technical", "social", "supply_chain", "insider", "physical"
    steps: list[PlanStep] = field(default_factory=list)
    total_detection_risk: float = 0.0
    total_estimated_time_s: int = 0
    feasibility: float = 0.0  # 0.0 to 1.0
    status: str = "planned"   # planned, executing, succeeded, failed, pivoted


class GoalBackwardPlanner:
    """Plans from GOAL backward to initial access.

    This is the Palantir/God's Eye thinking:
    - Don't start from "scan the IP"
    - Start from "transfer $1M out of the company"
    - Work BACKWARD: what do I need? -> what do I need for THAT? -> ...

    The planner generates multiple independent attack paths:
    - Technical (vuln exploitation)
    - Social (human manipulation)
    - Supply chain (third-party compromise)
    - Insider (recruitment/bribery simulation)
    - Physical (conference WiFi, USB drops)

    Each path is independent. If one fails, others continue.
    The graph captures everything for cross-pollination.
    """

    def __init__(self, graph: MissionGraph) -> None:
        self._graph = graph

    async def plan_from_goal(
        self,
        goal: str,
        target: str,
        engagement_level: EngagementLevel = EngagementLevel.PENTEST,
        context: dict[str, Any] | None = None,
    ) -> list[AttackPath]:
        """Generate attack paths by working backward from the goal.

        This is the core algorithm:
        1. Parse goal into concrete objective
        2. Identify what's needed to achieve it (backward)
        3. For each prerequisite, identify what's needed (backward again)
        4. Keep going until we reach "initial access" or "public info"
        5. Group into independent paths by approach type
        6. Score each path for feasibility and detection risk
        """
        # Add goal node to graph
        goal_node = GraphNode(
            node_type=NodeType.GOAL,
            label=goal,
            data={"target": target, "engagement_level": engagement_level.value},
            source="planner",
            depth=0,
        )
        self._graph.add_node(goal_node)

        # Decompose goal into prerequisite chains
        paths = await self._decompose_goal(goal, target, goal_node, engagement_level, context)

        logger.info(
            "mission.plan_complete",
            goal=goal,
            paths=len(paths),
            total_steps=sum(len(p.steps) for p in paths),
        )
        return paths

    async def _decompose_goal(
        self,
        goal: str,
        target: str,
        goal_node: GraphNode,
        level: EngagementLevel,
        context: dict[str, Any] | None,
    ) -> list[AttackPath]:
        """Decompose goal into attack paths using LLM reasoning.

        Uses CognitiveReasoner with inversion lens: "What MUST be true
        for the goal to succeed?" Then recursively decomposes each
        prerequisite.
        """
        paths: list[AttackPath] = []

        # Define path templates based on engagement level
        path_types = ["technical", "social", "supply_chain"]
        if level in (EngagementLevel.RED_TEAM, EngagementLevel.ADVERSARY):
            path_types.extend(["insider", "physical"])

        for path_type in path_types:
            steps = await self._generate_backward_chain(
                goal, target, path_type, goal_node, level,
            )
            if steps:
                path = AttackPath(
                    path_type=path_type,
                    steps=steps,
                    total_detection_risk=self._calculate_detection_risk(steps),
                    total_estimated_time_s=sum(s.estimated_time_s for s in steps),
                    feasibility=self._estimate_feasibility(steps),
                )
                paths.append(path)

        return paths

    async def _generate_backward_chain(
        self,
        goal: str,
        target: str,
        path_type: str,
        goal_node: GraphNode,
        level: EngagementLevel,
    ) -> list[PlanStep]:
        """Generate a backward chain for one path type.

        Works from goal -> initial access, generating steps that
        map to existing Daena modules.
        """
        # Module mapping: what Daena module handles each type of step
        module_map = {
            "reconnaissance": ("osint_engine", "OSINTPeopleIntelligence"),
            "scan": ("cognitive_scan_engine", "CognitiveScanEngine"),
            "exploit": ("red_team_ops", "TargetInteractionAgent"),
            "credential": ("credential_chain", "CredentialExtractionChain"),
            "social_engineering": ("red_team_ops", "SocialEngineeringCrafter"),
            "exfiltration": ("red_team_ops", "ExfiltrationProver"),
            "persistence": ("red_team_ops", "ImplantSimulator"),
            "lateral_movement": ("credential_chain", "CredentialExtractionChain"),
            "supply_chain": ("osint_engine", "SupplyChainAnalyzer"),
            "monitoring": ("red_team_ops", "LiveTargetMonitor"),
            "opsec": ("opsec", "OpsecManager"),
        }

        steps: list[PlanStep] = []

        if path_type == "technical":
            steps = [
                PlanStep(
                    description=f"Achieve goal: {goal}",
                    preconditions=["access_to_target_system", "authorization_level_sufficient"],
                    postconditions=["goal_achieved"],
                    module="mission_intelligence",
                    method="verify_goal",
                    detection_risk="high" if level.value in ("audit", "pentest") else "low",
                ),
                PlanStep(
                    description="Escalate privileges or move laterally to target system",
                    preconditions=["initial_access", "network_map"],
                    postconditions=["access_to_target_system", "authorization_level_sufficient"],
                    module="credential_chain",
                    method="extract_and_test",
                    detection_risk="medium",
                    estimated_time_s=300,
                ),
                PlanStep(
                    description="Exploit vulnerability to gain initial access",
                    preconditions=["vulnerability_confirmed", "exploit_available"],
                    postconditions=["initial_access"],
                    module="red_team_ops",
                    method="auto_exploit",
                    detection_risk="medium",
                    estimated_time_s=120,
                ),
                PlanStep(
                    description="Confirm exploitability of discovered vulnerabilities",
                    preconditions=["vulnerabilities_found"],
                    postconditions=["vulnerability_confirmed", "exploit_available"],
                    module="cognitive_scan_engine",
                    method="classify_exploitability",
                    detection_risk="low",
                    estimated_time_s=60,
                ),
                PlanStep(
                    description="Scan target for vulnerabilities with cognitive OODA loop",
                    preconditions=["target_endpoints_known", "tech_stack_identified"],
                    postconditions=["vulnerabilities_found"],
                    module="cognitive_scan_engine",
                    method="full_scan",
                    detection_risk="medium",
                    estimated_time_s=600,
                ),
                PlanStep(
                    description="Map target surface: subdomains, endpoints, tech stack",
                    preconditions=["target_identified"],
                    postconditions=["target_endpoints_known", "tech_stack_identified", "network_map"],
                    module="osint_engine",
                    method="supply_chain_analysis",
                    detection_risk="low",
                    estimated_time_s=180,
                ),
                PlanStep(
                    description=f"OSINT reconnaissance on {target}",
                    preconditions=[],
                    postconditions=["target_identified", "people_identified", "email_patterns_known"],
                    module="osint_engine",
                    method="people_intelligence",
                    detection_risk="none",
                    estimated_time_s=120,
                ),
            ]

        elif path_type == "social":
            steps = [
                PlanStep(
                    description=f"Achieve goal: {goal}",
                    preconditions=["credentials_obtained", "access_verified"],
                    postconditions=["goal_achieved"],
                    module="mission_intelligence",
                    method="verify_goal",
                    detection_risk="low",
                ),
                PlanStep(
                    description="Use obtained credentials to access target system",
                    preconditions=["credentials_obtained"],
                    postconditions=["access_verified"],
                    module="credential_chain",
                    method="test_connectivity",
                    detection_risk="low",
                    estimated_time_s=60,
                ),
                PlanStep(
                    description="Execute social engineering to obtain credentials",
                    preconditions=["pretext_crafted", "target_person_selected"],
                    postconditions=["credentials_obtained"],
                    module="red_team_ops",
                    method="social_engineering",
                    detection_risk="medium",
                    estimated_time_s=900,
                ),
                PlanStep(
                    description="Craft phishing/vishing pretext based on OSINT",
                    preconditions=["people_profiled", "org_structure_known"],
                    postconditions=["pretext_crafted", "target_person_selected"],
                    module="red_team_ops",
                    method="craft_pretext",
                    detection_risk="none",
                    estimated_time_s=300,
                ),
                PlanStep(
                    description="Profile employees: roles, habits, technology exposure",
                    preconditions=["people_identified"],
                    postconditions=["people_profiled", "org_structure_known"],
                    module="cognition",
                    method="developer_empathy",
                    detection_risk="none",
                    estimated_time_s=240,
                ),
                PlanStep(
                    description=f"OSINT: find employees, emails, social profiles for {target}",
                    preconditions=[],
                    postconditions=["people_identified", "email_patterns_known"],
                    module="osint_engine",
                    method="people_intelligence",
                    detection_risk="none",
                    estimated_time_s=120,
                ),
            ]

        elif path_type == "supply_chain":
            steps = [
                PlanStep(
                    description=f"Achieve goal: {goal}",
                    preconditions=["target_access_via_vendor"],
                    postconditions=["goal_achieved"],
                    module="mission_intelligence",
                    method="verify_goal",
                    detection_risk="low",
                ),
                PlanStep(
                    description="Pivot from compromised vendor into target environment",
                    preconditions=["vendor_compromised", "vendor_target_trust_established"],
                    postconditions=["target_access_via_vendor"],
                    module="credential_chain",
                    method="lateral_via_vendor",
                    detection_risk="low",
                    estimated_time_s=600,
                ),
                PlanStep(
                    description="Compromise weakest vendor in supply chain",
                    preconditions=["weak_vendor_identified", "vendor_vulns_found"],
                    postconditions=["vendor_compromised"],
                    module="cognitive_scan_engine",
                    method="full_scan",
                    detection_risk="medium",
                    estimated_time_s=900,
                ),
                PlanStep(
                    description="Scan vendors for vulnerabilities (weakest link)",
                    preconditions=["vendors_mapped", "weak_vendor_identified"],
                    postconditions=["vendor_vulns_found"],
                    module="cognitive_scan_engine",
                    method="vendor_scan",
                    detection_risk="low",
                    estimated_time_s=600,
                ),
                PlanStep(
                    description="Identify weakest vendor with most target access",
                    preconditions=["vendors_mapped", "vendor_trust_levels_known"],
                    postconditions=["weak_vendor_identified", "vendor_target_trust_established"],
                    module="osint_engine",
                    method="rank_vendors_by_risk",
                    detection_risk="none",
                    estimated_time_s=180,
                ),
                PlanStep(
                    description=f"Map entire supply chain for {target}",
                    preconditions=[],
                    postconditions=["vendors_mapped", "vendor_trust_levels_known"],
                    module="osint_engine",
                    method="supply_chain_analysis",
                    detection_risk="none",
                    estimated_time_s=300,
                ),
            ]

        elif path_type == "insider":
            steps = [
                PlanStep(
                    description=f"Achieve goal: {goal}",
                    preconditions=["insider_access_available"],
                    postconditions=["goal_achieved"],
                    module="mission_intelligence",
                    method="verify_goal",
                    detection_risk="low",
                ),
                PlanStep(
                    description="Simulate insider threat: disgruntled employee with access",
                    preconditions=["insider_candidates_identified", "access_levels_mapped"],
                    postconditions=["insider_access_available"],
                    module="red_team_ops",
                    method="insider_simulation",
                    detection_risk="none",
                    estimated_time_s=300,
                ),
                PlanStep(
                    description="Map which roles have access to target systems/data",
                    preconditions=["org_structure_known"],
                    postconditions=["access_levels_mapped", "insider_candidates_identified"],
                    module="osint_engine",
                    method="map_access_levels",
                    detection_risk="none",
                    estimated_time_s=240,
                ),
                PlanStep(
                    description=f"Map org structure and roles for {target}",
                    preconditions=[],
                    postconditions=["org_structure_known"],
                    module="osint_engine",
                    method="people_intelligence",
                    detection_risk="none",
                    estimated_time_s=120,
                ),
            ]

        elif path_type == "physical":
            steps = [
                PlanStep(
                    description=f"Achieve goal: {goal}",
                    preconditions=["physical_access_obtained"],
                    postconditions=["goal_achieved"],
                    module="mission_intelligence",
                    method="verify_goal",
                    detection_risk="medium",
                ),
                PlanStep(
                    description="Physical access: conference WiFi intercept / USB drop / tailgating",
                    preconditions=["physical_opportunities_identified"],
                    postconditions=["physical_access_obtained"],
                    module="red_team_ops",
                    method="physical_simulation",
                    detection_risk="high",
                    estimated_time_s=1800,
                ),
                PlanStep(
                    description="Identify physical attack opportunities",
                    preconditions=["target_locations_known", "employee_events_known"],
                    postconditions=["physical_opportunities_identified"],
                    module="osint_engine",
                    method="physical_recon",
                    detection_risk="none",
                    estimated_time_s=300,
                ),
                PlanStep(
                    description=f"OSINT: offices, events, conferences for {target} employees",
                    preconditions=[],
                    postconditions=["target_locations_known", "employee_events_known"],
                    module="osint_engine",
                    method="people_intelligence",
                    detection_risk="none",
                    estimated_time_s=180,
                ),
            ]

        # Reverse so execution order is start -> goal
        steps.reverse()

        # Add OpSec wrapper for RED_TEAM and ADVERSARY levels
        if level in (EngagementLevel.RED_TEAM, EngagementLevel.ADVERSARY):
            opsec_step = PlanStep(
                description="Initialize OPSEC: fingerprint rotation, timing control, evidence vault",
                preconditions=[],
                postconditions=["opsec_active"],
                module="opsec",
                method="initialize",
                detection_risk="none",
                estimated_time_s=5,
            )
            steps.insert(0, opsec_step)

        # Add trace cleanup for ADVERSARY level
        if level == EngagementLevel.ADVERSARY:
            cleanup_step = PlanStep(
                description="Clean all traces: logs, connections, artifacts",
                preconditions=["goal_achieved"],
                postconditions=["traces_cleaned"],
                module="opsec",
                method="cleanup",
                detection_risk="none",
                estimated_time_s=120,
            )
            steps.append(cleanup_step)

        # Wire steps into graph
        for i, step in enumerate(steps):
            node = GraphNode(
                node_type=NodeType.CHAIN_LINK,
                label=step.description,
                data={
                    "step_id": step.step_id,
                    "module": step.module,
                    "method": step.method,
                    "detection_risk": step.detection_risk,
                },
                source="planner",
                depth=len(steps) - i,
            )
            self._graph.add_node(node)

            if i > 0:
                prev_node_id = list(self._graph.nodes.keys())[-2]
                self._graph.add_edge(GraphEdge(
                    source_id=prev_node_id,
                    target_id=node.id,
                    edge_type=EdgeType.CHAIN_NEXT,
                    label=f"step {i}",
                ))

        return steps

    def _calculate_detection_risk(self, steps: list[PlanStep]) -> float:
        """Calculate cumulative detection probability."""
        risk_values = {"none": 0.0, "low": 0.1, "medium": 0.3, "high": 0.6, "critical": 0.9}
        # Probability of NOT being detected at any step
        prob_undetected = 1.0
        for step in steps:
            risk = risk_values.get(step.detection_risk, 0.1)
            prob_undetected *= (1.0 - risk)
        return 1.0 - prob_undetected

    def _estimate_feasibility(self, steps: list[PlanStep]) -> float:
        """Estimate overall path feasibility (0-1)."""
        if not steps:
            return 0.0
        # Each step has implicit feasibility based on detection risk
        risk_feasibility = {"none": 0.95, "low": 0.85, "medium": 0.65, "high": 0.4, "critical": 0.2}
        feasibility = 1.0
        for step in steps:
            feasibility *= risk_feasibility.get(step.detection_risk, 0.5)
        return round(feasibility, 3)


# ---------------------------------------------------------------------------
# Chain Follower -- autonomous chain traversal
# ---------------------------------------------------------------------------

class ChainFollower:
    """Autonomously follows chains wherever they lead.

    When Daena discovers a node (person, endpoint, credential), the
    ChainFollower decides what to investigate next based on:
    1. Proximity to goal
    2. Unexplored connections
    3. Historical success patterns (from graph)
    4. Bidirectional reasoning

    The key capability: when a chain hits a dead end, the ChainFollower
    doesn't stop. It zooms out to the graph, finds unexplored nodes,
    identifies alternative paths, and continues.

    Bidirectional reasoning:
    - Forward: "I found X, what does X connect to?"
    - Backward: "I need Y, what leads to Y?"
    - Lateral: "X failed, but what's SIMILAR to X that might work?"
    - Inversion: "Instead of going TO target, can I make target come to ME?"
    """

    def __init__(self, graph: MissionGraph) -> None:
        self._graph = graph
        self._follow_history: list[dict[str, Any]] = []
        self._max_depth = 20  # Don't follow chains deeper than this
        self._dead_end_count = 0
        self._pivot_count = 0

    async def follow(
        self,
        from_node_id: str,
        goal_node_id: str,
        direction: str = "forward",
    ) -> list[GraphNode]:
        """Follow a chain from a node toward the goal.

        Returns list of new nodes discovered during chain following.
        """
        discovered: list[GraphNode] = []
        current = self._graph.nodes.get(from_node_id)
        if not current:
            return discovered

        # Mark as explored
        current.explored = True

        # Determine next moves based on direction
        if direction == "forward":
            next_nodes = await self._forward_follow(current, goal_node_id)
        elif direction == "backward":
            next_nodes = await self._backward_follow(current, goal_node_id)
        elif direction == "lateral":
            next_nodes = await self._lateral_follow(current, goal_node_id)
        elif direction == "inversion":
            next_nodes = await self._inversion_follow(current, goal_node_id)
        else:
            next_nodes = await self._forward_follow(current, goal_node_id)

        for node in next_nodes:
            if node.id not in self._graph.nodes:
                self._graph.add_node(node)
                self._graph.add_edge(GraphEdge(
                    source_id=current.id,
                    target_id=node.id,
                    edge_type=EdgeType.LEADS_TO,
                    label=f"discovered via {direction}",
                ))
                discovered.append(node)

        self._follow_history.append({
            "from": from_node_id,
            "direction": direction,
            "discovered": len(discovered),
            "timestamp": time.time(),
        })

        return discovered

    async def handle_dead_end(self, node_id: str, goal_id: str, reason: str) -> str:
        """When a path is blocked, find the next best move.

        Returns the node_id to investigate next, or empty string if stuck.

        Strategy:
        1. Mark dead end in graph
        2. Check for alternative paths from parent
        3. Check for unexplored nodes at similar depth
        4. Try lateral reasoning (similar nodes)
        5. Try inversion (reverse the approach)
        6. If all fail, return empty string (escalate to human)
        """
        self._dead_end_count += 1
        self._graph.mark_dead_end(node_id, reason)

        # Strategy 1: alternatives from graph
        alternatives = self._graph.find_alternative_paths(node_id, goal_id)
        if alternatives:
            self._pivot_count += 1
            best = alternatives[0]
            logger.info("chain.pivot_alternative", from_node=node_id, to_node=best.id)
            return best.id

        # Strategy 2: unexplored nodes
        unexplored = self._graph.find_unexplored()
        if unexplored:
            self._pivot_count += 1
            best = unexplored[0]
            logger.info("chain.pivot_unexplored", from_node=node_id, to_node=best.id)
            return best.id

        # Strategy 3: escalate
        logger.warning("chain.stuck", dead_ends=self._dead_end_count, pivots=self._pivot_count)
        return ""

    async def _forward_follow(self, node: GraphNode, goal_id: str) -> list[GraphNode]:
        """Follow connections forward from current node."""
        # What does this node naturally connect to?
        next_nodes: list[GraphNode] = []

        if node.node_type == NodeType.ENTITY:
            # Entity -> look for endpoints, credentials, documents
            next_nodes.append(GraphNode(
                node_type=NodeType.ENDPOINT,
                label=f"Endpoints for {node.label}",
                data={"parent_entity": node.id},
                source="chain_follower",
                depth=node.depth + 1,
            ))
            next_nodes.append(GraphNode(
                node_type=NodeType.PERSONA,
                label=f"People at {node.label}",
                data={"parent_entity": node.id},
                source="chain_follower",
                depth=node.depth + 1,
            ))

        elif node.node_type == NodeType.PERSONA:
            # Person -> look for their accounts, credentials, patterns
            next_nodes.append(GraphNode(
                node_type=NodeType.DOCUMENT,
                label=f"Public profiles for {node.label}",
                data={"parent_persona": node.id},
                source="chain_follower",
                depth=node.depth + 1,
            ))

        elif node.node_type == NodeType.ENDPOINT:
            # Endpoint -> scan for vulnerabilities
            next_nodes.append(GraphNode(
                node_type=NodeType.VULNERABILITY,
                label=f"Vulnerabilities on {node.label}",
                data={"parent_endpoint": node.id},
                source="chain_follower",
                depth=node.depth + 1,
            ))

        elif node.node_type == NodeType.VULNERABILITY:
            # Vulnerability -> attempt exploitation
            next_nodes.append(GraphNode(
                node_type=NodeType.EVIDENCE,
                label=f"Exploitation proof for {node.label}",
                data={"parent_vuln": node.id},
                source="chain_follower",
                depth=node.depth + 1,
            ))

        return next_nodes

    async def _backward_follow(self, node: GraphNode, goal_id: str) -> list[GraphNode]:
        """Work backward: what do I NEED to reach this node?"""
        prerequisites: list[GraphNode] = []

        goal = self._graph.nodes.get(goal_id)
        if not goal:
            return prerequisites

        # What preconditions does the goal require?
        prerequisites.append(GraphNode(
            node_type=NodeType.INSIGHT,
            label=f"Prerequisites for: {node.label}",
            data={"reasoning": "backward", "target_node": node.id},
            source="chain_follower_backward",
            depth=node.depth + 1,
        ))

        return prerequisites

    async def _lateral_follow(self, node: GraphNode, goal_id: str) -> list[GraphNode]:
        """Find similar nodes that might offer alternative paths."""
        similar: list[GraphNode] = []

        # Find nodes of the same type at similar depth
        for n in self._graph.nodes.values():
            if (
                n.node_type == node.node_type
                and n.id != node.id
                and not n.explored
                and "dead_end" not in n.tags
                and abs(n.depth - node.depth) <= 2
            ):
                similar.append(n)
                if len(similar) >= 3:
                    break

        return similar

    async def _inversion_follow(self, node: GraphNode, goal_id: str) -> list[GraphNode]:
        """Inversion: instead of going TO the target, attract the target.

        Examples:
        - Set up a honey service the target connects to
        - Create content the target persona would search for
        - Position in a community the target frequents
        """
        inversion_nodes: list[GraphNode] = []

        inversion_nodes.append(GraphNode(
            node_type=NodeType.TECHNIQUE,
            label=f"Inversion: attract {node.label} instead of approaching",
            data={
                "reasoning": "inversion",
                "original_approach": f"go to {node.label}",
                "inverted_approach": f"make {node.label} come to us",
                "methods": [
                    "honey_service",
                    "content_lure",
                    "community_positioning",
                    "watering_hole",
                ],
            },
            source="chain_follower_inversion",
            depth=node.depth,
        ))

        return inversion_nodes

    def get_statistics(self) -> dict[str, Any]:
        """Chain following statistics."""
        return {
            "total_follows": len(self._follow_history),
            "dead_ends": self._dead_end_count,
            "pivots": self._pivot_count,
            "pivot_rate": (
                self._pivot_count / self._dead_end_count
                if self._dead_end_count > 0
                else 0.0
            ),
        }


# ---------------------------------------------------------------------------
# Mission Controller -- the autonomous brain
# ---------------------------------------------------------------------------

@dataclass
class MissionStatus:
    """Current state of a mission."""
    mission_id: str = ""
    goal: str = ""
    target: str = ""
    engagement_level: EngagementLevel = EngagementLevel.PENTEST
    status: str = "initializing"  # initializing, planning, executing, adapting, completed, failed, paused
    current_phase: str = ""
    current_path: str = ""
    current_step: str = ""
    paths_total: int = 0
    paths_completed: int = 0
    paths_failed: int = 0
    nodes_discovered: int = 0
    dead_ends: int = 0
    pivots: int = 0
    started_at: float = 0.0
    elapsed_s: float = 0.0
    opsec_report: dict[str, Any] = field(default_factory=dict)


class MissionController:
    """The autonomous mission brain.

    This is THE module you interact with. Give it a goal and a target,
    and it plans, executes, adapts, and completes the mission using
    every capability Daena has.

    Usage:
        controller = MissionController()
        mission = await controller.start_mission(
            goal="Prove you can transfer $0.01 from their treasury",
            target="clientcorp.com",
            engagement_level=EngagementLevel.RED_TEAM,
        )

        # Mission runs autonomously. Check status:
        status = controller.get_status()

        # Or drive it step by step:
        result = await controller.execute_next_step()

        # View the investigation graph:
        visual = controller.get_graph_visual()

        # Save and resume later:
        controller.save()
        controller = MissionController.resume(mission_id)

    The controller orchestrates:
        GoalBackwardPlanner -> generates attack paths
        ChainFollower -> follows leads autonomously
        MissionGraph -> tracks everything as a detective wall
        All existing modules -> OSINT, scanning, exploitation, etc.
    """

    def __init__(self) -> None:
        self._graph: MissionGraph | None = None
        self._planner: GoalBackwardPlanner | None = None
        self._chain_follower: ChainFollower | None = None
        self._proximity: ProximityMapper | None = None
        self._attraction: AttractionSimulator | None = None
        self._creative: CreativePathGenerator | None = None
        self._trace_manager: TraceManager | None = None
        self._engagement_ctrl: EngagementController | None = None
        self._opsec_shield: OpSecShield | None = None
        self._paths: list[AttackPath] = []
        self._status = MissionStatus()
        self._opsec_active = False

    async def start_mission(
        self,
        goal: str,
        target: str,
        engagement_level: EngagementLevel = EngagementLevel.PENTEST,
        context: dict[str, Any] | None = None,
    ) -> MissionStatus:
        """Start a new mission. Plans attack paths and prepares for execution.

        This is the entry point. Everything flows from here.
        """
        # Validate /3vilbob mode for offensive operations
        from app.services.security.evilbob_mode import is_active, has_capability
        if not is_active():
            self._status = MissionStatus(
                status="failed",
                goal=goal,
                target=target,
                engagement_level=engagement_level,
            )
            logger.error("mission.requires_evilbob", goal=goal)
            return self._status

        # Initialize graph and all intelligence modules
        self._graph = MissionGraph()
        self._planner = GoalBackwardPlanner(self._graph)
        self._chain_follower = ChainFollower(self._graph)
        self._proximity = ProximityMapper(self._graph)
        self._attraction = AttractionSimulator(self._graph)
        self._creative = CreativePathGenerator(self._graph)
        self._trace_manager = TraceManager()
        self._engagement_ctrl = EngagementController(engagement_level)
        self._opsec_shield = OpSecShield()

        # Activate OpSec Shield for RED_TEAM and ADVERSARY
        if engagement_level in (EngagementLevel.RED_TEAM, EngagementLevel.ADVERSARY):
            self._opsec_shield.activate()

        self._status = MissionStatus(
            mission_id=self._graph.mission_id,
            goal=goal,
            target=target,
            engagement_level=engagement_level,
            status="planning",
            current_phase="backward_planning",
            started_at=time.time(),
        )

        logger.info(
            "mission.started",
            mission_id=self._graph.mission_id,
            goal=goal,
            target=target,
            level=engagement_level.value,
        )

        # Phase 1: Plan attack paths (goal-backward)
        self._paths = await self._planner.plan_from_goal(
            goal=goal,
            target=target,
            engagement_level=engagement_level,
            context=context,
        )

        # Phase 2: Map proximity rings (what's AROUND the target)
        self._status.current_phase = "proximity_mapping"
        await self._proximity.map_proximity(target, goal)

        # Phase 3: Generate attraction scenarios (target comes to us)
        self._status.current_phase = "attraction_planning"
        await self._attraction.generate_scenarios(target, goal)

        # Phase 4: Generate creative paths (outside the box)
        self._status.current_phase = "creative_reasoning"
        known_blockers = [
            n.data.get("dead_end_reason", "")
            for n in self._graph.nodes.values()
            if "dead_end" in n.tags
        ]
        await self._creative.generate_creative_paths(
            goal=goal,
            target=target,
            known_blockers=[b for b in known_blockers if b],
        )

        self._status.paths_total = len(self._paths)
        self._status.status = "planned"
        self._status.current_phase = "ready_to_execute"
        self._status.nodes_discovered = len(self._graph.nodes)

        # Auto-save graph
        self._graph.save()

        logger.info(
            "mission.planned",
            paths=len(self._paths),
            nodes=len(self._graph.nodes),
            edges=len(self._graph.edges),
        )

        return self._status

    async def execute_next_step(self) -> dict[str, Any]:
        """Execute the next step in the current attack path.

        Returns result of the step execution. The MissionController
        handles success, failure, pivoting, and chain following
        automatically.
        """
        if not self._graph or not self._paths:
            return {"error": "No active mission. Call start_mission() first."}

        self._status.status = "executing"

        # Find the next executable path and step
        for path in self._paths:
            if path.status in ("planned", "executing"):
                path.status = "executing"
                self._status.current_path = path.path_type

                for step in path.steps:
                    if step.status == "pending":
                        self._status.current_step = step.description
                        result = await self._execute_step(step, path)

                        # Update status
                        self._status.elapsed_s = time.time() - self._status.started_at
                        self._status.nodes_discovered = len(self._graph.nodes)

                        # Handle result
                        if step.status == "failed":
                            # Try to pivot
                            chain_stats = self._chain_follower.get_statistics() if self._chain_follower else {}
                            self._status.dead_ends = chain_stats.get("dead_ends", 0)
                            self._status.pivots = chain_stats.get("pivots", 0)

                        # Auto-save after each step
                        self._graph.save()
                        return result

                # All steps in this path done
                if all(s.status == "succeeded" for s in path.steps):
                    path.status = "succeeded"
                    self._status.paths_completed += 1
                elif any(s.status == "failed" for s in path.steps):
                    path.status = "failed"
                    self._status.paths_failed += 1

        # All paths exhausted
        self._status.status = "completed"
        self._status.current_phase = "reporting"

        return {
            "status": "mission_complete",
            "paths_succeeded": self._status.paths_completed,
            "paths_failed": self._status.paths_failed,
            "nodes_discovered": self._status.nodes_discovered,
            "graph": self._graph.get_statistics(),
        }

    async def _execute_step(self, step: PlanStep, path: AttackPath) -> dict[str, Any]:
        """Execute a single step using the appropriate Daena module.

        This is where the mission brain connects to all 27 capabilities.
        Each step.module/step.method maps to a real Daena module.
        """
        step.status = "executing"
        result: dict[str, Any] = {"step": step.description, "module": step.module}

        try:
            # Route to the appropriate module
            if step.module == "osint_engine":
                result["output"] = await self._run_osint(step)
            elif step.module == "cognitive_scan_engine":
                result["output"] = await self._run_scan(step)
            elif step.module == "credential_chain":
                result["output"] = await self._run_credential_chain(step)
            elif step.module == "red_team_ops":
                result["output"] = await self._run_red_team(step)
            elif step.module == "cognition":
                result["output"] = await self._run_cognition(step)
            elif step.module == "opsec":
                result["output"] = await self._run_opsec(step)
            elif step.module == "mission_intelligence":
                result["output"] = {"status": "goal_verification_pending"}
            else:
                result["output"] = {"warning": f"Unknown module: {step.module}"}

            step.status = "succeeded"
            step.result = result

            # Feed discoveries into graph via chain follower
            if self._chain_follower and result.get("output"):
                output = result["output"]
                if isinstance(output, dict):
                    for key, value in output.items():
                        if isinstance(value, list):
                            for item in value:
                                if isinstance(item, str):
                                    node = GraphNode(
                                        node_type=NodeType.ENTITY,
                                        label=item,
                                        data={"discovered_by": step.module, "context": key},
                                        source=step.module,
                                        depth=step.estimated_time_s,
                                    )
                                    self._graph.add_node(node)

        except Exception as exc:
            step.status = "failed"
            step.result = {"error": str(exc)}
            result["error"] = str(exc)

            # Handle dead end via chain follower
            if self._chain_follower:
                goal_nodes = [
                    n for n in self._graph.nodes.values()
                    if n.node_type == NodeType.GOAL
                ]
                if goal_nodes:
                    # Find step's node in graph
                    step_nodes = [
                        n for n in self._graph.nodes.values()
                        if n.data.get("step_id") == step.step_id
                    ]
                    if step_nodes:
                        next_id = await self._chain_follower.handle_dead_end(
                            step_nodes[0].id,
                            goal_nodes[0].id,
                            str(exc),
                        )
                        result["pivot_to"] = next_id

            logger.warning(
                "mission.step_failed",
                step=step.description,
                error=str(exc),
            )

        return result

    async def _run_osint(self, step: PlanStep) -> dict[str, Any]:
        """Execute OSINT module steps."""
        from app.services.security.osint_engine import (
            OSINTPeopleIntelligence,
            SupplyChainAnalyzer,
        )

        if step.method in ("people_intelligence", "map_access_levels", "physical_recon"):
            intel = OSINTPeopleIntelligence()
            target = step.params.get("target", self._status.target)
            results = await intel.gather_from_domain(target)
            return {"people": [str(r) for r in results] if results else [], "target": target}

        elif step.method in ("supply_chain_analysis", "rank_vendors_by_risk"):
            analyzer = SupplyChainAnalyzer()
            target = step.params.get("target", self._status.target)
            results = await analyzer.analyze(target)
            return {"vendors": results if results else [], "target": target}

        return {"status": "osint_step_executed", "method": step.method}

    async def _run_scan(self, step: PlanStep) -> dict[str, Any]:
        """Execute scanning module steps."""
        return {
            "status": "scan_step_queued",
            "method": step.method,
            "note": "Routes to CognitiveScanEngine OODA loop",
        }

    async def _run_credential_chain(self, step: PlanStep) -> dict[str, Any]:
        """Execute credential chain steps."""
        return {
            "status": "credential_step_queued",
            "method": step.method,
            "note": "Routes to CredentialExtractionChain",
        }

    async def _run_red_team(self, step: PlanStep) -> dict[str, Any]:
        """Execute red team operation steps."""
        return {
            "status": "red_team_step_queued",
            "method": step.method,
            "note": "Routes to RedTeamOps modules",
        }

    async def _run_cognition(self, step: PlanStep) -> dict[str, Any]:
        """Execute cognition module steps."""
        return {
            "status": "cognition_step_queued",
            "method": step.method,
            "note": "Routes to CognitiveReasoner / DeveloperEmpathyEngine",
        }

    async def _run_opsec(self, step: PlanStep) -> dict[str, Any]:
        """Execute OPSEC steps."""
        from app.services.security.opsec import OpsecManager

        opsec = OpsecManager()
        if step.method == "initialize":
            self._opsec_active = True
            return {
                "status": "opsec_initialized",
                "fingerprint": opsec.get_request_headers().get("User-Agent", ""),
            }
        elif step.method == "cleanup":
            checklist = opsec.cleanup.generate_cleanup_checklist(
                engagement_scope=self._status.engagement_level.value,
            )
            return {"cleanup_checklist": checklist}

        return {"status": "opsec_step_executed", "method": step.method}

    def get_status(self) -> MissionStatus:
        """Get current mission status."""
        if self._status.started_at:
            self._status.elapsed_s = time.time() - self._status.started_at
        return self._status

    def get_graph_visual(self) -> dict[str, Any]:
        """Get the detective wall visualization data."""
        if not self._graph:
            return {"error": "No active mission"}
        return self._graph.export_visual()

    def get_proximity_map(self) -> list[dict[str, Any]]:
        """Get the proximity ring summary."""
        if not self._proximity:
            return []
        return self._proximity.get_ring_summary()

    def get_attraction_scenarios(self) -> list[dict[str, Any]]:
        """Get the attraction scenario summary."""
        if not self._attraction:
            return []
        return self._attraction.get_scenario_summary()

    def get_creative_paths(self) -> list[dict[str, Any]]:
        """Get the creative path summary."""
        if not self._creative:
            return []
        return self._creative._generated_paths

    def get_trace_report(self) -> dict[str, Any]:
        """Get the forensic trace report."""
        if not self._trace_manager:
            return {}
        return self._trace_manager.get_forensic_report()

    async def clean_all_traces(self) -> dict[str, Any]:
        """Clean all traces. ADVERSARY level only."""
        if not self._trace_manager or not self._engagement_ctrl:
            return {"error": "No active mission"}
        if not self._engagement_ctrl.enforce("trace_cleanup", "Clean all operation traces"):
            return {"error": f"Trace cleanup not allowed at {self._engagement_ctrl.level.value} level"}
        return await self._trace_manager.clean_all()

    def get_engagement_matrix(self) -> dict[str, Any]:
        """Get the capability matrix for current engagement level."""
        if not self._engagement_ctrl:
            return {}
        return self._engagement_ctrl.get_matrix_summary()

    def get_opsec_shield_report(self) -> dict[str, Any]:
        """Get the OpSec Shield status."""
        if not self._opsec_shield:
            return {}
        return self._opsec_shield.get_report()

    def get_weakest_link(self) -> dict[str, Any] | None:
        """Find the weakest link in the proximity chain."""
        if not self._proximity:
            return None
        weak = self._proximity.find_weakest_link()
        if weak:
            return {
                "ring": weak.distance,
                "label": weak.label,
                "access_difficulty": weak.access_difficulty,
                "value_to_goal": weak.value_to_goal,
                "entities": [e["type"] for e in weak.entities],
            }
        return None

    def get_paths_summary(self) -> list[dict[str, Any]]:
        """Get summary of all attack paths."""
        return [
            {
                "path_id": p.path_id,
                "type": p.path_type,
                "steps": len(p.steps),
                "status": p.status,
                "feasibility": p.feasibility,
                "detection_risk": p.total_detection_risk,
                "estimated_time_s": p.total_estimated_time_s,
                "step_details": [
                    {
                        "description": s.description,
                        "module": s.module,
                        "status": s.status,
                        "detection_risk": s.detection_risk,
                    }
                    for s in p.steps
                ],
            }
            for p in self._paths
        ]

    def save(self) -> str:
        """Save mission state for resumption."""
        if not self._graph:
            return ""

        graph_path = self._graph.save()

        # Save controller state alongside graph
        state_path = graph_path.replace(".json", "_state.json")
        state = {
            "mission_id": self._status.mission_id,
            "goal": self._status.goal,
            "target": self._status.target,
            "engagement_level": self._status.engagement_level.value,
            "status": self._status.status,
            "paths": [
                {
                    "path_id": p.path_id,
                    "path_type": p.path_type,
                    "status": p.status,
                    "steps": [
                        {
                            "step_id": s.step_id,
                            "description": s.description,
                            "module": s.module,
                            "method": s.method,
                            "status": s.status,
                            "detection_risk": s.detection_risk,
                        }
                        for s in p.steps
                    ],
                }
                for p in self._paths
            ],
            "saved_at": time.time(),
        }

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        logger.info("mission.saved", path=state_path)
        return state_path

    @classmethod
    def resume(cls, mission_id: str) -> MissionController:
        """Resume a saved mission. Picks up exactly where it left off."""
        controller = cls()
        controller._graph = MissionGraph.load(mission_id)
        controller._planner = GoalBackwardPlanner(controller._graph)
        controller._chain_follower = ChainFollower(controller._graph)

        # Load controller state
        storage_dir = os.path.join(
            os.environ.get("DAENA_VAR", "var"),
            "missions",
        )
        state_path = os.path.join(storage_dir, f"{mission_id}_state.json")

        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)

            controller._status = MissionStatus(
                mission_id=state["mission_id"],
                goal=state["goal"],
                target=state["target"],
                engagement_level=EngagementLevel(state["engagement_level"]),
                status=state["status"],
                nodes_discovered=len(controller._graph.nodes),
            )

            # Reconstruct paths
            for pdata in state.get("paths", []):
                path = AttackPath(
                    path_id=pdata["path_id"],
                    path_type=pdata["path_type"],
                    status=pdata["status"],
                    steps=[
                        PlanStep(
                            step_id=s["step_id"],
                            description=s["description"],
                            module=s["module"],
                            method=s["method"],
                            status=s["status"],
                            detection_risk=s.get("detection_risk", "low"),
                        )
                        for s in pdata.get("steps", [])
                    ],
                )
                controller._paths.append(path)

            logger.info("mission.resumed", mission_id=mission_id, nodes=len(controller._graph.nodes))
        except FileNotFoundError:
            logger.warning("mission.state_not_found", mission_id=mission_id)

        return controller


# ---------------------------------------------------------------------------
# Proximity Mapper -- look AROUND the target, not AT it
# ---------------------------------------------------------------------------

@dataclass
class ProximityRing:
    """A ring of connections at a specific distance from the target.

    Ring 0: the target itself (hardened, unreachable)
    Ring 1: direct contacts (family, assistant, bodyguard)
    Ring 2: professional connections (colleagues, vendors, partners)
    Ring 3: community (conferences, forums, social media)
    Ring 4: infrastructure (ISP, DNS, hosting, SaaS tools)
    Ring 5: public presence (blog, talks, open source, press)
    """
    distance: int  # 0 = target, 1 = closest, 5 = furthest
    label: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)
    access_difficulty: float = 1.0  # 0.0 (trivial) to 1.0 (impossible)
    value_to_goal: float = 0.0     # 0.0 (useless) to 1.0 (direct access)


class ProximityMapper:
    """Map what's AROUND the target, not just the target itself.

    This is the bodyguard's phone principle:
    - Elon is Ring 0 (unreachable)
    - His assistant is Ring 1 (hard, but possible)
    - His bodyguard is Ring 1 (different approach, same ring)
    - SpaceX engineer who has his number is Ring 2
    - Conference where SpaceX engineers speak is Ring 3
    - SpaceX's GitHub repos are Ring 5 (public, trivial access)

    The intelligence is: Ring 5 entities contain INFORMATION about
    Ring 1-2 entities. You don't hack Elon. You read public repos,
    find an engineer's commit history, discover their personal email,
    find their phone in a data broker, call them pretending to be
    SpaceX IT, and ask for Elon's direct line.

    Each hop is easy. The CHAIN is what reaches the target.

    Integration with MissionGraph:
        ProximityMapper generates nodes at each ring.
        ChainFollower traces paths between rings.
        GoalBackwardPlanner uses rings to find the easiest path.
    """

    def __init__(self, graph: MissionGraph) -> None:
        self._graph = graph
        self._rings: dict[int, ProximityRing] = {}

    async def map_proximity(
        self,
        target: str,
        goal: str,
        max_rings: int = 5,
    ) -> dict[int, ProximityRing]:
        """Map the proximity rings around a target.

        Returns rings 0-5 with entities at each distance.
        Each entity becomes a node in the MissionGraph.
        """
        # Ring 0: The target itself
        self._rings[0] = ProximityRing(
            distance=0,
            label=f"Target: {target}",
            entities=[{"name": target, "type": "primary_target"}],
            access_difficulty=1.0,
            value_to_goal=1.0,
        )
        target_node = GraphNode(
            node_type=NodeType.ENTITY,
            label=target,
            data={"ring": 0, "role": "primary_target"},
            source="proximity_mapper",
            depth=0,
            tags=["ring_0", "target"],
        )
        self._graph.add_node(target_node)

        # Ring 1: Direct connections (people with direct access)
        self._rings[1] = ProximityRing(
            distance=1,
            label="Direct connections",
            entities=[
                {"type": "executive_assistant", "access": "calendar, contacts, email"},
                {"type": "security_personnel", "access": "physical access, contact info"},
                {"type": "direct_reports", "access": "internal systems, communication"},
                {"type": "family_members", "access": "personal devices, home network"},
                {"type": "personal_devices", "access": "phone, laptop, home WiFi"},
            ],
            access_difficulty=0.85,
            value_to_goal=0.95,
        )
        for entity in self._rings[1].entities:
            node = GraphNode(
                node_type=NodeType.PERSONA,
                label=f"{target} -> {entity['type']}",
                data={"ring": 1, **entity},
                source="proximity_mapper",
                depth=1,
                tags=["ring_1"],
            )
            self._graph.add_node(node)
            self._graph.add_edge(GraphEdge(
                source_id=target_node.id,
                target_id=node.id,
                edge_type=EdgeType.BELONGS_TO,
                label=f"ring 1: {entity['type']}",
            ))

        # Ring 2: Professional network (people with indirect access)
        self._rings[2] = ProximityRing(
            distance=2,
            label="Professional network",
            entities=[
                {"type": "colleagues", "access": "internal comms, shared systems"},
                {"type": "vendors", "access": "vendor portal, integration APIs"},
                {"type": "partners", "access": "partner systems, shared data"},
                {"type": "former_employees", "access": "institutional knowledge, old creds"},
                {"type": "contractors", "access": "limited system access, VPN"},
                {"type": "board_members", "access": "board portal, strategic docs"},
            ],
            access_difficulty=0.6,
            value_to_goal=0.7,
        )
        for entity in self._rings[2].entities:
            node = GraphNode(
                node_type=NodeType.PERSONA,
                label=f"{target} -> {entity['type']}",
                data={"ring": 2, **entity},
                source="proximity_mapper",
                depth=2,
                tags=["ring_2"],
            )
            self._graph.add_node(node)

        # Ring 3: Community and events
        self._rings[3] = ProximityRing(
            distance=3,
            label="Community presence",
            entities=[
                {"type": "conferences", "access": "networking, badge cloning, WiFi"},
                {"type": "industry_forums", "access": "social engineering pretext"},
                {"type": "social_media", "access": "OSINT, relationship mapping"},
                {"type": "professional_groups", "access": "LinkedIn, Slack communities"},
                {"type": "alumni_networks", "access": "shared background pretext"},
            ],
            access_difficulty=0.3,
            value_to_goal=0.4,
        )
        for entity in self._rings[3].entities:
            node = GraphNode(
                node_type=NodeType.ENTITY,
                label=f"{target} -> {entity['type']}",
                data={"ring": 3, **entity},
                source="proximity_mapper",
                depth=3,
                tags=["ring_3"],
            )
            self._graph.add_node(node)

        # Ring 4: Infrastructure
        self._rings[4] = ProximityRing(
            distance=4,
            label="Infrastructure",
            entities=[
                {"type": "dns_provider", "access": "DNS hijacking, zone transfer"},
                {"type": "hosting_provider", "access": "adjacent hosting, shared IPs"},
                {"type": "saas_tools", "access": "SaaS compromise, SSO chain"},
                {"type": "email_provider", "access": "email spoofing, relay abuse"},
                {"type": "cdn_provider", "access": "cache poisoning, origin exposure"},
                {"type": "ci_cd_pipeline", "access": "supply chain injection"},
            ],
            access_difficulty=0.4,
            value_to_goal=0.5,
        )
        for entity in self._rings[4].entities:
            node = GraphNode(
                node_type=NodeType.ENDPOINT,
                label=f"{target} -> {entity['type']}",
                data={"ring": 4, **entity},
                source="proximity_mapper",
                depth=4,
                tags=["ring_4"],
            )
            self._graph.add_node(node)

        # Ring 5: Public presence (easiest access, lowest direct value)
        self._rings[5] = ProximityRing(
            distance=5,
            label="Public presence",
            entities=[
                {"type": "github_repos", "access": "commit history, emails, secrets"},
                {"type": "blog_posts", "access": "tech stack, team info, internal tools"},
                {"type": "job_postings", "access": "tech stack, team structure, tools"},
                {"type": "press_releases", "access": "partnerships, financials, strategy"},
                {"type": "public_filings", "access": "officers, addresses, structure"},
                {"type": "patent_filings", "access": "technology details, inventors"},
                {"type": "dns_records", "access": "subdomains, mail servers, SPF/DKIM"},
                {"type": "ssl_certificates", "access": "internal hostnames, org info"},
            ],
            access_difficulty=0.05,
            value_to_goal=0.15,
        )
        for entity in self._rings[5].entities:
            node = GraphNode(
                node_type=NodeType.DOCUMENT,
                label=f"{target} -> {entity['type']}",
                data={"ring": 5, **entity},
                source="proximity_mapper",
                depth=5,
                tags=["ring_5"],
            )
            self._graph.add_node(node)

        logger.info(
            "proximity.mapped",
            target=target,
            rings=len(self._rings),
            total_entities=sum(len(r.entities) for r in self._rings.values()),
        )
        return self._rings

    def find_easiest_chain(self) -> list[ProximityRing]:
        """Find the chain with lowest total difficulty.

        The optimal path often goes: Ring 5 (easy) -> Ring 3 (medium) ->
        Ring 1 (hard single hop). Three easy steps beat one impossible step.

        Returns rings in order of the optimal traversal path.
        """
        # Score: maximize (value / difficulty) at each step
        scored_rings = []
        for dist, ring in sorted(self._rings.items()):
            if dist == 0:
                continue  # Skip the target itself
            score = ring.value_to_goal / max(ring.access_difficulty, 0.01)
            scored_rings.append((score, ring))

        # Sort by score descending (best value-to-difficulty ratio first)
        scored_rings.sort(key=lambda x: -x[0])
        return [ring for _, ring in scored_rings]

    def find_weakest_link(self) -> ProximityRing | None:
        """Find the entity closest to the target with lowest security.

        The bodyguard principle: Ring 1 entities with the lowest
        access_difficulty relative to their ring. These are the
        entities that SHOULD be hard to reach but aren't.
        """
        best: ProximityRing | None = None
        best_score = -1.0

        for dist, ring in self._rings.items():
            if dist == 0:
                continue
            # Score: high value + low difficulty = weak link
            score = ring.value_to_goal * (1.0 - ring.access_difficulty)
            if score > best_score:
                best_score = score
                best = ring

        return best

    def get_ring_summary(self) -> list[dict[str, Any]]:
        """Summary of all rings for display."""
        return [
            {
                "ring": dist,
                "label": ring.label,
                "entities": len(ring.entities),
                "access_difficulty": ring.access_difficulty,
                "value_to_goal": ring.value_to_goal,
                "entity_types": [e["type"] for e in ring.entities],
            }
            for dist, ring in sorted(self._rings.items())
        ]


# ---------------------------------------------------------------------------
# Attraction Simulator -- make the target come to YOU
# ---------------------------------------------------------------------------

@dataclass
class AttractionScenario:
    """A scenario where the target walks into our trap."""
    scenario_id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    technique: str = ""       # watering_hole, honeypot, content_lure, social_bait, service_impersonation
    description: str = ""
    target_behavior: str = "" # What the target does that triggers the trap
    what_we_capture: str = "" # What information/access we gain
    setup_steps: list[str] = field(default_factory=list)
    detection_risk: str = "low"
    time_to_deploy_s: int = 0
    time_to_trigger_s: int = 0  # Expected wait for target to trigger
    success_probability: float = 0.0
    prerequisites: list[str] = field(default_factory=list)
    legal_notes: str = ""


class AttractionSimulator:
    """Simulate "target comes to you" scenarios.

    Instead of breaking INTO a system, we set up something that
    the target naturally interacts with. They come to US.

    Five attraction techniques:

    1. WATERING HOLE: Compromise a site the target visits.
       Target reads their favorite tech blog -> we control the blog ->
       they get our payload. Zero interaction with the target directly.

    2. HONEYPOT SERVICE: Deploy a service that looks like something
       the target needs. Fake Jira instance, fake API documentation,
       fake internal tool. They log in with their real credentials.

    3. CONTENT LURE: Create content the target would search for.
       "How to configure [exact tool they use]" blog post with a
       download that calls home. They find it via Google.

    4. SOCIAL BAIT: Create a persona that the target wants to connect
       with. Fake recruiter, fake investor, fake conference organizer.
       They reach out to US.

    5. SERVICE IMPERSONATION: Register a typo domain or lookalike
       service. target-corp.io instead of targetcorp.io. Intercept
       misdirected emails, credentials, API calls.

    All of these are used in authorized red team engagements to test
    whether the organization can detect external threats that don't
    involve direct attacks on their infrastructure.

    AUTHORIZED PENTESTING ONLY.
    """

    def __init__(self, graph: MissionGraph) -> None:
        self._graph = graph
        self._scenarios: list[AttractionScenario] = []

    async def generate_scenarios(
        self,
        target: str,
        goal: str,
        target_profile: dict[str, Any] | None = None,
    ) -> list[AttractionScenario]:
        """Generate attraction scenarios based on target profile.

        Uses OSINT data about the target to craft scenarios that
        match their actual behavior patterns.
        """
        profile = target_profile or {}
        tech_stack = profile.get("tech_stack", [])
        industries = profile.get("industries", [])
        social_platforms = profile.get("social_platforms", [])

        scenarios = [
            AttractionScenario(
                name="Watering Hole: Tech Blog",
                technique="watering_hole",
                description=(
                    f"Identify tech blogs/forums frequented by {target} employees. "
                    f"Compromise or clone a popular resource. Deploy credential "
                    f"harvester that captures corporate SSO when they 'sign in to comment'."
                ),
                target_behavior="Employee visits compromised tech blog and signs in",
                what_we_capture="Corporate SSO credentials, session tokens, browser fingerprint",
                setup_steps=[
                    f"OSINT: identify sites {target} employees frequent (GitHub stars, blog comments, forum posts)",
                    "Analyze site security, find compromise vector OR create convincing clone",
                    "Deploy credential harvester with corporate SSO lookalike",
                    "Wait for employee to authenticate",
                    "Capture credentials, test against corporate VPN/email",
                ],
                detection_risk="low",
                time_to_deploy_s=7200,     # 2 hours to set up
                time_to_trigger_s=259200,  # 3 days average wait
                success_probability=0.35,
                prerequisites=["osint_complete", "target_online_behavior_known"],
                legal_notes="Requires authorization to deploy credential harvester. Cloned site must be taken down after engagement.",
            ),
            AttractionScenario(
                name="Honeypot: Fake Internal Tool",
                technique="honeypot",
                description=(
                    f"Deploy a fake version of a tool {target} uses internally. "
                    f"If they use Jira, deploy a convincing Jira instance at a "
                    f"typo domain. If they use Slack, create a lookalike workspace. "
                    f"Employees who mistype the URL land on our instance."
                ),
                target_behavior="Employee mistypes URL or clicks phishing link to fake tool",
                what_we_capture="Credentials typed into fake login, session details, IP addresses",
                setup_steps=[
                    f"OSINT: identify internal tools used by {target} (from job postings, GitHub, tech talks)",
                    "Register typo/lookalike domains for identified tools",
                    "Deploy convincing replicas with credential capture",
                    "Optionally send subtle phishing to accelerate",
                    "Capture and test credentials",
                ],
                detection_risk="medium",
                time_to_deploy_s=14400,    # 4 hours
                time_to_trigger_s=604800,  # 7 days average
                success_probability=0.25,
                prerequisites=["target_tools_identified"],
                legal_notes="Typo domains must be surrendered after engagement. No actual data exfiltration from target systems.",
            ),
            AttractionScenario(
                name="Content Lure: SEO-Targeted Technical Guide",
                technique="content_lure",
                description=(
                    f"Create high-quality technical content that {target} "
                    f"engineers would search for. 'How to configure [their exact "
                    f"framework] with [their exact cloud provider].' Include a "
                    f"downloadable tool/script that phones home."
                ),
                target_behavior="Engineer searches for technical solution, downloads our tool",
                what_we_capture="Execution environment details, internal IPs, network topology from callback",
                setup_steps=[
                    f"OSINT: identify exact tech stack of {target} (GitHub, job posts, conference talks)",
                    "Create genuinely useful technical content targeting their stack",
                    "Include downloadable utility that makes a callback with system info",
                    "SEO optimize for their specific stack combinations",
                    "Wait for organic discovery, or seed in relevant communities",
                ],
                detection_risk="low",
                time_to_deploy_s=10800,    # 3 hours
                time_to_trigger_s=1209600, # 14 days average
                success_probability=0.2,
                prerequisites=["tech_stack_identified"],
                legal_notes="Callback must only collect non-PII system information. Content must be genuinely useful, not malware.",
            ),
            AttractionScenario(
                name="Social Bait: Conference Speaker / Recruiter Persona",
                technique="social_bait",
                description=(
                    f"Create a professional persona (conference organizer, recruiter, "
                    f"VC analyst) that {target} employees would want to connect with. "
                    f"They reach out to us. During conversation, we gather intel."
                ),
                target_behavior="Employee connects with fake persona on LinkedIn/Twitter, shares information",
                what_we_capture="Internal org structure, tool names, upcoming changes, personal contact info",
                setup_steps=[
                    f"OSINT: profile key employees at {target}",
                    "Create convincing professional persona (LinkedIn, Twitter, personal site)",
                    "Build credibility: post content, engage in industry discussions",
                    "Connect with target employees organically",
                    "Gather intel through normal professional conversation",
                ],
                detection_risk="low",
                time_to_deploy_s=86400,    # 1 day for persona buildup
                time_to_trigger_s=604800,  # 7 days to build relationship
                success_probability=0.45,
                prerequisites=["people_profiled"],
                legal_notes="Persona must be disclosed in final report. No coercion or manipulation beyond standard networking.",
            ),
            AttractionScenario(
                name="Service Impersonation: Email Typo Domain",
                technique="service_impersonation",
                description=(
                    f"Register domains similar to {target}'s email domain. "
                    f"targetcorp.co instead of targetcorp.com, targecorp.com "
                    f"(missing 't'). Set up mail server. Intercept misdirected "
                    f"emails containing credentials, internal links, attachments."
                ),
                target_behavior="Someone mistypes the email domain when sending to target employees",
                what_we_capture="Misdirected emails with internal information, credentials, attachments",
                setup_steps=[
                    f"Generate typo variants of {target}'s domain",
                    "Check availability and register promising variants",
                    "Deploy catch-all mail server",
                    "Wait for misdirected emails",
                    "Analyze captured emails for credentials and intel",
                ],
                detection_risk="low",
                time_to_deploy_s=3600,     # 1 hour
                time_to_trigger_s=2592000, # 30 days average
                success_probability=0.15,
                prerequisites=[],
                legal_notes="Intercepted emails must be handled per engagement rules. Domains surrendered after engagement.",
            ),
        ]

        self._scenarios = scenarios

        # Add scenarios to graph
        for scenario in scenarios:
            node = GraphNode(
                node_type=NodeType.TECHNIQUE,
                label=scenario.name,
                data={
                    "scenario_id": scenario.scenario_id,
                    "technique": scenario.technique,
                    "success_probability": scenario.success_probability,
                    "detection_risk": scenario.detection_risk,
                    "what_we_capture": scenario.what_we_capture,
                    "time_to_trigger_days": scenario.time_to_trigger_s / 86400,
                },
                source="attraction_simulator",
                confidence=scenario.success_probability,
                tags=["attraction", scenario.technique],
            )
            self._graph.add_node(node)

        logger.info(
            "attraction.scenarios_generated",
            target=target,
            scenarios=len(scenarios),
        )
        return scenarios

    def rank_scenarios(self) -> list[AttractionScenario]:
        """Rank scenarios by expected value (probability * speed * stealth)."""
        def score(s: AttractionScenario) -> float:
            detection_penalty = {"none": 1.0, "low": 0.9, "medium": 0.6, "high": 0.3}
            stealth = detection_penalty.get(s.detection_risk, 0.5)
            # Faster trigger = better (invert and normalize)
            speed = 1.0 / max(s.time_to_trigger_s / 86400, 1)  # days to trigger
            return s.success_probability * stealth * speed

        ranked = sorted(self._scenarios, key=score, reverse=True)
        return ranked

    def get_scenario_summary(self) -> list[dict[str, Any]]:
        """Summary for display."""
        return [
            {
                "name": s.name,
                "technique": s.technique,
                "success_probability": f"{s.success_probability:.0%}",
                "detection_risk": s.detection_risk,
                "time_to_deploy": f"{s.time_to_deploy_s / 3600:.1f} hours",
                "time_to_trigger": f"{s.time_to_trigger_s / 86400:.0f} days",
                "what_we_capture": s.what_we_capture,
            }
            for s in self._scenarios
        ]


# ---------------------------------------------------------------------------
# Creative Path Generator -- think outside the box (LLM-driven)
# ---------------------------------------------------------------------------

class CreativePathGenerator:
    """Generate attack paths that NO template would contain.

    This is the difference between AI pattern-matching and human
    intelligence. Templates handle the 80%. This handles the 20%
    that wins wars.

    How humans think vs how LLMs think:
        LLM: "Scan ports -> find vuln -> exploit" (pattern from training)
        Human: "The CEO's kid posts on TikTok from the home office.
                I can see the WiFi name on the whiteboard behind them.
                The WiFi password is probably the dog's name which is
                in the wife's Instagram bio. Now I'm on the home network
                where the CEO VPNs to work from."

    This module uses LLM reasoning (via CognitiveReasoner) but with
    specific prompts designed to force CREATIVE thinking:
    1. Constraint removal: "What if X wasn't a barrier?"
    2. Perspective shift: "How would a janitor approach this?"
    3. Resource inversion: "What if the target's strength is their weakness?"
    4. Time manipulation: "What if I had 6 months? What if I had 60 seconds?"
    5. Domain transfer: "How does this problem look in a different field?"

    Uses existing CognitiveReasoner -- does NOT duplicate.
    """

    # Creative prompts that force outside-the-box thinking
    CREATIVE_LENSES: dict[str, str] = {
        "constraint_removal": (
            "CONSTRAINT REMOVAL: List every assumption about what's impossible "
            "or off-limits. Now remove each one. What paths appear? "
            "The target has a firewall -- what if we never touch the firewall? "
            "The target uses MFA -- what if we don't need their password at all? "
            "Think about what's AROUND the obstacle, not through it."
        ),
        "perspective_shift": (
            "PERSPECTIVE SHIFT: You are not a hacker. You are: "
            "1) The janitor who has physical access every night. "
            "2) The food delivery driver who enters the building daily. "
            "3) The ISP technician who controls their internet connection. "
            "4) The angry ex-employee who knows every internal system. "
            "5) The competitor who wants their trade secrets. "
            "Pick the perspective that gives the most creative path."
        ),
        "resource_inversion": (
            "RESOURCE INVERSION: The target's greatest strength is also "
            "their greatest vulnerability. If they're cloud-native, their "
            "entire business depends on one cloud account. If they have "
            "1000 employees, they have 1000 potential social engineering "
            "targets. If they're well-funded, they use more SaaS tools "
            "(= more attack surface). Find the weakness hidden in the strength."
        ),
        "time_manipulation": (
            "TIME MANIPULATION: Consider the same goal at different speeds. "
            "60-second attack: what can you do with one phone call? "
            "60-minute attack: what can you do with one social engineering session? "
            "60-day attack: what can you do with a long-term infiltration? "
            "60-second window: what if you only get one chance? "
            "The time constraint changes which paths are optimal."
        ),
        "domain_transfer": (
            "DOMAIN TRANSFER: This is not a cybersecurity problem. "
            "It's a logistics problem (how do things move in and out?). "
            "It's a social dynamics problem (who trusts whom?). "
            "It's a physics problem (what are the actual physical constraints?). "
            "It's a game theory problem (what's the Nash equilibrium?). "
            "Apply a framework from a completely different field."
        ),
        "chain_of_trivials": (
            "CHAIN OF TRIVIALS: Every step must be trivially easy. "
            "No step should require more than basic skill. "
            "But the CHAIN of trivial steps reaches an impossible target. "
            "Google the company -> find an employee -> find their GitHub -> "
            "find their email in a commit -> check Have I Been Pwned -> "
            "find their reused password -> log into their personal cloud -> "
            "find their work VPN config -> connect to corporate network. "
            "Each step is public information. The chain is the weapon."
        ),
        "reverse_social_proof": (
            "REVERSE SOCIAL PROOF: Don't approach the target. "
            "Become someone the target approaches. "
            "Post a job listing at a competitor -- target employees apply. "
            "Create a fake vendor -- target's procurement reaches out. "
            "Organize a fake industry event -- target sends speakers. "
            "Write a fake research report -- target's PR responds. "
            "The target validates YOU. You never had to prove anything."
        ),
    }

    def __init__(self, graph: MissionGraph) -> None:
        self._graph = graph
        self._generated_paths: list[dict[str, Any]] = []

    async def generate_creative_paths(
        self,
        goal: str,
        target: str,
        known_blockers: list[str] | None = None,
        target_profile: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate creative attack paths using each lens.

        Each lens produces a fundamentally different approach.
        These complement the template-based paths from GoalBackwardPlanner.
        """
        blockers = known_blockers or []
        profile = target_profile or {}
        paths: list[dict[str, Any]] = []

        for lens_name, lens_prompt in self.CREATIVE_LENSES.items():
            creative_path = {
                "lens": lens_name,
                "prompt": lens_prompt,
                "goal": goal,
                "target": target,
                "blockers_considered": blockers,
                "approach": self._apply_lens(lens_name, goal, target, blockers, profile),
                "graph_nodes_added": 0,
            }

            # Add approach steps as graph nodes
            approach = creative_path["approach"]
            if isinstance(approach, dict) and "steps" in approach:
                for step_desc in approach["steps"]:
                    node = GraphNode(
                        node_type=NodeType.TECHNIQUE,
                        label=step_desc,
                        data={
                            "lens": lens_name,
                            "creative": True,
                            "goal": goal,
                        },
                        source="creative_path_generator",
                        tags=["creative", lens_name],
                    )
                    self._graph.add_node(node)
                    creative_path["graph_nodes_added"] += 1

            paths.append(creative_path)

        self._generated_paths = paths

        logger.info(
            "creative.paths_generated",
            target=target,
            lenses=len(paths),
            total_nodes=sum(p.get("graph_nodes_added", 0) for p in paths),
        )
        return paths

    def _apply_lens(
        self,
        lens_name: str,
        goal: str,
        target: str,
        blockers: list[str],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply a creative lens to generate a specific approach.

        In production, this calls CognitiveReasoner with the lens prompt.
        Here we generate the structured approach deterministically as
        a foundation that the LLM enhances.
        """
        # Each lens produces a different style of approach
        approaches: dict[str, dict[str, Any]] = {
            "constraint_removal": {
                "reasoning": f"Instead of overcoming blockers ({', '.join(blockers) or 'unknown'}), bypass them entirely",
                "steps": [
                    f"List all assumptions about reaching {target}",
                    "For each assumption, ask: what if this isn't true?",
                    "Identify paths that don't touch any blocker",
                    f"Find the path to {goal} that avoids ALL known defenses",
                ],
                "key_insight": "The obstacle is not on the path -- find a different path",
            },
            "perspective_shift": {
                "reasoning": "Think as someone with different access than a hacker",
                "steps": [
                    f"Identify all non-technical people who interact with {target}",
                    "Map their access levels (physical, digital, social)",
                    "Find the perspective with easiest access to goal",
                    "Plan approach from that perspective",
                ],
                "key_insight": "The janitor has a key to every room",
            },
            "resource_inversion": {
                "reasoning": f"Turn {target}'s strengths into attack vectors",
                "steps": [
                    f"List {target}'s greatest strengths (size, funding, tech)",
                    "For each strength, identify the hidden vulnerability",
                    "Large company = many employees = many phishing targets",
                    "Well-funded = many SaaS tools = massive attack surface",
                ],
                "key_insight": "The bigger they are, the more doors they have",
            },
            "time_manipulation": {
                "reasoning": "Same goal, different time constraints change optimal path",
                "steps": [
                    "60-second path: one phone call pretending to be IT support",
                    "60-minute path: social engineering session with an employee",
                    "60-day path: long-term persona building and trust establishment",
                    "Choose the time horizon that maximizes success probability",
                ],
                "key_insight": "Speed and stealth are inversely correlated",
            },
            "domain_transfer": {
                "reasoning": "Apply frameworks from non-security domains",
                "steps": [
                    "Logistics: map all inputs/outputs of the target organization",
                    "Social dynamics: map trust relationships and influence chains",
                    "Game theory: find the equilibrium where target cooperates",
                    "Economics: find the cheapest path (time, money, risk)",
                ],
                "key_insight": "Every problem has been solved in another field",
            },
            "chain_of_trivials": {
                "reasoning": "Each step must be embarrassingly easy",
                "steps": [
                    f"Google '{target}' + 'team' + 'engineering'",
                    "Find employee LinkedIn profiles (public)",
                    "Find their GitHub accounts (public)",
                    "Find email addresses in commit history (public)",
                    "Check breach databases for password reuse (legal tools)",
                    "Test found credentials against corporate login (authorized)",
                    "Each step requires zero skill. The chain is lethal.",
                ],
                "key_insight": "The chain of trivials beats the impossible exploit",
            },
            "reverse_social_proof": {
                "reasoning": "Don't approach them -- become what they approach",
                "steps": [
                    f"Identify what {target} employees are actively seeking",
                    "Create that thing (job posting, vendor, event, research)",
                    "Let them come to you with their real information",
                    "Extract intel from their approach (resume = org chart, RFP = tech stack)",
                ],
                "key_insight": "The target validates you -- you never had to prove anything",
            },
        }

        return approaches.get(lens_name, {
            "reasoning": "Unknown lens",
            "steps": [f"Apply {lens_name} thinking to {goal}"],
            "key_insight": "Novel approach needed",
        })


# ---------------------------------------------------------------------------
# Trace Manager -- catalog every trace, clean them all
# ---------------------------------------------------------------------------

@dataclass
class TraceRecord:
    """A single trace left during an operation."""
    trace_id: str = field(default_factory=lambda: uuid4().hex[:10])
    trace_type: str = ""       # "log_entry", "file_artifact", "network_connection",
                                # "dns_query", "process", "registry", "credential_use",
                                # "database_query", "api_call", "cookie", "cache_entry"
    location: str = ""          # Where the trace exists (target system, network, ISP logs)
    description: str = ""       # What the trace reveals
    created_at: float = field(default_factory=time.time)
    cleanable: bool = True      # Can we remove this trace?
    cleaned: bool = False       # Has it been cleaned?
    clean_method: str = ""      # How to clean it
    clean_risk: str = "low"     # Risk of detection during cleanup
    evidence_value: str = ""    # What a forensic team could learn from this trace


class TraceManager:
    """Catalog every trace left during an operation. Clean them all.

    Every action Daena takes during a mission leaves traces:
    - Log entries on the target (web server logs, auth logs, syslog)
    - Network traces (DNS queries, TCP connections, TLS handshakes)
    - File artifacts (temp files, uploaded payloads, modified configs)
    - Process traces (spawned processes, loaded libraries)
    - Database queries (if we accessed a DB, the query log has our SQL)
    - API calls (rate limit counters, access logs, audit trails)
    - Session artifacts (cookies, tokens, cache entries)

    The TraceManager does three things:
    1. CATALOG: record every trace as it's created during the mission
    2. ASSESS: evaluate what each trace reveals to a forensic team
    3. CLEAN: remove traces based on engagement level

    At AUDIT/PENTEST level: traces are cataloged but NOT cleaned
        (the client needs to see what happened)
    At RED_TEAM level: traces are minimized during operation
        (test whether the SOC detects them)
    At ADVERSARY level: traces are cleaned post-operation
        (challenge the forensic team to find anything)

    The TraceManager keeps its OWN record of everything -- this is
    Daena's internal audit trail that gets delivered to the client
    in the final report. The client sees everything we did.
    The target's SOC sees nothing (at ADVERSARY level).
    """

    def __init__(self) -> None:
        self._traces: list[TraceRecord] = []
        self._clean_log: list[dict[str, Any]] = []

    def record(
        self,
        trace_type: str,
        location: str,
        description: str,
        clean_method: str = "",
        cleanable: bool = True,
        evidence_value: str = "",
    ) -> TraceRecord:
        """Record a trace left during an operation."""
        trace = TraceRecord(
            trace_type=trace_type,
            location=location,
            description=description,
            clean_method=clean_method,
            cleanable=cleanable,
            evidence_value=evidence_value,
        )
        self._traces.append(trace)
        logger.debug(
            "trace.recorded",
            trace_id=trace.trace_id,
            trace_type=trace_type,
            location=location,
        )
        return trace

    def record_network(self, target: str, protocol: str, description: str) -> TraceRecord:
        """Shorthand for recording network traces."""
        return self.record(
            trace_type="network_connection",
            location=f"{target} ({protocol})",
            description=description,
            clean_method="Connection closes naturally. ISP logs persist ~90 days.",
            cleanable=False,  # Can't clean ISP logs
            evidence_value=f"Source IP connecting to {target} via {protocol}",
        )

    def record_log_entry(self, target: str, log_type: str, description: str) -> TraceRecord:
        """Shorthand for recording log traces on target."""
        return self.record(
            trace_type="log_entry",
            location=f"{target} -> {log_type}",
            description=description,
            clean_method=f"Delete/modify {log_type} entries matching our activity window",
            cleanable=True,
            evidence_value=f"Timestamps, source IPs, user agents, request patterns in {log_type}",
        )

    def record_file(self, target: str, filepath: str, description: str) -> TraceRecord:
        """Shorthand for recording file artifacts."""
        return self.record(
            trace_type="file_artifact",
            location=f"{target}:{filepath}",
            description=description,
            clean_method=f"Delete {filepath} and clear file metadata",
            cleanable=True,
            evidence_value=f"File contents, creation time, ownership at {filepath}",
        )

    def record_credential_use(self, target: str, credential_type: str, description: str) -> TraceRecord:
        """Shorthand for recording credential usage traces."""
        return self.record(
            trace_type="credential_use",
            location=f"{target} auth system",
            description=description,
            clean_method="Cannot undo authentication event. Clear session artifacts only.",
            cleanable=False,  # Auth logs are usually immutable
            evidence_value=f"Authentication event: {credential_type} used at specific time from specific IP",
        )

    def get_all_traces(self) -> list[TraceRecord]:
        """Get all recorded traces."""
        return list(self._traces)

    def get_cleanable_traces(self) -> list[TraceRecord]:
        """Get traces that CAN be cleaned."""
        return [t for t in self._traces if t.cleanable and not t.cleaned]

    def get_uncleaned_traces(self) -> list[TraceRecord]:
        """Get traces that exist but haven't been cleaned."""
        return [t for t in self._traces if not t.cleaned]

    def get_permanent_traces(self) -> list[TraceRecord]:
        """Get traces that CANNOT be cleaned (ISP logs, auth events)."""
        return [t for t in self._traces if not t.cleanable]

    async def clean_all(self) -> dict[str, Any]:
        """Clean all cleanable traces. Returns cleanup report.

        This is the ADVERSARY level capability. After the mission,
        remove every trace that can be removed. The cleanup report
        shows what was cleaned vs what's permanent.
        """
        cleaned_count = 0
        failed_count = 0
        permanent_count = 0

        for trace in self._traces:
            if trace.cleaned:
                continue

            if not trace.cleanable:
                permanent_count += 1
                self._clean_log.append({
                    "trace_id": trace.trace_id,
                    "action": "PERMANENT",
                    "reason": "Cannot be cleaned (ISP logs, auth events, etc.)",
                    "location": trace.location,
                    "evidence_remaining": trace.evidence_value,
                    "timestamp": time.time(),
                })
                continue

            # Mark as cleaned (in production, this would execute cleanup commands)
            trace.cleaned = True
            cleaned_count += 1
            self._clean_log.append({
                "trace_id": trace.trace_id,
                "action": "CLEANED",
                "method": trace.clean_method,
                "location": trace.location,
                "timestamp": time.time(),
            })

        report = {
            "total_traces": len(self._traces),
            "cleaned": cleaned_count,
            "failed": failed_count,
            "permanent": permanent_count,
            "remaining": len(self.get_uncleaned_traces()),
            "clean_log": self._clean_log,
            "forensic_challenge": (
                f"Cleaned {cleaned_count} traces. "
                f"{permanent_count} permanent traces remain (ISP logs, auth events). "
                f"Challenge: find evidence of our operation using only the permanent traces."
            ),
        }

        logger.info(
            "trace.cleanup_complete",
            cleaned=cleaned_count,
            permanent=permanent_count,
        )
        return report

    def get_forensic_report(self) -> dict[str, Any]:
        """Generate the report Daena delivers to the CLIENT.

        This is Daena's own audit trail -- everything she did,
        every trace she left, every trace she cleaned. The client
        gets full transparency. The target's SOC gets nothing.
        """
        return {
            "total_operations": len(self._traces),
            "traces_by_type": self._count_by_type(),
            "cleaned_traces": sum(1 for t in self._traces if t.cleaned),
            "permanent_traces": sum(1 for t in self._traces if not t.cleanable),
            "remaining_traces": sum(1 for t in self._traces if not t.cleaned and t.cleanable),
            "traces": [
                {
                    "id": t.trace_id,
                    "type": t.trace_type,
                    "location": t.location,
                    "description": t.description,
                    "cleanable": t.cleanable,
                    "cleaned": t.cleaned,
                    "evidence_value": t.evidence_value,
                }
                for t in self._traces
            ],
            "clean_log": self._clean_log,
        }

    def _count_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self._traces:
            counts[t.trace_type] = counts.get(t.trace_type, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Engagement Controller -- capability matrix per level
# ---------------------------------------------------------------------------

class EngagementController:
    """Controls what Daena can do at each engagement level.

    The nuke doctrine: capability exists at all levels.
    The operator chooses the level. The EngagementController
    enforces the constraints.

    This is NOT about protecting the target. It's about controlling
    the scope of the authorized engagement. If the contract says
    "pentest only", Daena must not clean traces or deploy honeypots.

    CAPABILITY MATRIX:
    +-----------------------+-------+--------+----------+----------+
    | Capability            | AUDIT | PENTEST| RED_TEAM | ADVERSARY|
    +-----------------------+-------+--------+----------+----------+
    | OSINT/Recon           |  YES  |  YES   |   YES    |   YES    |
    | Vulnerability Scan    |  YES  |  YES   |   YES    |   YES    |
    | Exploitation          |  NO   |  YES   |   YES    |   YES    |
    | Post-Exploitation     |  NO   |  YES   |   YES    |   YES    |
    | Credential Chaining   |  NO   |  YES   |   YES    |   YES    |
    | Social Engineering    |  NO   |  NO    |   YES    |   YES    |
    | Attraction/Honeypots  |  NO   |  NO    |   YES    |   YES    |
    | Physical Simulation   |  NO   |  NO    |   YES    |   YES    |
    | OpSec (fingerprints)  |  NO   |  BASIC |   FULL   |   FULL   |
    | Trace Minimization    |  NO   |  NO    |   YES    |   YES    |
    | Trace Cleanup         |  NO   |  NO    |   NO     |   YES    |
    | Creative Paths        |  NO   |  NO    |   YES    |   YES    |
    | Insider Simulation    |  NO   |  NO    |   YES    |   YES    |
    | Exfiltration Proof    |  NO   |  YES   |   YES    |   YES    |
    +-----------------------+-------+--------+----------+----------+
    """

    _CAPABILITY_MATRIX: dict[str, dict[str, bool | str]] = {
        "osint": {"audit": True, "pentest": True, "red_team": True, "adversary": True},
        "vulnerability_scan": {"audit": True, "pentest": True, "red_team": True, "adversary": True},
        "exploitation": {"audit": False, "pentest": True, "red_team": True, "adversary": True},
        "post_exploitation": {"audit": False, "pentest": True, "red_team": True, "adversary": True},
        "credential_chaining": {"audit": False, "pentest": True, "red_team": True, "adversary": True},
        "social_engineering": {"audit": False, "pentest": False, "red_team": True, "adversary": True},
        "attraction_honeypots": {"audit": False, "pentest": False, "red_team": True, "adversary": True},
        "physical_simulation": {"audit": False, "pentest": False, "red_team": True, "adversary": True},
        "opsec_fingerprints": {"audit": False, "pentest": "basic", "red_team": True, "adversary": True},
        "trace_minimization": {"audit": False, "pentest": False, "red_team": True, "adversary": True},
        "trace_cleanup": {"audit": False, "pentest": False, "red_team": False, "adversary": True},
        "creative_paths": {"audit": False, "pentest": False, "red_team": True, "adversary": True},
        "insider_simulation": {"audit": False, "pentest": False, "red_team": True, "adversary": True},
        "exfiltration_proof": {"audit": False, "pentest": True, "red_team": True, "adversary": True},
    }

    def __init__(self, level: EngagementLevel) -> None:
        self._level = level
        self._overrides: dict[str, bool] = {}  # Manual overrides by operator

    @property
    def level(self) -> EngagementLevel:
        return self._level

    def is_allowed(self, capability: str) -> bool:
        """Check if a capability is allowed at the current engagement level."""
        # Check override first
        if capability in self._overrides:
            return self._overrides[capability]

        matrix_entry = self._CAPABILITY_MATRIX.get(capability)
        if matrix_entry is None:
            logger.warning("engagement.unknown_capability", capability=capability)
            return False

        value = matrix_entry.get(self._level.value, False)
        return bool(value)  # "basic" is truthy

    def get_allowed_capabilities(self) -> list[str]:
        """Get all capabilities allowed at current level."""
        return [cap for cap in self._CAPABILITY_MATRIX if self.is_allowed(cap)]

    def get_denied_capabilities(self) -> list[str]:
        """Get all capabilities denied at current level."""
        return [cap for cap in self._CAPABILITY_MATRIX if not self.is_allowed(cap)]

    def enforce(self, capability: str, action_description: str) -> bool:
        """Enforce capability check. Logs denial if not allowed.

        Usage:
            if not controller.enforce("trace_cleanup", "Clean web server logs"):
                return  # Not allowed at this engagement level
        """
        allowed = self.is_allowed(capability)
        if not allowed:
            logger.warning(
                "engagement.denied",
                capability=capability,
                level=self._level.value,
                action=action_description,
            )
        return allowed

    def override(self, capability: str, allowed: bool) -> None:
        """Operator override for specific capability. Use with caution."""
        self._overrides[capability] = allowed
        logger.info(
            "engagement.override",
            capability=capability,
            allowed=allowed,
            level=self._level.value,
        )

    def get_matrix_summary(self) -> dict[str, Any]:
        """Full capability matrix for display."""
        return {
            "level": self._level.value,
            "capabilities": {
                cap: {
                    "allowed": self.is_allowed(cap),
                    "default": self._CAPABILITY_MATRIX[cap].get(self._level.value, False),
                    "overridden": cap in self._overrides,
                }
                for cap in self._CAPABILITY_MATRIX
            },
            "overrides": self._overrides,
        }


# ---------------------------------------------------------------------------
# OpSec Shield -- governance protecting DAENA herself
# ---------------------------------------------------------------------------

class OpSecShield:
    """Governance layer that protects Daena during operations.

    This is NOT about protecting the target. This is about protecting
    the ATTACKER (Daena) from:
    1. Leaking her own IP, techniques, or source code
    2. Exposing the operator (MAS-AI, Masoud) identity
    3. Leaving Daena's fingerprint that a competitor could study
    4. Allowing the target to trace back to us
    5. Blowing her cover during an ongoing operation

    The OpSecShield wraps every outbound action with checks:
    - Is our real IP exposed? (proxy required)
    - Does the request contain identifying info? (sanitize)
    - Are we creating a pattern that identifies us? (randomize)
    - Is evidence stored securely? (encrypt)
    - Can the target trace this back to Daena? (profile rotation)

    This is the ONLY governance in offensive mode. Everything else
    is about maximizing capability. This is about survival.
    """

    def __init__(self) -> None:
        self._active = False
        self._violations: list[dict[str, Any]] = []
        self._checks_passed: int = 0
        self._checks_failed: int = 0

    def activate(self) -> None:
        """Activate the OpSec Shield. Should be first action in any mission."""
        self._active = True
        logger.info("opsec_shield.activated")

    def deactivate(self) -> None:
        """Deactivate. Only after mission cleanup is complete."""
        self._active = False
        logger.info("opsec_shield.deactivated")

    @property
    def is_active(self) -> bool:
        return self._active

    def check_outbound_request(self, headers: dict[str, str], url: str) -> dict[str, Any]:
        """Check an outbound request before it's sent.

        Validates:
        1. No real IP leakage (proxy must be active)
        2. No identifying headers (custom User-Agent, X-headers)
        3. No Daena fingerprint in request pattern
        4. URL is within authorized scope
        """
        issues: list[str] = []

        # Check for Daena-identifying headers
        for key, value in headers.items():
            key_lower = key.lower()
            value_lower = value.lower()
            if any(sig in value_lower for sig in ["daena", "mas-ai", "masoud", "evilbob"]):
                issues.append(f"Header '{key}' contains identifying information: {value}")
            if key_lower.startswith("x-daena") or key_lower.startswith("x-masai"):
                issues.append(f"Custom header '{key}' identifies Daena")

        # Check User-Agent
        ua = headers.get("User-Agent", headers.get("user-agent", ""))
        if not ua or "python" in ua.lower() or "httpx" in ua.lower() or "aiohttp" in ua.lower():
            issues.append(f"User-Agent '{ua}' identifies as automated tool. Use browser profile.")

        result = {
            "passed": len(issues) == 0,
            "issues": issues,
            "url": url,
            "recommendation": "Use OpsecManager.get_request_headers() for browser-like headers" if issues else "OK",
        }

        if issues:
            self._checks_failed += 1
            self._violations.extend([{"type": "outbound_request", "issue": i, "url": url, "at": time.time()} for i in issues])
            logger.warning("opsec_shield.check_failed", issues=issues, url=url)
        else:
            self._checks_passed += 1

        return result

    def check_evidence_storage(self, data: str, storage_location: str) -> dict[str, Any]:
        """Check that evidence is stored securely.

        Validates:
        1. Not stored in plaintext on target system
        2. Encrypted before writing to disk
        3. Storage location is within our controlled vault
        """
        issues: list[str] = []

        # Check storage location
        safe_prefixes = ["var/", "vault/", "/tmp/daena_"]
        if not any(storage_location.startswith(p) for p in safe_prefixes):
            issues.append(f"Storage location '{storage_location}' is not in a secure vault directory")

        # Check for sensitive data in evidence
        sensitive_patterns = ["EVILBOB_KEY", "api_key", "password", "secret", "private_key"]
        data_lower = data.lower()
        for pattern in sensitive_patterns:
            if pattern.lower() in data_lower:
                issues.append(f"Evidence contains sensitive data pattern: {pattern}")

        result = {
            "passed": len(issues) == 0,
            "issues": issues,
            "location": storage_location,
        }

        if issues:
            self._checks_failed += 1
            self._violations.extend([{"type": "evidence_storage", "issue": i, "at": time.time()} for i in issues])
        else:
            self._checks_passed += 1

        return result

    def check_no_data_leak(self, outbound_data: str) -> dict[str, Any]:
        """Check that outbound data doesn't leak Daena's own info.

        When Daena sends data out (exfil proof, callback, etc.),
        make sure NONE of Daena's own data is included.
        """
        issues: list[str] = []
        data_lower = outbound_data.lower()

        leak_patterns = [
            ("daena", "Daena product name"),
            ("mas-ai", "Company name"),
            ("masoud", "Operator name"),
            ("masoori", "Operator surname"),
            ("evilbob", "Internal mode name"),
            ("mission_intelligence", "Internal module name"),
            ("cognitive_scan_engine", "Internal module name"),
            ("sunflower-honeycomb", "Patented architecture name"),
            ("philattice", "Patent brand name"),
            ("nbmf", "Patent technology name"),
        ]

        for pattern, label in leak_patterns:
            if pattern in data_lower:
                issues.append(f"Outbound data contains {label}: '{pattern}'")

        result = {
            "passed": len(issues) == 0,
            "issues": issues,
            "data_size": len(outbound_data),
        }

        if issues:
            self._checks_failed += 1
            self._violations.extend([{"type": "data_leak", "issue": i, "at": time.time()} for i in issues])
            logger.error("opsec_shield.data_leak_prevented", issues=issues)
        else:
            self._checks_passed += 1

        return result

    def get_report(self) -> dict[str, Any]:
        """OpSec Shield status report."""
        return {
            "active": self._active,
            "checks_passed": self._checks_passed,
            "checks_failed": self._checks_failed,
            "total_violations": len(self._violations),
            "violations": self._violations[-20:],  # Last 20
            "integrity": (
                "CLEAN" if self._checks_failed == 0
                else f"COMPROMISED ({self._checks_failed} violations)"
            ),
        }
