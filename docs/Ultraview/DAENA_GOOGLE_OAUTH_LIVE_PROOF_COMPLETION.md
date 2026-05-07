# Daena Google OAuth Live Proof — Completion Runbook
Date: 2026-05-07
Author: DAENA-GOOGLE-OAUTH-LIVE-PROOF-COMPLETION
Predecessor: Live validation report (`1181806`)

## Honest verdict (Mythos pre-flight)

This task is **operator-side**. I cannot:
- Open `console.cloud.google.com`
- Create the OAuth 2.0 Web client
- Type credentials into the Daena Account page
- Click Connect on a plugin card
- Approve a draft creation
- Approve a live send

What I CAN do is wire the runbook so tightly that you don't burn an hour on a wrong redirect URI or a stale role gate. I've already verified, against the running backend at `:8000`, every endpoint path and the exact callback URL Google must whitelist. Probe script at `scripts/check-google-oauth.ps1` lets you re-check state at any time.

Two moves ahead: the riskiest moment in this whole flow is the **first live send**. Sprint-15 + Sprint-16 already lock send to `{draft_id, owner_email}` only with a draft-snapshot integrity wall — but you still need to verify the wall HOLDS. The runbook ends with a deliberate sanity check for that.

## Verified facts (from the running backend, not from training data)

| Fact | Source | Value |
|---|---|---|
| Backend URL | running uvicorn | `http://127.0.0.1:8000` |
| Frontend URL | running Vite | `http://127.0.0.1:5173` |
| **OAuth callback URL** (Google must whitelist this exactly) | `connector_oauth.py:108-109` | `http://127.0.0.1:8000/api/v1/connectors/oauth/callback` |
| OAuth client save endpoint | OpenAPI | `POST /api/v1/account/oauth-clients/google` |
| OAuth client save body | `account_oauth_clients.py:60-68` | `{client_id: str, client_secret: str}` (both required, min 1 char) |
| Required role to save | `account_oauth_clients.py:117` | `ADMIN` |
| Per-account connect | `connector_oauth.py:91-147` | `GET /api/v1/connectors/{slug}/oauth/authorize` returns Google URL + state; OAuthConnectDrawer opens it |
| Status check | OpenAPI | `GET /api/v1/connections/google-setup-status` |
| Registered tools | controlled-execution probe | `gmail.create_draft`, `gmail.send_existing_draft` |
| Send rate limit | live probe | 3/day cap, 0 used today |

## The runbook (in exact order)

### Step 0 — Pre-flight

Both servers are still running from the validation session. If they aren't:

```powershell
cd D:\Ideas\Daena
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\cleanup-stale-dev.ps1
scripts\start-daena-local.bat
```

Then run the probe to confirm starting state:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check-google-oauth.ps1
```

Expected: `client_configured=False`, both accounts connected=False, READY=False. **Save this baseline output** so the after-state diff is unambiguous.

### Step 1 — Configure the Google OAuth client

In your browser:

1. Navigate to `https://console.cloud.google.com/apis/credentials?project=daena-467315`
2. Click `+ CREATE CREDENTIALS` → `OAuth client ID`
3. Application type: **Web application**
4. Name: `Daena Local Dev` (or similar — operator-visible only)
5. Authorized redirect URIs — add **EXACTLY ONE** of these (matching whichever URL you use to hit the backend):
   - `http://127.0.0.1:8000/api/v1/connectors/oauth/callback`
   - `http://localhost:8000/api/v1/connectors/oauth/callback` *(only if you sometimes hit `localhost` instead of `127.0.0.1`)*
6. Click CREATE
7. Copy the `Client ID` and `Client Secret` — you'll paste them in step 2

**Critical:** the redirect URI must be byte-exact. `http://127.0.0.1:8000/api/v1/connectors/oauth/callback/` (trailing slash) WILL NOT WORK. `https://` instead of `http://` WILL NOT WORK. Google enforces strict matching.

### Step 2 — Paste credentials into Daena

In the running frontend:

