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

- **Start Service:** `python scripts/start_daenabot_hands.py` (Run in a separate terminal)
- **Status:** Logs to `logs/daenabot_hands.log`. Listens on port 18789.
- **Architecture:** WebSocket server executing sandboxed commands from the backend.

See [docs/README.md](docs/README.md) for prerequisites, env vars, and architecture.
