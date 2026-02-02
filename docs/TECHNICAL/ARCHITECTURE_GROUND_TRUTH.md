# Daena AI VP - Architecture Ground Truth Analysis

**Date**: 2025-01-XX  
**Purpose**: Comprehensive code-level analysis of current Daena system architecture  
**Status**: Working Document - Updated as analysis progresses

---

## PART 0: REPO SCAN & GROUND TRUTH

### Current System Architecture (From Code)

#### 1. Departments & Agents Structure

**Source**: `backend/database.py`, `backend/utils/sunflower_registry.py`, `backend/scripts/seed_6x8_council.py`

**Current Implementation**:
- **8 Departments**: engineering, product, sales, marketing, finance, hr, legal, customer
- **6 Agents per Department**: Total 48 agents
  - `advisor_a` - Senior Advisor
  - `advisor_b` - Strategy Advisor
  - `scout_internal` - Internal Scout
  - `scout_external` - External Scout
  - `synth` - Knowledge Synthesizer
  - `executor` - Action Executor
- **Sunflower Coordinates**: Golden angle distribution (137.507°)
- **Cell IDs**: Format `D{n}` for departments, `A{role}` for agents
- **Database Models**: `Department`, `Agent` in `backend/database.py`

**Key Files**:
- `backend/database.py` - SQLAlchemy models
- `backend/utils/sunflower_registry.py` - In-memory registry
- `backend/scripts/seed_6x8_council.py` - Seed script

---

#### 2. Council System

**Source**: `backend/services/council_service.py`, `backend/services/council_scheduler.py`

**Current Implementation**:
- **Phase-Locked Rounds**: Scout → Debate → Commit → CMP Validation → Memory Update
- **Advisor Personas**: Trained on real-world experts (Steve Jobs, Jeff Bezos, etc.)
- **Scout Phase**: Scouts publish NBMF summaries with confidence/emotion
- **Debate Phase**: Advisors exchange counter-drafts on ring topics
- **Commit Phase**: Executor applies actions; NBMF writes abstract + pointer
- **CMP Validation**: Consensus-based validation
- **Memory Update**: Updates NBMF memory with council conclusions

**Key Files**:
- `backend/services/council_service.py` - Council logic (integrated with DeviceManager for batch inference)
- `backend/services/council_scheduler.py` - Phase-locked scheduler
- `backend/models/database.py` - `CouncilConclusion`, `CouncilDebate`, `DebateArgument`, `CouncilMember`

**Database Models**:
- `CouncilConclusion` - Final synthesized decisions
- `CouncilDebate` - Debate records
- `DebateArgument` - Individual arguments
- `CouncilMember` - Council participants

---

#### 3. NBMF Memory System

**Source**: `memory_service/router.py`, `memory_service/abstract_store.py`, `memory_service/trust_manager.py`

**Current Implementation**:
- **Three-Tier Architecture**: L1 (hot), L2 (warm), L3 (cold)
- **Trust Pipeline**: TrustManager computes trust scores, promotes from quarantine
- **Ledger**: Append-only JSON lines ledger (`memory_service/ledger.py`)
- **Drill**: Disaster recovery drills (`Tools/daena_drill.py`)
- **Metrics**: Comprehensive metrics collection (`memory_service/metrics.py`)
- **Encoder/Decoder**: `nbmf_encoder.py`, `nbmf_decoder.py` (integrated with DeviceManager)
- **CAS**: Content-Addressable Storage with SimHash (`memory_service/caching_cas.py`)
- **DeviceManager**: Hardware abstraction layer for CPU/GPU/TPU (`Core/device_manager.py`)

**Key Files**:
- `memory_service/router.py` - Memory routing logic
- `memory_service/abstract_store.py` - Abstract + Lossless Pointer pattern
- `memory_service/trust_manager.py` - Trust scoring and promotion
- `memory_service/ledger.py` - Audit ledger
- `memory_service/quarantine_l2q.py` - Quarantine system
- `Core/device_manager.py` - Hardware abstraction (CPU/GPU/TPU)

