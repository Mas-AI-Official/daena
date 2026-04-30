# Architecture Proposal A - System Architect Lens

Author: Council Member A (System Architect)
Scope: Connections / MCP / Plugins / Runtime rebuild (V2)
Stage: Karpathy llm-council Stage 1 proposer (system-architecture lens only)

---

## TL;DR (5 bullets)

1. **One canonical store, two read paths.** A new SQLAlchemy table `connection_v2` (Postgres / SQLite-compat) replaces the in-memory `runtimes/registry.py`, the JSON-backed `runtime_truth_registry.py` and the partial `mcp_servers` table. JSON-on-disk is **not** a viable persistence layer for a multi-tenant restartable backend - it has no row-level locking, no FK enforcement, no atomic transactions, and `var/` does not survive a Cloud Run revision.
2. **Six truth dimensions are columns, not a single status.** `detected / configured / imported / reachable / authenticated / callable` each have a boolean + `last_checked_at` + `last_failure_reason`. Lifecycle state is a **derived view** over those columns - never a free-form string field that can drift.
3. **Probes always do real I/O.** "Binary exists" is a `detected` signal, never a `reachable` or `callable` signal. Per-kind probe contracts are explicit (CLI = LLM round-trip; MCP = `tools/list`; provider = `/health` or `list_models`; OAuth = token exchange round-trip). Probe results are cached with a TTL but the cache is **stale-while-revalidate** - UI sees freshness metadata, never silently outdated state.
4. **Redis owns ephemeral state.** OAuth state, idempotency keys, install locks, probe TTL caches. Process-local dicts are banned. Redis is already in the stack (lifespan-checked) - it just isn't used here.
5. **Two-registry collapse + two-detector collapse are the cheapest wins.** `runtime_truth_registry.py` becomes the canonical service (it already handles the broader scope: providers + MCP + local models). `mcp_bootstrap.py` folds into `mcp_sync/`. The legacy `runtimes/registry.py` survives only as a thin in-process **adapter cache** keyed off the canonical store - no independent state.

---

## Section 1: Persistence layer

**Decision:** **SQLAlchemy table, Postgres in prod / SQLite in dev.** Reuse the existing migration infrastructure. Replace `models/mcp_server.py` with a generalized `connection_v2` table that handles all five connection kinds (CLI runtime, MCP server, provider, plugin/connector, OAuth app).

**Why not JSON-on-disk:**
- No row-level locking. Two operators importing the same MCP race on file write (`runtime_truth_registry.py` has no locking strategy).
- `var/` is mounted ephemeral on Cloud Run revisions; it does not survive deploys. Production deployment will silently lose all "imported" state on each push.
- No FK to `tenant_id`. The current JSON file mixes tenants in one document - multi-tenant safety relies on app-layer filtering.
- No atomic schema migrations. The current JSON has implicit schema drift (`runtime_truth_registry.py` carries 6 versions of nested dict shapes).

**Why not extend `models/mcp_server.py`:** It's tightly scoped to MCP. Extending it leaks MCP-specific columns (e.g. `mcp_command`, `mcp_args`) into rows that represent runtimes or providers. Cleaner to introduce `connection_v2` as a new table and migrate `McpServer` rows in.

**Schema:** see Section 11.

**Cite:** `02_backend_file_map.md` lines 79-84 (mcp_server / connections.py models); CLAUDE.md Rule 17 (in-memory registries hydrate from DB on startup).

---

## Section 2: Lifecycle state machine

**Pushback on the CEO's 16 states.** A monolithic 16-state enum is the disease, not the cure - it conflates orthogonal axes (installation vs. authentication vs. reachability). The right model is **6 boolean truth dimensions + a derived "user-facing label"**, not a single state field.

### Truth dimensions (booleans + timestamps)

| Dimension | Meaning | Probe |
|---|---|---|
| `detected` | We found evidence this thing exists somewhere we control or can read | Filesystem scan, CLI config parse, npm registry hit |
| `configured` | User supplied or selected the necessary config (auth method, URL, key reference) | Form submission persisted |
| `imported` | Daena has registered this in the canonical store | Row exists with `tenant_id` |
| `reachable` | Network/IPC handshake succeeded | TCP/HTTP/stdio open |
| `authenticated` | Auth credentials accepted by the upstream | Probe round-trip with auth |
| `callable` | A real operational call (`tools/list`, `chat.completions`, `/health`) returned 2xx in the last TTL | Real probe |

