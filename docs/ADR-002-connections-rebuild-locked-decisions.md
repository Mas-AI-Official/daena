# ADR-002 — Connections / MCP / Plugins / Runtime Rebuild — Locked Decisions

**Status:** Accepted
**Date:** 2026-04-30
**Decided by:** Founder (Masoud Masoori), after Ultraview review of Phase 0-2 deliverables
**Supersedes:** prior conflicting language in `CONNECTIONS_REBUILD_PLAN.md` and `CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` where applicable.
**Inputs:** `docs/Ultraview/ULTRAVIEW_REPORT.md`, founder reply 2026-04-30.

This ADR is the single source of truth for the design decisions surfaced by the Ultraview review. The V2 spec and rebuild plan are amended to match. Where this ADR conflicts with V2 §N, this ADR wins.

---

## D-001 — Per-dimension failure storage (resolves Ultraview B2)

**Decision.** Failure reasons and timestamps are stored **per truth dimension**. A single overwriting `last_failure_*` triple is rejected.

**Rule.**
- Each of the 6 truth dimensions (`detected`, `configured`, `imported`, `reachable`, `authenticated`, `callable`) carries its own:
  - `<dim>_at` timestamp (when last set true)
  - `<dim>_failure_at` timestamp (when last failure observed)
  - `<dim>_failure_reason` text (sanitized human-readable reason)
- A failed `reachable` probe MUST NOT overwrite the most recent `authenticated` failure reason, and vice-versa.
- The API response (`ConnectionV2Out.truth`) MUST expose per-dimension failure reasons keyed by dimension name.
- Implementation may use either explicit columns OR a typed JSONB object `truth_failures: { <dim>: { reason, at } }`. Choice is left to Phase 4a/4b implementer; both shapes are wire-compatible if the Pydantic surface keys by dim.
- For history beyond "most recent failure per dim," use the `audit_entries` table (V2 §17). The connection row tracks current state only.

**Why.** A single triple loses orthogonal failure context. `derive_label()` reads multiple dims; the help text the UI surfaces must match the dim that's actually false.

---

## D-002 — Operation-lock table for in-progress state (resolves Ultraview B3)

**Decision.** `auth_in_progress` and `probe_in_flight` are NOT columns on `connection_v2`. In-progress state is recorded in an operation-lock table with TTL, and `derive_label()` queries the lock state.

**Rule.**
- Add a new table `connection_v2_op_lock`:
  ```python
  class ConnectionOpLock(Base):
      __tablename__ = "connection_v2_op_lock"
      id            = Column(GUID, primary_key=True, default=uuid4)
      connection_id = Column(GUID, ForeignKey("connection_v2.id", ondelete="CASCADE"),
                             nullable=False, index=True)
      op            = Column(String(32), nullable=False)   # 'authenticate' | 'probe' | 'install' | 'oauth_callback'
      acquired_at   = Column(DateTime(timezone=True), nullable=False, default=now_utc)
      expires_at    = Column(DateTime(timezone=True), nullable=False)   # acquired_at + TTL
      owner_token   = Column(String(64), nullable=False)   # caller's request_id; lets the holder release/extend
      __table_args__ = (UniqueConstraint("connection_id", "op", name="uq_op_lock_conn_op"),)
  ```
- Per-op TTL defaults: `authenticate` 600s (matches OAuth state TTL), `probe` 30s, `install` 120s, `oauth_callback` 60s.
- Mirror the lock in Redis for fast reads (`SET NX EX <ttl>`); DB row is the durable source-of-truth and survives Redis flush.
- A background sweeper deletes rows where `expires_at < now()`.
- `derive_label()` resolves in-progress state by joining (or sub-querying) `connection_v2_op_lock` filtered by `op` and `expires_at > now()`. Pseudo-code:
  ```python
  def derive_label(row, active_ops: set[str]) -> str:
      ...
      if 'authenticate' in active_ops: return "auth_pending"
      if 'probe' in active_ops:        return "probing"
      if 'install' in active_ops:      return "installing"
      ...
  ```