**Storage Modes**:
- `ABSTRACT_ONLY` - Compressed semantic abstract
- `LOSSLESS_ONLY` - Exact preservation
- `HYBRID` - Abstract + lossless pointer

---

#### 4. Multi-Tenant / Per-Project Isolation

**Current State** (From Code Analysis):

**Tenant/Project Concepts**:
- **Tenant Rate Limiting**: `backend/middleware/tenant_rate_limit.py` - Per-tenant rate limits
- **Tenant Extraction**: `extract_tenant_id()` from headers/query params
- **Project Model**: Projects exist in `sunflower_registry.projects` but **NO Project database model found**
- **ABAC Policy**: `memory_service/policy.py` has `allow_tenants` / `deny_tenants` but **NOT consistently applied**
- **NBMF Router**: `router.py` has `tenant_allowlist` but **tenant_id NOT consistently scoped in memory operations**

**Gaps Identified**:
1. ❌ **No `Project` or `Tenant` database model** - Projects only in registry
2. ❌ **NBMF memory operations don't consistently include `tenant_id` in keys**
3. ❌ **Ledger entries don't consistently include `tenant_id`**
4. ❌ **ABAC policies exist but not enforced on all memory operations**
5. ⚠️ **Tenant isolation is partial** - rate limiting exists, but data isolation is incomplete

**Files with Tenant/Project References**:
- `backend/middleware/tenant_rate_limit.py` - Rate limiting per tenant
- `backend/routes/tenant_rate_limit.py` - Tenant rate limit API
- `memory_service/router.py` - `tenant_allowlist`, `_tenant_from_context()`
- `memory_service/policy.py` - `allow_tenants`, `deny_tenants` in policy config
- `memory_service/llm_exchange.py` - `tenant_id` parameter (optional)
- `backend/routes/projects.py` - Project routes (but no DB model)

---

#### 5. Backend Endpoints & Models

**System Summary**:
- `/api/v1/system/summary` - Single source of truth (`backend/routes/system_summary.py`)
- `/api/v1/system/health` - Health check
- `/api/v1/system/stats` - Backward compatible stats

**Monitoring**:
- `/api/v1/monitoring/metrics` - System metrics
- `/api/v1/monitoring/memory` - NBMF memory stats
- `/api/v1/monitoring/agent-metrics` - Agent metrics
- `/api/v1/monitoring/memory/cas` - CAS hit rate

**Council**:
- `/api/v1/council/*` - Council endpoints
- `/council-dashboard` - Council dashboard
- `/council-debate` - Debate interface
- `/council-synthesis` - Synthesis interface

**Projects**:
- `/api/v1/projects` - Projects list
- `/api/v1/projects/{project_id}` - Project details
- **Note**: Projects stored in-memory (`routes/projects.py`), not in database

**Departments/Agents**:
- `/api/v1/departments` - Department list
- `/api/v1/departments/{id}/agents` - Department agents
- `/department/{id}` - Department pages

**Database Models** (from `backend/database.py`):
- `User` - User accounts
- `Department` - 8 departments
- `Agent` - 48 agents (6 per department)
- `BrainModel` - LLM models
- `TrainingSession` - Training sessions
- `ConsensusVote` - Consensus votes
- `Decision` - Daena decisions
- `SystemConfig` - System configuration
- **Missing**: `Project`, `Tenant` models

**Database Models** (from `backend/models/database.py`):
- `CouncilConclusion` - Council conclusions
- `CouncilDebate` - Debate records
- `DebateArgument` - Arguments
- `CouncilMember` - Council members
- `KnowledgeBase` - Knowledge entries
- **Missing**: `Project`, `Tenant` models

---

#### 6. Frontend Pages

**Command Center** (`/command-center`):
- Shows system stats (total agents, active agents, projects, CAS hit rate)
- Department overview
- Central "D" hexagon (opens Daena Office)
- **Data Source**: `/api/v1/system/summary`

