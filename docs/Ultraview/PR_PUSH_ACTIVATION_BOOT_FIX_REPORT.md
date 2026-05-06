# PR-0: Push Activation Boot Fix — Report

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE
**Commit pushed:** `a852c03` (fast-forward, no force, no deploy)
**Range:** `5ca8fdb..a852c03 master -> master`
**Author:** Daena VP (Claude Opus 4.7) under Auto mode

## What this PR does

Pushes the local boot-fix commit that was held back during the Live Activation
Run-01. Nothing else. No deploy. No working-tree changes. No new code.

## Boot fix recap (commit `a852c03`)

`backend/app/main.py` line 805 used the dotted-import form

```python
import app.services.controlled_execution_handlers
```

inside the `lifespan(app: FastAPI)` async context manager. Python's dotted-import
form binds the *top-level* package name (`app`) into the function's local scope,
which silently shadows the lifespan parameter `app: FastAPI`. The shadow only
matters when later code reads `app.state.daena_kek = _kek` (line 832), so it
never tripped pytest fixtures (which never go through lifespan), only real
`uvicorn` boots.

Replaced with the from-import form so only the leaf name is bound:

```python
from app.services import controlled_execution_handlers  # noqa: F401
```

Comment block above the import documents the trap so future-me (and any future
side-effect import) does not re-introduce it.

## Verification

| Check                                        | Result                       |
|----------------------------------------------|------------------------------|
| `git fetch origin`                           | clean                        |
| Local master `a852c03` ahead of origin       | yes (1 commit)               |
| `git push origin master`                     | fast-forward, no force       |
| Push response                                | `5ca8fdb..a852c03  master -> master` |
| `curl -s http://127.0.0.1:8000/api/v1/health`| `status: healthy`            |
| Backend still running, lifespan completed    | yes                          |

## Hard rules respected

- [x] No deploy
- [x] No force push
- [x] No secrets read/printed/committed
- [x] Working tree unrelated drift left untouched (not staged, not committed)
- [x] No new architecture
- [x] No fake success — push response captured verbatim above

## Next

PR-1: Full UI route and button inventory.