- The list view query joins once per request: `LEFT JOIN connection_v2_op_lock l ON l.connection_id = c.id AND l.expires_at > now()`.
- The UI MUST render in-progress badges from the lock state, not from any client-side optimistic flag. Ban: `setState({probing: true})` ahead of backend confirmation.

**Why.** A static boolean on the connection row leaks if the worker crashes mid-op. TTL'd locks self-heal, double as concurrency control (V2 §6 race resolution), and remove the contradictory hidden columns from `derive_label`.

---

## D-003 — Vault V2 is a rewrite, split into Phase 4a + 4b (resolves Ultraview B4)

**Decision.** The current `core/vault.py` is single-key SHA-256 with no per-tenant DEK, no AAD, no envelope structure. V2 vault is a **rewrite, not an extension**. Vault and registry rebuild are split:

**Phase 4a — Vault rewrite (must ship before 4b)**
- New table `secrets` with envelope-encryption columns (V2 §6: `ciphertext`, `nonce`, `tag`, `dek_version`, `kek_version`, `tenant_id`, `class`, `bound_to`).
- New column `tenants.dek_wrapped` (per-tenant DEK, AES-GCM-wrapped under HKDF-derived per-tenant KEK).
- Env-var rename: `VAULT_ENCRYPTION_KEY` (legacy) → `DAENA_KEK` (32B). Both honored during transition; `DAENA_KEK` wins if both set; a deprecation warning is logged when only `VAULT_ENCRYPTION_KEY` is present.
- `RefuseToBoot` if `DAENA_KEK` missing in prod (`DEPLOYMENT_MODE=cloud`); dev mode falls back to placeholder with same warning the legacy vault prints.
- Boot log line: `vault.kek_loaded sha256_prefix=<first 8 hex>` for verification without exposure.
- Migration script: `scripts/migrate_vault_to_v2.py` re-encrypts every existing `ConnectorInstance.credentials_encrypted` row under the new envelope. Dry-run by default; `--apply` flag required to write. Idempotent.
- Gate: 100% of pre-existing encrypted rows readable via legacy AND new code paths during dual-read window. After 7 days zero-drift, legacy reader removed.

**Phase 4b — Registry / token / OAuth / API-key storage**
- Builds on the new vault. Cannot start until Phase 4a passes its gate.
- `oauth_credentials_store.py` and `.daena_oauth_overrides.json` are NOT deleted in Phase 4a. They stay live as fallback until the new vault is proven in Phase 4b.
- `connection_v2.vault_ref` points into the new `secrets` table; legacy rows continue to read from the old store via a compat shim until migration completes.
- Final deletion of `oauth_credentials_store.py` + JSON file moves to Phase 4b's done gate.

**Why.** Treating the vault rewrite as "extend" understates the schema and migration work. Splitting prevents a half-migrated vault from breaking the registry rebuild on top of it.

---

## D-004 — WRAP/compatibility layer for `/runtimes`, no 308 redirect (resolves Ultraview H5/M1)

**Decision.** Old runtimes APIs are NOT redirected. They WRAP the new service-layer functions.

**Rule.**
- `backend/app/api/v1/runtimes.py` keeps its public route surface verbatim.
- Internals are rewritten to call `connection_v2/registry.py` service functions directly. Response shapes are adapted in-process.
- Frontend migrates to `/api/v1/connections?kind=cli_runtime` on its own schedule; old endpoints stay live throughout.
- Deprecation header `Deprecation: true` and `Sunset: <date>` added on every old `/runtimes/*` response once the new endpoints are GA. UI consumes the header and surfaces a one-time admin notice.
- Deletion of `runtimes.py` is moved to a post-V2 cleanup phase (post-§24 sign-off + 14 days zero traffic on the old paths).
- No HTTP 308. No method/body translation surprises for non-browser clients (heartbeat scheduler, `daena-mcp`, founder scripts).

