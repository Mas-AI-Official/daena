# DAENA Local UI Visual Smoke -- VERIFIED

**Run at:** 2026-05-03 ~20:15 local
**Branch:** `rebuild-connections-mcp-runtime`
**Last sprint commit:** `07ab081` (Sprint-2 PR-4 docs pin)
**Driver:** chrome-devtools MCP (automated browser snapshot)
**Verdict:** **PASS** -- no UI fix PR required, Sprint-3 unblocked

---

## TL;DR

Every item on the operator's visual smoke checklist either PASSES or
is correctly DEFERRED-BY-DESIGN (waiting on real OAuth instance, not
broken UI). Backend integration is live: 18/18 API requests returned
200. Console clean (1 pre-existing a11y advisory, non-blocking).
PluginDetailDrawer renders the full 4-step probe ladder + 5 skill
chips with honest "Install or set up first" disabled state.

---

## Smoke checklist results (operator's wording)

| # | Check | Status | Evidence |
|---|---|---|---|
| 1 | Brain / Plugins / Advanced tabs show | PASS | Snapshot uid=5_76 / 5_77 / 5_78 all present |
| 2 | Plugin cards load | PASS | 57 cards rendered with provider icons, names, capability chips, status badges |
| 3 | No black overlay | PASS | Page fully interactive; no overlay element in snapshot |
| 4 | No "Backend Not Found" | PASS | Header "0 connected | 3 needs auth | 1 installed | 53 available" -- live backend counts (1 Installed = the running llama-server) |
| 5 | GitHub / Slack / Sentry / Filesystem cards open | PASS | All 4 visible in marketplace; GitHub drawer opened end-to-end (uid=6_*) |
| 6 | OAuth Refresh / Disconnect / Archive buttons appear on connected OAuth plugins | DEFERRED-BY-DESIGN | OAuthLifecyclePanel self-gates to `null` when no CONNECTED instance exists. Currently 0 connected OAuth instances. Panel is wired + tsc-clean (Sprint-2 PR-1 commit `ce6e244`) -- visual verify needs a completed OAuth flow |
| 7 | MCP Install / Test / Connected flow visible | PASS | Drawer renders 4-step probe ladder (uid=6_17-29): "MCP server installed | Credential present | Probe successful | Skills ready" + Install button + npm command + env var names + vendor doc link |
| 8 | Skill chips show Run only after plugin is callable | PASS | All 5 GitHub skills (uid=6_32-36) render as DISABLED with tooltip "Install or set up GitHub first to enable this skill". When plugin reaches `callable`, they enable -- exact contract documented in drawer copy uid=6_37-43 |

---

## Console + Network audit

### Console (4 messages, all benign)
- `[debug] [vite] connecting...`
- `[debug] [vite] connected.`
- `[info] React DevTools install hint`
- `[issue] A form field element should have an id or name attribute (count: 1)` -- pre-existing a11y advisory, not a Sprint-2 regression

### Network (18 XHR/fetch -- all 200)
- `/api/v1/heartbeat/status` x2
- `/api/v1/health` x4
- `/api/v1/security/mode/state`
- `/api/v1/governance/approvals?status=PENDING&page_size=1` x2
- `/api/v1/execution/tasks?status=RUNNING&page_size=1` x2
- `/api/v1/execution/tasks?status=PENDING&page_size=1` x2
- `/api/v1/notifications?limit=20` x2
- `/api/v1/settings/user`
- `/api/v1/connections/v2/marketplace/cards`
- `/api/v1/connections/v2`

Zero 4xx/5xx. Zero CORS errors. Zero auth errors.

---

## What the drawer proved (GitHub example, uid=6_*)

The PluginDetailDrawer fully realizes the "Install -> Test -> Connected -> Run skill" framing from `MCP_SETUP_GUIDE_FOR_PROMOTED_SKILLS.md` (Sprint-2 PR-2):