1. Open `http://127.0.0.1:5173/account#oauth-clients`
2. Find the Google row (slug=`google`)
3. Paste `client_id` + `client_secret`
4. Click Save

The frontend calls `POST /api/v1/account/oauth-clients/google` with `{client_id, client_secret}`. Server stores them in `backend/.daena_oauth_overrides.json` (chmod 0600 on POSIX, gitignored). Audit log emits `account_oauth_clients.saved` (no values logged).

After save, run the probe again:
```powershell
scripts\check-google-oauth.ps1
```

Expected after save: `client_configured=True`, `client_id_present=True`, `client_secret_present=True`. Both accounts still `connected=False`.

### Step 3 — Connect the founder account (Gmail / Drive / Calendar)

1. In the frontend, navigate to `http://127.0.0.1:5173/connections`
2. Click on the Gmail plugin card → OAuthConnectDrawer opens
3. Choose: **Founder account** (`masoud.masoori@mas-ai.co`)
4. Click Connect — frontend calls `GET /api/v1/connectors/gmail/oauth/authorize` → Google consent flow opens in popup
5. Sign in as `masoud.masoori@mas-ai.co` → grant Gmail scopes
6. Popup closes with success → status flips emerald
7. Repeat for **Drive** card → founder account → grant Drive scopes
8. Repeat for **Calendar** card → founder account → grant Calendar scopes

Run the probe:
```powershell
scripts\check-google-oauth.ps1
```

Expected:
- `founder_account.connected=True`
- `founder_account.instance_id=<some uuid>`
- `founder_account.connected_services=gmail, drive, calendar`
- `agent_account.connected=False` (still)

### Step 4 — Connect the agent account (DEFERRED for first proof)

