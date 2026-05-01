# Daena Frontend Action Design Rulebook

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Phase 10C-C task
**Status:** **Living document.** Authoritative for new frontend controls + retrofit of existing ones. Lives alongside CLAUDE.md project rules.
**Audience:** anyone (human or AI) adding or editing a button/toggle/form in `frontend/src/`.

---

## 0. Why this exists

Phase 9B–10b surfaced the same failure mode at scale: a UI control
appears, the user clicks, *something* persists somewhere, but the
backend either doesn't read what was saved (STUB), reads from a
different source (PARTIAL), or has no consumer at all (DEAD). The
matrix counted 25 such controls; the Phase 10b audit confirmed 9 of
14 focus settings are in this state.

This rulebook is the prevention. **Every action below has a
prescribed lifecycle.** If you're about to add a control whose
lifecycle doesn't match one of these — stop, write a new lifecycle,
get founder review, then add the control.

The rulebook respects two locked rules from `CLAUDE.md`:

- **Rule 17** (Honesty + Persistence + Visibility): every UI control
  advertises a real capability backed by persistent state; every
  persistent state is auditable; every failure is visible.
- **DESIGN-WITH-EFFECT-CHAINS PROTOCOL**: 7 questions answered
  before code (purpose, effect chain, states, governance hook, audit
  log, plain-English policy, second-order effects).

---

## 1. Universal lifecycle skeleton (applies to every action below)

Every action MUST traverse these phases in order:

1. **Trigger.** User intent expressed via click / keypress / voice.
2. **Pre-flight check.** Client-side validation; permission gate
   visibility (button greyed out for unauthorized roles); confirm
   dialog for destructive ops (per CLAUDE.md rule 2: archive by
   default).
3. **Optimistic UI** *(optional, only when reversible)* — toggle
   state immediately so the user sees feedback under 100 ms. Roll
   back on backend rejection.
4. **Backend call.** Single `api.METHOD(path, body)` via the shared
   `lib/api.ts` axios instance. Never bypass for `fetch`.
5. **Progress state.** For ops > 500 ms: show inline spinner OR
   skeleton OR live progress bar. The user must always know the
   button's request is in flight.
6. **Server response.**
   - 2xx → success state per below.
   - 4xx → user-actionable error per below.
   - 5xx → log + honest "something is wrong" + retry option.
7. **Persistence verification.** Confirmable side effect: a DB row /
   file / audit row / artifact path. The contract documents what
   landed where.
8. **UI refresh.** Either (a) refetch the relevant resource, (b)
   patch the local store with the server's authoritative payload,
   or (c) navigate. Never leave the UI in a stale state.
9. **Audit emit.** Every state-changing action writes a row to
   `goa_audit_events` (or equivalent) so the founder can reconstruct
   who-did-what.
10. **Result discoverability.** The result artifact (downloaded file /
    new row / archived record / sent message) must be findable
    within ≤ 2 clicks from the action that produced it.
11. **Undo / recovery.** Every destructive action has a documented
    rollback path. Soft-archive by default; hard-delete only with
    Developer Mode (per CLAUDE.md rule 2).

If any of phases 4–11 is "TODO", the control should not ship. **Mark
it `disabled` with a "Coming soon" Badge until all phases are real.**

---

## 2. Action lifecycles (per verb)

Each lifecycle below specifies the 11 universal phases at higher
specificity. Use the table format:

```
endpoint       — exact METHOD + path (or NONE for client-only)
persistence    — table / file / column written
progress state — what the user sees during the call
success state  — what the user sees on 2xx
error state    — what the user sees on 4xx / 5xx
audit event    — action_type written to goa_audit_events
undo / recovery— path to reverse the side effect
result location— where the user finds the produced artifact
deploy gates   — local? cloud? prod?
```

