# Realtime Sync Repair Plan

Date: 2026-04-29

## Current Realtime Map

| Domain | Mechanism | Endpoint/hook | Status |
|---|---|---|---|
| Chat stream | HTTP streaming | `/api/v1/chat/*/messages/stream` | working, needs live validation |
| Governance approvals | SSE | `/api/v1/governance/approvals/events`, `useApprovalsStream` | working, needs live validation |
| Cron heartbeat | SSE | `/api/v1/heartbeat/cron/events` | working, API singleton repaired |
| Autopilot/background queue | SSE | `/api/v1/autopilot/queue/events` | working, needs live validation |
| Pipeline | SSE | `/api/v1/pipeline/events` | working, needs live validation |
| Security scans | SSE | `/api/v1/security-dashboard/scans/{job_id}/events` | likely working |
| Runtime status | polling | `useRuntimeRegistry` | working |
| Connector/MCP status | polling | Connections page fetches registry/extensions | partial |
| WebSocket | legacy infra | `core\websocket.py`, old `ws.py` removed | retained infra, no primary UI route |

## Fix Completed

- `/api/v1/heartbeat/cron` now uses the same scheduler singleton that lifespan starts, so the UI does not read a different in-memory scheduler from the one executing jobs.

## Recommended Next Repairs

1. Add a unified `useRealtimeStatus` hook that reports connected/reconnecting/stale/error.
2. Add fallback polling for every SSE stream.
3. Add "stale" timestamps to approval, cron, queue, and runtime panels.
4. Expose persisted MCP rows plus live bootstrap state in one endpoint.
5. Remove or document unused WebSocket references so the team does not build against dead infra.

