---
name: auto-browser
description: Human-in-the-loop MCP browser agent. Controls a real Playwright browser via Docker with noVNC visual takeover, reusable auth profiles, PII scrubbing, and full audit trail. Use when browser tasks need human oversight, saved login sessions, or compliance logging. Start Docker first.
---

# auto-browser — MCP Browser Agent with Human Oversight

Runs at `D:\Ideas\auto-browser`. Exposes browser control as MCP tools to Claude Code and Daena.

## When to Use vs Alternatives

| Tool | Use when |
|------|----------|
| **auto-browser** | Needs human takeover, saved auth profiles, audit trail, social posting |
| **autobrowse** | Training a reusable scraping skill via iterative loops |
| **Playwright plugin** | Simple one-off browser actions in current session |

## Start the Server

```bash
cd D:\Ideas\auto-browser
docker compose up --build -d
```

Endpoints after startup:
- MCP API: `http://127.0.0.1:8000/mcp`
- Dashboard: `http://127.0.0.1:8000/dashboard`
- Visual takeover (noVNC): `http://127.0.0.1:6080/vnc.html`

MCP is pre-wired in `~/.claude/settings.local.json` — tools appear automatically once Docker is running.

## Key MCP Tools (curated profile)

- `navigate` — go to URL
- `snapshot` — accessibility tree of current page
- `click` / `fill` / `type` — interact with elements
- `screenshot` — capture current state
- `save_auth` / `load_auth` — persist login sessions by name
- `approve` / `reject` — human approval gate for sensitive actions
- `takeover` — open noVNC for manual control

## Auth Profile Workflow (e.g. for social posting)

```
1. load_auth("twitter")     # loads saved Twitter session
2. navigate(url)            # go to post page
3. fill / type / click      # compose post
4. approve("post tweet")    # human confirms before submit
5. click(submit)
6. save_auth("twitter")     # save refreshed session
```

## ContentOps Integration

auto-browser is the **preferred backend for social posting** when platform requires login persistence:
- Replace Puppeteer `page.fill()` with auto-browser `fill()` + `save_auth()`
- Use `approve()` gate for all 🟠 actions per CLAUDE.md social media table
- PII scrubbing is on by default — screenshots won't leak credentials

## Daena Integration

Daena's BrowserAgent should route through auto-browser MCP when:
1. Task requires saved auth state (social platforms, admin portals)
2. Governance mode = GOVERNED (approval gate required)
3. Operator wants visual oversight via noVNC

## Hardware

- Requires Docker Desktop running
- ~500 MB RAM for browser-node + controller containers
- Port 8000 (API), 6080 (noVNC), 5900 (VNC) must be free

## Known Failure Modes

- "connection refused" → Docker not running; `docker compose up -d`
- MCP tools not appearing → restart Claude Code after settings.local.json was written
- Page hangs → open noVNC at :6080 and take over manually