Each gets `<dim>_at` (timestamp) and `<dim>_failure_reason` (nullable text).

### Derived labels (UI-facing)

A pure function `derive_label(row) -> Label` maps the 6 booleans to one of:

`detected_only` → `configured_untested` → `installing` → `installed_unreachable` → `authenticating` → `auth_failed` → `online` → `degraded` → `offline_known` → `disabled` → `archived`

**11 user-facing labels, all derived.** They cannot drift from the underlying state because they are never persisted as their own field.

### Legal transitions (state graph)

```
detected_only ─────► configured_untested ─────► installing ─────► installed_unreachable
       │                       │                       │                    │
       │                       │                       │                    ▼
       │                       │                       │              authenticating
       │                       │                       │                    │
       │                       │                       │                    ▼
       │                       │                       │              ┌─ auth_failed (transient) ──► retry ──┐
       │                       │                       │              │                                       │
       │                       │                       │              ▼                                       ▼
       │                       │                       │           online ◄──────────────────────────── degraded
       │                       │                       │              │                                       │
       │                       │                       │              ▼                                       │
       │                       │                       │          offline_known ◄──────────────────────────── ┘
       │                       │                       │              │
       │                       │                       │              ▼
       │                       │                       └────────► disabled ────► archived
       │                       │                                                       ▲
       │                       └───────────────────────────────────────────────────────┤
       └───────────────────────────────────────────────────────────────────────────────┘
```

Transitions to `archived` are always legal (soft-delete). Transitions backward (e.g. `online` → `degraded` → `offline_known`) happen automatically via the probe scheduler.

### Gaps in the CEO's 16

**Missing:** `degraded` (probe slow, last 1 of 3 succeeded). **Collapse:** `imported` and `installed` are the same dimension (just different probe coverage). **Collapse:** `auth_pending` and `authenticating` are the same. **Wrong:** `connected` is meaningless - it should be either `reachable+authenticated` or `online`.

**Cite:** `01_damage_findings.md` "Six truth dimensions are explicit fields" (line 121).

---

## Section 3: Source of truth for "is this connection callable RIGHT NOW?"

**Hybrid with TTL + stale-while-revalidate (SWR).**

| Operation type | Source | TTL | Stale behavior |
|---|---|---|---|
| UI list-page render (e.g. `/connections`) | Last cached probe in DB | 60 s | Return cached value with `staleness_seconds`, async-trigger fresh probe |
| Pre-execution check (chat orchestrator about to call MCP) | Live probe with 2 s timeout | n/a | Fail closed (block call) if probe fails |
| Periodic background sweep | Live probe, batched | 5 min | Updates DB row + emits SSE delta |
| User-clicked "Test" button | Live probe, no TTL | n/a | Always fresh; record result with timestamp |

**Staleness budget:** 60 seconds for read; 2 seconds for write/execute. Anything older than 60 s renders with a "checking…" affordance (yellow), never green. Anything older than 5 min without a successful probe renders red.

**Cite:** `01_damage_findings.md` "No async handlers doing sync FS/network probes" (line 125); `02_backend_file_map.md` periodic_runtime_rescan every 60s.

---

## Section 4: Probe contract

**Per-kind probe contract - concrete, no `binary-exists` shortcuts:**

| Kind | What `detected` checks | What `reachable` checks | What `authenticated` checks | What `callable` checks |
|---|---|---|---|---|
| **CLI runtime** (claude_code, codex, gemini_cli, grok_cli, ollama via subscription) | `shutil.which()` or path exists | `<bin> --version` exits 0 within 5 s | `<bin> -p "ping"` returns valid JSON within 10 s | Real LLM round-trip with 1-token prompt |
| **MCP server (stdio)** | Config entry present in any CLI mcp config | `stdio_client(...)` opens subprocess | MCP `initialize` handshake succeeds | `tools/list` returns ≥0 tools |
| **MCP server (HTTP/SSE)** | URL configured | TCP connect to URL host | HTTP 200 on `/health` or first SSE event | `tools/list` JSON-RPC returns ≥0 tools |
| **API provider** (Anthropic/OpenAI/Groq/Together/etc.) | API key in env or vault | TCP connect to provider host | `list_models` or `/v1/models` returns 200 | Smallest possible chat completion (1 token) succeeds |
| **OAuth app** | Provider config + client_id present | OAuth authorize URL resolves | Token exchange round-trip succeeds | First authenticated API call succeeds |
| **Local LLM (Ollama / vLLM / llama-server)** | Endpoint configured | TCP connect to base URL | `/api/tags` or `/v1/models` returns 200 | One-token generation succeeds |
| **Plugin (skill pack only)** | SKILL.md present on disk | n/a (no runtime) | n/a | n/a - render as "Skill pack (not callable)" |

