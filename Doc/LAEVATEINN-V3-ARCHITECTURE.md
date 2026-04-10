# Laevateinn v3: Beyond-Mythos Cognitive Architecture
**Date:** 2026-04-10
**Version:** v3.0.0

## Overview

Laevateinn is Daena's cognitive engine -- the intelligence layer that makes any LLM smarter through system-level orchestration. v3 adds 4 capabilities that go beyond what any other reasoning system (including Mythos) has achieved.

## Key Insight: System-Level vs Weight-Level

Mythos-style improvements operate at the model weight level: expensive to train, locked to one model, slow to iterate. Laevateinn operates at the system orchestration level: deploys as code, works on every model, iterates in hours not months.

## Architecture

### Pipeline (10 stages)

```
Stage 1:   DCE (Deep Comprehension Engine)
           |-- L0: Feynman compress + Polya decompose
           |-- L1: Musk noise elimination (first principles)
           |-- L2: Tesla resonance (find REAL question)
           |-- L3: ACH multi-interpretation (3-5 scored)
           '-- Bloom taxonomy classification

Stage 1.5: EPISTEMIC STATE TRACKER [v3 NEW]
           |-- Classify uncertainty SHAPE:
           |   |-- CONTRADICTORY -> deepen debate
           |   |-- ABSENT -> search externally
           |   |-- AMBIGUOUS -> re-comprehend
           |   '-- COMPUTATIONAL -> execute code
           '-- Meta-strategy selection (HOW to reason)

Stage 2:   DCS (Dynamic Compute Scaler)
           |-- Kahneman System 1/2 routing
           |-- TRIVIAL / STANDARD / HARD / BRUTAL
           '-- Epistemic boost for high uncertainty

Stage 3:   AMD (Adversarial Model Debate) [v3 UPGRADED]
           |-- Round 1: Independent parallel answers
           |-- Round 1.5: Identify SPECIFIC disagreements [NEW]
           |-- Round 2: Argue disagreements WITH EVIDENCE [NEW]
           |-- Round 3: Defense/revision on focused critiques
           '-- Round 4: Judge selects winner

Stage 4:   RDE (Recursive Depth Engine) + CoVe
           |-- Generate verification questions
           |-- Answer independently (no cross-contamination)
           |-- Cross-check for inconsistencies
           |-- Self-critique with context
           '-- Regenerate if needed (up to 5 loops)

Stage 4.5: CRG (Causal Reasoning Graph) [v3 NEW]
           |-- Decompose into claim-nodes + logic-edges
           |-- Verify edges (does A actually support B?)
           |-- Identify load-bearing nodes
           |-- Check completeness (missing claims?)
           '-- Detect composition fallacies

Stage 5:   VALIDATION GAUNTLET
           |-- Feynman: explain simply
           |-- Popper: 3 falsification scenarios
           |-- Buffett: failure mode mapping
           |-- Hacker: 5 adversarial challenges
           |-- CoVe: cross-check with RDE
           '-- Temporal: time-sensitivity check

Stage 5.5: ADVERSARIAL VERIFICATION GATE [v3 NEW]
           |-- "If wrong, what evidence would exist?"
           |-- Check with CHEAP model (different blind spots)
           |-- Counter-evidence found -> loop to RDE
           '-- Not found -> confidence boost + deliver

Stage 6:   DELIVERY (Jobs Delivery Engine)
           |-- Hedge removal
           |-- Key point extraction
           |-- Confidence aggregation + gate boost
           |-- Format matching (technical/creative/concise)
           '-- Speculative follow-up prediction

Stage 7:   SELF-EVOLUTION (async, post-delivery)
```

### File Map

```
backend/app/services/laevateinn/
|-- __init__.py              Module exports
|-- types.py                 All data structures (17 types)
|-- pipeline.py              Main orchestrator (10 stages)
|-- comprehension.py         Stage 1: DCE
|-- epistemic_tracker.py     Stage 1.5: Epistemic State [v3]
|-- compute_scaler.py        Stage 2: DCS
|-- debate.py                Stage 3: AMD (with disagreement focus)
|-- depth_engine.py          Stage 4: RDE + CoVe
|-- causal_graph.py          Stage 4.5: CRG [v3]
|-- validation.py            Stage 5: Gauntlet
|-- adversarial_gate.py      Stage 5.5: Adversarial Gate [v3]
|-- delivery.py              Stage 6: Delivery
|-- code_verifier.py         Code execution mid-reasoning
|-- deep_think.py            Extended thinking mode
|-- episodic_memory.py       Experience-based recall
|-- interaction_logger.py    Training data accumulation
|-- tool_augmented.py        Search/tools in RDE loop
|-- knowledge_graph.py       Persistent knowledge graph
|-- meta_monitor.py          System health monitoring
'-- speculative.py           Speculative pre-computation
```

