# MAS-AI ECOSYSTEM ARCHITECTURE SPECIFICATION
## Top-Level System Design & Refactor Mission

**Version:** 1.0  
**Date:** 2025-12-07  
**Status:** ACTIVE - Implementation Guide

---

## PART 0 — CONTEXT: TWO MINDS, ONE ECOSYSTEM

We are building **TWO SEPARATE AI MINDS**:

1. **DAENA** = INTERNAL AI VP for MAS-AI (the company)
2. **VIBEAGENT** = PUBLIC PLATFORM for users to build and run agents

They are **NOT** the same product.

They must **NOT** share raw customer data.

They **DO** share abstract methodologies and patterns via a controlled **Knowledge Exchange Layer**.

You must keep this separation crystal clear in the codebase.

---

## PART 1 — DAENA (INTERNAL COMPANY BRAIN)

### ROLE:

- Daena is the AI VP of MAS-AI.
- It governs our products, strategy, experiments, and (future) employees.
- It is **NEVER** directly exposed as a public product.

### ARCHITECTURE:

```
FOUNDER (ultimate override, human)
   ↓
DAENA (executive brain / VP)
   ↓
COUNCIL (governance/oversight layer, NOT a department)
   ↓
8 DEPARTMENTS (internal only, 6 agents each, hexagon logic)
   ↓
AGENTS (do internal work for MAS-AI)
```

### RULES:

- There are **EXACTLY 8 departments**.
- Each department has **EXACTLY 6 agents** (hexagonal structure).
- The Council is a separate governance layer, **not a 9th department**.

### COUNCIL PROTOCOL (PROACTIVE):

- Council is an infinite pool of advisor agents, each domain-specialized.
- For any audit or escalation:
  - Filter council by domain.
  - Select the **TOP 5 advisors + Daena**.
  - Run 2–3 debate rounds: arguments → cross-examination → synthesis.
- Decisions output:
  - **A.** Governance rule update (EDNA)
  - **B.** Operational correction (department workflow change)
  - **C.** Memory promotion (NBMF routing)
  - **D.** Drift correction or retraining
  - **E.** Founder alert (high-risk)
- Council runs:
  - Proactively (daily audits)
  - Reactively (on escalations, conflicts, drift, negative feedback)
- Every Council decision:
  - Requires Daena's signature.
  - May update EDNA (governance), NBMF (memory), and department behavior.
  - Never becomes public by default.

### MEMORY & GOVERNANCE:

- Daena uses a memory/governance system conceptually similar to NBMF + EDNA:
  - Private internal memory
  - Pattern-level knowledge
  - Global internal "company brain"
- These are for MAS-AI only, not for VibeAgent users.

---

## PART 2 — VIBEAGENT (PUBLIC PRODUCT PLATFORM)

### ROLE:

- VibeAgent is for **ALL USERS** to build and run their own agents.
- It should feel like:
  - a visual workflow builder (n8n-style),
  - an AI agent platform,
  - with optional Sunflower–Honeycomb logic under each account.

### ARCHITECTURE:

```
VIBEAGENT USER
   ↓
LOCAL VIBE "BRAIN"
   - LLM router (e.g. DeepSeek v3.2, GPT, others via API)
   - Tool/connector logic (email, APIs, scraping, etc.)
   - Local memory per user/account
   ↓
WORKFLOW / VISUAL BUILDER
   - Drag-and-drop interface
   - Visual workflows (nodes/edges)
   - Optionally uses sunflower–honeycomb sharing between that user's agents
```

### KEY RULES:

- Each user has their own local "mini-brain" independent of Daena.
- Users can choose:
  - **A)** Simple isolated agents (no shared memory)
  - **B)** Shared ecosystem under their account (agents aware of each other, shared experience)
- VibeAgent must **NOT** read Daena's internal company memory or logs.
- VibeAgent uses **METHODS INSPIRED BY** Daena, but not Daena's raw data.

---

## PART 3 — KNOWLEDGE EXCHANGE LAYER (DAENA ↔ VIBEAGENT)

We need a **SAFE BRIDGE** that shares wisdom, not raw data.

### RULES:

#### 1) NO RAW DATA SHARING:

