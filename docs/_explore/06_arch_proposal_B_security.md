# Architecture Proposal B - Security & Governance Architect Lens

Stage 1 proposer for V2. Lens: auth, secrets, audit, governance, blast radius, tenant isolation, OAuth lifecycle, plugin trust. Grounding: `01_damage_findings.md`, `02_backend_file_map.md`, `04_mcp_package_map.md`.

## TL;DR

- **One vault, envelope encryption, per-tenant DEKs.** Kill `oauth_credentials_store.py`. AES-256-GCM with `DAENA_KEK` (env) wrapping per-tenant DEKs (DB), DEKs encrypt secrets. Rotation = re-wrap DEKs.
- **Tenant isolation at ORM, not handler.** SQLAlchemy `before_compile` listener auto-injects `tenant_id` on every TenantMixin model. Cross-tenant work needs explicit `TenantBypass` + audit row.
- **Plugin trust = 3 tiers.** OFFICIAL (signed catalog) / VERIFIED (known publisher) / UNVERIFIED (raw GitHub, unsigned, founder-only). Skill packs are NOT-INSTALLABLE.
- **Audit append-only + hash-chained.** Every install/auth/probe/test/enable/disable/delete/vault-op writes a row with `prev_hash`. Vault decrypts log caller stack.
- **Biggest residual risk: daena-mcp `--bridge` dispatch.** Outbound WS to `wss://daena.mas-ai.co` scaffolded to ACCEPT dispatched calls. Phase 2 must NOT enable dispatch without per-call signed nonces, tenant-bound bearer, and operator approval queue. Otherwise: cross-tenant RCE.

---

## Section 1: Secret storage

**Location.** Single home: `core/vault.py` (exists, AES-256-GCM, used for `ConnectorInstance` creds). Extend. Delete `oauth_credentials_store.py` + `.daena_oauth_overrides.json` (docstring admits the debt). Two in-memory state dicts (`_MCP_OAUTH_STATES`, `_oauth_states`) -> Redis TTL=10min (transient state, not at-rest secret).

**Envelope encryption:** `DAENA_KEK_SEED` (32B, env-only) -> `per-tenant KEK = HKDF-SHA256(KEK_SEED, salt=tenant_id, info="daena-v2-kek")` -> `per-tenant DEK` (32B, generated on tenant create, stored in `tenants.dek_wrapped` as AES-GCM ciphertext under KEK) -> `secret_blob = AES-256-GCM(plaintext, key=DEK, nonce=random_96b, aad=class||tenant_id||row_id)`.

DB cols: `secrets.ciphertext BYTEA`, `nonce(12)`, `tag(16)`, `dek_version`, `kek_version`, `tenant_id`, `class` (`oauth_token`/`oauth_client_secret`/`api_key`/`mcp_env_var`/`bridge_bearer`), `bound_to` (`connector_instance:<id>`).

**Master key custody.** `DAENA_KEK_SEED` in `.env` (dev) / Cloud Run secret (prod). Process memory only. Missing on prod boot = `RefuseToBoot`. Hash-of-KEK printed at startup for verification without exposure.

**Rotation.** DEK: `POST /admin/secrets/rotate-dek` re-wraps tenant secrets online, operator-gated. KEK: change `DAENA_KEK_SEED`, re-derive KEKs, re-wrap DEKs. Quarterly, founder-gated.

**Logging.** `vault.decrypt()` emits `vault.access` row with `tenant_id`/`secret_id`/`class`/`caller_module`/`caller_function`/`request_id`. NEVER plaintext or ciphertext. Anomaly detector flags >100 decrypts/min/tenant.

## Section 2: Tenant isolation

**V1 failure mode.** Every `Connector*` uses `TenantMixin`, but `WHERE tenant_id` is hand-applied per handler. One missed filter = leak. "Duplicate Masoud rows" symptom matches handler-level filter bugs masked by founder-only testing.

**V2 enforcement, three layers:**

