# Frontend Performance Report

Date: 2026-04-30

## Founder Symptom

Page switching felt like 4-5 seconds. That is not acceptable for an already-loaded local app.

## Evidence

- Old Connections page combined runtime providers, MCP servers, plugins, extensions, import flows, marketplace cards, and modal state into one route.
- Security Ops cold-load could wait up to the global 30-second Axios timeout when backend was unavailable.
- Runtime/provider/MCP pages were using split status endpoints, which encourages repeated scans and repeated failed probes.

## Patches Applied

- Rebuilt `/connections` into a Runtime & Connections Center backed by `/runtime/truth`.
- Added a short-lived durable backend registry so the frontend does not need to run full discovery on every route transition.
- Security Ops request timeout reduced to 10 seconds with explicit error state.
- Header wording fixed so autopilot state does not imply backend health.

## Current Measured Verification

- Vite served transformed `/src/pages/ConnectionsPage.tsx` successfully.
- Vite served transformed `/src/pages/SecurityDashboardPage.tsx` successfully.
- Runtime page frontend module contains the new refresh/untested logic and no stale `Database` import.

## Blocked Measurements

Backend-dependent page switch timing cannot be measured honestly while backend is down. The target remains:

- under 500 ms for already-loaded frontend-only page switches;
- under 1.5 s for backend data pages with backend online;
- never 4-5 seconds unless an explicit backend action is running.

## Next Repair

- Add route-level dev timing logs.
- Cache runtime truth for a short TTL.
- Avoid full provider scans on route mount.
- Cancel stale requests on route change.
