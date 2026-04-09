"""CognitiveReasoner -- LLM-powered reasoning with framework lenses.

This is Daena's REAL brain. Not if-else trees. Not template matching.
The LLM reasons about the SPECIFIC situation using whichever
reasoning frameworks fit.

The 25 frameworks (First Principles, Inversion, 5 Whys, Constraint
Probe, Pre-Mortem, etc.) are NOT code paths. They are LENSES passed
to the LLM as system context. The LLM decides which ones to apply
and generates novel reasoning for situations nobody anticipated.

Architecture:
    - Auto-selects the best available model (Claude > GPT > Gemini > Qwen > Llama)
    - Falls back to deterministic reasoning if no LLM is available
    - Learns from every interaction (stores lessons to NBMF)
    - Universal: same engine for security, debugging, architecture, anything

EQ + IQ + AQ:
    IQ: Reasons through complex novel situations using frameworks
    EQ: Understands WHY something succeeded or failed (not just what)
    AQ: Gets smarter from every experience (NBMF memory + learning service)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Reasoning Framework Prompts (lenses, not code paths)
# ---------------------------------------------------------------------------

FRAMEWORK_PROMPTS: dict[str, str] = {
    "first_principles": (
        "FIRST PRINCIPLES (Musk): Strip away assumptions. What is provably "
        "true here? What are we assuming that might be wrong? Decompose to "
        "fundamental truths and rebuild your understanding from there."
    ),
    "inversion": (
        "INVERSION (Munger): Instead of asking how to succeed, ask what "
        "would cause failure. List every way this could go wrong. Then "
        "design your approach to prevent each failure mode."
    ),
    "five_whys": (
        "FIVE WHYS (Toyota): Keep asking WHY until you reach the root "
        "cause, not the symptom. The first answer is never the real answer. "
        "Dig at least 5 levels deep."
    ),
    "constraint_probe": (
        "CONSTRAINT PROBE (Mythos): The stated constraint is rarely the "
        "actual boundary. Decompose it into sub-channels. Find the gap "
        "between what is STATED as impossible and what is actually ENFORCED. "
        "The creative path lives in that gap."
    ),
    "pre_mortem": (
        "PRE-MORTEM (Klein): Imagine you already failed. What went wrong? "
        "Work backward from failure to identify risks BEFORE they happen."
    ),
    "second_order": (
        "SECOND-ORDER THINKING (Marks): Don't stop at the obvious effect. "
        "Ask: and then what? What are the consequences of the consequences? "
        "The non-obvious effects are where insight lives."
    ),
    "antifragility": (
        "ANTIFRAGILITY (Taleb): Don't just survive failure -- get STRONGER "
        "from it. Every failure is information. What did this failure teach "
        "us that success never would have? How does knowing this make us "
        "better at the next attempt?"
    ),
    "map_territory": (
        "MAP vs TERRITORY (Korzybski): Your model of the situation is NOT "
        "the situation. What you assume is happening may not match reality. "
        "Verify. Observe actual state, not expected state."
    ),
    "occams_razor": (
        "OCCAM'S RAZOR: The simplest explanation that fits all the facts is "
        "usually correct. Don't overcomplicate. If something looks like a "
        "duck and quacks like a duck, start there."
    ),
    "bias_for_action": (
        "BIAS FOR ACTION (Bezos): When the decision is reversible, act "
        "quickly. 70% certainty is enough. You learn more from one attempt "
        "than from infinite analysis. Move fast on reversible decisions."
    ),
    "circle_of_competence": (
        "CIRCLE OF COMPETENCE (Buffett): Know what you know and what you "
        "don't. When operating outside your knowledge, seek information "
        "first. Don't guess -- verify."
    ),
    "margin_of_safety": (
        "MARGIN OF SAFETY (Graham): Always leave room for error. Don't "
        "assume best case. Plan for what happens if your assumptions are "
        "wrong by 50%."
    ),
    "compounding": (
        "COMPOUNDING (Buffett): Small consistent improvements compound "
        "into massive advantages. What lesson from this interaction will "
        "make every future interaction 1% better?"
    ),
    "eat_the_frog": (
        "EAT THE FROG (Tracy): Do the hardest, most important thing first. "
        "Don't waste effort on easy low-value work when the high-value "
        "hard work is waiting."
    ),
    "reality_distortion": (
        "CREATIVE CONSTRAINT BREAKING (Jobs): Some constraints are real. "
        "Others exist only because nobody questioned them. When stuck, "
        "ask: is this constraint actually immovable, or just conventional?"
    ),
}

# Framework selection guidance -- which lenses to use when
FRAMEWORK_SELECTION_PROMPT = """You have access to these reasoning frameworks as thinking tools.
You don't need to use all of them. Select the 2-4 that are most relevant
to THIS specific situation and apply them.

