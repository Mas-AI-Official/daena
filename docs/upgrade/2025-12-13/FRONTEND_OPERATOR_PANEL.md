## Frontend Operator Panel (2025-12-13)

### Goal
Provide a Manus-style Operator panel **inside** `/ui/dashboard` (no new pages).

### Where it is implemented
- UI: `frontend/templates/dashboard.html`
- Backend API: `backend/routes/automation.py`
- Live updates: SSE via `backend/routes/events.py` (`automation_process_update`)

### UX flow
- Click **Operator** in dashboard header
- Panel opens with:
  - left: process history (tabs)
  - right: create new process (currently: scrape URL)
  - timeline: per-step logs + outputs
  - cancel: stop a running process

### Why it’s implemented as an internal panel
Many pages include heavy inline initialization JS; full HTMX SPA-style swapping can be brittle.
Internal panels give the “app-like” Manus feeling while staying stable and debuggable.











