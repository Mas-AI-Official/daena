# Phase 4a — First PR: Isolated Envelope Vault Foundation

**Branch:** `rebuild-connections-mcp-runtime`
**Lock:** ADR-002 D-003
**PR scope:** NET-NEW files only — does not touch any existing code.

## What this PR adds

| File | Lines | Purpose |
|---|---|---|
| `backend/app/core/vault_v2.py` | ~290 | Pure-functional envelope-encryption module: per-tenant KEK derivation, DEK generation + wrapping, secret encrypt/decrypt with AAD binding, versioned wire format. |
| `backend/tests/test_vault_v2.py` | ~360 | 33 unit tests across 4 classes: roundtrip, AAD failure, version handling, malformed ciphertext, plus invariants (HKDF determinism, DEK uniqueness, JSON roundtrip, tenant isolation). |
| `docs/PHASE_4A_VAULT_FOUNDATION.md` | (this file) | Phase 4a-1 PR rationale + design + verification + non-goals. |

## What this PR does NOT do (intentional gates)

Per founder green-light constraints:
- No edits to `core/vault.py` (legacy single-key vault stays the production path).
- No edits to `main.py` (no boot-time KEK validation yet).
- No edits to `models/__init__.py` (no Secret model registration yet).
- No edits to `core/database.py` (no `secrets` table init yet).
- No edits to `core/constants.py` (no `DAENA_KEK` constant added yet).
- No Alembic migration (the `secrets` table + `tenants.dek_wrapped` column come in Phase 4a-2).
- No KEK env-var read at import time (the module is pure-functional; callers pass KEK explicitly).
- No singleton, no module-level state, no side effects on import.

These deliberate gates mean the V2 vault module can be imported in tests and exercised without altering any runtime behavior of the live application.

## Design

Per ADR-002 D-003 + V2 spec §6:

```
DAENA_KEK (env, 32B)
    -> per-tenant KEK = HKDF-SHA256(KEK_seed, salt=tenant_id, info="daena-v2-kek")
    -> per-tenant DEK = 32B random, stored in tenants.dek_wrapped
                        (AES-GCM under per-tenant KEK)
    -> secret_blob   = AES-256-GCM(plaintext, key=DEK,
                                   nonce=random_96b,
                                   aad=class || 0x1f || tenant_id || 0x1f || bound_to)
```

### Versioned wire format

| Field | Wrapped DEK | Encrypted secret |
|---|---|---|
| `format_version` | 2 | 2 |
| `kek_version` | 1 (current) | 1 |
| `dek_version` | 1 (current) | 1 |
| `wrapped_dek` / `ciphertext` | base64 | base64 |
| `wrap_nonce` / `nonce` | base64 (12 B) | base64 (12 B) |
| `wrap_tag` / `tag` | base64 (16 B) | base64 (16 B) |
| `tenant_id` | (in derive context) | str (UUID-as-str) |
| `class` | n/a | str (SecretClass enum value) |
| `bound_to` | n/a | str (e.g. `connection_v2:01926e7f-...`) |

`SUPPORTED_KEK_VERSIONS` and `SUPPORTED_DEK_VERSIONS` are explicit frozensets. New versions require a code change — we never silently accept unknown versions.

### `SecretClass` enum

```
oauth_token | oauth_client_secret | api_key | mcp_env_var | bridge_bearer
```

The class is bound into AAD, so a ciphertext encrypted as `api_key` cannot be decrypted as `oauth_token` even with the same DEK.

### Error hierarchy

```
VaultV2Error              base
├── TenantMismatchError   record's tenant_id != requested
├── AADMismatchError      class / bound_to / DEK mismatch -> InvalidTag
├── MalformedCiphertextError  missing fields, bad base64, wrong byte length, unsupported format_version
├── KEKVersionError       kek_version not in SUPPORTED_KEK_VERSIONS
└── DEKVersionError       dek_version not in SUPPORTED_DEK_VERSIONS
```

## Why envelope encryption?

- **KEK rotation is cheap.** The KEK lives in process memory (env var). Rotating it means re-wrapping each tenant's DEK once — secrets never decrypt-then-re-encrypt.
- **DB compromise alone yields nothing.** Without DAENA_KEK, the wrapped DEKs are just opaque ciphertext. The attacker also needs process memory access.
- **AAD binding tamper-evident.** A row stolen from tenant A and replanted under tenant B fails decrypt at the GCM tag level (AAD mismatch).
- **`bound_to` field cross-context security.** A ciphertext encrypted for `connection_v2:abc` cannot be decrypted as `connection_v2:def` even within the same tenant — useful when one row's secret is exfiltrated and an attacker tries to replay it elsewhere.

## Verification

### Unit tests (33 / 33 passed in 0.09s)