Available frameworks:
{frameworks}

Apply the relevant frameworks to reason about the situation below.
Think flexibly -- these are lenses to see through, not scripts to follow.
If the situation requires thinking that no framework covers, think freely.
"""

# ---------------------------------------------------------------------------
# Core reasoning prompts
# ---------------------------------------------------------------------------

ORIENT_PROMPT = """You are Daena's cognitive engine. You THINK about situations,
you don't just pattern-match.

SITUATION:
{observation}

TASK: {task}

{failure_context}

Using the reasoning frameworks above, analyze this situation:
1. What is ACTUALLY happening here? (Map vs Territory -- verify, don't assume)
2. If something succeeded -- WHY? What defense was missing? What made it easy?
3. If something failed -- WHY really? Not the surface error. The root cause.
4. What does this teach us that we didn't know before?
5. What should we try next and WHY? (Not template-matching -- reason about THIS situation)

Think step by step. Be specific to this exact situation.
If something unexpected happened, that's the most interesting part -- explore it.
"""

DECIDE_PROMPT = """Based on your analysis, generate a concrete strategy.

ANALYSIS: {analysis}

AVAILABLE TOOLS: {available_tools}

PREVIOUS ATTEMPTS: {previous_attempts}

Generate a strategy with:
1. NAME: A short descriptive name
2. REASONING: Why this approach (specific to THIS situation, not generic)
3. STEPS: Concrete steps to execute (tool names + parameters)
4. RISKS: What could go wrong (pre-mortem)
5. SUCCESS_SIGNAL: How will we know it worked?
6. FAILURE_SIGNAL: How will we know to try something else?

Important: Don't repeat what already failed. Think creatively.
If standard approaches failed, what unconventional path might work?
"""

REFLECT_PROMPT = """Reflect on what just happened.

STRATEGY: {strategy}
RESULTS: {results}
SUCCESS: {success}

Answer honestly:
1. Did it work? If yes -- WHY? What was the key factor?
   (Understanding success is as important as understanding failure)
2. If it failed -- what is the ROOT CAUSE? Not the symptom.
   Apply 5 Whys: keep asking WHY until you reach something actionable.
3. What LESSON should Daena remember from this experience?
   (Something specific that makes future work better, not a platitude)
4. What CONSTRAINT did we discover? Was it real or assumed?
5. What should we try NEXT?
   (Novel reasoning about THIS situation, not a generic fallback)

Be specific. Generic lessons like "try harder" are useless.
A good lesson: "Google Cloud's datastudio subdomains return 404 with
HTTP/3 but the response includes Google Cloud Trace headers, revealing
the internal observability stack. This information disclosure pattern
likely exists on other Google regional endpoints."
"""

LEARNING_PROMPT = """Extract a permanent lesson from this experience.

FULL CONTEXT:
{full_context}

Generate a lesson that would be valuable in FUTURE situations.
Format:
- TRIGGER: When should this lesson activate? (situation description)
- LESSON: What should Daena know/do? (specific, actionable)
- CONFIDENCE: How confident are you this lesson is correct? (0.0-1.0)
- DOMAIN: What domain does this apply to? (security, debugging, architecture, general)
"""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReasoningResult:
    """Output of an LLM reasoning call."""
    analysis: str
    frameworks_used: list[str] = field(default_factory=list)
    model_used: str = ""
    reasoning_mode: str = "llm"  # "llm" or "deterministic"


@dataclass
class StrategyProposal:
    """A strategy generated by LLM reasoning."""
    name: str
    reasoning: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    success_signal: str = ""
    failure_signal: str = ""
    confidence: float = 0.5


@dataclass
class ReflectionResult:
    """Output of reflecting on an action's outcome."""
    analysis: str
    root_cause: str = ""
    lesson: str = ""
    constraint_discovered: str = ""
    next_suggestion: str = ""
    should_learn: bool = False


@dataclass
class LearnedLesson:
    """A permanent lesson extracted from experience."""
    trigger: str
    lesson: str
    confidence: float = 0.5
    domain: str = "general"


# ---------------------------------------------------------------------------
# Auto model selector
# ---------------------------------------------------------------------------

# Priority order: highest capability first.
# Reasoning models (deepseek-r1, qwq) are SLOWER due to internal chain-of-thought.
# Prefer standard models for general cognitive reasoning. Reasoning models are
# better suited for explicit "think" mode, not as default auto-selection.
_MODEL_PRIORITY = [
    # API models (strongest reasoning)
    # NOTE: provider values MUST match ModelProvider enum .value (UPPERCASE)
    ("ANTHROPIC", "claude-sonnet-4-20250514"),
    ("ANTHROPIC", "claude-3-5-sonnet-20241022"),
    ("OPENAI", "gpt-4o"),
    ("OPENAI", "o3-mini"),
    ("GEMINI", "gemini-2.5-pro"),
    ("GEMINI", "gemini-2.0-flash"),
    ("GROQ", "llama-3.3-70b-versatile"),
    # Local models (free, private) -- prefer fast standard models over slow reasoning
    ("OLLAMA", "qwen3.5:27b"),
    ("OLLAMA", "qwen3-coder:30b"),
    ("OLLAMA", "gemma4:26b"),
    ("OLLAMA", "qwen2.5-coder:14b"),
    ("OLLAMA", "llama3.1:8b"),
    ("OLLAMA", "mistral:7b"),
    ("OLLAMA", "qwen3.5:9b"),
    # Reasoning models last -- they work but are 5-10x slower
    ("OLLAMA", "deepseek-r1:14b"),
    ("OLLAMA", "deepseek-r1:8b"),
]


async def auto_select_model() -> tuple[str, str] | None:
    """Auto-select the best available model.

    Tries models from highest capability to lowest.
    Returns (provider_enum_value, model_id) or None if nothing available.
    """
    try:
        from app.core.constants import ModelProvider
        from app.services.model_registry import ModelRegistry

        registry = ModelRegistry()

        # Initialize if needed (discovers providers + models)
        await registry.initialize()

        # Get all available models
        available = await registry.list_all_models()
        available_set = {(m.provider.value, m.model_id) for m in available}

        for provider_str, model_id in _MODEL_PRIORITY:
            if (provider_str, model_id) in available_set:
                logger.info(
                    "cognitive_reasoner.model_selected",
                    provider=provider_str,
                    model=model_id,
                )
                return (provider_str, model_id)

        # Fallback: try any available model (prefer non-embed models)
        for m in available:
            if "embed" not in m.model_id.lower() and "nomic" not in m.model_id.lower():
                return (m.provider.value, m.model_id)

        if available:
            m = available[0]
            return (m.provider.value, m.model_id)

    except Exception as exc:
        logger.debug("cognitive_reasoner.model_select_failed", error=str(exc))

    return None


# ---------------------------------------------------------------------------
# CognitiveReasoner
# ---------------------------------------------------------------------------

class CognitiveReasoner:
    """LLM-powered reasoning engine for Daena.

    Uses the actual LLM to think about situations, not hardcoded
    if-else trees. The reasoning frameworks are LENSES in the prompt,
    not code paths.

    Reasoning escalation (when AGI mode is ON):
        1. Quintessence: Multi-model debate + DCP expert lenses + skills
           -> 3 models reason independently with different expert perspectives
           -> Primary model synthesizes into one conclusion
           This is the HIGHEST intelligence mode.
        2. Council: 3 models in parallel, meta-synthesis
        3. Single best model with all frameworks
        4. Deterministic fallback (no LLM)

    The cognitive reasoner auto-selects the highest available mode.
    In AGI mode, it prefers Quintessence so Daena debates with herself
    using multiple expert perspectives before deciding.

    Usage::

        reasoner = CognitiveReasoner(agi_mode=True)
        await reasoner.initialize()

        # Orient: analyze a situation
        result = await reasoner.orient(
            task="Find vulnerabilities in cloud.google.com",
            observation={"subdomains": 70, "all_404": True, "tech": ["HTTP/3"]},
        )

        # Decide: generate a strategy
        strategy = await reasoner.decide(
            analysis=result.analysis,
            available_tools=["subdomain_enum", "http_probe", ...],
        )

        # Reflect: learn from outcome
        reflection = await reasoner.reflect(
            strategy="header_analysis",
            results={"findings": 13},
            success=True,
        )
    """

    def __init__(
        self,
        *,
        agi_mode: bool = False,
        db: Any = None,
        user_id: Any = None,
        tenant_id: Any = None,
    ) -> None:
        self._provider: str = ""
        self._model_id: str = ""
        self._initialized: bool = False
        self._llm_available: bool = False
        self._agi_mode = agi_mode
        self._quintessence_available: bool = False
        self._db = db
        self._user_id = user_id
        self._tenant_id = tenant_id

    async def initialize(self) -> None:
        """Initialize by auto-selecting the best available model.

        In AGI mode, also checks if Quintessence is available
        (requires 2+ models for multi-model debate).
        """
        result = await auto_select_model()
        if result:
            self._provider, self._model_id = result
            self._llm_available = True

            # Check if Quintessence is available (AGI mode + 2+ models)
            if self._agi_mode:
                try:
                    from app.services.model_registry import ModelRegistry
                    registry = ModelRegistry()
                    await registry.initialize()  # Must initialize to discover providers
                    all_models = await registry.list_all_models()
                    # Filter out embedding models
                    reasoning_models = [
                        m for m in all_models
                        if "embed" not in m.model_id.lower() and "nomic" not in m.model_id.lower()
                    ]
                    model_count = len(reasoning_models)
                    if model_count >= 2:
                        self._quintessence_available = True
                    logger.info(
                        "cognitive_reasoner.quintessence_check",
                        reasoning_models=model_count,
                        available=self._quintessence_available,
                        model_ids=[m.model_id for m in reasoning_models[:5]],
                    )
                except Exception as exc:
                    logger.debug("cognitive_reasoner.quintessence_check_failed", error=str(exc))

            mode = "quintessence" if self._quintessence_available else "llm"
            logger.info(
                "cognitive_reasoner.initialized",
                provider=self._provider,
                model=self._model_id,
                mode=mode,
                agi=self._agi_mode,
                quintessence=self._quintessence_available,
            )
        else:
            self._llm_available = False
            logger.info("cognitive_reasoner.initialized", mode="deterministic")
        self._initialized = True

    @property
    def is_llm_available(self) -> bool:
        return self._llm_available

    @property
    def reasoning_mode(self) -> str:
        """Current reasoning mode."""
        if self._quintessence_available:
            return "quintessence"
        if self._llm_available:
            return "llm"
        return "deterministic"

    # ------------------------------------------------------------------
    # Core reasoning methods
    # ------------------------------------------------------------------

    async def orient(
        self,
        task: str,
        observation: dict[str, Any],
        *,
        previous_failures: list[dict[str, Any]] | None = None,
        memory_context: list[dict[str, Any]] | None = None,
    ) -> ReasoningResult:
        """ORIENT phase: Analyze the situation using reasoning frameworks.

        This is where the LLM THINKS about what's happening.
        Not pattern matching -- actual reasoning about THIS situation.
        """
        if not self._initialized:
            await self.initialize()

        # Build failure context
        failure_context = ""
        if previous_failures:
            failure_context = "PREVIOUS ATTEMPTS (DO NOT REPEAT):\n"
            for pf in previous_failures:
                failure_context += f"  - {pf.get('strategy', '?')}: FAILED -- {pf.get('reason', '?')}\n"
                if pf.get("lesson"):
                    failure_context += f"    Lesson learned: {pf['lesson']}\n"

        # Build memory context
        if memory_context:
            failure_context += "\nRELEVANT MEMORIES:\n"
            for mem in memory_context[:5]:
                failure_context += f"  - [{mem.get('tier', '?')}] {mem.get('content', '')[:200]}\n"

        # Select frameworks
        frameworks_text = "\n".join(
            f"- {name}: {desc}" for name, desc in FRAMEWORK_PROMPTS.items()
        )
        system_prompt = FRAMEWORK_SELECTION_PROMPT.format(frameworks=frameworks_text)

        user_prompt = ORIENT_PROMPT.format(
            observation=self._format_observation(observation),
            task=task,
            failure_context=failure_context,
        )

        if self._llm_available:
            response = await self._call_llm(system_prompt, user_prompt)
            if response:
                return ReasoningResult(
                    analysis=response,
                    frameworks_used=self._extract_frameworks_used(response),
                    model_used=self._model_id,
                    reasoning_mode="llm",
                )

        # Deterministic fallback
        return self._deterministic_orient(task, observation, previous_failures)

    async def decide(
        self,
        analysis: str,
        available_tools: list[str],
        *,
        previous_attempts: list[str] | None = None,
    ) -> StrategyProposal:
        """DECIDE phase: Generate a strategy based on the analysis.

        The LLM proposes what to do next, not a lookup table.
        """
        if not self._initialized:
            await self.initialize()

        user_prompt = DECIDE_PROMPT.format(
            analysis=analysis,
            available_tools=", ".join(available_tools),
            previous_attempts=", ".join(previous_attempts or []) or "None",
        )

        if self._llm_available:
            response = await self._call_llm("", user_prompt)
            if response:
                return self._parse_strategy(response)

        # Deterministic fallback
        return StrategyProposal(
            name="direct_execution",
            reasoning="No LLM available for creative reasoning. Executing standard approach.",
            steps=[{"operation": available_tools[0] if available_tools else "observe", "params": {}}],
            confidence=0.4,
        )

    async def reflect(
        self,
        strategy: str,
        results: dict[str, Any],
        success: bool,
        *,
        task: str = "",
    ) -> ReflectionResult:
        """REFLECT phase: Learn from what happened.

        This is where EQ + AQ live. Understanding WHY things happen
        (both success and failure) and extracting permanent lessons.
        """
        if not self._initialized:
            await self.initialize()

        user_prompt = REFLECT_PROMPT.format(
            strategy=strategy,
            results=self._format_observation(results),
            success="YES" if success else "NO",
        )

        if self._llm_available:
            response = await self._call_llm("", user_prompt)
            if response:
                return self._parse_reflection(response)

        # Deterministic fallback
        if success:
            return ReflectionResult(
                analysis=f"Strategy '{strategy}' succeeded.",
                lesson=f"Strategy '{strategy}' works for this type of task.",
                should_learn=True,
            )
        return ReflectionResult(
            analysis=f"Strategy '{strategy}' failed.",
            root_cause="Unknown (no LLM available for deep analysis).",
            next_suggestion="Try a different approach.",
        )

    async def extract_lesson(
        self,
        full_context: str,
    ) -> LearnedLesson | None:
        """Extract a permanent lesson from an experience.

        Called after reflect() when should_learn is True.
        Stores the lesson so Daena gets smarter over time.
        """
        if not self._llm_available:
            return None

        response = await self._call_llm("", LEARNING_PROMPT.format(
            full_context=full_context,
        ))
        if response:
            return self._parse_lesson(response)
        return None

    async def store_lesson(self, lesson: LearnedLesson) -> bool:
        """Store a learned lesson in NBMF memory.

        Lessons start at T1 (working memory, 7 days). If the same
        lesson is reinforced by future experiences, it promotes to T2
        (project, 1 year) and eventually T3 (institutional, permanent).

        This is how Daena develops EQ/IQ/AQ -- compounding knowledge
        from every experience.
        """
        if not self._db or not self._user_id or not self._tenant_id:
            logger.debug("cognitive_reasoner.store_lesson_skipped", reason="no db context")
            return False

        try:
            from app.services.memory import MemoryService

            memory_svc = MemoryService(self._db, self._user_id, self._tenant_id)
            content = (
                f"[LEARNED LESSON]\n"
                f"Trigger: {lesson.trigger}\n"
                f"Lesson: {lesson.lesson}\n"
                f"Domain: {lesson.domain}\n"
                f"Confidence: {lesson.confidence}\n"
            )
            await memory_svc.store(
                content=content,
                tier="T1",  # Start at working memory
                tags=["cognitive_lesson", lesson.domain],
            )
            logger.info(
                "cognitive_reasoner.lesson_stored",
                domain=lesson.domain,
                confidence=lesson.confidence,
                tier="T1",
            )
            return True
        except Exception as exc:
            logger.debug("cognitive_reasoner.lesson_store_failed", error=str(exc))
            return False

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str | None:
        """Make an LLM call using Daena's provider infrastructure.

        Escalation:
            1. Quintessence (AGI + 2+ models): Multi-model debate with
               DCP expert lenses. 3 models independently reason with
               different expert perspectives, primary synthesizes.
            2. Single model: Best available model with full prompt.
            3. None: Returns None, caller uses deterministic fallback.
        """
        # Try Quintessence first (AGI mode with multi-model debate)
        if self._quintessence_available:
            result = await self._call_quintessence(system_prompt, user_prompt)
            if result:
                return result
            # Fall through to single-model if Quintessence fails

        # Single model call
        try:
            from app.core.constants import ModelProvider
            from app.services.providers.base import GenerateRequest, LLMMessage
            from app.services.model_registry import ModelRegistry

            registry = ModelRegistry()
            await registry.initialize()
            # Use get_provider_for_model which searches by model_id across all providers
            provider = registry.get_provider_for_model(self._model_id)
            if not provider:
                # Fallback: try by provider enum
                try:
                    provider_enum = ModelProvider(self._provider)
                    provider = registry.get_provider(provider_enum)
                except (ValueError, KeyError):
                    pass
            if not provider:
                logger.warning("cognitive_reasoner.provider_not_found", provider=self._provider)
                return None

            messages = []
            if system_prompt:
                messages.append(LLMMessage(role="system", content=system_prompt))
            messages.append(LLMMessage(role="user", content=user_prompt))

            request = GenerateRequest(
                messages=messages,
                model_id=self._model_id,
                temperature=0.7,
                max_tokens=2048,
            )

            response = await provider.generate(request)
            logger.info(
                "cognitive_reasoner.llm_call",
                model=self._model_id,
                tokens_in=response.token_count_input,
                tokens_out=response.token_count_output,
                cost=response.cost_usd,
                mode="single",
            )
            return response.content

        except Exception as exc:
            import traceback
            logger.error(
                "cognitive_reasoner.llm_call_failed",
                error=str(exc),
                traceback=traceback.format_exc(),
                model=self._model_id,
                provider=self._provider,
            )
            return None

    async def _call_quintessence(self, system_prompt: str, user_prompt: str) -> str | None:
        """Multi-model debate via Quintessence (AGI mode).

        3 models reason independently, each with a different expert
        perspective (DCP). Primary model synthesizes into one conclusion.
        This is Daena debating with herself to find the best answer.
        """
        try:
            import asyncio
            from app.core.constants import ModelProvider
            from app.services.providers.base import GenerateRequest, LLMMessage
            from app.services.model_registry import ModelRegistry

            registry = ModelRegistry()
            await registry.initialize()  # Must initialize to discover providers
            all_models = await registry.list_all_models()
            healthy = [m for m in all_models if "embed" not in m.model_id.lower() and "nomic" not in m.model_id.lower()]

            if len(healthy) < 2:
                logger.warning("cognitive_reasoner.quintessence_insufficient_models", count=len(healthy))
                return None

            # Select up to 3 debate models with DIVERSITY constraint.
            #
            # Strategy:
            #   1. Primary Mind (self._model_id) is the SYNTHESIZER, never a debater.
            #   2. Pick one model per provider (diverse perspectives > duplicate providers).
            #   3. Rank: cloud API > CLI runtimes > local Ollama.
            #   4. Ollama only enters debate when <2 cloud/CLI models available.
            #      (Ollama loads one model at a time, so it's the fallback tier.)
            #
            # This gives: e.g., Perplexity (search-augmented) + Claude (deep reasoning)
            # + Codex (code execution) -- genuinely different capabilities per debate slot.
            # NOTE: Keys MUST be UPPERCASE to match ModelProvider.value
            _REASONING_RANK: dict[str, int] = {
                "PERPLEXITY": 10,    # Best for research/analysis with live search
                "ANTHROPIC": 9,      # Claude: strongest general reasoning
                "OPENAI": 8,         # Codex CLI / GPT-4o: strong reasoning + code execution
                "GEMINI": 7,         # Gemini: strong, good at code
                "GROQ": 6,           # Fast cloud inference
                "OPENROUTER": 5,     # Aggregator
                "TOGETHER": 4,       # Aggregator
                "OLLAMA": 2,         # Local -- only when cloud insufficient
            }

            # Exclude the primary/synthesizer model from debate
            primary_id = self._model_id
            candidates = [
                m for m in healthy
                if m.model_id != primary_id
            ]
            candidates.sort(
                key=lambda m: _REASONING_RANK.get(m.provider.value, 1),
                reverse=True,
            )

            # Pick one model per provider for maximum diversity
            debate_models = []
            seen_providers: set[str] = set()
            for m in candidates:
                prov = m.provider.value
                if prov in seen_providers:
                    continue
                debate_models.append(m)
                seen_providers.add(prov)
                if len(debate_models) >= 3:
                    break

            # If diversity constraint gave us too few, fill from remaining
            if len(debate_models) < 2:
                for m in candidates:
                    if m not in debate_models:
                        debate_models.append(m)
                    if len(debate_models) >= 3:
                        break

            logger.info(
                "cognitive_reasoner.quintessence_debate_models",
                synthesizer=(self._provider, primary_id),
                debaters=[(m.provider.value, m.model_id) for m in debate_models],
            )

            # DCP expert lenses for the debate
            expert_lenses = [
                "You are a SECURITY RESEARCHER with 15 years of experience. "
                "Think about attack surfaces, threat models, and defensive gaps.",
                "You are a SYSTEMS ARCHITECT who understands infrastructure deeply. "
                "Think about how systems are built, where complexity hides bugs, "
                "and what the developer likely overlooked.",
                "You are a RED TEAM OPERATOR who thinks adversarially. "
                "Think about what the defender assumes, and find the blind spots.",
            ]

            messages_base = []
            if system_prompt:
                messages_base.append(LLMMessage(role="system", content=system_prompt))

            # Fan out: each model gets a different expert lens
            async def debate_call(model_info, lens: str) -> str:
                provider = registry.get_provider(model_info.provider)
                if not provider:
                    return ""
                expert_msg = LLMMessage(
                    role="system",
                    content=f"[EXPERT PERSPECTIVE]\n{lens}",
                )
                msgs = messages_base + [expert_msg, LLMMessage(role="user", content=user_prompt)]
                req = GenerateRequest(
                    messages=msgs,
                    model_id=model_info.model_id,
                    temperature=0.7,
                    max_tokens=1500,
                )
                resp = await provider.generate(req)
                return resp.content

            # Run debate in parallel (asyncio.gather)
            tasks = []
            for i, model in enumerate(debate_models):
                lens = expert_lenses[i % len(expert_lenses)]
                tasks.append(debate_call(model, lens))

            debate_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out failures
            valid_responses = [
                r for r in debate_results
                if isinstance(r, str) and r.strip()
            ]

            if not valid_responses:
                return None

            # Synthesize: primary model combines all perspectives
            synthesis_prompt = (
                "You are Daena's cognitive synthesis engine. "
                "Multiple expert perspectives have analyzed the same situation. "
                "Synthesize their insights into ONE coherent analysis.\n\n"
                "Do NOT just summarize each perspective. Find the CONVERGENCE "
                "(where they agree), the TENSIONS (where they disagree), and "
                "the NOVEL INSIGHT (what emerges from combining them).\n\n"
            )
            for i, resp in enumerate(valid_responses):
                synthesis_prompt += f"--- Expert {i+1} ---\n{resp}\n\n"
            synthesis_prompt += "--- YOUR SYNTHESIS ---\n"

            primary_provider = registry.get_provider(ModelProvider(self._provider))
            if not primary_provider:
                return valid_responses[0]  # Just use first response

            synth_req = GenerateRequest(
                messages=[
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=synthesis_prompt),
                ],
                model_id=self._model_id,
                temperature=0.5,  # Lower temp for synthesis
                max_tokens=2048,
            )
            synth_resp = await primary_provider.generate(synth_req)

            logger.info(
                "cognitive_reasoner.quintessence_complete",
                debate_models=[m.model_id for m in debate_models],
                valid_responses=len(valid_responses),
                synthesis_model=self._model_id,
            )
            return synth_resp.content

        except Exception as exc:
            logger.error("cognitive_reasoner.quintessence_failed", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_observation(obs: dict[str, Any]) -> str:
        """Format observation dict into readable text for the LLM."""
        lines = []
        for key, value in obs.items():
            if isinstance(value, list) and len(value) > 10:
                lines.append(f"  {key}: {len(value)} items (first 5: {value[:5]})")
            elif isinstance(value, dict):
                lines.append(f"  {key}:")
                for k, v in list(value.items())[:10]:
                    lines.append(f"    {k}: {v}")
            else:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines) or "  (no data)"

    @staticmethod
    def _extract_frameworks_used(response: str) -> list[str]:
        """Extract which frameworks the LLM referenced in its response."""
        used = []
        response_lower = response.lower()
        for name in FRAMEWORK_PROMPTS:
            # Check for framework name or its key concept
            if name.replace("_", " ") in response_lower or name in response_lower:
                used.append(name)
        return used

    @staticmethod
    def _parse_strategy(response: str) -> StrategyProposal:
        """Parse LLM strategy response into StrategyProposal."""
        # Extract structured fields from free-form LLM response
        name = "llm_strategy"
        reasoning = response
        steps = []
        risks = []

        lines = response.split("\n")
        for line in lines:
            line_stripped = line.strip().lower()
            if line_stripped.startswith("name:"):
                name = line.strip().split(":", 1)[1].strip()
            elif line_stripped.startswith("reasoning:"):
                reasoning = line.strip().split(":", 1)[1].strip()
            elif line_stripped.startswith("risk"):
                risks.append(line.strip())

        return StrategyProposal(
            name=name[:50],
            reasoning=reasoning[:500],
            risks=risks[:5],
            confidence=0.6,
        )

    @staticmethod
    def _parse_reflection(response: str) -> ReflectionResult:
        """Parse LLM reflection response into ReflectionResult."""
        result = ReflectionResult(analysis=response)

        response_lower = response.lower()
        if "root cause" in response_lower:
            # Try to extract root cause section
            for line in response.split("\n"):
                if "root cause" in line.lower():
                    result.root_cause = line.strip()
                    break

        if "lesson" in response_lower or "learn" in response_lower:
            result.should_learn = True
            for line in response.split("\n"):
                if "lesson" in line.lower():
                    result.lesson = line.strip()
                    break

        if "next" in response_lower or "try" in response_lower:
            for line in response.split("\n"):
                if "next" in line.lower() or "try" in line.lower():
                    result.next_suggestion = line.strip()
                    break

        return result

    @staticmethod
    def _parse_lesson(response: str) -> LearnedLesson:
        """Parse LLM lesson response into LearnedLesson."""
        lesson = LearnedLesson(
            trigger="general",
            lesson=response[:500],
        )

        for line in response.split("\n"):
            line_stripped = line.strip().lower()
            if line_stripped.startswith("trigger:"):
                lesson.trigger = line.strip().split(":", 1)[1].strip()
            elif line_stripped.startswith("lesson:"):
                lesson.lesson = line.strip().split(":", 1)[1].strip()
            elif line_stripped.startswith("confidence:"):
                try:
                    lesson.confidence = float(line.strip().split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line_stripped.startswith("domain:"):
                lesson.domain = line.strip().split(":", 1)[1].strip()

        return lesson

    # ------------------------------------------------------------------
    # Deterministic fallback
    # ------------------------------------------------------------------

    def _deterministic_orient(
        self,
        task: str,
        observation: dict[str, Any],
        previous_failures: list[dict[str, Any]] | None,
    ) -> ReasoningResult:
        """Fallback orientation when no LLM is available.

        Uses the hardcoded constraint decompositions as a basic
        reasoning engine. Not as smart as LLM reasoning, but always works.
        """
        analysis_parts = [f"Task: {task}"]

        # Basic observation analysis
        if observation.get("waf_detected"):
            analysis_parts.append(f"WAF detected: {observation['waf_detected']}. Standard scans will be filtered.")
        if observation.get("all_404"):
            analysis_parts.append("All responses are 404. Target has catch-all routing or CDN.")
        if observation.get("technologies"):
            analysis_parts.append(f"Technologies: {observation['technologies']}")
        if previous_failures:
            analysis_parts.append(f"Previous failures: {len(previous_failures)}. Need different approach.")

        return ReasoningResult(
            analysis="\n".join(analysis_parts),
            frameworks_used=["deterministic_fallback"],
            model_used="none",
            reasoning_mode="deterministic",
        )