**Hard rule:** `callable=True` requires an authenticated round-trip recorded in the DB with a timestamp. No exceptions. The current `claude_code.py:182` pattern (`check_installed → ONLINE`) is what V2 deletes.

**Cite:** `05_lying_ui_findings.md` "CLI runtime adapters return ONLINE on binary presence" (lines 33-37); `02_backend_file_map.md` ollama_adapter (counter-example, line 67).

---

## Section 5: Capability discovery

**When does it run:** Three triggers.
1. **On import**: synchronous, blocking the import response (so the user sees "imported with 12 tools" not "imported, capabilities pending").
2. **On every successful `callable` probe**: fast (just diff against stored capability set). If the diff is non-empty, persist and emit SSE delta.
3. **Manual "rediscover capabilities" button**: forces a refresh, busts the TTL.

**Where capabilities persist:** Side table `connection_v2_capability` - one row per (connection_id, capability_kind, capability_name). Kinds: `mcp_tool`, `provider_model`, `cli_command`, `runtime_capability` (e.g. "supports_streaming"). This is **not** a JSON column on `connection_v2` because:
- Capabilities are queried independently ("show all connections that expose tool X").
- Capability churn (new tools added by a server) shouldn't rewrite the parent row.
- FK from capability → connection enables tenant-scoped filtering on capability lookup.

**Schema sketch:**
```sql
connection_v2_capability (
  id            uuid pk,
  connection_id uuid fk -> connection_v2(id) on delete cascade,
  kind          text not null,           -- mcp_tool | provider_model | cli_command
  name          text not null,           -- e.g. 'list_models', 'github.create_issue'
  spec          jsonb,                   -- raw schema from upstream (tool input schema, model card, etc.)
  discovered_at timestamptz not null,
  last_seen_at  timestamptz not null,    -- updated when capability still appears
  -- soft-deleted by `last_seen_at` < now() - 24h, never hard-deleted
  unique (connection_id, kind, name)
);
create index on connection_v2_capability (kind, name);
```

**Representation of "this MCP exposes tool X":** Row in `connection_v2_capability` with `kind='mcp_tool', name='X', spec={...input_schema}`. The chat orchestrator queries `WHERE kind='mcp_tool' AND name=?` joined to `connection_v2` filtered by `tenant_id` and `callable=true` to find live tools.

**Cite:** `02_backend_file_map.md` `services/mcp_registry.py` (existing tenant-scoped MCP tool runtime cache).

---

## Section 6: Race conditions

| Race | Resolution |
|---|---|
| **Two operators import the same MCP simultaneously (same tenant)** | Redis lock keyed on `(tenant_id, mcp_canonical_key)` with 30 s TTL. Second caller sees lock-held → returns 409 with the in-progress op's idempotency key. |
| **Two operators import the same MCP, different tenants** | No conflict. Tenant-scoped row in `connection_v2`. |
| **Probe-while-installing** | Install holds the same Redis lock. Probe sees lock-held → returns "installing, last result: <prior>". |
| **Concurrent OAuth callbacks for the same `state` token** | OAuth `state` is single-use. Stored in Redis with `SET NX EX 600`. Second callback fails fast with 409 "state already consumed". |
| **Capability discovery during call** | `connection_v2_capability` is upsert with `last_seen_at`. Concurrent discovery is fine; the row's `spec` is last-write-wins (acceptable - tool schemas converge). |
| **Background probe vs. user-triggered probe** | Single-flight per (tenant_id, connection_id, probe_kind). Redis SETNX 5 s. Second caller awaits the first's result. |
| **Auth credential rotation while invoke in flight** | Vault read snapshots credentials at call start. Mid-flight rotation does not break the in-flight call but does invalidate the cached probe → next probe will surface the change. |

