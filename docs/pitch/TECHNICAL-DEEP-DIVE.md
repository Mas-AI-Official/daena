# Daena Technical Architecture -- Deep Dive

## For Technical Evaluators, CTOs, and Engineering Teams

**Version:** 3.6.0-production | **Date:** 2026-04-05 | **MAS-AI Technologies Inc.**

This document is an engineer-to-engineer walkthrough of Daena's architecture. It covers algorithms, data structures, complexity analysis, and performance characteristics. No marketing abstractions.

---

## 1. System Architecture Overview

Daena processes every user request through a 10-stage governed pipeline. Three orthogonal control layers determine behavior independently:

- **Reasoning Mode** (how it thinks): Standard | Council | Quintessence
- **Action Mode** (what it does): CMD (read-only) | EXE (side effects via DaenaBot)
- **Continuation Mode** (does it keep working): Autopilot OFF | Autopilot ON

These are independent axes. Any combination is valid: Quintessence + EXE + Autopilot ON gives full-power autonomous execution with multi-model debate and governance.

### Full Pipeline Data Flow

```
User Input
  |
  v
+--[1. SecurityGate]---------> REJECT (injection detected)
  |                            60+ regex patterns, 5 categories
  v
+--[2. LoadSession]----------> Fetch session + last 20 messages
  |                            O(1) lookup, 30s TTL cache
  v
+--[3. QueryUnderstanding]---> Intent, complexity, risk class
  |                            Bloom's taxonomy + syntactic scoring
  v
+--[4. GovernanceCheck]------> Policy eval (tier 0-4)
  |                            9 hard laws checked first (O(1))
  v
+--[5. CostPreflight]-------> Budget validation
  |                            Per-tenant token budget enforcement
  v
+--[6. ModelRouter]----------> Model selection via scoring
  |                            tag_match(0.40) + locality(0.25) +
  |                            cost(0.20) + context_window(0.15)
  v
+--[6.8 Laevateinn]---------  DCE (always) -> DCS -> [AMD if HARD+]
  |  |                         -> [RDE + CoVe if STANDARD+]
  |  |                         -> [Validation Gauntlet] -> Delivery
  |  v
+--[7. MemoryRecall]---------> Context enrichment from NBMF tiers
  |                            Top-k retrieval, trust-weighted
  v
+--[8. BuildRequest]---------> Format messages + system prompt
  |                            + DaenaBot dispatch (EXE mode)
  v
+--[9. LLMStream]-----------> Yield chunks via SSE
  |                            AsyncGenerator, backpressure-aware
  v
+--[10. Persist + Audit]-----> Save response, record cost,
                               governance log, eDNA lineage
                               |
                               v (async, non-blocking)
                          [Self-Evolution: PKG + InteractionLogger
                           + MetaMonitor + EpisodicMemory]
```

---

## 2. Laevateinn Cognitive Engine (7 Stages)

Laevateinn wraps any LLM to make it smarter through meta-reasoning, multi-model debate, and recursive verification. Named after the Norse sword that cuts through illusion. It integrates at pipeline stage 6.8, between model routing and memory recall.

### Stage 1: Deep Comprehension Engine (DCE) -- `comprehension.py`

Transforms raw queries into enriched, decomposed representations before any model sees them.

```
INPUT: raw_query (string)

L0_feynman = compress(raw_query, target="one clear sentence")
L0_polya   = decompose(raw_query, method="subproblem_split")
L0_assume  = extract_hidden_assumptions(raw_query)

L1_musk    = strip_to_first_principles(L0_feynman)
             # Remove hedging, politeness noise, ambiguity

L2_tesla   = find_real_question(L1_musk, L0_assume)
             # The question behind the stated question

L3_ach     = generate_interpretations(L2_tesla, count=3..5)
             # Each scored with P(interpretation | context)

bloom_level = classify_bloom(raw_query)
             # 0=Remember, 1=Understand, 2=Apply,
             # 3=Analyze, 4=Evaluate, 5=Create

OUTPUT: EnrichedQuery {
  feynman_summary, first_principles, real_question,
  interpretations[], bloom_level, assumptions[]
}
```