**Why.** 308 silently breaks any client that disables auto-redirect or that sends large bodies. WRAP is reversible, observable, and gives the frontend a calm migration window.

---

## D-005 — Stale ≠ Failed (resolves Ultraview M6)

**Decision.** Stale truth dimensions are NOT rendered as failed. The label set is extended OR a stale overlay is layered separately. Either is acceptable; the V2 spec must pick one and stop conflating them.

**Selected option:** Add explicit derived labels for stale states.
- Extend the label enum from 12 → 14 by adding `healthy_stale` and `degraded_stale`.
- `derive_label()` returns `healthy_stale` when `callable_at` is set AND `(now - callable_at) > CALLABLE_TTL` AND `callable_failure_at` is NULL or older than `callable_at`.
- `derive_label()` returns `degraded_stale` analogously when `healthy_call_ratio <= 0.7` AND TTL exceeded.
- `failed` is reserved for cases where the most recent probe actually failed (per-dim `_failure_at >= _at`).
- UI mapping (V2 §18): `healthy_stale` shows the teal callable pill at 60% opacity with a "Stale — re-probe" subtitle and a "Re-probe" CTA; `degraded_stale` mirrors but with the orange palette. Neither shows red.

**Why.** A stale callable = "we can't promise it's still up, but we don't have evidence it's down" — that is not the same as "the last call failed." Rendering them identically perpetuates the lying-UI category the rebuild is trying to kill.

---

## D-006 — Catalog signing deferred to post-V2 production hardening

**Decision.** Phase 3 is NOT blocked on a production catalog-signing service.

**Rule.**
- For dev / internal use: `connector_catalog.json` ships unsigned. The UI displays a `dev/internal trust state` banner: "Catalog source: unsigned — internal build only."
- No private signing key in the repo. No fake "official" badge that lies about signature status.
- Before public release (post-V2, separate ADR): implement signed catalog, private key in MAS-AI infra signing service (NOT on Daena instances), `DAENA_CATALOG_PUBKEY` baked into the build, sigfail → catalog read-only + tamper banner per V2 §7.
- Open Q #1 (V2 §21) is converted from "blocking" to "scheduled in post-V2 hardening backlog."

**Why.** Catalog signing is genuinely important but its absence does not produce lying UI. The dev/internal banner is honest about the current trust state; that satisfies the no-lie principle without blocking the rebuild.

---

## D-007 — `persisted` merges into `imported` only if imported survives restart (clarifies Ultraview H1)

**Decision.** The 7→6 dimension collapse is locked, with a binding semantic constraint:

**Rule.**
- `imported = true` MUST mean the connection row is persisted in the canonical Daena store and survives backend restart.
- A row that is added to an in-memory cache without a DB write MUST NOT set `imported = true`.
- Lifespan startup MUST NOT initialize `imported = true` for any connection it discovers — only for rows it loads from the DB. Discovered-but-unimported rows are `detected = true, imported = false`.
- Tests: a regression test asserts `restart_backend(); assert imported_count_before == imported_count_after`. CI fails on drift.

**Why.** The original 7-dim model split `imported` (DB row exists) from `persisted` (survives restart). The V2 collapse is correct only if `imported` *guarantees* durability. This rule writes that guarantee into the schema's contract.

---

## D-008 — Per-kind Pydantic discriminated-union validation moves to Phase 4 (resolves Ultraview H4)

**Decision.** `connection_v2.config` JSONB is validated by per-kind Pydantic discriminated unions starting in **Phase 4**, not Phase 7.

**Rule.**
- Phase 4a (vault) and Phase 4b (registry) MUST each ship the discriminated-union validator for the kinds they touch.
- `models/connection_v2.py` exports a discriminator union `ConnectionConfig = Annotated[Union[CliRuntimeConfig, McpStdioConfig, McpHttpConfig, ProviderConfig, OAuthAppConfig, LocalModelConfig, PluginConfig], Field(discriminator='kind')]`.
- Inserts validate against the union at the service layer. Unknown keys are rejected.
- CI test: every `ConnectionKind` enum value has a non-empty `Config` schema; assertion runs in the same suite that already gates `connection_v2` tests.