### 2.1 Install (e.g. install MCP server / install plugin)

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/connectors/{slug}/install/start` |
| Persistence | new row in `connector_instances` (legacy) or `connection_v2` (V2) with `detected=true, configured=false, imported=true` |
| Progress | inline "Installing…" spinner inside the install dialog |
| Success | dialog confirms; status badge flips to "Imported"; lists refresh |
| Error | dialog stays open; explicit error toast naming the missing dep / invalid path / OAuth-failure reason |
| Audit | `connector.installed` (action_params: `{slug, source: "user-click"}`) |
| Undo | Archive (V2 soft-archive sets `archived=true`) — recoverable via Show Archived |
| Result location | `/connections` panel row appears within 30 s poll cycle |
| Deploy gates | local + cloud + prod (founder-approved plugins only in prod) |

### 2.2 Import (e.g. import a discovered MCP runtime into the V2 registry)

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/connections/v2/import?slug=…` |
| Persistence | `connection_v2` row with `imported=true` set by the import handler |
| Progress | row's "Import" button becomes spinner |
| Success | row badge flips to "Imported (not configured)"; subsequent Probe button enables |
| Error | inline error in the row; offer "View backend log" link to `/governance/audit` filtered by `action_type=connection.import_failed` |
| Audit | `connection.imported` |
| Undo | Archive; row stays for re-import |
| Result location | same panel row |
| Deploy gates | local + cloud (skipped in prod until V2 flag flips) |

### 2.3 Connect (OAuth flow)

| Phase | Spec |
|---|---|
| Endpoint | popup to `GET /api/v1/connectors/{slug}/oauth/authorize` → callback `/api/v1/connectors/oauth/callback` |
| Persistence | tokens encrypted into vault; `connection_v2.authenticated=true` after callback success |
| Progress | popup window; main page shows "Waiting for authorization…" overlay |
| Success | popup closes; main page badge flips to "Connected"; subsequent probe enabled |
| Error | popup closes with error param; main page shows "Authorization failed: <reason>"; offer Retry |
| Audit | `connection.connected` (provider, scopes granted) |
| Undo | Disconnect (revokes vault token + flips `authenticated=false`) |
| Result location | same panel row |
| Deploy gates | local + cloud + prod |

### 2.4 Configure (set credentials / settings on a connection)

| Phase | Spec |
|---|---|
| Endpoint | `PUT /api/v1/connections/{id}/configure` (or per-connector `POST /settings/oauth-credentials`) |
| Persistence | vault for secrets; `connection_v2.configured=true` |
| Progress | save button becomes spinner |
| Success | toast "Configured"; row refreshes |
| Error | inline form errors per field |
| Audit | `connection.configured` (NEVER include the secret value) |
| Undo | Re-configure with empty fields = clears overrides |
| Result location | same panel row |
| Deploy gates | local + cloud + prod |

### 2.5 Test (live functional probe — one-shot)

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/runtimes/{id}/test` (two-stage: binary probe + auth probe) |
| Persistence | NONE (results are ephemeral) |
| Progress | button shows spinner with elapsed timer |
| Success | toast with "Binary OK + Authenticated as <plan>"; `latency_ms` displayed |
| Error | toast with the actionable summary string from `runtimes.py:test_runtime_connection.summary` ("Logged out — run the runtime's login command") |
| Audit | NONE (test is not a state change) |
| Undo | N/A |
| Result location | toast + drawer detail |
| Deploy gates | local + cloud + prod |

### 2.6 Probe (richer than Test — V2 truth-dimension probe)

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/connections/v2/{id}/probe` |
| Persistence | `connection_v2` truth fields (detected/configured/imported/reachable/authenticated/callable + per-dim `failure_reason`) |
| Progress | row badges shimmer briefly |
| Success | row badge updates; failure_dim cleared if all six dims flip true |
| Error | row badge shows the specific failed dim with `failure_reason` tooltip |
| Audit | `connection.probed` (with the resulting truth vector) |
| Undo | re-probe |
| Result location | row + drawer detail |
| Deploy gates | local + cloud (V2 flag) |

