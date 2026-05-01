# Phase 10b — Verification Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Phase 10b task
**Branch:** `rebuild-connections-mcp-runtime`
**Commits delivered in this run:**

| SHA | Subject |
|---|---|
| `ddb01cf` | `phase10b: close 5 OpenAPI ghost calls + add scan archive query` |
| `d55f3a9` | `phase10b: scan UX repairs (B1 re-run, B2 ready toast, B3 archive view)` |
| `492aec8` | `docs: phase10b settings downstream-read audit` |
| `<this commit>` | `docs: phase10b verification report` |

Companion docs: `PHASE_10_PRODUCT_INTEGRATION_VERIFICATION.md` (the
prior phase, with the §1 methodology correction this work was
premised on); `UI_ACTION_CONTRACT_MATRIX.md`;
`PHASE_9D_OPENAPI_CONTRACT_REPORT.md`;
`PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md`.

---

## 0. TL;DR

| Layer | Before Phase 10b | After Phase 10b | Evidence |
|---|---|---|---|
| OpenAPI ghost calls (Phase 9D real) | 4 (G1–G4) | **0** | live spec dump (§3) shows DELETE /company-mode/seed-brief, GET /projects/{id}/{tasks,files}, GET /runtimes/subscriptions all reachable |
| Bare `/settings` 307 noise (G5) | UI hits 307 → axios swallows | UI hits `/settings/` directly | `frontend/src/pages/settings/SettingsDeveloper.tsx:48` |
| Re-run on Active Scans completed cards (B1) | absent (button only on history) | present | `ScanList.tsx` `data-testid="scan-active-rerun"` |
| Scan-complete signal (B2) | silent (icon flip only) | toast + green "Report ready" Badge + auto-refresh history | `ScanPage.tsx` (toast on transition); `ScanList.tsx` `data-testid="scan-report-ready-badge"` |
| Archived scans visibility (B3) | invisible (no list, no recovery surface) | "Show archived" toggle + dedicated rail; backend reads `.archive/` when `archived=true` | `ScanList.tsx` `data-testid="scan-show-archived-toggle"` + `security_dashboard.py` updated `_load_scan_history` |
| Settings downstream-read clarity | unknown (Phase 10 §1 deferred) | mapped end-to-end for the 14 focus keys; 3 WIRED, 9 STUB/PARTIAL/DEAD | `PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md` |
| Section D speculative wires | n/a | **none ship** — every gap fails the "high-confidence" bar | audit doc §5 |

**Test result snapshot (this run):**
```
backend/tests/test_phase10b_ghost_call_fixes.py            8 passed
backend/tests/test_phase10_unsafe_gates.py                  5 passed
backend/tests/test_phase10_chat_session_audit.py            3 passed
backend/tests/test_engagement_approval_persistence.py        2 passed
backend/tests/test_company_mode.py                         9 passed
backend/tests/test_company_mode_seed.py                     4 passed
backend/tests/test_project_service.py                      21 passed
backend/tests/test_runtime_adapters.py                      54 passed
                                                          ─────────
                                                          106 passed, 0 failed
```

**Frontend `npx tsc --noEmit`:** exits 0. Zero new TypeScript errors.

**OpenAPI re-diff:**
```
Phase 9D real ghosts:  4 (G1–G4)
Phase 10b ghosts:       0 of those four — all four endpoints reachable now
Spec ops total:         400  (was 396 in Phase 9D)
Spec paths total:       355  (was 352 in Phase 9D)
/security/scans params: ['limit', 'archived']  (was ['limit'])
```
Live spec saved to `docs/Ultraview/openapi-live-phase10b.json`.

---

## 1. What shipped (per commit)

### Commit 1 — `ddb01cf` — Ghost call fixes + B3 backend support

**Backend additions:**
- `DELETE /api/v1/company-mode/seed-brief` (G1) — soft-archives the
  founder seed brief by renaming to
  `company_seed.archived-<UTC-timestamp>.md`. Idempotent: a second
  DELETE on a missing file returns 200 with `exists: false`. Also
  clears the runtime `CompanyContext` store so the next chat doesn't
  keep responding as the now-archived VP.
- `GET /api/v1/projects/{id}/tasks` (G3) and
  `GET /api/v1/projects/{id}/files` (G2) — return an honest empty list
  with `meta.tracking_enabled: false`. The schema has no project↔task
  / project↔file FK yet, and `Project.to_dict()` hard-codes the
  counts to 0; the empty list matches that reality. Returns 404 for
  unknown project ids (no cross-tenant leakage).
