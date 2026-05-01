# Stable Checkpoint — Phase 10b

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Phase 10b checkpoint task
**Branch:** `rebuild-connections-mcp-runtime`
**HEAD:** `917b975` — `docs: phase10b verification report + post-fix OpenAPI spec`
**Tag (proposed):** `stable-phase10b-local-demo` at HEAD

---

## 1. What this checkpoint pins

This is a **code-quality + audit-completion** checkpoint, not a clean-tree
checkpoint. The HEAD itself is clean and represents a logical milestone:

* Phase 9 audit complete (Tooling readiness, UI Action Contract Matrix,
  Live Playwright trace, OpenAPI contract diff, Multi-model review pack,
  Sanitized review pack, Synthesis).
* Phase 10 P0 fixes shipped (U1/U2/U3 unsafe gates, chat-session audit
  emit, chat file-remove honest tooltip).
* Phase 10b shipped (5 OpenAPI ghost calls closed, scan UX repairs,
  settings downstream-read audit, verification report).

The working tree is **NOT clean** — see §3 — because the
`rebuild-connections-mcp-runtime` branch carries substantial in-flight
connections-rebuild work that pre-dates Phase 9/10/10b. None of that
WIP is part of this checkpoint; the tag points at `917b975`, which is
the last clean commit.

---

## 2. Latest commits in this checkpoint

```
917b975 docs: phase10b verification report + post-fix OpenAPI spec
492aec8 docs: phase10b settings downstream-read audit
d55f3a9 phase10b: scan UX repairs (B1 re-run, B2 ready toast, B3 archive view)
ddb01cf phase10b: close 5 OpenAPI ghost calls + add scan archive query
a6bf128 docs: phase 9 audit + 9E multi-model review + phase 10 verification
dc9d666 phase10: chat session audit emit + chat file-remove honest tooltip
c696f6a phase10: fix unsafe action gates (U1+U2+U3) at REST boundary
```

Code-bearing commits in scope of this checkpoint: **5** —
`c696f6a`, `dc9d666`, `ddb01cf`, `d55f3a9`. (Plus `a6bf128`, `492aec8`,
`917b975` which are doc-only.)

---

## 3. Working tree status

```
 96  M    (modified)
 23  D    (deleted)
123  ??   (untracked)
---
242 total uncommitted entries
```

**This is connections-rebuild branch WIP, not regression.** Source-of-
truth: the operator's own pre-existing connections-rebuild work on this
branch. Examples (verified via `git status --short`):

* New `frontend/src/pages/connections/`, `frontend/src/components/connections/`,
  `frontend/src/components/policies/` directories — connections V2 panel
  refactor.
* New `frontend/src/hooks/useConnectorCatalog.ts`,
  `useApprovalsStream.ts`, `useRuntimeRegistry.ts`.
* New `frontend/src/lib/sse.ts`.
* New `frontend/src/stores/{backendHealthStore,errorStore}.ts`.
* New `packages/daena-mcp/` — daena-MCP package.
* Many `docs/Ultraview/STABILIZATION_*.md`, `WHAT_IS_*.md`,
  `WHAT_TO_REMOVE_*.md` reports written during this branch.
* Modified frontend pages (~30 files) under the same refactor.

**No Phase 10b code lives in this WIP.** Everything Phase 10b shipped
in the four numbered commits above. The tag will point at HEAD
(`917b975`), so a checkout at the tag gets Phase 10/10b without the
WIP noise.

---

## 4. Test results

**Scoped backend test sweep (this run):**

```
backend/tests/test_phase10b_ghost_call_fixes.py            8 passed
backend/tests/test_phase10_unsafe_gates.py                  5 passed
backend/tests/test_phase10_chat_session_audit.py            3 passed
backend/tests/test_engagement_approval_persistence.py        2 passed
backend/tests/test_company_mode.py                          9 passed
backend/tests/test_company_mode_seed.py                      4 passed
backend/tests/test_project_service.py                       21 passed
                                                          ─────────
                                                          52 passed in 20.79s
```

**Broader regression sweep (from prior phases this run):**
106/106 pass when the runtime adapter suite is included.

**Frontend `npx tsc --noEmit`:** exits 0.

**OpenAPI offline rebuild:** all 4 Phase 9D real ghosts (G1–G4) reachable
in the spec. `/security/scans` exposes `archived` parameter. Total ops
went 396 → 400; total paths 352 → 355. Spec saved to
`docs/Ultraview/openapi-live-phase10b.json`.

---

## 5. Local demo readiness

**Verdict: ready** (see `LOCAL_DEMO_SMOKE_REPORT_PHASE10B.md` for the
14-item smoke breakdown). Caveats:

| Area | Status |
|---|---|
| Health endpoint | ✓ healthy |
| Auth (register + login) | ✓ end-to-end working |
| V2 connections list (auth) | ✓ 200 |
| Runtimes registry | ✓ 200 |
| Scans list (active) | ✓ 200 |
| Phase 10b ghost-call routes | ✓ exist in offline spec; **running backend on :8000 is stale** — needs restart to serve them |
| Settings persistence | ✓ end-to-end (audit doc) |
| Settings downstream-consumer reads | ⚠ mapped: 3 WIRED, 9 STUB/PARTIAL/DEAD (audit doc) |