### 2.7 Enable / Disable

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/connections/v2/{id}/{enable\|disable}` |
| Persistence | `connection_v2.disabled` flag |
| Progress | toggle Switch shows mid-flip animation |
| Success | Switch settles; row gets greyed-out treatment when disabled |
| Error | Switch flips back; toast names the rejection reason |
| Audit | `connection.{enabled,disabled}` |
| Undo | flip the toggle back |
| Result location | same row |
| Deploy gates | local + cloud (V2 flag) |

### 2.8 Archive (default destructive action — soft)

| Phase | Spec |
|---|---|
| Endpoint | `DELETE /api/v1/{resource}/{id}` (no `?hard=true`) |
| Persistence | flip `archived=true` (or move file to `.archive/` for FS-backed resources like scans) |
| Progress | row briefly fades; for click-twice patterns the first click arms, second confirms within 3 s |
| Success | row drops from default list; "Show archived" toggle reveals it |
| Error | row stays + error toast |
| Audit | `{resource}.archived` |
| Undo | UI button "Restore" on the archived row (or manual file restore for FS) |
| Result location | "Show archived" view |
| Deploy gates | local + cloud + prod |

### 2.9 Delete (hard, irreversible)

| Phase | Spec |
|---|---|
| Endpoint | `DELETE /api/v1/{resource}/{id}?hard=true` |
| Persistence | row removed; or `os.unlink` for FS |
| Pre-flight | confirmDialog with explicit "permanently removes; will NOT be recoverable" copy |
| Progress | spinner |
| Success | row drops from all lists; toast "Deleted permanently" |
| Error | row stays + error toast |
| Audit | `{resource}.deleted_hard` |
| Undo | NONE — by design |
| Result location | N/A |
| Deploy gates | **DEV/local only by default.** Production requires Developer Mode flag (CLAUDE.md rule 2). Prod surface should hide the button when Dev Mode off. |

### 2.10 Scan (start a security scan)

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/security/scans/start` |
| Pre-flight | **REST-boundary scope gate** (Phase 10 U2): `target_matches_scope(body.target, load_authorized_scope(tenant_id))` — 403 with `code=target_not_in_scope` if out-of-scope |
| Persistence | `var/scan_traces/{job_id}.json` (workflow state) → `var/security_reports/{job_id}.json` (report) |
| Progress | live progress card with phase + percent + findings count via SSE `/security/scans/{id}/events` |
| Success | active card flips to "Report ready" Badge (Phase 10b B2); toast + auto-refresh history |
| Error | active card flips to red error Badge with `failure_reason` |
| Audit | `scan.started` (target, tier, scope-validated=true) + `scan.completed` |
| Undo | Archive (soft) → recoverable via Show Archived |
| Result location | active list → completed → click View Report → ScanReport panel |
| Deploy gates | local + cloud + prod (scope gate is the safety net) |

