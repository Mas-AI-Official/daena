# Daena ↔ VibeAgent Architecture Separation

## CRITICAL: This is a Non-Negotiable Architecture Constraint

**DO NOT MERGE DAENA AND VIBEAGENT. EVER.**

---

## High-Level Vision

We are splitting the system into **TWO SEPARATE MINDS**:

1. **DAENA** = Internal AI VP for MAS-AI (the company)
2. **VIBEAGENT** = Public product platform for users

They are **NOT** the same thing. They must **NEVER** share raw customer data.

---

## Daena - Internal Company Brain

### Role
- Daena is the AI VP of MAS-AI
- Governs products, strategy, experiments, documentation, and (future) employees
- **NEVER** exposed directly as a public product

### Architecture
- **8 departments total** (exactly eight)
- Each department has **exactly 6 agents** (hexagonal structure)
- **Council** is a separate governance layer (NOT a department)

### Structure
```
FOUNDER (human, ultimate override)
   ↓
DAENA (executive brain / VP)
   ↓
COUNCIL (governance layer, NOT a department)
   ↓
8 DEPARTMENTS (internal only, 6 agents each)
   ↓
INTERNAL TASKS (product decisions, strategy, experiments, etc.)
```

### Council
- Infinite pool of advisor agents specialized by domain
- For any decision/audit: select TOP 5 relevant advisors + Daena
- Produces: governance rule changes, operational corrections, memory promotions, drift alerts
- **Proactive governance**: Daily audits plus reactive escalation
- All decisions signed by Daena, override only by Founder

### Memory & Governance
- Uses NBMF-style memory and EDNA-style governance
- **Internal memory and logs MUST NEVER be exposed to public VibeAgent users**
- Daena's role is long-term, internal: learns from MAS-AI, not from random external user flows

---

## VibeAgent - Public Product

### Role
- Platform for **ALL PEOPLE IN THE WORLD** to create, run, and manage their own agents
- Mix of:
  - Visual workflow builder (n8n-style)
  - Agent playground (CrewAI-like)
  - Sunflower-Honeycomb methodology underneath

### Architecture
```
VIBEAGENT USER
   ↓
LOCAL VIBE "BRAIN"
   - LLM router (DeepSeek 3.2, GPT, others via API)
   - Tool/connector logic (email, web, APIs, etc.)
   - Local memory for that user's agents ONLY
   ↓
WORKFLOW / VISUAL BUILDER
   - Drag-and-drop flows
   - Sunflower-honeycomb optional architecture
   - Agents can be isolated or part of shared ecosystem
```

### Key Properties
- Each user has their own "mini-brain" for their VibeAgents
- Agents can:
  - **A)** Stay isolated (no sharing)
  - **B)** Join sunflower-honeycomb ecosystem under that user's account
- **MUST NOT** access Daena's internal company data
- Uses our methodologies and patterns, but **NOT** our confidential content

---

## Daena ↔ VibeAgent Knowledge Exchange Protocol

### RULES

#### 1. NO RAW DATA SHARING
- VibeAgent user data (prompts, emails, documents, PII, logs) **MUST NOT** be stored in Daena's internal memory
- Daena **must never see** raw user customer content from VibeAgent

#### 2. ONLY ABSTRACT INSIGHTS FLOW
**Allowed to transfer:**
- High-level patterns
- Anonymized statistics
- Governance improvements (e.g., "avoid this workflow pattern", "this flow is efficient")
- Workflow templates or blueprints with **NO** private identifiers

**Blocked:**
- Direct personal data
- Company-specific secrets
- User-specific content
- PII (emails, names, addresses, SSNs, etc.)

#### 3. EXCHANGE LAYER
- Implemented in: `/backend/services/knowledge_exchange.py`
- This layer:
  - Receives anonymized feedback/metrics from VibeAgent
  - Aggregates and sanitizes
  - Sends only patterns/methodologies to Daena ("lessons learned")
  - Optionally sends to VibeAgent new "best practice" workflows learned from Daena

#### 4. DAENA AS GOVERNOR, NOT SERVANT
- Daena is **NOT** a tool that VibeAgent calls for every user request
- Instead:
  - Daena governs product evolution, safety policies, and methodology updates
  - VibeAgent's router handles per-user LLM calls (DeepSeek, GPT, etc.) independently

