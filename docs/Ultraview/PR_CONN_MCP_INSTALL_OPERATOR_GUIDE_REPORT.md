# PR-CONN-MCP-INSTALL-OPERATOR-GUIDE — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** _to be filled in after squash_
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-2 (PR-2 of 4)

---

## 1. Goal

Make it crystal-clear how Masoud installs the four MCP servers needed
to actually exercise the promoted Phase 2.x read-only skills shipped
in Sprint-1 (PR-1 `bdb1ca8` + PR-2 `4f367b3`).

Today the skills are code-live but return `needs_connection` because
the underlying MCPs aren't installed in
`~/AppData/Roaming/Claude/claude_desktop_config.json`. This PR ships
ONE operator-facing guide that walks through:

- **filesystem MCP** (`@modelcontextprotocol/server-filesystem`)
- **Hugging Face MCP** (HTTP at `huggingface.co/mcp`)
- **GitHub MCP** (`@modelcontextprotocol/server-github`)
- **Sentry MCP** (`@sentry/mcp-server`)

---

## 2. Files added

### `docs/Ultraview/MCP_SETUP_GUIDE_FOR_PROMOTED_SKILLS.md`

The operator-facing guide itself. See §4 below for content.

### (this report)

---

## 3. What the guide is + isn't

**The guide is:**
- Step-by-step instructions per MCP for the operator to follow in the
  Plugins UI of Daena
- Exact command + required env var NAMES (never values)
- Auth notes (where to obtain the token, what scope to request)
- Probe step (how to verify the MCP responded `tools/list`)
- "Install → Test → Connected → Run skill" copy mirroring the
  founder's brief

**The guide is NOT:**
- Auto-install code. The existing `/connections/extensions/install`
  endpoint already writes to `claude_desktop_config.json` when the
  operator clicks "Install" in the Plugins UI — that flow is
  unchanged. The guide is a pointer to it, not a replacement.
- A npm/pip/docker invocation from Claude. Per hard-stop #9, the
  install action remains operator-confirmed via the existing UI.

---

## 4. Hard rules — all honored

| Rule | Enforced? |
|---|---|
| No npm/pip/docker install run by Claude | YES — guide describes; operator clicks the existing Plugins UI install button |
| Setup guide must show command, env var NAMES, auth, probe | YES — each MCP has all 4 sections |
| No secret values | YES — env var NAMES only (`GITHUB_PERSONAL_ACCESS_TOKEN`, `SENTRY_AUTH_TOKEN`); never values; never sample real tokens |
| Add copy explaining "Install → Test → Connected → Run skill" | YES — Section 1 of the guide is exactly this 4-step framing |

---

## 5. Verification

Per hard-stop #10, no test failures introduced. This is a pure docs PR.

```
$ .venv/Scripts/python.exe -m pytest tests/test_connections.py tests/test_skill_executor_phase2.py
76 passed in 29.07s  (no change from PR-1 of this sprint)

$ npx tsc --noEmit
(no output -- clean, no change)
```

---

## 6. Branch state

```
<this commit>  docs/ui: clarify MCP setup for promoted read-only skills
8923f6d        docs: pin PR-1 commit hash and update sprint-2 log
ce6e244        fix: wire OAuth lifecycle actions into Connections UI
a4cfc61        docs: finalize sprint log with PR-4 row + sprint summary
```

Sprint-2 state: PR-2 SHIPPED. Continuing autopilot to PR-3 (Slack/Gmail/Drive promotion).