1. **WHAT DAENA CAN DO** -- 3 example chat prompts as draft buttons (do NOT auto-send)
2. **CONNECTION STEPS** -- 4-step probe ladder with state per step
3. **SKILLS** -- 5 chips, all disabled with "Install or set up first" tooltip until the plugin reaches `callable`
4. **PERMISSIONS** -- Read/Write/Network scope + env var NAMES (`GITHUB_PERSONAL_ACCESS_TOKEN`) -- never values
5. **INSTALL / SETUP (NPM)** -- 5-step copy-paste flow with explicit "Daena does NOT execute it for you" warning, vendor doc link, post-install "Discover installed tools" instruction
6. **SOURCE & TRUST** -- Vendor official + Verified date
7. **COMPATIBILITY** -- AUTH/RISK/INSTALL/OS metadata
8. **Vendor documentation** link

This is the contract delivered by Sprint-2. UI is honest about what it
can and can't do, never fakes a Run button on an uncallable plugin,
never asks the operator to paste tokens into the catalog UI.

---

## Brain tab (also verified)

| Runtime | State | Note |
|---|---|---|
| Claude Code | Ready, set as Main Brain | Claude Max subscriber |
| Codex (OpenAI) | Ready | masoud.masori@gmail.com |
| Gemini CLI (Google) | Ready | masoud.masori@gmail.com |
| Grok (xAI) | Not installed | offline, controls disabled |
| vLLM (Local GPU) | Not installed | offline, controls disabled -- **see "Pre-existing finding" below** |
| Ollama (Local) | Ready | Local (free) |
| Groq Cloud (API) | Configured | 8 models discovered |
| Google Gemini (API) | Configured | 3 models discovered |
| Perplexity AI (API) | Configured | 3 models discovered |

Plus: live "Main Brain persists to User.settings.primary_runtime"
explanatory copy. Experimental Override checkbox honored.

### Pre-existing finding (not a Sprint-2 regression)

The Brain tab marks **vLLM (Local GPU) = Not installed / offline** even
though `llama-server.exe` is running on port 8080 and Daena's vLLM
adapter targets `VLLM_BASE_URL=http://127.0.0.1:8080/v1` per project
CLAUDE.md. The Brain-tab probe likely uses a different code path
(legacy probe) that doesn't hit the OpenAI-compatible endpoint of
llama-server. This is OUT OF SCOPE for Sprint-2 and was not introduced
by any sprint-2 PR -- noting it for the operator as a Sprint-3 candidate
(small UX correctness ticket).

---

## What the operator still has to do manually (unchanged from Sprint-2 status)

The visual surface is ready. To turn promoted skills from `code-live`
to `actually-fires`, the operator still needs to install the MCPs +
provide tokens via the UI:

1. **Filesystem MCP** -- `npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>`
2. **GitHub MCP** -- `npx -y @modelcontextprotocol/server-github` + `GITHUB_PERSONAL_ACCESS_TOKEN`
3. **Sentry MCP** -- `npx -y @sentry/mcp-server` + `SENTRY_AUTH_TOKEN` + `SENTRY_HOST`
4. **Slack MCP** -- per `MCP_SETUP_GUIDE_FOR_PROMOTED_SKILLS.md` Slack section
5. **HuggingFace MCP** -- still blocked-by-design (HTTP-MCP, no stdio)

The drawer makes step-by-step instructions visible per plugin. Daena
will NOT execute those install commands automatically -- consistent
with the project's CLAUDE.md hard-stop rule "no npm/pip/docker install
not in operator-confirmed flow."

---

## Decision: NEXT ACTION

Visual smoke PASSED. **No `PR-LOCAL-UI-VISUAL-SMOKE-FIX` is needed.**

Sprint-3 is unblocked. Recommended order from `DAENA_LOCAL_USABILITY_SMOKE_STATUS.md`:

1. **Option C tidy first** (low risk, fast) -- `PR-CONN-DB-DESCRIBE-SCHEMA-PROMOTE` + `PR-CONN-PLUGIN-INSTALL-UX-POLISH`
2. **Option A** (unlocks Gmail+Drive for real use) -- `PR-CONN-OAUTH-INVOKER` + `PR-CONN-PHASE2X-GMAIL-DRIVE`
3. **Option B** (gates Phase 3 writes) -- `PR-CONN-ASSET-SHIELD-CONSENT`

Per the established pattern, the operator authorizes the next sprint
with the specific brief. Awaiting that authorization.

---

## Hard stops encountered during smoke

NONE. Read-only browser navigation + snapshot only. No state mutation,
no install, no token entry, no external request, no file write outside
this report.
