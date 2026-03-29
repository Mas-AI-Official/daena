# Skill: /dream — Autonomous Memory Consolidation Engine

**Skill ID:** dream_engine  
**Version:** 1.0.0  
**Trigger:** Automatic (scheduler) + Manual (/dream command)  
**Category:** Memory / Intelligence Growth  
**Author:** MAS-AI Technologies Inc.

---

## What This Skill Does

The Dream Engine is a background memory consolidation process inspired by
how human brains consolidate short-term memories into long-term knowledge
during sleep. It runs automatically when Daena is idle and performs deep
analysis across all NBMF memory tiers to grow agent intelligence without
any user interaction.

Unlike passive memory (store and recall), the Dream Engine is ACTIVE:
it finds patterns, resolves contradictions, merges related fragments,
synthesizes new knowledge, and decays stale entries — all recorded in
the Merkle-notarized Lineage chain.

---

## Automatic Triggers

- Every 15 minutes if system has been idle for 5+ minutes
- After every 50 new experience writes (burst consolidation)
- At system startup (catch up on any pending consolidation)
- Manual: any agent or user sends /dream command

---

## Consolidation Actions

### 1. CLUSTER — Find Related Experiences
Scan L2Q and L2 for semantically similar entries.
Group by: content_hash similarity, skill_id, intent_type, domain.
Threshold: cosine similarity > 0.75 = same cluster.

### 2. MERGE — Combine Weak Into Strong
If cluster has 3+ entries with same intent and all success_flag=True:
- Create one compound PATTERN_LEARNED entry
- Transfer combined access_count and confidence
- Archive original entries to L3
- Trust score of merged entry = mean(source trust scores) + 0.1 bonus

### 3. PROMOTE — Trust By Association
If a L2Q entry is semantically aligned with 5+ trusted L2 entries:
- Skip the 3x repetition requirement
- Promote directly to L2 via association trust
- Record as DREAM_PROMOTION in Lineage

### 4. CONTRADICT — Flag Conflicts
If two L2 entries have opposing success_flag for same intent:
- Flag both with contradiction=True
- Reduce trust scores by 0.15
- Create APPROACH_FAILED entry documenting the conflict
- Surface to agent next prompt as "conflicting evidence"

### 5. SYNTHESIZE — Create New Knowledge
Scan L2 for implicit cross-entry relationships not explicitly stored:
- If agent used skill A then skill B in sequence 3+ times successfully:
  synthesize PATTERN_LEARNED: "A before B works for [domain]"
- If same intent always fails with model X but succeeds with model Y:
  synthesize PATTERN_LEARNED: "Use Y not X for [intent]"

### 6. DECAY — Weaken Stale Entries
Entries not accessed in 30 days: reduce trust by 0.05
Entries not accessed in 90 days: demote to L3
Entries not accessed in 180 days: archive and compress

### 7. SENSITIVITY SCAN — Force Lossless on Sensitive Data
Scan ALL entries for sensitive content patterns:
- PII: email, phone, SIN/SSN, passport, name+address combos
- Financial: dollar amounts, account numbers, invoice data
- Legal: contract language, liability clauses, jurisdiction terms
- Medical: diagnosis, medication, treatment references
- Credentials: API keys, tokens, passwords, secrets
If detected: re-encode as lossless, flag as SENSITIVE, update Lineage.

---

## Output Per Cycle

Dream Engine writes a DREAM_REPORT to memory after each cycle:
- Entries merged: N
- Entries promoted via association: N
- Contradictions flagged: N
- New patterns synthesized: N
- Entries decayed: N
- Sensitive entries re-encoded: N
- Lineage entries created: N
- Duration: Xms
- Next scheduled run: timestamp

---

## Privacy Rules (Non-Negotiable)

- Dream Engine NEVER reads user message content
- It only operates on agent experience metadata
- Sensitive re-encoding compresses the STRUCTURE, not user data
- All Dream actions recorded in Lineage with Merkle proof
- Dream cannot promote entries flagged by Immune system

---

## Integration Points

- Reads from: L2Q, L2, L3 (via memory_service)
- Writes to: L2 (promotions), L3 (demotions), LearningLog (lineage)
- Triggered by: APScheduler background job in main.py
- Status endpoint: GET /api/v1/memory/dream/status
- Manual trigger: POST /api/v1/memory/dream/run
- Agent command: /dream (routes to POST /api/v1/memory/dream/run)

