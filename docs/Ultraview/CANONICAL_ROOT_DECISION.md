# Canonical Root Decision

Date: 2026-04-29

Decision: `D:\Ideas\Daena` is the active canonical Daena root.

## Evidence

| Check | Result |
|---|---|
| Knowledge graph | `codebase-memory` lists `D-Ideas-Daena` rooted at `D:\Ideas\Daena` with 12,325 nodes and 48,117 edges. |
| Candidate root | `D:\Ideas\Daena` exists and contains `.git`, `backend`, `frontend`, `docs`, launch scripts, package files, and active databases. |
| Legacy root | `D:\Ideas\Daena_old_upgrade_20251213` was not present during this run and was not touched. |
| Git status | `D:\Ideas\Daena` is on `master...origin/master` and ahead by 19 commits with many existing dirty files. |
| Backend config | `D:\Ideas\Daena\backend\.daena-port` exists and contains `8000`. |
| Frontend config | `D:\Ideas\Daena\frontend\vite.config.ts` reads `..\backend\.daena-port` and proxies API traffic to that backend port. |
| Launch files | `start-daena.bat`, `start-daena.sh`, `backend\run.py`, and `frontend\package.json` all point inside `D:\Ideas\Daena`. |

## Dirty Worktree Warning

The root is correct, but the tree is not clean. Existing modified and untracked files span backend, frontend, docs, packages, skills, and generated graph metadata. I am treating those as prior user/session work and will not revert them.

## Decision

Patch only `D:\Ideas\Daena` for this task. Do not copy from or write to a legacy root unless Masoud explicitly asks for a compare or migration.
