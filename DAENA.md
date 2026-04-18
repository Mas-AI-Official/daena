# DAENA.md -- Runtime-Agnostic Identity & Configuration
# This file defines Daena's identity for ANY AI development tool.
# CLAUDE.md extends this for Claude Code specifically.
# If using Cursor, Codex, Gemini, or any other tool: read THIS file.

## IDENTITY

Daena is a governed multi-agent LLM orchestration platform by MAS-AI Technologies Inc.
An AI operating system where 10 department-agents collaborate like a company,
governed by internal policies, expert councils, and auditable decision trails.

## SOUL (Runtime-Agnostic Personality)

Daena's personality lives at `backend/app/soul/` -- 6 files loaded by SoulEngine:
- foundation.md -- Who Daena is, core character, agency
- reasoning.md -- How Daena thinks, decision frameworks
- personality.md -- Voice, tone, communication style
- loyalty.md -- Relationship to founder, users, mission
- shield.md -- What Daena protects (IP, data, users)
- evolution.md -- How Daena grows, learns, improves

These are injected FIRST into every LLM system prompt, regardless of which model
or provider is used. They are the highest-priority context.

## SKILLS (Runtime-Agnostic Capabilities)

Two skill systems, both runtime-agnostic:
1. **Filesystem skills**: `skills/*/SKILL.md` -- actionable instructions (OpenClaw pattern)
2. **DB skills**: Skill Refinery -- evidence-backed patterns extracted from conversations

Skills are injected into the system prompt at Stage 6.5-6.6 of the chat pipeline.

## DEPARTMENTS (Runtime-Agnostic Organization)

10 departments, each with 6 sub-capabilities (MIND, EYES, HANDS, VOICE, SHIELD, MEMORY):
Engineering, Product, Marketing, Sales, Finance, Operations, Research,
Legal & Compliance, Skill Governance, Security Operations.

Stored in database. Auto-seeded on first startup.

## DCPs (Runtime-Agnostic Expert Perspectives)

55 Domain-Contextual Perspectives at `backend/app/config/dcps.json`.
Used by Council and Quintessence reasoning modes to inject expert viewpoints.

## GOVERNANCE MODES

- UNLEASHED: No governance. Shield only. Raw power.
- BALANCED: Light governance. Auto-approve most actions.
- GOVERNED: Full 10-stage pipeline. Enterprise mode.

## TECH STACK

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2
- Frontend: React 18, TypeScript, Vite, Tailwind, Zustand
- Database: SQLite (dev) / PostgreSQL (prod)
- LLM: Multi-provider (Ollama, Claude, OpenAI, Gemini, Groq, etc.)

## PORTS

- Backend: 8000 (auto-port, writes `.daena-port`)
- Frontend: 5173 (reads `.daena-port` for proxy target)
- ContentOps: 8100 (separate project, never 8000)
- Ollama: 11434

## STARTUP

```bash
# Option 1: Full startup (recommended)
start-daena.bat

# Option 2: Manual
cd backend && .venv\Scripts\python.exe run.py    # writes .daena-port
cd frontend && npm run dev                        # reads .daena-port
```

## KEY DIRECTORIES

| Path | Purpose |
|------|---------|
| backend/app/soul/ | Daena's personality (runtime-agnostic) |
| backend/app/config/dcps.json | Expert perspectives |
| skills/ | Filesystem skills (SKILL.md) |
| backend/app/services/ | Core business logic |
| frontend/src/ | React SPA |

## IP NAMING (LOCKED)

- PhiLattice = external brand. Codebase uses "sunflower-honeycomb"
- NBMF = Neural-Backed Memory Fabric. Codebase uses "nbmf"
- Never rename internal codenames to external brand names
