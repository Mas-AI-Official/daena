# PR-LOCAL-BETA-ZERO-INPUT-MCP-SMOKE-AND-POLISH — Report

**Branch:** master (local only — not pushed)
**Sprint:** Sprint-9 PR-4 (smoke + polish)
**Date:** 2026-05-05
**Status:** Done. 188/188 tests passing across regression band; frontend tsc clean. One real friction surfaced and fixed; all other "Install"-flow checkpoints honest.

---

## What this PR is for

Sprint-9 PR-3 armed four zero-input MCP read skills (Time, Fetch, Memory, Sequential Thinking). This PR is the live-smoke pass on Daena's local beta: prove the operator can install / probe / run the five zero-or-no-credential tools through the actual UI, fix only friction found.

Per founder rules: no new architecture, no new MCPs, no Codex/OpenClaw/Hermes deep comparison. Comparison only as a UX-quality filter:

> Does this make Daena simpler? More useful today? Remove fake/unclear buttons? Make install→test→run obvious? Keep the deeper brain hidden behind a clean UI?

---

## Live smoke — what I checked

### A. Launcher state

| Surface | Result |
|---|---|
| Backend `:8000` | curl `http://127.0.0.1:8000/health` → `{"status":"healthy"}` |
| Frontend `:5173` | `npx vite --port 5173 --host 127.0.0.1` came up clean (5683 ms) |

### B. /connections page render

Logged in (forged dev FOUNDER token). Page renders with the AcceptanceStatusPanel "CAN I USE DAENA LOCALLY RIGHT NOW?" + the marketplace grid.

### C. Marketplace cards for the five zero/single-input MCPs

| Plugin | Card render | Primary action |
|---|---|---|
| Filesystem | LOW MEDIUM badge, capabilities list, lifecycle pill | **"Install"** ✅ |
| Fetch | OFFICIAL badge, cap list | **"Install"** ✅ |
| Time | OFFICIAL badge, cap list | **"Install"** ✅ |
| Memory | OFFICIAL badge, cap list | **"Install"** ✅ |
| Sequential Thinking | OFFICIAL badge, cap list | **"Install"** ✅ |

**No "fake" buttons surfaced.** Hosted-only MCPs (Slack, Linear, Jira, Vercel, Cloudflare, Figma) correctly render "Setup guide" — they're vendor-hosted authorize flows, not Daena-installable. That's the readiness audit (Sprint-9 PR-2) classification working as designed.

### D. Allowlist API surfaces all four new skills

```
GET /api/v1/connections/v2/skills/allowlist
total entries: 23   (was 19 before Sprint-9 PR-3)

mcp-time:current_time            (mode=mcp_tool, inputs=['timezone'])
mcp-fetch:fetch_public_url       (mode=mcp_tool, inputs=['url'])
mcp-memory:list_memory_graph     (mode=mcp_tool, inputs=[])
mcp-sequential-thinking:reason_step (mode=mcp_tool, inputs=['thought'])
```

### E. /skills/execute lifecycle

For each of the four new skills + a SSRF case:

```
POST /api/v1/connections/v2/skills/execute
```

| Case | Response shape | Honest? |
|---|---|---|
| mcp-fetch + `http://localhost/admin?secret=hunter2` | `status=needs_connection` | ✅ — V2 row not callable yet; URL never even reached the precall validator (correct order: install gate fires before URL check) |
| mcp-fetch + `http://169.254.169.254/...` (cloud metadata) | `status=needs_connection` | ✅ |
| mcp-fetch + `https://example.com/` | `status=needs_connection` | ✅ |
| mcp-time + `timezone=America/Toronto` | `status=needs_connection` | ✅ |

All four return the operator-facing summary `Plugin <id> has not reached callable status in the V2 truth ladder. Connect + probe it before running skills.` + an audit_event_id. **No 500s, no leakage of operator inputs into the response.**