**Founder-only path (operator's call 2026-05-07):** the agent account
(`daena@mas-ai.co`) is intentionally skipped for the first live-send proof.
Sending FROM the founder account is safer for the first send (clearly
human-authored, not an AI-bot mailbox; lower bounce/spam risk). The agent
account is added later when Daena needs to send AS the bot account in a
multi-account workflow.

After step 3 only (founder connected), the probe will show:

```
client_configured     : True
founder.connected     : True
founder.connected_services : gmail, drive, calendar
agent.connected       : False
agent.connected_services   :
READY                 : False     <-- EXPECTED for founder-only path
```

**`READY=False` is expected and not a blocker for the first proof.** The
backend's `google_setup_status` computes `ready = client_configured AND
founder.connected AND agent.connected`. The drill dispatch path does NOT
check `READY` — it checks the `ConnectorInstance` row for the specific
`owner_email`, which exists for the founder after step 3.

If founder is `connected=True` and `connected_services` includes
`gmail, drive, calendar`, you are past the OAuth blocker for the
founder-only proof. **Stop here and tell me.** I'll resume the
controlled-execution drill with `owner_email=masoud.masoori@mas-ai.co`.

### Optional step 4b — Connect agent account (POST first proof)

Same dance for `daena@mas-ai.co` once the founder-only proof is done +
audited. This is needed for full Daena-VP autonomy where Daena sends
AS the bot account. Not required tonight.

### Step 5 — Create one safe outreach draft (DO NOT proceed without operator approval)

Goal: prove `gmail.create_draft` end-to-end.

This is a controlled-execution dispatch. The operator approves the create_draft → Daena writes the draft into Gmail's drafts folder under `daena@mas-ai.co`. **No send happens.** The draft sits in Gmail until step 6.

The dispatch shape (when I run it on operator approval):

```json
POST /api/v1/integrations/controlled-execution/dispatch
{
  "tool": "gmail.create_draft",
  "owner_email": "daena@mas-ai.co",
  "to": "<recipient — operator-supplied, single address>",
  "subject": "<subject — operator-approved exact text>",
  "body": "<body — operator-approved exact text>"
}
```

Operator must approve this dispatch via the approval queue at `/governance/approvals`. **The approval row carries a draft snapshot** (Sprint-16) which the send path will later validate against.

**Stop point**: do not proceed to step 6 until the operator confirms the draft showed up in `mail.google.com` under daena@mas-ai.co with the EXACT recipient/subject/body they approved. Verify in Gmail UI directly.

### Step 6 — Send the draft (operator-approved live drill)

Once the draft is verified in Gmail:

```json
POST /api/v1/integrations/controlled-execution/dispatch
{
  "tool": "gmail.send_existing_draft",
  "owner_email": "daena@mas-ai.co",
  "draft_id": "<draft id from step 5 response>"
}
```

Operator must approve this **separately** from step 5 (the create-draft approval does NOT authorize send — `gmail_send_existing_draft.py:6-11` enforces this).

**Sprint-16 integrity wall fires here.** Before sending, the handler:
1. Re-fetches the draft from Gmail
2. Re-computes the canonical metadata snapshot
3. Compares against the snapshot taken at approval time
4. Refuses with a stable code if ANY field drifted: `draft_recipient_mismatch`, `draft_subject_mismatch`, `draft_owner_email_mismatch`, `draft_metadata_hash_mismatch`

**This is the moment of truth.** If the wall fires correctly, you can trust live send. If the wall fails to fire when it should (i.e., you edit the draft in Gmail between approval and send and it sends anyway), there's a bug. Test this.

### Step 7 — Verify in Gmail Sent + audit trail

After successful send:
1. `mail.google.com` under `daena@mas-ai.co` → Sent → confirm the message exists with the same recipient/subject/body
2. Daena audit log via `/governance/audit` → confirm the row carries the draft_snapshot, action_type=`gmail.send_existing_draft`, decision=APPROVED, outcome=SUCCESS
3. Probe `send-rate-limit` again — `used` should have incremented by 1

## Probe script reference

`scripts/check-google-oauth.ps1` is the one-shot read-only state checker. Run it any time to see:
- Backend health
- Dev token mintable (proves identity layer works)
- google-setup-status (full ladder)
- Registered controlled-execution tools (gmail.create_draft + send_existing_draft confirmed)
- Send rate limit (today's cap + remaining)

Output stays in your terminal; no values are persisted.

## Refusal codes you may hit

| Code | Cause | Fix |
|---|---|---|
| `oauth_not_connected:google` | Connect an account before draft/send | Step 3 or 4 |
| `client_configured=false` after step 2 | Wrong slug or non-ADMIN role | Verify slug = `google`, verify your user has ADMIN role |
| `redirect_uri_mismatch` (from Google) | Redirect URI in Google Cloud doesn't match what Daena sent | Re-check Step 1, item 5 — must be byte-exact |
| `payload_field_missing:draft_id` | Draft id missing on send | Use the draft id returned by create_draft response |
| `draft_recipient_mismatch` | Draft was edited in Gmail between approval and send | EXPECTED behaviour. Re-create + re-approve |
| `draft_owner_email_mismatch` | Snapshot says one account, draft is in another | Use the same `owner_email` for create + send |
| `draft_metadata_hash_mismatch` | Snapshot drifted but no specific field caught | Re-snapshot via re-create |

If you hit a code not in this table, the probe script + audit log will say which gate fired.

## Sprint-22 readiness gate

Sprint-22 may start ONLY after all three of:

1. ✅ Google OAuth client configured (step 2 done, probe shows `client_configured=True`)
2. ✅ Both accounts connected to Gmail + Drive + Calendar (probe shows `READY=True`)
3. ✅ One controlled draft creation + one operator-approved send completed cleanly with audit row + Gmail Sent verification

The first two are operator action. The third requires me to re-engage. **Tell me when you're at step 5 (READY=True) and I'll resume.**

## Servers

Backend `:8000` and frontend `:5173` are still running. Stop them via `scripts\cleanup-stale-dev.ps1` when done.

## What I will NOT do without explicit operator approval

- Print or log any client_secret or access_token value
- Trigger an actual send via dispatch (only after step 6 explicit approve)
- Edit your `claude_desktop_config.json` to fix the 4 unscoped MCPs (separate concern; deferred)
- Bypass the dispatcher's six gates
- Skip the draft-snapshot integrity wall
- Send to any recipient that isn't operator-supplied for this exact drill
