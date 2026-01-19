# NBMF Encoder Training

**Status**: Planning Phase  
**Purpose**: Upgrade stub encoder to production neural encoder

---

## Quick Start

### Current Status
- **Stub Encoder**: `memory_service/nbmf_encoder.py`
- **Benchmark Results**: Compression 1.14× (needs 2-5×), Accuracy 91.73% (needs 99.5%+)
- **Target**: Production neural encoder

### Next Steps
1. Review `docs/ENCODER_UPGRADE_PLAN.md`
2. Review `training/encoder_upgrade_roadmap.md`
3. Approve architecture
4. Start data collection

---

## Documentation

- `docs/ENCODER_UPGRADE_PLAN.md` - Complete upgrade plan
- `training/encoder_upgrade_roadmap.md` - Step-by-step roadmap
- `bench/BENCHMARK_STATUS.md` - Current benchmark status

---

## Requirements

### Compression
- Target: 2-5× vs raw
- Current: 1.14× (stub)

### Accuracy
- Target: 99.5%+ reconstruction
- Current: 91.73% (stub)

### Latency
- Target: <120ms L2 (maintain)
- Current: 18.46ms L2 ✅

---

## Timeline

**Estimated**: 2-4 weeks

- Week 1: Design & data collection
- Week 2: Training
- Week 3: Integration
- Week 4: Validation

---

**Status**: ⏳ Planning  
**Next**: Architecture review

