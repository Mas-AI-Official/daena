# Benchmark Status

**Date**: 2025-01-XX  
**Tool**: `bench/benchmark_nbmf.py` ✅ Ready

---

## Current Results (Baseline Encoder)

**Note**: The current encoder (`memory_service/nbmf_encoder.py`) is a **baseline stub** that will be replaced with a production-grade neural encoder in later phases.

### Test Results (10 samples)

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| **Compression Ratio** | 1.14× | 2-5× | ❌ FAIL (expected - stub encoder) |
| **Accuracy** | 91.73% | 99.5%+ | ❌ FAIL (expected - stub encoder) |
| **Latency L2** | 18.46ms | <120ms | ✅ PASS |

---

## Why Results Fail

The current encoder implementation:
- **Lossless mode**: Uses zlib compression (basic, not neural)
- **Semantic mode**: Returns preview text (not full neural encoding)

This is **intentional** - the encoder is marked as a stub:
```python
# From memory_service/nbmf_encoder.py:
"""
Baseline NBMF encoder stub.

Corsur will extend/replace this with a production-grade neural encoder during
later phases. For now, it offers deterministic behaviour so bootstrap/tests can
exercise imports and simple round-trips.
"""
```

---

## Next Steps

### 1. Upgrade Encoder (Required for Production)

**Action**: Replace `memory_service/nbmf_encoder.py` with production neural encoder:
- Domain-trained neural networks
- Learned compression (2-5×)
- Semantic fidelity (99.5%+)

**Estimated Time**: 2-4 weeks (neural model training)

### 2. Re-run Benchmarks

After encoder upgrade:
```bash
python bench/benchmark_nbmf.py --samples 200 --output bench/production_results.json
```

**Expected Results** (after upgrade):
- ✅ Compression: 2-5×
- ✅ Accuracy: 99.5%+
- ✅ Latency: L1 <25ms, L2 <120ms

---

## Benchmark Tool Features ✅

The benchmark tool is **production-ready** and will validate claims once the encoder is upgraded:

1. ✅ **Compression measurement** - Lossless & semantic modes
2. ✅ **Accuracy measurement** - Exact match (lossless) & similarity (semantic)
3. ✅ **Latency measurement** - Write & read times for L1/L2/L3
4. ✅ **Diverse test data** - Text, structured, mixed/multimodal
5. ✅ **Statistical analysis** - Mean, median, p95, min, max
6. ✅ **Validation** - Automatic PASS/FAIL against claims
7. ✅ **JSON output** - Results saved for CI/CD integration

---

## Usage

```bash
# Quick test (10 samples)
python bench/benchmark_nbmf.py --samples 10

# Full benchmark (200 samples)
python bench/benchmark_nbmf.py --samples 200 --output bench/results.json

# CI/CD integration
python bench/benchmark_nbmf.py --samples 100 --output bench/ci_results.json
```

---

**Status**: ✅ Benchmark tool ready, encoder upgrade needed for production claims

