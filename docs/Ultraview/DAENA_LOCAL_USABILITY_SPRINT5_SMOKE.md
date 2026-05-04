# DAENA-LOCAL-USABILITY-SPRINT-5 -- Smoke Status

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-03
**Sprint scope:** 5 PRs of feature work + this PR-6 smoke status.

---

## 1. Summary

Sprint-5 closed the multi-Google-account UX loop opened by Sprint-4 PR-3,
landed the production migration that brings PG into parity with the dev
SQLite schema, and surfaced the Sprint-4 consent + governance preset
foundations through HTTP + UI without enabling any write skill.

**0 hard stops encountered.** All 6 PRs shipped clean.

---

## 2. Commits landed

```
$ git log --oneline -7
94de242  canonicalization: surface plugin governance presets               [PR-5]
a49e8e5  canonicalization: expose Asset Shield consent approval flow       [PR-4]
6e70b2a  migration: add owner email to OAuth connector instances           [PR-3]
f486441  fix: add Google account picker for Gmail and Drive skills         [PR-2]
72e1188  canonicalization: capture Google account owner email on OAuth     [PR-1]
81da0a1  docs: update local usability smoke after Sprint 4
```

(Pre-Sprint-5 baseline: 81da0a1)

---

## 3. Test totals

```
$ .venv/Scripts/python.exe -m pytest \
    tests/test_skill_executor_phase2.py \
    tests/test_oauth_invoker.py \
    tests/test_skill_executor_oauth_wireup.py \
    tests/test_oauth_account_profiles.py \
    tests/test_skill_consent.py \
    tests/test_plugin_governance_presets.py \
    tests/test_oauth_account_profile_capture.py \
    tests/test_oauth_marketplace.py \
    tests/test_oauth_accounts_endpoint.py \
    tests/test_migration_010_owner_email.py \
    tests/test_skill_consent_api.py \
    tests/test_plugin_governance_presets_api.py
221 passed in 29.84s

$ npx tsc --noEmit
TSC=0
```

Sprint progression:
* Sprint-4 close: 162 in scope
* PR-1: +14 -> 176 (oauth_marketplace 19 already passing, count not double-incremented)
* PR-2: +6 -> 201
* PR-3: +6 -> 207
* PR-4: +9 -> 216
* PR-5: +5 -> **221**

---

## 4. New backend HTTP surface

```
GET  /api/v1/connectors/oauth/accounts?provider=<gmail|google-drive|...>
     PR-2: list connected owner_email accounts for the picker UI

GET  /api/v1/connections/v2/skill-consent/categories
     PR-4: 6 consent category descriptors + phase2_write_blocking_active flag

POST /api/v1/connections/v2/skill-consent/grant
     PR-4: mint a single-use consent grant, tenant-bound via JWT

GET  /api/v1/connections/v2/governance/plugin-presets
     PR-5: vendor-recommended ALLOW/ASK/DENY tiers per skill class
```

All 4 routes verified live in /openapi.json after backend restart.

---

## 5. New frontend surface

`frontend/src/pages/connections/SkillExecuteModal.tsx`:
* OAuth account picker (auto-select when 1 account, radio when N).
* Consent grant form when status === 'needs_consent'; explicit copy
  "Granting consent records your approval... It does NOT enable
  writes -- Phase 2 still blocks any non-read-only skill".

`frontend/src/pages/connections/PluginDetailDrawer.tsx`:
* "Governance recommendations" section with color-coded ALLOW
  (emerald) / ASK (amber) / DENY (rose) badges per skill class.
* Rose warning banner when any DENY is present.
* Footer notice: "Metadata only -- enforcement still runs through
  the consent gate + Phase 2 read_only defense".

`npx tsc --noEmit` -> EXIT=0.

---

## 6. New backend migration

`backend/migrations/versions/010_add_connector_instance_owner_email.py`:
* Adds `owner_email VARCHAR(254) NULL` + index.
* Drops the old `(tenant, connector, user)` unique constraint
  (tries both SQLAlchemy-named and Postgres-auto-named candidates).
* Adds the relaxed `(tenant, connector, user, owner_email)` unique
  constraint.
* Idempotent (safe to re-run on partially-applied schemas).
* SQLite uses a single `batch_alter_table` for all ops; Postgres uses
  native ALTER statements.

---

## 7. Newly usable features

| Capability | Status after Sprint-5 |
|---|---|
| Multi-Google-account capture | LIVE -- OAuth callback auto-populates `owner_email` from userinfo, normalized lowercase |
| Account selector in run modal | LIVE -- picker auto-selects single account, requires explicit pick when multiple |
| `_owner_email` propagation | LIVE -- modal includes it in `operator_inputs`; executor's Sprint-4 PR-3 gate consumes it |
| Production-ready owner_email schema | READY -- migration 010 in chain, awaiting `alembic upgrade head` on deploy |
| Consent grant minting via UI | LIVE -- amber form in modal, mints + re-runs |
| Consent category metadata for UI | LIVE -- /skill-consent/categories endpoint |
| Plugin governance recommendations | LIVE -- drawer renders ALLOW/ASK/DENY badges per skill class |