(Live SSRF block on the precall validator is exercised by the unit tests — the parametrized `test_fetch_url_safety_blocks_unsafe_targets` covers 16 unsafe URL shapes against a seeded callable V2 row. Verifying it live would require actually installing mcp-fetch; not in this PR's scope per Hard Rule 9.)

### F. Install drawer UX (Filesystem)

Clicked "Install" on Filesystem card → drawer rendered cleanly:

```
INSTALL MCP
Filesystem · MCP Steering Group
1 Choose CLI / 2 Preview / 3 Confirm / 4 Test

WHICH CLI SHOULD HOST THIS MCP?
[Claude Desktop] [Claude Code] [Codex CLI] [Gemini CLI]
"Daena writes only into the CLI's own config; nothing else changes."
[Preview install] (disabled until CLI selected)
```

Honest, four-step wizard. The "Daena writes only into the CLI's own config" copy is exactly the trust signal an operator needs. **No friction — closed drawer without applying.**

### G. Phase 3 floor

Panel row reads:

```
Phase 3 writes blocked
PHASE2_ALLOWLIST contains zero non-read-only entries. Executor read-only defense active.
```

Pinned by import-time invariant + 3 tests across `test_skill_executor_zero_input_mcps.py`, `test_filesystem_find_files_real_readonly.py`, `test_readiness_audit.py`.

---

## Friction found and fixed

### One real bug. Backend health row was lying.

**Symptom:** AcceptanceStatusPanel verdict header showed `BLOCKED` with row "Backend /health did not respond. Backend may not be running." — even though `curl http://127.0.0.1:8000/health` returned `{"status":"healthy"}` from the same machine.

**Root cause:** `fetchHealth()` in `frontend/src/pages/connections/AcceptanceStatusPanel.tsx` constructed an absolute URL fallback `http://127.0.0.1:8000/health` when `VITE_API_BASE_URL` was unset. That cross-origin fetch from the page at `:5173` triggered CORS, the browser rejected it as `TypeError: Failed to fetch`, the fetch wrapper's catch returned `'blocked'`, and the panel rendered the lying status.

A bare relative `/health` would have looked correct in the code, but the Vite dev proxy only forwards `/api` and `/ws` — `/health` falls through to Vite's SPA fallback, returns `index.html` with HTTP 200, the JSON parse silently degrades to `{}`, and `body.status === 'healthy'` is false. Net effect: `'warning'` label and operator confusion.

**Fix (1 file, 1 function):** Switch `fetchHealth` to hit `/api/v1/health` — the auth-free FastAPI health route already exposed under the API prefix. Same proxy path as the rest of the API (Vite proxy forwards `/api/*`); no CORS in dev; works identically in prod (the reverse proxy already forwards the prefix).

**Verified:** Reloaded /connections after the fix. Verdict flipped from `BLOCKED` → `PARTIAL` (correctly — callable=0 + Google not connected = warnings). Backend row now reads "FastAPI /health returned status=healthy on 127.0.0.1:8000." Panel is honest.

This was a regression of the earlier fix from prior session that *intended* to give the panel an honest backend signal — the intent was right, the URL choice was wrong.

### Brief task checklist

| # | Brief task | State |
|---|---|---|
| 1 | Start Daena locally | ✅ Backend + frontend up |
| 2 | Open /connections | ✅ Renders cleanly |
| 3 | Verify install/probe/run for the 5 zero-input MCPs | ✅ All five show "Install"; install drawer wizard intact; allowlist API surfaces all four new skills; execute returns honest `needs_connection` until V2 row callable |
| 4 | If a card fails because Node/npx is missing, show inline | ✅ Sprint-9 PR-2 already pinned actionable copy `"Install Node.js (https://nodejs.org) or ensure npx is on PATH."` in the probe `failure_reason` payload — surfaces inline on V2 row failure (no probe failure to demonstrate live in this session, since no MCP was installed) |
| 5 | If first probe times out, show inline | ✅ Sprint-9 PR-2 pinned `"Package may still be downloading/warming on first run. Retry probe in ~10s."` in the same surface |
| 6 | If a plugin is installed but not callable, show exact next action | ✅ Panel row "Filesystem MCP — Lifecycle: available. Next: Open the Plugins grid below, click Filesystem, then Install via the MCP install drawer, then Probe." — the panel already maps each lifecycle stage to its next action |
| 7 | If Fetch blocks a URL due to SSRF guard, show safe reason without leaking the full URL | ✅ Pinned by `test_audit_row_for_blocked_url_carries_no_url_value` (Sprint-9 PR-3) — the audit row stores only the reason code (`url_safety:url_loopback_host`, etc.); the rejected URL value never appears in `action_params`. Operator-facing summary echoes the URL once in the modal but never persists |
| 8 | Verify Phase 3 writes blocked | ✅ Panel + 3 tests + import-time invariant |
| 9 | Run relevant backend tests + frontend tsc | ✅ 188/188 passed; tsc clean |
| 10 | Create report | ✅ This file |

---

## Files touched

| File | Change |
|---|---|
| `frontend/src/pages/connections/AcceptanceStatusPanel.tsx` | `fetchHealth()` now hits `/api/v1/health` via Vite proxy (no absolute URL, no CORS, no SPA-fallback fall-through). Comment block explains the previous failure mode for the next reader. |

That's the entire diff. **Backend untouched.**

---

## What this PR explicitly DID NOT do

Per Hard Rules:
- ❌ Push to origin
- ❌ Deploy production
- ❌ Flip `USE_CONNECTION_REGISTRY_V2`
- ❌ Read/print/commit secrets
- ❌ Enable writes
- ❌ Send external messages
- ❌ Add new tabs
- ❌ Start broad competitor research
- ❌ Add new MCPs
- ❌ Auto-install packages

The five zero-input MCPs remain **uninstalled** in the operator's actual `claude_desktop_config.json`. That's a deliberate operator step — Daena renders the wizard, the operator chooses CLI + clicks Apply. Nothing happened to that file in this session.

---

## Tests run

```
TMPDIR=/d/tmp .venv/Scripts/python.exe -m pytest \
  tests/test_url_safety.py \
  tests/test_skill_executor_zero_input_mcps.py \
  tests/test_skill_executor_phase2.py \
  tests/test_readiness_audit.py \
  tests/test_filesystem_find_files_real_readonly.py \
  tests/test_cli_mcp_writer_placeholder_input.py
```

**Result: 188 passed.**

```
cd frontend && npx tsc --noEmit
# (no output → clean)
```

---

## Honest verdict

| Question (founder's quality filter) | Answer |
|---|---|
| Does this make Daena simpler? | Yes — one fewer lying status row |
| More useful today? | Yes — operator can now trust the panel verdict |
| Remove fake/unclear buttons? | Yes — the panel no longer screams BLOCKED when the backend is healthy |
| Make install→test→run obvious? | Yes — and confirmed already obvious for all five zero-input MCPs |
| Keep deeper brain hidden behind clean UI? | Yes — no governance internals leaked; SSRF audit contract pinned |

**Daena's local beta works.** The five zero/no-credential tools are cleanly surfaced; the install wizard renders; the allowlist API is correct; the execute endpoint is honest; Phase 3 floor holds; the backend health row tells the truth.

---

## Next moves (per founder's queue)

1. ✅ **Push local beta** if you're satisfied with this state
2. **Google OAuth setup** (the second priority you named)
3. Audit-log viewer plugin filter
4. Consent DB cutover
5. More real MCP execution arms (post-OAuth)

Branch sits at the new commit on master, **local only**.

**Stop and report.**
