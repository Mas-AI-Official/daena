# PR-DOC-DRIFT-FIX

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Parent commit:** `07aaede` (PR-AUDIT-VERIFY+RAG-HONEST PR #2)
**Scope:** Documentation-only. Zero product behavior change. Zero
code touched. Zero tests run (no code changed).

This PR reconciles three architecture documents with the ground
truth surfaced by the Backend Blind-Spot Inventory sweep
(2026-05-01) and adds one missing hard rule to project CLAUDE.md.
It carries no migrations, no flag flips, and does not modify any
of the protected files (vault_adapter.py, vault_migration.py,
oauth_credentials_store.py); it merely names them as protected
where they were previously implicit.

---

## What changed and why

### 1. `DAENA_ARCHITECTURE_GAP_BACKLOG.md`

Three structural updates:

1. **Top-of-doc reconciliation note.** New banner block under the
   convention paragraph lists the entries that landed PRs since the
   sweep (P0-01 closed, P0-04 reclassified, NEW P0-09 added) plus
   the Hallucination of Control reference.

2. **P0-01 (audit chain not validated):** marked CLOSED. The
   resolution shipped in commits `2492b82` (PR-AUDIT-VERIFY PR #1,
   `GET /audit/verify?deep=true`) and `07aaede` (PR-AUDIT-VERIFY
   PR #2, `POST /audit/verify` with rich diagnostic). Outstanding
   follow-ups (PR-AUDIT-VERIFY-CRON, PR-AUDIT-DELETE-GATE) carved
   out as separate ~1h tasks that do not block. Original entry text
   preserved verbatim for audit trail.

3. **P0-04 (Dream Engine "UNSCHEDULED"):** RECLASSIFIED to
   `P2-DREAM-UI`. Ground truth (verified by Phase D agent and direct
   read of `main.py.lifespan`) is that Dream Engine IS scheduled by
   APScheduler at a 15-minute interval. The `GET /memory/dream/status`
   endpoint exists and works; the gap is purely operator visibility
   (no UI surface for last-run-time). Effort downgraded from 3h
   backend rewrite to 1.5h frontend card. Original entry text
   preserved verbatim for audit trail.

4. **NEW P0-09 (HeartbeatDaemon not auto-started):** added as the
   real Rule 17 violation in the heartbeat neighborhood. The daemon
   is implemented (~650 LOC) and the API routes
   `POST /heartbeat/{start,pause,stop}` are mounted, but
   `main.py.lifespan` never starts it. UI controls in
   `SettingsHeartbeat.tsx` advertise daemon control that does not
   exist until an operator manually starts it. Two acceptable fix
   shapes documented (start it / remove the controls), each ~30
   minutes.

### 2. `DAENA_ARCHITECTURE_ATLAS.md`

Added new section **"Appendix B - Blind-Spot Reconciliation"** at
the end of the document, after the existing "Appendix - Multi-Model
Review" section. The Atlas body (sections A through J) is preserved
unchanged. The appendix contains six subsections:

- **B.1 Atlas under-counted backend surface area.** Headline counts
  table comparing what the Atlas implied against the filesystem
  ground truth (~753 backend files, ~318 services, 45 routers, 54
  models, 42 env flags) plus enumerated subtrees the Atlas did not
  name (benchmarks/ cluster, cognitive_scan_engine, swarm/, 5
  specialised DaenaBot agents, integrations cluster, department
  service splits, 20+ cognition analyzers).
- **B.2 Dream Engine: scheduled, not unscheduled.** Same correction
  as Backlog P0-04 reclassification, framed against Atlas section
  B.10.
- **B.3 HeartbeatDaemon: implemented but not auto-started.** Same
  correction as new Backlog P0-09, framed against Atlas section
  C.6. Names this as the real Rule 17 violation that the Blind-Spot
  Inventory previously misattributed to Dream Engine.
- **B.4 Vault path correction.** Documents that
  `backend/app/services/vault.py` does not exist. Names the three
  real paths (vault_adapter.py, vault_migration.py,
  oauth_credentials_store.py) and references the new project
  CLAUDE.md Rule 18.
- **B.5 PRs that landed since the Atlas was written.** Status table
  for the Atlas's recommended follow-on PRs: 4 LANDED (NOTIF-MIG-008,
  AUDIT-VERIFY PR #1, AUDIT-VERIFY PR #2, this PR), several still
  OPEN (LEARN-01, DREAM-01, HB-DAEMON-WIRE, AUDIT-VERIFY-CRON,
  NOTIF-FANOUT).
- **B.6 What this appendix does NOT change.** Explicit boundary: the
  Atlas conceptual model is preserved, the multi-model review
  appendix is preserved, the Hallucination of Control framing
  remains canonical.

### 3. `D:\Ideas\Daena\CLAUDE.md` (project-level)

Added new **Rule 18** (Protected files) after Rule 17. Lists the
three actual paths that must not be deleted:

- `backend/app/services/security/asset_shield/vault_adapter.py`
- `backend/app/services/vault_migration.py`
- `backend/app/services/integrations/oauth_credentials_store.py`

Why each matters and what breaks if it is removed (asset shield
egress filter / vault rotation / OAuth-backed connections
respectively). The rule explicitly notes that earlier drafts
referenced a `vault.py` that does not exist on disk.

The global `~/.claude/CLAUDE.md` is **not** modified; it does not
contain the inaccurate reference and per CLAUDE.md operating norms
the global file is the user's personal config.

### 4. `DAENA_BACKEND_BLINDSPOT_INVENTORY.md`

Fixed the false claim in section 3 ("CLAUDE.md 'do not delete' rule
check"). The original text quoted CLAUDE.md as containing a literal
*"Do not delete vault.py or oauth_credentials_store.py"* hard rule.
Direct grep of both project and global CLAUDE.md on 2026-05-02
found NO such literal text. The corrected entry preserves the
original ground-truth findings (vault.py does not exist; the real
implementation is vault_adapter.py under asset_shield/) but
explicitly notes that the protection rule was being carried only by
per-session briefs until PR-DOC-DRIFT-FIX added Rule 18 to project
CLAUDE.md.

### 5. `PR_DOC_DRIFT_FIX_REPORT.md`

This file. New.

---

## Files changed (5)

```
M docs/Ultraview/DAENA_ARCHITECTURE_GAP_BACKLOG.md
M docs/Ultraview/DAENA_ARCHITECTURE_ATLAS.md
M docs/Ultraview/DAENA_BACKEND_BLINDSPOT_INVENTORY.md
M CLAUDE.md (project-level)
A docs/Ultraview/PR_DOC_DRIFT_FIX_REPORT.md (this file)
```

No backend code, no frontend code, no tests, no migrations, no
config files, no env files, no protected files (vault_adapter.py,
vault_migration.py, oauth_credentials_store.py untouched).

---

## Verification

### Markdown / git sanity (per brief)

```
$ git status --short
 M CLAUDE.md
 M docs/Ultraview/DAENA_ARCHITECTURE_ATLAS.md
 M docs/Ultraview/DAENA_ARCHITECTURE_GAP_BACKLOG.md
 M docs/Ultraview/DAENA_BACKEND_BLINDSPOT_INVENTORY.md
?? docs/Ultraview/PR_DOC_DRIFT_FIX_REPORT.md
```

Only the 5 expected files are dirty. No unintended modifications.

### Hard-rule check

| Hard rule | Honored |
|---|---|
| No production deploy | Yes (no deploy at all) |
| No flag flip on `USE_CONNECTION_REGISTRY_V2` | Yes (flag not touched) |
| No `vault --apply` | Yes (vault not invoked) |
| No deletion of vault_adapter.py / vault_migration.py / oauth_credentials_store.py | Yes (those files NOT modified; CLAUDE.md Rule 18 added to NAME them as protected, opposite of deletion) |
| No secrets printed or committed | Yes (this is a doc PR; no secret material involved) |
| No external scans | Yes (no scans) |
| No external messages (email / DM / SMS / webhook) | Yes (no external calls) |
| Do not modify product behavior | Yes (zero code touched) |

### Sanity checks performed

1. Direct grep of project CLAUDE.md for `vault.py` returned zero
   matches before this PR's edit. After this PR, project CLAUDE.md
   names the three correct paths under Rule 18 and intentionally
   contains the string `vault.py` only in the historical-context
   sentence at the end of Rule 18.
2. Direct grep of global CLAUDE.md for `vault.py` returned zero
   matches. Global CLAUDE.md not modified by this PR.
3. The three protected files were verified to exist on disk via
   Glob before the rule was added:
   - `backend/app/services/security/asset_shield/vault_adapter.py`
   - `backend/app/services/vault_migration.py`
   - `backend/app/services/integrations/oauth_credentials_store.py`
4. The Backlog now has a single P0-09 entry for HeartbeatDaemon
   Rule 17 violation (verified: the previous P1-02 entry about
   heartbeat config persistence is a separate concern and was
   left intact).

---

## What this PR does NOT do

- **Does not start the HeartbeatDaemon.** That is product behavior
  change; the brief explicitly forbids it. Backlog P0-09 documents
  the gap and the two acceptable fix shapes; the implementation PR
  is `PR-HB-DAEMON-WIRE` (separate, ~30 min).
- **Does not add a Dream Engine UI surface.** That is product
  behavior change; the brief explicitly forbids it. Backlog
  P2-DREAM-UI documents the gap and the fix shape; the
  implementation PR is `PR-DREAM-UI-CARD` (separate, ~1.5h).
- **Does not delete or relocate the original P0-04 entry text.**
  It is preserved verbatim under the reclassification block for
  audit trail.
- **Does not delete or relocate the original CLAUDE.md "do not
  delete" rule** (because no such rule existed); it adds Rule 18
  with the three correct paths.
- **Does not run any tests.** Per the brief, "no product tests
  required unless code touched." No code was touched.
- **Does not modify the Atlas body.** Sections A through J are
  preserved unchanged. The reconciliation lives in a new appendix.
- **Does not modify the global CLAUDE.md** (`~/.claude/CLAUDE.md`).
  The brief refers to the project CLAUDE.md per context.

---

## Caveats

1. **Em-dash hygiene.** Project CLAUDE.md Rule 12 forbids em
   dashes. The existing Atlas / Backlog body uses them heavily
   (pre-existing). All NEW content added by this PR avoids em
   dashes (uses hyphens, parentheses, or rephrasing). No
   retroactive sweep is performed; that would be a separate
   doc-cleanup PR.
2. **Blindspot Inventory has other paragraph-level claims that
   were not re-verified by this PR.** Only the CLAUDE.md "do not
   delete" rule check (section 3) was corrected. Other sections
   stand as written. A future audit may find additional
   paraphrases that need similar correction, but the brief scoped
   this PR to the four named drift items.
3. **The reconciliation appendix uses Atlas section letters
   (B.1 through B.6).** The Atlas body already has section B
   ("Intelligence Layers"); the new appendix uses "B.1" notation
   to indicate "Appendix B section 1," not "Atlas section B
   subsection 1." If this collision becomes confusing, a future
   PR can rename the appendix subsections.

---

## Production deploy implications

None. Pure documentation. The protected-file rule (CLAUDE.md
Rule 18) is enforcement metadata for future PRs but does not
itself change code or runtime behavior.

---

## Next recommended PR

1. **PR-HB-DAEMON-WIRE** (~30 min) - implement the new Backlog
   P0-09 fix (start the daemon in deferred init OR remove the UI
   controls). Closes the only remaining Rule 17 violation in the
   heartbeat neighborhood.
2. **PR-DREAM-UI-CARD** (~1.5h) - add a "Memory > Dreams" card to
   `SettingsMemory.tsx` reading `/memory/dream/status` and
   surfacing last-run-time, total cycles, and last summary.
   Closes Backlog P2-DREAM-UI.
3. **PR-AUDIT-VERIFY-CRON** (~1h) - schedule a nightly auto-verify
   that writes an `audit.chain_verified` row, carved out of the
   P0-01 close.

This PR (PR-DOC-DRIFT-FIX) does not block any of those. It also
does not depend on any open PR.

---

**End of report.**