**Cite:** `02_backend_file_map.md` `_MCP_OAUTH_STATES` and `_oauth_states` (lines 13-14, 146-150).

---

## Section 7: Restart persistence

**Must survive restart:**
- All `connection_v2` rows (tenant_id, kind, slug, config, auth_method, vault_ref).
- All `connection_v2_capability` rows.
- `connection_v2_audit_log` rows (immutable).
- Encrypted credentials in vault (already restart-safe).
- OAuth refresh tokens (in vault).
- All cron-scheduled probe entries.

**Allowed to be lost (rebuild on first probe):**
- Live TTL probe cache in Redis (re-populated on first read).
- Probe single-flight locks in Redis (re-acquired naturally).
- In-process `RuntimeRegistry` adapter cache (rebuilt by `hydrate_from_db` on startup - same pattern `MCPRegistry.hydrate_from_db` already uses).

**MUST NOT survive restart in any form that could re-trigger:**
- In-flight install operations: marked `failed_due_to_restart` per CLAUDE.md Rule 17 (never auto-retry destructive operations on restart).
- Background queue jobs related to install/uninstall: same treatment.

**OAuth state mid-callback:** `oauth_state` rows in Redis with TTL=600s. If backend restarts during a 5-minute OAuth flow, the user's redirect-back will fail with "state expired" - they restart the flow. This is the correct behavior; we do not persist OAuth state to durable storage because it would leak credentials in DB backups.

**Cite:** CLAUDE.md Rule 17 ("Never auto-retry destructive operations on restart"); `02_backend_file_map.md` `MCPRegistry.hydrate_from_db`.

---

## Section 8: Idempotency keys

| Operation | Needs idempotency key? | How computed |
|---|---|---|
| `discover` (read-only scan of CLI configs) | No | Read-only |
| `import` (DB insert) | **Yes** | `sha256(tenant_id || canonical_key)` where `canonical_key = kind + ":" + slug + ":" + auth_signature`. Auth signature = sha256 of `(auth_method, sorted(config_keys))`. Same input → same key. |
| `install` (mutates Claude Desktop config + DB) | **Yes** | Same as import + `install_target` (e.g. claude_desktop, codex_cli). |
| `probe` | No (single-flight in Redis is enough) | n/a |
| `oauth_authorize` | **Yes** | `state` token (random nonce, 32 bytes, base64url). |
| `oauth_callback` | **Yes** | Same `state` token consumed atomically. |
| `uninstall` | **Yes** | `sha256(tenant_id || connection_id || "uninstall")`. |
| `rotate_credentials` | **Yes** | `sha256(tenant_id || connection_id || rotation_seq)`. |

Stored in `idempotency_record (key, response_hash, created_at, expires_at)` with 24 h TTL. Key reuse within TTL returns the prior response verbatim. After TTL the key may be reused.

**Cite:** Multi-tenant safety per CLAUDE.md DAENA section.

---

## Section 9: The two-registry collapse

**`runtimes/registry.py` (in-memory) and `runtime_truth_registry.py` (JSON) collapse to:**

- **One canonical store**: `connection_v2` table (kind in `cli_runtime, provider, mcp_server, plugin, oauth_app, local_model`).
- **One in-process cache**: `ConnectionRegistry` singleton - wraps the table with adapter instances. `hydrate_from_db` on lifespan startup. No independent state. Replaces both `runtimes/registry.py.RuntimeRegistry` and the read paths through `runtime_truth_registry.py`.
- **One service layer**: `ConnectionService` (rename of `ConnectionRegistryService`). Owns lifecycle transitions. The current `runtime_truth_registry.py` becomes the *implementation* of this service (its prober/probe/import logic is good - just plumbed onto the table instead of JSON).

### Migration path

