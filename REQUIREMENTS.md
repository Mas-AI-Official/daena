# Daena -- Requirements for Running and Development

## Prerequisites (install these first)

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | https://python.org (check "Add to PATH") |
| Node.js | 18+ (tested 24.x) | https://nodejs.org |
| npm | 9+ (comes with Node) | -- |
| Git | any | https://git-scm.com |
| Ollama | latest (optional) | https://ollama.ai |
| Docker Desktop | latest (optional, for production) | https://docker.com |

## Quick Setup

```bat
:: From D:\Ideas\Daena\
setup-daena.bat
```

This creates `venv_daena\`, installs backend deps, frontend deps, and Playwright chromium.

## Manual Setup

### 1. Python Virtual Environment

```bat
python -m venv venv_daena
venv_daena\Scripts\activate
pip install -e backend[dev]
```

### 2. Playwright + Chromium (for BrowserAgent + demos)

```bat
pip install playwright
playwright install chromium
```

### 3. Frontend

```bat
cd frontend
npm install
```

### 4. Environment File

```bat
copy .env.example backend\.env
:: Edit backend\.env with your API keys
```

## Backend Python Dependencies (from pyproject.toml)

### Core (required)

| Package | Purpose |
|---------|---------|
| fastapi>=0.115.0 | Web framework (async) |
| uvicorn[standard]>=0.34.0 | ASGI server |
| python-multipart>=0.0.18 | File uploads |
| sqlalchemy[asyncio]>=2.0.36 | ORM (async) |
| asyncpg>=0.30.0 | PostgreSQL driver |
| aiosqlite>=0.20.0 | SQLite async driver (dev) |
| alembic>=1.14.0 | Database migrations |
| pgvector>=0.3.6 | Vector search |
| redis>=5.2.0 | Cache + queue backend |
| celery[redis]>=5.4.0 | Task queue |
| pyjwt>=2.10.0 | JWT auth tokens |
| bcrypt>=4.2.0 | Password hashing |
| python-jose[cryptography]>=3.3.0 | JOSE/JWT |
| pydantic[email]>=2.10.0 | Validation |
| pydantic-settings>=2.7.0 | Settings from env |
| httpx>=0.28.0 | Async HTTP client |
| aiohttp>=3.11.0 | Async HTTP (alt) |
| structlog>=24.4.0 | Structured logging |
| python-dotenv>=1.0.1 | .env file loading |
| orjson>=3.10.0 | Fast JSON |

### Agent Capabilities (required for EXE mode)

| Package | Purpose |
|---------|---------|
| browser-use>=0.12.0 | AI browser automation |
| crawl4ai>=0.8.0 | Web crawling |
| playwright>=1.40.0 | Browser control |

### Dev/Test (optional, for development)

| Package | Purpose |
|---------|---------|
| pytest>=8.3.0 | Test runner |
| pytest-asyncio>=0.24.0 | Async test support |
| pytest-cov>=6.0.0 | Coverage reporting |
| ruff>=0.8.0 | Linter + formatter |
| mypy>=1.13.0 | Type checker |

## Frontend Dependencies (from package.json)

### Core

| Package | Purpose |
|---------|---------|
| react 19 | UI framework |
| react-dom 19 | DOM rendering |
| react-router-dom | Client routing |
| axios | HTTP client |
| zustand | State management |
| framer-motion | Animations |
| tailwindcss 4 | CSS framework |
| lucide-react | Icons |

### Dev

| Package | Purpose |
|---------|---------|
| typescript ~5.8 | Type system |
| vite 6 | Build tool + HMR |
| @playwright/test | E2E testing |
| eslint | Linting |

## Browser Requirements (Playwright)

After installing playwright, install browser binaries:

```bat
playwright install chromium
```

This downloads Chromium for BrowserAgent, demo screenshots, and E2E tests.

## Ollama Models (optional, for local AI)

```bat
ollama pull llama3.1:8b          :: 4.7 GB - General chat
ollama pull qwen2.5-coder:14b    :: 9 GB - Coding
ollama pull deepseek-r1:14b      :: 9 GB - Reasoning
ollama pull nomic-embed-text     :: Embeddings
```

## Running Daena

### Option 1: One-click (recommended)

```bat
start-daena.bat
```

Starts Ollama + Backend + Frontend + opens browser.

### Option 2: Separate terminals

Terminal 1 (backend):
```bat
start-backend.bat
```

Terminal 2 (frontend):
```bat
start-frontend.bat
```

### Option 3: Manual

Terminal 1:
```bat
cd backend
..\venv_daena\Scripts\activate
python run.py
```

Terminal 2:
```bat
cd frontend
npm run dev
```

### Option 4: Docker (production)

```bat
scripts\deploy-local.bat
```

## Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend (Vite) | 5173 | http://localhost:5173 |
| Backend (FastAPI) | 8000 (auto-find) | http://localhost:8000 |
| Backend API docs | 8000 | http://localhost:8000/docs |
| Ollama | 11434 | http://localhost:11434 |
| Redis | 6379 | -- |
| PostgreSQL (prod) | 5432 | -- |

## Health Check

```bat
health-check.bat
```

Checks backend, frontend, and Ollama status.

## Stopping

```bat
stop-daena.bat
```

## Canonical Virtual Environment

The project uses `venv_daena\` at the project root (NOT `backend\.venv`).
All bat files reference this path. Do not create or use `backend\.venv` separately.

```
D:\Ideas\Daena\
  venv_daena\          <-- canonical Python venv (241+ packages)
  backend\             <-- FastAPI app
  frontend\            <-- React app
  start-daena.bat      <-- one-click start
  setup-daena.bat      <-- first-time setup
  health-check.bat     <-- status check
  stop-daena.bat       <-- shutdown
```
