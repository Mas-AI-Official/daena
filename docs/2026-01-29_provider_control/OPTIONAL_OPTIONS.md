# Optional Provider Options (2026-01-29)

Optional enhancements for Moltbot-style provider control. None required for current Discord/Telegram onboarding.

---

## 1. Slack adapter

**What:** Add a third provider `slack` with the same interface (connect, disconnect, status, send_message, receive_message, verify_webhook).

**How:**
- Add `backend/providers/slack_adapter.py` implementing `ProviderBase`; credentials from `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` (env).
- In `backend/providers/config.py` `_DEFAULT["providers"]`, add `"slack": { "enabled": false, "allowed_tools": [], "standing_instructions": "" }`.
- In `backend/providers/registry.py`: `_credentials_for("slack")`, `get_adapter("slack")` → `SlackAdapter`.
- In `backend/routes/providers.py`: add `POST /webhook/slack` that parses Slack Events API payload and calls `_handle_inbound`.
- In onboarding UI, provider list is loaded from API so Slack will appear once added to config.

**Dependencies:** `httpx` (already in requirements). Slack uses signing secret for `verify_webhook`.

---

## 2. LLM-based intent for provider messages

**What:** Instead of keyword-only mapping (health check → health_check, run git status → git_status), use the LLM to map free-form provider messages to (tool_name, args) so users can say “check if the server is up” or “list what tools I can run”.

**How:**
- In `backend/services/provider_tool_request.py`, add an optional path: if `_parse_intent(text)` returns None, call a small LLM (or existing Daena chat) with prompt: “Given standing_instructions and user message, output exactly one line: TOOL_NAME json_args” or “NONE”.
- Parse LLM output and create ProviderToolRequest only if tool_name is in provider allowlist.
- Keep keyword path as fast path; LLM as fallback when configured (e.g. `PROVIDER_LLM_INTENT=1`).

**Dependencies:** Existing Ollama/LLM stack. No new pip install.

---

## 3. Smoke test in CI

**What:** Run provider smoke tests in GitHub Actions (or other CI) on every push/PR.

**How:**
- Add a job in `.github/workflows/*.yml` (or create `ci.yml`):
  - Checkout, set up Python 3.10+, install from `requirements.txt`, set `PYTHONPATH`, run `pytest tests/test_provider_tool_request_smoke.py -v`.
- Optional: also run a quick backend health check (e.g. `curl` to `/health`) after starting uvicorn in background.

---

## 4. Encrypted provider config (optional)

**What:** Store provider tokens in encrypted config instead of env (e.g. for multiple Slack workspaces). Not required for current single-token-per-provider design.

**How:** Use a small secrets module (e.g. Fernet with key from env `PROVIDER_CONFIG_KEY`); write/read `config/provider_credentials.enc`; decrypt in registry when building credentials. Prefer env for simplicity unless you need multiple tokens per provider.

---

## 5. Standing instructions in ToolRequest flow

**What:** Today standing_instructions are stored but not yet passed into the Execution Layer or LLM. Use them when resolving intent or when Daena replies to provider messages.

**How:**
- In `create_tool_request_from_message`, pass `get_standing_instructions(msg.provider_id)` into any LLM-based intent step (see option 2).
- When replying to provider (e.g. after tool run), prepend standing_instructions to the reply context so Daena’s tone/constraints are applied.

---

## Summary

| Option              | Effort | Suggestion                          |
|---------------------|--------|-------------------------------------|
| Slack adapter       | Medium | Add when you need Slack.            |
| LLM-based intent   | Medium | Add when keyword list is too limited. |
| Smoke test in CI   | Low    | **Recommended** – add to existing or new workflow. |
| Encrypted config   | Low–Med| Skip unless multi-tenant tokens.   |
| Standing in flow   | Low    | **Recommended** – wire into LLM intent and reply. |
