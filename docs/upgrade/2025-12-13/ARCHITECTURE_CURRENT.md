## ARCHITECTURE_CURRENT (2025-12-13)

### Runtime stack
- **Backend**: FastAPI (`backend/main.py`)
- **Frontend**: HTML + HTMX + Alpine (templates under `frontend/templates/`)
- **Database**: SQLite `daena.db` (local dev default)

### No-Auth local mode (required)
- Config: `DISABLE_AUTH=1` (default in this upgrade)
- Behavior:
  - `/` redirects to `/ui/dashboard`
  - `/ui/*` works without login
  - **All `/api/*` works without tokens/keys**
  - `get_current_user()` returns a **Dev Founder**

### Daena “brain” central path
Daena responses come from the canonical service layer:
- **Primary LLM path**: `backend/services/llm_service.py`
  - Local-first (Ollama when available)
  - Cloud providers are optional and disabled by default
- **Daena chat API**: `backend/routes/daena.py` (`POST /api/v1/daena/chat`)
  - Uses the LLMService (and can run CMP tools for scrape intent)
- **Brain facade**: `backend/daena_brain.py`
  - Now delegates to `LLMService` (no hard cloud imports)

### Agents / topology
- Canonical structure: **8 departments × 6 agents = 48** (`backend/config/council_config.py`)
- Registry: `backend/utils/sunflower_registry.py`
  - Populated from DB at startup / seeding

### Message bus (why there are two)
- `backend/utils/message_bus.py`: neighbor-first routing + CMP fallback (used by honeycomb routing/health)
- `backend/utils/message_bus_v2.py`: topic-based pub/sub (used by council presence/rounds)
These are **different responsibilities**, so we did **not** merge them into a single file.

### Memory layers (NBMF / EDNA)
- NBMF stores exist under `.l1_store/ .l2_store/ .l3_store/` (local)
- Enterprise-DNA API: `backend/routes/enterprise_dna.py`
  - Default tenant is seeded so UI does not show `not_configured`

### Operator / Automation (added cleanly)
- Service: `backend/services/automation_service.py`
- API: `backend/routes/automation.py`
- Canonical tool runner:
  - `backend/tools/registry.py` (single tool registry)
  - `backend/tools/policies.py` (allowlist/rate-limit/redaction)
  - `backend/tools/audit_log.py` (JSONL audit log)
  - `backend/routes/tools.py` (`POST /api/v1/tools/execute`)
- CMP compatibility endpoint: `backend/routes/cmp_tools.py` (delegates to canonical tool runner)
- UI: Operator panel is inside `frontend/templates/dashboard.html`


