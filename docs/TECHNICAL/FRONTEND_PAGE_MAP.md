# Frontend Page-by-Page Map

**Last Updated**: 2025-01-XX  
**Source**: Actual code analysis

---

## Page Inventory

### 1. Command Center (`/command-center`)
- **File**: `frontend/templates/daena_command_center.html`
- **API Endpoints**:
  - Initial: `/api/v1/registry/summary` (8×6 structure)
  - Real-time: `/api/v1/events/stream` (SSE)
- **WebSocket/SSE Topics**:
  - `registry_summary` - 8×6 structure (`daena_command_center.html:441`)
  - `council_health` - Council validation (`daena_command_center.html:458`)
  - `council_status` - Council phase (`daena_command_center.html:467`)
  - `system_metrics` - System-wide metrics (`daena_command_center.html:479`)
- **Displayed Numbers**:
  - Total Agents: `stats.totalAgents` (must be 48)
  - Active Agents: `stats.activeAgents` (must be 48)
  - Departments: `departments.length` (must be 8)
  - Council Phase: `councilStatus.current_phase`
- **Source of Truth**: `/api/v1/registry/summary` (initial), SSE events (updates)

### 2. Dashboard (`/` or `/dashboard`)
- **File**: `frontend/templates/dashboard.html`
- **API Endpoints**:
  - Initial: `/api/v1/registry/summary`
  - Real-time: `/api/v1/events/stream` (SSE)
- **WebSocket/SSE Topics**:
  - `system_metrics` - System-wide metrics
  - `council_health` - Council validation
- **Displayed Numbers**:
  - Agent counts (from registry summary)
  - Department counts (from registry summary)
- **Source of Truth**: `/api/v1/registry/summary` (initial), SSE events (updates)

### 3. Enhanced Dashboard (`/enhanced-dashboard`)
- **File**: `frontend/templates/enhanced_dashboard.html`
- **API Endpoints**:
  - Initial: `/api/v1/registry/summary`
  - Real-time: `/api/v1/events/stream` (SSE)
- **WebSocket/SSE Topics**:
  - `system_metrics` - System-wide metrics
  - `council_health` - Council validation
  - `sec_loop_status` - SEC-Loop metrics (if SEC-Loop panel present)
- **Displayed Numbers**:
  - Agent counts (from registry summary)
  - Department counts (from registry summary)
  - SEC-Loop metrics (if panel present)
- **Source of Truth**: `/api/v1/registry/summary` (initial), SSE events (updates)

### 4. Daena Office (`/daena-office`)
- **File**: `frontend/templates/daena_office.html`
- **API Endpoints**:
  - Initial: `/api/v1/registry/summary`
  - Real-time: `/api/v1/events/stream` (SSE)
- **WebSocket/SSE Topics**:
  - `system_metrics` - System-wide metrics
  - `council_health` - Council validation
- **Displayed Numbers**:
  - Agent counts (from registry summary)
  - Department counts (from registry summary)
- **Source of Truth**: `/api/v1/registry/summary` (initial), SSE events (updates)

### 5. Analytics (`/analytics`)
- **File**: `frontend/templates/analytics.html`
- **API Endpoints**:
  - Initial: `/api/v1/monitoring/metrics`
  - Real-time: `/api/v1/events/stream` (SSE)
- **WebSocket/SSE Topics**:
  - `system_metrics` - System-wide metrics
- **Displayed Numbers**:
  - CPU/Memory/Disk usage
  - NBMF metrics (encode/decode latency)
  - Council decision latency
- **Source of Truth**: `/api/v1/monitoring/metrics` (initial), SSE events (updates)

### 6. Projects (`/projects`)
- **File**: Not found (may not exist)
- **Status**: TODO - Verify if this page exists

### 7. External (`/external`)
- **File**: Not found (may not exist)
- **Status**: TODO - Verify if this page exists

### 8. Customer Service (`/customer-service`)
- **File**: Not found (may not exist)
- **Status**: TODO - Verify if this page exists

---

## Standardized Metrics Summary Endpoint

**New Endpoint**: `/api/v1/monitoring/metrics/summary`
- **File**: `backend/routes/monitoring.py:93-180`
- **Returns**: Authoritative counts for all dashboards
- **Fields**:
  - `agents.total` - Total agents (must be 48)
  - `agents.active` - Active agents
  - `departments.total` - Total departments (must be 8)
  - `departments.active` - Active departments
  - `structure.valid` - Structure validation (8×6)
  - `council.rounds` - Total council rounds
  - `tasks.completed` - Completed tasks
  - `tasks.failed` - Failed tasks
  - `errors` - Error count
  - `heartbeat.status` - Live state (live/degraded/stale)

---

## Live-State Badge Implementation

**Status**: 🟢 live / 🟡 degraded / 🔴 stale

**Logic**:
- 🟢 live: Heartbeat age < 10 seconds
- 🟡 degraded: Heartbeat age 10-30 seconds
- 🔴 stale: Heartbeat age > 30 seconds

**Implementation**:
- Backend: `backend/services/realtime_metrics_stream.py:147-152` (heartbeat status)
- Frontend: TODO - Add badge component to all dashboards

---

## E2E Tests

**File**: `tests/e2e/test_council_structure.py:1-152`
- Tests dashboard shows correct counts (8 departments, 48 agents)
- Tests council health endpoint integration
- Tests real-time updates
- **Requires**: `playwright` module (install: `pip install playwright && playwright install`)

---

## Next Steps

1. ✅ Create `/api/v1/monitoring/metrics/summary` endpoint
2. ⏳ Add live-state badge to all dashboards
3. ⏳ Update all pages to use `/metrics/summary` as source of truth
4. ⏳ Complete E2E tests (install playwright)

