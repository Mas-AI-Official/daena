# PR-CONN-RUN-FIRST-READONLY-SKILL-FLOW -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-LAPTOP-USABLE-TODAY-SPRINT-7 (PR-4 of 7)

---

## 1. Goal

After PR-3 helped the operator make a plugin callable, this PR makes
running the first read-only skill obvious. On the Filesystem plugin's
detail drawer, when the lifecycle is `callable`, a hero block surfaces
"Try your first Daena skill: Run find_files (read-only)".

The actual run goes through the existing SkillExecuteModal so the
operator always sees the no-writes/no-deletes/no-external-network
confirmation BEFORE invoking.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| No bypassing the Phase 2 confirmation modal | YES -- pinned by `test_block_uses_phase2_modal_for_actual_run` |
| No auto-fill of folder paths | YES -- pinned by `test_block_never_auto_fills_inputs` (forbids `process.cwd`, `homedir`, `localStorage.getItem`, `api.get`, etc.) |
| Hero block silent unless plugin is callable AND skill is allowlisted | YES -- pinned by component logic + tests |
| Plugin recognized but not callable -> route to install/probe path | YES -- "almost there" locked variant pinned by `test_block_handles_not_callable_path_honestly` |
| find_files stays read-only at the backend | YES -- pinned by `test_find_files_is_read_only` (and Sprint-6 PR-5 floor: `PHASE2_ALLOWLIST` rejects `read_only=False`) |
| No write/delete via the hero path | YES -- Phase 2 executor still rejects writes; hero only points at `find_files` which is read-only |

---

## 3. Surface area

### Frontend

#### `frontend/src/pages/connections/FirstSkillRunBlock.tsx` (NEW)

* `FIRST_RUN_SKILLS` map -- `{ 'mcp-filesystem': { skill_id, label, why } }`.
  Conservative (one entry today). Future PRs add more recipes here.
* Renders one of three states:
  - **Recipe + callable + allowlisted** -> emerald hero with
    `Run find_files` button (opens SkillExecuteModal).
  - **Recipe + recognized but not callable** -> amber "almost there"
    hint pointing at MCP Store install + Probe.
  - **Recipe + callable + NOT in allowlist** OR **no recipe** -> null
    (fall back to the existing skill chip cluster).
* Uses the SYNC `lookupPhase2(plugin_id, skill_id)` API (no async
  flicker; the hook keeps the allowlist cached).
* `data-testid` hooks: `first-skill-run-block`,
  `first-skill-run-block-locked`, `first-skill-run-button`.

#### `frontend/src/pages/connections/PluginDetailDrawer.tsx` (MODIFIED, +6 LOC)

* Imports `FirstSkillRunBlock`.
* Renders the block ABOVE the existing Skills section so the hero
  action is the FIRST thing the operator sees on a callable plugin.

### Tests

#### `backend/tests/test_first_skill_run_contract.py` (NEW, 8 tests)

1. **`test_find_files_is_phase2_allowlisted`** -- exactly one
   `(mcp-filesystem, find_files)` row in `PHASE2_ALLOWLIST`.
2. **`test_find_files_is_read_only`** -- the row's `read_only` flag
   is True (Sprint-6 PR-5 invariant).
3. **`test_block_hard_codes_filesystem_to_find_files`** -- the
   recipe map references both ids verbatim.
4. **`test_block_uses_phase2_modal_for_actual_run`** -- imports +
   renders SkillExecuteModal (cannot bypass the confirmation).
5. **`test_block_never_auto_fills_inputs`** -- forbidden prefill
   sources (`process.cwd`, `homedir`, `localStorage`, `api.get`/`post`)
   absent from the source.
6. **`test_block_carries_test_ids`** -- 3 stable testids for browser
   smoke.
7. **`test_block_handles_not_callable_path_honestly`** -- "almost
   there" copy lives in the locked branch.
8. **`test_drawer_renders_first_skill_run_block`** -- the
   PluginDetailDrawer imports + renders the block.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_first_skill_run_contract.py -q
........                                                                 [100%]
8 passed in 0.07s

$ npx tsc --noEmit
EXIT=0
```

**Sprint progression:** PR-3 ended at 302 in scope.
PR-4 adds 8 tests = **310 in scope**.

---

## 5. Smoke (manual, tomorrow)

1. Open `/connections` on the Plugins tab.
2. Click into Filesystem (after install + probe makes it callable).
3. The drawer shows the new emerald hero block at top: "Try your first
   Daena skill -- Run find_files (read-only)".
4. Click `Run find_files` -- the SkillExecuteModal opens with the
   existing no-writes/no-deletes/no-external-network confirmation.
5. Type a folder path, hit Run -- Phase 2 returns a planned preview
   (Phase 3 writes are still off; the executor rejects writes).
6. Close the modal. Open a non-callable plugin (e.g. `app-gmail`
   without OAuth) -- the hero block stays silent there (no recipe
   registered).

---

## 6. What did NOT change

* SkillExecuteModal -- the existing Phase 2 read-only modal is
  unchanged. The hero block delegates to it without modifying its
  behavior.
* Phase 2 allowlist contents -- unchanged. The hero merely opens
  what the backend already permits.
* Connector probe / install API -- unchanged.
* Phase 3 writes -- still impossible. The executor's `read_only`
  defense is unchanged; this PR adds zero new entries to
  `PHASE2_ALLOWLIST`.

---

## 7. Follow-up PRs

1. **`PR-CONN-FIRST-RUN-MORE-RECIPES`** -- add recipes for other
   easy-to-test plugins (e.g. `mcp-everything-search`,
   `mcp-time`, `mcp-fetch` for read-only HTTP). Defer until ops
   feedback identifies the next-most-useful first run.
2. **`PR-CONN-FIRST-RUN-INLINE-RESULT`** -- after the modal returns,
   surface a tiny "last run: 12 files in C:\Foo" badge inline so
   the hero conveys recent success without opening the modal again.
3. **`PR-CONN-FIRST-RUN-CHAT-DRAFT`** -- when the modal returns,
   offer "Send result to chat" CTA that drops a draft into the
   composer (Phase 1 chat-draft is already supported by the modal).