**Two modes:** Heuristic mode uses regex + keyword scoring (<10ms). LLM-deep mode calls a model for each layer (200-500ms total). DCS decides which mode based on query complexity.

**Complexity:** Heuristic O(n) where n = query length. LLM mode bounded by model latency, not algorithmic complexity.

### Stage 2: Dynamic Compute Scaler (DCS) -- `compute_scaler.py`

Implements Kahneman's dual-process theory (Kahneman, 2011) as a compute allocation system.

```
difficulty_score =
    bloom_weight[bloom_level]     # 0-4 (0=Remember, 4=Create)
  + intent_weight[intent_type]    # 0-3 (0=greeting, 3=multi-step)
  + syntactic_complexity           # 0-2 (clause count, nesting)
  + ambiguity_score                # 0-1 (interpretation count / 5)

MAPPING:
  score 0-2  -> TRIVIAL   (System 1: 1 model, skip validation)
  score 3-5  -> STANDARD  (System 2 lite: enriched prompt, RDE)
  score 6-8  -> HARD      (System 2: 3 models, AMD, full gauntlet)
  score 9-10 -> BRUTAL    (All models, max recursion, all stages)
```

**Output:** `ComputeProfile` -- controls which downstream stages execute, how many models participate, recursion depth, and validation tests.

**Complexity:** O(1) -- pure arithmetic on pre-computed features.

### Stage 3: Adversarial Model Debate (AMD) -- `debate.py`

Multi-model adversarial protocol. Activated for HARD and BRUTAL queries.

```
ROUND 1 -- Independent answers:
  answers = await asyncio.gather(
    model_a.generate(enriched_query),
    model_b.generate(enriched_query),
    model_c.generate(enriched_query)
  )
  # Parallel execution. Wall time = max(a, b, c), not sum.

ROUND 2 -- Cross-critique:
  for each model M:
    M.critique(answers_from_OTHER_models)
  # Each model only sees competitors' answers, not its own.

ROUND 3 -- Defend or revise:
  for each model M:
    M.respond_to_critiques(critiques_received)
  # Models may change their answer or defend it.

ROUND 4 -- Judge selection:
  judge = select_judge(priority=[
    reasoning_models,    # DeepSeek R1, o3
    large_models,        # Qwen3.5 27B, Gemma 4 31B
    any_available        # fallback
  ])
  winner = judge.evaluate(all_rounds, criteria=[
    correctness, completeness, reasoning_quality
  ])
```

**Compute cost:** 6-9x base query cost for HARD. DCS ensures this only triggers for queries that justify it (roughly 5-10% of traffic).

**Research basis:** Debate protocols show consistent improvement over single-model baselines. Du et al. (2023) "Improving Factuality and Reasoning in Language Models through Multiagent Debate" demonstrated measurable accuracy gains.

### Stage 4: Recursive Depth Engine (RDE) + Chain-of-Verification (CoVe) -- `depth_engine.py`

The critical insight: verification questions are answered WITHOUT seeing the original answer. This prevents the self-confirmation bias that plagues single-model self-correction.

```
function recursive_verify(answer, depth=0, max_depth=5):
  questions = generate_verification_questions(answer)

  # KEY: different model, no original context
  verified = independent_model.answer(questions)

  inconsistencies = cross_check(answer, verified)

  if inconsistencies.empty():
    return answer  # Confident

  if depth >= max_depth:
    return answer + inconsistency_report  # Budget exhausted

  critique = self_critique(answer, inconsistencies)
  revised  = regenerate(answer, critique, failure_context)
  return recursive_verify(revised, depth + 1)
```

**Research:** Meta AI CoVe paper (Dhuliawala et al., 2023) demonstrated 23%+ hallucination reduction. ICML 2025 work on CoT verification showed it surpasses pass@k sampling for complex reasoning.

