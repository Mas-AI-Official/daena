# Connections / MCP / Plugins / Runtime Architecture V2

**Status:** Draft 1 -- chairman synthesis (2026-04-30, 3 council proposers)
**Replaces:** prior connections architecture (see `CONNECTIONS_CURRENT_DAMAGE_REPORT.md`)
**Sources:** `docs/_explore/06_arch_proposal_{A_system,B_security,C_frontend}.md`
**Inventory:** `CONNECTIONS_FILE_MAP.md` (action plan §19)

---

## 1. Goals

1. One row, one truth -- no JSON-on-disk, no registry drift, no name-string "alive" match (A§1).
2. Probes do real I/O -- `callable=true` requires authenticated round-trip in TTL (A§4).
3. 6-boolean truth model IS schema; UI labels derived (D1, A§2).
4. Tenant isolation structural (ORM auto-inject), not policy (D3, B§2).
5. One envelope-encrypted vault; kill `oauth_credentials_store.py` (D4, B§1).
6. Plugin trust tiered OFFICIAL/COMMUNITY/UNVERIFIED + governance matrix (D5, B§4).
7. Default new-tenant governance = BALANCED (D6, B§15).
8. Page tree = 5 tabs + 2 drawers (D7, C§1).
9. Real-time = SSE-backed when advertised (D8, CLAUDE§17).
10. No-lie rule enforced via single mapper + ESLint (D9, C§5).
11. Bridge dispatch BLOCKED in V2; inbound CLIs read-only (D10, B§15).
12. Every Phase 4-9 file traces back to a section here.

## 2. Non-goals

Bridge dispatch enablement (Phase 2); VSCode/Cursor/Cline/Continue/Zed MCP detection (Phase 7); macOS/Linux Claude Desktop discovery beyond current detector; `daena-mcp` npm publish (Phase 8); Quintessence DCP / Skill Refinery / NBMF / Daena-as-MCP-server refactors (KEEP); new OAuth providers beyond 6 wired; mobile/tablet layouts; Asset Shield / SecurityGate refactors (HANDS OFF); permanent deletion of `var/runtime_truth.json` (migrated then archived).

## 3. Lifecycle truth model (D1)

### Six boolean dimensions (not 16 states)

| Dim | Meaning | Sets true when |
|---|---|---|
| `detected` | Evidence it exists | FS scan / npm hit / CLI config parse |
| `configured` | Operator supplied required config | Form submission persisted |
| `imported` | DB row exists for this tenant | Row insert |
| `reachable` | Network/IPC handshake OK | TCP/HTTP/stdio open in TTL |
| `authenticated` | Auth current, not expired | Probe round-trip w/ auth in TTL |
| `callable` | Real capability invocation succeeded | Per-kind probe (§14) succeeds in TTL |

Each carries `<dim>_at` timestamp + `<dim>_failure_reason` text.

### 11 derived labels (UI-facing, NOT persisted)

`unknown`, `installable`, `installing`, `needs_auth`, `auth_pending`, `needs_config`, `probing`, `healthy`, `degraded`, `failed`, `disabled`, `archived` (12 total; `archived` is soft-delete state).

Pure-function output of `derive_label(row)`. Frontend never writes a label. ESLint rule blocks `state = '...'` assignments (D9).

### State graph

```
detected -> needs_config -> configured -> needs_auth -> auth_pending -> probing
                                                                          |
                       healthy <-- degraded <-- failed <------------------+
                          |          ^             ^
                          +--> disabled --> archived (D14 soft-delete)
```

### `derive_label()` reference

```python
def derive_label(row: ConnectionV2) -> str:
    if row.archived: return "archived"
    if row.disabled: return "disabled"
    if not row.detected: return "unknown"
    if not row.configured: return "needs_config"
    if not row.imported: return "installable"
    if row.last_op == "install" and not row.reachable: return "installing"
    if not row.reachable: return "failed"
    if row.requires_auth and not row.authenticated:
        return "auth_pending" if row.auth_in_progress else "needs_auth"
    if row.probe_in_flight: return "probing"
    if row.callable and (now() - row.callable_at) < CALLABLE_TTL:
        return "healthy" if row.healthy_call_ratio > 0.7 else "degraded"
    return "failed"
```

**Rejected: 16-state enum.** A pushed back; monolithic enum conflates orthogonal axes (install vs auth vs reach) and produced string-prefix badges (`McpServersPanel.tsx:296`). 6 booleans + derived labels is the cure.

## 4. ConnectionRegistryV2 schema (D2)

One SQLAlchemy table covers all 6 kinds. Postgres prod, SQLite dev. Reuse Alembic. Migration: `006_connection_v2.py`.

