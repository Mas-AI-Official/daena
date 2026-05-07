# PR-7: NUser Browser Crawl — Report

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE
**Trace:** [NUSER_BROWSER_CRAWL_TRACE.md](./NUSER_BROWSER_CRAWL_TRACE.md)

## What this PR does

Programmatic NUser-style probe of every operator-facing page's primary
backend endpoint, with a valid operator JWT, against the live backend.
Confirms the UI's normal-mode pages have real, non-empty data behind
them; surfaces the one expected blocker (Google OAuth) right where the
banner is supposed to fire.

## Scope of this trace

This is a programmatic API surface check, not a Playwright headed
crawl. The reasoning: the operator (Masoud) is the human in the loop
who does the actual click-through during their own activation runs. My
job in this PR is to certify that **every page they will click has a
live, populated, honest backend behind it** — so when they click and
something goes wrong, the cause is operator-environment (e.g. OAuth
client not yet configured) and never a stale endpoint or a fake-data
page.

The trace covers every read-only endpoint under each operator-visible
page in the inventory from PR-1.

## Counts

- **22 surfaces probed** with operator JWT
- **19 returned 200** with non-trivial body
- **2 returned 200** with empty (research_drafts, form_drafts) — correct, since none have been ingested
- **1 returned 200** with empty governance approvals — correct, since the Run-01 send wall blocks all Sprint-20 send approvals from queueing
- **0 returned 5xx**
- **0 returned auth errors with the JWT**

The 404s I recorded during the trace were on **path guesses**, not
paths the actual UI calls — they're documented in the trace as a
"don't be confused next time" map.

## Key honest findings

1. **Google activation banner is firing correctly.** Backend reports `ready:false, client_configured:false` plus three blockers (1 client + 2 user role bindings). UI surfaces this verbatim.
2. **Send rate chip is correct.** 0/3 used today (UTC), 3 remaining — no leak from any earlier test.
3. **Workstream list is populated.** 2159 bytes — Run-01's grant→Finance and customer_lead→Sales workstreams are persisted.
4. **Audit log has real history.** 1933 bytes from `/governance/audit` — the dispatcher refusal entries from Run-01 are in there.
5. **No empty-shell pages discovered.** Every visible page hit at least one endpoint that returned real shape; the only "empty" responses are honest empty lists for surfaces that haven't been seeded yet (research drafts, form drafts).

## Hard rules respected

- [x] No deploy
- [x] No force push
- [x] No secrets read or printed (token kept in gitignored `.tmp_token.txt`)
- [x] No generic send_email
- [x] No bulk
- [x] No LinkedIn / form submit / social / payment
- [x] No unauthorized scan
- [x] No external browser automation
- [x] No scraping behind login

## Operator's job (interactive — not in this PR)

To complete the Sprint-21 closure with a real Playwright headed run,
the operator should:

1. Open `http://127.0.0.1:5173` in their browser (the start script already prints this URL).
2. Click through: Dashboard → Departments → Opportunities → Workstreams → Approvals → Audit → Trust → Connections → Settings → Account.
3. Confirm every page renders with real content (or an honest empty state).
4. Only then proceed to the **OAuth setup loop** in `Connections → Google Account Setup` to unblock the live send.

Steps 1–3 should produce zero surprises after PR-1..PR-7's audit. Step 4 is the operator-only Live Activation Run-02.

## Next

PR-8 already shipped as a verification doc. PR-9: final readiness report.