**Founder action required for full local demo:** restart the local
backend so the new Phase 10b routes are actually served. The currently
running uvicorn on `127.0.0.1:8000` was launched before Phase 10b
commits and returns 405 on `DELETE /company-mode/seed-brief`. See §8.

---

## 6. Cloud `daena-v2` status

From `CLEAN_GCLOUD_REBUILD_CORS_FIX_REPORT.md` (2026-05-01):

| Field | Value |
|---|---|
| Service | `daena-v2` |
| URL | `https://daena-v2-mj6b2zy7xa-uc.a.run.app` |
| Latest revision | `daena-v2-00003-7zx` |
| Image SHA | `sha256:1b4e0e4e43bb724f3ed23c78157f7ff227cd7ae777be4340dc6bd2b477939fe2` |
| Built from commit | `5646877` (NOT this checkpoint — significantly older) |
| Traffic | 100% |
| Readiness | 17 PASS / 0 FAIL / 0 WARN / 0 SKIP |
| `USE_CONNECTION_REGISTRY_V2` | `false` (locked) |
| CORS_ORIGINS | `["https://daena.mas-ai.co","https://mas-ai.co","http://localhost:5173"]` |
| Health | HEALTHY |

**Cloud daena-v2 does NOT yet carry Phase 10 + Phase 10b.** A fresh
image build is required to ship c696f6a, dc9d666, ddb01cf, d55f3a9
(and is documented in `DAENA_V2_PHASE10B_DEPLOY_PLAN.md`).

Legacy `daena` service: untouched, broken-by-design, kept for autopsy.

---

## 7. Remaining blockers (if any)

None blocking a local demo at HEAD `917b975`. Items to surface:

1. **Running backend on :8000 is stale** — restart needed to serve the
   Phase 10b routes (see §8).
2. **Settings downstream-consumer gaps** — 9 of 14 focus settings persist
   without a backend reader. Founder caveat to surface during demo;
   Phase 11 sprint sequenced in
   `PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md` §6.
3. **Cloud `daena-v2` lags behind** — no Phase 10 + 10b in the deployed
   image. Not blocking *local* demo; blocks any *cloud-served* demo
   until the deploy plan is run under founder approval.
4. **Phase 9B matrix items still open**: connection V2 empty for fresh
   tenants, policy hard-delete vs soft-archive, Global Sync Status
   indicator. Not blocking demo, queued for Phase 11+.

---

## 8. Rollback notes

**Rollback strategy: tag-based, atomic, reversible.**

The tag `stable-phase10b-local-demo` points at `917b975`. To roll back
to this checkpoint from any later state:

```bash
# Local rollback (preserves WIP via stash):
git stash push -m "phase10b-checkpoint-rollback-stash"
git checkout stable-phase10b-local-demo

# To resume work from this checkpoint:
git checkout rebuild-connections-mcp-runtime
git stash pop  # if WIP existed
```

**Per-commit rollback** (if a specific Phase 10b commit needs to be
backed out individually):

| Commit | What it touches | How to revert |
|---|---|---|
| `917b975` | docs only | `git revert 917b975` — pure doc revert, no code |
| `492aec8` | docs only | `git revert 492aec8` — pure doc revert, no code |
| `d55f3a9` | scan UX (frontend + e2e test) | `git revert d55f3a9` will re-introduce the giant ScanPage.tsx pre-refactor; expect tsc errors. Better: cherry-pick only the Phase 10b scan UX hunks back out. |
| `ddb01cf` | backend ghost calls + scan archive query | `git revert ddb01cf` — clean revert; UI calls would 404/405 again per Phase 9D. |
| `dc9d666` | chat session audit emit + chat file-remove tooltip | `git revert dc9d666` — clean revert. Audit ledger loses the new action types. |
| `c696f6a` | UNSAFE gate fixes (U1/U2/U3) | **DO NOT REVERT casually** — opens Daena to out-of-scope scans + Company Mode contradiction. If revert is unavoidable, file a blocker note in `inbox.md`. |

**Database / vault / secret rollback:** none required. Phase 10b
introduced no schema migrations, no vault changes, no secret rotation.
The only on-disk state side-effect is that
`backend/app/soul/company_seed.archived-<ts>.md` files may now exist if
a founder used the new DELETE route — those are gitignored and harmless
to delete or rename.

**Cloud rollback:** N/A — Phase 10b not deployed to cloud yet.

---

## 9. Boundaries respected this checkpoint

* No production deploy.
* No `USE_CONNECTION_REGISTRY_V2=true` flip.
* No `vault --apply`.
* `vault.py` and `oauth_credentials_store.py` not touched.
* No secrets read or printed.
* No external network scans.
* No external messages / emails sent.
* No Phase 11 work begun.

End of checkpoint.
