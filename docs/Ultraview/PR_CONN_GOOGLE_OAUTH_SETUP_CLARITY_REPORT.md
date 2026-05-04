# PR-CONN-GOOGLE-OAUTH-SETUP-CLARITY -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-LAPTOP-USABLE-TODAY-SPRINT-7 (PR-5 of 7)

---

## 1. Goal

Make Gmail / Drive / Calendar setup clear without needing Masoud
awake. The Apps panel now ships a static informational block that
explains the two-account split and exactly what the operator must do
manually (Daena never starts the OAuth flow on her own).

Two distinct accounts, two distinct roles:

| Role | Account | Use |
|---|---|---|
| Founder / operator | `masoud.masoori@mas-ai.co` | Read-only access to YOUR personal mail / calendar / drive |
| Daena / agent voice | `daena@mas-ai.co` | The seat Daena uses when she sends or files anything on the company's behalf |

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| No auto-OAuth from this guide | YES -- pinned by `test_guide_does_not_start_oauth_flow` (forbids `window.location =`, `google.accounts.oauth2`, `api.post`, etc.) |
| No credential prompts | YES -- forbidden `type="password"` substring |
| No backend API calls from the guide | YES -- forbidden `api.post(` / `api.get(` / `fetch(http...` |
| Names BOTH accounts explicitly | YES -- pinned by `test_guide_names_both_account_roles` |
| Carries "Manual step required" status | YES -- pinned by `test_guide_carries_manual_step_callout` |
| Renders BEFORE the Search input so the split is seen first | YES -- pinned by `test_apps_panel_renders_the_guide` (positional) |

---

## 3. Surface area

### Frontend

#### `frontend/src/pages/connections/GoogleAccountSetupGuide.tsx` (NEW)

Static, informational, no API surface. Three blocks:

* Header with **Manual step required** amber pill + one-paragraph
  explanation that Daena uses two accounts and never mixes them.
* Two-column role grid:
  - **Founder / operator** -- `masoud.masoori@mas-ai.co`,
    "personal account, read-only access to your inbox / calendar /
    drive when you ask Daena to summarize or search. Never used
    for posting on the company's behalf."
  - **Daena / agent voice** -- `daena@mas-ai.co`,
    "Daena's own Google Workspace seat. Anything Daena sends or
    files goes through this account so the audit trail is
    unambiguous. Never used to read your personal mail."
* "What you need to do" 4-step ordered list:
  1. Configure the OAuth client in Settings -> OAuth Clients.
  2. Connect Gmail/Drive/Calendar as `masoud.masoori@mas-ai.co`.
  3. Connect a SECOND time as `daena@mas-ai.co`.
  4. Daena asks which account before any tool call that writes/sends.
* Closing reminder that Daena does NOT start OAuth automatically and
  does NOT ask for credentials anywhere outside Google's own consent
  screens, plus a deep link to `accounts.google.com` for the
  pre-sign-in step.

`data-testid` hooks: `google-account-setup-guide`, `google-role-founder`,
`google-role-agent`.

#### `frontend/src/pages/connections/AppsPanel.tsx` (MODIFIED, +5 LOC)

* Imports `GoogleAccountSetupGuide`.
* Renders it AFTER the error banner and BEFORE the search input, so
  the two-account split lands in the operator's eyeline before they
  click Connect on any row.

### Tests

#### `backend/tests/test_google_oauth_setup_guide_contract.py` (NEW, 6 tests)

1. **`test_guide_exists`** -- file present at expected path.
2. **`test_guide_names_both_account_roles`** -- both email addresses
   appear verbatim.
3. **`test_guide_carries_manual_step_callout`** -- the "Manual step
   required" copy is present.
4. **`test_guide_does_not_start_oauth_flow`** -- 11 forbidden
   patterns absent (window.location redirects, fetch http, api.*,
   password prompts, secret tokens, oauth2 library calls).
5. **`test_guide_carries_test_ids`** -- 3 stable testids exist for
   future browser smoke.
6. **`test_apps_panel_renders_the_guide`** -- the guide renders
   BEFORE the Search input (positional check).

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_google_oauth_setup_guide_contract.py -q
......                                                                   [100%]
6 passed in 0.07s

$ npx tsc --noEmit
EXIT=0
```

**Sprint progression:** PR-4 ended at 310 in scope.
PR-5 adds 6 tests = **316 in scope**.

---

## 5. Smoke (manual, tomorrow)

1. Open Connections -> Apps tab.
2. The amber "Manual step required" guide is the first thing under
   the Apps header.
3. Read the two role cards. Both email addresses appear verbatim.
4. Click "Connect" on Gmail in the rows below. Standard OAuth flow
   fires through the existing OAuthConnectDrawer.
5. Sign in to Google as `masoud.masoori@mas-ai.co`.
6. Repeat for `daena@mas-ai.co` -- a second Connect run creates a
   second connector instance with a different `owner_email`.

---

## 6. What did NOT change

* OAuth backend -- untouched.
* OAuthConnectDrawer -- untouched. The guide is a sibling, not a
  replacement.
* AppsPanel rendering of the row list -- untouched.
* Phase 3 writes -- still impossible.

---

## 7. Follow-up PRs

1. **`PR-CONN-GOOGLE-ACCOUNT-PICKER`** -- once both accounts are
   connected, surface a per-skill "act as" picker in the modal
   (`SkillExecuteModal` already supports an account picker via
   `_PROVIDER_TO_CONNECTOR_NAME`). Defer until both rows exist.
2. **`PR-CONN-GUIDE-DISMISSAL`** -- if both Google accounts are
   already connected, the guide could auto-collapse to a one-line
   "2 of 2 Google accounts connected" status. Defer until after
   the operator confirms the guide is noisy.
3. **`PR-CONN-GUIDE-LOCALIZED-COPY`** -- the role descriptions are
   English-only today. If MAS-AI ships a non-English UI, swap in
   i18n keys.
