# Local-First Daena Architecture

**Status:** PRIMARY operating mode (effective 2026-05-01)
**Operator:** Masoud Masoori (founder, single user)
**Audience:** Founder + Claude Code/Codex CLI engineering partners

> Daena's primary deployment is the founder's Windows + WSL2 + RTX
> 4060 workstation. Cloud Run is **paused** (see
> `CLOUD_DEPLOYMENT_PAUSED_DECISION.md`) and remains as an optional
> future surface for demos / managed-client engagements.

---

## 1. Positioning

Daena is a **personal AI operating system** plus a **Palantir-style
managed AI/security operations platform**. The founder is the only
user. There is no SaaS multi-tenant constraint to satisfy in the
critical path. Every governance, audit, and cost-control feature still
runs — but the audience is "founder + Daena", not "tenant N of M".

This means the design priorities shift:

| Concern              | SaaS-first (paused)            | Local-first (active)                  |
|----------------------|--------------------------------|---------------------------------------|
| Tenancy              | Strict isolation per tenant    | Single founder tenant; no cross-talk  |
| Auth                 | JWT + OAuth + RBAC             | Local-only; founder bypass acceptable |
| Latency target       | < 500 ms p95 from Cloud Run    | < 100 ms p95 on localhost             |
| Cost                 | Cloud SQL + Cloud Run + egress | Electricity                           |
| Backup               | Cloud SQL PITR                 | SQLite snapshot + Daena-Mind git      |
| Failure recovery     | Multi-region                   | Restart `start-daena.bat`             |
| LLM defaults         | Cloud APIs                     | llama-server + cloud APIs override    |
| Connections          | Per-tenant OAuth callbacks     | Founder-owned OAuth tokens            |
| Asset Shield         | Tenant + asset                 | Founder + asset                       |

Governance — Shield (PromptInjectionScanner + BehaviorGuard +
tenant isolation), Security (SecurityGate + ToolCallClassifier +
LoopDetector), Asset Shield (vault + egress filter + consent tokens) —
remains **always on**. Local-first does not mean ungoverned. It means
the audience is a single trusted operator, so initiator-aware tier
collapse leans toward auto-consent for operator-initiated actions and
full T0-T4 ladder for background/heartbeat/delegated.

