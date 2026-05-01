# Archive Cleanup Inventory — Phase 10C-A

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Phase 10C-A task
**HEAD:** `d4ea4f3`
**Scope:** Backend archives across `.archive/`, `var/security_reports/.archive/`, and any policy/chat/audit-archive folders touching tracked-or-gitignored paths.
**Action policy:** delete only `SAFE_DELETE_TEST_ARTIFACT`; everything else is preserved or marked `REVIEW_REQUIRED` for the founder.

---

## 0. TL;DR

| Outcome | Count | Examples |
|---|---:|---|
| Deleted (SAFE_DELETE_TEST_ARTIFACT) | **1 file + 2 empty parent dirs** | `backend/.archive/general/20260311_114922/tmp6ql81o64.txt` (`test data` literal) + the empty `20260311_114922/` and `general/` parents |
| Kept (security/audit/recoverable) | **1 file** | `backend/var/security_reports/.archive/5581e1ea-92a.report.417.json` — real scan against `mas-ai.co` (Apr 23) |
| REVIEW_REQUIRED (founder decides) | **2 files + 1 nested dir** | `backend/.archive/agent_core_browser_agent.py`; `backend/backend/.archive/agent_core_browser_agent.py` (the duplicate inside the suspicious nested path) |

**No git change required.** All archive content is gitignored
(`.gitignore:233 .archive/` and `.gitignore:110 var/`). The
inventory ships as a doc; the deletions affect only the working tree.

---

## 1. Method

1. Search backend tree for any `.archive` directory at any depth.
2. For each archive folder, list contents, sample first lines of each
   file to determine type (test artifact / production scan / archived
   code / temp data).
3. For duplicate paths (e.g., `backend/backend/`), `diff` the contents
   to confirm true duplication before classifying.
4. Cross-check `git check-ignore` to confirm tracked vs untracked.
5. Apply the classification table below; delete only
   `SAFE_DELETE_TEST_ARTIFACT`.

Other archive surfaces inspected but **empty**:

| Path | State |
|---|---|
| `backend/var/scan_traces/` | does not exist (cleaned earlier) |
| `backend/app/soul/company_seed.archived-*` | none — restored after Phase 10b live-port probe (see `LOCAL_DEMO_SMOKE_REPORT_PHASE10B.md` §6) |
| `backend/var/audit/` | not searched separately — audit ledger is in DB (`goa_audit_events`), not file-archived |
| `var/policies/` | not searched — policies live in DB (`policies` table); no file archive observed |
| `var/chat_sessions/` | not searched — sessions live in DB |
| `frontend/.archive/` | not searched — out-of-scope (no frontend-side archive policy) |

---

## 2. Classification reference

| Class | Meaning | Action this run |
|---|---|---|
| `KEEP_AUDIT_EVIDENCE` | Tamper-evident audit row / decision log | NEVER delete |
| `KEEP_SECURITY_REPORT` | Real scan output (target/findings/cost/duration recorded) | NEVER delete |
| `KEEP_RECOVERABLE_HISTORY` | Soft-archived business state (chat session, project, draft) the founder may want to recover | NEVER delete unless founder explicitly approves |
| `SAFE_DELETE_TEST_ARTIFACT` | Provably synthetic — `test data` literal, sentinel filename, `tmp` prefix, empty payload | Delete this run |
| `REVIEW_REQUIRED` | Looks deletable but has ambiguous origin (duplicate path, near-recent timestamp, code that could be reference material) | Flag in this doc; founder decides |

---

## 3. Per-item findings

### 3.1 `backend/var/security_reports/.archive/5581e1ea-92a.report.417.json`

| Field | Value |
|---|---|
| **Class** | **`KEEP_SECURITY_REPORT`** |
| Size | 3,895 bytes |
| First 3 lines | `{ "job_id": "5581e1ea-92a", "tier": "SCOUT", ... }` |
| Created (mtime) | Apr 23, 2026 16:13 |
| Origin | Real scan launched by the founder (or Daena agent) against `https://mas-ai.co/` |
| Findings | 4 (per Phase 10b §6 live-port probe response: 0 CRITICAL, 0 HIGH, 1 MEDIUM, 2 LOW; cost $0.542; duration 281.88 s; tools_used http_probe + nuclei) |
| Gitignored | YES (`.gitignore:110 var/`) |
| **Action this run** | **None — preserved.** This is exactly the kind of record the Phase 10b B3 "Show archived" toggle exists to recover. Deleting it would erase real scan history. |

