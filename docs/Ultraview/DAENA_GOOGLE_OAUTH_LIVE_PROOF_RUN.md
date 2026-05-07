# Daena Google OAuth Live Proof Run

**Date opened:** 2026-05-06
**Run name:** DAENA-GOOGLE-OAUTH-LIVE-PROOF-RUN
**Status:** ⏸ **Waiting on operator interactive OAuth steps.**
**Verdict at hand-off:** local environment ready; activation summary returns the exact three blockers; nothing was sent.

This doc is a **living checklist**. Each section is one step, in order. Update the [ ] boxes as you go; re-run the verification probe at the bottom of each section to confirm the state before moving on.

---

## Pre-flight (Daena's side — DONE before this hand-off)

- [x] Backend healthy (`/api/v1/health` → `status:healthy`, db healthy, version 2.0.0)
- [x] Frontend up on `http://[::1]:5173` (Vite default IPv6 bind; `start-daena-local.bat` probes both)
- [x] Sprint-21 readiness verdict: **READY_FOR_LOCAL_BUSINESS_BETA — conditional on this OAuth run**
- [x] Activation summary endpoint live and returning honest blockers

### Live activation summary (captured 2026-05-06, immediately before this run)

```json
{
  "ready": false,
  "client_configured": false,
  "blockers": [
    {"role": "client",  "email": null,                          "missing": ["client_id", "client_secret"]},
    {"role": "founder", "email": "masoud.masoori@mas-ai.co",     "missing": ["gmail", "drive", "calendar"]},
    {"role": "agent",   "email": "daena@mas-ai.co",              "missing": ["gmail", "drive", "calendar"]}
  ]
}
```

This is the precise state the UI banner is rendering on `/opportunities` right now.

---

## Step A — Configure Google OAuth client (operator only)

### A.1 Open the Google Cloud Console

Go to: **https://console.cloud.google.com/apis/credentials**

If you haven't already:
- Create or select a project (e.g. "Daena-Local")
- In **APIs & Services → Library**, enable: **Gmail API**, **Google Drive API**, **Google Calendar API**

### A.2 Create OAuth 2.0 Client ID

