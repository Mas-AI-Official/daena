# DAENA -- Live Activation Run 01 Report

**Run:** DAENA-LIVE-ACTIVATION-RUN-01
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)
**Operator:** Masoud Masoori (masoud.masoori@mas-ai.co)
**Machine:** D:\Ideas\Daena (Windows 11, local SQLite dev DB)

This is the truth at the close of the first live activation run.
Daena's Sprint-20 business loop was exercised end-to-end on Masoud's
actual machine, against his actual database, by his actual user
account. Where a step required Google OAuth consent (browser /
operator interaction), the run stopped honestly with the expected
refusal code. Nothing was sent. Nothing was faked.

## Bottom line

| Question | Answer |
|---|---|
| Backend boots clean? | YES, after fixing one real bug found during run |
| Frontend boots clean? | YES |
| Sprint-14..20 fast subset? | 494 / 494 pass |
| Frontend tsc? | 0 errors |
| Discovery loop runs end-to-end? | YES (manual_seed source, 3 opps persisted) |
| Workstream promotion routes correctly? | YES (grant->Finance, customer_lead->Sales, duplicate refused) |
| Local outreach draft factory works via chat? | YES (PR-7 chat command created BizOutreachDraft on operator's DB) |
| Vague chat commands still refuse? | YES |
| Gmail bridge correctly refuses without OAuth? | YES (`gmail_oauth_not_ready`) |
| Google OAuth ready? | NO -- operator has not connected either pinned account |
| Send tested? | NO -- intentionally skipped per hard rule (no OAuth, no allowlist) |
| Daena ready for daily business use? | NO until operator completes 4 OAuth steps below |
| Sprint-21 can start? | YES, but only AFTER operator runs the 4 OAuth steps + a real send |

## Bug found and fixed during the run

**`app.state` AttributeError on backend boot.**

`backend/app/main.py` line 805 had:
```python
import app.services.controlled_execution_handlers  # noqa: F401
```

Inside the `lifespan(app: FastAPI)` async generator. Python's dotted-
import form binds the top-level name `app` in the local scope, which
SHADOWED the lifespan parameter `app: FastAPI`. Line 832 then said
`app.state.daena_kek = _kek` and resolved `app` to the package
instead of the FastAPI instance, raising
`AttributeError: module 'app' has no attribute 'state'` and aborting
the whole startup.

Fix: changed to
```python
from app.services import controlled_execution_handlers  # noqa: F401
```

which only binds the local name `controlled_execution_handlers`, not
`app`. Verified by booting the backend after the fix -- it came up
clean and `/api/v1/health` returned 200.

This bug had been in the tree since Sprint-14 PR-2 but only surfaced
on real boot (test fixtures don't go through the lifespan). Caught
because the activation run actually started the server. That's the
point of activation runs: tests pass; integration fails differently.

## Verified live (read-only or DB-state mutations only -- NO external traffic)

### Step 1 -- Backend + frontend boot

```
GET /api/v1/health
  -> 200 {"status":"healthy",
          "checks":{"redis":"unavailable","database":"healthy",
                    "essentials_ready":true,"seedings_complete":true,
                    "seed_phase":"complete"},
          "version":"2.0.0"}
```

Frontend Vite up on `[::1]:5173`, IPv6 by default; `localhost:5173`
works in browser. Proxy target wired from `.daena-port`.

### Step 2 -- Sprint-20 endpoints mounted + auth-gated

| Endpoint | Without bearer | With bearer (operator) |
|---|---|---|
| GET /api/v1/connections/google-activation-summary | 401 | see below |
| GET /api/v1/opportunities/send-rate-limit | 401 | 200 |
| GET /api/v1/opportunities/ | 401 | 200 |
| POST /api/v1/opportunities/run-discovery | 401 | 200 |
| POST /api/v1/opportunities/{id}/create-workstream | 401 | 200 |
| POST /api/v1/business/chat | 401 | 200 |

All four new Sprint-20 endpoints mounted, all auth-required, all
return 401 without a valid bearer.

### Step 3 -- Google activation summary on operator's machine

```
GET /api/v1/connections/google-activation-summary
  -> {
       "ready": false,
       "client_configured": false,
       "blockers": [
         {"role":"client", "email":null,
          "missing":["client_id","client_secret"]},
         {"role":"founder", "email":"masoud.masoori@mas-ai.co",
          "missing":["gmail","drive","calendar"]},
         {"role":"agent", "email":"daena@mas-ai.co",
          "missing":["gmail","drive","calendar"]}
       ]
     }
```

This is the EXACT operator-facing truth: the OAuth client is not
configured, neither pinned account is connected. The /opportunities
page banner (Sprint-20 PR-1) renders this verbatim.

### Step 4 -- Send rate limit

```
GET /api/v1/opportunities/send-rate-limit
  -> {"today_utc":"2026-05-06","used":0,"cap":3,"remaining":3}
```

Cap is 3/day per the Sprint-19 design. Counter is at 0 -- no sends
attempted today. The /opportunities header chip will render
"3/3 sends left today" in slate.

### Step 5 -- Opportunity sources configuration

`backend/.opportunity_sources.json` was missing. Created an empty
shell with `_comment` instructing the operator to add real RSS
feeds + URL pages they trust. Until the operator adds entries,
`manual_seed` remains the only registered source. (File is
gitignored.)

`backend/.opportunity_seed.json` was missing. Created with three
`activation-run-01 placeholder` entries (one grant, one accelerator,
one customer_lead) so the operator can see the pipeline produce
data on first run. Operator should replace these with real
opportunities before relying on the system. (File is gitignored.)

### Step 6 -- Discovery loop runs

```
POST /api/v1/opportunities/run-discovery {"top_n":10}
  -> {"discovered_count":3, "deduped_count":3, "persisted_count":3,
      "updated_count":0, "capped_count":0,
      "sources_queried":["manual_seed"], "sources_failed":[]}
```

Three opportunities persisted into the operator's DB:

| Type | Score | Source | Status |
|---|---|---|---|
| customer_lead | 57 | manual_seed | discovered |
| grant | 54 | manual_seed | discovered |
| accelerator | 52 | manual_seed | discovered |

Scores are deterministic Python (Sprint-19 PR-1 contract); same input
will always produce the same score. Sources_failed=[] -- no adapter
errored.

### Step 7 -- Workstream promotion (Sprint-20 PR-3)

```
POST /api/v1/opportunities/{grant_id}/create-workstream
  -> {"workstream_id":"9eb03996-b363-486a-ab4d-cf55862b23c4",
      "department_name":"Finance",
      "collaborators":["Founder Office"]}

POST /api/v1/opportunities/{customer_lead_id}/create-workstream
  -> {"workstream_id":"3d7c722a-7198-49ac-ab94-b733cb6c81a4",
      "department_name":"Sales",
      "collaborators":["Product"]}

POST same grant_id again
  -> 409 Conflict
     {"detail":{"code":"duplicate_workstream",
                "existing_workstream_id":"9eb03996-..."}}
```

Routing map verified live: grant -> Finance, customer_lead -> Sales.
Duplicate refused with stable code + existing_id. Opportunity rows
correctly stamped with `assigned_department` + status flipped from
`discovered` to `queued`.

### Step 8 -- Outreach draft via chat (Sprint-20 PR-7)

```
POST /api/v1/business/chat
  {"text":"draft outreach for opp <customer_lead_id> to test@example.com"}
  -> {"matched":true, "command":"draft_outreach_for_opp_to",
      "summary":"Local outreach draft created.",
      "structured":{"ok":true,
                    "draft_id":"978fd2ae-0d56-4332-a2cd-2df07744ca85",
                    "status":"drafted", "blocked_reason":null}}
```

PR-7 explicit-id chat command works end-to-end on the operator's
DB. Draft persisted with the customer_cold_email template body
(deterministic Python, no LLM).

```
POST /api/v1/business/chat {"text":"send the approved draft"}
  -> {"matched":true, "command":"send_approved_draft",
      "implemented":false}
```

Vague Sprint-19 stub still refuses. PR-7 narrowing held.

### Step 9 -- Gmail draft bridge against the live draft

Direct call into `outreach.gmail_bridge.queue_gmail_draft_creation`
against `978fd2ae-...`:

```
{"success": False,
 "refusal_code": "gmail_oauth_not_ready",
 "approval_id": None,
 "auto_approved": False}
```

This is the EXPECTED, HONEST blocker. The bridge correctly refuses
because no Gmail ConnectorInstance exists for
`masoud.masoori@mas-ai.co`. NO HTTP call to Google was attempted.
NO approval row was created. NO trust ladder graduation occurred.
The draft remains in `drafted` status, NOT advanced to
`queued_create_draft` -- exactly as the Sprint-19 PR-4 contract
specifies.

### Step 10 -- Send

INTENTIONALLY SKIPPED per the activation-run-01 hard rules:
* No OAuth -> bridge cannot create the Gmail draft anyway.
* No allowlisted recipient -> drill would refuse.
* Test recipient `test@example.com` is RFC-2606 reserved + would
  bounce; sending to it is rude even if it could happen.

The drill helper (`backend/app/services/outreach/drill.py`) is
present and tested (13/13). Operator can run it once OAuth is up.

## What the operator must do to finish activation

The four steps below are interactive -- I cannot do them. They are
ordered so that each one is a hard precondition for the next.

### A. Configure Google OAuth client (one-time, ~10 minutes)

1. Open `https://console.cloud.google.com`. Create a new project
   (or pick the existing MAS-AI one).
2. APIs & Services -> Library: enable Gmail API, Google Calendar API,
   Google Drive API.
3. APIs & Services -> OAuth consent screen: Internal user type
   (Workspace) or External + add yourself as test user.
4. APIs & Services -> Credentials: Create Credentials -> OAuth
   client ID -> Web application. Add the local redirect URI exactly
   as printed by Daena in the Connections page (Daena will refuse
   any URL that doesn't match).
5. Copy the client_id + client_secret.
6. In Daena: Settings -> OAuth Clients -> Google -> paste both,
   Save.
7. Verify: refresh `/connections`, the activation summary endpoint
   should now report `client_configured: true`.

### B. Connect masoud.masoori@mas-ai.co (~2 minutes)

1. In Daena: Connections -> Apps -> Gmail -> Connect.
2. Complete Google consent flow as masoud.masoori@mas-ai.co.
   Grant the requested scopes.
3. Repeat for Google Drive and Google Calendar (same account).
4. Verify: activation summary `founder_account.missing` -> empty.

### C. Connect daena@mas-ai.co (~2 minutes)

1. Sign out of Google in the browser tab (or use a different
   profile).
2. Sign in as daena@mas-ai.co.
3. Repeat the three Connect clicks (Gmail / Drive / Calendar).
4. Verify: activation summary `agent_account.missing` -> empty.

### D. First real outreach send (~5 minutes)

1. In `/opportunities`, click `Run discovery` (or chat command).
2. Pick a real opportunity with a real recipient.
3. Use the chat:
   `draft outreach for opp <uuid> to <real-recipient@domain>`.
4. Open `/governance/approvals`. Approve the
   `gmail.create_draft` GoaRequest. The handler creates the Gmail
   draft via the controlled spine.
5. Approve the `gmail.send_existing_draft` GoaRequest (second wall).
   The send fires through 6 dispatch gates + recipient safety +
   payload hash + snapshot integrity + rate limit.
6. Verify in Gmail: draft appears in Drafts, and once the second
   approval fires, message appears in Sent.
7. Verify: rate-limit chip on `/opportunities` flips from
   `3/3 sends left` to `2/3`.

## Hard-rule audit (this run)

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied -- `.opportunity_sources.json` and `.opportunity_seed.json` are gitignored |
| No generic send_email | applied -- bridge refused at OAuth wall, never made an HTTP call |
| No bulk send | applied -- exactly one draft created in this run |
| No LinkedIn automation | applied |
| No form/application submit | applied |
| No social post | applied |
| No payment | applied |
| No unauthorized scan | applied |
| No browser automation on external websites | applied -- only seed file source registered |
| No scraping behind login | applied |
| No send unless Gmail controlled send path passes all gates | enforced -- bridge refused at OAuth wall |
| No send beyond daily cap | applied -- 0/3 used |
| No feature work unless live blocker found | applied -- one bug fix (real boot blocker), nothing else |

## Files changed this run

```
modified:   backend/app/main.py             (boot bug fix)
new:        backend/.opportunity_seed.json  (gitignored placeholder)
new:        backend/.opportunity_sources.json (gitignored skeleton)
new:        docs/Ultraview/DAENA_LIVE_ACTIVATION_RUN_01_REPORT.md
```

## Whether Sprint-21 can start

**Not yet.** Sprint-21 should start AFTER the operator runs steps
A-D above and successfully sends one real outreach email through
the controlled spine. Until that single live send succeeds, we
cannot claim the loop "works" -- only that "the code paths are
correct and the walls are honest." The remaining proof has to come
from the real Gmail HTTP round-trip, the real second-approval click,
the real message landing in someone's inbox.

If/when that single live send succeeds, the Sprint-21 direction the
operator suggested is the right one:

> Controlled grant/hackathon/application preparation
> -> local form draft
> -> approval
> -> manual submit first
> -> later controlled submit for specific safe platforms

That is a *form-draft* sprint, not a *new-architecture* sprint. The
form-draft surface (`backend/app/api/v1/form_drafts.py`,
`backend/app/models/form_draft.py`) already exists from Sprint-11
PR-3. Sprint-21 would extend it with: a controlled-execution handler
for "submit local form draft" (still Phase 3, still gated, still
manual-approve-first), then -- ONLY after that proves out -- a tiny
allowlist of platforms with stable, public submission APIs (NOT
browser automation; NOT scraping behind login).

## End

Activation run-01 closed. Backend healthy on 8000, frontend on 5173.
Both processes left running for the operator to continue from the
browser.

The walls held. The loop runs to the OAuth wall and refuses
honestly. The operator's next move is in their hands -- the four
interactive steps above.

Mythos out.