**Why.** Heterogeneous JSONB without per-kind validation regenerates the `connector_catalog.json` `config_schema: {}` placeholder drift. Backfilling validation across live data is harder than gating inserts.

---

## D-009 — `ConnectionsMcpServers.tsx` is ARCHIVE (resolves Ultraview B1)

**Decision.** `frontend/src/pages/connections/ConnectionsMcpServers.tsx` (54 KB, untracked, zero external imports) is classified ARCHIVE.

**Rule.**
- Same archive treatment as `ConnectionsConnectors.tsx` / `ConnectionsExtensions.tsx` / `ConnectionsRuntimes.tsx`: move to `frontend/src/pages/connections/_archived/` with header comment `// ARCHIVED <date> — DO NOT EDIT — DELETE BY <date+14d>`.
- `git add` the file in its archived location so the move is tracked (currently untracked → first commit lands it as `_archived/ConnectionsMcpServers.tsx`).
- Any unique CRUD UI patterns in the file (Codex-parity toggle / settings / add / delete from the file's docstring) MUST be reviewed and ported into the new V2 `McpServersPanel.tsx` Tools sub-tab BEFORE the archive PR merges.
- File map updated in this round to add the missing row.

**Why.** Phase 3 archive script must classify every file in scope. An unclassified 54 KB file is a Phase-3 blocker on its own.

---

## D-010 — `connection_service.py` is RECLASSIFIED to REWRITE (resolves Ultraview M1)

**Decision.** `backend/app/services/connection_service.py` is REWRITE in Phase 4b, not KEEP.

**Rule.**
- `_status_for_install` (lines 131-143) is the worst single backend offender (P0 #2 and #4 in damage report).
- The function MUST be deleted in the same Phase 4b PR that introduces the 6 truth-field schema. No transition window where both the lying status function and the new truth fields coexist.
- The rest of the file (vault encrypt/decrypt for credentials, per-tool permission CRUD) is consolidated into `connection_v2/registry.py` and `connection_v2/permissions.py`. Original `connection_service.py` deleted at end of Phase 4b.
- File map row updated in this round.

**Why.** Leaving the lying status function alive while the new truth fields exist guarantees a transition window where two truth models compete. The whole point of V2 is to kill that pattern.

---

## D-011 — `daena-mcp` package classified OFFICIAL before npm publish (resolves Ultraview H7)

**Decision.** Daena's own MCP package gets explicit OFFICIAL trust-tier classification before its Phase 9 npm publish.

**Rule.**
- `connector_catalog.json` row for `daena-mcp` (and any future MAS-AI-published MCP/connector) sets `trust_tier: "official"` and includes the publisher signature path.
- The npm publish pipeline signs the artifact with `DAENA_CATALOG_PUBKEY`. Unsigned `daena-mcp` is rejected by V2's catalog loader.
- Regression test: `npm install -g daena-mcp` followed by `POST /api/v1/connections {kind: 'mcp_server', slug: 'daena-mcp'}` does NOT trigger the founder gate when governance mode is BALANCED or UNLEASHED.
- If for any reason the package ships unsigned (dev/internal): force `trust_tier: "unverified"` and accept the founder-gate friction (consistent with D-006 catalog dev banner).

**Why.** Forgetting Daena's own package would make first-install on a fresh tenant impossible without bypass — the rebuild's first user experience would be a permission wall.

---

## D-012 — `mcp_bridge` name disambiguation before any new file lands

**Decision.** The runtime-adapter `mcp_bridge.py` and the bootstrap-source-of-MCP-servers concept are renamed to remove the collision.

**Rule.**
- `backend/app/services/runtimes/adapters/mcp_bridge.py` → `mcp_bridge_runtime_adapter.py` (the adapter that runs an MCP server as a runtime). Update all imports.
- `services/mcp_sync/detector.py` becomes the unique home of "discover MCP servers from CLI configs." There is no second source.
- Done in Phase 4b alongside the registry rewrite (single-PR rename).

**Why.** Two `mcp_bridge` concepts in the tree confuse readers and make `gitnexus impact` searches return mixed results. Rename now, before more files reference either name.

---

## D-013 — `governance_tier` has no silent default; if a default is required, BALANCED-equivalent (`tier=2`) and explicitly documented (resolves Ultraview M7)

**Decision.** `connection_v2.governance_tier` MUST be set explicitly at insert time. If a fallback default is required by ORM constraints, it is `2` (notified post-hoc, BALANCED-equivalent), and the column docstring states the rationale.

**Rule.**
- Service layer functions that insert into `connection_v2` MUST require `governance_tier` as an argument; no kwargs default.
- The SQLAlchemy column may have `default=2` for migration-time inserts only; runtime inserts bypass the default by always passing the value.
- Docstring on the column: `# 0=auto-logged, 1=logged, 2=notified post-hoc (BALANCED default), 3=approval required, 4=founder approval. Service callers MUST pass explicitly; the column default is for Alembic compatibility only.`
- Tenant-mode mapping: UNLEASHED tenants get `0` for OFFICIAL plugins / `2` for COMMUNITY / `3` for UNVERIFIED; BALANCED gets `1/2/3`; GOVERNED gets `2/3/4`. Mapping function lives in `governance_engine`.

**Why.** A silent column default makes the governance posture invisible at the call site. Callers should think about the right tier per insert; the default is a safety net, not a policy.

---

## D-014 — `connector_catalog.json` tracking status (resolves Ultraview M8)

**Decision.** The catalog file MUST be tracked in git before Phase 3 archive begins.

**Rule.**
- Status checked 2026-04-30: `?? backend/app/config/connector_catalog.json` (untracked).
- This commit batch (the doc/spec correction round) commits the catalog into the repo at its current state.
- After commit, `git ls-files backend/app/config/connector_catalog.json` MUST return the path.
- Future updates to the catalog go through normal review.
- Per-category split (V2 §19) deferred to a later phase; the monolithic JSON ships as-is for now to lock the spine.

**Why.** An untracked spine can be lost by `git stash`, `git clean`, branch switch, or accidental delete. V2 calls this catalog "the V2 spine" — losing it would lose 116 connector definitions.

---

## D-016 — `OAuthSetupModal.tsx` is ARCHIVE (Phase 3 supplement, 2026-04-30)

**Decision.** `frontend/src/pages/connections/OAuthSetupModal.tsx` (13 KB, untracked, zero external consumers) is classified ARCHIVE. Moved to `archive/connections_rebuild_20260430_171410/frontend/src/pages/connections/OAuthSetupModal.tsx` in a 1-file follow-up commit to the Phase 3 batch.

**Rule.**
- Same archive treatment as the Phase 3 batch (D-009): no header comment, original file moved as-is, recovery via `mv` reversal.
- Verified zero consumers via four checks: static `from '...OAuthSetupModal'` grep (0 external), dynamic `import(...)` / `React.lazy` grep (0), URL/route grep (0), `gitnexus impact OAuthSetupModal --direction upstream --depth 3` (LOW risk, 0 affected modules / processes).
- The file imported `CONNECTOR_MCP_EQUIVALENT` from `catalog.ts`; after archive, `catalog.ts` has exactly one remaining live consumer (`PluginsCatalogBrowser`). The catalog.ts Phase-7 extraction plan (D-009 deferral) is unaffected.
- The OAuth flow that this modal claimed to provide is now owned by `installFlow.ts` + `components/connections/ConnectorInstallDialog.tsx` (both KEEP). No replacement needed.

**Why.** Found during Ultraview review and Phase 3 archive verification. Same orphan pattern as `ConnectionsMcpServers.tsx` (D-009): file is in tree, has no consumers, would have silently survived Phase 3 if not flagged. Archiving in a tiny follow-up commit (rather than rolling into Phase 7) keeps the live `pages/connections/` tree honest about what is actually mounted.

---

## D-015 — Pre-Phase-3 baseline tests recorded in CONNECTIONS_REBUILD_PLAN.md (resolves Ultraview B5)

**Decision.** Backend pytest, frontend `tsc --noEmit`, frontend `npm run build`, and frontend lint baselines MUST be recorded in `CONNECTIONS_REBUILD_PLAN.md` before any `git mv`.

**Rule.**
- Baselines run on commit `6d3ca5e` (current HEAD on `rebuild-connections-mcp-runtime`) at the time of doc-fix commit.
- Any test count regression in subsequent phases is measured against this baseline.
- Known-failing tests (if any) are listed by name, not aggregated, so future failures can be told apart from pre-existing.
- Recorded in this commit batch.

**Why.** R1 mitigation (V2 risk register) requires a baseline. Without it, "net delta zero" is unmeasurable.

---

## Decisions explicitly NOT changed by this ADR

- 6 truth dimensions (V2 §3 / proposal A §2) — confirmed.
- Single `connection_v2` table for all kinds (V2 §4) — confirmed.
- 5 tabs + 2 drawers UI (V2 §9 / proposal C §1) — confirmed.
- Default new-tenant governance = BALANCED (V2 §8) — confirmed.
- Bridge dispatch BLOCKED in V2 (V2 §12) — confirmed.
- Plugin trust tiers OFFICIAL / COMMUNITY / UNVERIFIED with founder gate on UNVERIFIED in all modes (V2 §7) — confirmed.
- SSE channel for state changes (V2 §10) — confirmed; load test in Open Q #2 stays open.
- Hash-chained append-only audit log (V2 §17) — confirmed.
- 30-day soft-delete grace + founder hard-delete (V2 §16) — confirmed.

---

## Effect on the rebuild plan

The 15 REQUIRED CHANGES BEFORE PHASE 3 from the Ultraview report are addressed by this ADR as follows:

| # | Required change | Resolved by |
|---|---|---|
| 1 | Add `ConnectionsMcpServers.tsx` classification | D-009 + file-map update in this batch |
| 2 | Resolve `last_failure_*` schema contradiction | D-001 |
| 3 | Add `auth_in_progress` / `probe_in_flight` OR rewrite derive_label | D-002 (lock table; columns NOT added) |
| 4 | Rewrite vault migration as Phase 4 P0 | D-003 (split into Phase 4a + 4b) |
| 5 | Run pytest + npm build, record baseline | D-015 |
| 6 | Resolve catalog-signing key custody | D-006 (deferred to post-V2 hardening) |
| 7 | Move per-kind discriminated-union validator to Phase 4 | D-008 |
| 8 | Reclassify `connection_service.py` to REWRITE | D-010 |
| 9 | Document 7→6 dimension collapse | D-007 |
| 10 | Decide `runtimes.py` migration mechanism | D-004 (WRAP, not 308) |
| 11 | Disambiguate `mcp_bridge` name collision | D-012 |
| 12 | `ConnectionsConnectors.tsx` 7-day git-log diff | Done in this batch (no commits in last 7 days; see baseline section of plan) |
| 13 | Add `daena-mcp` OFFICIAL classification | D-011 |
| 14 | `gitnexus impact` per file before archive | Procedural — added to Phase 3 entry criteria in plan |
| 15 | Confirm catalog tracking | D-014 + commit in this batch |

When this ADR is committed and the four amended documents (V2 spec, file map, rebuild plan, this ADR) are in the repo, Phase 3 entry criteria are satisfied **subject to the baseline test results recorded in CONNECTIONS_REBUILD_PLAN.md being acceptable to the founder.**

---

**End of ADR-002.**