- VibeAgent user inputs, documents, emails, PII, logs must **NOT** be copied into Daena's internal memory.
- Daena must never see raw, identifiable end-user content.

#### 2) ONLY ABSTRACT INSIGHTS FLOW:

**Allowed to send across:**
- High-level patterns (e.g., "this workflow pattern is efficient")
- Aggregated statistics
- Governance learnings ("avoid this type of risky workflow")
- Sanitized templates/blueprints with no private identifiers

**NOT allowed:**
- Any clear PII, secrets, or customer-specific raw content.

#### 3) EXCHANGE MODULE:

- Implement a clear service/module (e.g., `/services/knowledge_exchange.*`).
- Responsibilities:
  - Receive anonymized metrics & patterns from VibeAgent.
  - Aggregate and sanitize.
  - Provide abstract best practices/policies back to Daena.
  - Optionally publish anonymized "best practice workflows" from Daena to VibeAgent.

#### 4) ROUTING:

- VibeAgent uses its own LLM router (DeepSeek, GPT, etc.) directly for user queries.
- Daena uses LLMs for internal reasoning, not as a proxy for VibeAgent.
- The only cross-talk is via the Knowledge Exchange Layer with sanitized, abstract content.

#### 5) AGENT DRIFT PREVENTION:

- **INTERNAL AGENTS** (Daena departments) must not appear in VibeAgent's runtime.
- **PUBLIC AGENTS** (VibeAgent) must not appear inside Daena's department graph.
- Enforce in code:
  - separate namespaces/modules for internal vs public agents
  - separate registries and config
  - separate database or schema, if applicable.

---

## PART 4 — BACKEND & FRONTEND CLEANUP TASK

### YOU MUST:

#### 1) DISCOVER PROJECT STRUCTURE:

- Identify:
  - Daena backend (e.g., FastAPI or similar).
  - Daena internal UI (founder dashboard, internal tools).
  - VibeAgent frontend/backend (public).
- Ensure they are clearly separated:
  - e.g., `/daena-internal/*`
  - e.g., `/vibeagent-public/*`
- If previous tools (AntiGravity/Cursor) mixed them, **UNMIX THEM**.

#### 2) FIND DUPLICATE OR CONFLICTING FILES:

- Scan for files/modules that:
  - Have similar names but different locations.
  - Do the same job (e.g. multiple API clients doing similar things).
  - Implement the same UI more than once (duplicate dashboards/components).
- For each cluster of duplicates:
  - Decide on a **SINGLE, canonical implementation**.
  - Refactor code to use that canonical module.
  - Delete or deprecate older/incorrect copies.
- Do **NOT** leave two components that do identical work under different names.
- Examples to resolve:
  - Duplicate API client wrappers.
  - Multiple "dashboard" components.
  - Multiple workflow builders.
  - Old experimental directories vs final structure.

#### 3) ENSURE BACKEND ↔ FRONTEND ALIGNMENT:

- Inspect backend API routes and schemas.
- Inspect frontend API clients and hooks.
- Make sure:
  - every frontend call maps to a real backend endpoint,
  - field names and types match,
  - unused endpoints are either used or removed.
- If an endpoint has been duplicated or renamed, consolidate onto **ONE** official route.

#### 4) CLEAN DEAD CODE:

- Identify unused:
  - components,
  - routes,
  - agents,
  - utility functions,
  - old scripts from earlier experiments.
- If they are not part of the final Daena/VibeAgent design, remove or archive them in a clearly labeled `/legacy` or `/archive` folder.

#### 5) ENFORCE NAMING AND FOLDER CONVENTIONS:

- Keep Daena internal code grouped and clearly labelled.
- Keep VibeAgent public code grouped and clearly labelled.
- Do **NOT** put internal governance components inside VibeAgent folders.
- Use clear, semantic names that reflect:
  - `daena_*`
  - `vibe_*`
  - `exchange_*`
- Avoid generic names like "new_dashboard.tsx" or "temp_api.ts".

#### 6) UPDATE DOCUMENTATION:

- Add or update a top-level ARCHITECTURE / README:
  - Explain:
    - Daena = internal AI VP (8 departments × 6 agents, council).
    - VibeAgent = public platform.
    - Knowledge Exchange Layer = only bridge, abstract insights only.
  - Document where internal code lives and where public code lives.
  - Document how agents are registered and how they are separated.

