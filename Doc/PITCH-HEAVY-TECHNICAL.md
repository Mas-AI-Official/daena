# Daena Laevateinn v3: Beyond-Mythos Cognitive Architecture

## Technical Deep Dive

### Architecture Overview

Laevateinn v3 is a 10-stage cognitive pipeline that operates at the **system orchestration level**, not the model weight level. This is architecturally fundamental: improvements at the model level (Mythos, o1-style reasoning, chain-of-thought) require billions in training compute and are locked to a single model. Laevateinn improvements deploy as code changes across ALL models simultaneously.

```
Query -> [DCE] -> [Epistemic] -> [DCS] -> [AMD] -> [RDE] -> [CRG] -> [Gauntlet] -> [AdvGate] -> [Delivery]
           |          |            |         |        |        |          |             |
           v          v            v         v        v        v          v             v
        Comprehend  Classify    Scale     Debate   Recurse  Verify    Validate    Falsify
        the query   uncertainty compute   models   & verify structure  6 tests    counter-
                    SHAPE       budget    on       claims   of logic             evidence
                                         conflicts
```

### Stage-by-Stage Technical Specification

#### Stage 1: Deep Comprehension Engine (DCE)
- **L0 Feynman Intake**: Compress query to single clear sentence + Polya decomposition into sub-questions
- **L1 Musk Noise Elimination**: Strip hedges, politeness, noise to first principles
- **L2 Tesla Resonance**: Detect the REAL question ("How do I X?" -> "What's the best approach for X?")
- **L3 ACH Multi-Interpretation**: Generate 3-5 scored interpretations using Analysis of Competing Hypotheses
- **Bloom Classification**: Map to taxonomy level (REMEMBER through CREATE) for compute routing
- **Latency**: <10ms heuristic mode, 200-500ms LLM mode

#### Stage 1.5: Epistemic State Tracker (BEYOND MYTHOS)
- **Uncertainty Shape Classification**: Not just confidence level, but the TYPE of uncertainty
  - `CONTRADICTORY`: Evidence conflicts -- route to deeper AMD debate
  - `ABSENT`: No evidence exists -- trigger tool use / external search
  - `AMBIGUOUS`: Multiple valid interpretations -- re-comprehend via DCE
  - `COMPUTATIONAL`: Can't verify analytically -- execute code
  - `CONFIDENT`: Low uncertainty -- proceed at standard compute
- **Meta-Strategy Selection**: Chooses reasoning APPROACH before reasoning starts
  - `DEPTH_FIRST`: Deep recursive analysis (for contradictions)
  - `BREADTH_FIRST`: Explore many options (for ambiguity)
  - `HYPOTHESIS_DRIVEN`: Test and eliminate (for computation)
  - `CONSTRAINT_PROPAGATION`: Narrow from constraints (for analysis)
  - `ANALOGICAL`: Import from other domains (for creation)
- **Compute Boost**: Uncertain queries automatically get deeper processing

#### Stage 2: Dynamic Compute Scaler (DCS)
- **Kahneman Dual-Process Router**: System 1 (fast, intuitive) vs System 2 (slow, deliberate)
- **Difficulty Classification**: TRIVIAL / STANDARD / HARD / BRUTAL
- **Budget Allocation**: num_models, recursion_depth, validation_level, amd_rounds, target_latency_ms
- **Epistemic Override**: CONTRADICTORY/ABSENT shapes boost compute automatically

#### Stage 3: Adversarial Model Debate (AMD) with Disagreement Focus (UPGRADED)
- **Round 1**: All models answer independently (asyncio.gather, parallel)
- **Round 1.5**: Identify SPECIFIC disagreement points between answers (NEW)
- **Round 2**: Models argue their case WITH EVIDENCE on each disagreement point (NEW)
  - Old approach: broad critique of whole answer
  - New approach: focused argumentation on exact conflict points
- **Round 3**: Defense/revision based on targeted critiques
- **Round 4**: Judge model selects winner with reasoning
- **Disagreement Tracking**: Structured `DisagreementPoint` objects with topic, positions per model, resolution

#### Stage 4: Recursive Depth Engine (RDE) + Chain-of-Verification
- **CoVe Protocol**: Generate verification questions -> answer independently (NO context from original, prevents self-confirmation) -> cross-check for inconsistencies
- **Recursive Loop**: If inconsistencies found -> self-critique with context -> regenerate -> verify again
- **Model Independence**: Uses DIFFERENT model for verification than generation (eliminates shared blind spots)
- **Budget**: Up to 5 recursive loops for BRUTAL difficulty

