# Laevateinn Cognitive OS -- Architecture

> "You don't beat a bigger brain by growing a bigger brain. You beat it by thinking about thinking."

## What Laevateinn Is

Laevateinn is Daena's cognitive engine -- a self-evolving intelligence layer that wraps any LLM to make it smarter through meta-reasoning, multi-model debate, recursive verification, and continuous self-improvement.

Named after the mythical Norse sword that cuts through illusion.

## Core Thesis

Single models have blind spots invisible to themselves. Laevateinn eliminates blind spots by:
1. **Understanding the question deeply** before any model sees it
2. **Scaling compute** proportional to difficulty (not one-size-fits-all)
3. **Making models debate** each other (not just self-correct)
4. **Verifying facts independently** (not confirming own hallucinations)
5. **Learning from every interaction** (weekly improvement, not annual)

## Architecture Overview

```
User Query
    |
    v
[Daena Pipeline: Security -> Session -> QueryUnderstanding -> Governance -> Cost -> Routing]
    |
    v
+=========================================================+
| LAEVATEINN SMART ORCHESTRATOR                            |
|                                                          |
| Stage 1: Deep Comprehension Engine (DCE)     [ALWAYS]    |
|   L0: Feynman compress (one clear sentence)              |
|   L1: Musk noise elimination (first principles)          |
|   L2: Tesla resonance (find the REAL question)           |
|   L3: ACH multi-interpretation (3-5 hypotheses)          |
|   -> Bloom's taxonomy level detection                    |
|                                                          |
| Stage 2: Dynamic Compute Scaler (DCS)        [ALWAYS]    |
|   Kahneman dual-process routing:                         |
|     TRIVIAL  -> System 1: 1 model, skip validation       |
|     STANDARD -> System 2 lite: enriched prompt            |
|     HARD     -> System 2: 3 models, AMD, RDE, gauntlet   |
|     BRUTAL   -> Full power: ALL models, max recursion     |
|                                                          |
| Stage 3: Adversarial Model Debate (AMD)      [HARD+]     |
|   Round 1: All models answer independently               |
|   Round 2: Each model critiques the OTHERS               |
|   Round 3: Each model defends or revises                 |
|   Round 4: Judge selects winner with reasoning           |
|                                                          |
| Stage 4: Recursive Depth Engine (RDE)        [STANDARD+] |
|   + Chain-of-Verification (CoVe)                         |
|   Generate verification questions about the answer       |
|   Answer them INDEPENDENTLY (no self-confirmation bias)  |
|   Cross-check for inconsistencies                        |
|   Regenerate with failure context if needed              |
|                                                          |
| Stage 5: Validation Gauntlet                 [STANDARD+] |
|   1. Feynman Test: explain in 2 sentences                |
|   2. Popper Test: 3 ways this could be wrong             |
|   3. Buffett Inversion: map failure modes                |
|   4. Hacker Test: 5 adversarial challenges               |
|   5. CoVe Verification: cross-check facts                |
|   6. Temporal Validity: is this time-sensitive?           |
|                                                          |
| Stage 6: Jobs Delivery Engine                [ALWAYS]     |
|   Remove hedges, add confidence scores                   |
|   Extract key points (max 3)                             |
|   Predict follow-up questions (SPC)                      |
+=========================================================+
    |
    v
[Daena Pipeline: Stream -> Persist -> Cost -> Audit]
    |
    v (async, non-blocking)
[Self-Evolution: InteractionLogger + PKG + MetaMonitor]
```

## Compute Profiles

| Difficulty | Models | Recursion | Validation | AMD Rounds | Target Latency |
|---|---|---|---|---|---|
| TRIVIAL | 1 fastest | 0 | none | 0 | <500ms |
| STANDARD | 1 best-fit | 1 | Feynman only | 0 | <3s |
| HARD | 3 parallel | 3 | Full gauntlet | 2 | <15s |
| BRUTAL | ALL available | 5 | Gauntlet + CoVe | 3 | <45s |

## Module Map (15 modules)

```
backend/app/services/laevateinn/
  __init__.py                 # 15 exports

  # Core Pipeline (Stages 1-6)
  types.py                    # 15 data structures
  comprehension.py            # DCE: Feynman/Musk/Tesla/ACH/Bloom
  compute_scaler.py           # DCS + Kahneman dual-process routing
  debate.py                   # AMD: 4-round adversarial model debate
  depth_engine.py             # RDE + Chain-of-Verification (CoVe)
  validation.py               # 6-test Validation Gauntlet
  delivery.py                 # Jobs Delivery + speculative followups
  pipeline.py                 # Full pipeline orchestrator

  # Intelligence Extensions
  code_verifier.py            # Execute code mid-reasoning (sandbox)
  deep_think.py               # Extended thinking (<think> tag parsing)
  tool_augmented.py           # Tools in verification loop (search, math, code)

  # Self-Evolution (Stage 7)
  episodic_memory.py          # Experience-based recall (sessions, decisions, patterns)
  interaction_logger.py       # DPO training data accumulation + implicit feedback
  knowledge_graph.py          # PKG: entities, relationships, patterns
  meta_monitor.py             # Laevateinn watching Laevateinn
  speculative.py              # SPC: pre-compute follow-ups in background
```

## Integration with Daena

Laevateinn is wired into `chat_orchestrator.py` at Stage 6.8 (between skill retrieval and LLM request building):

- **DCE always runs** (<10ms overhead, enriches every query)
- **DCS decides** which stages execute (Kahneman routing)
- **HARD/BRUTAL bypasses** normal LLM call with debate-verified answer
- **Post-response** logging is async (PKG + InteractionLogger + MetaMonitor)
- **Laevateinn is non-critical** -- if anything fails, falls through to normal pipeline

## Provider Strategy

- **Primary:** vLLM (cloud deploy, PagedAttention, high concurrency)
- **Fallback:** Ollama (local Windows dev, always available)
- **Top models:** Gemma 4 31B, DeepSeek R1 14B, Qwen3-Coder 30B, Qwen3.5 27B

## Self-Evolution Loop

After every response (async, non-blocking):

1. **InteractionLogger** records query/response with implicit feedback scoring
2. **PKG** ingests entities, relationships, and patterns from the interaction
3. **MetaMonitor** records pipeline trace (which stages helped, which hurt)
4. **EpisodicMemory** stores the experience for future retrieval

Weekly:
- Export top interactions for DPO fine-tuning
- Generate MetaReport (stage performance, model win rates, calibration accuracy)
- Constitutional self-improvement: generate new pipeline rules from failure patterns

## Test Coverage

- 80 dedicated Laevateinn tests (46 core + 34 extensions)
- Full Daena suite: 1692/1692 passing
- Zero regressions from integration
