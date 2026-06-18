# Duplicates, Dead Files, and Unwired Report

Date: 2026-04-29

No files were deleted or archived in this pass.

## High-Confidence Findings

| Path | Type | Evidence | Confidence | Recommended action | Risk if touched |
|---|---|---|---|---|---|
| `D:\Ideas\Daena_old_upgrade_20251213` | legacy/missing | Listed in older memory, not present on disk during audit. | high | Treat as legacy reference only unless user restores it. | Copying from it could fork the product. |
| `D:\Ideas\Daena\Doc\v1-docs` | legacy docs | Old v1 docs, archive folders, duplicate README families. | high | Keep read-only; archive index later. | May contain patent/business history, do not delete. |
| `D:\Ideas\Daena\landing` | separate site/remnant | Standalone landing folder outside active Vite frontend. | medium | Audit before archiving. | Could still feed marketing/deploy docs. |
| `D:\Ideas\Daena\agent-harness` | unclear/legacy harness | Separate harness tree outside active backend/frontend. | medium | Keep until owner confirms. | May contain useful CLI agent experiments. |
| `D:\Ideas\Daena\backend\app\api\v1\ws.py` | removed/dead route | Deleted in current worktree; `__init__.py` notes old placeholder route removal. | high | Keep deleted if tests pass. | Re-adding can confuse SSE/WebSocket model. |
| `D:\Ideas\Daena\frontend\src\pages\DaenaBotPage.tsx` | removed/dead page | Deleted in current worktree; `/daenabot` redirects to `/chat`. | high | Keep deleted if build passes. | Re-adding duplicates chat surface. |
| `D:\Ideas\Daena\frontend\src\pages\FounderPage.tsx` | removed/dead page | Deleted in current worktree; `/founder` redirects to settings/governance. | high | Keep deleted if build passes. | Re-adding duplicates governance/settings. |
| `D:\Ideas\Daena\backend\app\api\v1\laevateinn.py` | placeholder | Comment says placeholder until fully wired. | medium | Mark UI as experimental or wire response to full pipeline. | Could overstate cognitive system readiness. |
| `D:\Ideas\Daena\backend\app\services\laevateinn\tool_augmented.py` | stub | Multiple `web_search_stub` references. | high | Replace with approved research provider or label as offline verification. | Fake research evidence in strategic mode. |
| `D:\Ideas\Daena\frontend\src\pages\ConnectionsPage.tsx` | mixed old/new file | New componentized `frontend\src\pages\connections\*` files exist, but old monolith still active. | medium | Finish split after tests pass. | Touching too much can break connectors UX. |
| `D:\Ideas\Daena\backend\testssl.sh` | vendored security tool | Large third-party tree under backend. | medium | Keep but document ownership. | Security workflow may rely on it. |
| `D:\Ideas\Daena\venv_daena` and `venv_daena_main_py310` | local environment duplicates | Multiple historical virtual envs plus active `backend\.venv`. | high | Do not delete in this pass; later archive old envs after confirming launch path. | Deleting wrong venv can break local launch. |

## Static Catalog Findings

- `frontend\src\pages\connections\*` is a newer modular connections surface, while `ConnectionsPage.tsx` remains a large active page. This is technical debt, not proof of breakage.
- The browse marketplace still contains static extension/connector browse arrays in the frontend. The main connector catalog is DB-sourced, but browse modal entries are not fully DB-sourced yet.
- `backend\app\services\heartbeat\work_queue.py` is separate from the newer `autopilot\background_queue.py`. It may be intentional for heartbeat tasks, but should be documented to avoid two task-queue mental models.
- `.archive` already exists; future archive operations should move files there with timestamps and never delete permanently.

## Do Not Touch Without Approval

- `D:\Ideas\Daena\Doc\*` old docs and patent folders.
- `D:\Ideas\Daena\.secrets`, `.env`, `.env.production`, and any live credential files.
- `D:\Ideas\Daena\backend\testssl.sh` security tooling.
- Any Cloud Run/deployment config.

