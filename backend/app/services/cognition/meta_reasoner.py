"""MetaReasoner -- Thinks about thinking.

Charlie Munger: "To a man with only a hammer, every problem looks like a nail."

Daena has 25 frameworks. This module decides WHICH ones to apply for each
problem. It classifies the problem type, then selects the best combination
of reasoning frameworks from the latticework.

Also handles:
    - Anti-analysis-paralysis: if meta-reasoning takes too long, force action
    - Framework adoption: new frameworks can be registered dynamically
    - Track record: frameworks that worked before score higher (Dalio believability)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Problem type classification
# ---------------------------------------------------------------------------

PROBLEM_TYPES = {
    "debugging": {
        "keywords": [
            "error", "bug", "fix", "broken", "fail", "crash", "exception",
            "wrong", "issue", "not working", "problem", "trace", "stack",
        ],
        "description": "Something is broken and needs diagnosis + fix",
    },
    "creation": {
        "keywords": [
            "create", "build", "make", "generate", "write", "implement",
            "add", "new", "develop", "design", "scaffold", "set up",
        ],
        "description": "Build something new from scratch",
    },
    "deployment": {
        "keywords": [
            "deploy", "ship", "release", "publish", "push", "launch",
            "production", "staging", "docker", "cloud", "ci/cd",
        ],
        "description": "Get something running in an environment",
    },
    "security_assessment": {
        "keywords": [
            "vulnerability", "vuln", "scan", "security", "pentest", "penetration",
            "exploit", "cve", "attack", "hack", "bounty", "recon", "reconnaissance",
            "subdomain", "port scan", "nmap", "nuclei", "injection", "xss", "sqli",
        ],
        "description": "Security assessment, vulnerability scanning, or bug bounty research",
    },
    "research": {
        "keywords": [
            "find", "search", "research", "learn", "understand", "explain",
            "what is", "how does", "why", "compare", "analyze", "investigate",
        ],
        "description": "Find information or understand something",
    },
    "optimization": {
        "keywords": [
            "optimize", "improve", "faster", "better", "reduce", "increase",
            "performance", "efficient", "refactor", "clean", "simplify",
        ],
        "description": "Make something work better",
    },
    "decision": {
        "keywords": [
            "should", "choose", "decide", "which", "compare", "tradeoff",
            "option", "alternative", "evaluate", "recommend", "best",
        ],
        "description": "Choose between alternatives",
    },
    "configuration": {
        "keywords": [
            "config", "setting", "install", "setup", "configure", "connect",
            "integrate", "wire", "enable", "disable", "permission",
        ],
        "description": "Set up or configure a system",
    },
    "data": {
        "keywords": [
            "data", "csv", "json", "database", "query", "table", "report",
            "chart", "visualization", "export", "import", "transform",
        ],
        "description": "Work with data",
    },
}


# ---------------------------------------------------------------------------
# Framework mapping: problem type -> which frameworks to use
# ---------------------------------------------------------------------------

FRAMEWORK_MAP: dict[str, list[str]] = {
    # Debugging: Find root cause, invert (what causes failure?), think deep
    "debugging": [
        "five_whys",           # Toyota: drill to root cause
        "inversion",           # Munger: what would cause this to fail?
        "first_principles",    # Musk: strip away assumptions
        "constraint_analyzer", # Mythos: what constraints are real vs assumed?
    ],

    # Creation: Decompose, plan carefully, imagine failure
    "creation": [
        "first_principles",    # Musk: build from fundamental truths
        "pre_mortem",          # Klein: imagine failure before starting
        "consequence_chain",   # Marks: second-order effects
        "task_prioritizer",    # Tracy: hardest/most-important first
    ],

    # Deployment: Risk assessment, pre-mortem, know the terrain
    "deployment": [
        "pre_mortem",          # Klein: imagine deployment failure
        "consequence_chain",   # Marks: what breaks if this fails?
        "inversion",           # Munger: what would cause deployment to fail?
        "constraint_analyzer", # Mythos: what assumed constraints can we relax?
    ],

    # Research: Find what you don't know, use competence map
    "research": [
        "resource_finder",     # Einstein: know where to find, not everything
        "first_principles",    # Musk: decompose the question
        "competence_map",      # Buffett: what do we know vs not know?
    ],

    # Optimization: Pareto, simplify, second-order effects
    "optimization": [
        "task_prioritizer",    # Pareto: 20% that gives 80%
        "first_principles",    # Musk: strip to essentials
        "consequence_chain",   # Marks: unintended consequences of optimization
        "inversion",           # Munger: what would make this WORSE?
    ],

    # Decision: Multiple perspectives, believability, inversion
    "decision": [
        "inversion",           # Munger: what would cause each option to fail?
        "pre_mortem",          # Klein: imagine choosing wrong
        "consequence_chain",   # Marks: second-order effects of each choice
        "first_principles",    # Musk: what is fundamentally true about each option?
    ],

    # Configuration: Know the system, constraint analysis
    "configuration": [
        "first_principles",    # Musk: what does this system actually need?
        "constraint_analyzer", # Mythos: what constraints are flexible?
        "resource_finder",     # Einstein: find the docs/examples
    ],

    # Data: Structured analysis
    "data": [
        "first_principles",    # Musk: what question are we actually answering?
        "task_prioritizer",    # Pareto: which data matters most?
        "consequence_chain",   # Marks: what conclusions follow from this data?
    ],

    # Security: Systematic enumeration, constraint probing, depth-first testing
    "security_assessment": [
        "constraint_probe",    # Mythos: decompose constraints, find open channels
        "first_principles",    # Musk: what is the actual attack surface?
        "inversion",           # Munger: what would an attacker exploit?
        "task_prioritizer",    # Pareto: focus on high-severity findings first
    ],

    # Unknown: Start with basics
    "unknown": [
        "first_principles",    # Always safe starting point
        "resource_finder",     # Search for context
        "constraint_analyzer", # Understand the boundaries
    ],
}


# ---------------------------------------------------------------------------
# Custom (user/self-discovered) framework registry
# ---------------------------------------------------------------------------

@dataclass
class CognitiveFramework:
    """A reasoning framework (built-in or discovered)."""
    name: str
    description: str
    when_to_use: list[str]  # problem types
    steps: list[str]  # reasoning steps
    source: str = "built_in"  # built_in, discovered, user_taught
    score: float = 0.5  # 0.0-1.0 effectiveness score (Dalio believability)
    uses: int = 0
    successes: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.uses, 1)


# ---------------------------------------------------------------------------
# MetaReasoner
# ---------------------------------------------------------------------------

class MetaReasoner:
    """Selects reasoning frameworks for a given problem.

    Munger's Latticework: don't use one model. Use 25+ models from
    different fields. This class picks the right combination.

    Also supports dynamic framework registration (self-upgrade).
    """

    def __init__(self) -> None:
        self._custom_frameworks: dict[str, CognitiveFramework] = {}
        self._framework_scores: dict[str, float] = {}  # name -> believability score

    async def classify_problem(
        self,
        task: str,
        prior_failures: list[str] | None = None,
        observation: Any = None,
    ) -> str:
        """Classify a task into a problem type.

        Uses keyword matching first (fast), then LLM classification
        if ambiguous (slower but accurate).
        """
        task_lower = task.lower()

        # Score each problem type by keyword matches
        scores: dict[str, int] = {}
        for ptype, config in PROBLEM_TYPES.items():
            score = sum(1 for kw in config["keywords"] if kw in task_lower)
            if score > 0:
                scores[ptype] = score

        if not scores:
            return "unknown"

        # Pick highest scoring type
        best = max(scores, key=scores.get)  # type: ignore[arg-type]

        # If prior failures exist, we might need to re-classify
        # A "creation" task that keeps failing might actually be "debugging"
        if prior_failures and best in ("creation", "configuration"):
            # After 2+ failures, it's likely a debugging problem
            if len(prior_failures) >= 2:
                logger.info(
                    "meta_reasoner.reclassify",
                    original=best,
                    new="debugging",
                    reason="repeated_failures",
                )
                return "debugging"

        return best

    async def select_frameworks(
        self,
        problem_type: str,
        prior_failures: list[str] | None = None,
    ) -> list[str]:
        """Select the best reasoning frameworks for this problem type.

        Combines:
            1. Built-in framework map (FRAMEWORK_MAP)
            2. Custom/discovered frameworks (self-upgrade)
            3. Believability scoring (track record)
            4. Prior failure avoidance (don't reuse failed frameworks)
        """
        # Start with built-in frameworks
        frameworks = list(FRAMEWORK_MAP.get(problem_type, FRAMEWORK_MAP["unknown"]))

        # Add custom frameworks that match this problem type
        for name, cf in self._custom_frameworks.items():
            if problem_type in cf.when_to_use and name not in frameworks:
                frameworks.append(name)

        # Remove frameworks that were used in failed prior attempts
        if prior_failures:
            frameworks = [f for f in frameworks if f not in prior_failures]

        # Sort by believability score (Dalio) -- higher score = used first
        frameworks.sort(
            key=lambda f: self._framework_scores.get(f, 0.5),
            reverse=True,
        )

        # Cap at 4 frameworks (anti-analysis-paralysis)
        return frameworks[:4]

    # ------------------------------------------------------------------
    # Self-upgrade: register new frameworks
    # ------------------------------------------------------------------

    async def register_framework(self, framework: CognitiveFramework) -> None:
        """Register a new reasoning framework (discovered or user-taught).

        This is how Daena evolves -- she discovers new ways of thinking
        and adopts them if they prove effective.
        """
        self._custom_frameworks[framework.name] = framework
        self._framework_scores[framework.name] = framework.score
        logger.info(
            "meta_reasoner.framework_registered",
            name=framework.name,
            source=framework.source,
            problem_types=framework.when_to_use,
        )

    async def register_external(self, framework_data: dict[str, Any]) -> None:
        """Register a framework discovered from external research."""
        cf = CognitiveFramework(
            name=framework_data.get("name", "unknown"),
            description=framework_data.get("description", ""),
            when_to_use=framework_data.get("problem_types", ["unknown"]),
            steps=framework_data.get("steps", []),
            source="discovered",
            score=0.3,  # Start low, earn trust (Dalio believability)
        )
        await self.register_framework(cf)

    # ------------------------------------------------------------------
    # Believability scoring (Dalio)
    # ------------------------------------------------------------------

    async def update_score(self, framework_name: str, succeeded: bool) -> None:
        """Update framework believability based on outcome.

        Dalio: weight opinions by track record. A framework that works
        9/10 times is weighted higher than one that works 1/10.
        """
        if framework_name in self._custom_frameworks:
            cf = self._custom_frameworks[framework_name]
            cf.uses += 1
            if succeeded:
                cf.successes += 1
            cf.score = cf.success_rate

        # Update score map
        current = self._framework_scores.get(framework_name, 0.5)
        if succeeded:
            self._framework_scores[framework_name] = min(1.0, current + 0.05)
        else:
            self._framework_scores[framework_name] = max(0.1, current - 0.05)

    def get_all_frameworks(self) -> dict[str, Any]:
        """Return all frameworks with their scores (for debugging/display)."""
        result = {}
        for ptype, frameworks in FRAMEWORK_MAP.items():
            for f in frameworks:
                if f not in result:
                    result[f] = {
                        "score": self._framework_scores.get(f, 0.5),
                        "problem_types": [],
                        "source": "built_in",
                    }
                result[f]["problem_types"].append(ptype)

        for name, cf in self._custom_frameworks.items():
            result[name] = {
                "score": cf.score,
                "problem_types": cf.when_to_use,
                "source": cf.source,
                "uses": cf.uses,
                "successes": cf.successes,
            }

        return result
