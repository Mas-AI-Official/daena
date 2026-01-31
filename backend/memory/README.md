# Daena Unified Memory System

This package (`backend.memory`) is the **new canonical implementation** of the Daena memory system, replacing the legacy `memory_service` and root-level `memory` folder.

## Architecture

| Tier | Component | Description | Latency |
|------|-----------|-------------|---------|
| **L1** | `l1_hot.py` | Vector Index / Hot Cache | < 25ms |
| **L2** | `l2_warm.py` | NBMF Primary Storage | < 120ms |
| **L3** | `l3_cold.py` | Deep Archive | < 500ms |
| **CAS** | `cas_engine.py` | Content-Addressable Storage (Deduplication) | - |

## Migration Status

- [x] **New Unified Structure**: Implemented in this folder.
- [ ] **Refactor Imports**: `memory_service` imports throughout the codebase need to be migrated to `backend.memory`.
- [ ] **Legacy Cleanout**: Delete `memory_service/` and `memory/` once migration is complete.

## Usage

```python
from backend.memory import memory

# Write
memory.write("project_alpha", "plans", {"status": "draft"})

# Read
data = memory.read("project_alpha", "plans")

# Search
results = memory.search("draft status")
```