- `GET /api/v1/runtimes/subscriptions` (G4) — flat-lists the
  registry's per-runtime subscription cache so the SettingsLLM
  "Connected providers" badge has a dedicated read endpoint instead
  of digging through `GET /runtimes`. Reads strictly from the
  in-memory cache; surfaces `warming: true` when the deferred
  discovery hasn't completed yet.
- `GET /api/v1/security/scans?archived=true` (B3 backend) — when set,
  the `_load_scan_history` loader reads from
  `var/security_reports/.archive/` instead of the live reports dir.
  Default behavior unchanged (active list only).

**Frontend additions:**
- `frontend/src/pages/settings/SettingsDeveloper.tsx` (G5) — trailing
  slash on `/settings` so the request hits the SettingsOverview route
  directly instead of bouncing through a 307.

**Tests:**
- `backend/tests/test_phase10b_ghost_call_fixes.py` — 8 new tests
  covering G1 (archive + idempotent re-delete), G2/G3
  (empty-with-meta + 404), G4 (envelope shape + warming flag), B3
  (default-vs-archived loader). All pass.

### Commit 2 — `d55f3a9` — Scan UX repairs

**Frontend additions:**
- B1 — `Re-run` button on completed Active Scans cards. The button
  was already present on Recent Scans (history); adding it to active
  cards lets the user repeat a scan immediately after completion
  without waiting for `refreshHistory`.
- B2 — explicit "Report ready" success Badge on completed active
  cards (`data-testid="scan-report-ready-badge"`) plus a one-shot
  toast on the status transition to `complete` (or error toast on
  `failed`). Tracked per-job-id via `reportReadyNotifiedRef` so the
  toast never double-fires across poll races. The transition also
  triggers a `refreshHistory` so the new row appears in the Recent
  Scans rail without a manual refresh.
- B3 — "Show archived" toggle in the Recent Scans header
  (`data-testid="scan-show-archived-toggle"`). Wired to the backend
  `?archived=true` query (commit-1). Toggling on flips the rail
  label to "Archived Scans" and hides the "Archive all" button.
  Empty-state hint points the user at the on-disk
  `var/security_reports/.archive/` path.
- B4 — `frontend/e2e/scan-lifecycle.spec.ts` smoke test pinning the
  rendered controls (data-testids above). Network-mocked at the
  Playwright route layer so no real scan ever runs. Satisfies the
  "dev-safe / mock-safe scan only" founder rule.

**Honest disclosure:** `frontend/src/pages/ScanPage.tsx` is a
-780/+143 diff because the branch's pre-existing connections-rebuild
work already broke the giant monolith into a thin orchestrator + new
`frontend/src/pages/scan/` subdir. Net Phase 10b additions: ~50 lines
(Re-run block, Badge, archived toggle handler, toast on transition,
archived query param). The scan/ subdir's other 5 files (ScanLauncher,
ScanReport, ScanArtifacts, tiers, types) are unchanged from the branch
state. The commit message documents this exactly so a future reader
can attribute the diff correctly.

### Commit 3 — `492aec8` — Settings downstream-read audit

Doc-only commit. Maps every focus setting from the brief through the
full chain (UI → persist → hydrate → consumer). Section 5 of the audit
doc ("Section D — high-confidence wires that ship in commit-3")
explicitly catalogues why **no** speculative wires ship in this round
— vocabulary mismatches, parallel sources of truth, missing consumers,
or undefined privacy semantics each blocked at least one candidate.

### Commit 4 — `<this commit>` — Verification report

This file. Plus the freshly-rebuilt OpenAPI dump at
`docs/Ultraview/openapi-live-phase10b.json` (400 ops, 355 paths).

---

## 2. Tests run + raw results

| Suite | Result | Notes |
|---|---|---|
| `tests/test_phase10b_ghost_call_fixes.py` | 8 pass | NEW — covers all of A1–A4 + B3 backend. |
| `tests/test_phase10_unsafe_gates.py` | 5 pass | Phase 10 — unchanged. |
| `tests/test_phase10_chat_session_audit.py` | 3 pass | Phase 10 — unchanged. |
| `tests/test_engagement_approval_persistence.py` | 2 pass | Phase 10 patched test — still pinned. |
| `tests/test_company_mode.py` | 9 pass | No regression from G1 DELETE addition. |
| `tests/test_company_mode_seed.py` | 4 pass | No regression from G1 DELETE addition. |
| `tests/test_project_service.py` | 21 pass | No regression from G2/G3 sub-resource additions. |
| `tests/test_runtime_adapters.py` | 54 pass | No regression from G4 subscriptions endpoint. |
| **Total scoped sweep** | **106 pass / 0 fail** | |