### 2.11 Re-run scan

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/security/scans/{scan_id}/rerun` |
| Persistence | new `ScanJob` (original record untouched in history) |
| Progress | new active card appears at top of list |
| Success | new card runs through normal scan lifecycle |
| Error | toast naming why (target gone from authorized scope, etc.) |
| Audit | `scan.rerun` (links to original scan_id) |
| Undo | Archive the new run |
| Result location | active list, then history |
| Deploy gates | local + cloud + prod |

### 2.12 View Report

| Phase | Spec |
|---|---|
| Endpoint | `GET /api/v1/security/scans/{job_id}/report` |
| Persistence | NONE (read-only) |
| Progress | inline skeleton on the report panel |
| Success | full report renders (findings, severity counts, recommendations) |
| Error | inline message offering Download JSON fallback |
| Audit | NONE (read-only is not a state change) — exception: in MAS-AI compliance contexts, log `report_viewed` with `tenant_id, user_id, scan_id` if needed |
| Undo | N/A |
| Result location | inline ScanReport component |
| Deploy gates | local + cloud + prod |

### 2.13 Download Report

| Phase | Spec |
|---|---|
| Endpoint | `GET /api/v1/security/scans/{job_id}/report/pdf` (auto-detects PDF / Markdown / HTML) |
| Persistence | NONE server-side; client `Blob` save dialog |
| Progress | toast "Preparing report…" |
| Success | browser save dialog appears |
| Error | toast "Failed to generate report"; offer JSON-only fallback |
| Audit | `report.downloaded` |
| Result location | user filesystem |
| Deploy gates | local + cloud + prod |

### 2.14 Save Setting

| Phase | Spec |
|---|---|
| Endpoint | `PUT /api/v1/settings/user` (single endpoint for all user prefs) |
| Persistence | `users.settings` JSONB column |
| Pre-flight | client-side validation per Pydantic schema (`UserPreferencesUpdate`) |
| Progress | none (debounce 500 ms then write fire-and-forget) |
| Success | response is the merged settings object; uiStore updates from response |
| Error | toast "Failed to save"; uiStore rolls back to last-known value |
| Audit | `settings.changed` (per-key diff in action_params) — **TODO Phase 11 cross-cut** |
| Undo | toggle the control back; another PUT lands |
| Result location | reload the page → toggle reflects new value |
| Deploy gates | local + cloud + prod |
| **HONESTY GATE** | **The setting MUST have a backend consumer.** If no service reads `users.settings.<key>`, label the control "Coming soon" and disable it (Phase 10C-D pattern). |

### 2.15 Toggle Setting

Same lifecycle as Save Setting (2.14). Boolean toggles have an
extra constraint: the optimistic UI flip is mandatory (sub-100 ms
feedback on Switch). Rollback on backend reject must animate back
to the previous state.

### 2.16 Main Brain switch

| Phase | Spec |
|---|---|
| Endpoint | `PUT /api/v1/runtimes/primary` |
| Pre-flight | V2 callable gate (V2 mode): refuse if `connection_v2.callable=false` unless `experimental_override=true` |
| Persistence | `users.settings.primary_runtime` |
| Progress | dropdown disabled briefly; current selection greyed |
| Success | dropdown shows new selection; chat header re-renders with new runtime icon |
| Error | dropdown reverts; toast names the gate failure |
| Audit | `runtime.primary_changed` (formal AuditLog row, not just WARNING) — **CLAUDE.md Rule 17 item still open per Phase 9B §4.5** |
| Undo | re-select previous |
| Result location | header + Connections > Main Brain panel |
| Deploy gates | local + cloud + prod |

### 2.17 Experimental Override (for non-callable runtimes)

| Phase | Spec |
|---|---|
| Endpoint | feeds into `PUT /runtimes/primary` body's `experimental_override: true` |
| Persistence | one-shot — no separate persistent flag (the override applies to a single set call) |
| Progress | none |
| Success | runtime is pinned despite V2 gate; warning Badge in UI |
| Error | only when V2 gate is otherwise satisfied (override unnecessary) |
| Audit | `runtime.primary_override` (HIGH risk_level, governance_tier 3) |
| Undo | re-set primary without override |
| Result location | header + audit ledger |
| Deploy gates | local + cloud (founder only); audit-traced in prod |

### 2.18 Send External Action (email / DM / LinkedIn post / SMS)

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/{provider}/send` (e.g. `/api/v1/company-mode/missions/{mid}/drafts/{did}/send`) |
| Pre-flight | **Approval gate by default** (CLAUDE.md social-media-marketing-soul section): never auto-send DMs; never auto-follow/unfollow; rate limits respected |
| Persistence | `drafts.status: awaiting_approval → sending → sent\|blocked\|failed` |
| Progress | button becomes "Sending…" spinner |
| Success | row flips to "Sent"; `sent_at` timestamped; channel chip shows |
| Error | row flips to "Blocked" or "Failed" with `error` field shown inline |
| Audit | `external_action.sent` with `external_action_sent: true` flag (CRITICAL — this is the marker the founder filters audit by) |
| Undo | NONE — once sent, sent. Recovery is to send a follow-up draft. |
| Result location | drafts list + audit ledger filterable by `external_action_sent: true` |
| Deploy gates | local + cloud + prod (with full governance pipeline always on) |