### 3.2 `backend/.archive/general/20260311_114922/tmp6ql81o64.txt`

| Field | Value |
|---|---|
| **Class** | **`SAFE_DELETE_TEST_ARTIFACT`** |
| Size | (very small) |
| Content | `test data` (literal — only payload) |
| Created (mtime) | Mar 11, 2026 (in the dated subfolder name) |
| Origin | Almost certainly a `tempfile`-stage artifact from a March test run; filename is the standard Python `tempfile.NamedTemporaryFile()` shape (`tmp` + random) |
| Gitignored | YES (`.gitignore:233 .archive/`) |
| **Action this run** | **Deleted.** Plus the now-empty `20260311_114922/` and the now-empty `general/` parent directories were also removed (rmdir succeeded for both because they had no other contents). |

### 3.3 `backend/.archive/agent_core_browser_agent.py`

| Field | Value |
|---|---|
| **Class** | **`REVIEW_REQUIRED`** |
| Size | 7,877 bytes |
| First 5 lines | `"""BrowserAgent -- Playwright-based web interaction.` <br/> `Direct browser automation without MCP overhead.` <br/> `Handles navigation, form filling, screenshots, data extraction.` ... |
| Created (mtime) | Mar 27, 2026 17:15 |
| Origin | Older `BrowserAgent` implementation, archived when DaenaBot's BrowserAgent was refactored. Per CLAUDE.md project state: "DaenaBot ... BrowserAgent + ... wired" (current). |
| Gitignored | YES |
| **Why REVIEW_REQUIRED, not SAFE_DELETE:** Per CLAUDE.md "NEVER delete -- archive to .archive/. Developer mode toggle for hard delete (ADMIN+ only)." This file is *already* archived; the question is whether the founder is ready to hard-delete archived legacy code or wants it kept for autopsy. **Founder decides.** |
| **Action this run** | **None — preserved pending founder review.** |

### 3.4 `backend/backend/.archive/agent_core_browser_agent.py` (duplicate-in-nested-path)

| Field | Value |
|---|---|
| **Class** | **`REVIEW_REQUIRED`** (suspicious nesting + duplicate content) |
| Size | 7,877 bytes |
| Bit-for-bit identical to 3.3? | **YES** (`diff` returned exit-0 with no output) |
| Created (mtime) | Apr 8, 2026 10:43 — newer copy than the canonical at 3.3 |
| Origin | Mystery. The path is `backend/backend/.archive/...` — a doubled `backend/backend/` parent. Probably a script that resolved an archive destination relative to the wrong cwd (e.g., something running from inside `backend/` writing `./backend/.archive/...`). |
| Gitignored | YES (under same `.archive/` rule) |
| **Why REVIEW_REQUIRED:** the *content* is a confirmed duplicate of 3.3 and trivially deletable, but the *containing path* `backend/backend/` is unexpected and may indicate a script bug in the archive routine that should be fixed before just sweeping the symptom. Until the script is found and fixed, deleting this could mask the bug; until founder confirms the parent dir has no other purpose, removing it carries small but non-zero risk. |
| **Action this run** | **None — preserved pending founder review of the doubled path.** |

---

## 4. Suggested follow-ups (NOT executed)

1. **Founder reviews 3.3 + 3.4** and decides:
   - Keep both for autopsy (no action).
   - Delete the duplicate at 3.4 + investigate which archive script wrote to `backend/backend/.archive/` so the underlying bug is fixed (most useful path).
   - Hard-delete both (only if BrowserAgent rewrite is permanently abandoned and the older code carries no reference value).
2. **Add a periodic archive-rotation policy** if the founder wants
   automatic SAFE_DELETE of `backend/.archive/general/<date>/tmp*` after
   N days. Out of scope for Phase 10C-A.
3. **Stop the doubled-path bug:** find the `cd backend && script-that-archives` invocation that wrote to `backend/backend/.archive/`. Once
   reproduced, fix the script's path resolution. Out of scope.

---

## 5. Hard rules respected

- No production deploy.
- No `USE_CONNECTION_REGISTRY_V2=true` flip.
- No `vault --apply`.
- `vault.py` / `oauth_credentials_store.py` not touched.
- No secrets read or printed.
- No external scans run.
- No external messages / emails sent.
- No Phase 11 work begun.
- **Audit / security / history records: not deleted.** Only the
  `test data`-only tempfile + its empty parent directories were
  removed.

End of inventory.