---

## PART 5 — NON-NEGOTIABLE CONSTRAINTS

- Do **NOT** re-merge Daena and VibeAgent into one monolith.
- Do **NOT** create a 9th department.
- Do **NOT** change the 6-agents-per-department rule.
- Do **NOT** let internal Daena agents run in public VibeAgent workflows.
- Do **NOT** keep duplicate files that do the same job; consolidate properly.
- The final structure must be:
  - clean,
  - non-conflicting,
  - aligned with this architecture,
  - easy for a human developer to understand.

Your mission is to:
- reconcile the existing code with this design,
- refactor safely,
- remove duplication and confusion,
- and leave the project in a stable, consistent state.

---

## PART 6 — FULL-SYSTEM DEEP CLEAN & LEGACY PURGE

The MAS-AI codebase (Daena + VibeAgent) has been evolving for ~1 year.

There are **MANY** leftover, experimental, conflicted, or obsolete files.

### YOU MUST:

#### 1) SCAN THE ENTIRE REPOSITORY (BACKEND + FRONTEND + SCRIPTS)

- Include:
  - Daena internal backend
  - Daena internal frontend
  - VibeAgent backend/frontend
  - Shared libraries
  - Old experiment folders
  - Scripts (PowerShell, bash, Python utilities, etc.)
  - Configs (YAML, JSON, env examples)
  - Docs and markdown files related to old flows

#### 2) FIND ALL FORMS OF DUPLICATION

Not just similar structure, but **ANY** of:
- Multiple files that implement the same feature under different names.
- Components that visually do the same UI with different props.
- API clients that wrap the same endpoints differently.
- Utility functions repeated in different folders.
- "Backup" or "copy" versions of files (names like `*_old`, `*_backup`, `*_copy`, `*_v2`, `*_final`, `*_new`).
- Legacy folders like `/old`, `/tmp`, `/test2`, `/playground`, etc.

For each group of duplicates:
- Pick **ONE** canonical implementation.
- Refactor references to use that canonical version.
- Delete or quarantine the others into a `/legacy` or `/archive` folder clearly marked as non-production.
- Do **NOT** leave two active versions of the same logic.

#### 3) IDENTIFY DEAD / UNUSED CODE

- Detect files that:
  - Are never imported anywhere.
  - Are not referenced in any routing configuration.
  - Are not used in any rendered component tree.
  - Are not included in any launch script or build pipeline.
- Include:
  - Unused React components
  - Old hooks
  - Unused backend handlers / endpoints
  - Old schemas / types not referenced any more
  - Old agent definitions not wired to the current system
- For each unused file:
  - If clearly obsolete → remove or move to `/legacy`.
  - If uncertain but likely experimental → move to `/archive` with a short README note.

#### 4) CLEAN CONFIG & ENVIRONMENTS

- Find and consolidate:
  - Duplicate config files for the same purpose.
  - Deprecated environment variables.
  - Multiple `.env.example` or config templates that conflict.
- Ensure final config strategy:
  - One clear pattern for environment loading (local, dev, prod).
  - No hard-coded secrets or API keys in code.
  - Daena and VibeAgent have clearly separated config where necessary.

#### 5) STANDARDIZE ENTRYPOINTS AND SCRIPTS

- Identify all scripts used to launch or manage the system:
  - PowerShell, bash, npm/yarn/pnpm scripts, Python entrypoints, etc.
- Remove old or conflicting launch scripts that no longer match the architecture.
- Ensure:
  - There is a **SINGLE, clear way** to:
    - Launch Daena internal system
    - Launch VibeAgent public platform
  - Optional master script to launch everything together is well-documented.
- Update `package.json` / docs to reflect **ONLY** these official commands.

#### 6) ALIGN TYPES, INTERFACES, AND SCHEMAS

- Ensure all shared models (TypeScript types, Pydantic models, etc.) reflect the **CURRENT** architecture:
  - No references to old department counts, old agent numbers, or deprecated flows.
- Remove or update:
  - Types for removed features.
  - Interfaces that no longer align with the new Daena/VibeAgent split.
- Make sure type names and schema names clearly indicate:
  - internal vs public
  - daena vs vibe
  - governance vs operational.