**Enhanced Dashboard** (`/enhanced-dashboard`):
- System metrics
- Memory stats (L1/L2/L3)
- Trust pipeline stats
- Department analytics
- **Data Source**: `/api/v1/system/summary`, `/api/v1/monitoring/metrics`

**Analytics** (`/analytics`):
- System performance metrics
- Department analytics
- Agent efficiency
- **Data Source**: `/api/v1/system/summary`, `/api/v1/monitoring/metrics`

**Daena Office** (`/daena-office`):
- VP interaction interface
- Chat with Daena
- Streaming responses
- **Data Source**: `/api/v1/daena/chat` (streaming)

**Department Pages** (`/department/{id}`):
- Individual department views
- Agent lists
- Department stats
- **Data Source**: `/api/v1/system/summary` (filtered by department)

**Council Pages**:
- `/council-dashboard` - Council overview
- `/council-debate` - Debate interface
- `/council-synthesis` - Synthesis interface
- **Data Source**: Council service endpoints

---

#### 7. Real-Time Update Mechanisms

**Current Implementation**:
- **Polling**: Frontend pages poll `/api/v1/system/summary` every 5 seconds
- **WebSocket**: `/ws/council` for council updates (`backend/services/websocket_service.py`)
- **SSE**: Streaming responses for Daena chat (`/api/v1/daena/chat`)

**Gaps**:
- ⚠️ No WebSocket for general system stats updates
- ⚠️ No real-time memory write notifications
- ⚠️ No real-time agent status updates (except council)

---

#### 8. Governance Layers

**Current Implementation**:
- **ABAC**: `backend/middleware/abac_middleware.py` - Attribute-Based Access Control
- **Policy**: `memory_service/policy.py` - Access policies
- **Ledger**: `memory_service/ledger.py` - Audit trail
- **Trust Manager**: `memory_service/trust_manager.py` - Trust scoring
- **Quarantine**: `memory_service/quarantine_l2q.py` - Quarantine system
- **Metrics**: `memory_service/metrics.py` - Comprehensive metrics

**Gaps**:
- ⚠️ ABAC not consistently applied to all endpoints
- ⚠️ Policy enforcement not verified on all memory operations

---

#### 9. Security Layers

**Current Implementation**:
- **API Key Guard**: `backend/middleware/api_key_guard.py` - API key authentication
- **Rate Limiting**: `backend/middleware/rate_limit.py` - Global rate limiting
- **Tenant Rate Limiting**: `backend/middleware/tenant_rate_limit.py` - Per-tenant limits
- **ABAC**: `backend/middleware/abac_middleware.py` - Access control
- **Encryption**: `memory_service/crypto.py` - AES-256 encryption
- **KMS**: `memory_service/kms.py` - Key management

**Gaps**:
- ❌ No threat detection system
- ❌ No red/blue team simulation
- ❌ No anomaly detection
- ❌ No intrusion detection
- ⚠️ Security logging exists but not centralized

---

#### 10. Message Bus & Routing

**Current Implementation**:
- **Message Bus V2**: `backend/utils/message_bus_v2.py` - Topic-based pub/sub
- **Topics**: `cell/{dept}/{cell_id}`, `ring/{k}`, `radial/{arm}`, `global/cmp`
- **Presence Service**: `backend/services/presence_service.py` - Agent presence
- **Quorum**: `backend/utils/quorum.py` - Quorum-based consensus
- **Backpressure**: `backend/utils/backpressure.py` - Flow control

**Key Features**:
- Topic-based subscriptions
- Wildcard patterns
- Ring/radial/global routing
- Presence beacons
- Quorum validation

---

#### 11. DeviceManager - Hardware Abstraction Layer

**Source**: `Core/device_manager.py`, `backend/config/settings.py`

**Current Implementation**:
- **Device Detection**: Automatic detection of CPU, GPU (CUDA/TensorFlow), and TPU (JAX)
- **Device Selection**: Configurable preference (auto, cpu, gpu, tpu) with automatic fallback
- **Batch Optimization**: Automatic batch size adjustment for TPU (default 128× multiplier)
- **Tensor Operations**: Unified interface for creating and moving tensors across devices
- **Cost Tracking**: Device cost estimation per hour
- **Memory Management**: Device memory reporting

