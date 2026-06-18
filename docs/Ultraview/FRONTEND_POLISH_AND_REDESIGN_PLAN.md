# Frontend Polish and Redesign Plan

Date: 2026-04-29

Goal: Daena should feel like a founder control center, not a collection of demo cards.

## Design Rules

- Show live data or an honest empty/error state.
- Every action button must have a handler, backend route, loading state, error state, and audit/approval policy when relevant.
- Avoid fake metrics and fake runtime/connector status.
- Prefer dense operational screens over marketing hero layouts.
- Surface approvals, background work, and connector failures in the shell.

## Required Pages

| Page | Current status | Next design action |
|---|---|---|
| Founder Command Center | Dashboard exists, needs stronger operating summary. | Merge health, approvals, tasks, pipeline, runtime risk. |
| Daena Chat / VP Console | Working route and stream. | Add demo workflow launcher and visible model/tool trace. |
| Agent Departments | Exists. | Add actual department task status and latest outputs. |
| Task Queue | Exists via Tasks/Workstreams/Heartbeat. | Clarify queue ownership. |
| Approval Queue | Exists with SSE. | Make external-action risk obvious. |
| Audit Logs | Exists. | Add filters by action level/model/connector. |
| Model / Runtime Router | Exists in Connections/settings. | Add one consolidated status table. |
| MCP and Connectors | Exists, repaired persistence truth. | Move browse catalog to backend. |
| Skills Registry | Exists. | Add trust/source labels. |
| Memory / RAG / Obsidian | Partial. | Add honest status endpoints and panels. |
| Sales Pipeline | Pipeline and sales endpoints exist. | Build one guided lead/outreach draft workflow. |
| Investor / Grants Pipeline | Mostly docs. | Build tracker API after demo workflow. |
| Cybersecurity Authorized Workflows | Exists partially. | Keep authorization scope front-and-center. |
| Customer Support / Delivery | Department/project routes exist. | Add workflow templates later. |
| System Health | Exists in health routes. | Add single founder-readable status card. |
| Settings | Exists. | Keep advanced settings grouped and searchable. |

## P0/P1 Frontend Work Completed

- MCP install UI now reports backend persistence failures.
- Header exposes backend/API failures via global status indicator.
- Runtime selection no longer relies on fake fallback data.

## Next UI Work

1. Create a "Demo: find customer and draft outreach" guided panel.
2. Add RAG/Obsidian status card with honest not-connected states.
3. Consolidate Connections monolith into `pages\connections\*` components.
4. Add a visible "requires founder approval" badge on all external send/submit actions.