#### 7) TEST FOR CONFLICTS

- After cleanup, ensure:
  - Project builds successfully.
  - Type-checking passes (e.g., `tsc`, `mypy` or equivalent if present).
  - Linting doesn't explode due to missing imports/paths.
- If tests exist:
  - Ensure test suite runs without referencing removed or legacy modules.
- If no tests exist:
  - At minimum, ensure:
    - Core entrypoints don't crash.
    - Core API routes for Daena and VibeAgent respond.
    - Frontend compiles and main pages render.

#### 8) PREPARE FOR GIT & CLOUD READINESS

- Ensure the cleaned repo is:
  - Consistent,
  - Free of dead/unused production code,
  - Free of temporary experimental clutter.
- Make sure:
  - `.gitignore` is up to date (no `node_modules`, build artifacts, or secrets tracked).
  - There are no large unused assets that hurt repo size without value.
- The goal:
  - A clean, understandable codebase ready to:
    - push to GitHub as the canonical version,
    - deploy to cloud,
    - and train future "brain" systems on its structure and conventions.

#### 9) DOCUMENT WHAT CHANGED

- Update or create a CHANGELOG / UPGRADE_NOTES explaining:
  - That a major cleanup and refactor occurred.
  - That Daena and VibeAgent are now clearly separated.
  - That legacy folders contain old experiments only, not production code.
- This is important so future tools and developers do **NOT** resurrect old patterns or files.

---

## PART 7 — PER-USER LIVE ECOSYSTEMS & VIBE MAIN BRAIN

VIBEAGENT IS NOT JUST A SET OF INDIVIDUAL AGENTS.

**EACH USER HAS THEIR OWN LIVING ECOSYSTEM.**

### 1) PER-USER ECOSYSTEM MODEL

- Every VibeAgent account has its **OWN** ecosystem of agents.
- For each agent under an account, the user can choose:
  - **A) ISOLATED mode:**
    - Agent has its own memory.
    - It does **NOT** share memory or experience with other agents, even under the same account.
  - **B) SHARED ECOSYSTEM mode:**
    - Agent becomes part of that user's live "sunflower–honeycomb" ecosystem.
    - Agents under the same account in SHARED mode:
      - are aware of each other's existence,
      - can share experience via NBMF-like mechanisms,
      - can coordinate via the local "mini-brain".
- Implement this as:
  - A per-agent flag or config: `ecosystem_mode = "isolated" | "shared"`
  - A per-account ecosystem graph:
    - nodes = agents
    - edges = relationships / communication paths

### 2) LOCAL NBMF + EDNA PER ACCOUNT

- Each account should conceptually have its own local NBMF/EDNA-like system:
  - **NBMF:**
    - L1: session/short-term memory (per agent)
    - L2: pattern memory for that user's ecosystem
    - L3: user-level global knowledge within that account **ONLY**
  - **EDNA:**
    - Local rules & preferences for that user's ecosystem:
      - style, risk tolerance, automation level, privacy preferences, allowed tools.
- Implementation expectations:
  - You don't need full NBMF/EDNA formalism, but:
    - You **MUST** separate:
      - short-lived context,
      - reusable patterns,
      - user-level configuration/knowledge.
    - You **MUST** allow users to:
      - inspect,
      - clear/reset,
      - or tune their ecosystem behavior via dashboard controls.

### 3) USER DASHBOARD FOR ECOSYSTEM CONTROL

- Each user **MUST** have a VibeAgent dashboard that lets them:
  - See all their agents.
  - See which agents are:
    - isolated vs
    - part of their shared ecosystem.
  - Wire agents together visually (connect flows, share outputs).
  - Split agents apart (remove from ecosystem, revert to isolated).
  - Audit:
    - recent actions,
    - workflow history,
    - memory or pattern summaries (at a high level, not raw logs).
- Ensure:
  - There is a clear visualization of the user's sunflower–honeycomb graph:
    - center = their "local brain"
    - surrounding cells = agents
    - edges = flows and relationships.

### 4) VIBE MAIN BRAIN (GLOBAL META-LAYER, NO RAW DATA)

