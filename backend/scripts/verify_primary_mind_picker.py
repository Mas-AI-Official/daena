"""verify_primary_mind_picker.py

PROVES the auto-pick-highest-tier-per-platform contract end-to-end.

For each value of `primary_mind` (None, claude_code, codex, gemini_cli,
ollama, grok_cli, perplexity), call ModelRouter.route() with both STANDARD
and COUNCIL modes against the live ModelRegistry. Print:

  - which model wins as `decision.primary` (and its `priority` tag state)
  - the council debate roster and which provider was excluded as Judge
  - top-5 scored candidates so we can see WHY the picker chose what it did

Run from D:\\Ideas\\Daena\\backend with the project venv:
    .\\venv_daena\\Scripts\\python.exe scripts\\verify_primary_mind_picker.py

If a provider is not configured (no API key, CLI not authed) it will be
absent from the candidate list -- that is normal and the picker falls
through to the next-best provider.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.constants import RoutingMode  # noqa: E402
from app.services.model_registry import ModelRegistry  # noqa: E402
from app.services.model_router import ModelRouter  # noqa: E402
from app.services.query_understanding import (  # noqa: E402
    ComplexityLabel,
    IntentType,
    QueryUnderstanding,
    RiskLevel,
)


CASES = [
    None,           # auto -- whatever scoring picks
    "claude_code",  # should win Anthropic priority-tagged flagship
    "codex",        # should win OpenAI priority-tagged flagship
    "gemini_cli",   # should win Gemini priority-tagged flagship
    "ollama",       # should win local
    "grok_cli",     # falls through if not registered
    "perplexity",   # provider value direct
]


def _make_qu(intent: IntentType, complexity: ComplexityLabel) -> QueryUnderstanding:
    """Synthetic QueryUnderstanding mimicking what Stage 2 emits."""
    return QueryUnderstanding(
        intent=intent,
        confidence=0.95,
        complexity_score=0.5 if complexity == ComplexityLabel.MODERATE else 0.9,
        complexity_label=complexity,
        risk_level=RiskLevel.MEDIUM,
        governance_tier=1,
        suggested_mode=RoutingMode.STANDARD,
        suggested_providers=[],
        ambiguity_signals=[],
        clarifying_question=None,
        processing_time_ms=2,
    )


async def run() -> int:
    print("=" * 78)
    print("Daena Primary Mind picker -- live verification")
    print("=" * 78)

    registry = ModelRegistry()
    await registry.initialize()
    router = ModelRouter(registry)

    available = list(registry.available_providers)
    print(f"\nProviders configured/available: {[p.value for p in available]}")
    print(f"Model cache: {len(registry._model_cache)} models")

    flagship_priority = []
    for mid, info in registry._model_cache.items():
        tags = [t.lower() for t in (info.tags or [])]
        if "priority" in tags:
            flagship_priority.append(f"  {info.provider.value}: {mid}  tags={tags}")
    print("\nPriority-tagged flagships in catalog:")
    print("\n".join(flagship_priority) or "  (none -- catalog drift, picker will fall back)")

    # ── STANDARD MODE: COMPLEX query -----------------------------------------
    print("\n" + "=" * 78)
    print("STANDARD mode, COMPLEX/MULTI_STEP intent")
    print("=" * 78)
    qu = _make_qu(IntentType.MULTI_STEP, ComplexityLabel.COMPLEX)
    for primary_mind in CASES:
        decision = router.route(
            qu, requested_mode=RoutingMode.STANDARD, primary_mind=primary_mind,
        )
        chosen = decision.primary
        meta = decision.metadata
        boosted = meta.get("primary_mind_boosted", False)
        priority_hit = meta.get("primary_mind_priority_tier", False)
        unavailable = meta.get("primary_mind_available") is False
        flag = (
            "PRIORITY-TIER" if priority_hit
            else "BOOSTED" if boosted
            else "NOT-AVAILABLE" if unavailable
            else "AUTO"
        )
        top5 = ", ".join(c["model_id"] for c in meta.get("top_candidates", [])[:5])
        print(
            f"  primary_mind={str(primary_mind):<14}  ->  {chosen.model_id:<35}"
            f"  ({chosen.provider.value:<12}) score={chosen.score:>6.3f}  [{flag}]"
        )
        print(f"      top-5 candidates: {top5}")

    # ── COUNCIL MODE: same intent, judge vs debaters --------------------------
    print("\n" + "=" * 78)
    print("COUNCIL mode -- effort=medium -- Primary Mind as JUDGE, OTHERS as debaters")
    print("=" * 78)
    qu_c = _make_qu(IntentType.ANALYSIS, ComplexityLabel.COMPLEX)
    for primary_mind in [pm for pm in CASES if pm is not None]:
        decision = router.route(
            qu_c, requested_mode=RoutingMode.COUNCIL, primary_mind=primary_mind,
            effort_level="medium",
        )
        debaters = [c.model_id for c in decision.council_models]
        debater_providers = [c.provider.value for c in decision.council_models]
        print(
            f"  Judge ({primary_mind:<14}) = {decision.primary.model_id:<30} "
            f"  | debaters: {debaters}"
        )
        print(f"      debater providers: {debater_providers}")

    # ── COUNCIL MODE @ HIGH effort -------------------------------------------
    # Step 1 of Council R2 plan (2026-04-25). When complexity is COMPLEX /
    # MULTI_STEP / VERY_COMPLEX, the orchestrator passes effort_level in
    # {"high","xhigh"} to the router. The router admits the Primary Mind's
    # provider AS A DEBATER alongside being the Chairman.
    # Slim-Claude-as-proposer (proposer_system_prompt, no cognitive layer) and
    # full-Claude-as-Chairman (full system_prompt with cognitive toolkit + DCP
    # experts) are DIFFERENT reasoning surfaces even at the same model_id.
    print("\n" + "=" * 78)
    print("COUNCIL mode -- effort=high -- Primary Mind in BOTH chairman + debater")
    print("=" * 78)
    for primary_mind in [pm for pm in CASES if pm is not None]:
        decision = router.route(
            qu_c, requested_mode=RoutingMode.COUNCIL, primary_mind=primary_mind,
            effort_level="high",
        )
        debaters = [c.model_id for c in decision.council_models]
        debater_providers = [c.provider.value for c in decision.council_models]
        chairman_provider = decision.primary.provider.value
        same_provider_debater = chairman_provider in debater_providers
        flag = "SAME-PROVIDER-DEBATER OK" if same_provider_debater else "(no same-provider in roster)"
        print(
            f"  Judge ({primary_mind:<14}) = {decision.primary.model_id:<30} "
            f"  | {flag}"
        )
        print(f"      debaters: {debaters}")
        print(f"      debater providers: {debater_providers}")

    # ── Edge: what happens if catalog is missing the priority tag for a CLI? --
    print("\n" + "=" * 78)
    print("Sanity: every priority-tagged candidate should NEVER be a flash/mini/haiku")
    print("=" * 78)
    bad = []
    for mid, info in registry._model_cache.items():
        tags = [t.lower() for t in (info.tags or [])]
        if "priority" in tags:
            mid_lower = mid.lower()
            for forbidden in ("flash", "mini", "haiku", "instant", "nano"):
                if forbidden in mid_lower:
                    bad.append(f"  WARN: {info.provider.value}/{mid} priority-tagged but contains {forbidden!r}")
    print("\n".join(bad) or "  OK -- no cheap models slipped into the priority slot.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
