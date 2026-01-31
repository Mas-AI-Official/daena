# Daena: Autonomous Company Operating System

**Status: Pre-Alpha / Active Development**  
**Docs:** [Honest Audit & Roadmap](docs/2026-01-31/DAENA_HONEST_AUDIT_AND_ROADMAP.md)

Daena is a **VP-level AI operating system** designed to run an entire autonomous company. Unlike simple agent frameworks, Daena integrates deep memory, council-based governance, and verified execution into a unified platform.

## 🚀 Key Features

- **NBMF Memory System**: 3-tier memory (Hot/Warm/Cold) with CAS deduplication, saving 60%+ on LLM context costs.
- **Council Governance**: 5-expert panel (Finance, Tech, Legal, etc.) that debates decisions before execution.
- **VP Hierarchy**: Founder → Daena (VP) → Department Heads → Sub-Agents.
- **Local-First**: Runs on private infrastructure with optional cloud scale.
- **DeFi Native**: Integrated security scanning and treasury management (Slither/Mythril pipeline).

## 🛠️ Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Mas-AI-Official/Daena-old-upgrade-20251213.git
   cd Daena-old-upgrade-20251213
   ```

2. **Setup Environment**
   ```bash
   # Windows
   ./ENV_DOCTOR.bat
   ```

3. **Run the Killer Demo** (3-minute end-to-end showcase)
   ```bash
   python scripts/killer_demo.py
   ```
   This demonstrates:
   - Autonomous task decomposition
   - Real-time agent activity
   - DeFi security scanning
   - Council debate and decision making

## 🏗️ Architecture

- **Core**: `backend/` - FastAPI, DaenaAgent, Orchestration
- **Memory**: `backend/memory/` - Unified L1/L2/L3 storage
- **Interfaces**:
  - `backend/connectors/mcp_server.py`: Model Context Protocol (MCP) server
  - `frontend/`: Dashboard and Command Center

## 🔒 Security

- **Secrets**: Managed via environment variables only.
- **Audit**: `scripts/secrets_audit.py` runs on pre-commit.
- **Access**: `SECURITY.md` defines strict access controls.

## 🗺️ Roadmap

We are currently in **Phase 2: The Demo & Foundation**.
See [DAENA_HONEST_AUDIT_AND_ROADMAP.md](docs/2026-01-31/DAENA_HONEST_AUDIT_AND_ROADMAP.md) for the detailed plan.

---

*Note: This repository is under active consolidation. Legacy folders are being migrated to the unified `backend/` structure.*