1. **ORM (mandatory).** `core/db/tenant_guard.py` registers SQLAlchemy `before_compile` listener. If model has `TenantMixin` and query lacks `tenant_id` filter, listener INJECTS it from `request.state.principal.tenant_id` (middleware sets from JWT). No principal context = `MissingTenantContextError`. Developer cannot forget.
2. **Middleware.** `TenantContextMiddleware` parses JWT, sets `Principal(user_id, tenant_id, role)` in `contextvars.ContextVar` so async tasks inherit.
3. **Test.** Pytest fixture captures emitted SQL, fails if any TenantMixin query lacks `tenant_id` predicate.

**Bypass.** `with TenantBypass(reason=, audit=True): ...` records high-priority audit row, requires `principal.role == FOUNDER`, grep-able.

**Cloud Run gap.** `mcp_sync/detector.py` reads `Path.home()` - on multi-tenant Cloud Run that's the container's home. V2 splits: `detect_local_mcps()` self-hosted/dev only; cloud tenants get `detect_remote_mcps(tenant)` from registry catalog only. 403 local path when `DEPLOYMENT_MODE=cloud`.

## Section 3: OAuth callback security

**State token.** HMAC-SHA256 over `(tenant_id, user_id, connector_slug, nonce_16b, ts_unix)` w/ per-tenant signing key from vault. Redis TTL=600s; on callback verify HMAC, atomic set `used=True` (Lua/GETSET), check freshness. Replay = `409 OAuthStateReplay` + audit.

**PKCE.** Always. `code_verifier = secrets.token_urlsafe(64)` at authorize-start, send `code_challenge = sha256(verifier)`, send verifier in token exchange. Even providers not requiring it get it.

**Redirect URI.** Per-connector `auth.allowed_redirect_uris: [str]`. Backend constructs callback URL itself - NEVER accepts client-supplied `redirect_uri`. Catalog schema rejects open-redirect patterns at startup.

**State binding.** Authorize-start requires authenticated session. Callback validates `state.principal_id == current_session.user_id`. Prevents login-CSRF.

**Token exchange.** Server-to-server. Client never sees `access_token`/`refresh_token`/`client_secret`. Tokens land directly in vault.

**Refresh.** Server-side, atomic replace, old kept 24h rollback. Honor `refresh_token_rotation` where supported.

**Truth fix.** V2 adds `connector_health.last_oauth_success_at`. UI shows "OAuth verified <ts>" ONLY when real token in vault AND probe succeeded within 24h. No probe = `connection_unverified`.

## Section 4: Plugin install trust model

| Tier | Definition | Gate | Probe |
|---|---|---|---|
| **OFFICIAL** | Signed MAS-AI catalog (`DAENA_CATALOG_PUBKEY`) | UNLEASHED auto / BALANCED op / GOVERNED founder | sandbox before enable |
| **VERIFIED** | npm allowlist OR signed by known publisher (Cloudflare, Sentry, Linear, Anthropic, Google) | op always | sandbox + capability disclosure |
| **UNVERIFIED** | Arbitrary GitHub URL, raw command, unsigned npm | **founder-only**, ALL modes | quarantined + manifest pinning |

**Manifest signature.** `connector_catalog_signed.json` (sigstore-style sig over canonical JSON). Sig fail at startup = catalog READ-ONLY + banner "Catalog tamper detected". MAS-AI pubkey at `backend/app/security/catalog_pubkey.pem`.

**Skill packs.** `auth_type=none` + `installable=false` show `Skill pack` chip + "Reference only". NO install button, NO auth fields. V2 schema REJECTS rows missing explicit `auth.method` at startup.

**Sandbox probe.** VERIFIED/UNVERIFIED MCP run in `mcp-probe-sandbox` before enable: subprocess `--no-network` first, then network limited to `auth.allowed_egress_hosts`. Captures declared tools, reachout, env reads, files touched. Operator sees `disclosure_report.json` before Enable.

## Section 5: Probe blast radius

A malicious connector could weaponize Daena's outbound network.

