# Security

## Secrets: environment variables only

**Do not hardcode API keys, passwords, or tokens in source code.** All secrets must be supplied via environment variables (e.g. `.env` or system env). See `.env.example` for the list of supported variables.

- **Execution Layer:** `EXECUTION_TOKEN` (required for `/api/v1/execution/*` when set on server)
- **Web search:** `BRAVE_API_KEY`, `SERPER_API_KEY`, `TAVILY_API_KEY`
- **Voice / LLM:** `OPENAI_API_KEY`, `AZURE_OPENAI_API_KEY`, `ELEVENLABS_API_KEY`
- **Auth:** `JWT_SECRET_KEY` or `SECRET_KEY`
- **Integrations:** `DISCORD_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET_TOKEN`
- **Windows Node:** `WINDOWS_NODE_TOKEN`
- **Monitoring:** `DAENA_MONITORING_API_KEY` (optional)

Copy `.env.example` to `.env` and set values there. Never commit `.env` to version control.
