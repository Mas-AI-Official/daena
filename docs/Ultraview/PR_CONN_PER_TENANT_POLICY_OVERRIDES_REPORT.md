# PR-CONN-PER-TENANT-POLICY-OVERRIDES -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-OVERNIGHT-LOCAL-PRODUCTION-SPRINT-6 (PR-6 of 8)

---

## 1. Goal

Sprint-4 PR-5 + Sprint-5 PR-5 shipped the static plugin governance
preset table -- vendor-recommended ALLOW / ASK / DENY tiers per
(plugin, skill_class). PR-6 lets the operator OVERRIDE one cell at
a time per tenant. The override wins on read; the static preset
remains the baseline.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Metadata baseline only unless safe | YES -- this PR adds an override surface but does NOT change the consent gate or read_only defense |
| Do not enable writes | YES -- pinned by `test_override_does_not_unlock_phase2_writes`: PHASE2_ALLOWLIST stays empty of non-read-only entries even after an `allow` override |
| Do not change global governance mode | YES -- only per-(plugin, skill_class) tiers are overridable; UNLEASHED/BALANCED/GOVERNED are untouched |
| Default remains static preset | YES -- GET returns `[]` for fresh tenants; the frontend's merge logic falls back to the static preset for any cell with no override |
| Founder-only PUT | YES -- `Depends(require_role("FOUNDER"))` on the upsert endpoint |
| Tenant binding from JWT | YES -- never from request body; pinned by `test_tenant_a_override_invisible_to_tenant_b` |
| No new confusing settings sprawl | YES -- override is rendered inline in the existing `PluginDetailDrawer` "Governance recommendations" block; no new tab |
| Invalid tier rejected | YES -- 422 via Pydantic enum validation (`test_invalid_tier_rejected_with_422`) |

---

## 3. Surface area

### Backend

#### `backend/app/models/plugin_policy_override.py` (NEW)

* `PluginPolicyOverride` model with TenantMixin + TimestampMixin.
* Columns: `id`, `tenant_id`, `plugin_id`, `skill_class`, `tier`,
  `rationale`, `updated_by`, `created_at`, `updated_at`.
* Unique constraint on `(tenant_id, plugin_id, skill_class)` so PUT
  is upsert by content (no duplicate row for the same cell).

#### `backend/app/models/__init__.py`

* Imported + added to `__all__` for Alembic auto-discovery.

#### `backend/migrations/versions/012_add_plugin_policy_overrides.py` (NEW)

* `revision = "012_add_plugin_policy_overrides"`,
  `down_revision = "011_add_consent_grants"`.
* Idempotent guards mirror migrations 010 / 011.

#### `backend/app/api/v1/plugin_governance_presets_api.py`

* New `PolicyOverridePut` Pydantic model (Field-validated enum types).
* `GET /plugin-policy-overrides` -- returns the calling tenant's
  override list. Empty for fresh tenants.
* `PUT /plugin-policy-overrides` -- founder-only upsert.
  Tenant-bound from JWT. Returns the canonical row dict.
* The existing `GET /plugin-presets` is unchanged (vendor baseline).

### Frontend

#### `frontend/src/pages/connections/PluginDetailDrawer.tsx`

* `loadOverridesForPlugin(pluginId)` helper fetches
  `/plugin-policy-overrides` and filters client-side to the open
  drawer's plugin.
* `GovernancePresetsBlock` extended:
  * Builds a merged tier map: vendor baseline + per-cell overrides.
  * Renders an inline "Tenant overrides active for N skill classes"
    cyan badge when overrides exist.
  * Each badge gets a cyan ring + "(override)" suffix when the
    cell is overridden; the tooltip carries the original baseline
    so the operator can see what they replaced.

### Tests

#### `backend/tests/test_plugin_policy_overrides_api.py` (NEW, 10 tests)

1. GET returns empty list when no overrides
2. PUT inserts override; GET reflects it
3. PUT idempotent (no duplicate row; second call updates the existing)
4. Invalid tier rejected with 422
5. Invalid skill_class rejected with 422
6. Tenant A's override invisible to tenant B
7. GET requires auth
8. PUT requires auth
9. Override does NOT unlock Phase 2 writes (PHASE2_ALLOWLIST stays empty)
10. Response payload carries no token / secret substring

Frontend type check: `npx tsc --noEmit` -> EXIT=0.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_plugin_policy_overrides_api.py -q
10 passed in 8.39s

$ npx tsc --noEmit
EXIT=0
```

Sprint progression:
* End of PR-5: 260 in scope
* PR-6 adds: 10 new override tests = **270 in scope**

---

## 5. Smoke

```
$ curl http://127.0.0.1:8000/openapi.json | jq '.paths | keys[] | select(test("plugin-policy-overrides"))'
"/api/v1/connections/v2/governance/plugin-policy-overrides"
```

Backend restarted (PID 12564 killed, fresh uvicorn) -- new routes
live. Frontend tsc clean.

---

## 6. What did NOT change

* No PHASE2 enforcement change.
* No consent gate behavior change.
* No vendor preset table change.
* `GET /plugin-presets` shape unchanged (Sprint-5 PR-5 contract).
* Phase 3 writes -- still impossible.

---

## 7. Limitations + follow-ups

1. **Override editor UI is read-only in this PR.** The drawer renders
   the merged view + override badge, but there's no inline form to
   create/edit overrides yet. Operator must POST via curl or the
   future founder-policies page. Defer the editor UI until at least
   one operator asks for it -- the API + read view is what unblocks
   subsequent PRs.
2. **No DELETE endpoint** -- overrides are upserted; to "remove" an
   override the operator PUTs the same cell back to the vendor
   baseline tier. A DELETE endpoint can land if the operator wants
   to reset a cell to the live baseline (which itself can change
   as Daena ships new plugin presets).
3. **No bulk import / preset template apply** -- one cell per PUT.
   A future PR could add a "use preset" template button that PUTs
   N cells at once.
4. **The override is read-only metadata** -- it doesn't yet feed
   into the consent gate decision tree. A follow-up PR will plumb
   the merged tier into `check_consent_or_request` so a tenant
   override of `deny` actually blocks at the gate (today the gate
   only knows the consent category, not the per-tenant policy).
