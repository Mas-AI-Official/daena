# PR-CONN-PHASE2-ARM-ZERO-INPUT-MCPS — Report

**Branch:** master (local only — not pushed)
**Sprint:** Sprint-9 PR-3
**Date:** 2026-05-05
**Status:** Done. 214/214 tests passing across regression band; frontend tsc clean.

---

## What this PR is for

Sprint-9 PR-2 (`PR-CONN-MCP-READINESS-AUDIT-AND-INSTALL-POLISH`) classified the 57-entry marketplace catalog into 6 readiness statuses. Verdict: **4 entries are zero-input one-click installable** — `mcp-time`, `mcp-fetch`, `mcp-memory`, `mcp-sequential-thinking` — but **none of them carry an armed `mcp_tool` execution skill**. Filesystem (`find_files`) was the *only* demonstrable Daena-armed skill on a callable plugin.

This PR closes that gap. After install, each of the four zero-input MCPs now has one safe, read-only skill the operator can run from the Connections plugin drawer. No tokens, no OAuth, no paid services, no Phase 3 writes.

---

## Honest before/after

| What the local-beta operator can demonstrate | Before this PR | After this PR |
|---|---|---|
| Filesystem `find_files` (sandbox search) | ✅ | ✅ |
| Time `current_time` (wall-clock in any IANA tz) | ❌ | ✅ |
| Fetch `fetch_public_url` (read public URL, capped) | ❌ | ✅ (with SSRF guard) |
| Memory `list_memory_graph` (cross-tool KG dump) | ❌ | ✅ |
| Sequential-Thinking `reason_step` (single-step plan record) | ❌ | ✅ (single-step only) |

Phase 3 floor still holds. **`PHASE2_ALLOWLIST` has zero non-read-only entries — pinned at module-load time and re-pinned by a fresh test in this PR.**

---

## Skills added

All four are wired with `backend_surface="mcp"`, `read_only=True`, `execution_mode="mcp_tool"`.

### A. `mcp-time:current_time` → `get_current_time(timezone)`

* **Required input:** `timezone` (IANA, e.g. `UTC`, `America/Toronto`)
* **Reads:** wall-clock time + offset
* **Writes:** none
* **Network:** none (the time MCP runs locally, returns local clock)
* **Audit row:** records skill invocation + zone string. No PII.

### B. `mcp-fetch:fetch_public_url` → `fetch(url, max_length=65536)`

* **Required input:** `url`
* **Reads:** public-internet URL response body, capped at 64KB by the MCP
* **Writes:** none (no cookies, no POST, no file download)
* **Pre-call SSRF guard (NEW module `url_safety.py`):**
  - Blocks loopback (127/8, ::1, `localhost`, `broadcasthost`)
  - Blocks RFC1918 (10/8, 172.16/12, 192.168/16) + IPv6 ULA (`fc00::/7`)
  - Blocks link-local (169.254/16 — incl. cloud metadata 169.254.169.254 — and `fe80::/10`)
  - Blocks reserved/multicast/unspecified IPs
  - Blocks internal-DNS suffixes: `.local`, `.internal`, `.corp`, `.home`, `.lan`, `.intranet`, `.localdomain`
  - Blocks non-`http(s)` schemes (`ftp://`, `file://`, `javascript:`, etc.)
* **Audit row:** records BLOCK fact + reason code (`url_safety:url_loopback_host`, etc.). The rejected URL value is **never** stored in the audit row — only the reason code travels.
* **Defense-in-depth:** `max_length` cap at the MCP boundary + `_RESULT_SUMMARY_MAX_CHARS=1200` trim at the executor + SHA256[:8] hash in the audit row (existing contract).

### C. `mcp-memory:list_memory_graph` → `read_graph()`

* **Required input:** none
* **Reads:** the memory MCP's full entity + relation graph
* **Writes:** **none — explicitly mapped to `read_graph` only.** A regression test pins that the executor never targets `create_entities`, `create_relations`, `add_observations`, `delete_entities`, `delete_relations`, or `delete_observations`.
* **Cap:** result trimmed to 1200 chars at the executor before reaching the operator.

### D. `mcp-sequential-thinking:reason_step` → `sequentialthinking(thought, thoughtNumber=1, totalThoughts=1, nextThoughtNeeded=False)`

* **Required input:** `thought` (one short string from the operator)
* **Reads:** structured acknowledgement of the recorded thought
* **Writes:** none — the MCP keeps an in-process plan (no disk, no network, no LLM inference)
* **Hidden CoT exposure:** **none.** The MCP does NO LLM inference on its own — it's a structured recorder. The arg builder pins single-step usage (no multi-iteration loops). The reads_summary copy explicitly states this is not hidden chain-of-thought.

---

## Did anything stay planned-only?

No. All four candidates the brief named were safely armable. No blocker required a `planned_only` fallback.

The brief allowed me to keep memory or sequential-thinking as `planned_only` if the MCP only exposed write tools or otherwise was unsafe. Both turned out to be safe:
- `mcp-memory` exposes both reads and writes; we map exclusively to a read.
- `mcp-sequential-thinking` is a structured recorder, not an LLM; single-step usage is safe.