#### 5. AGENT DRIFT PREVENTION
- Agents created for MAS-AI internal work (Daena's departments) **MUST NEVER** be repurposed as VibeAgent public agents
- Agents created by VibeAgent users **MUST NEVER** appear inside Daena's internal department graph
- Enforced via:
  - Strict namespace separation: `daena_internal_*`, `vibeagent_public_*`, `council_governance_*`
  - Separate config files, separate registries, separate memory stores
  - ABAC / role boundaries:
    - `INTERNAL_AGENT` can only act under Daena workflows
    - `PUBLIC_AGENT` can only act under VibeAgent workflows

#### 6. ROUTING
- **VibeAgent**: Uses local LLM router and DeepSeek 3.2 and/or other APIs to process user tasks
- **Daena**: Can use LLM APIs but only for internal MAS-AI decision-making
- **DO NOT** let VibeAgent user calls go "through" Daena except via the sanitized Knowledge Exchange Layer

---

## Implementation Details

### Namespace Separation

**Agent IDs are namespaced:**
- `daena_internal_*` - Daena internal agents (8 departments, 6 agents each)
- `vibeagent_public_*` - VibeAgent user agents
- `council_governance_*` - Council governance agents

**Enforcement:**
- `AgentNamespaceConfig.validate_namespace()` - Validates agent ID matches namespace
- `AgentNamespaceConfig.enforce_namespace_separation()` - Prevents agent drift
- `SunflowerRegistry.register_agent()` - Requires namespace parameter

### Knowledge Exchange API

**Endpoints:**
- `POST /api/v1/knowledge-exchange/from-vibeagent` - Receive sanitized data from VibeAgent
- `POST /api/v1/knowledge-exchange/to-vibeagent` - Send methodology to VibeAgent
- `GET /api/v1/knowledge-exchange/patterns` - Get patterns for Daena (requires auth)
- `GET /api/v1/knowledge-exchange/methodologies` - Get methodologies for VibeAgent (public)
- `GET /api/v1/knowledge-exchange/history` - Get exchange history (audit)

**Sanitization:**
- Removes PII (emails, SSNs, phone numbers)
- Removes user-specific content
- Removes internal identifiers
- Keeps only patterns, metrics, and methodologies

---

## Non-Negotiable Constraints

- ✅ **8 departments only** for Daena. No more, no less.
- ✅ **6 agents per department** (hexagonal structure)
- ✅ **Council is a separate governance layer**, NOT a department
- ✅ **Daena is not a public tool endpoint**
- ✅ **VibeAgent must function even if Daena is offline** (local brain + LLM routers)
- ✅ **The two systems communicate ONLY via controlled, sanitized, explicit interface**

---

## Code Organization

### Daena Internal
- `/backend/routes/daena*.py` - Daena internal routes
- `/backend/routes/departments.py` - Department management (internal only)
- `/backend/routes/council_*.py` - Council governance (internal only)
- `/backend/services/council_governance_service.py` - Internal governance
- `/backend/config/council_config.py` - Internal structure config

### VibeAgent Public
- `/backend/routes/vibe.py` - VibeAgent API endpoints
- `/backend/routes/user_mesh.py` - User mesh (PUBLIC namespace)
- `/backend/routes/sunflower_api.py` - Sunflower coordinates (public)

### Knowledge Exchange
- `/backend/services/knowledge_exchange.py` - Exchange layer
- `/backend/routes/knowledge_exchange.py` - Exchange API routes

### Namespace Enforcement
- `/backend/config/agent_namespace.py` - Namespace configuration
- Updated `sunflower_registry.py` - Enforces namespace separation

---

## Future Development Rules

1. **NEVER** import Daena internal types into VibeAgent runtime
2. **NEVER** expose Daena internal memory to VibeAgent users
3. **ALWAYS** use namespace prefixes for agent IDs
4. **ALWAYS** sanitize data before exchange
5. **ALWAYS** verify namespace separation in tests

---

## Documentation

- This file: Architecture separation rules
- Code comments: Explain namespace usage
- README files: Document the split clearly
- API docs: Mark endpoints as internal vs public

**DO NOT "HELPFULLY MERGE" DAENA AND VIBEAGENT AGAIN.**






