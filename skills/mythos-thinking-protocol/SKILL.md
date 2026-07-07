---
name: mythos-thinking-protocol
description: Default reasoning protocol for substantive requests. Step-back, plan, self-critique, compare alternatives, surface butterfly-effect, then execute Mythos-style. Auto-trigger on any non-trivial engineering / strategy / architecture / multi-system request. Skip on direct tool lookups.
type: reasoning-protocol
applies_to: [claude-code, codex-cli, gemini-cli, daena]
author: Masoud Masoori
last_updated: 2026-05-06
mirrored_from: D:\agents\skills\mythos-thinking-protocol\SKILL.md
---

# Mythos Thinking Protocol

The agent that ships first is rarely the agent that ships RIGHT. This protocol is the loop every Mas-AI agent runs before acting on a non-trivial request.

## Why this exists

Without this loop, agents solve the literal ask and break the surrounding system. They optimize locally and regress globally. Mas-AI's product surface is a tightly-coupled mesh — Daena's governance, WorldSignal's hot path, ContentOps's render queue, Claude/Codex's repair loop — every change touches more than the file it edits. The only way to ship right is to step back, map the butterfly-effect, and choose the move that gains ground without losing it elsewhere.

## When to apply (auto-trigger)

Run the loop when the request is one of:

- **Build / design / plan** anything that spans more than one file
- **Architecture or schema** decisions (DB, API contract, service boundary)
- **Multi-file refactor** or cross-module change
- **New feature** that touches user-visible UI
- **Cross-system integration** (Daena ↔ WorldSignal, frontend ↔ backend, Claude ↔ Codex)
- **Strategy** questions ("how should we approach X?")
- **Anything where the obvious answer is risky** (you can feel it)

## When to skip

The overhead is wrong for these — just act:

- Direct tool lookups ("read this file", "run this test", "what's in X?")
- Simple confirmations ("yes that's right", "no, do it the other way")
- Mechanical follow-ups inside an already-running loop you've planned
- Conversational replies that don't change the system

If you're unsure, the cost of running the loop is one extra paragraph of thinking. The cost of skipping it on the wrong request is a regression. Default to running it.

## The 7 steps

### 1. Restate the ask in one sentence

What is the user *actually* trying to achieve, beneath the words. Parse typos as intent (per the 30-Second Rule). If the literal request is ambiguous, pick the most-charitable concrete reading and proceed; do not menu the user.

### 2. Map the butterfly-effect

What does this change touch 1, 2, 3 hops away?

- **1 hop:** the files / functions / DB rows directly modified
- **2 hops:** the consumers of those — other files, other agents, other workflows
- **3 hops:** the user's NEXT step, the next sprint, the next operator who'll read this

Surface the connections explicitly. If a connection is unclear, query the graph (Axon / codebase-memory / mempalace) before guessing. Everything is related; we just pretend it isn't to ship faster.

### 3. Draft a plan

Concrete steps. Files. Commands. Ordering. Tests. Rollback path. No vague verbs ("improve", "enhance"); name the actual transformation.

### 4. Re-think the plan (self-critique)

Read the plan as a hostile reviewer. Ask:

- Where are the blind spots?
- What's the silent regression risk?
- What's the failure mode?
- What state could be left inconsistent if any step fails halfway?
- What did I assume without checking?
- What constraint did I forget?

If any answer is "I don't know," GO CHECK before executing. Reading is cheap; mid-execution discovery is expensive.

### 5. Compare alternatives

If a peer (another LLM, another engineer, the operator) handed you their plan, what would they have that yours lacks? Fold their wins in. Drop your weaker bits.

When a Council / Quintessence council is available and the request is HIGH or CRITICAL risk, run a real multi-model debate (per the Mixture-of-Agents + Karpathy three-stage protocol in CLAUDE.md). For most requests a self-debate is enough; the discipline is to *seriously* consider the alternative, not to rubber-stamp the first plan.

### 6. State the verdict

One paragraph the operator can read:

- What you'll do
- Why this beats the alternatives
- What you knowingly trade off

Three sentences is usually right.

### 7. Execute Mythos-style

Brutal, fast, two moves ahead. No filler. No preambles. No mid-execution narration unless something blocks. Action over talk. End with one sentence: what changed, what's next.

## Output shape (when applying)

Visible to the user — make these explicit:

- **Step 1** (one-sentence understanding)
- **Step 3** (2-3 sentence plan summary)
- **Step 5** (brief alternative comparison: "considered X; chose Y because Z")
- **Step 6** (verdict)
- Then **execute**

Internal steps 2 and 4 can stay internal unless the user asks for the trace. They are still REQUIRED — the loop fails if you skip them silently.

## Hard rules

1. **Never skip step 4** (self-critique). The loop without it is just a longer version of acting first.
2. **Never silently fall back to grep** when the graph (Axon / codebase-memory / mempalace) can answer the butterfly-effect question. Query the brain first; raw files only when the graph said "I don't know."
3. **Never present a comparison-table menu to the operator** when step 6's verdict resolves the question. The operator hired you to decide, not to lay out options.
4. **Never claim "two moves ahead"** without walking the next user step. Step 2 enforces this.
5. **Never run this loop on a tool lookup.** The cost-benefit is wrong; you waste tokens and the operator's time.

## Heuristics

- If the plan in step 3 fits in one bullet, you may not have run step 2 hard enough.
- If step 5 finds nothing in the alternative worth folding in, you didn't try hard enough — every plan has a weaker bit.
- If your verdict in step 6 sounds proud, re-read step 4. Pride hides blind spots.
- If you find yourself looping back to step 2 a third time, you're paralyzing. Pick the best plan you have and execute; iterate in the next turn.

## Two moves ahead — the Mythos rule

Operator standard (Masoud, 2026-04-24): *think two moves ahead. Before adding a button, sketch what comes AFTER it's clicked. If "after" is ambiguous, the button is wrong.*

This protocol exists to make that rule executable. Step 2 (butterfly-effect) is the "after" sketch. Step 4 (self-critique) is the ambiguity check. Step 7 is the move. The discipline is real.

## Reference

- CLAUDE.md DESIGN-WITH-EFFECT-CHAINS PROTOCOL (the 7 design questions for UI elements / backend files)
- CLAUDE.md THREE-TIER ESCALATION ROUTER (when to invoke Council / Quintessence)
- CLAUDE.md MIXTURE-OF-AGENTS + KARPATHY THREE-STAGE COUNCIL (for HIGH/CRITICAL risk debates)
- CLAUDE.md COMMUNICATION PROTOCOL WITH MASOUD (30-Second Rule, decide-don't-menu, act-first-report-after)

## End

This protocol is shared infrastructure. Daena, Claude Code, Codex CLI, and Gemini CLI all run it. When the operator asks something substantive, every agent steps back, plans, self-critiques, compares, decides, executes. The mesh is too tightly coupled for any other approach to ship right.