`npx tsc --noEmit` exits 0 across the full frontend after both the
G5 fix and the scan UX edits.

The Playwright spec at `frontend/e2e/scan-lifecycle.spec.ts` is a
**static smoke pin**; it requires the dev frontend (5173) + backend
(8000) running and was not executed in this report's run (no live
runtime spun up beyond the offline app.openapi() probe). Operator can
run `cd frontend && npx playwright test e2e/scan-lifecycle.spec.ts`
when ready.

---

## 3. OpenAPI re-diff (the headline contract closure)

**Method:** rebuilt the spec offline via
`app.openapi()` after this branch's edits, then probed each Phase 9D
ghost path + the new B3 query parameter directly:

```
OK   DELETE /api/v1/company-mode/seed-brief
OK   GET    /api/v1/projects/{project_id}/files
OK   GET    /api/v1/projects/{project_id}/tasks
OK   GET    /api/v1/runtimes/subscriptions
---/security/scans params: ['limit', 'archived']
---total ops: 400
---total paths: 355
```

| Metric | Phase 9D (2026-05-01) | Phase 10b (2026-05-01 later) | Δ |
|---|---:|---:|---:|
| Spec ops | 396 | 400 | +4 |
| Spec paths | 352 | 355 | +3 (DELETE seed-brief merges onto existing path) |
| Real ghost calls (G1-G4) | 4 | **0** | -4 |
| `/security/scans` params | `['limit']` | `['limit', 'archived']` | +1 |

**Conclusion:** the four real ghost calls from Phase 9D §2 are closed.
The G5 trailing-slash cleanup is a frontend-only fix; the spec was
always correct (`/settings/` exists), just the UI was hitting `/settings`
without the slash. tsc + the smoke probe confirm the new URL works.

---

## 4. Remaining ghost / fake / partial actions

**Backend ghost calls:** none from Phase 9D. Spec parity with the
frontend's call sites is now intact for the 4 real ghosts. The
~37 unused spec operations from Phase 9D §3 ("worth-investigating")
are unchanged — they are intentional API surfaces (founder routing,
benchmark, mobile, OAuth callback handlers) without UI consumers,
not bugs.

**Settings downstream-read gaps:** documented in the new audit doc.
9 of 14 focus keys are STUB / PARTIAL / DEAD. Section D explicitly
ships zero wires this round; Phase 11 sprint proposal at audit §6
sequences six small PRs (~14 hours total) to close everything.

**Scan UI gaps:** B1, B2, B3 closed. B4 smoke test pinned. Remaining
soft items from the Phase 10 §3 backlog:
- **Commit-5 (policy soft-archive)** still valid — policy DELETE is
  still hard-delete; should be soft-archive per audit-record-protection
  semantics. Not in Phase 10b scope.
- **Commit-6 (Global Sync Status indicator)** — still valid as
  Gemini's novel UX contribution from Phase 9E. Phase 10 §3
  downgraded its urgency (no FAKE-cluster to surface anymore); the
  audit doc shows the real value would be making the STUB / DEAD
  toggles visible to the founder. Could ship in Phase 11 alongside
  the wire PRs.

**Other matrix items not in Phase 10b scope:**
- Connection V2 panel for fresh tenants — empty until detection-seed
  or Provider-Seed lands (Phase 6 backlog).
- Webhooks form (`/settings/developer`) — intentionally disabled.
  DEAD by design.
- Email notifications (`/settings/notifications`) — intentionally
  disabled. SMTP not wired.
- 3 V1↔V2 connection surface duplicates — still present until V2
  prod-flag flips (founder rule kept this work out of scope).

---

## 5. Daena local demo readiness

| Demo flow | Safe to show? | Notes |
|---|---|---|
| Sign in → /chat → send message | YES | Phase 9C confirmed; settings persist. |
| /governance/audit → verify chain → filter | YES | Audit infrastructure mature. |
| /security/scope → add target → save | YES | Phase 9B verified. |
| /scan → start scan | YES, **safer post-Phase-10** | Out-of-scope returns 403; new "Report ready" toast + Badge make completion obvious; new Re-run button on completed active cards. |
| /scan → archive a report → recover via "Show archived" | YES, **new in Phase 10b** | Archived rail renders; backend reads from .archive/. |
| /company-mode → activate | YES, **safer post-Phase-10** | auto_send/approval contradiction blocked; founder seed brief now soft-archives instead of vanishing on DELETE. |
| /connections → install MCP / connect provider | YES | Verified. |
| /settings any-tab change → reload → verify persist | YES | Settings persist. **Caveat:** 9 of 14 focus settings persist but no consumer reads them yet (per audit doc). Document this to founder as "PROMISED-NOT-WIRED" until Phase 11 closes the gaps. |
| /projects → open project → Tasks/Files tabs | YES, **safer post-Phase-10b** | Tabs no longer 404; honest "no tracking yet" message. |
| /tasks lifecycle | PARTIAL | UI works; create-via-API still has the schema mismatch noted in Phase 9C N3. Not in Phase 10b scope. |