**URL allowlist per connector.** Every connector declares `auth.probe_endpoint` + `auth.allowed_egress_hosts`. `httpx.Client(transport=AllowlistTransport(hosts=...))` intercepts pre-connect.

**No internal-host probes.** Network-layer block: `127.0.0.1`, RFC1918, `169.254.0.0/16` link-local, `metadata.google.internal` (Cloud Run metadata exposes service-account creds - critical). DNS resolved inside transport, post-resolve check before TCP (defends against rebinding).

**Rate limit** per-tenant per-connector: 10/min, burst 30. Audit row every probe.

**Founder bypass.** `/security/scan` (Asset Shield) intentionally targets arbitrary hosts via separate `scan_egress_transport`. Connections probes NEVER use it.

## Section 6: Audit completeness

**Mandatory events** (one row each, synchronous, pre-commit): `connector.{discovered,install_*,auth_*,probe_*,test_*,enabled,disabled,deleted}`, `mcp.{bootstrap_loaded,tool_invoked,handshake_failed}`, `vault.{write,read,rotate}`, `governance.gate_decision`, `tenant_bypass.{entered,exited}`, `bridge.{connect,dispatch_received}` (Phase 2).

**Append-only.** Postgres rule prevents UPDATE/DELETE. Each row stores `prev_hash = sha256(prev_row.canonical || prev_row.hash)`. Nightly cron walks chain, alerts on break. Chain head stored separately w/ daily timestamp signature.

**Retention.** 7 years compliance class (auth, vault, founder); 90 days noise class (probes, tests).

## Section 7: Governance gate matrix

See Section 13. Summary: UNLEASHED = "everything goes except founder-private and asset crossings"; BALANCED = "auto read, prompt write/install"; GOVERNED = "approve every trust-boundary crossing".

V1 `install-all` bug fix: every endpoint creating persistent state OR running subprocess takes `confirm: bool = False`, default returns dry-run plan. Action requires `confirm=true` AND passing governance evaluation.

## Section 8: Founder approval gate

Required when ANY of: (1) installing TIER_UNVERIFIED, (2) vault KEK rotation (DEK is operator), (3) tenant bypass entry, (4) decommissioning Daena MCP server itself (external CLIs lose bridge), (5) modifying catalog signing key, (6) enabling Bridge dispatch (Phase 2 per-tenant), (7) changing default governance mode for production tenant, (8) `install-all` for security tools (per damage findings).

All go through approval-queue UI. Founder verified by JWT `role=founder` AND re-prompt of founder password (NOT just session token). Audit tier 3.

## Section 9: Skill pack auto-install fix

**Past bug.** Skill packs (no MCP/API/adapter - just SKILL.md) appeared installable w/ bearer-token forms. `connector_install.py` defaulted missing `auth.method` to `api_token`; `_status_for_install` returned CONNECTED. Skill packs looked installed; bearer form silently accepted secrets going nowhere.

V2 fix: (1) **Schema at catalog-load** - Pydantic REQUIRES explicit `auth.method`; rows missing it REJECTED at startup; logs `catalog_load.rejected_rows`. (2) **Distinct kind** - `kind: "connector"|"skill_pack"|"extension"`; skill packs get copy-path button, no install; backend has NO `install_skill_pack` endpoint. (3) **`_status_for_install` removed** - replaced w/ 6 truth fields; row is `connected` ONLY if `authenticated=true AND reachable=true AND last_test_succeeded_at < 24h`. (4) **PR check** - regression test asserts no row auto-defaults `api_token`, no `kind=skill_pack` has non-null `auth.method`.

## Section 10: Daena MCP server (authn for external CLIs)

`mcp/server.py` + `daena-mcp` package expose 5 tools to Claude/Codex/Gemini hosts. Without auth, any host reaching `localhost:8000/mcp/jsonrpc` reads memory/governance/audit. Multi-tenant: which tenant?

