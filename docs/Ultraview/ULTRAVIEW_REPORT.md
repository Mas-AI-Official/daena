# Ultraview Manual Review — `rebuild-connections-mcp-runtime`

**Reviewer:** Claude Code (Opus 4.7), invoked via `/ultrareview` manual mode
**Date:** 2026-04-30
**Branch:** `rebuild-connections-mcp-runtime`
**Baseline commit:** `6d3ca5e connections-rebuild: phase 0-2 deliverables`
**Scope reviewed:**
- `docs/CONNECTIONS_REBUILD_PLAN.md`
- `docs/CONNECTIONS_CURRENT_DAMAGE_REPORT.md`
- `docs/CONNECTIONS_FILE_MAP.md`
- `docs/CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md`
- `docs/_explore/05_lying_ui_findings.md`
- `docs/_explore/06_arch_proposal_{A_system,B_security,C_frontend}.md`
- Live code: `connection_service._status_for_install`, `claude_code.check_health`, `core/vault.py`, `model_router` (primary_mind plumbing), `ConnectionsPage.tsx`, `pages/connections/*` directory listing, lifespan `_periodic_runtime_rescan`

**Mode:** Documentation + spot-verified source. No edits.

---

## Verdict

**DO NOT START PHASE 3 ARCHIVING UNTIL THE BLOCKERS BELOW ARE RESOLVED.**

The 6-boolean truth model, the single `connection_v2` table, the envelope-encrypted vault, the SSE channel, and the 5-tab + 2-drawer UI are all directionally correct and represent a real improvement over today's two-registry / lying-adapter sprawl. The work is not over-designed. But the plan currently has at least four contradictions and one silently missing source file (`ConnectionsMcpServers.tsx`, 54 KB) that will break Phase 3 if executed as written.

The architecture is salvageable with ~1-2 hours of doc fixes before any file moves.

---

## BLOCKERS

These must be resolved before `git mv` runs in Phase 3.

### B1. `ConnectionsMcpServers.tsx` (54 KB) is in the tree but absent from the file map

`frontend/src/pages/connections/ConnectionsMcpServers.tsx` is 53,995 bytes (the largest file in the directory) and was last modified 2026-04-29. It does NOT appear in `CONNECTIONS_FILE_MAP.md` §"pages/connections/". The file map enumerates `ConnectionsConnectors.tsx` / `ConnectionsExtensions.tsx` / `ConnectionsRuntimes.tsx` / `BrowseModal.tsx` / `McpServersPanel.tsx` but skips this one entirely.

Without an explicit KEEP / ARCHIVE / REWRITE decision for this file, Phase 3 archive scripts will leave a 54 KB orphan that may still compile, may still import the legacy `catalog.ts`, and may still be discoverable via dynamic-import or future routing. **Phase 3 cannot start until this file is classified.**

It is not mounted by `pages/ConnectionsPage.tsx` (verified — the shell only renders `MainBrainPanel`, `PluginsCatalogBrowser`, `McpServersPanel`).

### B2. Single `last_failure_*` triple contradicts per-dimension `<dim>_failure_reason`

`CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` §3 says: *"Each carries `<dim>_at` timestamp + `<dim>_failure_reason` text."* — i.e. **6 per-dim failure fields**.

The schema sketch in §4 of the same doc (and in proposal A §11) has only **one** triple: `last_failure_dim` + `last_failure_msg` + `last_failure_at`.

These are not the same model. With a single triple, when `authenticated` fails first and then `reachable` fails 30 seconds later, the auth failure reason is overwritten — but `derive_label()` (§3) still tests both conditions and renders the wrong help text. This is exactly the class of "callable refreshes back to nothing" bug the rebuild is trying to kill.

Pick one. If you go with the single triple, audit log + capability table must back-fill per-dim history. If you go with per-dim columns, the schema sketch needs 12 more fields. Don't ship Alembic migration `006` until this is decided in writing.

### B3. `derive_label()` references columns that don't exist in the schema