| Class | Tests |
|---|---|
| `TestRoundtrip` | 4 (basic + empty + 64 KiB + per-class) |
| `TestAADFailure` | 5 (wrong tenant + wrong class + wrong bound_to + wrong DEK + record tamper) |
| `TestVersionHandling` | 6 (unsupported KEK/DEK at wrap/unwrap/decrypt + supported-versions invariant) |
| `TestMalformedCiphertext` | 7 (missing field + bad format_version + bad base64 + truncated nonce/tag + wrong KEK) |
| `TestInvariants` | 11 (HKDF determinism, per-tenant divergence, per-seed divergence, DEK uniqueness, ciphertext uniqueness per call, JSON roundtrip, UUID normalization, length-validation guards, enum-only `secret_class`, end-to-end tenant isolation) |

Total: **33 tests**, all green, sub-100ms. Pure-functional module with no fixture dependencies.

### Sanity checks
- Frontend `tsc --noEmit`: CLEAN (unchanged from baseline).
- Phase 4a-1 only adds files — `git diff` against tracked files returns the 4 pre-existing NEEDS_FOUNDER_DECISION files unchanged from before this PR. None touched by this work.
- `core/vault.py` (legacy) UNCHANGED.

## What comes next

**Phase 4a-2 — DONE** (committed alongside Phase 4a-1's foundation):
- ✅ Alembic migration `006_secrets_envelope_vault.py` -- creates `secrets` table + adds `tenants.dek_wrapped` column. Idempotent guards mirror migrations 003-005. Chain verified: `001 → 002 → 003 → 004 → 005 → 006`.
- ✅ `Secret` SQLAlchemy model at `backend/app/models/secret.py` -- TenantMixin + TimestampMixin + unique constraint on `(tenant_id, secret_class, bound_to)` + index on `(tenant_id, secret_class)`. Ciphertext / nonce / tag stored as `LargeBinary` (BYTEA on Postgres, BLOB on SQLite).
- ✅ `Secret` registered in `backend/app/models/__init__.py` (import + `__all__`). Triggers Alembic auto-discovery; `Base.metadata.create_all` picks it up in dev.
- ✅ Boot-time KEK validation in `main.py` lifespan ESSENTIALS (added BEFORE the auto-create-tables step). Calls `load_kek_from_env(is_production=settings.is_production)`. Stores the validated KEK on `app.state.daena_kek`. Logs `vault.kek_loaded sha256_prefix=<8hex>` with `is_production` flag. `RefuseToBoot` propagates from the lifespan and aborts startup in production.
- ✅ Env-var plumbing: `DAENA_KEK_ENV` + `LEGACY_VAULT_KEK_ENV` constants in `core/constants.py`. New `core/vault_boot.py` (~140 LOC) reads either env var (DAENA_KEK precedence), validates 64-char hex OR 44-char base64 yielding 32 bytes, raises `RefuseToBoot` in prod / falls back to deterministic `DEV_FALLBACK_KEK` in dev with a loud warning. Placeholder values (`CHANGE-ME`, `PLACEHOLDER`, etc.) treated as "not set."
- ✅ 38 new tests (`test_vault_boot.py` 32 + `test_secret_model.py` 6). All pass.
- ✅ vault_v2.py module unchanged (per founder rule "Do not modify vault_v2.py unless a test proves a bug").
- ✅ Legacy `core/vault.py` unchanged.
- ✅ No existing secrets migrated.

**Phase 4a-3 — DONE** (see `docs/PHASE_4A_VAULT_MIGRATION.md`):
- ✅ `backend/scripts/migrate_vault_to_v2.py` (CLI) + `backend/app/services/vault_migration.py` (library)
- ✅ Default `--dry-run`; `--apply` requires explicit flag; `--force` overrides drift
- ✅ Dual-read invariant: encrypt then immediately decrypt; mismatch counts as drift
- ✅ All 7 founder counters tracked; structured-log + JSON-report output
- ✅ Plaintext NEVER in logs / report (sentinel-string tests pin this)
- ✅ Graceful precheck for missing `secrets` table
- ✅ 20 new tests; legacy `vault.py` + `oauth_credentials_store.py` UNTOUCHED
- ✅ Tenant.dek_wrapped Mapped column added in models/identity.py
- ✅ Dry-run on dev DB: 44 candidates / 44 skipped (JSON-null literals; no real encrypted creds present)

**Phase 4b** kicks off after operator runs `--apply` on production AND the 7-day dual-read soak window proves zero drift.

## Module API surface (intentionally minimal for Phase 4a-1)

```python
from app.core.vault_v2 import (
    SecretClass,
    derive_tenant_kek,    # bytes seed + tenant_id -> 32B per-tenant KEK
    generate_dek,         # () -> fresh 32B DEK
    wrap_dek,             # dek + tenant_kek -> wire dict
    unwrap_dek,           # wire dict + tenant_kek -> dek bytes
    encrypt_secret,       # plaintext + dek + class + tenant_id + bound_to -> wire dict
    decrypt_secret,       # wire dict + dek + class + tenant_id + bound_to -> plaintext bytes
    # error hierarchy
    VaultV2Error, TenantMismatchError, AADMismatchError,
    MalformedCiphertextError, KEKVersionError, DEKVersionError,
)
```

No imports from `app.main`, `app.core.database`, `app.core.constants`. No FastAPI dependencies. Safe to import in tests, scripts, and migration tooling without dragging in the rest of the application graph.

---

**End of Phase 4a-1 PR doc.**