### Type System (types.py)

```python
# Enums
Difficulty          TRIVIAL | STANDARD | HARD | BRUTAL
BloomLevel          REMEMBER | UNDERSTAND | APPLY | ANALYZE | EVALUATE | CREATE
CognitiveSystem     SYSTEM_1 | SYSTEM_2
UncertaintyShape    CONTRADICTORY | ABSENT | AMBIGUOUS | COMPUTATIONAL | CONFIDENT
ReasoningStrategy   DEPTH_FIRST | BREADTH_FIRST | CONSTRAINT_PROPAGATION | HYPOTHESIS_DRIVEN | ANALOGICAL | STANDARD

# Core results
ComprehensionResult     DCE output (query enrichment)
ComputeProfile          DCS output (budget allocation)
DebateResult            AMD output (winner + disagreements)
DepthResult             RDE output (verified answer)
CausalGraphResult       CRG output (structural validity)  [v3]
ValidationResult        Gauntlet output (6-test results)
AdversarialGateResult   Gate output (counter-evidence)     [v3]
EpistemicState          Tracker output (uncertainty shape)  [v3]
DeliveryResult          Final formatted response

# Supporting types
Interpretation          ACH hypothesis
VerificationQuestion    CoVe fact-check question
DebateRound             Single debate round
DisagreementPoint       Specific model conflict             [v3]
CausalNode              Claim in reasoning graph            [v3]
CausalEdge              Logic between claims                [v3]

# Trace
LaevateinnTrace         Full pipeline execution record
```

### Model Tiering

| Role | Preferred Model | Cost | Why |
|---|---|---|---|
| Primary generation | Best available | $$$ | Quality matters most here |
| Debate participants | 2-3 diverse models | $$ | Different perspectives |
| CoVe verification | Different from primary | $$ | Independent blind spots |
| Adversarial gate | Cheapest (7B Ollama) | $ | Just checking evidence |
| Heuristic stages | No LLM | Free | DCE, Gauntlet, DCS, Epistemic |

### Performance Matrix

| Difficulty | Models | RDE | AMD | CRG | Gate | Latency |
|---|---|---|---|---|---|---|
| TRIVIAL | 1 | 0 | 0 | -- | -- | <1s |
| STANDARD | 1 | 1 | 0 | -- | Yes | 2-3s |
| HARD | 3 | 2 | 3 rounds | Yes | Yes | 5-15s |
| BRUTAL | All | 5 | 4 rounds | Yes | Yes | 15-60s |

### Loop-Back Architecture

```
                   +--[CRG invalid]--+
                   |                 |
Answer -> [RDE] --+--> [Gauntlet] --+--> [AdvGate] --> [Delivery]
  ^        |       |                 |        |
  |        v       +--[fail]--------+        |
  +---[regenerate with failure context]<-----+
                                    [counter-evidence found]
```

Three independent verification stages can each loop back to RDE:
- CRG: composition invalid -> RDE with structural context
- Gauntlet: validation failed -> RDE with gauntlet context
- AdvGate: counter-evidence found -> RDE with counter-evidence

This creates a self-correcting mesh, not a linear pipeline.

## Beyond Mythos: What We Have That Nobody Else Does

1. **Epistemic State Tracking**: SHAPE of uncertainty, not just level
2. **Causal Reasoning Graph**: Structural verification of logic, not just facts
3. **Adversarial Verification Gate**: Active falsification before delivery
4. **Disagreement-Focused Debate**: Arguments on specific conflicts, not broad critiques
5. **Meta-Strategy Selection**: Choose reasoning approach before starting
6. **Model Tiering**: Cheap verification, expensive generation
7. **Multi-Runtime**: Same pipeline governs any model from any provider
