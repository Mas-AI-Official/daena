# Quick Reference Guide

**Date**: 2025-01-XX  
**Purpose**: Quick reference for common operations

---

## 🚀 Quick Start

### Run Tests
```bash
# All tests
python -m pytest --noconftest \
  tests/test_memory_service_phase2.py \
  tests/test_memory_service_phase3.py \
  tests/test_phase3_hybrid.py \
  tests/test_phase4_cutover.py \
  tests/test_new_features.py \
  tests/test_quorum_neighbors.py \
  -v

# Expected: 35/35 passing
```

### Operational Checks
```bash
# Comprehensive rehearsal
python Tools/operational_rehearsal.py

# DR drill
python Tools/daena_drill.py

# Cutover verification
python Tools/daena_cutover.py --verify-only
```

### Benchmarks
```bash
# Quick test (10 samples)
python bench/benchmark_nbmf.py --samples 10

# Full benchmark (200 samples)
python bench/benchmark_nbmf.py --samples 200 --output bench/results.json
```

---

## 📊 Key Metrics

### Check System Health
```bash
# Memory metrics
curl http://localhost:8000/monitoring/memory | jq '{
  cas_hit_rate: .llm_cas_hit_rate,
  write_latency: .nbmf_write_p95_ms,
  read_latency: .nbmf_read_p95_ms,
  divergence_rate: .divergence_rate,
  cost_savings: .estimated_cost_savings_usd
}'

# CAS efficiency
curl http://localhost:8000/monitoring/memory/cas

# Memory snapshot
curl http://localhost:8000/monitoring/memory/snapshot
```

---

## 🔧 Common Operations

### Write to NBMF
```python
from memory_service.router import MemoryRouter

router = MemoryRouter()
result = router.write_nbmf_only("item_1", "test", {"data": "value"})
```

### Read from NBMF
```python
data = router.read_nbmf_only("item_1", "test")
```

### Store Abstract + Lossless Pointer
```python
from memory_service.abstract_store import AbstractStore, StorageMode

store = AbstractStore()
result = store.store_abstract(
    item_id="doc_1",
    class_name="document",
    payload={"text": "content"},
    lossless_pointer="file:///path/to/source.pdf",
    confidence=0.8,
    mode=StorageMode.ABSTRACT_POINTER
)
```

### Start Quorum (4/6 Neighbors)
```python
from backend.utils.quorum import quorum_manager, QuorumType

quorum_id = quorum_manager.start_quorum(
    quorum_id="decision_1",
    quorum_type=QuorumType.LOCAL,
    cell_id="D1"  # Automatically gets neighbors
)

# Cast votes from neighbors (need 4/6)
for neighbor in ["D2", "D3", "D4", "D5"]:
    result = quorum_manager.cast_vote(quorum_id, neighbor, True)
```

### Apply Aging
```python
from memory_service.aging import apply_aging, promote_hot_records

# Apply aging policies
stats = apply_aging(router)

# Promote hot records
promo_stats = promote_hot_records(router, min_access_count=10)
```

---

## 📁 Key Files

### Code
- `memory_service/router.py` - Main memory router
- `memory_service/aging.py` - Aging and promotion
- `memory_service/abstract_store.py` - OCR hybrid pattern
- `backend/utils/quorum.py` - Quorum management
- `backend/utils/backpressure.py` - Backpressure management

### Tools
- `Tools/operational_rehearsal.py` - Operational checks
- `Tools/daena_drill.py` - DR drill
- `Tools/daena_cutover.py` - Cutover management
- `bench/benchmark_nbmf.py` - Benchmark tool

### Tests
- `tests/test_memory_service_phase2.py` - Core NBMF tests
- `tests/test_new_features.py` - New feature tests
- `tests/test_quorum_neighbors.py` - Quorum tests

### Documentation
- `docs/FINAL_STATUS_AND_NEXT_STEPS.md` - Main status
- `docs/MASTER_SUMMARY_AND_ROADMAP.md` - Roadmap
- `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` - Deployment guide

---

## 🎯 Feature Status

| Feature | Status | Location |
|---------|--------|----------|
| NBMF 3-tier | ✅ | `memory_service/router.py` |
| Trust pipeline | ✅ | `memory_service/trust_manager.py` |
| Access-based aging | ✅ | `memory_service/aging.py` |
| OCR hybrid | ✅ | `memory_service/abstract_store.py` |
| Multimodal | ✅ | `memory_service/router.py` |
| Phase 7 (hex-mesh) | ✅ | `backend/utils/message_bus_v2.py` |
| 4/6 neighbor quorum | ✅ | `backend/utils/quorum.py` |

---

## ⚡ Quick Tips

1. **Check metrics first** - Always check `/monitoring/memory` before troubleshooting
2. **Run operational rehearsal** - Before any deployment, run `operational_rehearsal.py`
3. **Monitor CAS hit rate** - Should be >60% for efficiency
4. **Check latency** - L1 <25ms, L2 <120ms targets
5. **Review governance artifacts** - Generate weekly with `generate_governance_artifacts.py`

---

**Status**: ✅ System Ready  
**Tests**: 35/35 passing  
**Phase 7**: 100% complete

