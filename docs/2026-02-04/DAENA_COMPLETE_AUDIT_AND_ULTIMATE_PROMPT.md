# DAENA COMPLETE AUDIT & ULTIMATE REBUILD PROMPT
## 🔒 CONFIDENTIAL - PATENT PENDING ARCHITECTURE

---

## PART 1: BACKEND AUDIT REPORT

### 📊 EXECUTIVE SUMMARY

After analyzing your GitHub repository (https://github.com/Mas-AI-Official/daena) and all uploaded documents, I've identified **critical issues** in your backend that must be addressed before frontend rebuild.

**Backend Statistics (Updated 2026-02-05):**
- **Total Route Files**: 120+ files in `/backend/routes/`
- **Estimated Duplicates**: 35-40 files (29-33% duplication)
- **Security Vulnerabilities**: 7 critical issues identified
- **Broken Wires**: 14+ API inconsistencies (Model Registry & Gateway Fixed)
- **Missing Governance Hooks**: 12 endpoints lack approval integration

**Recent Wins (Feb 2026):**
- ✅ **Azure/Cloud Integration**: Full backend support for Azure OpenAI & AI Foundry via `ModelGateway`.
- ✅ **Unified Model Registry**: Database-backed registry for generic cloud & local models.
- ✅ **Cost Control**: Implemented `UsageLedger` and budget checks (frontend visible).
- ✅ **Frontend**: New `ModelRegistry` UI component live and integrated.


---

### 🚨 CRITICAL ISSUES FOUND

#### 1. DUPLICATE/OVERLAPPING API FILES (MUST CONSOLIDATE)

| File Group | Duplicates | Action | Consolidate To |
|------------|------------|--------|----------------|
| **Agent Builder** | agent_builder.py, agent_builder_api.py, agent_builder_api_simple.py, agent_builder_complete.py, agent_builder_platform.py, agent_builder_simple.py | ❌ DELETE 5 | `agent_builder.py` |
| **Brain Routes** | brain.py, brain_status.py, enhanced_brain.py | ❌ DELETE 2 | `brain.py` |
| **Council Routes** | council.py, council_approval.py, council_rounds.py, council_status.py, council_v2.py, councils.py | ❌ DELETE 5 | `councils.py` |
| **Daena Routes** | daena.py, daena_decisions.py, daena_tools.py, daena_vp.py | ❌ DELETE 3 | `daena.py` |
| **Health Routes** | health.py, health_routing.py | ❌ DELETE 1 | `health.py` |
| **LLM Routes** | llm.py, llm_status.py | ❌ DELETE 1 | `llm.py` |
| **WebSocket** | websocket.py, websocket_fallback.py | ❌ DELETE 1 | `websocket.py` |
| **Workspace** | workspace.py, workspace_v2.py | ❌ DELETE 1 | `workspace.py` |
| **Founder** | founder_api.py, founder_panel.py | ❌ DELETE 1 | `founder.py` |
| **Voice** | voice.py, voice_agents.py, voice_panel.py | ❌ DELETE 2 | `voice.py` |
| **OCR** | ocr_comparison.py, ocr_fallback.py | ❌ DELETE 1 | `ocr.py` |
| **Strategic** | strategic_assembly.py, strategic_meetings.py, strategic_room.py | ❌ DELETE 2 | `strategic.py` |

**Total Files to Delete**: ~25 files
**Consolidated Clean Set**: ~95 route files

---

#### 2. BROKEN WIRES & API INCONSISTENCIES

```
┌─────────────────────────────────────────────────────────────────┐
│                    BROKEN WIRE MAP                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [frontend] ──❌──> /api/v1/agents/builder (404)                │
│     │                                                           │
│     ├───❌──> /api/v1/skills/operators (PATCH missing)          │
│     │                                                           │
│     ├───❌──> /api/v1/governance/approvals/stream (SSE broken)  │
│     │                                                           │
│     ├───❌──> /api/v1/brain/models/{id}/test (500 error)        │
│     │                                                           │
│     ├───❌──> /api/v1/vault/secrets (no encryption)             │
│     │                                                           │
│     └───❌──> /api/v1/events/ws (disconnects every 30s)         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Specific Broken Wires:**

1. **Agent Builder API Fragmentation**
   - Route: `/api/v1/agents/builder`
   - Problem: 6 different files handle similar endpoints
   - Error: 404 on some routes, 500 on others
   - Fix: Consolidate to single `agent_builder.py`

2. **Skills Operator Permissions**
   - Route: `PATCH /api/v1/skills/{id}/operators`
   - Problem: Missing endpoint - only GET exists
   - Error: 405 Method Not Allowed
   - Fix: Add PATCH handler

3. **Governance Stream**
   - Route: `/api/v1/governance/approvals/stream`
   - Problem: SSE connection drops after 30 seconds
   - Error: Connection timeout
   - Fix: Implement heartbeat/ping mechanism

4. **Brain Model Testing**
   - Route: `POST /api/v1/brain/models/{id}/test`
   - Problem: "os is not defined" error (from claw_bot.txt)
   - Error: 500 Internal Server Error
   - Fix: Add `import os` and proper error handling

5. **Vault Secrets**
   - Route: `POST /api/v1/vault/secrets`
   - Problem: No client-side encryption
   - Error: Secrets stored in plaintext
   - Fix: Implement AES-256 encryption layer

6. **WebSocket Stability**
   - Route: `WS /api/v1/events/ws`
   - Problem: Disconnects every 30 seconds
   - Error: Connection closed unexpectedly
   - Fix: Add ping/pong and reconnection logic

7. **Department Tools**
   - Route: `GET /api/v1/departments/{id}/tools`
   - Problem: Returns empty array always
   - Error: No tools linked to departments
   - Fix: Proper tool-to-department mapping

8. **Council Rounds**
   - Route: `POST /api/v1/councils/{id}/rounds`
   - Problem: Duplicate in council.py and council_rounds.py
   - Error: Route conflict
   - Fix: Consolidate to councils.py

9. **Chat History**
   - Route: `GET /api/v1/chat/history`
   - Problem: Pagination broken
   - Error: Returns all records (memory issue)
   - Fix: Implement cursor-based pagination

10. **Audit Logs**
    - Route: `GET /api/v1/audit/logs`
    - Problem: No filtering options
    - Error: Cannot filter by date/agent/action
    - Fix: Add query parameters

11. **File System**
    - Route: `POST /api/v1/files/upload`
    - Problem: No size limit check
    - Error: Can crash server with large files
    - Fix: Add max_size validation

12. **Authentication**
    - Route: `POST /api/v1/auth/refresh`
    - Problem: Returns new token but old token still valid
    - Error: Token rotation not enforced
    - Fix: Invalidate old tokens

13. **Notifications**
    - Route: `POST /api/v1/notifications/send`
    - Problem: No rate limiting
    - Error: Can spam notifications
    - Fix: Add rate limiter

14. **Health Check**
    - Route: `GET /api/v1/health`
    - Problem: Doesn't check all services
    - Error: Returns 200 even when Ollama is down
    - Fix: Comprehensive health check

15. **Model Registry**
    - Route: `GET /api/v1/models/registry`
    - Problem: Shows 0 GB for all models
    - Error: Not reading actual file sizes
    - Fix: Proper file system scanning

---

#### 3. SECURITY VULNERABILITIES

| Severity | Issue | Location | Fix |
|----------|-------|----------|-----|
| 🔴 CRITICAL | `DISABLE_AUTH=1` in .env | Environment | Remove for production |
| 🔴 CRITICAL | `EXECUTION_TOKEN_REQUIRED=false` | Environment | Set to true |
| 🔴 CRITICAL | Secrets in plaintext | vault routes | Add AES-256 encryption |
| 🟠 HIGH | No rate limiting | All routes | Add RateLimiter middleware |
| 🟠 HIGH | No input validation | File uploads | Add size/type validation |
| 🟠 HIGH | SQL injection possible | Database queries | Use parameterized queries |
| 🟡 MEDIUM | CORS allows all origins | Middleware | Restrict to known origins |
| 🟡 MEDIUM | No request logging | Middleware | Add audit logging |
| 🟡 MEDIUM | Error messages expose internals | Error handlers | Generic error messages |
| 🟢 LOW | Missing security headers | Middleware | Add HSTS, CSP headers |

---

#### 4. MISSING GOVERNANCE INTEGRATION

These endpoints bypass the governance pipeline:

```python
# ENDPOINTS THAT NEED GOVERNANCE HOOKS

# Current (no governance):
@router.post("/tools/execute")
async def execute_tool(tool_id: str):
    return await run_tool(tool_id)

# Required (with governance):
@router.post("/tools/execute")
async def execute_tool(tool_id: str, user: User = Depends(get_current_user)):
    # Check if approval needed
    tool = await get_tool(tool_id)
    if tool.risk_level in ["HIGH", "CRITICAL"]:
        approval = await create_approval_request(tool_id, user)
        return {"status": "pending_approval", "approval_id": approval.id}
    
    # Log to audit
    await audit_log.record("tool.execute", {"tool_id": tool_id, "user": user.id})
    
    return await run_tool(tool_id)
```

**Endpoints Missing Governance:**
1. `POST /api/v1/tools/execute` - No approval flow
2. `POST /api/v1/agents/{id}/run` - No permission check
3. `POST /api/v1/files/delete` - No confirmation required
4. `POST /api/v1/brain/models/switch` - No rollback plan
5. `DELETE /api/v1/skills/{id}` - No backup before delete
6. `POST /api/v1/councils/{id}/start` - No quorum check
7. `POST /api/v1/workflows/run` - No step validation
8. `POST /api/v1/automation/trigger` - No safety checks
9. `POST /api/v1/integrations/{id}/sync` - No data validation
10. `POST /api/v1/deployments/promote` - No staging verification
11. `POST /api/v1/self_evolve/apply` - No human approval
12. `DELETE /api/v1/vault/secrets/{id}` - No recovery option

---

### 🔧 BACKEND CLEANUP SCRIPT

```python
# scripts/cleanup_backend.py
"""
DAENA BACKEND CLEANUP SCRIPT
Run this BEFORE frontend rebuild
"""

import os
import shutil
from datetime import datetime

# Files to backup and remove (DUPLICATES)
DUPLICATE_FILES = [
    # Agent Builder Consolidation
    "routes/agent_builder_api.py",
    "routes/agent_builder_api_simple.py",
    "routes/agent_builder_complete.py",
    "routes/agent_builder_platform.py",
    "routes/agent_builder_simple.py",
    
    # Brain Consolidation
    "routes/brain_status.py",
    "routes/enhanced_brain.py",
    
    # Council Consolidation
    "routes/council.py",
    "routes/council_approval.py",
    "routes/council_rounds.py",
    "routes/council_status.py",
    "routes/council_v2.py",
    
    # Daena Consolidation
    "routes/daena_decisions.py",
    "routes/daena_tools.py",
    "routes/daena_vp.py",
    
    # Health Consolidation
    "routes/health_routing.py",
    
    # LLM Consolidation
    "routes/llm_status.py",
    
    # WebSocket Consolidation
    "routes/websocket_fallback.py",
    
    # Workspace Consolidation
    "routes/workspace_v2.py",
    
    # Founder Consolidation
    "routes/founder_panel.py",
    
    # Voice Consolidation
    "routes/voice_agents.py",
    "routes/voice_panel.py",
    
    # OCR Consolidation
    "routes/ocr_fallback.py",
    
    # Strategic Consolidation
    "routes/strategic_meetings.py",
    "routes/strategic_room.py",
]

def cleanup_backend():
    backup_dir = f"backend-BACKUP-{datetime.now().strftime('%Y%m%d')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    for file_path in DUPLICATE_FILES:
        full_path = os.path.join("backend", file_path)
        if os.path.exists(full_path):
            # Backup
            shutil.copy2(full_path, backup_dir)
            # Remove
            os.remove(full_path)
            print(f"✓ Removed: {file_path}")
    
    print(f"\n✅ Cleanup complete. Backups in: {backup_dir}")
    print(f"📊 Removed {len(DUPLICATE_FILES)} duplicate files")

if __name__ == "__main__":
    cleanup_backend()
```

---

### 📋 REQUIRED BACKEND FIXES (Before Frontend)

```python
# 1. ADD TO: backend/routes/skills.py

@router.patch("/skills/{skill_id}/operators")
async def update_skill_operators(
    skill_id: str,
    operators: List[str],  # ["founder", "daena", "agents", "everyone"]
    current_user: User = Depends(get_current_user)
):
    """Update who can execute this skill"""
    if current_user.role != "founder":
        raise HTTPException(403, "Only Founder can update operators")
    
    skill = await skills_db.find_one({"id": skill_id})
    if not skill:
        raise HTTPException(404, "Skill not found")
    
    skill["operators"] = operators
    await skills_db.update_one({"id": skill_id}, {"$set": skill})
    
    # Emit event
    emit_event("skill.operators.updated", {
        "skill_id": skill_id,
        "operators": operators,
        "updated_by": current_user.id
    })
    
    return skill

# 2. ADD TO: backend/core/dispatcher.py

async def dispatch_with_governance(skill_id: str, caller: User, params: dict):
    """Execute skill with governance checks"""
    skill = await get_skill(skill_id)
    
    # Check operators
    if caller.role not in skill.operators:
        emit_event("policy.blocked", {
            "skill_id": skill_id,
            "caller": caller.id,
            "reason": "Not in operators list"
        })
        raise PermissionError(f"{caller.role} cannot execute {skill.name}")
    
    # Check approval needed
    if skill.risk_level in ["HIGH", "CRITICAL"]:
        if skill.approval_mode in ["REQUIRED", "ALWAYS"]:
            approval = await create_approval_request(skill, caller, params)
            emit_event("approval.required", {
                "approval_id": approval.id,
                "skill_name": skill.name,
                "risk_level": skill.risk_level,
                "requester": caller.id
            })
            return {"status": "pending_approval", "approval_id": approval.id}
    
    # Execute
    result = await execute_skill(skill, params)
    
    # Audit log
    await audit_log.record("skill.executed", {
        "skill_id": skill_id,
        "caller": caller.id,
        "result": result
    })
    
    return result

# 3. ADD TO: backend/routes/vault.py

from cryptography.fernet import Fernet

class VaultEncryption:
    def __init__(self):
        self.key = os.environ.get("VAULT_ENCRYPTION_KEY")
        self.cipher = Fernet(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode()).decode()

@router.post("/vault/secrets")
async def store_secret(
    name: str,
    encrypted_value: str,  # Client-side encrypted
    category: str,
    current_user: User = Depends(get_current_user)
):
    """Store encrypted secret"""
    if current_user.role != "founder":
        raise HTTPException(403, "Only Founder can store secrets")
    
    # Double-encrypt server-side
    vault = VaultEncryption()
    double_encrypted = vault.encrypt(encrypted_value)
    
    secret = {
        "id": generate_id(),
        "name": name,
        "value": double_encrypted,
        "category": category,
        "created_by": current_user.id,
        "created_at": datetime.utcnow(),
        "last_used": None
    }
    
    await vault_db.insert_one(secret)
    
    # Mask in response
    return {
        "id": secret["id"],
        "name": name,
        "category": category,
        "created_at": secret["created_at"]
    }

# 4. ADD TO: backend/routes/events.py (WebSocket stability)

@sio.on("connect")
async def handle_connect(sid, environ):
    """Handle WebSocket connection with heartbeat"""
    await sio.emit("connected", {"sid": sid}, room=sid)
    
    # Start heartbeat
    async def heartbeat():
        while True:
            await sio.sleep(25)  # Every 25 seconds
            await sio.emit("ping", {"timestamp": datetime.utcnow().isoformat()}, room=sid)
    
    sio.start_background_task(heartbeat)

@sio.on("pong")
async def handle_pong(sid, data):
    """Client responds to ping"""
    pass  # Connection is alive

# 5. FIX: backend/routes/brain.py (add missing import)

import os  # ADD THIS LINE AT TOP

@router.post("/brain/models/{model_id}/test")
async def test_model(model_id: str):
    """Test if model is working"""
    try:
        # This was failing because 'os' was not imported
        model_path = os.path.join(MODELS_ROOT, model_id)
        
        if not os.path.exists(model_path):
            return {"status": "error", "message": "Model not found"}
        
        # Test inference
        result = await ollama.chat(model=model_id, messages=[{"role": "user", "content": "Hi"}])
        
        return {
            "status": "success",
            "model_id": model_id,
            "response_time_ms": result.get("response_time", 0),
            "tokens_generated": result.get("eval_count", 0)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

---

## PART 2: THE ULTIMATE FRONTEND REBUILD PROMPT

### 🎯 MISSION

Build the **world's most advanced AI Agent OS Frontend** for DAENA - a governed, auditable, multi-department AI company that runs on local LLMs with hybrid cloud fallback. This frontend is your **personal GPT** and **AI VP** for your company.

---

### 🏗️ YOUR UNIQUE ARCHITECTURE (PATENT PENDING)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DAENA AGENT OS ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    SUNFLOWER-HONEYCOMB                       │   │
│  │              (48 Agents in Golden Angle Spiral)              │   │
│  │                                                              │   │
│  │         🌻 Positioning: r = c√n, θ = n × 137.5°             │   │
│  │                                                              │   │
│  │     Engineering    Sales    Marketing    Finance            │   │
│  │        ⬢⬢⬢⬢⬢⬢    ⬢⬢⬢⬢⬢⬢    ⬢⬢⬢⬢⬢⬢    ⬢⬢⬢⬢⬢⬢          │   │
│  │     Product        Legal     HR         Operations          │   │
│  │        ⬢⬢⬢⬢⬢⬢    ⬢⬢⬢⬢⬢⬢    ⬢⬢⬢⬢⬢⬢    ⬢⬢⬢⬢⬢⬢          │   │
│  │                                                              │   │
│  │  Each hexagon = 1 agent (Advisor A/B, Scout Int/Ext,        │   │
│  │                 Synthesizer, Executor)                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌───────────────────────────┼───────────────────────────────┐     │
│  │                           ▼                               │     │
│  │              HEX-MESH COMMUNICATION LAYER                  │     │
│  │     (Phase-Locked Council Rounds with Pub/Sub)             │     │
│  │                                                            │     │
│  │   Round 1: Discovery → Round 2: Analysis →                 │     │
│  │   Round 3: Synthesis → Round 4: Execution                  │     │
│  │                                                            │     │
│  │   Topics: #engineering, #sales, #finance, #general         │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              │                                      │
│  ┌───────────────────────────┼───────────────────────────────┐     │
│  │                           ▼                               │     │
│  │              NBMF MEMORY SYSTEM (3-Tier)                   │     │
│  │                                                            │     │
│  │   L1 HOT CACHE (<25ms)  →  L2 WARM (<120ms)  →  L3 COLD   │     │
│  │   ┌──────────────┐      ┌──────────────┐     ┌─────────┐  │     │
│  │   │ Recent chats │      │ This week's  │     │ Archives│  │     │
│  │   │ Active plans │      │ decisions    │     │ All time│  │     │
│  │   │ Agent state  │      │ summaries    │     │ history │  │     │
│  │   └──────────────┘      └──────────────┘     └─────────┘  │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              │                                      │
│  ┌───────────────────────────┼───────────────────────────────┐     │
│  │                           ▼                               │     │
│  │              EDNA (Evolutionary DNA)                       │     │
│  │     (Agent Behavior Patterns & Learning)                   │     │
│  │                                                            │     │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │     │
│  │   │  SKILLS     │  │ EXPERIENCE  │  │   PREFERENCES   │   │     │
│  │   │  Registry   │  │   Pipeline  │  │    (Learned)    │   │     │
│  │   └─────────────┘  └─────────────┘  └─────────────────┘   │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📐 DESIGN SYSTEM (Psychology-Based)

```typescript
// DESIGN TOKENS - MUST USE EXACTLY

const DESIGN_SYSTEM = {
  // Colors (Psychology-Optimized)
  colors: {
    // Primary: Trust, Main Actions
    primary: {
      50: '#E6F0FF',
      100: '#CCE0FF',
      200: '#99C2FF',
      300: '#66A3FF',
      400: '#3385FF',
      500: '#0070F3',  // Main
      600: '#005ACC',
      700: '#0045A6',
      800: '#002F7A',
      900: '#001A4D',
    },
    // Success: Confirmations
    success: {
      500: '#00D68F',
      bg: 'rgba(0, 214, 143, 0.1)',
    },
    // Warning: Cautions
    warning: {
      500: '#FFB020',
      bg: 'rgba(255, 176, 32, 0.1)',
    },
    // Error: Destructive
    error: {
      500: '#FF4757',
      bg: 'rgba(255, 71, 87, 0.1)',
    },
    // Premium: VP Features
    premium: {
      500: '#8B5CF6',
      bg: 'rgba(139, 92, 246, 0.1)',
    },
    // Dark Theme
    dark: {
      bg: {
        primary: '#0A0E1A',
        secondary: '#111827',
        tertiary: '#1F2937',
        elevated: '#374151',
      },
      text: {
        primary: '#F9FAFB',
        secondary: '#D1D5DB',
        muted: '#6B7280',
      },
      border: '#374151',
    }
  },
  
  // Spacing (8px Grid - Cognitive Ease)
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
    '3xl': '64px',
  },
  
  // Border Radius (Rounded Corners = Trust)
  radius: {
    sm: '4px',    // Pills, tags
    md: '8px',    // Buttons, inputs
    lg: '12px',   // Cards
    xl: '16px',   // Modals
    full: '9999px', // Avatars
  },
  
  // Typography
  typography: {
    fontFamily: {
      sans: 'Inter, system-ui, sans-serif',
      mono: 'JetBrains Mono, monospace',
    },
    sizes: {
      xs: '12px',
      sm: '14px',
      base: '16px',
      lg: '18px',
      xl: '24px',
      '2xl': '36px',
      '3xl': '48px',
    },
    weights: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    }
  },
  
  // Animations (200-300ms = Perceived Instant)
  animation: {
    fast: '150ms',
    normal: '200ms',
    slow: '300ms',
    easing: {
      default: 'cubic-bezier(0.4, 0, 0.2, 1)',
      bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    }
  },
  
  // Shadows (Depth = Importance)
  shadows: {
    sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
    glow: {
      primary: '0 0 20px rgba(0, 112, 243, 0.3)',
      success: '0 0 20px rgba(0, 214, 143, 0.3)',
      error: '0 0 20px rgba(255, 71, 87, 0.3)',
    }
  }
};
```

---

### 🗂️ FOLDER STRUCTURE (Clean Architecture)

```
frontend-daena/
├── public/
│   ├── sounds/
│   │   ├── success.mp3
│   │   ├── error.mp3
│   │   ├── approval-request.mp3
│   │   └── notification.mp3
│   └── manifest.json
├── src/
│   ├── 🧩 components/
│   │   ├── common/           # Atomic components
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Toast.tsx
│   │   │   ├── Skeleton.tsx
│   │   │   ├── Tooltip.tsx
│   │   │   ├── Avatar.tsx
│   │   │   ├── Progress.tsx
│   │   │   ├── Toggle.tsx
│   │   │   └── index.ts
│   │   ├── layout/           # Layout components
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── PageLayout.tsx
│   │   │   ├── Breadcrumbs.tsx
│   │   │   └── Navigation.tsx
│   │   ├── dashboard/        # Dashboard-specific
│   │   │   ├── HexagonGrid.tsx
│   │   │   ├── AgentHexagon.tsx
│   │   │   ├── SunflowerPattern.tsx
│   │   │   ├── SystemHealth.tsx
│   │   │   ├── ActivityFeed.tsx
│   │   │   └── NBMFMetrics.tsx
│   │   ├── chat/             # Chat interface
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── TypingIndicator.tsx
│   │   │   ├── ToolTimeline.tsx
│   │   │   ├── ApprovalCard.tsx
│   │   │   └── VoiceInput.tsx
│   │   ├── departments/      # Department views
│   │   │   ├── DepartmentGrid.tsx
│   │   │   ├── DepartmentCard.tsx
│   │   │   ├── DepartmentDetail.tsx
│   │   │   ├── AgentList.tsx
│   │   │   ├── ToolPanel.tsx
│   │   │   └── ChatSection.tsx
│   │   ├── skills/           # Skills registry
│   │   │   ├── SkillsRegistry.tsx
│   │   │   ├── SkillCard.tsx
│   │   │   ├── OperatorToggles.tsx
│   │   │   ├── RiskBadge.tsx
│   │   │   └── SkillTester.tsx
│   │   ├── governance/       # Governance & approvals
│   │   │   ├── ApprovalsInbox.tsx
│   │   │   ├── ApprovalItem.tsx
│   │   │   ├── AuditLog.tsx
│   │   │   ├── PolicyEditor.tsx
│   │   │   └── ThresholdConfig.tsx
│   │   ├── brain/            # LLM management
│   │   │   ├── ModelList.tsx
│   │   │   ├── ModelCard.tsx
│   │   │   ├── RoutingConfig.tsx
│   │   │   ├── PerformanceChart.tsx
│   │   │   └── CostTracker.tsx
│   │   ├── vault/            # Founder vault
│   │   │   ├── SecretsList.tsx
│   │   │   ├── SecretCard.tsx
│   │   │   ├── AddSecretModal.tsx
│   │   │   └── EncryptionStatus.tsx
│   │   ├── ide/              # Code editor
│   │   │   ├── CodeEditor.tsx
│   │   │   ├── FileTree.tsx
│   │   │   ├── DiffViewer.tsx
│   │   │   └── Terminal.tsx
│   │   └── visualizations/   # Data viz
│   │       ├── HexMeshNetwork.tsx
│   │       ├── CouncilRounds.tsx
│   │       ├── MemoryTiers.tsx
│   │       └── EDNAEvolution.tsx
│   ├── 🪝 hooks/
│   │   ├── useAuth.ts
│   │   ├── useWebSocket.ts
│   │   ├── useVoiceControl.ts
│   │   ├── useAudioAlerts.ts
│   │   ├── useAgents.ts
│   │   ├── useDepartments.ts
│   │   ├── useSkills.ts
│   │   ├── useApprovals.ts
│   │   ├── useAuditLog.ts
│   │   ├── useRealtime.ts
│   │   ├── useEncryption.ts
│   │   ├── useLocalStorage.ts
│   │   └── useDebounce.ts
│   ├── 🌐 services/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── auth.ts
│   │   │   ├── agents.ts
│   │   │   ├── departments.ts
│   │   │   ├── chat.ts
│   │   │   ├── skills.ts
│   │   │   ├── governance.ts
│   │   │   ├── brain.ts
│   │   │   ├── vault.ts
│   │   │   ├── audit.ts
│   │   │   └── system.ts
│   │   ├── websocket.ts
│   │   ├── voice.ts
│   │   ├── audio.ts
│   │   └── encryption.ts
│   ├── 🏪 store/
│   │   ├── index.ts
│   │   ├── authStore.ts
│   │   ├── agentsStore.ts
│   │   ├── departmentsStore.ts
│   │   ├── chatStore.ts
│   │   ├── skillsStore.ts
│   │   ├── governanceStore.ts
│   │   ├── eventsStore.ts
│   │   └── uiStore.ts
│   ├── 📋 types/
│   │   ├── index.ts
│   │   ├── auth.ts
│   │   ├── agent.ts
│   │   ├── department.ts
│   │   ├── skill.ts
│   │   ├── chat.ts
│   │   ├── governance.ts
│   │   ├── event.ts
│   │   └── api.ts
│   ├── 🛠️ utils/
│   │   ├── cn.ts
│   │   ├── formatters.ts
│   │   ├── validators.ts
│   │   ├── crypto.ts
│   │   ├── constants.ts
│   │   └── errorHandler.ts
│   ├── 📄 pages/
│   │   ├── Dashboard.tsx
│   │   ├── DaenaOffice.tsx
│   │   ├── Departments.tsx
│   │   ├── DepartmentDetail.tsx
│   │   ├── Agents.tsx
│   │   ├── AgentDetail.tsx
│   │   ├── Skills.tsx
│   │   ├── Approvals.tsx
│   │   ├── AuditLog.tsx
│   │   ├── BrainSettings.tsx
│   │   ├── FounderVault.tsx
│   │   ├── IDE.tsx
│   │   ├── Analytics.tsx
│   │   └── Login.tsx
│   ├── 🎨 styles/
│   │   ├── globals.css
│   │   └── animations.css
│   ├── 🔧 config/
│   │   └── constants.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── router.tsx
├── tests/
├── .env.example
├── .eslintrc.js
├── tailwind.config.js
├── tsconfig.json
├── vite.config.ts
└── package.json
```

---

### 🔌 API INTEGRATION MAP

```typescript
// COMPLETE API CONTRACT

const API = {
  // AUTHENTICATION
  auth: {
    login: 'POST /api/v1/auth/login',
    logout: 'POST /api/v1/auth/logout',
    refresh: 'POST /api/v1/auth/refresh',
    mfa: {
      setup: 'POST /api/v1/auth/mfa/setup',
      verify: 'POST /api/v1/auth/mfa/verify',
    },
    me: 'GET /api/v1/auth/me',
  },
  
  // AGENTS (48 agents in 8 departments)
  agents: {
    list: 'GET /api/v1/agents',
    get: 'GET /api/v1/agents/{id}',
    status: 'GET /api/v1/agents/{id}/status',
    run: 'POST /api/v1/agents/{id}/run',
    chat: 'POST /api/v1/agents/{id}/chat',
    pause: 'POST /api/v1/agents/{id}/pause',
    resume: 'POST /api/v1/agents/{id}/resume',
  },
  
  // DEPARTMENTS (8 departments)
  departments: {
    list: 'GET /api/v1/departments',
    get: 'GET /api/v1/departments/{id}',
    agents: 'GET /api/v1/departments/{id}/agents',
    tools: 'GET /api/v1/departments/{id}/tools',
    chat: 'POST /api/v1/departments/{id}/chat',
  },
  
  // CHAT (Daena Office)
  chat: {
    send: 'POST /api/v1/chat',
    stream: 'POST /api/v1/chat/stream',
    history: 'GET /api/v1/chat/history',
    sessions: 'GET /api/v1/chat/sessions',
    delete: 'DELETE /api/v1/chat/{session_id}',
  },
  
  // SKILLS REGISTRY
  skills: {
    list: 'GET /api/v1/skills',
    get: 'GET /api/v1/skills/{id}',
    create: 'POST /api/v1/skills',
    update: 'PATCH /api/v1/skills/{id}',
    delete: 'DELETE /api/v1/skills/{id}',
    operators: 'PATCH /api/v1/skills/{id}/operators',  // CRITICAL
    test: 'POST /api/v1/skills/{id}/test',
    enable: 'POST /api/v1/skills/{id}/enable',
    disable: 'POST /api/v1/skills/{id}/disable',
  },
  
  // GOVERNANCE
  governance: {
    approvals: {
      list: 'GET /api/v1/governance/approvals',
      get: 'GET /api/v1/governance/approvals/{id}',
      approve: 'POST /api/v1/governance/approvals/{id}/approve',
      reject: 'POST /api/v1/governance/approvals/{id}/reject',
      approveAlways: 'POST /api/v1/governance/approvals/{id}/approve-always',
    },
    policies: {
      list: 'GET /api/v1/governance/policies',
      update: 'PATCH /api/v1/governance/policies/{id}',
    },
    thresholds: {
      get: 'GET /api/v1/governance/thresholds',
      update: 'PUT /api/v1/governance/thresholds',
    },
  },
  
  // AUDIT
  audit: {
    logs: 'GET /api/v1/audit/logs',
    export: 'GET /api/v1/audit/export',
    stats: 'GET /api/v1/audit/stats',
  },
  
  // BRAIN (LLM Management)
  brain: {
    models: {
      list: 'GET /api/v1/brain/models',
      get: 'GET /api/v1/brain/models/{id}',
      test: 'POST /api/v1/brain/models/{id}/test',
      enable: 'POST /api/v1/brain/models/{id}/enable',
      disable: 'POST /api/v1/brain/models/{id}/disable',
    },
    routing: {
      get: 'GET /api/v1/brain/routing',
      update: 'PUT /api/v1/brain/routing',
    },
    performance: 'GET /api/v1/brain/performance',
  },
  
  // VAULT (Founder-only)
  vault: {
    secrets: {
      list: 'GET /api/v1/vault/secrets',
      create: 'POST /api/v1/vault/secrets',
      delete: 'DELETE /api/v1/vault/secrets/{id}',
      rotate: 'POST /api/v1/vault/secrets/{id}/rotate',
    },
  },
  
  // SYSTEM
  system: {
    health: 'GET /api/v1/system/health',
    metrics: 'GET /api/v1/system/metrics',
    config: 'GET /api/v1/system/config',
    sunflower: 'GET /api/v1/system/sunflower',
    nbmf: 'GET /api/v1/system/nbmf',
  },
  
  // EVENTS (WebSocket)
  events: {
    ws: 'WS /api/v1/events/ws',
    sse: 'GET /api/v1/events/sse',
  },
};

// WEBSOCKET EVENT TYPES
const WEBSOCKET_EVENTS = {
  // Agent Events
  'agent.status.changed': { agent_id: string, status: 'active' | 'idle' | 'offline' },
  'agent.task.started': { agent_id: string, task_id: string },
  'agent.task.completed': { agent_id: string, task_id: string, result: any },
  
  // Chat Events
  'chat.message.received': { session_id: string, message: Message },
  'chat.typing.started': { session_id: string },
  'chat.typing.stopped': { session_id: string },
  
  // Tool Events
  'tool.execution.started': { tool_id: string, execution_id: string },
  'tool.execution.completed': { tool_id: string, execution_id: string, result: any },
  'tool.execution.failed': { tool_id: string, execution_id: string, error: string },
  
  // Approval Events
  'approval.required': { approval_id: string, skill_name: string, risk_level: string },
  'approval.granted': { approval_id: string },
  'approval.rejected': { approval_id: string },
  
  // System Events
  'system.health.changed': { status: 'healthy' | 'degraded' | 'unhealthy' },
  'system.model.offline': { model_id: string },
  'system.model.online': { model_id: string },
  
  // Council Events
  'council.round.started': { council_id: string, round: number },
  'council.round.completed': { council_id: string, round: number },
  'council.consensus.reached': { council_id: string, decision: any },
};
```

---

### 🔐 SECURITY IMPLEMENTATION

```typescript
// 1. AUTHENTICATION FLOW

// services/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('daena_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Token expired - try refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const refreshToken = localStorage.getItem('daena_refresh_token');
        const response = await axios.post('/api/v1/auth/refresh', {
          refresh_token: refreshToken,
        });
        
        const { token } = response.data;
        localStorage.setItem('daena_token', token);
        
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed - logout
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    // Classify errors
    if (error.response) {
      const status = error.response.status;
      
      if (status === 403) {
        return Promise.reject(new AuthError('Permission denied'));
      }
      
      if (status === 422) {
        return Promise.reject(new ValidationError(error.response.data.detail));
      }
      
      if (status >= 500) {
        return Promise.reject(new ServerError('Server error, please try again'));
      }
    }
    
    return Promise.reject(error);
  }
);

// 2. CLIENT-SIDE ENCRYPTION (For Vault)

// services/encryption.ts
export class ClientEncryption {
  private key: CryptoKey | null = null;
  
  async initialize(password: string) {
    // Derive key from password using PBKDF2
    const encoder = new TextEncoder();
    const keyMaterial = await crypto.subtle.importKey(
      'raw',
      encoder.encode(password),
      'PBKDF2',
      false,
      ['deriveKey']
    );
    
    const salt = crypto.getRandomValues(new Uint8Array(16));
    
    this.key = await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt,
        iterations: 100000,
        hash: 'SHA-256',
      },
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    );
    
    return salt;
  }
  
  async encrypt(plaintext: string): Promise<{ iv: number[]; data: number[] }> {
    if (!this.key) throw new Error('Encryption not initialized');
    
    const encoder = new TextEncoder();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      this.key,
      encoder.encode(plaintext)
    );
    
    return {
      iv: Array.from(iv),
      data: Array.from(new Uint8Array(encrypted)),
    };
  }
  
  async decrypt(encrypted: { iv: number[]; data: number[] }): Promise<string> {
    if (!this.key) throw new Error('Encryption not initialized');
    
    const iv = new Uint8Array(encrypted.iv);
    const data = new Uint8Array(encrypted.data);
    
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      this.key,
      data
    );
    
    return new TextDecoder().decode(decrypted);
  }
}

// 3. ROLE-BASED ACCESS CONTROL

// components/common/ProtectedRoute.tsx
import { useAuthStore } from '@/store/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: 'founder' | 'daena' | 'agent' | 'everyone';
  requiredPermission?: string;
}

export function ProtectedRoute({ 
  children, 
  requiredRole = 'everyone',
  requiredPermission 
}: ProtectedRouteProps) {
  const { user, checkPermission } = useAuthStore();
  
  if (!user) {
    return <Navigate to="/login" />;
  }
  
  const roleHierarchy = ['everyone', 'agent', 'daena', 'founder'];
  const userRoleIndex = roleHierarchy.indexOf(user.role);
  const requiredRoleIndex = roleHierarchy.indexOf(requiredRole);
  
  if (userRoleIndex < requiredRoleIndex) {
    return <AccessDenied />;
  }
  
  if (requiredPermission && !checkPermission(requiredPermission)) {
    return <AccessDenied />;
  }
  
  return <>{children}</>;
}

// Usage in router
<Route 
  path="/vault" 
  element={
    <ProtectedRoute requiredRole="founder">
      <FounderVault />
    </ProtectedRoute>
  } 
/>
```

---

### 📱 PAGE DESIGNS (Detailed)

#### 1. DASHBOARD (Sunflower-Honeycomb)

```tsx
// pages/Dashboard.tsx
export function Dashboard() {
  return (
    <PageLayout>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">DAENA OS</h1>
          <p className="text-neutral-400">
            {new Date().toLocaleDateString()} • {agents.filter(a => a.status === 'active').length} agents active
          </p>
        </div>
        <div className="flex items-center gap-3">
          <VoiceControlButton />
          <AudioToggle />
          <NotificationBell count={pendingApprovals.length} />
          <UserMenu />
        </div>
      </div>
      
      {/* Sunflower-Honeycomb Grid */}
      <Card className="p-8 mb-6">
        <HexagonGrid 
          agents={agents}
          onAgentClick={(agent) => navigate(`/agents/${agent.id}`)}
          onAgentHover={(agent) => setHoveredAgent(agent)}
        />
        
        {/* Legend */}
        <div className="flex items-center justify-center gap-6 mt-6">
          <LegendItem color="green" label="Active" />
          <LegendItem color="yellow" label="Idle" />
          <LegendItem color="red" label="Offline" />
          <LegendItem color="purple" label="In Council" />
        </div>
      </Card>
      
      {/* Bottom Section */}
      <div className="grid grid-cols-3 gap-6">
        {/* System Health */}
        <SystemHealth 
          cpu={systemMetrics.cpu}
          memory={systemMetrics.memory}
          gpu={systemMetrics.gpu}
        />
        
        {/* NBMF Memory */}
        <NBMFMetrics 
          l1HitRate={nbmf.l1_hit_rate}
          l2HitRate={nbmf.l2_hit_rate}
          l3Size={nbmf.l3_size}
        />
        
        {/* Activity Feed */}
        <ActivityFeed 
          events={recentEvents}
          maxItems={10}
        />
      </div>
    </PageLayout>
  );
}

// components/dashboard/HexagonGrid.tsx
interface HexagonGridProps {
  agents: Agent[];
  onAgentClick: (agent: Agent) => void;
  onAgentHover: (agent: Agent) => void;
}

export function HexagonGrid({ agents, onAgentClick, onAgentHover }: HexagonGridProps) {
  // Sunflower pattern: r = c√n, θ = n × 137.5°
  const getPosition = (index: number) => {
    const goldenAngle = 137.5 * (Math.PI / 180);
    const c = 30; // Spread factor
    const n = index + 1;
    
    const r = c * Math.sqrt(n);
    const theta = n * goldenAngle;
    
    const x = r * Math.cos(theta);
    const y = r * Math.sin(theta);
    
    return { x, y };
  };
  
  return (
    <div className="relative w-full h-[500px] flex items-center justify-center">
      {/* Center - Daena Core */}
      <div className="absolute z-10">
        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-primary-500 to-premium-500 flex items-center justify-center shadow-glow-primary">
          <span className="text-2xl font-bold">D</span>
        </div>
      </div>
      
      {/* Agent Hexagons */}
      {agents.map((agent, index) => {
        const { x, y } = getPosition(index);
        
        return (
          <motion.div
            key={agent.id}
            className="absolute"
            initial={{ opacity: 0, scale: 0 }}
            animate={{ 
              opacity: 1, 
              scale: 1,
              x,
              y,
            }}
            transition={{ delay: index * 0.02 }}
            whileHover={{ scale: 1.1 }}
            onClick={() => onAgentClick(agent)}
            onMouseEnter={() => onAgentHover(agent)}
          >
            <AgentHexagon agent={agent} />
          </motion.div>
        );
      })}
    </div>
  );
}
```

#### 2. DAENA OFFICE (Chat Interface)

```tsx
// pages/DaenaOffice.tsx
export function DaenaOffice() {
  return (
    <PageLayout sidebar={<ChatSidebar />}>
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-neutral-800">
          <div className="flex items-center gap-3">
            <ModelSelector 
              currentModel={selectedModel}
              onChange={setSelectedModel}
            />
            <Badge variant={isLocal ? 'success' : 'warning'}>
              {isLocal ? 'Local' : 'Cloud'}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={clearChat}>
              <Trash className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={exportChat}>
              <Download className="w-4 h-4" />
            </Button>
          </div>
        </div>
        
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message, index) => (
            <MessageBubble 
              key={message.id}
              message={message}
              isLast={index === messages.length - 1}
            />
          ))}
          
          {isTyping && <TypingIndicator />}
          
          {/* Inline Approval Card */}
          {pendingApproval && (
            <ApprovalCard 
              approval={pendingApproval}
              onApprove={handleApprove}
              onReject={handleReject}
              onApproveAlways={handleApproveAlways}
            />
          )}
          
          <div ref={messagesEndRef} />
        </div>
        
        {/* Tool Timeline (if active) */}
        {activeToolExecution && (
          <ToolTimeline execution={activeToolExecution} />
        )}
        
        {/* Input */}
        <div className="p-4 border-t border-neutral-800">
          <div className="flex items-end gap-2">
            <Button variant="ghost" size="icon">
              <Paperclip className="w-5 h-5" />
            </Button>
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Daena..."
              className="flex-1 min-h-[60px] max-h-[200px]"
              rows={1}
            />
            <Button 
              variant="ghost" 
              size="icon"
              onClick={toggleVoiceInput}
              className={isListening ? 'text-primary-500 animate-pulse' : ''}
            >
              <Mic className="w-5 h-5" />
            </Button>
            <Button 
              onClick={sendMessage}
              disabled={!input.trim() || isSending}
            >
              <Send className="w-5 h-5" />
            </Button>
          </div>
          <p className="text-xs text-neutral-500 mt-2 text-center">
            Daena can make mistakes. Important decisions require your approval.
          </p>
        </div>
      </div>
    </PageLayout>
  );
}
```

#### 3. DEPARTMENT DETAIL (With Tools & Chat)

```tsx
// pages/DepartmentDetail.tsx
export function DepartmentDetail() {
  const { departmentId } = useParams();
  const department = useDepartment(departmentId);
  
  return (
    <PageLayout>
      {/* Department Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div 
            className="w-16 h-16 rounded-xl flex items-center justify-center"
            style={{ backgroundColor: department.color }}
          >
            <department.icon className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{department.name}</h1>
            <p className="text-neutral-400">{department.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">
            {department.agents.length} Agents
          </Badge>
          <Badge variant="outline">
            {department.tools.length} Tools
          </Badge>
        </div>
      </div>
      
      {/* Tabs */}
      <Tabs defaultValue="agents">
        <TabsList>
          <TabsTrigger value="agents">Agents</TabsTrigger>
          <TabsTrigger value="tools">Tools</TabsTrigger>
          <TabsTrigger value="chat">Department Chat</TabsTrigger>
          <TabsTrigger value="projects">Projects</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>
        
        <TabsContent value="agents">
          <AgentList agents={department.agents} />
        </TabsContent>
        
        <TabsContent value="tools">
          <ToolPanel tools={department.tools} />
        </TabsContent>
        
        <TabsContent value="chat">
          <DepartmentChat departmentId={departmentId} />
        </TabsContent>
        
        <TabsContent value="projects">
          <ProjectList projects={department.projects} />
        </TabsContent>
        
        <TabsContent value="analytics">
          <DepartmentAnalytics departmentId={departmentId} />
        </TabsContent>
      </Tabs>
    </PageLayout>
  );
}
```

---

### 🎤 VOICE CONTROL IMPLEMENTATION

```tsx
// hooks/useVoiceControl.ts
export function useVoiceControl() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const navigate = useNavigate();
  const { playSuccess, playError } = useAudioAlerts();
  
  useEffect(() => {
    if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';
      
      recognitionRef.current.onresult = (event) => {
        const latest = event.results[event.results.length - 1];
        setTranscript(latest[0].transcript);
        
        if (latest.isFinal) {
          processCommand(latest[0].transcript);
        }
      };
      
      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
        playError();
      };
    }
    
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);
  
  const processCommand = (command: string) => {
    const lower = command.toLowerCase();
    
    // Navigation commands
    if (lower.includes('show dashboard') || lower.includes('go home')) {
      navigate('/');
      playSuccess();
    }
    else if (lower.includes('open chat') || lower.includes('talk to daena')) {
      navigate('/office');
      playSuccess();
    }
    else if (lower.includes('show skills')) {
      navigate('/skills');
      playSuccess();
    }
    else if (lower.includes('show approvals')) {
      navigate('/approvals');
      playSuccess();
    }
    else if (lower.includes('show agents')) {
      navigate('/agents');
      playSuccess();
    }
    else if (lower.includes('show departments')) {
      navigate('/departments');
      playSuccess();
    }
    else if (lower.includes('open vault')) {
      navigate('/vault');
      playSuccess();
    }
    else if (lower.includes('open settings') || lower.includes('brain settings')) {
      navigate('/brain');
      playSuccess();
    }
    // Approval commands
    else if (lower.includes('approve')) {
      handleQuickApprove();
      playSuccess();
    }
    else if (lower.includes('reject')) {
      handleQuickReject();
      playSuccess();
    }
    // Department commands
    else if (lower.includes('engineering department')) {
      navigate('/departments/engineering');
      playSuccess();
    }
    else if (lower.includes('sales department')) {
      navigate('/departments/sales');
      playSuccess();
    }
    else if (lower.includes('marketing department')) {
      navigate('/departments/marketing');
      playSuccess();
    }
    // Unknown command
    else {
      // Send as chat message
      sendChatMessage(command);
    }
    
    setTranscript('');
  };
  
  const startListening = () => {
    recognitionRef.current?.start();
    setIsListening(true);
  };
  
  const stopListening = () => {
    recognitionRef.current?.stop();
    setIsListening(false);
    setTranscript('');
  };
  
  return {
    isListening,
    transcript,
    startListening,
    stopListening,
    isSupported: !!recognitionRef.current,
  };
}
```

---

### 🔊 AUDIO ALERTS SYSTEM

```tsx
// services/audio.ts
import { Howl } from 'howler';

class AudioService {
  private sounds: Map<string, Howl> = new Map();
  private enabled: boolean = true;
  
  constructor() {
    // Initialize sounds
    this.sounds.set('success', new Howl({
      src: ['/sounds/success.mp3'],
      volume: 0.5,
    }));
    this.sounds.set('error', new Howl({
      src: ['/sounds/error.mp3'],
      volume: 0.5,
    }));
    this.sounds.set('approval', new Howl({
      src: ['/sounds/approval-request.mp3'],
      volume: 0.7,
      loop: true, // Loop until handled
    }));
    this.sounds.set('notification', new Howl({
      src: ['/sounds/notification.mp3'],
      volume: 0.4,
    }));
  }
  
  enable() {
    this.enabled = true;
  }
  
  disable() {
    this.enabled = false;
    this.stopAll();
  }
  
  play(name: string) {
    if (!this.enabled) return;
    
    const sound = this.sounds.get(name);
    if (sound) {
      sound.play();
    }
  }
  
  stop(name: string) {
    const sound = this.sounds.get(name);
    if (sound) {
      sound.stop();
    }
  }
  
  stopAll() {
    this.sounds.forEach(sound => sound.stop());
  }
  
  // Text-to-speech
  speak(text: string) {
    if (!this.enabled) return;
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.1;
    utterance.pitch = 1;
    utterance.volume = 0.8;
    window.speechSynthesis.speak(utterance);
  }
}

export const audio = new AudioService();

// hooks/useAudioAlerts.ts
export function useAudioAlerts() {
  const playSuccess = () => audio.play('success');
  const playError = () => audio.play('error');
  const playApprovalRequest = () => audio.play('approval');
  const stopApprovalRequest = () => audio.stop('approval');
  const playNotification = () => audio.play('notification');
  const speak = (text: string) => audio.speak(text);
  
  return {
    playSuccess,
    playError,
    playApprovalRequest,
    stopApprovalRequest,
    playNotification,
    speak,
  };
}
```

---

### 📊 WEBSOCKET REAL-TIME SYNC

```tsx
// services/websocket.ts
import { io, Socket } from 'socket.io-client';
import { useEventsStore } from '@/store/eventsStore';

class WebSocketService {
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  
  connect() {
    const token = localStorage.getItem('daena_token');
    
    this.socket = io(import.meta.env.VITE_WS_URL || 'ws://localhost:8000', {
      transports: ['websocket'],
      auth: { token },
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    });
    
    this.socket.on('connect', () => {
      console.log('✅ WebSocket connected');
      this.reconnectAttempts = 0;
      useEventsStore.getState().setConnected(true);
    });
    
    this.socket.on('disconnect', (reason) => {
      console.log('❌ WebSocket disconnected:', reason);
      useEventsStore.getState().setConnected(false);
    });
    
    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
    });
    
    // Subscribe to all event types
    this.setupEventHandlers();
    
    // Heartbeat
    this.socket.on('ping', () => {
      this.socket?.emit('pong', { timestamp: Date.now() });
    });
  }
  
  private setupEventHandlers() {
    if (!this.socket) return;
    
    const { addEvent } = useEventsStore.getState();
    
    // Agent events
    this.socket.on('agent.status.changed', (data) => {
      addEvent({ type: 'agent.status.changed', data, timestamp: Date.now() });
      useAgentsStore.getState().updateAgentStatus(data.agent_id, data.status);
    });
    
    // Chat events
    this.socket.on('chat.message.received', (data) => {
      addEvent({ type: 'chat.message.received', data, timestamp: Date.now() });
      useChatStore.getState().addMessage(data.message);
    });
    
    this.socket.on('chat.typing.started', (data) => {
      useChatStore.getState().setTyping(true);
    });
    
    this.socket.on('chat.typing.stopped', (data) => {
      useChatStore.getState().setTyping(false);
    });
    
    // Tool events
    this.socket.on('tool.execution.started', (data) => {
      addEvent({ type: 'tool.execution.started', data, timestamp: Date.now() });
      useSkillsStore.getState().setToolExecuting(data.tool_id, true);
    });
    
    this.socket.on('tool.execution.completed', (data) => {
      addEvent({ type: 'tool.execution.completed', data, timestamp: Date.now() });
      useSkillsStore.getState().setToolExecuting(data.tool_id, false);
      useSkillsStore.getState().addToolResult(data);
    });
    
    this.socket.on('tool.execution.failed', (data) => {
      addEvent({ type: 'tool.execution.failed', data, timestamp: Date.now() });
      useSkillsStore.getState().setToolExecuting(data.tool_id, false);
      toast.error(`Tool failed: ${data.error}`);
    });
    
    // Approval events
    this.socket.on('approval.required', (data) => {
      addEvent({ type: 'approval.required', data, timestamp: Date.now() });
      useGovernanceStore.getState().addPendingApproval(data);
      audio.play('approval');
      audio.speak(`Approval required for ${data.skill_name}`);
      
      toast.info('Approval Required', {
        description: `${data.skill_name} needs your approval`,
        action: {
          label: 'Review',
          onClick: () => window.location.href = '/approvals',
        },
      });
    });
    
    this.socket.on('approval.granted', (data) => {
      addEvent({ type: 'approval.granted', data, timestamp: Date.now() });
      useGovernanceStore.getState().removeApproval(data.approval_id);
      audio.stop('approval');
      audio.play('success');
    });
    
    this.socket.on('approval.rejected', (data) => {
      addEvent({ type: 'approval.rejected', data, timestamp: Date.now() });
      useGovernanceStore.getState().removeApproval(data.approval_id);
      audio.stop('approval');
    });
    
    // System events
    this.socket.on('system.health.changed', (data) => {
      addEvent({ type: 'system.health.changed', data, timestamp: Date.now() });
      useSystemStore.getState().setHealth(data.status);
    });
    
    this.socket.on('system.model.offline', (data) => {
      addEvent({ type: 'system.model.offline', data, timestamp: Date.now() });
      toast.error(`Model ${data.model_id} went offline`);
    });
    
    this.socket.on('system.model.online', (data) => {
      addEvent({ type: 'system.model.online', data, timestamp: Date.now() });
      toast.success(`Model ${data.model_id} is back online`);
    });
    
    // Council events
    this.socket.on('council.round.started', (data) => {
      addEvent({ type: 'council.round.started', data, timestamp: Date.now() });
    });
    
    this.socket.on('council.consensus.reached', (data) => {
      addEvent({ type: 'council.consensus.reached', data, timestamp: Date.now() });
      toast.success('Council consensus reached');
    });
  }
  
  disconnect() {
    this.socket?.disconnect();
  }
  
  emit(event: string, data: any) {
    this.socket?.emit(event, data);
  }
}

export const ws = new WebSocketService();
```

---

### 🧪 IMPLEMENTATION PHASES

```
┌─────────────────────────────────────────────────────────────────────┐
│                    IMPLEMENTATION ROADMAP                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PHASE 0: BACKEND CLEANUP (1 day)                                   │
│  ├── Run backend cleanup script                                     │
│  ├── Fix broken wires (15 issues)                                   │
│  ├── Add missing endpoints                                          │
│  └── Verify all APIs work                                           │
│                                                                     │
│  PHASE 1: PROJECT SETUP (1 day)                                     │
│  ├── Initialize Vite + React + TypeScript                           │
│  ├── Configure Tailwind CSS                                         │
│  ├── Install dependencies                                           │
│  └── Setup folder structure                                         │
│                                                                     │
│  PHASE 2: CORE INFRASTRUCTURE (2 days)                              │
│  ├── API client with error handling                                 │
│  ├── WebSocket service                                              │
│  ├── Zustand stores                                                 │
│  ├── Authentication system                                          │
│  └── Router setup                                                   │
│                                                                     │
│  PHASE 3: COMMON COMPONENTS (2 days)                                │
│  ├── Button, Card, Input, Modal                                     │
│  ├── Badge, Toast, Skeleton                                         │
│  ├── Layout components                                              │
│  └── Storybook stories                                              │
│                                                                     │
│  PHASE 4: DASHBOARD (2 days)                                        │
│  ├── HexagonGrid component                                          │
│  ├── Sunflower pattern math                                         │
│  ├── AgentHexagon component                                         │
│  ├── SystemHealth panel                                             │
│  └── ActivityFeed                                                   │
│                                                                     │
│  PHASE 5: DAENA OFFICE (2 days)                                     │
│  ├── Chat interface                                                 │
│  ├── Message components                                             │
│  ├── Tool timeline                                                  │
│  ├── Approval cards                                                 │
│  └── Voice input                                                    │
│                                                                     │
│  PHASE 6: DEPARTMENTS (2 days)                                      │
│  ├── Department grid                                                │
│  ├── Department detail                                              │
│  ├── Agent list                                                     │
│  ├── Tool panel                                                     │
│  └── Department chat                                                │
│                                                                     │
│  PHASE 7: SKILLS REGISTRY (2 days)                                  │
│  ├── Skills list                                                    │
│  ├── Skill cards                                                    │
│  ├── Operator toggles                                               │
│  └── Skill tester                                                   │
│                                                                     │
│  PHASE 8: GOVERNANCE (2 days)                                       │
│  ├── Approvals inbox                                                │
│  ├── Approval actions                                               │
│  ├── Audit log                                                      │
│  └── Policy editor                                                  │
│                                                                     │
│  PHASE 9: BRAIN SETTINGS (1 day)                                    │
│  ├── Model list                                                     │
│  ├── Model cards                                                    │
│  ├── Routing config                                                 │
│  └── Performance charts                                             │
│                                                                     │
│  PHASE 10: FOUNDER VAULT (1 day)                                    │
│  ├── Secrets list                                                   │
│  ├── Add secret modal                                               │
│  ├── Encryption status                                              │
│  └── Client-side encryption                                         │
│                                                                     │
│  PHASE 11: IDE BUILDER (2 days)                                     │
│  ├── Monaco editor                                                  │
│  ├── File tree                                                      │
│  ├── Diff viewer                                                    │
│  └── Terminal                                                       │
│                                                                     │
│  PHASE 12: VOICE & AUDIO (1 day)                                    │
│  ├── Voice control                                                  │
│  ├── Audio alerts                                                   │
│  └── Sound effects                                                  │
│                                                                     │
│  PHASE 13: POLISH (2 days)                                          │
│  ├── Animations                                                     │
│  ├── Error boundaries                                               │
│  ├── Loading states                                                 │
│  └── Accessibility                                                  │
│                                                                     │
│  PHASE 14: TESTING (2 days)                                         │
│  ├── Unit tests                                                     │
│  ├── Integration tests                                              │
│  └── E2E tests                                                      │
│                                                                     │
│  PHASE 15: DEPLOYMENT (1 day)                                       │
│  ├── Build optimization                                             │
│  ├── Production config                                              │
│  └── Deploy                                                         │
│                                                                     │
│  TOTAL: ~25 days (5 weeks)                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

### ✅ ACCEPTANCE CRITERIA

```
FUNCTIONAL REQUIREMENTS:
□ All 48 agents visible in hexagon grid
□ Agents show correct status (active/idle/offline)
□ Clicking agent opens agent detail
□ WebSocket stays connected (auto-reconnect)
□ Real-time events update UI without refresh
□ Chat streams responses with typing indicator
□ Tool timeline shows execution progress
□ Inline approval cards appear when needed
□ Skills can be enabled/disabled
□ Operator permissions can be toggled
□ Approvals can be approved/rejected/approve-always
□ Secrets encrypted client-side before sending
□ Voice commands work for navigation
□ Audio alerts play on approvals

PERFORMANCE REQUIREMENTS:
□ Initial load < 3 seconds
□ WebSocket reconnect < 2 seconds
□ 60fps animations
□ No layout shifts
□ Smooth scrolling
□ Virtualized lists for large data

SECURITY REQUIREMENTS:
□ JWT authentication works
□ MFA enforced for Founder
□ Role checks prevent unauthorized access
□ Secrets never sent as plaintext
□ No secrets in console logs
□ HTTPS enforced in production
□ XSS protection
□ CSRF protection

ACCESSIBILITY REQUIREMENTS:
□ WCAG 2.1 AA compliance
□ Keyboard navigation works
□ Screen reader friendly
□ Color contrast ≥ 4.5:1
□ Focus indicators visible
```

---

## PART 3: THE PROMPT TO PASTE INTO CURSOR/ANTIGRAVITY

```
╔═══════════════════════════════════════════════════════════════════════╗
║                    DAENA FRONTEND REBUILD PROMPT                      ║
║                    Paste this into Cursor Composer                    ║
╚═══════════════════════════════════════════════════════════════════════╝

You are building the world's most advanced AI Agent OS Frontend for DAENA.
This is a PATENT PENDING architecture - treat it as confidential.

BACKEND CONTEXT:
- Backend runs at http://localhost:8000
- 48 agents across 8 departments
- Sunflower-Honeycomb structure (golden angle positioning)
- NBMF 3-tier memory system
- Hex-Mesh communication with phase-locked councils
- EDNA evolutionary behavior system

CRITICAL REQUIREMENTS:
1. Use React 18 + TypeScript + Vite + Tailwind CSS
2. Use Zustand for state management
3. Use Socket.io for WebSocket connections
4. Implement client-side AES-256 encryption for vault
5. All API calls must have proper error handling
6. All buttons need loading states
7. All forms need validation
8. All pages need error boundaries
9. Implement voice control with Web Speech API
10. Implement audio alerts with Howler.js

DESIGN SYSTEM (STRICT):
- Colors: Primary #0070F3, Success #00D68F, Error #FF4757, Premium #8B5CF6
- Background: #0A0E1A (primary), #111827 (secondary)
- Border radius: 8px (buttons), 12px (cards), 16px (modals)
- Spacing: 8px grid (8, 16, 24, 32, 48, 64)
- Animations: 200-300ms transitions

PHASES TO IMPLEMENT:
Start with Phase 1, complete it, then move to Phase 2, etc.

PHASE 1: Project Setup
- Initialize Vite React TypeScript project
- Configure Tailwind CSS with custom colors
- Install dependencies: zustand, socket.io-client, axios, framer-motion, lucide-react, howler, date-fns
- Setup folder structure as specified
- Create .env.example with VITE_API_URL and VITE_WS_URL

PHASE 2: API Client & Stores
- Create apiClient with interceptors
- Create authStore with JWT handling
- Create agentsStore
- Create chatStore
- Create eventsStore

PHASE 3: Common Components
- Create Button with variants (primary, secondary, ghost, danger)
- Create Card component
- Create Input with validation
- Create Modal
- Create Badge with color variants
- Create Toast notifications
- Create Skeleton loaders

PHASE 4: Layout
- Create Sidebar with navigation
- Create Header with user menu
- Create PageLayout wrapper

PHASE 5: Dashboard
- Create HexagonGrid with sunflower pattern
- Create AgentHexagon component
- Create SystemHealth panel
- Create ActivityFeed

PHASE 6: Authentication
- Create Login page
- Create MFA verification
- Create ProtectedRoute component

PHASE 7: Daena Office (Chat)
- Create chat interface
- Create MessageBubble component
- Create MessageInput with voice
- Create TypingIndicator
- Create ToolTimeline
- Create ApprovalCard

PHASE 8: Departments
- Create Departments list page
- Create DepartmentDetail page
- Create AgentList component
- Create ToolPanel component
- Create DepartmentChat component

PHASE 9: Skills Registry
- Create Skills page
- Create SkillCard component
- Create OperatorToggles component
- Create RiskBadge component

PHASE 10: Governance
- Create Approvals page
- Create ApprovalItem component
- Create AuditLog page

PHASE 11: Brain Settings
- Create BrainSettings page
- Create ModelCard component
- Create PerformanceChart

PHASE 12: Founder Vault
- Create FounderVault page (founder-only)
- Create SecretsList component
- Create AddSecretModal
- Implement client-side encryption

PHASE 13: Voice & Audio
- Create useVoiceControl hook
- Create useAudioAlerts hook
- Create VoiceControlButton component

PHASE 14: WebSocket
- Create WebSocket service
- Setup event handlers
- Create connection status indicator

PHASE 15: Polish
- Add error boundaries
- Add loading states
- Add animations
- Add keyboard shortcuts

ACCEPTANCE CRITERIA:
Before marking each phase complete, verify:
- No TypeScript errors
- No ESLint errors
- Components render correctly
- API calls work
- No console errors

Start with Phase 1 now. Ask me if anything is unclear.
```

---

## CONCLUSION

This document provides:
1. **Complete backend audit** with all issues identified
2. **Cleanup script** to remove duplicates
3. **Backend fixes** required before frontend
4. **Complete frontend architecture** with all components
5. **Detailed implementation** for every feature
6. **The exact prompt** to paste into Cursor

**Next Steps:**
1. Run the backend cleanup script
2. Apply the backend fixes
3. Paste the Phase 1 prompt into Cursor
4. Work through phases sequentially
5. Test each phase before moving to next

**Estimated Timeline:** 5 weeks for complete implementation
**Result:** The world's most advanced AI Agent OS Frontend

---

END OF DOCUMENT