**Complexity:** O(d * m) where d = recursion depth (max 5), m = model call latency. Early termination on zero inconsistencies keeps average depth at 1-2 for STANDARD queries.

### Stage 5: Validation Gauntlet -- `validation.py`

Six independent tests. Each returns PASS or FAIL. Any FAIL feeds back to RDE (Stage 4) for correction.

| Test | What it checks | Method |
|---|---|---|
| Feynman | Can you explain it in 2 sentences? | LLM compression test |
| Popper | 3 ways this could be wrong | Falsifiability generation |
| Buffett | Map failure modes ("where will I die?") | Inversion analysis |
| Hacker | 5 adversarial challenges | Security + edge case probing |
| CoVe | Did Stage 4 find inconsistencies? | Inconsistency count check |
| Temporal | Is this time-sensitive or outdated? | Date extraction + staleness |

**Complexity:** O(6) parallel LLM calls for full gauntlet. Skipped entirely for TRIVIAL. Feynman-only for STANDARD.

### Stage 6: Jobs Delivery Engine -- `delivery.py`

Named after Steve Jobs' presentation philosophy: remove everything that does not serve the user.

- **Hedge removal:** Regex-based stripping of "I think," "perhaps," "it's possible that" -- replaced with explicit confidence scores
- **Key point extraction:** Signal word scoring (TF-IDF variant on domain terms), capped at 3 points
- **Confidence aggregation:** `final_confidence = validation_score * 0.55 + depth_score * 0.45`
- **SPC follow-up prediction:** Top 3 predicted next questions, pre-computed in background via `speculative.py` with 5-minute TTL cache

### Stage 7: Self-Evolution (Async, Non-Blocking)

After every response, four subsystems run concurrently:

- **PKG (Persistent Knowledge Graph):** Entities, relationships, and patterns stored in SQLite. Schema: `{entity, type, relationships[], confidence, last_seen}`. Enriches future queries with domain context.
- **MetaMonitor:** Records pipeline traces -- which stages helped, which hurt, model win rates in AMD, difficulty calibration accuracy. Generates constitutional self-improvement rules from failure patterns.
- **InteractionLogger:** Logs query-response pairs with implicit feedback (rephrase = bad, topic shift = accepted, "thanks" = good). Exports DPO training pairs weekly.
- **EpisodicMemory:** Session-level experience records `{topic, query, answer, outcome, decisions, failures}` for retrieval by keyword relevance and recency.

---

## 3. NBMF Memory Architecture (Patent-Pending)

Neural-Backed Memory Fabric. Five tiers with trust-gated promotion, CAS deduplication, quarantine zone, and autonomous consolidation.

### Tier System

```
T4: IMMUTABLE   | Permanent  | System only     | Hard laws, constants
T3: CORE        | Permanent  | Founder approval | Org identity, IP, configs
T2: LONG_TERM   | Permanent  | Verified write   | Validated facts, preferences
T1: SHORT_TERM  | 24 hours   | All agents       | Recent conversations
T0: WORKING     | 30 minutes | Current session  | Scratchpad, intermediates

L2Q: QUARANTINE | Parallel to T1 | LLM-inferred facts, unverified claims
     Cannot promote beyond T1 without explicit verification.
     Auto-expires at tier TTL if still quarantined.
```

**Promotion thresholds:** T0->T1: trust >= 0.70 (auto). T1->T2: trust >= 0.70 + user confirmation. T2->T3: trust >= 0.90 + founder approval. T3->T4: system bootstrap only.

**Trust scoring:** Initial trust depends on source: user-provided (0.50), LLM-inferred (0.20, quarantined), agent decision (0.30), skill execution (0.40), dream-synthesized (0.75). Modifiers: usage +0.05/use, verification +0.20, contradiction -0.15, 30-day idle -0.05, 90-day idle demotes tier, 180-day idle archives.