§3 reference function reads `row.auth_in_progress` and `row.probe_in_flight`. Neither is in the §4 schema sketch.

Either:
- Add `auth_in_progress: bool` and `probe_in_flight: bool` columns (then they need lock semantics so two concurrent probes don't trample each other), OR
- Replace with `EXISTS(SELECT 1 FROM connection_v2_op_lock WHERE …)` using a separate single-flight table or Redis lock as proposal A §6 already specifies for "single-flight per (tenant_id, connection_id, probe_kind)".

Today the function would crash on attribute access. Phase 4 cannot ship without this resolved.

### B4. Vault is **not** envelope-encrypted today; V2 §6 calls it "extend AES-256-GCM"

`backend/app/core/vault.py` is 143 LOC. It derives a single global key via `SHA-256(VAULT_ENCRYPTION_KEY)`, no per-tenant DEK, no HKDF, no `bound_to`, no `dek_version`, no `kek_version`, no class field, no AAD. Format is `enc:v1:` + base64(`nonce(12) || ciphertext || tag(16)`).

The V2 spec in §6 / proposal B §1 calls this an "extend." It is a **complete rewrite** of:
- The cipher path (AAD + per-tenant DEK + KEK wrapping + envelope serialization)
- The schema (5+ new columns: `nonce`, `tag`, `dek_version`, `kek_version`, `class`, `bound_to`)
- The migration story for already-encrypted creds in `ConnectorInstance.credentials_encrypted`
- The `tenants.dek_wrapped` column (does not exist)
- `RefuseToBoot` semantics on missing `DAENA_KEK` in prod

Without an explicit migration plan for existing encrypted rows AND a plan for the `vault_encryption_key` → `DAENA_KEK` env-var rename, Phase 4 cannot start. **`oauth_credentials_store.py` deletion in Phase 4 is gated on this.**

Also: catalog signing key custody (§21 Open Q #1) is unresolved. ADR-002 lock at the Phase 3 gate cannot happen with an open question of this severity.

### B5. No green test baseline before archive begins

`CONNECTIONS_CURRENT_DAMAGE_REPORT.md` admits the audit pass "crashed on `ncrypto::CSPRNG` and `WinError 10106` before any test or build ran." Risk register R1 ("Phase 4 backend rebuild may break existing 3086 passing tests") cannot be measured against an unknown baseline.

Before any `git mv`, run `pytest backend/tests` and `npm run build` and record the pass/fail counts in `docs/CONNECTIONS_REBUILD_PLAN.md` "baseline" section. Without this, R1's mitigation ("net delta must be zero failures or better") has nothing to compare to.

---

## HIGH RISK

### H1. The 6-boolean truth model collapses 7 source dimensions, undocumented

`CONNECTIONS_CURRENT_DAMAGE_REPORT.md` §"Two-registry problem" cites **7** source dimensions: *"detected / configured / imported / persisted / reachable / callable / authenticated."* V2 §3 has **6** — `persisted` is silently merged into `imported`.

This is probably correct (the catalog already conflates the two), but it is a deliberate semantic decision and it is undocumented. Without explicit ADR text, the next rebuild cycle will surface "but where did `persisted` go?" as a new bug ticket. Add to ADR-002.

### H2. Brain-routing `primary_mind` plumbing is deep and not analyzed in V2

`backend/app/services/model_router.py` references `primary_mind` at 27 sites between lines 297 and 1172, including a debate-mode side path (`_RUNTIME_TO_PROVIDER_DEBATE`, lines 503-508). V2 §15 lists `GET/PUT /api/v1/brain/main` as "verbatim CEO" but does not analyze the contract change.

If `connection_v2.slug` for a CLI runtime no longer matches the `_RUNTIME_TO_PROVIDER` lookup keys, **chat routing breaks silently**. The only failure signal is `route_metadata["primary_mind_available"] = False` and a structlog warn — no user-facing error, no SSE.

Phase 8 ("Brain switching with real routing impact") needs to enumerate every `primary_mind` callsite, lock the slug-to-provider map, and add a regression test that flipping `main_brain` actually changes the chat response provider.

### H3. `useRuntimeRegistry` hook has zero non-self consumers (already dead code)

`grep -rn "useRuntimeRegistry()" frontend/src/` returns one match: a doc-comment inside `RuntimeSwapper.tsx` saying "*typically from useRuntimeRegistry()*." `RuntimeSwapper` itself takes `runtimes` as a prop; nothing actually calls `useRuntimeRegistry()`.

The file map calls this "honest" and "polls /runtimes every 30s" — true of the hook code, false of the runtime behavior because nobody invokes it. The 30-second poll never fires.

This means: the V2 plan to merge `useRuntimeRegistry` + `useConnectorCatalog` → `useConnectionRegistry` is fine, but the damage report's "Frontend honest paths" list is overstating what's actually wired. Don't trust that section of the damage report as a proxy for what's live.

### H4. Single `connection_v2` table will accumulate JSONB drift unless Phase 4 ships per-kind discriminated unions on day one

Proposal A §13 risk #2 calls this out. V2 §4 mentions Pydantic discriminated unions per kind with CI assertion. The migration plan (§19) does not list this validator as a Phase 4 deliverable — it appears only in the Definition of Done (§24, gate 3).

If the validator slips to Phase 7+, the `config` JSONB will already have rows from 6 kinds with 6 schemas. Backfilling validation across heterogeneous live data is harder than gating on insert. **Move the discriminated-union validator to Phase 4 explicitly.**

### H5. `runtimes.py` (620 LOC) → 308 redirect to `/connections?kind=cli_runtime` is fragile

308 redirect spec preserves method + body, but:
- Browsers follow it; many native clients (Python `requests` with `allow_redirects=False`, fetch with `redirect: 'manual'`) do not
- Existing callers may include the founder's own scripts, the heartbeat scheduler, and the `daena-mcp` package
- The damage report mentions `_periodic_runtime_rescan` runs every 60s — if it hits a 308 it will break silently

`grep` the codebase for in-process callers of `/runtimes` before Phase 6 read-flip. If anything internal calls `/runtimes` it should be moved to a service-layer function call, not an HTTP round-trip.

### H6. SSE for ~6000 concurrent streams is explicitly untested (Open Q #2)

V2 §10 quantifies probe load to ~24 probes/min/tenant worst case but defers SSE scale ("HTTP/2 multiplexing limits unknown"). Cloud Run instance-level concurrency limits and the Postgres connection pool used by the SSE handler need an actual load test before Phase 7 frontend rebuild ships against this assumption.

If SSE collapses, fallback is "60s SWR poll" — which is the *opposite* of the no-lie principle (a 60s-old badge is a stale badge). Either accept the staleness explicitly in Section 11 Rule 5 (and shrink the "Stale" subtitle threshold from 5min → 60s+ε), or schedule the load test in Phase 5 dual-write window.

### H7. Plugin trust tier of `daena-mcp` itself is undefined

V2 §7 says UNVERIFIED plugins require founder approval in ALL governance modes. `daena-mcp` is Daena's own package, currently unsigned and unpublished. If it gets installed by a user via `npm install -g`, it will be UNVERIFIED → founder gate → user cannot install it on a fresh tenant without bypass.

Before Phase 9 npm publish: explicitly classify `daena-mcp` as OFFICIAL, sign the published artifact with `DAENA_CATALOG_PUBKEY`, and add a regression test that `npm install -g daena-mcp` followed by Daena registration does NOT trigger the founder gate.

### H8. Phase 3 archive risk: `ConnectionsConnectors.tsx` was edited 2026-04-30 (today)

`ls -la` shows `ConnectionsConnectors.tsx` modified 2026-04-30 10:37 (today's date). The file map says it's "NOT mounted by current ConnectionsPage shell." Both can be true — but if a recent edit was made under the impression it would ship, archiving it loses that work.

Before `git mv`: `git log -p -- frontend/src/pages/connections/ConnectionsConnectors.tsx` for the last 7 days. If recent diffs contain bug fixes (e.g. a 2026-04-30 hotfix), port them into the new tree before archiving.

---

## MEDIUM RISK

### M1. KEEP/ARCHIVE decisions are mostly correct but file map misclassifies activity

- **CORRECT ARCHIVE candidates:** `ConnectionsConnectors.tsx`, `ConnectionsExtensions.tsx`, `ConnectionsRuntimes.tsx`, `BrowseModal.tsx`, `oauth.ts`, `shared.tsx`. Verified: `pages/ConnectionsPage.tsx` does not import any of them.
- **INCORRECT KEEP** (per H3): `useRuntimeRegistry.ts` is unused.
- **MISSING DECISION** (per B1): `ConnectionsMcpServers.tsx` (54 KB).
- **REWRITE rather than KEEP**: `connection_service._status_for_install` is the worst single backend offender (P0 #2, #4 in damage report) — V2 says "removed (replaced by 6 truth fields)" but `connection_service.py` itself is still marked `KEEP` in the file map. The file should be marked `REWRITE` with `_status_for_install` flagged for deletion, otherwise Phase 4 risks leaving the lying function in place.
- **WRAP rather than KEEP** for `runtimes.py`: file map says WRAP (correct), V2 §13 says 308-redirect (different mechanism). Pick one.

### M2. `mcp_bridge.py` has a name collision with itself (adapter vs sync source)

`mcp_bridge.py` is BOTH a runtime adapter (`backend/app/services/runtimes/adapters/mcp_bridge.py`) AND it's referenced by the bootstrap path that is being folded into `mcp_sync/detector.py`. After Phase 4-5, there will be two distinct `mcp_bridge` concepts in the tree — one as a runtime, one as detector glue. Disambiguate names now (e.g. `mcp_bridge_adapter.py`).

### M3. Tenant isolation enforcement is plumbed through ORM listener, but `Path.home()` detector path is the wrong fix

V2 §5 says "cloud tenants get `detect_remote_mcps_for_tenant(tenant_id)` from curated catalog + uploaded configs only." There is no API spec for HOW configs are uploaded by a tenant, no schema for `tenant.synced_cli_configs`, and no UI for it.

In practice, this either (a) stays Windows-/dev-only forever, or (b) becomes an attack surface (tenant uploads a malicious MCP config). Add to Phase 7 backlog: explicit upload endpoint, schema, governance tier, and quota.

### M4. OAuth state in Redis assumes Redis is up

V2 §6 moves `_MCP_OAUTH_STATES` and `_oauth_states` into Redis with TTL=600s. The current lifespan check on Redis is graceful-fallback (per the project memory). If Redis goes down mid-OAuth, the user gets "state expired" — correct UX, but the Slack/email notification path (this is OAuth, the user is staring at a popup) is not specified. Probably fine; flag for Phase 5.

### M5. Probe rate limit (10/min, burst 30) is per-tenant per-connector, not global

V2 §14 specifies per-tenant per-connector limit. With ~120 connections per tenant, a malicious tenant could legitimately drive 1200 probes/min globally. Add a global probe budget at the AllowlistTransport layer, not just per-tenant.

### M6. `derive_label()` does not surface `staleness` distinctly from `failed`

§3 reference returns `"failed"` if `(now() - row.callable_at) > CALLABLE_TTL`. But TTL-stale ≠ failed: the connection might still be callable, we just haven't re-checked. Today's Frontend §11 Rule 5 says stale renders dim with "Stale" subtitle — that requires a `staleness_seconds` field on the API output (V2 §4 has it). Backend `derive_label` returning `"failed"` for stale will lock the UI into showing red, which contradicts the "stale dim" UX rule.

Either change derive_label to return `"healthy_stale"` / `"degraded_stale"` (now you have 14 labels not 11) OR have the UI compute "stale" overlay independently of label. Document the choice.

### M7. `governance_tier` SmallInteger default=2 — meaning of 2?

`ConnectionV2.governance_tier = Column(SmallInteger, default=2)`. Section 8 of V2 says "Tier 0-1 logged, Tier 2 notified, Tier 3+ approval." So `2` = "notified post-hoc." Why is that the default? This is a per-tenant policy decision; default 2 silently opts every connection into post-hoc notification. The risk-tolerant founder might want default 0; the risk-averse enterprise tenant default 3. Make it `Column(SmallInteger, nullable=False)` with no default and force every insert to specify; or document why 2 is the org-wide default.

### M8. `connector_catalog.json` (3352 lines, version `2026-04-29.3`) is "untracked" per damage report

If untracked, `git mv` won't see it; if .gitignore'd, archive script silently misses it; if just unstaged, anyone running `git stash` loses it. Before Phase 3: `git status` and either commit it or document its non-tracked status with a recovery procedure.

### M9. No specified order for SSE event delivery

V2 §10 lists SSE event types. If `probe_completed` fires before `connection_state_changed` (or vice versa), the UI may render "Failed" then immediately "Healthy" — acceptable UX flicker. But during install, the order of `oauth_callback_completed` vs `connection_state_changed` matters for the modal close timing. Spec event ordering or specify "fire-and-forget; UI must be order-independent."

### M10. `MCPTool` defined twice with different shapes (P1 #6 in damage report) is not assigned a fix in V2

Damage report P1 #6: `services/mcp/server.py` and `services/mcp_registry.py` both define `MCPTool`. V2 §19 marks both files KEEP without consolidating. This will continue to cause "easy to confuse on import" — pick one canonical location in Phase 4.

---

## SAFE TO PROCEED

These elements are well-designed and ready as-specified.

- **6 booleans + 11 derived labels** is genuinely safer than the original 16-state enum. Council disagreement #1 ruled correctly. (Caveat: see B2/B3/H1.)
- **Single envelope-encrypted vault + per-tenant DEK** is the right shape. (Caveat: see B4 — design is right, plan calls it "extend" when it's a rewrite.)
- **3-tier plugin trust (OFFICIAL/COMMUNITY/UNVERIFIED) with founder gate on UNVERIFIED in all modes** correctly resolves the friendly-demo RCE risk. (Caveat: H7 — Daena's own package needs OFFICIAL classification before npm publish.)
- **Default new-tenant governance = BALANCED** is the right call. UNLEASHED for first 24h is the documented breach window.
- **5 tabs + 2 drawers UI** is enough; 10-subtab CEO original conflated row-level concerns with nav. C wins council on this.
- **Per-kind probe contract requiring END capability call to succeed (not "binary exists")** kills 5 lying CLI adapters in one stroke. This is the single highest-impact fix in V2.
- **`_status_for_install` removal** is correct.
- **ESLint `no-derived-state` rule + single `stateToBadge` mapper** codifies the no-lie principle in CI.
- **Hash-chained append-only audit log with nightly walk** is reasonable; retention tiers are sensible.
- **Soft-delete + 30-day grace + founder hard-delete** is the right decommission posture.
- **Bridge dispatch BLOCKED in V2 with read-only inbound CLI** is correct and necessary.
- **Two-registry collapse onto `connection_v2`** is the right architectural call. Two parallel registries is the disease; one canonical store is the cure.
- **MCP detection unification (`mcp_bootstrap.py` folded into `mcp_sync/detector.py`)** is correct.

---

## REQUIRED CHANGES BEFORE PHASE 3

In dependency order. None of these require code edits — only doc + ADR updates.

1. **Add `ConnectionsMcpServers.tsx` (54 KB) to `CONNECTIONS_FILE_MAP.md`** with explicit KEEP / ARCHIVE / REWRITE decision and rationale. (B1)
2. **Resolve `last_failure_*` schema contradiction** in `CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` — pick per-dim columns OR a single triple, document why, update the §4 SQLAlchemy sketch. (B2)
3. **Add `auth_in_progress` and `probe_in_flight` to schema** OR rewrite `derive_label()` to query the lock table / Redis. (B3)
4. **Rewrite `core/vault.py` migration plan as a Phase 4 P0 task**, not "extend." Include: schema migration for existing `ConnectorInstance.credentials_encrypted` rows, env-var rename plan (`vault_encryption_key` → `DAENA_KEK`), `tenants.dek_wrapped` column add, `RefuseToBoot` semantics, hash-of-KEK boot log line. (B4)
5. **Run pytest + npm build, record baseline counts** in `CONNECTIONS_REBUILD_PLAN.md` "Baseline" section before any archive operation. (B5)
6. **Resolve catalog-signing key custody (Open Q #1)** before ADR-002 lock. Either propose the separate signing service architecture as a Phase-9 deliverable or defer catalog signing to Phase 11+ and ship V2 unsigned with banner.
7. **Move `connection_v2.config` per-kind Pydantic discriminated-union validator from Phase-7 gate to Phase-4 deliverable.** (H4)
8. **Reclassify `connection_service.py` from KEEP to REWRITE** in the file map; flag `_status_for_install` for deletion in the same Phase 4 PR that introduces the 6 truth-field schema. (M1)
9. **Document the 7→6 dimension collapse** (`persisted` merged into `imported`) explicitly in ADR-002. (H1)
10. **Decide `runtimes.py` migration mechanism**: 308 redirect (V2 §13) vs WRAP layer (file map). Pick one, audit internal callers before Phase 6. (H5/M1)
11. **Disambiguate `mcp_bridge` name collision** before any new file lands. (M2)
12. **Add `ConnectionsConnectors.tsx` 7-day git-log diff review** to the Phase-3 archive script. Port any 2026-04-30 fixes forward before `git mv`. (H8)
13. **Add `daena-mcp` OFFICIAL trust-tier classification** to the catalog before Phase 9 npm publish. (H7)
14. **Run `gitnexus impact` per file in the ARCHIVE list** before Phase 3 `git mv` to catch dynamic-import callers `grep` would miss.
15. **Confirm `connector_catalog.json` (3352 LOC, v2026-04-29.3) is committed,** not untracked. Record commit SHA in the rebuild plan. (M8)

---

## OPTIONAL CHANGES LATER

1. Per-kind discriminated-union docs in Storybook so the Phase 4-5 implementer doesn't need to chase the V2 spec for `config` shape per kind.
2. Load test: 50 tenants × 120 connections × SSE, before Phase 7 frontend rebuild ships against the assumption it scales. (H6)
3. Replace `useRuntimeRegistry` polling with the new SSE channel (currently dead code per H3 — not a Phase 4 priority since nobody depends on it).
4. Spec the tenant `synced_cli_configs` upload API for cloud-mode MCP detection. Tier into Phase 7 backlog. (M3)
5. Add a global probe budget at AllowlistTransport, complementing the per-tenant rate limit. (M5)
6. Resolve `derive_label` "stale ≠ failed" UX (M6) — either expand to 14 labels with explicit `_stale` variants or document the UI-side overlay.
7. Make `governance_tier` non-defaulting and force callers to specify at insert time. (M7)
8. Spec SSE event ordering, especially `oauth_callback_completed` vs `connection_state_changed`. (M9)
9. Consolidate the duplicate `MCPTool` definition in Phase 4. (M10)
10. Catalog signing key — propose the separate MAS-AI infra signing service architecture as a Phase-11 ADR.
11. Mobile/responsive pass for `/connections` (V2 §2 explicitly defers; document target version).

---

## Concrete sign-off ask

Founder: please respond with:
- Yes / No / Modify on each of items 1-15 in REQUIRED CHANGES BEFORE PHASE 3.
- Decision on B2 (per-dim vs single-triple failure storage).
- Decision on B4 vault rewrite scope (Phase 4 P0 vs split into Phase 4a vault + Phase 4b registry).
- Approval to record pytest + npm build baseline before Phase 3 starts.

Once those are written into `CONNECTIONS_REBUILD_PLAN.md` and `CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md`, Phase 3 is safe to begin.

---

**End of Ultraview report.**