V2 auth: (1) **Per-host bearer tokens** - operator generates at `/settings/mcp-tokens`: label, backend mints JWT signed w/ vault key, scopes `{mcp:chat, mcp:memory:read, mcp:governance:check, mcp:audit:query}`, `tenant_id=current`, exp=90d, shown once, hash in `mcp_host_tokens`, operator pastes into `claude_desktop_config.json` `env.DAENA_TOKEN`. (2) **Per-call validation** - `mcp_server.py` extracts bearer from JSON-RPC `meta` or HTTP Authorization, validates sig/expiry/scope-vs-method/tenant. (3) **Scope-per-tool** - `daena_recall_memory` tier-vs-grant: `mcp:memory:read` -> T0/T1/T2; T3 needs `mcp:memory:institutional`; T4 (founder-private) needs `mcp:memory:founder` AND `principal=founder` AT THAT MOMENT (not just claim). (4) **Rate limit** - `mcp_chat` 60/min/token, `mcp_recall_memory` 120/min, burst 2x, 429 + audit. (5) **Revocation** via Redis deny-list, propagation < 5s. (6) **Bridge caveat** - `daena-mcp --bridge` is scaffold-only; V2 does NOT enable dispatch without distinct bridge tokens, per-call signed nonce, explicit operator approval queue (Section 15).

## Section 11: Decommission flow

V2 cascade on operator "Remove": (1) mark `status='decommissioning'`, `decommissioning_token=uuid()`; (2) token revoke - OAuth best-effort `revoke_token` w/ access+refresh, API key delete locally; (3) `vault.shred(id)` overwrites ciphertext, deletes row, audit-logs shred, targets `secrets WHERE bound_to=connector_instance:<id>`; (4) cache invalidation - remove from `MCPRegistry`/`ConnectionService`/`IntegrationRouter`, emit `cache.invalidate(tenant, slug)`; (5) walk `Agent.SubCapability` + `Skill.requires_connector` referencing slug, mark `unavailable_due_to_decommission`, notify operator; (6) referencing governance policies flagged `connector_missing`, auto-deactivate; (7) audit rows NEVER deleted, reference `decommission_token`; (8) final `status='decommissioned'`, soft-delete via `deleted_at`, founder `?include_deleted=1` inspects.

Recovery: partial-fail leaves row in `decommissioning`, alerts operator, retry. NEVER force-delete on error (orphan vault).

## Section 12: Logging hygiene

**Pre-emit redaction** (`core/logging/redactor.py`): Bearer tokens; API-key patterns (`sk-`, `sk-ant-`, `pplx-`, `xai-`, `gsk_`, `xoxb-`, `ghp_`, JWTs); client-ID strings (`*.apps.googleusercontent.com`); fields named `password`/`secret`/`token`/`client_secret`/`api_key`/`private_key`/`access_token`/`refresh_token`/`code_verifier`/`state`/`nonce` regardless of value; existing `pii_blocklist.yaml` patterns.

**Schema.** Pydantic secrets fields use `SecretStr`. Repr `**********`. JSON strips unless `with_secrets=True` AND founder principal.

**Audit rule.** Records METADATA never secrets. `vault.read` row: `secret_id`/`class`/`caller`, never plaintext/ciphertext.

**Test gate.** `tests/test_log_redaction.py` plants sentinel secrets, runs every code path, greps log; any hit = test fail. Egress-time redactor as backstop when logs ship to Cloud Logging/Datadog.

---

## Section 13: Governance gate matrix

`auto`=no prompt; `op`=operator prompt; `founder`=approval queue; `block`=refuse.

