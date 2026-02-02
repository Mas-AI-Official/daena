# Repository Scan Summary - QA Guardian Extended Implementation

**Date:** 2026-01-21
**Objective:** Enable Daena VP to audit and fix errors across entire system with founder approval gates, wire frontend-backend real-time sync, and redesign CMP as n8n-like node graph.

---

## 📊 What Exists Now

### 1. QA/Guardian System
| Component | Status | Path |
|-----------|--------|------|
| QA Guardian Charter | ✅ Exists | `docs/QA_GUARDIAN_CHARTER.md` |
| QA Guardian Module | ✅ Exists | `backend/qa_guardian/` |
| Guardian Loop | ✅ Exists | `backend/qa_guardian/guardian_loop.py` |
| Decision Engine | ✅ Exists | `backend/qa_guardian/decision_engine.py` |
| 6 QA Agents | ✅ Exists | `backend/qa_guardian/agents/` |
| API Routes | ✅ Exists | `backend/routes/qa_guardian.py` |
| DB Models | ✅ Exists | `backend/database.py` (QAIncident, QAPatchProposal, QAAuditLog) |
| Dashboard UI | ✅ Exists | `frontend/templates/qa_guardian_dashboard.html` |
| Unit Tests | ✅ Exists | `tests/qa_guardian/test_qa_guardian.py` |
| Golden Workflows | ✅ Exists | `tests/golden_workflows/test_golden_workflows.py` |
| CI Workflow | ✅ Exists | `.github/workflows/qa-guardian-ci.yml` |
| Legacy Guardian Stubs | ⚠️ Multiple | `Core/guardian/`, `security/guardian/`, etc. |

### 2. Auditing
| Component | Status | Path |
|-----------|--------|------|
| Audit Log Tool | ✅ Exists | `backend/tools/audit_log.py` |
| Audit Routes | ✅ Exists | `backend/routes/audit.py` |
| Decision Audit | ✅ Exists | `Core/ethics/decision_audit.py` |
| System Audit | ✅ Exists | `Core/system/system_audit.py` |
| Memory Audit | ✅ Exists | `memory_service/audit.py` |
| Chain Auditor | ⚠️ Stub | `Core/reaction_audit/chain_auditor.py` |

### 3. CMP (Consensus Model Protocol)
| Component | Status | Path |
|-----------|--------|------|
| CMP Tool Registry | ✅ Rich | `backend/core/cmp/registry.py` (489 lines, full categories) |
| CMP Service | ✅ Core | `backend/services/cmp_service.py` |
| CMP Tool Routes | ✅ Exists | `backend/routes/cmp_tools.py` |
| CMP Voting Routes | ✅ Exists | `backend/routes/cmp_voting.py` |
| CMP Voting HTML | ⚠️ Minimal | `frontend/templates/cmp_voting.html` (506 bytes) |
| CMP Orchestrator | ✅ Exists | `Core/cmp/cmp_orchestrator.py` |
| CMP Brain | ✅ Exists | `Core/cmp/cmp_brain.py` |
| Graph UI | ❌ Missing | No n8n-like node graph exists |

### 4. WebSocket/SSE & Event Bus
| Component | Status | Path |
|-----------|--------|------|
| Event Bus Service | ✅ Full | `backend/services/event_bus.py` (publishes to WebSocket) |
| WebSocket Routes | ✅ Full | `backend/routes/websocket.py` |
| WebSocket Manager | ✅ Exists | `backend/core/websocket_manager.py` |
| WebSocket Metrics | ✅ Exists | `backend/core/websocket_metrics.py` |
| WebSocket JS Client | ✅ Exists | `frontend/static/js/websocket-client.js` |
| WebSocket Enhanced | ✅ Exists | `frontend/static/js/websocket-enhanced.js` |
| SSE Fallback | ❌ Missing | No SSE fallback endpoint |

### 5. Capability Registry
| Component | Status | Path |
|-----------|--------|------|
| Tool Registry | ✅ Exists | `backend/tools/registry.py` |
| Model Registry | ✅ Exists | `backend/services/model_registry.py` |
| Integration Registry | ✅ Exists | `backend/services/integration_registry.py` |
| Sunflower Registry | ✅ Exists | `backend/utils/sunflower_registry.py` |
| Capabilities Endpoint | ❌ Missing | No `/capabilities` endpoint |
| Health/Keys Endpoint | ❌ Missing | No `/health/keys` status |