1. **Phase 1 (write-through dual store):** Add `connection_v2` table + Alembic migration. Wrap `runtime_truth_registry.py` writes to also write to the table. Reads still come from JSON. Both stores agree.
2. **Phase 2 (flip read path):** Change `api/v1/runtime.py` and `api/v1/runtimes.py` reads to query `connection_v2`. Keep JSON write for one release as a fallback. Verify count parity in audit log.
3. **Phase 3 (delete JSON):** Drop the `var/runtime_truth.json` write. Delete the JSON file. Delete `_load_state`/`_save_state` methods. Final shape: `runtime_truth_registry.py` becomes a thin orchestrator over `ConnectionRegistry` + adapters.
4. **Phase 4 (fold `runtimes/registry.py`):** It's already a thin in-memory cache. Replace with `ConnectionRegistry.get_runtime(slug)` which queries the table and returns the cached adapter instance.

**Migration safety:** Phase 1 is reversible (delete the table, rerun). Phase 3 is the irreversible step - gated on Phase 2 audit log showing 100% read parity for 7 days.

**Cite:** `02_backend_file_map.md` "Two-source problem on RUNTIMES" (lines 127-131).

---

## Section 10: MCP detection unification

**`mcp_bootstrap.py` and `mcp_sync/detector.py` collapse to:** **`mcp_sync/detector.py`** (it's already broader: reads Claude/Codex/Gemini configs; `mcp_bootstrap.py` only reads Claude Desktop).

### Steps
1. Move the `MCPBridgeAdapter` instantiation logic from `mcp_bootstrap.py` into a new method `mcp_sync/detector.py.adapt_to_bridge(detected_mcp) -> MCPBridgeAdapter`.
2. Delete `mcp_bootstrap.py:bootstrap_installed_mcps`. Replace lifespan call (`init_mcp_registry`) with `detector.bootstrap()` which:
   - Reads all candidate paths (existing `_CANDIDATES`).
   - For each found MCP: upsert to `connection_v2` (kind=`mcp_server`, status=`detected_only`).
   - Build adapter cache in `ConnectionRegistry`.
3. Detector grows two new methods:
   - `discover_remote(tenant_id) -> list[DetectedMCP]` - calls Anthropic's `mcp-registry` MCP for npm-published servers (currently a gap per `04_mcp_package_map.md`).
   - `discover_filesystem_for_tenant(tenant_id) -> list[DetectedMCP]` - for the multi-tenant Cloud Run case where `Path.home()` is the wrong scope, looks at `tenant.synced_cli_configs` (uploaded by user) instead.

**Dedup key (already correct in detector):** `(name, command, tuple(args))`. Extend with `(name, url)` for HTTP MCPs.

**Cite:** `02_backend_file_map.md` "Two-source problem on MCP DETECTION" (lines 133-138); `04_mcp_package_map.md` Gaps 5-10.

---

## Section 11: Schema sketch (Pydantic + SQLAlchemy)

### SQLAlchemy

```python
# backend/app/models/connection_v2.py

class ConnectionKind(str, Enum):
    CLI_RUNTIME    = "cli_runtime"
    MCP_SERVER     = "mcp_server"
    PROVIDER       = "provider"        # Anthropic / OpenAI / Groq / etc.
    PLUGIN         = "plugin"          # connector_catalog row, may or may not have MCP
    OAUTH_APP      = "oauth_app"       # OAuth provider for plugin/connector
    LOCAL_MODEL    = "local_model"     # Ollama / vLLM / llama-server endpoint

class AuthMethod(str, Enum):
    NONE                = "none"
    API_TOKEN           = "api_token"
    OAUTH_MANAGED       = "oauth_managed"
    MCP_REMOTE_OAUTH    = "mcp_remote_oauth"
    SUBSCRIPTION        = "subscription"     # CLI logged in via vendor flow

class ConnectionV2(Base, TenantMixin, TimestampMixin):
    __tablename__ = "connection_v2"
    id            = Column(GUID, primary_key=True, default=uuid4)
    tenant_id     = Column(GUID, ForeignKey("tenants.id"), nullable=False, index=True)
    kind          = Column(Enum(ConnectionKind), nullable=False, index=True)
    slug          = Column(String(128), nullable=False)        # canonical: 'claude_code', 'github-mcp', 'anthropic'
    display_name  = Column(String(256), nullable=False)
    canonical_key = Column(String(64), nullable=False, index=True)  # sha256 prefix; used for idempotency
    auth_method   = Column(Enum(AuthMethod), nullable=False)
    config        = Column(JSONBCompat, nullable=False, default=dict)   # kind-specific (command/args/url/...)
    vault_ref     = Column(String(256))                                  # opaque pointer into core.vault; nullable

    # 6 truth dimensions
    detected         = Column(Boolean, nullable=False, default=False)
    configured       = Column(Boolean, nullable=False, default=False)
    imported         = Column(Boolean, nullable=False, default=False)
    reachable        = Column(Boolean, nullable=False, default=False)
    authenticated    = Column(Boolean, nullable=False, default=False)
    callable         = Column(Boolean, nullable=False, default=False)

    # Per-dimension metadata
    detected_at      = Column(DateTime(timezone=True))
    configured_at    = Column(DateTime(timezone=True))
    imported_at      = Column(DateTime(timezone=True))
    reachable_at     = Column(DateTime(timezone=True))
    authenticated_at = Column(DateTime(timezone=True))
    callable_at      = Column(DateTime(timezone=True))
    last_failure_dim = Column(String(32))                  # which dimension last failed
    last_failure_msg = Column(Text)
    last_failure_at  = Column(DateTime(timezone=True))

    # Soft delete + governance
    archived         = Column(Boolean, nullable=False, default=False)
    archived_at      = Column(DateTime(timezone=True))
    governance_tier  = Column(SmallInteger, nullable=False, default=2)

    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "slug", name="uq_connection_v2_tenant_kind_slug"),
        Index("ix_connection_v2_tenant_callable", "tenant_id", "callable"),
    )
```

```python
class ConnectionCapability(Base):
    __tablename__ = "connection_v2_capability"
    id              = Column(GUID, primary_key=True, default=uuid4)
    connection_id   = Column(GUID, ForeignKey("connection_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    kind            = Column(String(32), nullable=False)       # 'mcp_tool', 'provider_model', 'cli_command'
    name            = Column(String(256), nullable=False)
    spec            = Column(JSONBCompat, nullable=False, default=dict)   # raw input_schema for MCP tools, etc.
    discovered_at   = Column(DateTime(timezone=True), nullable=False)
    last_seen_at    = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("connection_id", "kind", "name"),)
```

```python
class ConnectionAuditLog(Base):
    __tablename__ = "connection_v2_audit_log"
    id            = Column(GUID, primary_key=True, default=uuid4)
    connection_id = Column(GUID, ForeignKey("connection_v2.id"), nullable=False, index=True)
    tenant_id     = Column(GUID, nullable=False, index=True)
    op            = Column(String(64), nullable=False)         # 'discover','import','probe','authenticate','call','archive'
    actor_user_id = Column(GUID)                               # null for background
    initiator     = Column(String(32), nullable=False)         # 'user','heartbeat','probe_scheduler','chat_orchestrator'
    dim_changes   = Column(JSONBCompat, nullable=False, default=dict)  # {'reachable':[false,true],'callable':[false,true]}
    payload       = Column(JSONBCompat, default=dict)
    result        = Column(String(32), nullable=False)         # 'ok','error','noop'
    error_msg     = Column(Text)
    duration_ms   = Column(Integer)
    created_at    = Column(DateTime(timezone=True), nullable=False, default=now_utc)
```

### Pydantic

```python
class ConnectionV2Out(BaseModel):
    id: UUID
    kind: ConnectionKind
    slug: str
    display_name: str
    auth_method: AuthMethod
    truth: ConnectionTruthOut          # the 6 dims + timestamps + last_failure
    label: ConnectionLabel             # derived: 'online' | 'degraded' | ...
    capabilities_count: int
    last_probed_at: datetime | None
    staleness_seconds: int | None      # for SWR rendering

class ConnectionTruthOut(BaseModel):
    detected: TruthDimOut
    configured: TruthDimOut
    imported: TruthDimOut
    reachable: TruthDimOut
    authenticated: TruthDimOut
    callable: TruthDimOut

class TruthDimOut(BaseModel):
    value: bool
    at: datetime | None
    failure_msg: str | None
```

---

## Section 12: API endpoint shape (delta from CEO's listed routes)

| Method | Path | Purpose | Notes / delta |
|---|---|---|---|
| GET | `/api/v2/connections` | List all connections (tenant-scoped) | Replaces `/connections`, `/runtimes`, `/runtime/truth`, `/mcp-registry`, `/mcp-sync/detected` - single endpoint, `?kind=` filter |
| GET | `/api/v2/connections/{id}` | Single connection detail | Includes truth dims, capabilities, last 50 audit entries |
| POST | `/api/v2/connections/discover` | Trigger discovery scan (CLI configs + remote registry) | Idempotent; returns count of new `detected` rows |
| POST | `/api/v2/connections/import` | Import a discovered connection | Body: `{detected_id} OR {kind, slug, config}`; idempotency key required |
| POST | `/api/v2/connections/{id}/probe` | Run live probe; bust TTL | Returns refreshed `ConnectionV2Out`; 2 s timeout |
| POST | `/api/v2/connections/{id}/authenticate` | Start auth flow | For OAuth: returns authorize URL; for API token: accepts token + validates |
| POST | `/api/v2/connections/oauth/callback` | OAuth callback | `state` from Redis; validates + exchanges; persists to vault |
| DELETE | `/api/v2/connections/{id}` | Soft-archive | `?hard=true` requires governance tier 4 |
| POST | `/api/v2/connections/{id}/rediscover-capabilities` | Force capability refresh | |
| GET | `/api/v2/connections/{id}/audit` | Audit log for this connection | Paginated |
| GET | `/api/v2/connections/capabilities` | Cross-connection capability lookup | `?kind=mcp_tool&name=X` returns connections that expose tool X |

**Differences from CEO's draft routes:**
- **Single `/connections` namespace** for all kinds - no separate `/runtimes`, `/mcp-sync`, `/connectors`. Frontend filters with `?kind=`.
- **Derived label is read-only.** No endpoint to set state directly. State changes via probe/authenticate/import side effects.
- **No `/install` separate from `/import`.** "Install" in V2 means: write upstream config (e.g. Claude Desktop JSON) + import row. Done in a single endpoint with `import_target=claude_desktop` flag.
- **`/probe-auth` removed.** Replaced by `/probe` - probe always tests the dimension that the connection's auth method requires.
- **Versioned at `/api/v2`** to allow gradual cutover; v1 stays alive in degraded read-only mode for one release.

---

## Section 13: Three biggest risks of THIS proposal

1. **Migration window is fragile.** Phase 1 (dual write) → Phase 2 (flip read) → Phase 3 (delete JSON) requires three deploys with audit-log verification between each. If the JSON store and the `connection_v2` table diverge mid-migration (e.g. background probe writes only to JSON because of a missed code path), V2 reads will appear to "lose" connections that v1 still shows. Mitigation: a daily reconciliation cron that compares row counts and emits a hard alert on drift; deleting JSON only after 7 days of zero drift.

2. **`connection_v2.config` JSONB becomes a dumping ground.** The kind-specific `config` field (CLI command/args, MCP URL, provider base_url) is heterogeneous. Without per-kind validation we'll grow back the same drift the connector_catalog has today (`config_schema: {}` placeholder per `04_mcp_package_map.md` line 100). Mitigation: per-kind Pydantic discriminated unions enforced at write time; reject unknown keys; CI test that every `kind` has a non-empty `config_schema`.

3. **Probe scheduler load.** With N connections × 6 dimensions × 1 probe per 5 min = N×72/hour HTTP+stdio calls. At ~120 connections (existing Daena tenant baseline) that's ~14k probes/hour. Most will be cheap, but stdio MCP probes spawn subprocesses (~100-400 ms each per `04_mcp_package_map.md`). Mitigation: backoff on consecutive failures (exponential to 1 hour), batch probes by host (one TCP probe covers all MCPs on `mcp.linear.app`), and gate background probes behind a per-tenant rate limiter. `BACKGROUND PATH ONLY` markers required so probes never run inline in chat orchestrator.

---

## Closing note for the chairman

Three things this proposal does **not** answer (other proposers' lanes): (a) UX flow for the install dialog when probe is in progress (Council Member B?), (b) credential rotation key escrow / governance tier mapping (Security lens), (c) frontend Zustand store shape that consumes the SWR semantics. I expect the synthesis to integrate those without conflicting with the table/state-machine/probe contracts above.
