# Laevateinn Module Reference

## Core Pipeline (Stages 1-6)

### Stage 1: DeepComprehensionEngine (`comprehension.py`)
Transforms raw queries into enriched, decomposed, first-principles representations.

- **L0 Feynman Intake:** Compress to one clear sentence + Polya decompose + surface hidden assumptions
- **L1 Musk Noise Elimination:** Strip to first principles, remove hedging/politeness noise
- **L2 Tesla Resonance:** Find the REAL question behind the stated one
- **L3 ACH Multi-Interpretation:** Generate 3-5 scored interpretations with probability estimates
- **Bloom's Level Detection:** Classify query by cognitive taxonomy (Remember through Create)

Operates in heuristic mode (<10ms) or LLM-deep mode (200ms+).

### Stage 2: DynamicComputeScaler (`compute_scaler.py`)
Allocates compute proportional to difficulty. Implements Kahneman dual-process routing.

- **Difficulty estimation:** Bloom's level + intent type + syntactic complexity + ambiguity
- **System 1 (fast):** TRIVIAL queries, pattern-matching, instant response
- **System 2 (deep):** HARD/BRUTAL queries, full debate + verification
- Outputs a `ComputeProfile` that controls all downstream stages

### Stage 3: AdversarialModelDebate (`debate.py`)
Multi-model adversarial debate protocol.

- **Round 1:** All models answer independently (parallel via asyncio.gather)
- **Round 2:** Each model critiques the OTHER models' answers
- **Round 3:** Each model defends or revises based on critiques received
- **Round 4:** Judge model (strongest available) selects winner with reasoning
- Judge selection: reasoning models > large models > any available

### Stage 4: RecursiveDepthEngine (`depth_engine.py`)
Recursive self-correction with Chain-of-Verification (CoVe).

- Generate verification questions about the answer
- Answer them INDEPENDENTLY (different model, no original context)
- Cross-check for inconsistencies between original and verification
- Self-critique with inconsistency context
- Regenerate with full failure context
- Repeat until confident or budget exhausted

Research basis: ICML 2025 (self-correction with CoT verification) + Meta AI 2023 (CoVe reduces hallucination by 23%+).

### Stage 5: ValidationGauntlet (`validation.py`)
Six independent tests every non-trivial answer must survive.

1. **Feynman Test:** Can you explain it in 2 sentences to a junior?
2. **Popper Test:** 3 ways this could be wrong (falsifiability)
3. **Buffett Inversion:** Map failure modes ("tell me where I'm going to die")
4. **Hacker Test:** 5 adversarial challenges (security, edge cases)
5. **CoVe Verification:** Did Stage 4 find inconsistencies?
6. **Temporal Validity:** Is this answer time-sensitive/outdated?

FAIL feeds back to Stage 4 (recursive). PASS proceeds to delivery.

### Stage 6: JobsDeliveryEngine (`delivery.py`)
Formats the validated answer for delivery.

- Remove hedging language, replace with confidence scores
- Extract max 3 key points
- Predict 3 follow-up questions (Speculative Pre-computation)
- Format matched to query type (concise/standard/technical/creative)

---

## Intelligence Extensions

### CodeVerifier (`code_verifier.py`)
Executes code snippets mid-reasoning to verify claims.

- Extracts fenced code blocks (Python, Bash)
- Runs in sandboxed subprocess with timeout (10s default)
- No network access, no file writes outside temp
- Returns execution output, exit code, timing

### DeepThinkEngine (`deep_think.py`)
Extended thinking mode for single-model deep reasoning.

- Crafts meta-prompts forcing multi-path exploration
- Parses DeepSeek R1 native `<think>` tags
- Counts reasoning paths explored and backtracks
- Returns thinking trace + final answer + confidence

### ToolAugmentedReasoner (`tool_augmented.py`)
Calls tools DURING the RDE verification loop.

- Extract verifiable claims from answers
- Classify: code, factual, numerical, temporal
- Verify code claims by execution
- Verify numerical claims by safe math eval
- Verify factual/temporal claims via LLM grounding

---

## Self-Evolution (Stage 7)

### EpisodicMemory (`episodic_memory.py`)
Experience-based recall extending NBMF.

- Records episodes: session, topic, query, answer, outcome, decisions, patterns, failures, preferences
- Retrieval by keyword relevance, topic, recency
- Enriches queries with relevant past experience

### InteractionLogger (`interaction_logger.py`)
Accumulates training data for DPO fine-tuning.

- Logs every query-response pair with metadata
- Implicit feedback scoring (rephrase=bad, topic shift=accepted, "thanks"=good)
- Exports top interactions for supervised fine-tuning
- Exports DPO pairs (chosen vs rejected) for preference learning

### PersistentKnowledgeGraph (`knowledge_graph.py`)
Living knowledge graph of domain understanding.

- **Entities:** projects, components, concepts, patterns, failures
- **Relationships:** depends_on, extends, causes, fixes, related_to
- **Patterns:** code patterns, failure patterns, preferences, workflows
- Query enrichment: adds domain context before any model sees the query
- Interaction ingestion: learns from every Q&A pair

### MetaMonitor (`meta_monitor.py`)
Laevateinn watching Laevateinn.

- Records pipeline runs, model debates, difficulty predictions
- Analyzes stage performance (improvement rate, skip rate, latency)
- Tracks model win rates in AMD debates
- Measures difficulty calibration accuracy
- Generates constitutional self-improvement rules

### SpeculativePrecomputer (`speculative.py`)
Pre-computes predicted follow-up answers in the background.

- Predicts 3 most likely follow-ups (from PKG or heuristic)
- Launches background asyncio tasks to compute answers
- In-memory cache with TTL (5 min) + LRU eviction
- Cache hit = near-instant response for predicted queries
