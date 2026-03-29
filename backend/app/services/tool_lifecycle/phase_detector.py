"""Conversation Phase Detector -- zero-cost per-turn tool optimization.

Analyzes the current user message (using CHEAP keyword heuristics, NOT LLM
calls) to detect what phase/task the user is in RIGHT NOW, and returns
exactly which tools should be active for this turn.

This is the intelligence layer that makes TLM actually save tokens:
- Build 1 (frontend): needs terminal, file_system, browser
- Build 2 (backend tests): needs terminal, file_system
- Build 3 (mobile API): needs terminal, file_system
- Build 4 (deploy): needs terminal, docker
- Ship: needs terminal, git

Without this: 4200 tokens of tool schemas loaded every turn.
With this: 200-600 tokens loaded per turn (only active tools).
Savings: 3600+ tokens per turn * 100 turns = 360,000 tokens saved per session.

The detection is 100% heuristic (regex + keyword match). Zero LLM calls.
Zero extra tokens burned. Pure savings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PhaseDetection:
    """Result of phase detection for a single message."""

    phase: str                      # "frontend", "backend", "testing", "deploy", "research", etc.
    confidence: float               # 0.0 to 1.0
    recommended_tools: list[str]    # tool IDs to activate
    deactivate_tools: list[str]     # tool IDs to deactivate (from previous phase)
    reasoning: str                  # human-readable explanation


# ── Phase Definitions ─────────────────────────────────────────

# Each phase: keywords that trigger it, tools it needs, tools it doesn't need
_PHASES: dict[str, dict[str, Any]] = {
    "frontend": {
        "keywords": [
            r"\breact\b", r"\bvue\b", r"\btypescript\b", r"\bcss\b", r"\btailwind\b",
            r"\bcomponent\b", r"\bpage\b", r"\bui\b", r"\bux\b", r"\bfrontend\b",
            r"\bvite\b", r"\bnpm\b", r"\bnode\b", r"\bbuild\b.*\bfrontend",
            r"\bstyling\b", r"\blayout\b", r"\brender\b", r"\bstore\b.*\bzustand\b",
            r"\btsx\b", r"\bjsx\b", r"\bhtml\b",
        ],
        "tools": ["terminal", "file_system", "browser", "web_search"],
        "not_needed": ["docker", "database", "email", "calendar", "spreadsheet"],
    },
    "backend": {
        "keywords": [
            r"\bpython\b", r"\bfastapi\b", r"\bflask\b", r"\bdjango\b",
            r"\bendpoint\b", r"\bapi\b", r"\brouter\b", r"\bservice\b",
            r"\bbackend\b", r"\bsqlalchemy\b", r"\bdatabase\b", r"\bmodel\b.*\bpython",
            r"\bpydantic\b", r"\basync\b", r"\bdef\b", r"\bclass\b",
            r"\borm\b", r"\bmigration\b", r"\bschema\b",
        ],
        "tools": ["terminal", "file_system"],
        "not_needed": ["browser", "docker", "email", "spreadsheet", "calendar"],
    },
    "testing": {
        "keywords": [
            r"\btest\b", r"\bpytest\b", r"\bjest\b", r"\bspec\b",
            r"\bassert\b", r"\bmock\b", r"\bfixture\b", r"\bcoverage\b",
            r"\bregression\b", r"\bverif", r"\bvalidat",
            r"\brun.*tests?\b", r"\btest.*suite\b", r"\bgreen\b.*\bpass",
        ],
        "tools": ["terminal", "file_system"],
        "not_needed": ["browser", "docker", "email", "slack", "calendar", "spreadsheet"],
    },
    "deploy": {
        "keywords": [
            r"\bdeploy\b", r"\bdocker\b", r"\bgcp\b", r"\bcloud\s*run\b",
            r"\bkubernetes\b", r"\bcontainer\b", r"\bproduc", r"\bship\b",
            r"\brelease\b", r"\btag\b.*\bversion", r"\bversion\b.*\bbump",
            r"\bci.?cd\b", r"\bpipeline\b.*\bdeploy", r"\binfra",
        ],
        "tools": ["terminal", "file_system"],
        "not_needed": ["browser", "email", "spreadsheet", "calendar", "web_search"],
    },
    "research": {
        "keywords": [
            r"\bresearch\b", r"\banalyze\b", r"\bcompare\b", r"\bcompetit",
            r"\bmarket\b", r"\btrend\b", r"\bstudy\b", r"\binvestigat",
            r"\breview\b.*\bliterature", r"\bstate\s+of\s+the\s+art",
            r"\bfind\b.*\binformation", r"\bsearch\b.*\bfor\b",
        ],
        "tools": ["web_search", "file_system"],
        "not_needed": ["terminal", "docker", "email", "spreadsheet"],
    },
    "writing": {
        "keywords": [
            r"\bwrite\b.*\b(?:email|document|report|blog|article|copy)\b",
            r"\bdraft\b", r"\bcompose\b", r"\bcontent\b",
            r"\bmarketing\b.*\b(?:email|copy|content)\b",
            r"\bslack\b.*\bmessage\b", r"\bnotif",
        ],
        "tools": ["email", "slack", "file_system"],
        "not_needed": ["terminal", "docker", "browser", "spreadsheet"],
    },
    "data": {
        "keywords": [
            r"\bdata\b", r"\bcsv\b", r"\bexcel\b", r"\bspreadsheet\b",
            r"\bchart\b", r"\bgraph\b", r"\bvisuali", r"\bmetric",
            r"\bbilling\b", r"\bcost\b.*\banalysis", r"\breport\b.*\bfinancial",
            r"\bbudget\b", r"\bforecast\b",
        ],
        "tools": ["spreadsheet", "file_system", "terminal"],
        "not_needed": ["browser", "docker", "email", "slack"],
    },
    "git": {
        "keywords": [
            r"\bgit\b", r"\bcommit\b", r"\bbranch\b", r"\bmerge\b",
            r"\bpull\s*request\b", r"\bpr\b", r"\bpush\b", r"\bcheckout\b",
            r"\brebase\b", r"\bstash\b", r"\bdiff\b", r"\bgithub\b",
        ],
        "tools": ["terminal", "github", "file_system"],
        "not_needed": ["browser", "docker", "email", "spreadsheet", "calendar"],
    },
    "conversation": {
        "keywords": [
            r"^(?:hi|hello|hey|thanks|thank you|ok|yes|no|sure|got it)\b",
            r"^(?:what|how|why|when|who|can you)\b",
            r"\bchat\b", r"\btalk\b", r"\bexplain\b", r"\bhelp\b",
        ],
        "tools": [],  # NO tools needed for simple conversation
        "not_needed": ["terminal", "file_system", "browser", "docker", "email",
                        "slack", "calendar", "spreadsheet", "web_search", "github"],
    },
}

# Pre-compile all patterns for performance
_COMPILED_PHASES: dict[str, list[re.Pattern]] = {}
for phase_name, phase_def in _PHASES.items():
    _COMPILED_PHASES[phase_name] = [
        re.compile(kw, re.IGNORECASE) for kw in phase_def["keywords"]
    ]


class ConversationPhaseDetector:
    """Detects the current conversation phase from user message.

    Zero LLM calls. Pure keyword heuristics. <0.1ms per detection.
    Returns which tools should be active for this specific turn.

    Usage:
        detector = ConversationPhaseDetector()
        detection = detector.detect("Run pytest and check all 1347 tests pass")
        # -> PhaseDetection(phase="testing", tools=["terminal", "file_system"])
    """

    def __init__(self) -> None:
        self._previous_phase: str | None = None
        self._phase_history: list[str] = []

    def detect(
        self,
        message: str,
        active_tools: list[str] | None = None,
    ) -> PhaseDetection:
        """Detect phase from a user message.

        Args:
            message: the user's current message
            active_tools: currently active tool IDs (for deactivation decisions)

        Returns:
            PhaseDetection with recommended tools to activate/deactivate
        """
        scores: dict[str, float] = {}

        for phase_name, patterns in _COMPILED_PHASES.items():
            score = 0.0
            for pattern in patterns:
                if pattern.search(message):
                    score += 1.0
            if score > 0:
                # Normalize by number of patterns
                scores[phase_name] = score / len(patterns)

        if not scores:
            # No phase detected: keep current tools, low confidence
            return PhaseDetection(
                phase=self._previous_phase or "conversation",
                confidence=0.2,
                recommended_tools=active_tools or [],
                deactivate_tools=[],
                reasoning="No phase keywords detected, maintaining current state",
            )

        # Pick highest scoring phase
        best_phase = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_phase] * 3)  # scale up for visibility

        phase_def = _PHASES[best_phase]
        recommended = phase_def["tools"]
        not_needed = phase_def.get("not_needed", [])

        # Determine what to deactivate
        deactivate = []
        if active_tools:
            deactivate = [t for t in active_tools if t in not_needed]

        # Track phase transitions
        if best_phase != self._previous_phase:
            self._phase_history.append(best_phase)
        self._previous_phase = best_phase

        return PhaseDetection(
            phase=best_phase,
            confidence=round(confidence, 2),
            recommended_tools=recommended,
            deactivate_tools=deactivate,
            reasoning=self._build_reasoning(best_phase, scores, recommended, deactivate),
        )

    def get_phase_history(self) -> list[str]:
        """Return the sequence of detected phases in this conversation."""
        return list(self._phase_history)

    def reset(self) -> None:
        """Reset detector state (new conversation)."""
        self._previous_phase = None
        self._phase_history.clear()

    def _build_reasoning(
        self,
        phase: str,
        scores: dict[str, float],
        tools: list[str],
        deactivate: list[str],
    ) -> str:
        parts = [f"Detected phase: {phase}"]
        if tools:
            parts.append(f"Active tools: {', '.join(tools)}")
        if deactivate:
            parts.append(f"Deactivating: {', '.join(deactivate)}")
        others = {k: round(v, 2) for k, v in scores.items() if k != phase}
        if others:
            parts.append(f"Other signals: {others}")
        return ". ".join(parts)


class AdaptiveToolSelector:
    """Combines phase detection with TLM for per-turn tool optimization.

    This is the bridge between ConversationPhaseDetector and the TLM
    SessionManager. Each turn:
    1. Detect phase from user message (free, <0.1ms)
    2. Activate recommended tools (SessionManager)
    3. Deactivate unneeded tools (SessionManager)
    4. Return only active tool schemas for LLM context

    Token savings calculation:
        baseline = ALL_TOOLS * SCHEMA_TOKENS_EACH * TURNS
        adaptive = ACTIVE_TOOLS_PER_TURN * SCHEMA_TOKENS_EACH * TURNS
        savings  = baseline - adaptive

    For a 100-turn conversation with 20 tools (210 tokens each):
        baseline = 20 * 210 * 100 = 420,000 tokens
        adaptive = 2.5 * 210 * 100 = 52,500 tokens (avg 2.5 active per turn)
        savings  = 367,500 tokens (87.5% reduction)
    """

    def __init__(self) -> None:
        self.detector = ConversationPhaseDetector()
        self._turn_count = 0
        self._total_tools_loaded = 0
        self._total_tools_baseline = 0
        self._total_tools_available = 20  # default

    def select_tools_for_turn(
        self,
        message: str,
        active_tools: list[str] | None = None,
        total_tools: int = 20,
    ) -> PhaseDetection:
        """Select optimal tools for this turn.

        Returns PhaseDetection with activate/deactivate recommendations.
        Also tracks cumulative savings for reporting.
        """
        self._total_tools_available = total_tools
        detection = self.detector.detect(message, active_tools)
        self._turn_count += 1
        self._total_tools_loaded += len(detection.recommended_tools)
        self._total_tools_baseline += total_tools
        return detection

    def get_efficiency_report(self) -> dict[str, Any]:
        """Get cumulative efficiency metrics for this conversation."""
        if self._turn_count == 0:
            return {
                "turns": 0,
                "avg_tools_per_turn": 0,
                "baseline_tools_per_turn": 0,
                "token_reduction_percent": 0,
            }

        avg_active = self._total_tools_loaded / self._turn_count
        avg_baseline = self._total_tools_baseline / self._turn_count
        tokens_per_tool = 210
        actual_tokens = self._total_tools_loaded * tokens_per_tool
        baseline_tokens = self._total_tools_baseline * tokens_per_tool
        savings = baseline_tokens - actual_tokens
        pct = (savings / baseline_tokens * 100) if baseline_tokens > 0 else 0

        return {
            "turns": self._turn_count,
            "avg_tools_per_turn": round(avg_active, 1),
            "baseline_tools_per_turn": round(avg_baseline, 1),
            "total_tokens_loaded": actual_tokens,
            "baseline_tokens": baseline_tokens,
            "tokens_saved": savings,
            "token_reduction_percent": round(pct, 1),
            "phase_transitions": self.detector.get_phase_history(),
        }

    def reset(self) -> None:
        self.detector.reset()
        self._turn_count = 0
        self._total_tools_loaded = 0
        self._total_tools_baseline = 0