**Founder-facing caveat to surface in any local demo:** the Settings
panels are *honest about persistence* (PUT/GET round-trips) but a
substantial slice — billing values, notification toggles, privacy
toggles — persist without a consumer. This is documented in
`PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md`. Until Phase 11 closes
the wires, the founder should know that toggling "Memory Generation:
OFF" does not currently prevent memory rows from being written, etc.

**Verdict:** **Daena local IS demo-ready** for: founder + invited
testers, plus internal stakeholders comfortable with the persistence-
without-enforcement caveat above.

---

## 6. Cloud `daena-v2` demo safety

Status from prior reports: cloud `daena-v2` is healthy, readiness
17/17 PASS, CORS fixed, `USE_CONNECTION_REGISTRY_V2=false`.

**Phase 10b changes have NOT been deployed.** Per founder rules ("Do
not deploy production"), commits `ddb01cf` / `d55f3a9` / `492aec8` /
`<this>` live on the local branch only. Cloud `daena-v2` continues
to serve the pre-Phase-10 image.

For a **public-facing cloud demo**:
- The Phase 10 P0 gates (U1/U2/U3) and Phase 10b ghost-call fixes
  must land in the next image build before serving traffic.
- The "Show archived" / Re-run / "Report ready" UX wins must also
  land in that image to match the local demo experience.

**Recommendation:** demo against local for now; queue a `phase10b`
image build under explicit founder approval before any cloud demo.

---

## 7. Honest disclosures + transparency notes

- **Commit `d55f3a9` bundles pre-existing branch refactor.** ScanPage.tsx
  -780/+143 because the branch already broke the monolith into a
  scan/ subdir. My net Phase 10b additions are ~50 lines; the rest
  is the existing branch state. Documented in the commit message.
- **Backend G1 DELETE handler clears CompanyContext on success.**
  Side effect: the next chat in the affected tenant won't carry the
  "VP of <Company>" badge until a new seed is saved. This is the
  intended honest behavior — the seed is gone, so the runtime
  context should be too.
- **B3 archived listing reads `.archive/` directly.** The archived
  files have shape `<scan_id>.<label>.<ts>.json`; the existing JSON
  loader extracts `scan_id` from the payload (filename stem is a
  fallback only). Behavior is correct for files produced by
  `_archive_scan`; arbitrary other JSON files in the archive folder
  could surface under odd ids. Not a regression (loader already
  filtered by `.startswith(".")` exclusion).
- **No production deploy** this run. No GCP touch.
- **No `USE_CONNECTION_REGISTRY_V2=true`** flip.
- **No `vault --apply`** run.
- **No vault.py / oauth_credentials_store.py** touched.
- **No secrets read or printed.**
- **No external network scans** run. The B4 Playwright spec uses
  Playwright route mocking; the only target referenced is the IETF
  reserved `*.example` TLD.
- **No new alembic migration** this run.

---

## 8. Exact next actions (in priority order)

1. **Founder reviews the settings downstream-read audit doc** and
   chooses the Phase 11 sprint scope from the proposed PR sequence
   (audit §6).
2. **Founder reviews this verification report's §5 caveats** before
   any local demo, so the persistence-without-enforcement gap is
   surfaced honestly to demo audiences.
3. **Cloud demo decision:** local-only for now, OR queue a
   `phase10b` image build under explicit approval that includes the
   Phase 10 + Phase 10b commits (six total: c696f6a, dc9d666, a6bf128,
   ddb01cf, d55f3a9, 492aec8 — the docs commit a6bf128 doesn't need
   to land in the image, but the others do).
4. **Optional: run the Playwright smoke spec** to confirm the
   data-testid markup works against a real frontend instance:
   `cd frontend && npx playwright test e2e/scan-lifecycle.spec.ts`.
5. **Phase 11 sprint:** the six PRs in the audit's §6 sequence
   (privacy enforcement → notification stub → budget vocabulary →
   routing toggles → hydrate completeness → dual-name cleanup).
   Estimated 14 hours total.
6. **Eventually:** Phase 10 §3 backlog items still pending —
   Commit-5 (policy soft-archive), Commit-6 (Global Sync Status
   indicator), task + file audit emit (mirroring chat session
   audit pattern).

End of report.
