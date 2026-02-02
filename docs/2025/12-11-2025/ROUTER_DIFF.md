# Router & Orchestration - Target vs Current State

## Target Design Requirements

### 1. Meta-Router
**Target**: `backend/services/router.py`
- `route(task_meta)` → `{provider, model, skills[], temperature, rationale}`
- Considers: department, agent, risk level, task type, skill requirements
- Automatic council escalation for high-risk/ambiguous tasks
- Returns routing rationale for transparency

**Current State**: ❌ **MISSING**
- Multiple simple routers exist but no unified meta-router
- `backend/llm/model_router.py` only does basic task→provider mapping
- No skill consideration, no council escalation logic

### 2. Model Registry
**Target**: Unified registry with local fallback, skill adapter registration, health endpoint

**Current State**: ✅ **PRESENT** (but needs upgrade)
- `backend/services/model_registry.py` exists and works well
- ✅ Local Ollama fallback implemented
- ✅ Trained model prioritization
- ❌ No skill adapter registration
- ❌ No `/api/health/models` endpoint

**Upgrade Needed**: Add adapter registration, health endpoint

### 3. Skill Adapters
**Target**: `backend/services/adapters.py`
- `load_adapter(skill)` - Load LoRA adapter
- `unload_adapter()` - Free VRAM
- `fuse_adapters(skills[])` - Combine multiple adapters
- LRU cache + reference counting

**Current State**: 🟡 **PARTIALLY PRESENT**
- `backend/services/skill_capsules.py` exists but is metadata-only
- ❌ No actual LoRA adapter loading/fusing
- ❌ No VRAM management
- ❌ No per-department adapter support

**Upgrade Needed**: Implement actual adapter loading/fusing with VRAM management

### 4. Council Orchestration
**Target**: Automatic escalation, 2-3 rounds, synthesis with Daena signature

**Current State**: ✅ **PRESENT** (but needs integration)
- `backend/services/council_governance_service.py` has full protocol
- ✅ 2-3 rounds implemented
- ✅ Synthesis with Daena signature
- ✅ Advisor selection by department
- ❌ Not automatically triggered by router
- ❌ No risk-based escalation logic in router

**Upgrade Needed**: Integrate council escalation into router

### 5. Knowledge Exchange (VibeAgent Bridge)
**Target**: Sanitized insights only, no PII/raw data

**Current State**: ✅ **PRESENT**
- `backend/services/vibe_bridge_client.py` exists
- `backend/services/knowledge_exchange.py` has sanitization
- ✅ Already filters PII
- ✅ Only shares patterns/methodologies
- ✅ No raw data exchange

**No Changes Needed**: Already compliant

### 6. UI Pages
**Target**: 
- `/ui/task/playground` - Test routing decisions
- `/ui/skills` - Manage adapters
- `/ui/training/distill` - Training interface

**Current State**: ❌ **MISSING**
- ✅ HTMX infrastructure exists
- ✅ Council audit UI exists (`/ui/council/run_audit`)
- ❌ No task playground
- ❌ No skills management UI
- ❌ No training/distill UI

**Upgrade Needed**: Create all three UI pages

### 7. Graceful "No Cloud Key" Behavior
**Target**: System works with local model, friendly errors (400 not 404)

**Current State**: ✅ **MOSTLY PRESENT**
- ✅ Model registry falls back to Ollama
- ✅ Local LLM service works
- ✅ Routes return 400 with helpful messages
- 🟡 Some routes may still crash (need verification)

**Upgrade Needed**: Verify all routes handle missing keys gracefully

## Implementation Checklist

### ✅ Already Present (No Changes)
- [x] Model registry with local fallback
- [x] Council governance with rounds/synthesis
- [x] VibeBridge client (sanitized)
- [x] Local Ollama integration
- [x] HTMX UI infrastructure
- [x] Knowledge exchange sanitization

### 🟡 Present But Needs Upgrade
- [ ] Model registry: Add adapter registration + health endpoint
- [ ] Council service: Integrate escalation into router
- [ ] Skill capsules: Add actual LoRA loading/fusing
- [ ] Routes: Verify graceful "no cloud key" handling

### ❌ Missing (Will Implement)
- [ ] Unified meta-router (`backend/services/router.py`)
- [ ] Adapter service (`backend/services/adapters.py`)
- [ ] Task playground UI (`/ui/task/playground`)
- [ ] Skills management UI (`/ui/skills`)
- [ ] Training/distill UI (`/ui/training/distill`)
- [ ] Router telemetry (`/api/metrics/router`)
- [ ] Model health endpoint (`/api/health/models`)

## Priority Order

1. **HIGH**: Unified router (core functionality)
2. **HIGH**: Adapter service (skill loading/fusing)
3. **MEDIUM**: UI pages (playground, skills, training)
4. **MEDIUM**: Router telemetry
5. **LOW**: Model health endpoint (nice to have)

## Duplicate Cleanup Needed

- `backend/llm/model_router.py` - Keep but integrate into unified router
- `Core/model_gateway.py` - Keep for hardware routing
- `Core/llm/llm_router_core.py` - Can be removed (too simple)
- `Core/kernel/model_router.py` - Can be removed (too simple)
- `Core/cmp/cmp_multimodel_router.py` - Review, may keep for CMP


