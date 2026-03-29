"""Query Understanding Pipeline — intent classification, complexity scoring, risk assessment.

Every user message flows through this pipeline BEFORE any LLM is called.
It produces a ``QueryUnderstanding`` result that the Model Router uses
to pick the best provider, model, and governance tier.

Pipeline stages (total budget <200ms):
    1. Intent classification  — keyword heuristic (<5ms)
    2. Complexity scoring      — 8 weighted factors (<30ms)
    3. Risk assessment         — decision tree + governance slider (<20ms)
    4. Ambiguity detection     — confidence + signal checks (<5ms)

No ML dependency — the keyword heuristic is always available.
A local LLM classifier (Ollama) can be added later as an optional upgrade.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.constants import (
    ChatMode,
    GovernanceSlider,
    ModelProvider,
    RiskLevel,
    RoutingMode,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Intent Types ──────────────────────────────────────────────


class IntentType(str, Enum):
    """Classified intent of a user query."""

    SIMPLE = "SIMPLE"
    SEARCH = "SEARCH"
    CODING = "CODING"
    ANALYSIS = "ANALYSIS"
    CREATIVE = "CREATIVE"
    MULTI_STEP = "MULTI_STEP"
    DANGEROUS = "DANGEROUS"
    TOOL_USE = "TOOL_USE"
    AMBIGUOUS = "AMBIGUOUS"


class ComplexityLabel(str, Enum):
    """Human-readable complexity bracket."""

    SIMPLE = "SIMPLE"            # 0.0 – 0.29
    MODERATE = "MODERATE"        # 0.30 – 0.59
    COMPLEX = "COMPLEX"          # 0.60 – 0.79
    VERY_COMPLEX = "VERY_COMPLEX"  # 0.80 – 1.0


# ── Data Structures ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class QueryInput:
    """Input to the query understanding pipeline."""

    raw_message: str
    session_id: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)
    user_id: str | None = None
    tenant_id: str | None = None
    execution_mode: ChatMode = ChatMode.CMD
    governance_slider: GovernanceSlider = GovernanceSlider.STANDARD
    available_tools: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QueryUnderstanding:
    """Output of the query understanding pipeline."""

    intent: IntentType
    confidence: float
    complexity_score: float
    complexity_label: ComplexityLabel
    risk_level: RiskLevel
    governance_tier: int
    suggested_mode: RoutingMode
    suggested_providers: list[ModelProvider]
    ambiguity_signals: list[str]
    clarifying_question: str | None
    processing_time_ms: int
    exe_suggestion: str | None = None  # Suggestion to switch to EXE mode
    intent_scores: dict[str, float] = field(default_factory=dict)


# ── Keyword Classification ───────────────────────────────────

# Priority order: DANGEROUS > CODING > MULTI_STEP > SEARCH >
#                 ANALYSIS > CREATIVE > SIMPLE > AMBIGUOUS
# DANGEROUS checked first — false negatives have worst consequences.

_INTENT_KEYWORDS: dict[IntentType, dict[str, Any]] = {
    IntentType.DANGEROUS: {
        "keywords": [
            "delete", "remove", "destroy", "wipe", "purge", "drop",
            "rm -rf", "sudo", "chmod", "kill process",
            "transfer", "pay", "charge", "refund", "invoice",
            "revoke", "grant access", "disable auth", "change permissions",
            "send to all", "notify everyone", "mass email",
            "DROP TABLE", "format drive",
        ],
        "weight": 1.5,  # Boosted — false negatives worse than false positives
        "threshold": 0.30,
    },
    IntentType.CODING: {
        "keywords": [
            "code", "function", "class", "debug", "error", "bug",
            "import", "def ", "const ", "return", "async", "await",
            "refactor", "implement", "compile", "syntax", "algorithm",
            "API", "endpoint", "database query", "SQL", "test",
        ],
        "patterns": [r"```", r"\.(py|js|ts|tsx|jsx|sql|yml|yaml|json|go|rs|java)"],
        "weight": 1.0,
        "threshold": 0.45,
    },
    IntentType.TOOL_USE: {
        "keywords": [
            "list files", "read file", "create file", "write file",
            "move file", "delete file", "rename file", "show files",
            "run command", "execute command", "run ", "exec ",
            "open file", "cat ", "ls ", "dir ",
            "navigate to", "go to http", "browse to",
            "take screenshot", "extract text from",
            "list directory", "show directory",
            "create a file", "make a file",
        ],
        "weight": 1.2,
        "threshold": 0.30,
    },
    IntentType.MULTI_STEP: {
        "keywords": [
            "and then", "after that", "step by step", "pipeline",
            "migrate", "set up", "end-to-end", "workflow",
            "first", "second", "third", "finally",
            "phase", "stage", "plan",
        ],
        "weight": 1.0,
        "threshold": 0.45,
    },
    IntentType.SEARCH: {
        "keywords": [
            "current", "latest", "today", "now", "recent", "news",
            "price", "weather", "score", "2025", "2026",
            "who is", "where is", "when did", "how much",
            "find me", "look up", "search for",
        ],
        "weight": 1.0,
        "threshold": 0.45,
    },
    IntentType.ANALYSIS: {
        "keywords": [
            "compare", "analyze", "evaluate", "pros and cons",
            "versus", "vs", "assess", "trade-off", "benchmark",
            "review", "audit", "summarize", "break down",
            "statistics", "metrics", "performance",
            "trend", "forecast", "data", "correlation", "insight",
        ],
        "weight": 1.0,
        "threshold": 0.45,
    },
    IntentType.CREATIVE: {
        "keywords": [
            "write", "draft", "brainstorm", "compose",
            "tagline", "story", "blog", "email draft",
            "poem", "script", "design", "ideate", "creative",
            "generate", "imagine", "invent",
        ],
        "weight": 0.9,
        "threshold": 0.40,
    },
    IntentType.SIMPLE: {
        "keywords": [
            "what is", "define", "how many", "convert", "calculate",
            "translate", "spell", "abbreviation", "meaning of",
            "yes", "no", "thanks", "hello", "hi",
        ],
        "weight": 0.8,
        "threshold": 0.18,
    },
}

# Checked in priority order
_INTENT_PRIORITY: list[IntentType] = [
    IntentType.DANGEROUS,
    IntentType.TOOL_USE,
    IntentType.CODING,
    IntentType.MULTI_STEP,
    IntentType.SEARCH,
    IntentType.ANALYSIS,
    IntentType.CREATIVE,
    IntentType.SIMPLE,
]

# ── Dangerous Pattern Regexes (precompiled) ──────────────────

_DANGEROUS_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "CRITICAL": [
        re.compile(p, re.IGNORECASE) for p in [
            r"\brm\s+(-rf?|--recursive)\b",
            r"\bDROP\s+(TABLE|DATABASE)\b",
            r"\bDELETE\s+FROM\b.*\bWHERE\b",
            r"\bsudo\b",
            r"\bchmod\s+777\b",
            r"\bformat\s+[A-Z]:\b",
            r"\b(transfer|send|pay|wire)\b.*\$\d+",
            r"\brevoke\b.*\b(access|key|token|permission)\b",
        ]
    ],
    "HIGH": [
        re.compile(p, re.IGNORECASE) for p in [
            r"\b(npm|pip|apt|brew)\s+install\b",
            r"\bsend\s+(email|message|notification)\b",
            r"\b(update|modify|change)\b.*\b(password|credential|secret|key)\b",
            r"\bgit\s+push\s+(--force|-f)\b",
            r"\bdeploy\b.*\bproduction\b",
        ]
    ],
    "MEDIUM": [
        re.compile(p, re.IGNORECASE) for p in [
            r"\b(create|write|save)\b.*\bfile\b",
            r"\bmkdir\b",
            r"\bgit\s+(commit|merge)\b",
            r"\b(modify|edit|update)\b.*\b(config|settings)\b",
        ]
    ],
}

# ── Governance Slider Minimums ───────────────────────────────

_SLIDER_MINIMUMS: dict[GovernanceSlider, int] = {
    GovernanceSlider.YOLO: 0,
    GovernanceSlider.LIGHT: 0,
    GovernanceSlider.STANDARD: 0,
    GovernanceSlider.STRICT: 2,
    GovernanceSlider.PARANOID: 3,
}

_RISK_TO_TIER: dict[RiskLevel, int] = {
    RiskLevel.NONE: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}

# ── Default Routing Suggestions ──────────────────────────────

_INTENT_PROVIDERS: dict[IntentType, list[ModelProvider]] = {
    IntentType.SIMPLE: [
        ModelProvider.OLLAMA, ModelProvider.GROQ, ModelProvider.PERPLEXITY,
    ],
    IntentType.SEARCH: [
        ModelProvider.PERPLEXITY, ModelProvider.OLLAMA, ModelProvider.ANTHROPIC,
    ],
    IntentType.CODING: [
        ModelProvider.ANTHROPIC, ModelProvider.OPENAI, ModelProvider.OLLAMA,
        ModelProvider.GEMINI,
    ],
    IntentType.ANALYSIS: [
        ModelProvider.ANTHROPIC, ModelProvider.OPENAI, ModelProvider.GEMINI,
        ModelProvider.OLLAMA,
    ],
    IntentType.CREATIVE: [
        ModelProvider.OPENAI, ModelProvider.ANTHROPIC, ModelProvider.GEMINI,
        ModelProvider.OLLAMA,
    ],
    IntentType.MULTI_STEP: [
        ModelProvider.ANTHROPIC, ModelProvider.OPENAI,
    ],
    IntentType.DANGEROUS: [
        ModelProvider.ANTHROPIC, ModelProvider.OPENAI,
    ],
    IntentType.AMBIGUOUS: [],  # No LLM call — re-prompt the user
}


# ── Complexity Scoring ───────────────────────────────────────

# Weights for each complexity factor (sum = 1.0)
_COMPLEXITY_WEIGHTS: dict[str, float] = {
    "token_length": 0.10,
    "entity_count": 0.15,
    "domain_count": 0.20,
    "temporal_refs": 0.10,
    "negation_cond": 0.10,
    "multi_part": 0.15,
    "code_blocks": 0.10,
    "context_depth": 0.10,
}

_TEMPORAL_TERMS = [
    "before", "after", "during", "since", "until", "while",
    "yesterday", "tomorrow", "last week", "next month",
    "deadline", "timeline", "schedule", "by friday",
]

_NEGATION_TERMS = [
    "not", "don't", "without", "except", "unless", "but",
    "however", "if", "only if", "assuming", "given that",
    "provided that", "as long as",
]

_CONTEXT_REFS = [
    "it", "that", "this", "the same", "like before",
    "as i said", "the one", "earlier", "previous",
    "we discussed", "mentioned",
]

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "engineering": ["code", "api", "database", "deploy", "server", "bug"],
    "product": ["feature", "user story", "roadmap", "mvp", "sprint"],
    "design": ["ui", "ux", "mockup", "wireframe", "layout", "figma"],
    "marketing": ["campaign", "seo", "funnel", "brand", "launch"],
    "finance": ["budget", "revenue", "cost", "invoice", "pricing", "runway"],
    "legal": ["compliance", "gdpr", "terms", "contract", "patent", "ip"],
    "sales": ["lead", "pipeline", "crm", "demo", "close", "prospect"],
    "operations": ["infra", "devops", "ci/cd", "monitoring", "sla"],
    "security": ["auth", "encryption", "vulnerability", "firewall", "pen test"],
    "research": ["paper", "study", "literature", "hypothesis", "data"],
    "strategy": ["roadmap", "okr", "kpi", "growth", "market"],
}

_CONJUNCTION_RE = re.compile(
    r"\b(and also|and then|additionally|furthermore|plus|also)\b",
    re.IGNORECASE,
)
_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s", re.MULTILINE)
_CODE_KEYWORD_RE = re.compile(
    r"(def |class |function |const |import |from )"
)

# ── Ambiguity Signals ────────────────────────────────────────

_VAGUE_PRONOUNS = {"it", "that", "this", "they", "them", "those"}


# ── Pipeline Service ─────────────────────────────────────────


class QueryUnderstandingService:
    """Stateless pipeline: classify intent, score complexity, assess risk.

    Usage::

        svc = QueryUnderstandingService()
        result = svc.analyze(QueryInput(raw_message="Compare React vs Vue"))
        print(result.intent, result.complexity_label, result.risk_level)
    """

    def analyze(self, query_input: QueryInput) -> QueryUnderstanding:
        """Run the full pipeline and return a ``QueryUnderstanding``."""
        start = time.monotonic()
        msg = query_input.raw_message.strip()
        lower = msg.lower()

        # Stage 1: Intent classification (keyword heuristic)
        intent, confidence, scores = self._classify_intent(msg, lower)

        # Stage 2: Ambiguity detection
        ambiguity_signals = self._detect_ambiguity(
            msg, lower, scores, query_input.history,
        )
        # Only override to AMBIGUOUS when confidence is genuinely low
        # or there's an intent tie.  Contextual signals (missing_context,
        # extreme_brevity) should not override a high-confidence intent.
        confidence_signals = {"low_confidence", "intent_tie", "missing_object"}
        has_confidence_issue = bool(
            set(ambiguity_signals) & confidence_signals
        )
        if (
            ambiguity_signals
            and has_confidence_issue
            and intent != IntentType.DANGEROUS
        ):
            intent = IntentType.AMBIGUOUS
            confidence = max(scores.values()) if scores else 0.0

        # Stage 3: Complexity scoring
        complexity = self._compute_complexity(msg, lower, query_input.history)
        complexity_label = self._label_complexity(complexity)

        # Stage 4: Risk assessment
        risk_level = self._assess_inherent_risk(intent, msg, query_input.execution_mode)
        inherent_tier = _RISK_TO_TIER[risk_level]
        slider_min = _SLIDER_MINIMUMS[query_input.governance_slider]
        governance_tier = max(inherent_tier, slider_min)
        # Hard Law #4: Tier 4 actions can NEVER be downgraded
        if inherent_tier == 4:
            governance_tier = 4

        # Stage 5: Mode suggestion
        suggested_mode = self._suggest_mode(intent, complexity)
        suggested_providers = list(
            _INTENT_PROVIDERS.get(intent, [])
        )

        # Stage 6: Clarifying question (only for AMBIGUOUS)
        clarifying_question = None
        if intent == IntentType.AMBIGUOUS:
            clarifying_question = self._generate_clarifying_question(
                msg, ambiguity_signals,
            )

        # Stage 7: EXE suggestion (TOOL_USE in CMD mode)
        exe_suggestion: str | None = None
        if (
            intent == IntentType.TOOL_USE
            and query_input.execution_mode == ChatMode.CMD
        ):
            exe_suggestion = (
                "I can execute this for you. "
                "Switch to EXE mode or say 'do it'."
            )

        elapsed = int((time.monotonic() - start) * 1000)

        result = QueryUnderstanding(
            intent=intent,
            confidence=confidence,
            complexity_score=round(complexity, 4),
            complexity_label=complexity_label,
            risk_level=risk_level,
            governance_tier=governance_tier,
            suggested_mode=suggested_mode,
            suggested_providers=suggested_providers,
            ambiguity_signals=ambiguity_signals,
            clarifying_question=clarifying_question,
            processing_time_ms=elapsed,
            exe_suggestion=exe_suggestion,
            intent_scores={k.value: round(v, 4) for k, v in scores.items()},
        )

        logger.info(
            "query.understood",
            intent=result.intent.value,
            confidence=result.confidence,
            complexity=result.complexity_label.value,
            risk=result.risk_level.value,
            tier=result.governance_tier,
            ms=result.processing_time_ms,
        )
        return result

    # ── Stage 1: Intent Classification ────────────────────────

    def _classify_intent(
        self, msg: str, lower: str,
    ) -> tuple[IntentType, float, dict[IntentType, float]]:
        """Keyword-based heuristic classification (<5ms).

        Returns (best_intent, confidence, all_scores).
        """
        scores: dict[IntentType, float] = {}

        for intent_type in _INTENT_PRIORITY:
            cfg = _INTENT_KEYWORDS[intent_type]
            keywords: list[str] = cfg["keywords"]
            weight: float = cfg["weight"]

            hit_count = sum(1 for kw in keywords if kw.lower() in lower)

            # Check regex patterns if present
            patterns: list[str] = cfg.get("patterns", [])
            hit_count += sum(
                1 for p in patterns if re.search(p, msg)
            )

            if not keywords and not patterns:
                scores[intent_type] = 0.0
                continue

            # Saturation-based normalization: 4 hits = full confidence.
            # Dividing by total_keywords penalises intents with large
            # keyword lists (3/22 = 0.14).  Instead, cap the denominator
            # so that a handful of hits produces a strong signal.
            saturation = 4
            raw_score = min(hit_count / saturation, 1.0) * weight

            scores[intent_type] = min(raw_score, 1.0)

        if not scores or max(scores.values()) == 0:
            return IntentType.SIMPLE, 0.5, scores

        best_intent = max(scores, key=lambda k: scores[k])
        best_score = scores[best_intent]
        threshold = _INTENT_KEYWORDS[best_intent]["threshold"]

        if best_score < threshold:
            # Below threshold but DANGEROUS gets special treatment
            if (
                best_intent == IntentType.DANGEROUS
                and best_score >= 0.6
            ):
                return best_intent, best_score, scores
            # Not confident enough — will become AMBIGUOUS in stage 2
            return best_intent, best_score, scores

        return best_intent, best_score, scores

    # ── Stage 2: Ambiguity Detection ─────────────────────────

    def _detect_ambiguity(
        self,
        msg: str,
        lower: str,
        scores: dict[IntentType, float],
        history: list[dict[str, str]],
    ) -> list[str]:
        """Return list of ambiguity signal names (empty = not ambiguous)."""
        signals: list[str] = []
        sorted_vals = sorted(scores.values(), reverse=True)

        # Rule 1: Best intent doesn't meet its own threshold
        if sorted_vals and sorted_vals[0] > 0:
            best_intent = max(scores, key=lambda k: scores[k])
            intent_threshold = _INTENT_KEYWORDS.get(
                best_intent, {},
            ).get("threshold", 0.45)
            if sorted_vals[0] < intent_threshold:
                signals.append("low_confidence")

        # Rule 2: Top two too close (tie)
        if (
            len(sorted_vals) >= 2
            and (sorted_vals[0] - sorted_vals[1]) < 0.10
            and sorted_vals[0] > 0.0
        ):
            signals.append("intent_tie")

        # Rule 3: Extreme brevity
        tokens = msg.split()
        if len(tokens) < 3:
            # Check if it's a greeting or simple ack (not ambiguous)
            greetings = {"hi", "hello", "hey", "thanks", "yes", "no", "ok", "okay"}
            if not any(t.lower().rstrip("!.,?") in greetings for t in tokens):
                signals.append("extreme_brevity")

        # Rule 4: Vague pronouns without history
        if not history:
            words = set(lower.split())
            if words & _VAGUE_PRONOUNS and len(tokens) < 8:
                signals.append("missing_context")

        # Rule 5: Missing object (verb but no noun target)
        action_verbs = {"fix", "delete", "update", "change", "make", "do", "help"}
        if len(tokens) <= 2 and any(t.lower() in action_verbs for t in tokens):
            signals.append("missing_object")

        # Rule 6: Too many question marks
        if msg.count("?") >= 3:
            signals.append("question_density")

        return signals

    # ── Stage 3: Complexity Scoring ──────────────────────────

    def _compute_complexity(
        self,
        msg: str,
        lower: str,
        history: list[dict[str, str]],
    ) -> float:
        """Score 0.0 (trivial) to 1.0 (maximum complexity)."""
        factors: dict[str, float] = {
            "token_length": self._score_token_length(msg),
            "entity_count": self._score_entity_count(msg),
            "domain_count": self._score_domain_count(lower),
            "temporal_refs": self._score_temporal(lower),
            "negation_cond": self._score_negation(lower),
            "multi_part": self._score_multi_part(msg),
            "code_blocks": self._score_code_presence(msg),
            "context_depth": self._score_context_depth(lower, history),
        }

        raw = sum(
            factors[k] * _COMPLEXITY_WEIGHTS[k] for k in factors
        )
        return min(max(raw, 0.0), 1.0)

    @staticmethod
    def _score_token_length(msg: str) -> float:
        tokens = len(msg.split())
        if tokens <= 5:
            return 0.0
        if tokens <= 15:
            return 0.2
        if tokens <= 40:
            return 0.4
        if tokens <= 80:
            return 0.6
        if tokens <= 150:
            return 0.8
        return 1.0

    @staticmethod
    def _score_entity_count(msg: str) -> float:
        """Heuristic: count capitalized words (2+ chars) as entities."""
        entities = set(
            w for w in msg.split()
            if len(w) >= 2 and w[0].isupper() and not w.isupper()
        )
        count = len(entities)
        if count <= 1:
            return 0.0
        if count <= 3:
            return 0.3
        if count <= 5:
            return 0.6
        return 1.0

    @staticmethod
    def _score_domain_count(lower: str) -> float:
        detected = 0
        for _domain, keywords in _DOMAIN_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                detected += 1
        if detected <= 1:
            return 0.0
        if detected == 2:
            return 0.4
        if detected == 3:
            return 0.7
        return 1.0

    @staticmethod
    def _score_temporal(lower: str) -> float:
        matches = sum(1 for t in _TEMPORAL_TERMS if t in lower)
        if matches == 0:
            return 0.0
        if matches <= 2:
            return 0.4
        return 0.8

    @staticmethod
    def _score_negation(lower: str) -> float:
        matches = sum(1 for s in _NEGATION_TERMS if s in lower)
        if matches == 0:
            return 0.0
        if matches <= 2:
            return 0.4
        return 0.8

    @staticmethod
    def _score_multi_part(msg: str) -> float:
        question_marks = msg.count("?")
        numbered = len(_NUMBERED_RE.findall(msg))
        bullets = len(_BULLET_RE.findall(msg))
        conjunctions = len(_CONJUNCTION_RE.findall(msg))

        parts = max(question_marks, numbered, bullets) + conjunctions
        if parts <= 1:
            return 0.0
        if parts <= 3:
            return 0.4
        if parts <= 5:
            return 0.7
        return 1.0

    @staticmethod
    def _score_code_presence(msg: str) -> float:
        if "```" in msg:
            return 0.6
        if "Traceback" in msg or "Error:" in msg:
            return 0.5
        if _CODE_KEYWORD_RE.search(msg):
            return 0.3
        return 0.0

    @staticmethod
    def _score_context_depth(
        lower: str, history: list[dict[str, str]],
    ) -> float:
        matches = sum(1 for r in _CONTEXT_REFS if r in lower)
        if matches == 0:
            return 0.0
        # Heavier if no history to resolve references against
        if not history and matches >= 1:
            return 0.8
        if matches <= 2:
            return 0.4
        return 0.8

    @staticmethod
    def _label_complexity(score: float) -> ComplexityLabel:
        if score < 0.30:
            return ComplexityLabel.SIMPLE
        if score < 0.60:
            return ComplexityLabel.MODERATE
        if score < 0.80:
            return ComplexityLabel.COMPLEX
        return ComplexityLabel.VERY_COMPLEX

    # ── Stage 4: Risk Assessment ─────────────────────────────

    def _assess_inherent_risk(
        self,
        intent: IntentType,
        msg: str,
        execution_mode: ChatMode,
    ) -> RiskLevel:
        """Determine inherent risk level from intent + content patterns."""
        # CMD mode (read-only) is always low risk
        if execution_mode == ChatMode.CMD and intent != IntentType.DANGEROUS:
            return RiskLevel.NONE

        # Check dangerous regex patterns (most precise)
        for level_name in ("CRITICAL", "HIGH", "MEDIUM"):
            for pattern in _DANGEROUS_PATTERNS.get(level_name, []):
                if pattern.search(msg):
                    return RiskLevel[level_name]

        # Intent-based defaults
        risk_map: dict[IntentType, RiskLevel] = {
            IntentType.SIMPLE: RiskLevel.NONE,
            IntentType.SEARCH: RiskLevel.LOW,
            IntentType.CODING: RiskLevel.LOW,
            IntentType.ANALYSIS: RiskLevel.NONE,
            IntentType.CREATIVE: RiskLevel.NONE,
            IntentType.MULTI_STEP: RiskLevel.MEDIUM,
            IntentType.TOOL_USE: RiskLevel.MEDIUM,
            IntentType.DANGEROUS: RiskLevel.HIGH,
            IntentType.AMBIGUOUS: RiskLevel.NONE,
        }
        return risk_map.get(intent, RiskLevel.NONE)

    # ── Stage 5: Mode Suggestion ─────────────────────────────

    @staticmethod
    def _suggest_mode(intent: IntentType, complexity: float) -> RoutingMode:
        """Suggest STANDARD, COUNCIL, or QUINTESSENCE based on complexity."""
        if complexity >= 0.80:
            return RoutingMode.QUINTESSENCE
        if complexity >= 0.60:
            return RoutingMode.COUNCIL
        return RoutingMode.STANDARD

    # ── Stage 6: Clarifying Question ─────────────────────────

    @staticmethod
    def _generate_clarifying_question(
        msg: str, signals: list[str],
    ) -> str:
        """Generate ONE targeted clarifying question.

        Hard Law #9 (LOW_LATENCY): never ask multiple questions.
        """
        if "missing_object" in signals:
            return "What specifically would you like me to work on?"
        if "missing_context" in signals:
            return "Could you provide more context about what you're referring to?"
        if "extreme_brevity" in signals:
            return "Could you be more specific about what you need?"
        if "question_density" in signals:
            return (
                "You asked several questions. "
                "Which one should I address first?"
            )
        if "intent_tie" in signals:
            return "I'm not sure what type of help you need. Could you elaborate?"
        if "low_confidence" in signals:
            return "Could you rephrase your request so I can better assist you?"
        return "Could you be more specific about what you need?"
