# DAENA — Control Plane Integration Guide

## What This Update Does

Replaces the fragmented frontend (10+ stub pages) with ONE unified Control Plane.
Adds a chat→governance pipeline so typing in Daena Office triggers the full
Think → Plan → Act → Report loop with real-time visibility.

---

## File Drop Locations

| Delivered File | Drop To | Action |
|---|---|---|
| `control_plane_v2.html` | `frontend/templates/control_plane_v2.html` | **REPLACE** existing file |
| `sidebar.html` | `frontend/templates/partials/sidebar.html` | **REPLACE** existing file |
| `ui.py` | `backend/routes/ui.py` | **REPLACE** existing file |
| `chat.py` | `backend/routes/chat.py` | **NEW FILE** (create) |

---

## main.py Changes

Find where routers are registered (look for `include_router` calls).
Add the chat router if not already present:

```python
# Add this import near the top with other route imports:
from backend.routes.chat import router as chat_router

# Add this with the other include_router calls:
app.include_router(chat_router)
```

**Verify these routers are already registered** (from previous sessions):
```python
# These should already exist — confirm, don't duplicate:
from backend.routes.skills import router as skills_router
from backend.routes.packages import router as package_audit_router  # or packages
from backend.routes.governance import router as governance_router
from backend.routes.ui import router as ui_router
from backend.routes.defi import router as defi_router
from backend.routes.integrity import router as integrity_router
from backend.routes.research import router as research_router
from backend.routes.shadow import router as shadow_router
from backend.routes.capabilities import router as capabilities_router
```

If any are missing, add them. The chat router is the only guaranteed new one.

---

## Sidebar Integration

The new `sidebar.html` is a standalone `<nav>` block.
If your `base.html` or page templates include the sidebar via Jinja2:

```html
{% include 'partials/sidebar.html' %}
```

It will pick up the new version automatically after you replace the file.

If `control_plane_v2.html` is served as a **standalone page** (not inside a base template),
it already has its own built-in sidebar — no extra inclusion needed.

The `daena_office.html` page should include the sidebar partial so both pages
share the same navigation. If it doesn't currently, add:

```html
<div style="display:flex;height:100vh">
  {% include 'partials/sidebar.html' %}
  <div style="flex:1">
    <!-- existing daena_office content -->
  </div>
</div>
```

---

## Verification

After dropping files and updating main.py:

```bash
# 1. Verify imports compile
python -c "from backend.routes.chat import router; print('✅ chat.py OK')"
python -c "from backend.routes.ui import router; print('✅ ui.py OK')"

# 2. Start backend
python -m backend.main

# 3. Test routes
curl http://127.0.0.1:8000/ui/control-plane      # Should return HTML (200)
curl http://127.0.0.1:8000/ui/daena-office        # Should return HTML (200)
curl http://127.0.0.1:8000/api/v1/chat            # POST endpoint exists

# 4. Test legacy redirects (should 307 → /ui/control-plane)
curl -I http://127.0.0.1:8000/ui/skills           # 307 → /ui/control-plane#skills
curl -I http://127.0.0.1:8000/ui/system-monitor   # 307 → /ui/control-plane#agents

# 5. Test chat pipeline
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"research blockchain security trends"}'
# Should return pipeline_id, stages, and governance_status

# 6. Test autopilot toggle
curl -X POST http://127.0.0.1:8000/api/v1/governance/toggle-autopilot \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
# Then send a chat message — should show governance_status: "pending"
```

---

## What Was Removed / Why

| Removed | Reason |
|---|---|
| Integrations / App Setup page | Was a Moltbot stub — functionality doesn't exist |
| Skills (standalone page) | Lives in Control Plane → Skills tab |
| Execution (standalone page) | Lives in Control Plane → Governance tab |
| Proactive (standalone page) | Lives in Control Plane → Governance tab |
| Tasks & Runbook pages | Lives in Control Plane → Agents tab |
| Approvals (standalone page) | Lives in Control Plane → Governance tab |
| Provider Onboarding | Was a stub — no backend support |
| System Monitor (standalone) | Merged into Agents tab stats |
| Analytics page | Merged into Agents tab |

All legacy URLs redirect to the correct Control Plane tab — nothing 404s.

---

## Architecture Summary

```
Browser
  │
  ├── /ui/control-plane  →  control_plane_v2.html
  │     ├── Tab: Brain        → GET /api/v1/memory/stats, /api/v1/research/*
  │     ├── Tab: DeFi/Web3    → POST /api/v1/defi/scan, GET /api/v1/defi/*
  │     ├── Tab: Skills       → GET /api/v1/skills, POST /api/v1/skills/create
  │     ├── Tab: Packages     → GET /api/v1/packages/records, POST /request-install
  │     ├── Tab: Governance   → GET /api/v1/governance/*, toggle-autopilot
  │     ├── Tab: Council      → GET /api/v1/council/debates
  │     ├── Tab: Trust        → GET /api/v1/integrity/*, POST /verify
  │     ├── Tab: Shadow       → GET /api/v1/shadow/*
  │     ├── Tab: Treasury     → (blockchain routes, pending deploy)
  │     ├── Tab: Agents       → WebSocket /ws/events live feed
  │     └── AGI Autopilot     → POST /api/v1/governance/toggle-autopilot
  │
  ├── /ui/daena-office    →  daena_office.html
  │     └── Chat box       → POST /api/v1/chat  ← THINK→PLAN→ACT pipeline
  │
  └── WebSocket /ws/events  →  Real-time event feed (all tabs)
```