```python
# backend/app/models/connection_v2.py
class ConnectionKind(str, Enum):  # CLI_RUNTIME|MCP_SERVER|PROVIDER|PLUGIN|OAUTH_APP|LOCAL_MODEL
class AuthMethod(str, Enum):      # NONE|API_TOKEN|OAUTH_MANAGED|MCP_REMOTE_OAUTH|SUBSCRIPTION
class TrustTier(str, Enum):       # OFFICIAL|COMMUNITY|UNVERIFIED

class ConnectionV2(Base, TenantMixin, TimestampMixin):
    __tablename__ = "connection_v2"
    id = Column(GUID, primary_key=True, default=uuid4)
    tenant_id = Column(GUID, ForeignKey("tenants.id"), nullable=False, index=True)
    kind = Column(Enum(ConnectionKind), nullable=False, index=True)
    slug = Column(String(128), nullable=False); display_name = Column(String(256), nullable=False)
    canonical_key = Column(String(64), nullable=False, index=True)
    auth_method = Column(Enum(AuthMethod), nullable=False)
    trust_tier = Column(Enum(TrustTier), nullable=False, default=TrustTier.OFFICIAL)
    config = Column(JSONBCompat, nullable=False, default=dict); vault_ref = Column(String(256))
    # 6 truth dims: each Boolean(default=False) + <dim>_at DateTime(timezone=True)
    #   detected | configured | imported | reachable | authenticated | callable
    last_failure_dim = Column(String(32)); last_failure_msg = Column(Text)
    last_failure_at = Column(DateTime(timezone=True))
    last_op = Column(String(32))  # discover|import|install|configure|authenticate|probe
    archived = Column(Boolean, default=False); archived_at = Column(DateTime(timezone=True))
    governance_tier = Column(SmallInteger, default=2); disabled = Column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("tenant_id","kind","slug", name="uq_conn_v2_tenant_kind_slug"),
        Index("ix_conn_v2_tenant_callable","tenant_id","callable"),
        Index("ix_conn_v2_tenant_kind","tenant_id","kind"))

class ConnectionCapability(Base):  # mcp_tool | provider_model | cli_command
    __tablename__ = "connection_v2_capability"
    id = Column(GUID, primary_key=True, default=uuid4)
    connection_id = Column(GUID, ForeignKey("connection_v2.id", ondelete="CASCADE"), index=True)
    kind = Column(String(32)); name = Column(String(256)); spec = Column(JSONBCompat, default=dict)
    discovered_at = Column(DateTime(timezone=True)); last_seen_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("connection_id","kind","name"),)
```

Pydantic `ConnectionV2Out` = 6 truth dims + label + capabilities count + `staleness_seconds` (A§11).

**Sample row (Cloudflare MCP, healthy):**
```json
{"id":"01926e7f-...","kind":"mcp_server","slug":"cloudflare-mcp","trust_tier":"official",
 "auth_method":"mcp_remote_oauth","vault_ref":"secrets/.../oauth_token/01926e7f-...",
 "config":{"transport":"http","url":"https://mcp.cloudflare.com/sse"},
 "detected":true,"configured":true,"imported":true,
 "reachable":true,"authenticated":true,"callable":true,
 "callable_at":"2026-04-30T19:42:11Z","label":"healthy",
 "capabilities_count":12,"staleness_seconds":12}
```

## 5. Tenant isolation (D3)

Three layers; ORM is load-bearing. (1) **ORM listener** (`core/db/tenant_guard.py`): SQLAlchemy `before_compile` on any `TenantMixin` query; missing `tenant_id` predicate auto-injected from `request.state.principal.tenant_id`; no principal -> `MissingTenantContextError`. (2) **Middleware** (`TenantContextMiddleware`): parses JWT, sets `Principal(user_id, tenant_id, role)` in `contextvars.ContextVar`; async tasks inherit. (3) **Test gate**: pytest fixture captures emitted SQL; any `TenantMixin` query missing `tenant_id` fails.

**Bypass:** `with TenantBypass(reason="...", founder=True): ...` -- requires `principal.role==FOUNDER`, emits `tenant_bypass.entered` audit row, grep-able.

**Cloud Run gap:** `mcp_sync/detector.py` reads `Path.home()` -- container's home, not tenant's. V2 splits: `detect_local_mcps()` gated on `DEPLOYMENT_MODE=local`; cloud tenants get `detect_remote_mcps_for_tenant(tenant_id)` from curated catalog + uploaded configs only.

## 6. Secret vault (D4)

One vault: `backend/app/core/vault.py` (extend AES-256-GCM). Delete `oauth_credentials_store.py` + `.daena_oauth_overrides.json`. Move `_MCP_OAUTH_STATES` + `_oauth_states` -> Redis TTL=600s.

**Envelope encryption:**
```
DAENA_KEK (env, 32B) -> per-tenant KEK = HKDF-SHA256(KEK, salt=tenant_id, info="daena-v2-kek")
                     -> per-tenant DEK = 32B random, in tenants.dek_wrapped (AES-GCM under KEK)
                     -> secret = AES-256-GCM(plaintext, key=DEK, nonce=random_96b,
                                              aad=class || tenant_id || row_id)
```