### 2.19 Upload File

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/files/upload` (multipart, 20 MB limit, MIME allowlist) |
| Persistence | `file_records` row + blob to `var/files/<sha256>` |
| Pre-flight | client size check; mime sniff |
| Progress | upload progress bar; chunked if backend supports |
| Success | new row in `/files` page; chip appears on draft if attached to chat |
| Error | toast naming reason (size / type / quota / virus-scan) |
| Audit | `file.uploaded` (filename, sha256, size, purpose) — **gap: not currently emitted (matrix §4.1 cross-cutting)** |
| Undo | Delete (hard) — explicit |
| Result location | `/files` page |
| Deploy gates | local + cloud + prod |

### 2.20 Remove File from Draft (chat X-button)

| Phase | Spec |
|---|---|
| Endpoint | NONE (client-side only) |
| Persistence | NONE (file row + blob both remain in `/files`) |
| Pre-flight | none |
| Progress | chip animates out |
| Success | chip removed from draft; tooltip + aria-label MUST state "removes from this draft only; the file remains in /files" (Phase 10 fix) |
| Error | N/A |
| Audit | NONE — local UI state only |
| Undo | re-attach via paperclip |
| Result location | none (file persists) |
| Deploy gates | local + cloud + prod |
| **HONESTY GATE** | The X button looks destructive. The tooltip + aria-label MUST disambiguate. Phase 10 closed this; new chip patterns must follow. |

### 2.21 Delete File (from /files page)

Use the Hard Delete lifecycle (2.9) with explicit "permanently
removes... will NOT be recoverable" copy in the confirm dialog. Phase
9B matrix §3.6 confirmed this shape.

### 2.22 Create Task

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/execution/tasks` (or auto-created via chat orchestrator) |
| Persistence | `tasks` row with `status: PENDING` |
| Progress | inline skeleton in tasks list |
| Success | row appears at top of list with PENDING badge |
| Error | inline form errors |
| Audit | `task.created` — **gap: not currently emitted (Phase 9B §4.1)** |
| Undo | Cancel → status: CANCELLED |
| Result location | `/tasks` page |
| Deploy gates | local + cloud + prod |

### 2.23 Run Task

| Phase | Spec |
|---|---|
| Endpoint | `POST /api/v1/execution/tasks/{id}/run` |
| Persistence | `tasks.status: PENDING → RUNNING`, `started_at` set |
| Progress | row shows progress percent (15s polling) |
| Success | row transitions to COMPLETED with result payload |
| Error | row transitions to FAILED with `error` text |
| Audit | `task.run_started` + `task.run_completed/failed` — **gap: not currently emitted** |
| Undo | Cancel mid-run; Retry on failure |
| Result location | row → drawer detail; result artifact path linked if applicable |
| Deploy gates | local + cloud + prod |

---

## 3. Cross-cutting design rules

### 3.1 Realtime claims (matrix §4.2 / ADR-001)

> "No advertised real-time without an SSE channel. Polling is honest only if labeled."

If a UI surface shows a live-pulse animation but is actually polling,
**add a small `(live · polling 5s)` tag**. Reserve the unlabeled
pulse for genuine SSE channels (chat stream, governance approvals,
scan walkthrough).

### 3.2 Permission gate visibility (matrix §4.4)

When an endpoint enforces a role/scope server-side, **the UI SHOULD
mirror the gate**: button greyed out + tooltip "Requires <ROLE>" for
unauthorized users. Server-side gate is still authoritative; UI hint
prevents click-then-403 confusion.

### 3.3 Audit-event coverage (matrix §4.1 / Rule 17)

**Every state-changing endpoint MUST emit a row to
`goa_audit_events`.** Phase 10 added the chat-session pattern; Phase
11 PR-T1 + PR-T2 will retrofit tasks + chat-attach + export.

### 3.4 Coming Soon labeling

If a control's backend consumer doesn't exist:

```tsx
<Badge variant="warning" size="sm">Coming soon</Badge>
<Switch checked={value} onChange={toggle} disabled={true} />
```