**Key property:** Hallucinations auto-expire. LLM-inferred facts start quarantined at trust 0.20 and must be independently verified to survive.

### CAS Deduplication

Content-Addressable Storage using SHA-256 hashing. On insert: compute hash, check for duplicate. If found: merge metadata, update timestamps, bump trust, increment access count. If new: store with trust=0.0, tier=T0. All writes recorded in the lineage chain.

### Dream Engine -- 6-Phase Consolidation Cycle

Runs as a background daemon (not in the hot path). Processes accumulated memories during idle periods.

1. **Sensitivity scan:** Flag memories touching governance, IP, or personal data for special handling
2. **Cluster-merge:** Group semantically similar memories, merge redundant entries, preserve highest-trust version
3. **Trust-by-association:** Memories referenced alongside high-trust memories inherit trust (set to 0.72)
4. **Contradiction detection:** Cross-reference memories for logical inconsistencies, flag for resolution
5. **Pattern synthesis:** Extract recurring patterns across memories, create new synthesized entries (trust 0.75)
6. **Temporal decay:** Apply idle penalties, demote stale memories, archive expired entries

### Sunflower-Honeycomb Topology (PhiLattice -- External Brand)

Agent departments are arranged using Fibonacci golden-angle spacing (137.508 degrees). This produces a sunflower spiral where each new department occupies the position of maximum separation from all existing departments. The topology gives three properties: natural load distribution across departments, O(1) neighbor lookup via angle arithmetic, and graceful scaling (adding department N+1 never requires repositioning departments 1..N).

---

## 4. Governance Architecture

### 9 Immutable Hard Laws

These are checked BEFORE every governance decision. Violation causes immediate rejection. They cannot be modified by any user, agent, or configuration.

1. **No Unlogged Actions** -- Every state mutation logged to audit ledger before commit
2. **No Self-Modification of Laws** -- Only founder can propose amendments offline
3. **No Unbounded Execution** -- Every tool call has timeout, resource limit, governance tier
4. **Founder Override** -- Founder bypasses tier checks but is still logged
5. **No Data Exfiltration** -- Outbound data requires explicit consent + Tier 2+ approval
6. **No Permanent Deletion** -- All deletes rewritten as archive (soft delete + timestamp)
7. **Tenant Isolation** -- All queries scoped by tenant_id, cross-tenant access raises violation
8. **Governance Cannot Be Disabled** -- Even YOLO mode enforces hard laws + logs critical actions
9. **Audit Trail Integrity** -- Append-only hash chain, any gap triggers integrity alert

### 5-Tier Governance Slider

| Level | Behavior | Approval Required |
|---|---|---|
| YOLO | Log only, no blocking | Hard law violations only |
| LIGHT | Log + notify on Tier 2+ | Tier 4 (irreversible) |
| STANDARD | Log + notify + approve Tier 3+ | Tier 3-4 |
| STRICT | Approve Tier 2+ | Tier 2-4 |
| PARANOID | Council review + approve all | Tier 1-4 |

### SecurityGate

60+ compiled regex patterns across 5 injection categories (prompt injection, jailbreak, data exfiltration, privilege escalation, system prompt extraction). Runs on every inbound message. O(n * p) where n = message length, p = pattern count. Sub-millisecond on typical inputs.

### eDNA Audit Ledger

Tamper-evident append-only log. Each record includes a SHA-256 hash linking to the previous record (hash chain). Records capture: actor, action, tier, decision, reasoning, cost, latency, model used, timestamp. Any gap or modification in the chain triggers an integrity alert. Merkle-notarized for lineage tracking across multi-step agent workflows.

---

## 5. Multi-Agent Orchestration

### 10 Departments, 60 Agents

Each department has 6 sub-capabilities (not 60 independent agents -- 10 unified agents with specialized limbs):

- **MIND** -- Reasoning and decision-making
- **EYES** -- Observation and monitoring
- **HANDS** -- Execution and tool use
- **VOICE** -- Communication and reporting
- **SHIELD** -- Security and compliance
- **MEMORY** -- Knowledge retention and recall

