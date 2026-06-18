# What Was Rebuilt

Date: 2026-04-30

## Runtime & Connections Center

`frontend/src/pages/ConnectionsPage.tsx` was rebuilt around `/api/v1/runtime/truth`.

Tabs now map to:

- Overview
- AI Runtimes
- MCP Servers
- Plugins / Skills
- API Providers
- Local Models
- Import Sources
- Health Events

Rows show detected/configured/persisted/reachable/callable/authenticated state separately and expose Refresh, Import, Test, Configure, Disable, and Remove actions.

## Backend Runtime Truth

`backend/app/services/runtime_truth_registry.py` and `backend/app/api/v1/runtime.py` were added to provide durable runtime truth state and events.