The Badge MUST be inside the same wrapper as the Switch (so screen
readers associate them) and MUST appear *before* the Switch in DOM
order (so it's announced first).

### 3.5 Honest empty states

When a list endpoint legitimately returns zero rows (matrix
"honest empty"):

```tsx
<EmptyState
  icon={<RelevantIcon size={32} />}
  title="No <resource> yet"
  description="<concrete next action the user can take to populate this list>"
/>
```

NEVER render a fake "online" pill, fake stat, or fake row to fill
the space. (Per the deleted `RuntimeSwapper.DEFAULT_RUNTIMES`
pattern documented in CLAUDE.md Rule 17.)

### 3.6 Undo path documented in copy

For every destructive action, the confirm dialog copy MUST tell the
user how to recover:

- Archive: "You can recover this from the Show Archived view."
- Hard delete: "This cannot be undone."
- Send external action: "Once sent, you can only follow up with another draft."

### 3.7 Deploy-gate matrix (when an action is allowed)

| Tier | Local dev | Cloud staging | Cloud prod |
|---|---|---|---|
| Read-only (View, List, Download) | ✓ | ✓ | ✓ |
| Soft mutations (Save Setting, Archive, Probe) | ✓ | ✓ | ✓ |
| Send External Action | ✓ (sandboxed) | ✓ (test prospects only) | ✓ (governance pipeline always on) |
| Hard Delete | ✓ (Dev Mode optional) | ✗ default; ✓ with Dev Mode flag | ✗ default; ✓ with Dev Mode flag (audit-traced) |
| `vault --apply` / secret rotation | only via founder-approved CLI | ✗ via UI | ✗ via UI; only via founder-approved process |
| `USE_CONNECTION_REGISTRY_V2=true` flip | ✓ | ✓ | **EXPLICIT FOUNDER APPROVAL ONLY** |

---

## 4. Anti-patterns (don't do these)

1. **Save to `localStorage` only when the action implies a server effect.** Phase 9C falsely flagged 25 settings as `localStorage`-only — actually they round-trip to `users.settings`. The lesson: localStorage is fine as a *cache*, not as the *primary* store for any settings the backend should consume.
2. **Don't ship a button without an effect chain.** Per CLAUDE.md DESIGN-WITH-EFFECT-CHAINS PROTOCOL: walk the 7 questions before code.
3. **Don't catch errors silently.** `try/catch` that swallows 4xx is a Rule-17 violation. Always either retry, surface, or audit-log.
4. **Don't render hardcoded "demo data" fallbacks** in production components. If a list is empty, render an honest empty state. Per ADR-001.
5. **Don't auto-send external actions.** DMs, follows, posts always need human approval (CLAUDE.md social-media-marketing-soul). Auto-send only with explicit `auto_send=true` AND `require_founder_approval=true` (Phase 10 U1 enforcement).
6. **Don't use `fetch` directly when `lib/api.ts` exists.** Bypassing the shared axios instance breaks auth-refresh, error capture, and the silent-prefix logic.
7. **Don't use the same name for two different bits.** `developer_mode` collision (system Settings vs user.settings) is the case study.

---

## 5. Action lifecycle template (copy this when adding a new verb)

```markdown
### 2.X New Verb

| Phase | Spec |
|---|---|
| Endpoint | `<METHOD> /api/v1/...` (or `NONE` for client-only) |
| Persistence | <table>.<column> / file path / vault key |
| Pre-flight | <validation, permission gate, confirm dialog> |
| Progress | <inline spinner / skeleton / progress bar / toast> |
| Success | <UI state on 2xx> |
| Error | <UI state on 4xx / 5xx; user-actionable message> |
| Audit | `<resource>.<verb>` with action_params: `{...}` |
| Undo | <how to reverse the side effect> |
| Result location | <where the user finds the produced artifact> |
| Deploy gates | local? cloud? prod? |
| HONESTY GATE | <any specific Rule-17 trap to avoid> |
```

End of rulebook.