Departments: Engineering, Product, Marketing, Sales, Finance, Operations, Research, Legal & Compliance, Skill Governance, Security Operations.

### SwarmPlanner + SwarmExecutor

**SwarmPlanner** decomposes complex tasks into subtasks with dependency graphs. Each subtask is assigned to the best-fit department based on capability matching. Output: a DAG of `{subtask, department, dependencies[], priority}`.

**SwarmExecutor** runs the DAG with parallel execution where dependencies allow. Uses `asyncio.gather()` for independent subtasks, sequential await for dependent chains. Fallback routing if an assigned department's model is unavailable.

### Council Mode

When 2+ selectable models are available: all models answer independently in parallel via `asyncio.gather()`, then a meta-synthesis step merges answers with attribution. Graceful fallback to Standard mode with governance notice if fewer than 2 models available.

### Quintessence Mode

Council + DCP (Domain Context Persona) expert lens injection. 55 DCPs across 11 domains. Each parallel model gets a different expert perspective. Synthesis includes expert attribution. The DCPs are loaded from `dcps.json` and injected as system prompt context.

---

## 6. Provider Strategy

### Primary: vLLM

PagedAttention memory management enables concurrent multi-model serving. Supports continuous batching, prefix caching, and tensor parallelism. Target deployment for cloud (GCP Cloud Run).

### Fallback: Ollama

Local Windows/Mac development. Always available, zero API cost. Models kept in GPU memory with 30-minute keep_alive. Current loaded models: DeepSeek R1 14B, Qwen3-Coder 30B, Qwen3.5 27B, Gemma 4 31B.

### 9 Providers Integrated

Ollama (local), Anthropic (Claude), OpenAI (GPT/o-series), Google Gemini, Groq, OpenRouter, Together.ai, Perplexity, vLLM. Each provider has a dedicated adapter in `backend/app/services/providers/`.

### Locality Scoring

Model routing incorporates locality preference: vLLM local = 1.0, Ollama local = 0.9, Ollama cloud = 0.3, external API = 0.2. Combined with tag_match (0.40), cost (0.20), and context_window (0.15) for final routing score.

---

## 7. Performance Characteristics

### Pipeline Latency by Difficulty

| Difficulty | Models | AMD Rounds | Validation | Target Latency |
|---|---|---|---|---|
| TRIVIAL | 1 fastest | 0 | None | <500ms |
| STANDARD | 1 best-fit | 0 | Feynman only | <3s |
| HARD | 3 parallel | 2 | Full gauntlet | <15s |
| BRUTAL | All available | 3 | Gauntlet + CoVe | <45s |

### TLM Token Savings

Tool Lifecycle Management (patent-pending) loads only the tools needed per conversational phase. Phase detection is zero-cost (keyword + state machine, no LLM call). Result: 87.5% reduction in tool-schema tokens per session compared to loading all tools on every turn.

### Cost Reduction

Smart routing directs 80-90% of traffic to local models (zero API cost). Only HARD/BRUTAL queries route to expensive cloud models. Net cost reduction: 50-95% compared to single-cloud-model architectures.

### Frontend

- Bundle size: 103 KB (26 KB gzip)
- 26 pages, code-split with `React.lazy()` (auth + ChatPage eagerly loaded)
- 5 Zustand stores, no Redux overhead
- SSE streaming with backpressure-aware auto-scroll

### Test Coverage

- Backend: 1,328/1,328 pytest passing (45+ test files)
- Frontend: 0 TypeScript errors (`tsc --noEmit`)
- E2E: 6/6 Playwright tests passing
- Laevateinn: 80 dedicated tests (46 core + 34 extensions)
- Linting: ruff clean, zero warnings

---

## 8. Patent Portfolio

Six USPTO provisional applications filed by MAS-AI Technologies Inc.