#### Stage 4.5: Causal Reasoning Graph (CRG) (BEYOND MYTHOS)
- **Three-Layer Verification**:
  1. **Node verification**: Are individual claims true? (handled by CoVe)
  2. **Edge verification**: Do logical connections hold? ("A supports B" -- does A actually imply B?)
  3. **Completeness verification**: Are load-bearing claims MISSING from the reasoning?
- **Composition Fallacy Detection**: Catches cases where each step is correct but the conclusion is invalid
  - Example: "Python is fast (for dev)" + "need fast (runtime)" -> "Use Python" = WRONG (equivocation on "fast")
- **Load-Bearing Node Identification**: Marks which claims, if false, would invalidate the conclusion
- **Loop-Back**: Invalid composition sends answer back to RDE with structural failure context

#### Stage 5: Validation Gauntlet
- **Feynman Test**: Can the answer be explained in 2 simple sentences?
- **Popper Test**: 3 specific ways this answer could be wrong
- **Buffett Inversion**: Map all failure modes ("tell me where I'll die so I never go there")
- **Hacker Test**: 5 adversarial challenges (security, edge cases, injection)
- **CoVe Test**: Cross-check with Stage 4 verification results
- **Temporal Test**: Is this answer time-sensitive? Will it become stale?

#### Stage 5.5: Adversarial Verification Gate (BEYOND MYTHOS)
- **Counter-Evidence Generation**: "If this answer is WRONG, what evidence would I expect to see?"
- **Cheap Model Checking**: Uses smallest available model (Ollama 7B) to check for counter-evidence
  - Different model = different blind spots = genuine independence
  - Cheap model = near-zero cost for the gate
- **Modus Tollens Reasoning**: Instead of confirming (confirmation bias), actively seeks disconfirmation
- **Gate Protocol**: Counter-evidence found -> loop back to RDE -> re-verify -> deliver
- **Confidence Boost**: Surviving the gate adds +5% to +15% confidence (scaled by difficulty)

#### Stage 6: Jobs Delivery Engine
- Hedge removal, key point extraction, confidence aggregation
- Format matching (technical/creative/concise based on Bloom level)
- Speculative follow-up prediction (3 most likely next questions)
- Adversarial gate confidence boost applied at delivery

### Performance Characteristics

| Difficulty | Models | RDE Depth | AMD Rounds | CRG | Adv Gate | Target Latency |
|---|---|---|---|---|---|---|
| TRIVIAL | 1 | 0 | 0 | Skip | Skip | <1s |
| STANDARD | 1 | 1 | 0 | Skip | Run | 2-3s |
| HARD | 3 | 2 | 3 | Run | Run | 5-15s |
| BRUTAL | All | 5 | 4 | Run | Run | 15-60s |

### Model Tiering Strategy

| Role | Model Type | Cost | Purpose |
|---|---|---|---|
| Primary Generation | Best available (Claude, GPT-4, DeepSeek-R1) | $$$ | Quality answer generation |
| Debate Participants | Multiple diverse models | $$ | Eliminate shared blind spots |
| Verification (CoVe) | Different model from primary | $$ | Independent fact-checking |
| Adversarial Gate | Cheapest (Ollama 7B, Mistral 7B) | $ | Counter-evidence checking |
| Heuristic Stages | No LLM (regex/rules) | Free | DCE, Gauntlet, DCS |

### Unique Capabilities (No Other System Has These)

1. **Epistemic State Tracking**: Classifies the SHAPE of uncertainty, not just level. Routes each shape to optimal resolution.
2. **Causal Reasoning Graph**: Verifies logical STRUCTURE (edges between claims), not just individual facts (nodes).
3. **Adversarial Verification Gate**: Actively tries to PROVE ITSELF WRONG before delivery using counter-evidence.
4. **Disagreement-Focused Debate**: Models argue specific CONFLICTS with evidence, not general critiques.
5. **Meta-Strategy Selection**: Chooses HOW to reason (depth-first, breadth-first, analogical, etc.) BEFORE starting.
6. **Multi-Runtime Governance**: Same pipeline governs Claude, GPT, Gemini, Ollama -- any model, same verification.

### Technology Stack

- **Backend**: Python 3.12, FastAPI (async), SQLAlchemy 2.0, Pydantic v2
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS + Zustand
- **LLM Integration**: 9 providers (Ollama, Claude, GPT, Gemini, Groq, OpenRouter, Together, Perplexity, Codex)
- **Execution**: asyncio.gather for parallel model calls, SSE streaming
- **Tests**: 1328/1328 passing, zero TS errors
- **Architecture**: Multi-tenant, governed-first, audit-everything

### Patent-Pending IP

- **PhiLattice Architecture**: Fibonacci-derived hexagonal topology for department placement
- **NBMF (Neural-Backed Memory Fabric)**: 5-tier memory with hallucination auto-expiry

---

*Laevateinn v3 -- The sword that cuts through illusion, now sharper than ever.*