### 6. Connectors
| Component | Status | Path |
|-----------|--------|------|
| Connectors Directory | ✅ Exists | `connectors/` |
| Event Hooks | ✅ Exists | `connectors/event_hooks.py` |
| MCP Registry | ✅ Exists | `backend/services/mcp/mcp_registry.py` |
| Connections Route | ✅ Exists | `backend/routes/connections_route.py` |

### 7. RBAC/JWT
| Component | Status | Path |
|-----------|--------|------|
| JWT Service | ✅ Exists | `backend/services/jwt_service.py` |
| JWT Usage Guide | ✅ Docs | `docs/JWT_USAGE_GUIDE.md` |
| JWT Rotation Tests | ✅ Tests | `tests/test_jwt_rotation.py` |
| Full RBAC | ⚠️ Partial | Auth middleware exists but limited role enforcement |

### 8. Frontend Stack
| Component | Status | Details |
|-----------|--------|---------|
| Templates | ✅ 44 files | Jinja2 HTML templates |
| Static JS | ✅ 33 files | Vanilla JS with modules |
| Base Template | ✅ | `frontend/templates/base.html` |
| Real-time JS | ✅ | `realtime.js`, `sync-manager.js` |
| No React/Vue | ✅ | Pure HTML/JS/CSS stack |
| Dashboards | ✅ Multiple | dashboard.html, founder_panel.html, etc. |

---

## 🔴 Gaps to Address

### Part A: QA Guardian Extension
- [ ] Charter lacks explicit frontend patching rules
- [ ] Charter lacks Daena VP authority definition
- [ ] No unified "Guardian Control API" for Daena
- [ ] No approval workflow UI (diff preview, risk rating)
- [ ] No quarantine mode implementation

### Part B: Real-Time Sync
- [ ] No SSE fallback endpoint
- [ ] No command channel from frontend to backend
- [ ] Event schema validation tests missing
- [ ] QA Guardian events not integrated with event bus

### Part C: Capability Registry
- [ ] No `/capabilities` endpoint
- [ ] No `/health/keys` endpoint
- [ ] No "Control Center" panel

### Part D: CMP n8n-like Graph
- [ ] No node canvas UI
- [ ] No edge/connection visualization
- [ ] No graph persistence (nodes, edges)
- [ ] No graph execution engine
- [ ] No sample workflow template

### Part E: Wiring Audit
- [ ] No frontend-backend wiring audit command
- [ ] No automated route coverage check

---

## 🟢 Implementation Plan

### Phase 1: Extend QA Guardian Charter & Control API
1. Update `docs/QA_GUARDIAN_CHARTER.md` with frontend patching rules
2. Create `backend/qa_guardian/control_api.py` - Unified Guardian Control API
3. Create approval workflow API endpoints
4. Implement quarantine mode

### Phase 2: Real-Time Sync
1. Add SSE fallback endpoint
2. Add command channel to WebSocket
3. Integrate QA Guardian with event bus
4. Add event schema validation

### Phase 3: Capability Registry
1. Create `/capabilities` endpoint
2. Create `/health/keys` endpoint
3. Create Control Center UI

### Phase 4: CMP Node Graph
1. Create CMP Graph database models
2. Create CMP Graph API routes
3. Create n8n-like canvas UI
4. Wire execution to CMP service
5. Add sample template

### Phase 5: Wiring Audit
1. Create wiring audit command
2. Add frontend-backend coverage check

---

## 📁 Files to Create/Modify

### New Files
| Path | Purpose |
|------|---------|
| `backend/qa_guardian/control_api.py` | Unified Guardian Control API |
| `backend/routes/capabilities.py` | Capabilities and health endpoints |
| `backend/routes/sse.py` | SSE fallback endpoint |
| `backend/qa_guardian/quarantine.py` | Quarantine mode |
| `backend/routes/cmp_graph.py` | CMP graph CRUD and execution |
| `backend/database_cmp_graph.py` | CMP graph database models |
| `frontend/templates/cmp_canvas.html` | n8n-like node graph UI |
| `frontend/static/js/cmp-canvas.js` | Canvas interaction logic |
| `frontend/templates/approval_workflow.html` | Founder approval UI |
| `frontend/templates/control_center.html` | Capabilities control center |

### Modified Files
| Path | Changes |
|------|---------|
| `docs/QA_GUARDIAN_CHARTER.md` | Add frontend patching, Daena authority, enhanced deny-list |
| `backend/qa_guardian/guardian_loop.py` | Integrate with event bus |
| `backend/services/event_bus.py` | Add QA Guardian event types |
| `backend/database.py` | Add CMP graph models |
| `backend/main.py` | Register new routes |

---

*Scan completed. Ready to proceed with implementation.*
