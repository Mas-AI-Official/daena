# Moltbot-Style Provider Control & Onboarding (2026-01-29)

## Overview

Daena now supports **Moltbot-style provider control**: chat-provider adapters (Discord, Telegram) with onboarding wizard, standing instructions, and provider-level tool allowlists. Provider messages **never** call tools directly; they create **ToolRequests** that go through the Execution Layer (allowlist, approval mode, budget, audit). Default: all providers disabled until onboarded.

## Setup

### 1. Credentials (env only; never in git)

Add to `.env` (do **not** commit tokens):

```env
# Discord (optional)
DISCORD_BOT_TOKEN=your_discord_bot_token

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_WEBHOOK_SECRET_TOKEN=optional_secret_for_webhook_verification
```

### 2. Provider config (stored in repo-safe config)

- Path: `config/provider_config.json` (created on first save).
- Contains per-provider: `enabled`, `allowed_tools`, `standing_instructions`.
- No credentials are stored here.

### 3. Onboarding wizard

1. Open **Dashboard** → **Provider onboarding** (or sidebar **Provider onboarding**, or `/ui/provider-onboarding`).
2. **Step 1**: Choose providers (Discord, Telegram).
3. **Step 2**: Set tokens in `.env`, then click **Connect selected**.
4. **Step 3**: Set standing instructions; then set **allowed tools** (comma-separated, e.g. `git_status`, `health_check`, `list_tools`) and click **Save allowlist & enable** (this also enables the provider for receiving messages).
5. **Step 4**: Send a test message (channel ID / Telegram chat_id).

### 4. Webhooks (safe exposure)

- **Discord**: Configure your Discord app to send events to `POST /api/v1/providers/webhook/discord` (your public URL).
- **Telegram**: Set webhook to `POST /api/v1/providers/webhook/telegram` via Bot API `setWebhook`.

Only webhook endpoints receive inbound traffic. Control plane (dashboard, execution config) must **not** be exposed to the public internet; keep them behind auth/VPN or localhost.

## Security rules

- **Provider messages never call tools directly.** They generate a ToolRequest that goes through:
  - **Provider allowlist**: only tools in `allowed_tools` for that provider can be requested.
  - **Execution Layer**: `tool_enabled`, `approval_mode`, `require_approval_for_risky`, `max_steps_per_run`, `max_retries_per_tool`.
  - **Audit**: every action is logged in `logs/tools_audit.jsonl`.
- **Default**: all providers disabled until you enable them in the onboarding wizard.
- **Never expose** local admin or control plane to the public internet.

## Smoke test

**From project root (Windows):**
- `run_smoke_tests.bat` – runs provider smoke test.
- `scripts\run_provider_smoke_test.bat` – same, with venv detection and pip install of pytest/pytest-asyncio/httpx if needed.

**From shell:**
```bash
cd Daena_old_upgrade_20251213
python -m pytest tests/test_provider_tool_request_smoke.py -v -s
```

Tests verify: mock provider inbound message creates a ToolRequest; denial when provider disabled; denial when tool not in allowlist; health_check submission succeeds; execution config (approval mode) is respected.

## Files

See `IMPLEMENTATION_REPORT.md` in this folder for a file-by-file list of changes.

---

## Completion checklist

- [x] Provider adapters (Discord, Telegram) with common interface; credentials from env.
- [x] Provider config: enabled, allowed_tools, standing_instructions; default all disabled.
- [x] ToolRequest from provider messages via Execution Layer (allowlist, approval, audit).
- [x] Onboarding wizard (4 steps) in existing dashboard; sidebar and dashboard links.
- [x] Save allowlist enables provider; POST /config accepts plain JSON dict.
- [x] Smoke test script; docs and implementation report.
- [ ] **Optional next**: See `OPTIONAL_OPTIONS.md` – Slack adapter; LLM-based intent; smoke test in CI; standing instructions in flow.