`secrets` cols: `ciphertext BYTEA, nonce(12), tag(16), dek_version, kek_version, tenant_id, class, bound_to`. Class: `oauth_token | oauth_client_secret | api_key | mcp_env_var | bridge_bearer`.

**KEK custody / rotation:** `DAENA_KEK` in `.env` (dev) / Cloud Run secret (prod). Process memory only. Missing on prod boot = refuse. **Hash-of-KEK printed at boot** (B§1). DEK per-tenant rotation operator-gated online; KEK system-wide founder-gated quarterly.

**Logging:** `vault.decrypt()` emits `vault.access` audit row with `tenant_id/secret_id/class/caller_module/caller_function/request_id`. NEVER plaintext/ciphertext. Anomaly detector flags >100 decrypts/min/tenant.

## 7. Plugin trust tiers (D5)

| Tier | Definition | UNLEASHED | BALANCED | GOVERNED |
|---|---|---|---|---|
| OFFICIAL | Daena curated, signed via `DAENA_CATALOG_PUBKEY` | auto | auto | operator |
| COMMUNITY | npm verified-publisher sig OR git URL verified author | auto | operator | founder |
| UNVERIFIED | Arbitrary GitHub URL, unsigned npm, raw command | **founder** | founder | founder |

UNVERIFIED has NO exception -- chairman ratifies B§15#2 (malicious manifest harvests vault tokens during friendly demo).

**Catalog signing:** `connector_catalog_signed.json` -- sigstore-style sig over canonical JSON. Verified at startup against `backend/app/security/catalog_pubkey.pem`. Sig fail -> catalog read-only + UI banner "Catalog tamper detected".

**Skill packs** (`auth_method=none AND installable=false`): render "Skill pack" chip. NO install button. Schema rejects rows missing explicit `auth_method` at startup. Regression test asserts no auto-default to `api_token` (B§9).

## 8. Default governance mode (D6)

**New tenants default to BALANCED, not UNLEASHED.** UNLEASHED requires founder-gated opt-in. Rationale: first-24-72h breach risk is highest (no baselines, untrained operator, no policy library). BALANCED auto-allows reads, prompts on writes/installs. `governance_mode.changed` audit (Tier 3) on any flip.

## 9. Page tree (D7)

5 tabs + 2 drawers replaces 10-subtab sprawl (C§1).

| # | Tab | Purpose | Replaces |
|---|---|---|---|
| 1 | **Brain** | Primary mind + fallback chain + Local Ollama/llama-server inline + SSE health-events ticker. | MainBrainPanel + Local Ollama (SettingsModelsRuntimes) + CEO Brain Routing + Local Runtimes + Health Events |
| 2 | **Catalog** | Browse 116 connectors + filter + install. Card grid. | PluginsCatalogBrowser + CEO Catalog + Plugins (`kind=plugin`) |
| 3 | **Installed** | Unified table: MCP/plugin/provider/runtime/OAuth. Pill, last-checked, probe button. | CEO Overview + Installed |
| 4 | **MCP Servers** | Power view; per-tool drilldown (C§13). Bridge BLOCKED banner. | McpServersPanel + CEO MCP Servers |
| 5 | **API Keys** | Provider keys (9 providers). Save/rotate/test. | SettingsModelsRuntimes form + CEO API Providers |

**Drawers** (preserve table context, not routes): **Connection Detail** opens from any Catalog/Installed row; sub-tabs Overview/Auth/Tools/Skills/Permissions/Diagnostics/Audit; default tab=Auth when `label in {needs_auth, auth_pending}`. **Audit Trail** filtered to selected `connection_id`, 50 most recent.

CEO 10-subtab -> V2: Overview->T3 header; Catalog->T2; Installed->T3; MCP Servers->T4; Plugins->T2/3; Skills->Detail drawer; API Providers->T5; Local Runtimes->T1; Brain Routing->T1; Health Events->T1 footer.

## 10. Real-time updates (D8)

**One SSE channel:** `GET /api/v1/connections/events` (tenant-scoped, JSON-line frames).

| Signal | Channel | Latency | Fallback |
|---|---|---|---|
| `connection_state_changed` (any dim flipped) | SSE | <=2s | 60s SWR poll |
| `probe_completed` `{id, success, duration_ms}` | SSE | <=2s | 60s SWR poll |
| `oauth_callback_completed` | SSE + `window.opener.postMessage` | <=3s | window.opener |
| `connection_install_progress` `{step, pct, msg}` | SSE | <=1s/step | none (foreground) |
| Catalog list (116 rows) | HTTP on mount+focus, 5min cache | n/a | existing cache |
| Audit log entries | Lazy on drawer open | drawer+1s | none |