## 2. Stack (what runs on the founder's machine)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Windows host (founder's PC, RTX 4060, 32 GB+ RAM)                  │
│                                                                     │
│  llama-server.exe (Windows binary)        Cron / heartbeat daemon  │
│   127.0.0.1:8080  GGUFs in MODELS_ROOT     APScheduler in backend  │
│       ▲                                                             │
│       │ /v1/* (OpenAI-compatible)                                   │
│       │                                                             │
│  ┌────┴───────────────────────────────────────────────┐             │
│  │ WSL2 (kali-linux) -- preferred backend host         │             │
│  │                                                     │             │
│  │  backend/run.py  (FastAPI + uvicorn)               │             │
│  │   127.0.0.1:8000  (auto-port via .daena-port)      │             │
│  │   .venv/ -- project-local Python 3.12              │             │
│  │                                                     │             │
│  │   ├─ SQLite + aiosqlite (daena.db, WAL mode)       │             │
│  │   ├─ Vault (DAENA_KEK envelope; vault.py)          │             │
│  │   ├─ NBMF memory T0-T4                             │             │
│  │   ├─ Connections V2 (op-lock + truth dims)         │             │
│  │   ├─ MCP Registry (hydrate_from_db on boot)        │             │
│  │   ├─ Runtime Adapter (claude-code, codex, llama)   │             │
│  │   └─ Audit chain (tamper-evident, append-only)     │             │
│  └────┬───────────────────────────────────────────────┘             │
│       │ Vite dev proxy (.daena-port)                                │
│       │                                                             │
│  Vite dev server (Windows or WSL)                                   │
│   127.0.0.1:5173  React + TS + Tailwind + Zustand                   │
│                                                                     │
│  Daena-Mind vault   D:\Ideas\Daena-Mind\                            │
│   T0/ T1/ T2/ T3/ T4/  -- Obsidian-compatible markdown              │
│                                                                     │
│  MODELS_ROOT        D:\Ideas\MODELS_ROOT\                           │
│   gguf/ hf/ ltx/ wan2gp/ heygem/ xtts/ whisper/ entities/           │
│                                                                     │
│  Optional: Redis (caching), Postgres+pgvector (if installed),       │
│            cloud LLM APIs (Anthropic/OpenAI/Groq/Gemini),           │
│            Codex CLI, Gemini CLI, Grok CLI                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Versions

- Python 3.12, FastAPI async, SQLAlchemy 2.0 async, Pydantic v2
- React 18 + TypeScript + Vite + Tailwind + Zustand + Framer Motion
- aiosqlite (dev), asyncpg (when local Postgres added)
- llama.cpp `llama-server.exe` (CUDA build) on `127.0.0.1:8080`

## 3. Component status

Components below are currently wired and operating in local mode.
Anything marked "verify-on-launch" should be exercised the first time
the local readiness script is run.

| Component                       | Status        | Local entry point |
|---------------------------------|---------------|--------------------|
| Backend (FastAPI)               | ✓ live        | `python backend/run.py` |
| Frontend (Vite dev)             | ✓ live        | `cd frontend && npm run dev` |
| llama-server (local LLM)        | verify-on-launch | `backend/start-llama-server.ps1` |
| Vault (envelope encryption)     | ✓ live        | `app.state.daena_kek` (loaded in lifespan) |
| Connections V2 truth UI         | ✓ live (tab) | `/connections` → V2 tab |
| Main Brain V2 callable gate     | ✓ live        | `/connections` → Main Brain |
| MCP server discovery            | verify-on-launch | `/connections` → MCP Servers tab |
| Local provider probes           | ✓ live (Phase 7) | install via lifespan auto-seed |
| Runtime Adapter (Claude/Codex)  | ✓ live        | `/connections` → Runtimes |
| NBMF memory T0-T4               | ✓ live        | backed by `memory_entries` table |
| Heartbeat daemon                | ✓ live        | configured via `/heartbeat` |
| Audit chain (hash-linked)       | ✓ live        | `audit_events` table |
| Asset Shield                    | ✓ live        | initiator-aware (founder = auto-consent on operator-initiated) |
| Skill Refinery (Phase 1+2)      | ✓ live        | `/skills` |
| Voice (TTS/STT)                 | ✓ live        | navbar toggle |
| Connections V2 reconciliation   | ✓ live        | `python backend/scripts/reconcile_connection_v2.py` |

## 4. The local launch path

Two equivalent options:

### Option A — One-button `start-daena.bat` (Windows)

```powershell
cd D:\Ideas\Daena
.\start-daena.bat
```

This script:
1. Checks WSL2 kali-linux is available (falls back to Windows backend)
2. Starts `llama-server.exe` with default GGUF if not already running
3. Starts backend (`python backend/run.py`) inside WSL2
4. Starts frontend (`cd frontend && npm run dev`) on Windows
5. Opens `http://localhost:5173`

### Option B — Manual (3 terminals)

```bash
# Terminal 1: llama-server (Windows host, optional but recommended)
D:\Ideas\llama.cpp\llama-server.exe \
  -m D:\Ideas\MODELS_ROOT\gguf\qwen3-8b\Qwen3-8B-Q4_K_M.gguf \
  -c 16384 -ngl 999 --host 127.0.0.1 --port 8080 --jinja --parallel 1

# Terminal 2: backend (WSL2 kali-linux preferred)
cd /mnt/d/Ideas/Daena/backend
.venv/bin/python run.py
# → reports actual port to backend/.daena-port

# Terminal 3: frontend (Windows or WSL)
cd D:\Ideas\Daena\frontend
npm run dev
# → http://localhost:5173 (proxies API to .daena-port)
```

### Health checks (after launch)

```bash
# Backend
curl -fsS http://127.0.0.1:8000/api/v1/health | jq .

# Frontend
curl -fsS http://127.0.0.1:5173 -o /dev/null -w '%{http_code}\n'

# llama-server (if started)
curl -fsS http://127.0.0.1:8080/v1/models | jq '.data[].id'

# Or run the bundled local readiness script
pwsh D:\Ideas\Daena\scripts\local_readiness_check.ps1
```

## 5. Memory + RAG path (NBMF + Daena-Mind + Obsidian)

```
T0 Ephemeral  — 1 hr  — backend/memory_entries (SQLite)
T1 Working    — 7 d   — backend/memory_entries (SQLite)
T2 Project    — 1 yr  — backend/memory_entries + D:\Ideas\Daena-Mind\T2\
T3 Institutional — perm — D:\Ideas\Daena-Mind\T3\ (founder approval gate)
T4 Founder-Private — perm — D:\Ideas\Daena-Mind\T4\ (founder only)
```

`Daena-Mind/` is an **Obsidian-compatible markdown vault**. Every
T2/T3/T4 entry is a `.md` file that renders directly inside Obsidian
with backlinks, tags, and embedded media. The folder structure is
flat-by-tier so Obsidian's graph view shows tier separation visually.

### RAG retrieval today

Backend uses semantic search over `memory_entries` rows. Embeddings
are computed via the local `nomic-embed-text:latest` (stored in
`hf/`) when the model is available, falling back to keyword search
otherwise. There is no pgvector dependency in the SQLite path.

### RAG retrieval after local Postgres + pgvector (optional upgrade)

When the founder installs local Postgres 16 + pgvector, switch
`DATABASE_URL` to `postgresql+asyncpg://...` and Daena automatically
uses the same SQL surface (SQLAlchemy 2.0 portable schema). The
hand-rolled `ALTER TABLE` block in `backend/app/main.py` is dev-only
and a no-op when `app_env=production` — for Postgres-local we
recommend running `alembic upgrade head` once at install time and
letting Alembic own the schema thereafter.

## 6. Local backup strategy

Three layers, all founder-managed:

1. **SQLite (live data)** — WAL mode is on by default. To take a
   consistent snapshot at any time:
   ```powershell
   sqlite3 D:\Ideas\Daena\backend\daena.db ".backup D:\Backups\Daena\daena-$(Get-Date -Format yyyyMMdd-HHmm).db"
   ```
   Recommended cadence: nightly via Task Scheduler. Restore: stop
   backend → copy snapshot → start backend.

2. **Daena-Mind vault (long-term knowledge)** — track in a private
   git repo:
   ```bash
   cd D:\Ideas\Daena-Mind
   git init && git add -A && git commit -m "snapshot $(date +%F)"
   # Push to founder-private remote (e.g., GitHub private repo,
   # local NAS, or both via multi-remote config)
   ```
   Recommended cadence: nightly via cron / Task Scheduler. Vault
   files are markdown; diff is human-readable.

3. **Vault secrets (envelope-encrypted)** — `vault.py` writes
   ciphertext + IV to `vault_records`. The DAENA_KEK is the only
   thing that decrypts them. Back up DAENA_KEK separately:
   ```powershell
   # KEK lives in environment; export the env file (gitignored)
   # to encrypted USB or password manager attachment.
   ```
   Never commit the KEK. Never email it. The vault snapshot itself
   is safe to back up alongside the SQLite snapshot — without the
   KEK it is opaque ciphertext.

## 7. What does NOT depend on Cloud Run

The local launch path has zero hard dependency on any GCP resource:

- ✓ Backend boots without any GCP credential
- ✓ Frontend boots without any GCP credential
- ✓ llama-server is local CUDA, no cloud
- ✓ Vault uses local DAENA_KEK from `.env`
- ✓ Audit chain writes to local SQLite
- ✓ NBMF tiers write to local SQLite + Daena-Mind folder
- ✓ MCP servers connect to local-only or operator-allowed external
- ✓ Heartbeat / autopilot / cron scheduler all run in-process

If `DAENA_KEK` is unset, the app's `vault_boot.py` uses a
deterministic dev KEK with a warning (per ADR-002 D-003). Production
and `--strict` modes refuse to boot — but local dev works without
explicit KEK provisioning.

The only place Daena reaches **out** is:

- Cloud LLM APIs (Anthropic/OpenAI/Groq/Gemini) when the founder has
  configured a key and the router selects that model
- MCP servers the founder has authorized in `/connections`
- Web scrapers (ContentOps; opt-in per pipeline run)
- OAuth callbacks for Google / GitHub / Slack / etc. when the
  founder triggers them via `/connections`

All outbound calls are subject to Asset Shield egress filtering.

## 8. Hardware + capacity targets

| Resource          | Founder workstation       | Budget per request          |
|-------------------|---------------------------|------------------------------|
| GPU               | RTX 4060 Laptop, 8 GB     | 4-8 GB for llama Q4 quants  |
| RAM               | 32 GB+                    | 8-12 GB headroom for backend |
| Disk              | NVMe; >100 GB free       | SQLite + Daena-Mind + GGUFs |
| Network           | Home broadband            | Cloud LLM only when needed  |
| Concurrent users  | 1 (founder)               | Multi-tenant code paths still active for safety, just unused |

## 9. When to consider cloud again (resume criteria)

Cloud Run resumes only if **one** of these is true:

1. Founder runs a live demo for an investor / client and prefers
   `daena.mas-ai.co` over a localhost screen-share.
2. Founder takes on a managed-client engagement where the customer
   wants a hosted instance.
3. Founder needs Daena reachable from outside the home network for
   24/7 unattended operation (e.g., heartbeat tasks that must keep
   running while the workstation is off).

Until then, every cloud-deploy-related TODO is parked in
`CLOUD_DEPLOYMENT_PAUSED_DECISION.md`.

## 10. What still goes in `D:\Claude-Coworker\inbox.md`

Local-first does not mean fewer tickets. Tickets that matter most now:

- **Connections V2 polish**: edge cases on probe → state-machine
  transitions, op-lock cleanup, label distinction (stale vs failed)
- **MCP discovery**: founder's installed Claude Desktop / VS Code
  MCP configs should hydrate Daena's MCP registry on launch
- **Provider probes**: real round-trip semantics against the 9
  configured providers; never leak keys
- **Heartbeat reliability**: cron scheduler must persist runs and
  not silently fail
- **Audit chain integrity**: hash-linked verification on every boot
- **Backup automation**: schedule nightly SQLite + Daena-Mind
  snapshots
- **Skill Refinery Phase 3**: governance integration for skill trust
  tiers, news monitor for stale skills

These are the "make local Daena reliable, fast, and fully wired"
deliverables.

---

**Last updated:** 2026-05-01
**Decision authority:** Founder
**Counterpart doc:** `CLOUD_DEPLOYMENT_PAUSED_DECISION.md`
