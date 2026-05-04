# PR-CONN-OAUTH-ORPHAN-RECLAIM-UI -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-OVERNIGHT-LOCAL-PRODUCTION-SPRINT-6 (PR-4 of 8)

---

## 1. Goal

Sprint-5 PR-1 captured `owner_email` on OAuth callback. When userinfo
fetch fails (intermittent network, rate-limit, partial scope), the
ConnectorInstance lands with `owner_email=NULL`. The same orphan
state also exists for pre-Sprint-5 legacy rows. PR-4 surfaces these
to the operator with explicit Reconnect / Archive affordances, so
they can either complete the OAuth dance again (capturing the
email) or hide the row from default lists.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Same-tenant only can archive | YES -- pinned in `test_archive_orphan_cross_tenant_returns_404` (the existing `_get_or_404` already enforces tenant scoping) |
| No token in archive response | YES -- `connection_service.archive` clears `credentials = None` and the response payload is the sanitized dict; pinned in `test_archive_response_carries_no_token_substring` |
| Connected named accounts not archived accidentally | YES -- pinned in `test_archive_one_orphan_does_not_archive_named_account` |
| Confirm gate required | YES -- backend rejects `confirm != True` with 400; pinned in `test_archive_orphan_without_confirm_returns_400`. Frontend ALSO uses `window.confirm()` -- two-layer defense |
| No row delete (per founder rule) | YES -- archive sets status=ARCHIVED + clears credentials; row preserved for audit history |
| No new endpoint required | YES -- reuses the existing `POST /connections/instances/{id}/archive` endpoint shipped 2026-05-03 |

---

## 3. Surface area

### Frontend

#### `frontend/src/pages/connections/SkillExecuteModal.tsx`

* New `OrphanReclaimSection` component (rendered inline in the
  account picker) shown when `accounts.some(a => a.owner_email === null)`.
* For each orphan instance, two buttons:
  * **Reconnect** -- opens `/api/v1/connectors/<provider>/oauth/start`
    in a new tab (preserves modal state); on success the OAuth
    callback creates a fresh ConnectorInstance with the captured
    email (Sprint-5 PR-1 path).
  * **Archive orphan** -- `window.confirm()` then POST to
    `/connections/instances/{id}/archive` with `{confirm: true}`.
    Archived instance is removed from the local accounts list via
    the `onArchived` callback so the picker updates immediately.
* `data-testid="orphan-reclaim-section"` for downstream
  Playwright/Chrome-DevTools smoke.

### Backend

* No new code paths. Reuses:
  * `POST /api/v1/connections/instances/{id}/archive` (existing)
  * `GET /api/v1/connectors/oauth/accounts?provider=...` (Sprint-5)
* PR-4 only adds the test coverage that pins the orphan-specific
  semantics so future refactors can't silently regress them.

### Tests

#### `backend/tests/test_oauth_orphan_reclaim.py` (NEW, 6 tests)

1. **`test_orphan_owner_email_null_can_be_archived`** -- the happy
   path: same-tenant FOUNDER archives an orphan with `confirm=true`
   and gets back `status=ARCHIVED`.
2. **`test_archive_response_carries_no_token_substring`** --
   defense-in-depth: archive response NEVER carries
   `FAKE-CANARY-TOKEN`/`FAKE-CANARY-RT` (both seeded into
   credentials), nor `access_token`/`refresh_token`/`Bearer`.
3. **`test_archive_one_orphan_does_not_archive_named_account`** --
   regression: archiving an orphan does NOT touch a sibling
   instance with the same connector_id but different owner_email.
4. **`test_oauth_accounts_lists_archived_status_for_frontend_filter`**
   -- the listing endpoint surfaces the row with `status=ARCHIVED`
   so the picker's `.status === 'CONNECTED'` filter drops it.
5. **`test_archive_orphan_without_confirm_returns_400`** --
   regression: confirm gate still blocks unintentional archives.
6. **`test_archive_requires_auth`** -- anonymous request returns
   401/403 before any DB lookup, preventing an enumeration oracle.

Frontend type check: `npx tsc --noEmit` -> EXIT=0.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_oauth_orphan_reclaim.py -q
6 passed in 3.80s

$ .venv/Scripts/python.exe -m pytest \
    tests/test_oauth_orphan_reclaim.py \
    tests/test_oauth_account_profile_capture.py \
    tests/test_oauth_accounts_endpoint.py \
    tests/test_marketplace_diagnostic.py \
    tests/test_marketplace_coming_soon_classifier.py \
    tests/test_skill_consent_api.py \
    tests/test_plugin_governance_presets_api.py \
    tests/test_connections.py -q
91 passed in 54.74s
```

Sprint progression:
* End of PR-3: 246 in scope
* PR-4 adds: 6 new orphan-reclaim tests = **252 in scope**

---

## 5. What did NOT change

* No new HTTP endpoint.
* No model schema change.
* No migration.
* No alteration to the existing archive semantics (still soft, still
  preserves audit, still requires `confirm=true`).
* Phase 3 writes -- still impossible.

---

## 6. Limitations + follow-ups

1. **Reconnect flow opens in a new tab.** A future PR could rework
   the OAuth start path to support same-tab redirect-with-state so
   the modal isn't lost. Defer until a real operator needs it.
2. **Discovery of orphans is currently scoped to the SkillExecuteModal
   account picker.** A future PR could add the same affordance in
   `OAuthLifecyclePanel` (the Advanced drawer surface) so operators
   can clean up orphans without opening a skill modal.
3. **No bulk archive** -- one button per row. A future PR could
   add "Archive all orphans for provider X" if the orphan count
   ever exceeds 3-4 in practice.