**Probe load (A§13#3):** ~120 conns/tenant x 1 probe/5min = 24 probes/min/tenant worst case. Mitigations: exponential backoff to 1h on consecutive failures; batch-by-host; per-tenant rate limiter; `# BACKGROUND PATH ONLY` markers.

**Footer indicator (C§15#2):** Every Connections page footer shows green "live" or amber "reconnecting (last update 47s ago)". User can never be lulled into thinking a stale badge is fresh.

**Sample SSE payloads:**
```
event: connection_state_changed
data: {"connection_id":"...","label":"healthy",
       "truth":{"reachable":true,"authenticated":true,"callable":true,
                "callable_at":"..."},"staleness_seconds":0}
event: probe_completed
data: {"connection_id":"...","success":true,"duration_ms":342,
       "capability_diff":{"added":["new_tool"],"removed":[]}}
```

## 11. The codified no-lie principle (D9)

Five rules (C§5), each enforced in code review:

1. **Badge is pure function of `row.label`.** Single mapper at `lib/connectionState.ts`: `stateToBadge(label)` exhaustive switch over all 12 labels (§18); TS enforces completeness; `default: const _e:never = label; throw` traps drift. **Forbidden:** `name.includes(...)`, `package.has(...)`, `Object.keys(probe).length>0`. ESLint rule `no-derived-state` blocks; CI fails.
2. **State set ONLY by backend.** Frontend never writes `row.callable=true` after probe. SSE delivers backend-stamped truth dims; UI re-renders.
3. **Optimistic-success toasts banned for state-changing ops.** `SettingsGeneral.tsx:269` ("Your data has been imported!") banned. Toast fires from response handler, not click handler; for installs, spinner persists until SSE confirms.
4. **Unknown states render "Unknown -- re-probe".** `RuntimeSwapper.tsx:29-43` defaulted unknown to "online" -- banned. Out-of-enum labels render `<UnknownBadge />` with re-probe CTA; never gold/green by default.
5. **`last_checked_at` mandatory on every pill.** Missing or >5min -> dim to 60% + "Stale" subtitle.

**Enforcement:** `lib/connectionState.ts` + `eslint-rules/no-derived-state.js` + `components/connections/StatusPill.tsx` (only badge) + `lib/errorSanitizer.ts` (backend errors -> UI text per C§9).

## 12. Bridge dispatch security (D10)

`daena-mcp --bridge` opens outbound WS to `wss://daena.mas-ai.co` scaffolded to accept dispatched calls. **Without per-call signed nonces + tenant-bound bearer + operator approval queue, this is RCE across user fleet** (B§15#1).

V2: (1) Backend WS handler **refuses inbound dispatch** regardless of handshake; returns `{"error":"bridge_dispatch_blocked","phase":"v2"}`. (2) Inbound CLI hosts **READ state** only (`daena_status`, `daena_recall_memory`, `daena_governance_check`, `daena_audit_query`). (3) Inbound CLI hosts **CANNOT INVOKE write tools**. Phase 2 unblock requires per-call HMAC nonces (single-use 10s TTL) + tenant-bound bearer (separate from MCP tokens) + operator approval queue + founder gate first 30 days. (4) UI: MCP Servers tab banner "Bridge dispatch: BLOCKED -- Phase 2 pending"; Bridge column shows "Read-only".

## 13. Two-registry collapse (D11)

| Old | New |
|---|---|
| `runtime_truth_registry.py` (JSON) | Promoted; logic re-plumbed onto `connection_v2`. Renamed `connection_v2/registry.py`. |
| `runtimes/registry.py` (in-memory) | Demoted to LRU adapter cache; reads `connection_v2 WHERE kind=cli_runtime`. |
| `mcp_bootstrap.py` | Folded into `mcp_sync/detector.py` -- one detector, startup AND on-demand. |
| `api/v1/runtime.py` (singular) | Promoted, merged into `connections.py`. |
| `api/v1/runtimes.py` (plural, 620 LOC) | 308-redirect to `/connections?kind=cli_runtime`. Deleted next release. |
| `useRuntimeRegistry.ts` + `useConnectorCatalog.ts` | One hook: `useConnectionRegistry.ts`. |

**Migration timeline:** Phase 4 new table+service+migration (gate tests pass); Phase 5 dual-write, JSON primary read (gate daily reconciliation); Phase 6 flip read to `connection_v2`, JSON write 1 release fallback (gate 7-day zero drift); Phase 7 drop JSON write, delete `var/runtime_truth.json` (gate reconciliation green); Phase 8 replace `RuntimeRegistry` -> `ConnectionRegistry.get_runtime(slug)`, archive old file (gate callers migrated). Phase 7 is irreversible; daily reconciliation cron emits hard alert on drift.

## 14. Probe contract per kind (D12)

Headline change. `success` requires END capability call to succeed, not "process started." Five lying CLI adapters (`claude_code.py:182-186`, `codex.py:93-97`, `gemini_cli.py:59-63`, `grok_cli.py:49-53`, `mcp_bridge.py:88-93`) rewritten.

| Kind | `detected` | `reachable` | `authenticated` | `callable` |
|---|---|---|---|---|
| **CLI runtime** | `shutil.which(bin)` | `<bin> --version` exit 0 in 5s | `<bin> -p "ping"` valid JSON in 10s | Real LLM round-trip, 1-token, against bound config |
| **MCP stdio** | Config entry exists | `stdio_client(...)` opens | MCP `initialize` OK | `tools/list` returns >=0 tools in 5s |
| **MCP HTTP/SSE** | URL configured | TCP connect | HTTP 200 on `/health` or first SSE event | `tools/list` JSON-RPC returns >=0 tools |
| **API provider** | Key in vault | TCP connect | `/v1/models` returns 200 | Smallest chat completion (e.g. Anthropic `max_tokens=1`) succeeds |
| **OAuth app** | Provider config + client_id | Authorize URL resolves | Token exchange OK | First authenticated API call succeeds |
| **Local LLM** | Endpoint configured | TCP connect | `/api/tags` or `/v1/models` 200 | One-token generation succeeds |
| **Plugin (skill pack)** | SKILL.md present | n/a | n/a | render "Skill pack (not callable)" |

**Hard rule:** `callable=True` requires authenticated round-trip recorded with timestamp. No exceptions.

**Probe blast radius (B§5):** URL allowlist per connector via `auth.allowed_egress_hosts`; `httpx.Client(transport=AllowlistTransport(hosts=...))`. Network-layer block: `127.0.0.1`, RFC1918, `169.254.0.0/16`, `metadata.google.internal`. DNS post-resolve check defends against rebinding. Rate limit per-tenant per-connector: 10/min, burst 30. Audit row every probe.

## 15. API surface (D13)

CEO routes adopted with 4 refinements (#1 import+install merge w/ `mode` field; #2 probe+test merge -- a probe IS a test; #3 SSE replaces polling `?since=`; #4 `mcp_server.py` + `mcp_sync.py` collapse to one router `mcp.py` -- Daena-as-MCP-server stays `/mcp/*`, detector `/mcp/sync/*`).

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/connections` | List, `?kind=` filter. Replaces `/runtimes`, `/runtime/truth`, `/mcp-registry`, `/mcp-sync/detected`. |
| GET | `/api/v1/connections/{id}` | Detail: truth + capabilities + last 50 audit. |
| POST | `/api/v1/connections/discover` | Trigger discovery; returns count of new `detected`. |
| POST | `/api/v1/connections` | **Merged import+install**; body `{mode:"import"\|"install", kind, slug, config}`. Idempotency key required. |
| POST | `/api/v1/connections/{id}/probe` | **Merged probe+test**; live, busts TTL. 2s timeout. |
| POST | `/api/v1/connections/{id}/authenticate` | OAuth: returns authorize URL. api_token: validates inline. |
| POST | `/api/v1/connections/oauth/callback` | `state` from Redis; persists token to vault. |
| DELETE | `/api/v1/connections/{id}` | Soft-archive (D14); `?hard=true` requires founder + 30-day grace. |
| POST | `/api/v1/connections/{id}/rediscover-capabilities` | Force refresh. |
| GET | `/api/v1/connections/{id}/audit` | Filtered, paginated. |
| GET | `/api/v1/connections/capabilities` | `?kind=mcp_tool&name=X` cross-conn lookup. |
| GET | `/api/v1/connections/events` | **SSE stream** (D8). |
| GET/PUT | `/api/v1/brain/main` | Get/set primary mind. Verbatim CEO. |
| GET | `/api/v1/brain/runtimes` | List runtimes for Brain tab. Verbatim. |
| GET | `/api/v1/brain/fallback-chain` | Fallback chain visualization. Verbatim. |

Versioning: stays at `/api/v1`. The 6-boolean truth model is the breaking change but wire shape is additive.

## 16. Decommission flow (D14)

Operator clicks Remove -> V2 cascade: (1) mark `archived=true`, `archived_at=now()`; (2) **capability unbinding** -- walk `Agent.SubCapability` + `Skill.requires_connection`, mark `unavailable_due_to_decommission`, notify operator; (3) **vault crypto-erase** -- `vault.shred_for_connection(id)` overwrites ciphertext, marks DEK rotation pending; next rotation makes refs unrecoverable; (4) **token revoke (best-effort)** -- OAuth `revoke_token` (access + refresh), API key delete, MCP `shutdown` JSON-RPC; (5) **cache invalidation** -- `cache.invalidate(tenant, slug)` to `MCPRegistry`/`ConnectionRegistry`/`IntegrationRouter`; (6) **governance flagging** -- referencing policies marked `connection_missing`, auto-deactivated; (7) **audit preserved** -- append-only; reference `decommission_token=uuid()`; (8) **hard delete via founder + 30-day grace** -- `?hard=true` requires `principal.role==FOUNDER`, 30-day countdown in `pending_hard_deletes`; founder may cancel before T+30d.

Recovery: partial fail leaves `archived=true` + flags `decommission_incomplete`. Alert operator. Never force-delete on error.

## 17. Audit row schema (D15)

Single table `audit_entries`, append-only, hash-chained. Schema enriched with B§14 fields.

```python
class AuditEntry(Base):
    __tablename__ = "audit_entries"
    id = Column(GUID, primary_key=True, default=uuid7)  # time-ordering
    tenant_id = Column(GUID, nullable=False, index=True)
    actor_id = Column(GUID, nullable=True)
    actor_kind = Column(Enum(ActorKind))  # operator|founder|system|external|bridge
    action = Column(String(64))  # 'connection.imported','vault.read','probe.completed'
    event_class = Column(String(32))  # auth|install|vault|governance|mcp|tenant_bypass|system
    target_kind = Column(String(32)); target_id = Column(GUID); target_slug = Column(String(128))
    before_hash = Column(LargeBinary(32)); after_hash = Column(LargeBinary(32))
    metadata = Column(JSONBCompat, default=dict)  # redacted; NEVER secrets
    governance_mode = Column(String(16))
    decision = Column(String(32))  # allowed|denied|pending|auto
    correlation_id = Column(GUID); request_id = Column(GUID); ip_address = Column(String(45))
    severity = Column(SmallInteger); tier = Column(SmallInteger)  # 1-3 retention
    prev_hash = Column(LargeBinary(32))
    signature = Column(LargeBinary(32))   # HMAC(canonical || prev_hash)
    created_at = Column(DateTime(timezone=True), default=now_utc)
```

**Append-only:** DB role `daena_app` has `INSERT, SELECT` only; `UPDATE/DELETE` denied. **Hash chain:** nightly cron walks 7-day chain, alerts on break; head stored separately w/ daily timestamp signature. **Retention:** Tier 1 (auth/vault/founder/tenant_bypass) 7yr; Tier 2 (governance/install/decommission) 1yr; Tier 3 (probes/tests) 90d.

## 18. State -> UI mapping

| Label | Pill | Icon | Color | Primary | Secondary |
|---|---|---|---|---|---|
| `unknown` | Unknown -- re-probe | `?` | `#64748B` | Re-probe | Details |
| `installable` | Installable | download | `#D4A843` | Install | Details |
| `installing` | Installing | spinner-anim | `#D4A843` | Cancel | -- |
| `needs_config` | Configure | gear | `#D4A843` | Configure | Disconnect |
| `needs_auth` | Sign in | key | `#D4A843` | Sign in | Cancel |
| `auth_pending` | Authorizing | spinner-anim | `#D4A843` | Open auth window | Cancel |
| `probing` | Testing | spinner-anim | `#2DD4BF` | -- | Cancel |
| `healthy` | Callable | bolt | `#2DD4BF` | Use in chat | Re-probe |
| `degraded` | Degraded | warning | `#F59E0B` | View error | Re-probe |
| `failed` | Failed | x | `#EF4444` | View error | Re-probe |
| `disabled` | Disabled | pause | `#64748B` | Enable | Remove |
| `archived` | Archived | archive | `#64748B` 50% | Restore | Hard-delete (founder) |

Each label carries a one-line copy string in pill tooltip + drawer header (e.g. healthy "Last call succeeded `<n>` ago"; failed "Probe failed `<n>` ago"; archived "Soft-deleted -- 30-day grace"). Palette: design system (`#0F1419`, `#D4A843`, `#2DD4BF`) + traffic-light (`#10B981`, `#F59E0B`, `#EF4444`, `#64748B`).

## 19. Migration plan: V1 -> V2 file action

Codes: **K**=KEEP, **A**=ARCHIVE, **R**=REWRITE, **W**=WRAP, **S**=SPLIT, **P**=PROMOTE, **E**=EXTEND, **N**=NEW. LOC noted for size context.

### Backend api/v1/

**S** `connections.py`(1150) -> router + `connections_service.py`; endpoints renumbered to D13. **P** `runtime.py`(116) merged into `connections.py`. **W** `runtimes.py`(620) 308-redirect to `/connections?kind=cli_runtime`; deleted next release. **N** `mcp.py` consolidates `mcp_server` + `mcp_sync`. **K** `connector_install.py`(848) OAuth->Redis + idempotency A§8; `connector_oauth.py`(313) +PKCE B§3; `mcp_server.py`(71) + `mcp_sync.py`(235) folded into `mcp.py` (refinement #4); `settings.py`(459) override store removed; `founder.py`, `dynamic_models.py`, `integrations.py`, `security_authorized_scope.py` (HANDS OFF).

### Backend services/

- **R**: `connection_service.py`(622) -> `connection_v2/registry.py`; `_status_for_install` removed (replaced by 6 truth fields). `integrations/oauth_credentials_store.py`(145) -> vault; JSON deleted.
- **P**: `runtime_truth_registry.py`(565) -> canonical `connection_v2/registry.py`; JSON write removed Phase 7.
- **W**: `mcp_bootstrap.py`(208) folded into `mcp_sync/detector.py` (A§10); `dynamic_model_service.py`(325) stop importing private `_PROVIDER_MAP`.
- **E**: `mcp_sync/detector.py`(191) +VSCode/Cursor/Cline/Continue/Zed paths +remote `mcp-registry` +per-tenant detection; bootstrap moved here.
- **S**: `model_router.py`(1464) split routing strategies (out of V2 critical path).
- **R (5 lying CLI adapters)**: `runtimes/adapters/{claude_code(358), codex(253), gemini_cli(306), grok_cli(167), mcp_bridge(214)}.py` ALL -- `check_health` rewritten to do real round-trip per §14; gemini handles "--version hangs" timeout.
- **K**: `mcp_invoker.py`, `mcp_registry.py`(592) demoted to LRU, `model_registry.py`(561) +public `_PROVIDER_MAP` API, `mcp/server.py`(443) +per-host bearer, `runtimes/registry.py`(508) demoted to LRU, `runtimes/{base_adapter,health_tracker,recovery_monitor,capability_matrix,cost_estimator,session_manager,subscription_auth}.py`, `runtimes/adapters/{claude_session,vllm_adapter,ollama_adapter}.py`, all 10 providers + `llama_server_manager.py` + `gguf_catalog.py`, `integrations/{oauth_service,integration_router,gmail_client,calendar_client,notion_client}.py`.

### Backend models/, schemas/, core/, config/, migrations/

**K** `models/{connections(101),mcp_server(180)}.py` (migration window, deleted Phase 8). **N** `models/connection_v2.py` (§4), `models/audit_entries.py` (§17), `core/db/tenant_guard.py` (§5), `core/logging/redactor.py` (B§12), `migrations/006_connection_v2.py`. **E** `core/vault.py` envelope crypto §6. **R** `schemas/connections.py`(118) new Pydantic. **S** `config/connector_catalog.json`(3352) per-category split; v`2026-04-29.3` is V2 spine.

### Frontend

**R** (5 files): `pages/ConnectionsPage.tsx` 5-tab shell §9; `pages/connections/MainBrainPanel.tsx` +Local Ollama +SSE ticker; `pages/connections/McpServersPanel.tsx` P0 badges fixed via `labelFromRow()` + two-tier badge C§13 + Bridge BLOCKED banner; `pages/connections/PluginsCatalogBrowser.tsx` Catalog card layout C§6; `pages/settings/SettingsModelsRuntimes.tsx` 308-redirect to `/connections?tab=brain` for 2 ship cycles, then delete. Plus `hooks/{useConnectorCatalog,useRuntimeRegistry}.ts` merged into `useConnectionRegistry.ts`.
**N**: `pages/connections/{InstalledPanel,ApiKeysPanel}.tsx`; `components/connections/{StatusPill,ConnectionDetailDrawer,AuditTrailDrawer}.tsx`; `hooks/{useConnectionRegistry,useConnectionEvents}.ts`; `lib/{connectionState,errorSanitizer}.ts`; `eslint-rules/no-derived-state.js`.
**A** (-> `_archived/` with "DELETE BY 2026-05-14" header): `pages/connections/{ConnectionsConnectors(33KB), ConnectionsExtensions(26KB), ConnectionsRuntimes(31KB), BrowseModal, oauth, shared, catalog(880)}.{tsx,ts}`. CLIBridgeCard re-ported into MainBrainPanel first; `CONNECTOR_MCP_EQUIVALENT` extracted to `connectorMcpMap.ts`.
**K**: `pages/connections/installFlow.ts`(208); `components/connections/ConnectorInstallDialog.tsx` (default tab=Auth when label in {needs_auth, auth_pending} per C§15#3); `components/chat/RuntimeSwapper.tsx`; `lib/{api,mutations}.ts`.
**S**: `pages/connections/types.ts`.

### daena-mcp + scripts

**K** `packages/daena-mcp/src/{index,daena-client,tools/{status,chat,memory,governance}}.ts`; `scripts/scrape_codex_plugins.py`; `backend/scripts/{verify_primary_mind_picker,council_perplexity}.py`. **R** `daena-mcp/src/tools/audit.ts` finish list trim + aggregate; `daena-mcp/package.json` bump 0.2.0 + npm publish Phase 8.

## 20. Rollout plan (Phase 3-10)

| Phase | Deliverable | Gate |
|---|---|---|
| 3 | This doc + ADR-002 lock + Storybook fixtures (12 labels) | Founder accepts doc |
| 4 | `connection_v2` table + migration + ConnectionRegistry + tenant_guard + envelope vault | Tests pass; old untouched |
| 5 | Dual-write + Redis OAuth state + audit chain + reconciliation cron | 7-day drift = 0 |
| 6 | Read-flip + per-kind probe contracts + detector extension | 5 lying CLI adapters real round-trip; tests assert |
| 7 | Frontend rebuild: 5 tabs, 2 drawers, StatusPill, ESLint rule, SSE consumer | E2E green; Storybook = prod |
| 8 | Decommission flow + hard-delete grace + legacy deletes (JSON, archived FE) | Founder approves grace |
| 9 | `daena-mcp` v0.2.0 npm publish + per-host bearer tokens | Bridge dispatch still BLOCKED |
| 10 | Catalog signing + KEK rotation playbook + production deploy | Founder runs first KEK rotation in staging |

Bridge dispatch enablement = post-Phase 10 (Phase 2 in B§ terms). Out of V2 scope.

## 21. Open questions

1. **Catalog signing key custody during updates?** `DAENA_CATALOG_PUBKEY` at boot; where does the private key live? Proposal: separate signing service in MAS-AI infra, never on Daena instance. Founder-approved release. Need ops sign-off.
2. **Per-tenant SSE channels under load?** ~120 conns x 50 tenants = ~6000 concurrent streams. HTTP/2 multiplexing limits unknown at scale. Test before prod.
3. **`last_op` enum values?** `discover|import|install|configure|authenticate|probe|disable|archive`?
4. **Deprecate `connector_catalog.json` once V2 catalog in DB?** Defer to Phase 7.
5. **Stale-OAuth recovery copy + docs link strategy?** Help system that survives V2 needs design.
6. **Cap-discovery in Phase 5 dual-write -- feature flag?** Probing 120 conns + discovery per probe = burst. Flag-gate per-tenant.

## 22. Disagreements

| # | Topic | Disagreement / Ruling |
|---|---|---|
| 1 | 16-state vs 6-boolean | A: "the disease, not the cure"; C built mapping for 16 -> **A wins** (6-boolean + 11 derived labels, D1). |
| 2 | `auth_complete` as state | C: state; B: "vault token != authenticated; need probe in 24h" -> **B wins**; stale-token Storybook fixture mandatory. |
| 3 | `SettingsModelsRuntimes` delete vs repair | C: "Delete"; file map: REWRITE -> **C wins**; 308-redirect 2 cycles, then delete. |
| 4 | Default new-tenant governance | B: BALANCED; CEO implied UNLEASHED -> **B wins** (D6). |
| 5 | TIER_UNVERIFIED in UNLEASHED | B: "founder-approve in ALL modes" -> **B wins**; no exception. |
| 6 | Label naming | A: `authenticating`/`auth_failed`; C: `auth_required` -> CEO binding `needs_auth`; single name. |
| 7 | `callable` vs `healthy` | A: `online`; C: "Pick `healthy`, drop `callable`" -> `healthy`=label (C), `callable`=truth dim (A). Pill says "Callable". |
| 8 | Audit schema richness | B: rich (`event_class`,`decision`,`tier`,`prev_hash`); CEO bare -> **B wins**; D15 enriched. |
| 9 | Probe load math | A: "~14k probes/hr; backoff+host-batch+rate-limit"; B/C silent -> **A wins** (§14 + Open Q#6 flag-gate). |

## 23. Three biggest risks

1. **Migration drift (Phase 5-6)** -- code path writes to JSON but not `connection_v2` -> V2 reads "lose" connections V1 shows. Mitigation: daily reconciliation cron; 7-day zero-drift gate before Phase 7 deletes JSON; founder-approved abort back to JSON-only. (A§13#1.)
2. **Probe scheduler stampede on first deploy** -- first probe of every connection on Phase 6 = simultaneous load against every upstream. Mitigation: probe rollout flagged per-tenant; cron starts disabled; operator opts in; per-tenant rate limit day one. (A§13#3, Open Q#6.)
3. **Bridge dispatch RCE if Phase 2 unblocks without all 3 guards** -- V2 BLOCKS dispatch; Phase 2 unblock without per-call signed nonces + tenant-bound bearer + operator approval queue = RCE across user fleet. Mitigation: §12 unblock criteria; founder approval to enable; each criterion gets own ADR. (B§15#1.)

## 24. Definition of done -- when can V2 ship?

All 15 gates green: (1) Alembic `006_connection_v2` applied + reconciliation cron 7 days zero-drift; (2) 5 lying CLI adapters do real LLM round-trip + tests assert failure on missing auth; (3) `connection_v2.config` Pydantic discriminated unions per kind + CI asserts every kind has non-empty schema; (4) all 6 truth dims persist + emit SSE + E2E toggles each dim observing `connection_state_changed`; (5) `oauth_credentials_store.py` deleted + vault tests show envelope crypto + KEK rotation works; (6) tenant isolation fixture cross-tenant access count = 0; (7) Storybook fixtures all 12 labels + visual regression passes; (8) `eslint no-derived-state` active + CI fails on violation; (9) Bridge BLOCKED banner visible + integration test confirms dispatch returns 403; (10) hard-delete grace queue + 30-day countdown working + founder-only dry-run test; (11) audit chain nightly cron 7 days no break; (12) all 12 P0 lying-UI symptoms have regression tests; (13) 308 redirect `/runtimes` -> `/connections?kind=cli_runtime` deployed + legacy gone next release; (14) tests 3086+ passing + 0 TS errors + clean Vite build; (15) founder signs off on doc + Phase 7 cutover ADR.

When all 15 green: V2 ships. Bridge dispatch enablement (Phase 2) is post-V2, gated separately.

---

**End of V2.** Anything Phase 4-9 not tracing back to a section here is orphan -- delete or wire.