**Configuration**:
- `COMPUTE_PREFER`: Device preference ("auto", "cpu", "gpu", "tpu")
- `COMPUTE_ALLOW_TPU`: Enable/disable TPU usage (default: true)
- `COMPUTE_TPU_BATCH_FACTOR`: Batch size multiplier for TPU (default: 128)

**Integration Points**:
- **NBMF Encoder/Decoder**: `memory_service/nbmf_encoder_production.py` - Tensor operations route through DeviceManager
- **Council Service**: `backend/services/council_service.py` - Batch inference for advisor debates
- **Diagnostic Tool**: `Tools/daena_device_report.py` - Device status reporting

**Key Features**:
- Automatic device detection (PyTorch CUDA, TensorFlow GPU, JAX TPU, nvidia-smi fallback)
- Batch size optimization for TPU efficiency
- Framework-agnostic tensor operations
- Device cost tracking
- Memory footprint reporting

**Files**:
- `Core/device_manager.py` - Main DeviceManager implementation
- `backend/config/settings.py` - Configuration settings
- `Tools/daena_device_report.py` - Diagnostic CLI tool

---

## PART 1: SPARRING QUESTIONS (5 CRITICAL CHECKS)

### Question 1: Tenant Data Isolation

**Where are the hard boundaries between global Daena memory and per-customer memory?**

**Current State** (From Code):
1. **Tenant Rate Limiting**: Exists (`tenant_rate_limit.py`) but only for rate limiting
2. **NBMF Router**: Has `tenant_allowlist` but tenant_id extraction is inconsistent
3. **Memory Operations**: `router.py` has `_tenant_from_context()` but **NOT consistently called**
4. **Ledger**: Ledger entries **DO NOT include tenant_id** in meta
5. **Abstract Store**: **NO tenant_id scoping** in abstract records
6. **Database**: **NO Project/Tenant models** - only in-memory registry

**Data Leakage Risks**:
- ❌ **HIGH RISK**: NBMF memory keys don't include tenant_id prefix
- ❌ **HIGH RISK**: Ledger entries don't include tenant_id
- ❌ **HIGH RISK**: Abstract store records don't include tenant_id
- ⚠️ **MEDIUM RISK**: Council conclusions don't include tenant_id
- ⚠️ **MEDIUM RISK**: Agent interactions don't include tenant_id

**Attack Paths**:
1. Attacker could query NBMF memory without tenant filter → see all tenant data
2. Attacker could read ledger entries → see all tenant operations
3. Attacker could access abstract store → see all tenant abstracts

**Gap**: **NO HARD BOUNDARIES** - Tenant isolation is incomplete.

---

### Question 2: Autonomous Action Flows

**Which flows today allow Daena to act without explicit human approval?**

**Current State** (From Code):
1. **Council Decisions**: `council_scheduler.py` - Executor can commit actions without approval
2. **Memory Writes**: `router.py` - Agents can write to NBMF without approval
3. **Trust Promotion**: `trust_manager.py` - Auto-promotes from quarantine based on trust score
4. **Aging/Compression**: `aging.py` - Automatic aging and compression
5. **CAS Deduplication**: Automatic deduplication
6. **Agent Actions**: Agents can execute tasks without explicit approval

**Worst-Case Impact**:
- **Financial**: Agent could allocate resources, approve spending, commit to contracts
- **Security**: Agent could modify access policies, disable security controls
- **Data**: Agent could delete or modify critical data
- **Reputation**: Agent could send unauthorized communications

**Gaps**:
- ❌ No approval workflow for high-impact actions
- ❌ No financial limits on autonomous actions
- ❌ No security action approval
- ⚠️ Council executor can commit without human review

---

### Question 3: Attack Pivot Paths

**If an attacker compromises one tenant's agents, how can they pivot?**

**Attack Paths Identified**:

