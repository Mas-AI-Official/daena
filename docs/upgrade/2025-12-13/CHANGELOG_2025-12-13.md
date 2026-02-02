## CHANGELOG (2025-12-13)

### Backend
- Fixed broken endpoint: `backend/routes/departments.py` (`/api/v1/departments`)
- Unified brain facade: `backend/daena_brain.py` now delegates to `backend/services/llm_service.py` (local-first, no hard cloud imports)
- Added Operator/Automation:
  - `backend/services/automation_service.py`
  - `backend/routes/automation.py`
  - `backend/services/cmp_tool_registry.py`
  - `backend/routes/cmp_tools.py`
  - Router registration in `backend/main.py`

### Frontend
- Removed unnecessary API key headers in templates (no-auth mode):
  - `frontend/templates/dashboard.html`
  - `frontend/templates/enhanced_dashboard.html`
  - `frontend/templates/daena_command_center.html`
  - `frontend/templates/analytics.html`
  - `frontend/templates/council_rounds_panel.html`
- Added Operator panel inside `frontend/templates/dashboard.html` (no new pages)

### Tests
- Added no-auth API coverage in sanity tests:
  - `/api/v1/agents` returns non-empty
  - `/api/v1/departments` returns 8+ depts