---

## Files touched

### Backend (new)

| File | Purpose |
|---|---|
| `backend/app/services/connection_v2/url_safety.py` | Pure SSRF classifier — no DNS, no network, offline-testable. Public API: `is_public_url_safe(url) -> (ok, reason)`. |

### Backend (modified)

| File | Change |
|---|---|
| `backend/app/services/connection_v2/skill_executor.py` | +4 `SkillToolMapping` entries · +4 server-key candidate sets in `_PLUGIN_TO_SERVER_KEY` · +4 arg builders in `_ARG_BUILDERS` · NEW `_PRECALL_VALIDATORS` table + dispatcher · NEW Step 4.5 in `execute()` · NEW constant `_FETCH_MAX_LENGTH=65536` |

### Backend (tests, new)

| File | Tests | Purpose |
|---|---|---|
| `backend/tests/test_url_safety.py` | 38 | SSRF classifier — 16 public-pass cases, 22 blocked-target cases across loopback, RFC1918, link-local, reserved, internal-DNS, bad-scheme, malformed |
| `backend/tests/test_skill_executor_zero_input_mcps.py` | 26 | Allowlist invariants · arg-builder dispatch · per-skill happy paths · SSRF block contract · audit-row no-secret-leak · `needs_connection` when V2 row missing · per-validator/builder-targets-armed-entry defenses |

### Backend (tests, modified)

| File | Change |
|---|---|
| `backend/tests/test_skill_executor_phase2.py` | Added 4 entries to `PROMOTED_TO_MCP_TOOL` (the pin that catches stealth promotions). |

### Frontend

No code changes. The existing `SkillExecuteModal.tsx` reads `required_inputs` + `reads_summary` from the allowlist API generically — new entries surface automatically. `npx tsc --noEmit` clean.

---

## Hard rules — every one held

| Rule | Held |
|---|---|
| 1. Do not push to origin | ✅ |
| 2. Do not deploy production | ✅ |
| 3. Do not flip `USE_CONNECTION_REGISTRY_V2` | ✅ |
| 4. Do not run `vault --apply` | ✅ |
| 5. Do not read/print/grep/log/commit secrets | ✅ |
| 6. Do not send emails / DMs / webhooks | ✅ |
| 7. Do not enable Phase 3 writes | ✅ — pinned by import-time invariant + 2 tests |
| 8. Do not run external browser automation | ✅ |
| 9. Do not add paid/API-token requirements | ✅ — every armed skill is zero-credential |
| 10. Do not auto-install packages | ✅ — no install runs in this PR |
| 11. Do not mark callable without probe truth | ✅ — `needs_connection` returned when V2 row not callable |
| 12. If a tool cannot be proven read-only, keep it planned or blocked | ✅ — memory mapped to `read_graph` only |

---

## Tests run

```
TMPDIR=/d/tmp .venv/Scripts/python.exe -m pytest \
  tests/test_url_safety.py \
  tests/test_skill_executor_zero_input_mcps.py \
  tests/test_readiness_audit.py \
  tests/test_filesystem_find_files_real_readonly.py \
  tests/test_cli_mcp_writer_placeholder_input.py \
  tests/test_skill_executor_phase2.py \
  tests/test_skill_executor_oauth_wireup.py \
  tests/test_security_scope_add_from_scan.py
```

**Result: 214 passed.** Sprint-9 PR-3's tests + adjacent regression: 0 failures.

---

## What the operator can do now on a clean install

1. Install Filesystem from marketplace → run `find_files` on D:\Ideas
2. Install Time from marketplace → run `current_time` for any IANA zone
3. Install Fetch from marketplace → run `fetch_public_url` on `https://example.com/`
4. Install Memory from marketplace → run `list_memory_graph` (empty on first run; populates as cross-tool agents write to the MCP)
5. Install Sequential-Thinking from marketplace → run `reason_step` with one operator-supplied thought

Five demonstrable read-only skills, zero credentials required.

---

## Sprint-9 queue update

| # | State |
|---|---|
| 1 | `PR-SCAN-ADD-TO-SCOPE-INLINE-CTA` — done |
| 2 | `PR-CONN-MCP-READINESS-AUDIT-AND-INSTALL-POLISH` — done |
| **3** | **`PR-CONN-PHASE2-ARM-ZERO-INPUT-MCPS` — done** |
| 4 | `PR-CONN-FS-PROBE-AUTO-INSTALL-NOTICE` — partly done (probe copy already actionable). Remaining: surface those hints inline on the marketplace card. |
| 5 | `PR-CONN-CONSENT-EXECUTOR-DB-CUTOVER` |
| 6 | Audit-log viewer plugin filter |
| 7 | Google OAuth manual setup helpers |

**Next natural step:** `#4 PR-CONN-FS-PROBE-AUTO-INSTALL-NOTICE` — finish the inline marketplace-card hints so the operator doesn't have to drill into the probe response to discover they need Node.js. Or push the local beta if you're satisfied with the demo path.

**Stop and report.**