- Above all user ecosystems, there is a global **VIBE MAIN BRAIN**.
- Vibe Main Brain **DOES NOT** store personal user data.
- It **ONLY** receives:
  - anonymized statistics,
  - aggregated patterns of successful workflows,
  - high-level performance metrics,
  - de-identified failure cases, and safety incidents.
- Responsibilities:
  - Learn which workflows work best in general.
  - Suggest better default blueprints / templates.
  - Improve routing strategies between LLMs.
  - Generate global best practices and safety policies.
- The Vibe Main Brain must interface with:
  - The Knowledge Exchange Layer → which passes abstract insights to Daena.
  - The template/blueprint system → which provides recommended agents/flows to future users.

### 5) EXPERIENCE SHARING WITHOUT PERSONAL DATA LEAKAGE

- For each account, you may:
  - Aggregate anonymized experience (e.g., "Workflow X with pattern Y had good success rate in scenario Z").
- Before sending anything to:
  - Vibe Main Brain
  - Knowledge Exchange Layer
  you **MUST**:
  - Strip all personal identifiers (names, emails, raw text, URLs, etc.).
  - Generalize data to patterns and stats only.
- The goal:
  - Use the **EXPERIENCE**, not the **PERSONAL DATA**.

### 6) DAENA ESCALATION FOR COMPLEX OR CRITICAL TASKS

- In some cases, a user's request or agent workflow may be:
  - Very complex,
  - Very high-stakes (e.g. financial, legal, strategic),
  - Or consistently failing using the local VibeAgent brain.
- In these cases, VibeAgent should support an **OPTIONAL** escalation to Daena, via the Knowledge Exchange Layer.
- Escalation flow:
  1. VibeAgent identifies a task as complex/high-risk or the user clicks "Ask Daena".
  2. VibeAgent composes a **SANITIZED** meta-request:
     - Describe the GOAL, constraints, and context in abstract terms.
     - **DO NOT** send raw confidential text if it can be avoided.
     - Where user consent is given, and only to the extent needed, include minimal necessary details.
  3. This meta-request goes to Daena through the Knowledge Exchange Layer.
  4. Daena uses:
     - her internal departments,
     - governance council,
     - NBMF/EDNA,
     to produce:
     - a high-quality plan/strategy,
     - key considerations and risks,
     - recommended workflows (not direct execution inside user data).
  5. VibeAgent:
     - receives Daena's guidance,
     - converts it into:
       - one or more recommended workflows,
       - agent configurations,
       - or manual guidance for the user.
- **IMPORTANT:**
  - Daena should **NOT** become a generic proxy for all user requests.
  - Daena is consulted only for complex/critical situations.
  - Any knowledge Daena gains must be abstracted; no user's raw data becomes part of MAS-AI's private brain.

### 7) NEVER FAIL THE USER (FALLBACKS)

- The architecture should aim to:
  - Use VibeAgent local brain and routers for normal cases.
  - Use Vibe Main Brain for improved templates and routing strategies.
  - Optionally escalate to Daena for high complexity, with privacy preserved.
- Fallback logic:
  - If a workflow fails repeatedly:
    - Suggest improvements from Vibe Main Brain.
    - If still unsatisfactory, offer Daena escalation (if the user consents).
- The objective: architect the system so that:
  - Users always have a path to "smarter help".
  - We maximize success rate without compromising data boundaries.

---

## PART 7 SUMMARY

- Every user has a personal VibeAgent ecosystem:
  - with agents that can be isolated or part of a shared sunflower–honeycomb under that account.
- Each account has its own NBMF/EDNA-style logic and auditability on the dashboard.
- A global Vibe Main Brain learns from anonymized experiences only.
- Knowledge Exchange Layer sends patterns to Daena, never raw user data.
- Daena can be optionally consulted for complex/high-risk tasks, to give best-in-class guidance.
- This design must be encoded in both backend and frontend structures, routing, and dashboards.

---

## SUMMARY OBJECTIVE

Do a **FULL-STACK, FULL-REPO** cleanup:

- No duplicate logic.
- No ghost or orphan files.
- No conflicting components doing the same thing.
- Clear separation of **DAENA** (internal brain) and **VIBEAGENT** (public platform).
- Clean, minimal, production-ready structure suitable for GitHub, cloud deployment, and future AI brain training.

---

**END OF SPECIFICATION**