1. **NBMF Memory**:
   - Current: Memory keys don't include tenant_id → attacker could read other tenants' memory
   - Risk: **HIGH** - No isolation

2. **Other Tenants**:
   - Current: No tenant_id in agent assignments → attacker could access other tenants' agents
   - Risk: **HIGH** - No isolation

3. **Global Brain**:
   - Current: Council conclusions stored globally → attacker could read global decisions
   - Risk: **MEDIUM** - Some isolation via ABAC but not complete

4. **Governance Modules**:
   - Current: ABAC policies stored globally → attacker could read/modify policies
   - Risk: **HIGH** - Policy access not tenant-scoped

**Gaps**:
- ❌ No tenant isolation in memory operations
- ❌ No tenant isolation in agent assignments
- ❌ No tenant isolation in council conclusions
- ❌ No tenant isolation in governance policies

---

### Question 4: Operational Visibility

**Which dashboards/logs would an operator use to answer: "What did Daena actually do for tenant X in the last 24 hours?"**

**Current State**:

**Dashboards**:
- `/command-center` - Shows system-wide stats (NOT tenant-specific)
- `/analytics` - Shows system-wide analytics (NOT tenant-specific)
- `/enhanced-dashboard` - Shows system-wide metrics (NOT tenant-specific)
- **Gap**: **NO tenant-specific dashboard**

**Logs**:
- Ledger: `memory_service/ledger.py` - But **NO tenant_id in entries**
- Council: `CouncilConclusion`, `CouncilDebate` - But **NO tenant_id**
- Agent Actions: Not logged with tenant_id
- **Gap**: **CANNOT query by tenant**

**Monitoring Endpoints**:
- `/api/v1/monitoring/metrics` - System-wide (NOT tenant-specific)
- `/api/v1/monitoring/memory` - System-wide (NOT tenant-specific)
- **Gap**: **NO tenant-specific monitoring**

**Answer**: **CANNOT ANSWER** - No tenant-scoped visibility exists.

---

### Question 5: Novelty vs. Competitors

**What is genuinely novel about NBMF + Sunflower-Honeycomb compared to LangGraph, crewAI, AutoGen?**

**Novel Features** (From Code):

1. **NBMF Memory**:
   - Abstract + Lossless Pointer pattern (NOT in competitors)
   - Confidence-based OCR fallback (NOT in competitors)
   - Three-tier memory with progressive compression (NOT in competitors)
   - CAS + SimHash deduplication (NOT in competitors)
   - Trust pipeline with quarantine (NOT in competitors)

2. **Sunflower-Honeycomb**:
   - Golden angle distribution (137.507°) - Mathematical novelty
   - Hex-mesh communication (NOT in competitors)
   - Phase-locked council rounds (NOT in competitors)
   - Ring/radial/global topic routing (NOT in competitors)

3. **Council System**:
   - Persona-based advisors (trained on real experts) - Similar to some but with NBMF integration
   - Phase-locked coordination (NOT in competitors)
   - NBMF memory feedback loop (NOT in competitors)

4. **Governance**:
   - Ledger-based audit trail (some competitors have this)
   - Trust-based promotion (NOT in competitors)
   - Quarantine system (NOT in competitors)

**Unique Combination**:
- NBMF + Sunflower + Council + Governance = **Unique stack**
- Individual components may exist elsewhere, but **combination is novel**

---

## BLIND SPOTS IDENTIFIED

### Critical Gaps

1. ❌ **No Project/Tenant Database Models**
2. ❌ **No Tenant Isolation in NBMF Memory**
3. ❌ **No Tenant Isolation in Ledger**
4. ❌ **No Tenant-Scoped Dashboards**
5. ❌ **No Tenant-Scoped Monitoring**
6. ❌ **No Approval Workflow for High-Impact Actions**
7. ❌ **No Threat Detection System**
8. ❌ **No Red/Blue Team Simulation**
9. ⚠️ **Council Conclusions Not Tenant-Scoped**
10. ⚠️ **Agent Assignments Not Tenant-Scoped**

---

**Next Steps**: Address each gap systematically in subsequent parts.

