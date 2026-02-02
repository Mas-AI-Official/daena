# Daena AI VP

World's most advanced AI agent system (48 agents, NBMF memory, hex-mesh communication).

**Full documentation:** [docs/README.md](docs/README.md)

## Access (backend at http://localhost:8000)

- **Command Center**: http://localhost:8000/command-center (redirects to UI)
- **Control Panel**: http://localhost:8000/ui/control-panel (Skills, Governance, DaenaBot Tools, Crypto)
- **API base**: http://localhost:8000/api/v1
- **API docs**: http://localhost:8000/docs

## Deploy

```powershell
# Windows (PowerShell; run from repo root)
.\scripts\deploy_production.ps1
```

```bash
# Linux/Mac
chmod +x scripts/deploy_production.sh
./scripts/deploy_production.sh
```

## DaenaBot Hands (tool runtime)

- **Install (Windows + Docker):** `.\scripts\setup_daenabot_hands.ps1` — clones OpenClaw, generates token, binds to 127.0.0.1 only, writes `DAENABOT_HANDS_URL` / `DAENABOT_HANDS_TOKEN` to `.env`.
- **Status:** `GET /api/v1/hands/status` — configured, reachable, message (token never returned).
- **Architecture:** [docs/ARCHITECTURE_DAENABOT_HANDS.md](docs/ARCHITECTURE_DAENABOT_HANDS.md) — 8 departments → ToolBroker → policy → Approvals Inbox → Hands → audit.

See [docs/README.md](docs/README.md) for prerequisites, env vars, and architecture.
