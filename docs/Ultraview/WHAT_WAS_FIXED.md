# What Was Fixed

Date: 2026-04-30

- Added durable JSON runtime truth store at `backend/var/runtime_truth_registry.json`.
- Added runtime truth endpoints under `/api/v1/runtime`.
- Registered runtime router in `backend/app/api/v1/__init__.py`.
- Fixed provider lifecycle labels so configured API keys are `configured_untested`.
- Fixed generic no-safe-test path so it does not mark provider tests as real health failures.
- Fixed Daena MCP package persistence default.
- Fixed Connections row Refresh to call health-check instead of reusing Test.
- Disabled Test for API providers with no safe zero-cost test.
- Reduced Connections layout density.
- Removed unused `Database` import from Connections page.
- Changed header status wording from `AGI ACTIVE/OFF` to `AUTOPILOT ON/OFF`.
- Reduced Security Ops cold-load timeout to 10 seconds and added explicit backend failure copy.
