# Router & Orchestration Inventory

## Existing Routers/Registries Found

### 1. Model Registry
**File**: `backend/services/model_registry.py`
- **Purpose**: Manages AI model registration and retrieval
- **Features**:
  - Auto-detects Ollama when no cloud keys
  - Prioritizes trained model (`daena-brain`) over default
  - Returns 400 (not 404) with helpful messages
  - Supports multiple providers (Azure, OpenAI, DeepSeek, Anthropic, Gemini, Ollama)
- **Status**: ✅ Well-implemented, already handles local fallback

### 2. LLM Service
**File**: `backend/services/llm_service.py`
- **Purpose**: Provider abstraction layer for cloud LLMs
- **Features**:
  - Supports OpenAI, Azure, Gemini, Anthropic, DeepSeek, Grok
  - Has fallback mechanism
  - Streaming support
- **Status**: ✅ Good, but doesn't integrate with model_registry or router

### 3. Local LLM (Ollama)
**File**: `backend/services/local_llm_ollama.py`
- **Purpose**: Local inference via Ollama
- **Features**:
  - Auto-detects trained model
  - Falls back to default model
  - Respects `OLLAMA_MODELS` env var (D: drive)
- **Status**: ✅ Complete, well-integrated

### 4. Model Router (Basic)
**File**: `backend/llm/model_router.py`
- **Purpose**: Simple task-based routing
- **Features**:
  - `pick(task)` method
  - Basic provider selection
- **Status**: 🟡 Present but basic - no skills, no council escalation, no rationale

### 5. Model Gateway (Core)
**File**: `Core/model_gateway.py`
- **Purpose**: Hardware-aware model gateway
- **Features**:
  - CPU/GPU/TPU routing
  - Provider abstraction
  - Cost tracking
- **Status**: 🟡 Present but separate from backend services

### 6. Council Governance Service
**File**: `backend/services/council_governance_service.py`
- **Purpose**: Proactive governance and auditing
- **Features**:
  - 2-3 rounds of debate
  - Synthesis with Daena signature
  - Multiple audit types
  - Advisor selection
- **Status**: ✅ Well-implemented, has rounds and synthesis

### 7. Council Service
**File**: `backend/services/council_service.py`
- **Purpose**: Core council orchestration
- **Features**:
  - Debate rounds
  - Advisor responses
  - Synthesis
- **Status**: ✅ Exists, used by governance service

### 8. Skill Capsules
**File**: `backend/services/skill_capsules.py`
- **Purpose**: Skill/ability management
- **Status**: ✅ Exists, need to check adapter loading/fusing

### 9. VibeBridge Client
**File**: `backend/services/vibe_bridge_client.py`
- **Purpose**: Safe exchange with VibeAgent
- **Features**:
  - Sends sanitized insights only
  - No raw data exchange
- **Status**: ✅ Exists, already sanitized

### 10. Other Routers (Core)
- `Core/llm/llm_router_core.py` - Simple router
- `Core/kernel/model_router.py` - Another simple router
- `Core/cmp/cmp_multimodel_router.py` - Multi-model router
- **Status**: 🟡 Multiple simple routers, need consolidation

## Current Routing Decision Logic

### How Routing Works Today:
1. **LLM Service**: Uses `get_best_provider()` - priority-based (OpenAI > Gemini > Anthropic)
2. **Model Router**: Uses `pick(task)` - task-based rules
3. **Model Gateway**: Hardware-based routing (CPU/GPU/TPU)
4. **No unified meta-router** that considers:
   - Department/agent context
   - Risk level
   - Skill requirements
   - Council escalation triggers

### Council Orchestration:
- ✅ **Exists**: `council_governance_service.py` has full protocol
- ✅ **Rounds**: 2-3 rounds implemented
- ✅ **Synthesis**: Daena signature required
- ✅ **Advisor Selection**: By department/domain
- 🟡 **Triggering**: Not automatically triggered by router

### Skill Adapters:
- ✅ **Service exists**: `skill_capsules.py`
- ❓ **Loading/Fusing**: Need to check if LoRA adapters are loaded/fused
- ❓ **Per-department**: Need to verify department-specific adapters

### UI Integration:
- ✅ **HTMX templates exist**: `backend/ui/templates/`
- ✅ **Council audit UI**: `/ui/council/run_audit` exists
- ❌ **Task playground**: Not found
- ❌ **Skills management UI**: Not found
- ❌ **Training/distill UI**: Not found

## Current Model Registry Usage

### How It's Used:
- **Registration**: Auto-seeds from env vars on startup
- **Retrieval**: `model_registry.get(model_id)` returns ModelConfig
- **Fallback**: Returns default model if requested not found
- **Integration**: Used by `ai_models.py` routes

### Missing:
- ❌ Integration with router for automatic model selection
- ❌ Skill adapter registration
- ❌ Health endpoint (`/api/health/models`)

## VibeAgent Bridge

### Current Implementation:
- ✅ **Client exists**: `vibe_bridge_client.py`
- ✅ **Sanitized**: Only sends insights, not raw data
- ✅ **Routes exist**: Knowledge exchange layer registered
- ✅ **No PII**: Already filtered

## Summary

### ✅ What's Good:
- Model registry with local fallback ✅
- Council governance with rounds/synthesis ✅
- VibeBridge client (sanitized) ✅
- Local Ollama integration ✅
- HTMX UI infrastructure ✅

### 🟡 What Needs Upgrade:
- Multiple simple routers → Need unified meta-router
- No automatic council escalation from router
- Skill adapters loading/fusing unclear
- No task playground UI
- No skills management UI

### ❌ What's Missing:
- Unified meta-router (`backend/services/router.py`)
- Task playground UI (`/ui/task/playground`)
- Skills management UI (`/ui/skills`)
- Training/distill UI (`/ui/training/distill`)
- Router telemetry/metrics
- Automatic council escalation logic
- Skill adapter loading/fusing implementation
- Health endpoint for models/adapters