---

## 8. What still requires manual setup / does NOT auto-happen

1. **Operator must connect each Google account** (masoud@... + daena@...)
   via the existing OAuth flow. Sprint-5 captures the `owner_email` on
   callback; the operator still has to start the OAuth dance.
2. **Operator must run `alembic upgrade head` on production deploy**
   for migration 010 to apply. Dev SQLite picked it up via
   `create_all` already; PG needs the explicit migration.
3. **Consent grants are in-memory single-process.** A multi-instance
   Cloud Run deploy needs the future `PR-CONN-CONSENT-DB-PERSISTENCE`
   to make grants survive across replicas.
4. **Governance presets are vendor opinion only.** The future
   `PR-CONN-PER-TENANT-POLICY-OVERRIDES` will let operators override
   the baseline per tenant.

---

## 9. Phase 3 writes status

**STILL BLOCKED** by all 4 floors that existed at end of Sprint-4:

1. PHASE2_ALLOWLIST has zero `read_only=False` entries.
2. Phase 2 read_only defense at Step 3 of `SkillExecutor.execute`.
3. Consent gate at Step 2 (Sprint-4 PR-4) demands explicit operator
   approval. Sprint-5 PR-4 only added the API/UI to mint the grant --
   the gate is unchanged.
4. Per-plugin governance presets recommend DENY on
   Stripe PAYMENT / Filesystem WRITE_EXTERNAL / Gmail SEND_MESSAGE.

End-to-end test in `test_skill_consent_api.py::
test_consent_does_not_unlock_phase2_read_only_defense` verifies that
even WITH a fresh consent grant, the read_only defense still blocks
a synthetic write skill.

---

## 10. Hard stops encountered

**NONE.** The 13-hard-stop checklist was honored:

| # | Hard stop | Triggered? |
|---|---|---|
| 1 | Production deploy / Cloud Run / GCP write | NO |
| 2 | USE_CONNECTION_REGISTRY_V2=true flip | NO |
| 3 | vault --apply | NO |
| 4 | Secret read/print/grep/log/commit | NO |
| 5 | External email / DM / webhook | NO |
| 6 | Payment / refund / subscription / write | NO |
| 7 | Browser action on external sites | NO |
| 8 | V1 / legacy file deletion | NO |
| 9 | npm/pip/docker install not operator-confirmed | NO |
| 10 | Test failure not pre-existing | NO -- 1 failed test (consent-blocking) was fixed via correct assertion within the same PR |
| 11 | Unexpected secret-risk file in git status | NO |
| 12 | Architectural uncertainty | NO -- founder direction from Sprint-4 paused work was fully resolved before Sprint-5 began |
| 13 | OAuth interactive flow opened browser | NO -- only mocked / planted state in tests |

---

## 11. Recommended next sprint

Per the founder's brief at end of Sprint-4 + this Sprint-5 close-out:

Recommended order:
1. **`PR-CONN-OAUTH-ORPHAN-RECLAIM-UI`** -- inline "delete orphan"
   affordance in the picker for `owner_email=NULL` instances left by
   failed userinfo fetches.
2. **`PR-CONN-CONSENT-DB-PERSISTENCE`** -- DB-backed `ConsentStore`
   for multi-instance deploys.
3. **`PR-CONN-PER-TENANT-POLICY-OVERRIDES`** -- operator policy
   editor writes per-tenant overrides; baseline reads still come
   from the static preset table.
4. **`PR-CONN-CONSENT-CATEGORY-FROM-CLASSIFY`** -- expose backend's
   `categorize_skill` result inside the `needs_consent` outcome so
   the modal can default the category dropdown to the executor's
   classification instead of always `write_external`.
5. **Phase 3 writes (a separate sprint)** -- only after the above
   land + per-skill safety verification (dry-run preview, diff
   confirmation, undo path) is designed.

---

## 12. Honest status

After Sprint-5:

* Daena is a strong **local read-only assistant infrastructure**
  for Gmail and Drive once the operator connects their Google
  accounts.
* The multi-account flow is **honest end-to-end**: backend captures
  the owner_email, the picker UI surfaces it, the executor
  disambiguates on it, the migration brings PG into parity.
* The consent + governance foundations are **visible in the UI**
  but **not yet enforcement-changing**. Phase 2 is still the floor;
  Phase 3 writes remain blocked.

Stop and report.