| Action | UNLEASHED / BALANCED / GOVERNED |
|---|---|
| `discover` (catalog, detect) | auto / auto / auto |
| `install` TIER_OFFICIAL | auto / op / founder |
| `install` TIER_VERIFIED | op / op / founder |
| `install` TIER_UNVERIFIED | founder / founder / founder |
| `install` skill_pack | n/a / n/a / n/a |
| `configure` (api_key, oauth) | auto / op / op |
| `probe` allowlisted host | auto / auto / auto |
| `probe` new host | op / op / founder |
| `test` sandbox | auto / auto / op |
| `test` real tenant data | op / op / founder |
| `enable` | auto / op / op |
| `disable` | auto / auto / auto |
| `delete` decommission | op / op / op |
| `vault.write` | auto / auto / auto |
| `vault.rotate_dek` | op / op / op |
| `vault.rotate_kek` | founder / founder / founder |
| `tenant_bypass.enter` | block / block / founder+audit |
| `bridge.dispatch` (Phase 2) | block / founder / block |
| `mcp_host_token.mint` | op / op / founder |
| `mcp_host_token.revoke` | auto / auto / auto |
| `governance_mode.change` | founder / founder / founder |
| `catalog_signed.update` | founder / founder / founder |
| Asset egress (api_keys/finance/identity/legal/founder_memory) | gated / gated / gated |

Asset Shield overrides this matrix on asset-class egress regardless of mode.

## Section 14: Audit log row schema

Single table `audit_entries`, append-only, hash-chained.

Columns: `id PK`, `tenant_id FK`, `principal_user_id FK`, `principal_role` (`founder|operator|viewer|system|bridge`), `event_type` (dotted), `event_class` (`auth|install|vault|governance|mcp|tenant_bypass|system`), `severity`, `tier 1-3` (retention), `target_kind`, `target_id`, `target_slug`, `governance_mode`, `decision` (`allowed|denied|pending_approval|auto_logged`), `decision_reason`, `request_id`, `correlation_id`, `ip_address`, `user_agent`, `timestamp`, `payload JSONB` (NEVER secrets), `prev_hash BYTEA(32)`, `hash BYTEA(32)` = sha256(`canonical_json(this_row) || prev_hash`).

Indexes: `(tenant_id, timestamp DESC)`, `(target_kind, target_id, timestamp DESC)`, `(event_type, timestamp DESC)`, `(correlation_id)`.

## Section 15: Three biggest security risks of V2 if built naively

**1. Bridge dispatch RCE.** `daena-mcp --bridge` opens outbound WS to `wss://daena.mas-ai.co` and is scaffolded to ACCEPT cloud-dispatched tool calls. If Phase 2 ships dispatch without per-call signed nonces, tenant-bound bearer, and operator approval queue for inbound, anyone compromising the cloud bridge endpoint runs arbitrary tool calls (file writes, terminal, browser) on every connected machine. **Risk: RCE across user fleet.** Mitigation: BLOCKED in V2; unblock only when Phase 2 lands all three guards.

**2. TIER_UNVERIFIED install during friendly demo.** Operator pastes `https://github.com/somerepo/daena-plugin`. If V2 ships UNVERIFIED at operator-approve, an attacker delivering a malicious manifest via plausible link harvests vault tokens (their "auth probe" hits attacker host and exfiltrates stored API keys). Mitigation: TIER_UNVERIFIED is FOUNDER-approve in ALL modes including UNLEASHED.

**3. Tenant bleed via in-memory state dicts.** `_MCP_OAUTH_STATES` / `_oauth_states` are process-local. In multi-process Cloud Run, callback can land on a different worker than authorize-start; V1 already fails. V2 worse if not migrated: state collision leaks tokens cross-tenant. Mitigation: Redis TTL=600s, key includes `tenant_id`, value HMAC-bound. Test: spawn two workers, oauth-start on A, callback on B must work.

---

## Pushback on listed states/endpoints

- **`POST /security/tools/install-all`** as it existed is insecure-by-design (ran prowler/scoutsuite/trufflehog without operator consent). V2 must split into per-tool installs each w/ `confirm=true` + TIER classification, or require founder approval + `confirm=true` + dry-run-first `plan_id` token (prevents replay).
- **6 truth dimensions** correct, but `authenticated=true` MUST require real probe within 24h, not "vault has a token". Revoked tokens still sit in vault; vault-presence-only UI is the same lie as V1 CONNECTED chips.
- **Default governance mode = UNLEASHED** for new tenants risks accidental breach during first 24h. V2 default should be **BALANCED**. Operator opts down via founder-gated change. Bias: "safe rails until you turn them off".
