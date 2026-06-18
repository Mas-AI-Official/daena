# Security and Governance Audit

Date: 2026-04-29

## Guardrails Confirmed

- Auth routes and JWT flows exist.
- Role guards are used in multiple admin/founder routes.
- Approval queue exists and has SSE.
- Audit routes exist.
- PII guard and policy compiler files are present in current worktree.
- Security authorized scope routes exist.
- Security dashboard routes include scan start/status/report/events.
- Connector permissions exist per instance/tool and persist in user settings.

## Fixes Made

- MCP install/uninstall now reflects persistence truth to the UI.
- MCP install/uninstall now uses tenant-scoped DB persistence, not only Claude config.
- Heartbeat cron API now reads the active process scheduler.

## Risks

| Risk | Evidence | Priority | Action |
|---|---|---|---|
| Secrets in local env files | `.env`, `.env.production`, `.secrets` exist. Values were not printed. | P0 operational | Keep out of docs/git; run secret scan before commit. |
| External send path in Company Mode | `company_mode.py` has draft send route semantics. | P0 product | Ensure approval gate before any real send. |
| Security scan misuse | Security tools and scan routes exist. | P0 product | Require authorized scope and documented authorization. |
| Placeholder cognitive web search | `tool_augmented.py` has web search stubs. | P1 truth | Label as offline/stub or wire approved research. |
| CORS/auth not live-tested | Environment prevented launch. | P1 validation | Re-run launch once OS crypto/socket issue is fixed. |
| Static browse catalog | Frontend browse modal contains hardcoded marketplace entries. | P2 | Move to backend catalog. |

## Required Policy Statements

- Outreach: Daena may draft messages, but sending requires founder approval and CASL-safe identity/unsubscribe handling where applicable.
- Investor/grant submissions: Daena may draft and package, but submission requires founder approval.
- Security: Daena may only scan owned or explicitly authorized targets.
- Connectors: installed does not mean authenticated; UI must show connected/authenticated/live separately.

