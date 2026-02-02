# Security

## Supported versions

- **Backend:** Python 3.10+; see `requirements.txt` and `requirements-lock.txt`.
- **Frontend:** Node 18 LTS+; see `frontend/package.json`.

## Vulnerability reporting

- **Email:** security@daena.ai (or open a private security advisory on GitHub).
- **Process:** Describe the issue, steps to reproduce, and impact. We will respond within 48 hours for critical/high.
- **Patch timeline:** Critical: 24–48h; High: 7 days; Medium: 30 days; Low: next release.
- **Responsible disclosure:** We ask for 90 days before public disclosure; we will credit researchers.

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