- **APIs & Services → Credentials → Create Credentials → OAuth client ID**
- Application type: **Web application**
- Name: `Daena Local`
- Authorized redirect URIs (add both — Daena's connector OAuth callback handles the loopback):
  - `http://127.0.0.1:8000/api/v1/connectors/oauth/callback`
  - `http://localhost:8000/api/v1/connectors/oauth/callback`

If the OAuth consent screen prompts you to set it up first:
- User type: **External**
- App name: `Daena Local`
- User support email: `masoud.masoori@mas-ai.co`
- Scopes: add `gmail.compose`, `gmail.send`, `gmail.modify`, `drive.file`, `calendar.events` (or the broader equivalents Daena's connector requests on first use — Daena will surface the requested scopes at consent time)
- Test users: add **masoud.masoori@mas-ai.co** AND **daena@mas-ai.co** (required while the app is in Testing mode; otherwise consent fails for non-test users)

### A.3 Paste credentials into Daena

- In Daena: open **http://127.0.0.1:5173/account/oauth-clients** (or in the sidebar: avatar dropdown → Account → OAuth Clients)
- Find the **Google (Gmail / Calendar / Drive)** row
- Paste:
  - **client_id** → `…-….apps.googleusercontent.com`
  - **client_secret** → `GOCSPX-…`
- Save

### A.4 Verify

Refresh `/opportunities` — the banner should drop the first blocker (`role:client`).

Optional CLI verification (no secrets read, only "configured: true|false"):

```powershell
# (operator-side; from backend with venv activated)
cd D:\Ideas\Daena\backend
.\.venv\Scripts\python.exe -c "
import asyncio, requests
from app.core.database import get_db
from app.core.security import create_access_token
from sqlalchemy import select
from app.models.identity import User
async def main():
    async for s in get_db():
        u = (await s.execute(select(User).where(User.email == 'masoud.masoori@mas-ai.co').limit(1))).scalar_one_or_none()
        tok = create_access_token(user_id=str(u.id), tenant_id=str(u.tenant_id), role='FOUNDER', email=u.email, display_name='')
        r = requests.get('http://127.0.0.1:8000/api/v1/connections/google-activation-summary', headers={'Authorization': f'Bearer {tok}'})
        print(r.json())
        break
asyncio.run(main())
"
```

Expect: `client_configured: true` after A.3.

- [ ] A.1 Console project + APIs enabled
- [ ] A.2 OAuth client + consent screen + test users
- [ ] A.3 client_id + client_secret pasted into Daena
- [ ] A.4 Activation summary now reports `client_configured: true`

**STOP if this fails.** Common gotchas:
- Authorized redirect URI mismatch → activation will succeed at the form level but consent will redirect to an error
- Test users missing → consent fails for both accounts
- Missing API enablement → first scope request fails with `invalid_scope`

---

## Step B — Connect masoud.masoori@mas-ai.co (operator only)

- Open **http://127.0.0.1:5173/connections** (Apps tab)
- The **Google Account Setup Guide** card should now show **client_id + client_secret present** (post-A.3) instead of the prior "open Settings → OAuth Clients and paste…" prompt
- Click **Connect Gmail** for the founder row → consent prompt opens in a new tab
- Sign in as **masoud.masoori@mas-ai.co**, accept all requested scopes
- Repeat for **Drive** and **Calendar** (or Daena may bundle them — the UI will show)

**Verify:** Refresh the page. The founder row should now show all three scopes as connected; the activation banner on `/opportunities` should drop the second blocker.

- [ ] B.1 Gmail connected for masoud.masoori@mas-ai.co
- [ ] B.2 Drive connected
- [ ] B.3 Calendar connected
- [ ] B.4 Activation summary `founder` blocker missing list is `[]`

---

## Step C — Connect daena@mas-ai.co (operator only)

Same flow as Step B, but **sign in as daena@mas-ai.co** at the consent screen. (You may need to sign out of Google first or use a separate Chrome profile / Incognito window to ensure the second account's consent is captured separately.)

- [ ] C.1 Gmail connected for daena@mas-ai.co
- [ ] C.2 Drive connected
- [ ] C.3 Calendar connected
- [ ] C.4 Activation summary `agent` blocker missing list is `[]`

After C.4, the activation summary should be:

```json
{ "ready": true, "client_configured": true, "blockers": [] }
```

The `/opportunities` banner should disappear automatically (it only renders while `!activation.ready`).

---

## Step D — Run the first controlled outreach loop (operator-driven; Daena assists)

Once the activation summary reports `ready: true`, drop me back into this conversation and I'll do the deterministic parts:

### D.1 (Daena) — Run discovery

I will issue: `POST /api/v1/opportunities/run-discovery {top_n: 10}` and capture the result. Already proven during Run-01: the seed file produces 3 deterministic opportunities (grant 57, accelerator 54, customer_lead 52).

### D.2 (Operator picks one safe target)

You select **one** opportunity from the inbox at `/opportunities`. Recommended for the first proof: a low-stakes recipient — your own personal email, or a single trusted partner who has explicitly opted in. Add the recipient email to:

- `DAENA_DRILL_RECIPIENT_ALLOWLIST` env var (comma-separated), AND
- the opportunity's `raw_metadata.recipient_email`

(Per Sprint-20 PR-5 design: an email outside the allowlist refuses with `drill_recipient_not_in_allowlist`; an opportunity without `recipient_email` refuses with `drill_recipient_not_present`.)

### D.3 (Daena) — Create workstream

I will click the **Workstream** button on your chosen opportunity card (or call `POST /api/v1/opportunities/{id}/create-workstream`). The opportunity is promoted to the right department (e.g. customer_lead → Sales).

### D.4 (Daena) — Draft outreach via VP chat

Chat command: `draft outreach for opp <uuid> to <email>` → creates a `BizOutreachDraft` with subject + body.

### D.5 (Daena) — Queue Gmail draft

Chat command: `send draft <draft_uuid>` → routes through controlled-execution dispatcher → enqueues `gmail.create_draft` approval. **Stops here for operator approval.** No Gmail API call yet.

### D.6 (Operator) — Approve `gmail.create_draft`

Open `/governance/approvals`. There will be a pending row. Read the payload (subject + body verbatim). If it's correct, click **Approve**. Daena calls Gmail's draft creation endpoint via the OAuth bound in Step B/C. The draft now exists in the **Drafts** folder of `daena@mas-ai.co` (or whichever account is bound as the agent — verify in Gmail UI).

### D.7 (Operator) — Approve `gmail.send_existing_draft`

A second approval row appears. **This is the final, irreversible gate.** Verify:
- Recipient email is correct
- Body still reads correctly
- Send-rate chip on `/opportunities` shows ≥1 send remaining
- Recipient not in suppression list

If all good: click **Approve send**. Daena issues `users.drafts.send` on the bound Gmail account. The send-rate counter increments to 1/3 used today.

### D.8 (Daena) — Verify audit row

I will probe `GET /governance/audit?page_size=10` and confirm the two approval-grant rows + the dispatch event exist with the correct payload hashes.

### D.9 (Operator) — Verify Gmail Sent folder

Open **gmail.com** logged in as `daena@mas-ai.co` (the agent account). Go to **Sent**. Confirm the email is there with the correct recipient, subject, body, and timestamp.

### D.10 (Daena) — Update this doc + report verdict

I'll fill in:
- timestamp of first send
- subject + recipient (last 4 chars of recipient hash, never full)
- audit row IDs
- send-rate chip after-state
- whether Sprint-22 may start

**Hard rules respected throughout:**
- No deploy
- No secrets printed (this doc never contains client_id, client_secret, or token values)
- No generic send_email
- No bulk send (3-per-day rate limit + recipient allowlist + recipient suppression list, all enforced by drill module + send-bridge)
- No form submit / post / pay / LinkedIn / browser automation
- No external action without an explicit operator approval click in `/governance/approvals`

---

## Where we are right now

| Item                                          | Status                  |
|-----------------------------------------------|-------------------------|
| Backend healthy                               | ✅                       |
| Frontend up                                   | ✅ on `[::1]:5173`       |
| Activation summary returns honest blockers    | ✅ (above)               |
| Google OAuth client configured                | ❌ — Step A required     |
| masoud.masoori@mas-ai.co connected            | ❌ — Step B required     |
| daena@mas-ai.co connected                     | ❌ — Step C required     |
| First Gmail draft created                     | ❌ — pending Step D.5/D.6|
| First controlled send completed               | ❌ — pending Step D.7    |
| Audit row verified                            | ❌ — pending Step D.8    |
| Gmail Sent folder verified                    | ❌ — pending Step D.9    |
| Sprint-22 may start                           | ❌ — gated on D.7+D.9    |

## Sprint-22 gate

Sprint-22 (controlled grant / form / hackathon submission) **must not start** until D.7 succeeds (one real outreach actually lands in someone's inbox) and D.9 confirms it. Once it does, this doc gets the verdict and Sprint-22 brief follows.

---

**Operator action requested:** complete Steps A, B, C. Drop back into this thread when activation summary reports `ready: true`. I'll run D.1–D.5 and D.8, you do D.6, D.7, D.9.