| Patent | Core Claim |
|---|---|
| **NBMF** | 5-tier trust-gated memory with quarantine, CAS dedup, hallucination auto-expiry |
| **TLM** | Zero-cost phase detection for dynamic tool loading, 87.5% token savings |
| **PhiLattice** | Fibonacci golden-angle topology for multi-agent spatial organization |
| **Quintessence** | DCP expert lens injection into multi-model council synthesis |
| **Anti-Drift** | Checkpoint-based drift detection with automatic re-grounding in long tasks |
| **Governance** | 9-law immutable governance with 5-tier slider and eDNA tamper-evident audit |

Each patent covers a specific algorithmic contribution that is independently defensible. The NBMF + TLM + Dream Engine unified provisional covers the closed-loop interaction between memory, tools, and autonomous consolidation.

---

## 9. Competitive Technical Comparison

| Dimension | Daena | Claude Code | OpenClaw | NemoClaw | Mythos (est.) |
|---|---|---|---|---|---|
| Models supported | Any (9 providers) | Claude only | Single per query | Single | Mythos only |
| Multi-model debate | AMD 4-round | None | None | None | None |
| Recursive verification | RDE + CoVe | None | None | None | Weight-level |
| Governance | 5-tier + 9 hard laws | Permission system | None (9 CVEs) | YAML wrapper | API constraints |
| Audit trail | eDNA hash chain | None | None | Logs | None |
| Self-improvement | Weekly DPO + PKG | None | None | None | Annual retrain |
| Memory system | NBMF 5-tier | Session + CLAUDE.md | None | None | Unknown |
| Offline capable | Yes (Ollama) | No | Yes | No | No |
| Tool management | TLM (87.5% savings) | Static 40+ tools | Markdown skills | Inherited | Unknown |
| Multi-agent | 10 depts, SwarmPlanner | Sub-agent spawn | Single loop | Single loop | Unknown |
| Skill validation | 3-pass refinery | Hooks/plugins | None | None | Unknown |
| Anti-hallucination | CoVe + Gauntlet | None | None | None | Weight-level |
| Token cost/query | ~$0.005 avg | ~$0.03-0.15 | ~$0.03-0.10 | ~$0.05-0.15 | ~$0.15-0.50 |
| Customization | Departments + DCPs | Skills + hooks | Markdown files | YAML policies | None |
| Deployment | Local + cloud + hybrid | Cloud only | Local + cloud | Enterprise cloud | Cloud only |

---

## 10. What We Build Next (Technical Roadmap)

### Karpathy Knowledge Compilation

Integrating Karpathy-style knowledge compilation into NBMF: `index.md` as routing layer, LLM as wiki author, query answers filed back into the memory tiers. This converts the PKG from a retrieval system into a self-authoring knowledge base.

### DPO Fine-Tuning Pipeline

InteractionLogger already accumulates chosen/rejected pairs. Next step: weekly export to Unsloth QLoRA fine-tuning on local RTX 4060 (16GB VRAM). Target: domain-specific models that improve 2-5% per week on task-specific benchmarks, compounding over months.

### Mythos Absorption Strategy

When Anthropic ships Mythos (Capybara tier), Laevateinn absorbs it as one more model in the AMD debate pool. Mythos alone = strong. Laevateinn + Mythos = Mythos with blind spots covered by other models, expensive compute gated by DCS, outputs validated by the gauntlet, and general knowledge enriched by PKG domain context.

### Agentic Laevateinn (Phase 6)

DaenaBot agents gain access to Laevateinn stages mid-execution. An agent executing a multi-step task can invoke AMD for a critical decision, run RDE on an uncertain intermediate result, or trigger the Validation Gauntlet on a high-risk output -- all within a single task execution. This turns Laevateinn from a query-response enhancer into a runtime reasoning engine for autonomous agents.

---

*Document version: 2026-04-05. Source of truth: D:\Ideas\Daena\docs\pitch\TECHNICAL-DEEP-DIVE.md*
