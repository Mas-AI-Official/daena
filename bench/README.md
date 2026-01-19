# NBMF Benchmark Suite

Benchmark tool to validate NBMF innovation claims:
- **Compression**: 2-5× vs raw storage
- **Accuracy**: 99.5%+ reconstruction accuracy
- **Latency**: L1 <25ms p95, L2 <120ms p95

---

## Quick Start

```bash
# Run with default settings (100 samples)
python bench/benchmark_nbmf.py

# Run with custom sample count
python bench/benchmark_nbmf.py --samples 200

# Save results to file
python bench/benchmark_nbmf.py --output bench/results.json

# Verbose output
python bench/benchmark_nbmf.py --verbose
```

---

## What It Tests

### 1. Compression Ratio
- **Lossless mode**: Exact reconstruction with compression
- **Semantic mode**: Meaning-preserving compression
- **Metrics**: Mean, median, min, max, p95 compression ratios

### 2. Accuracy
- **Lossless mode**: 100% exact match (bit-perfect)
- **Semantic mode**: Similarity score (character overlap, meaning preservation)
- **Metrics**: Mean accuracy, min accuracy, p95 accuracy

### 3. Latency
- **Write latency**: Time to encode and store
- **Read latency**: Time to retrieve and decode
- **Tiers**: L1 (hot), L2 (warm), L3 (cold)
- **Metrics**: Mean, p95, p99, min, max

---

## Test Data

The benchmark generates three types of test data:

1. **Text samples** (33%): Conversation text, documents
2. **Structured data** (33%): JSON objects with nested structures
3. **Mixed/multimodal** (33%): Combined text + metadata + binary references

---

## Output Format

Results are saved as JSON with the following structure:

```json
{
  "compression": {
    "lossless": {
      "mean": 3.2,
      "median": 3.1,
      "min": 2.1,
      "max": 4.8,
      "p95": 4.5
    },
    "semantic": {
      "mean": 4.1,
      "median": 4.0,
      "min": 2.5,
      "max": 5.2,
      "p95": 5.0
    }
  },
  "accuracy": {
    "lossless": {
      "accuracy": 100.0,
      "exact_matches": 100,
      "total": 100
    },
    "semantic": {
      "mean_accuracy": 99.7,
      "min_accuracy": 98.5,
      "p95_accuracy": 99.9
    }
  },
  "latency": {
    "write": {
      "l2": {
        "mean_ms": 45.2,
        "p95_ms": 78.5,
        "p99_ms": 95.2
      }
    },
    "read": {
      "l1": {
        "mean_ms": 12.3,
        "p95_ms": 22.1
      },
      "l2": {
        "mean_ms": 65.4,
        "p95_ms": 98.7
      }
    }
  },
  "summary": {
    "compression_result": {
      "mean_ratio": 4.1,
      "meets_claim": true,
      "status": "✅ PASS"
    },
    "accuracy_result": {
      "mean_accuracy": 99.7,
      "meets_claim": true,
      "status": "✅ PASS"
    },
    "latency_results": {
      "l1": {
        "p95_ms": 22.1,
        "target_ms": 25.0,
        "meets_claim": true,
        "status": "✅ PASS"
      },
      "l2": {
        "p95_ms": 98.7,
        "target_ms": 120.0,
        "meets_claim": true,
        "status": "✅ PASS"
      }
    }
  }
}
```

---

## Validation Criteria

### ✅ Compression: PASS
- Mean ratio between 2.0× and 5.0× (semantic mode)

### ✅ Accuracy: PASS
- Lossless: 100% exact matches
- Semantic: Mean accuracy ≥ 99.5%

### ✅ Latency: PASS
- L1 read p95 < 25ms
- L2 read p95 < 120ms

---

## Usage in CI/CD

```bash
# Run benchmark in CI
python bench/benchmark_nbmf.py --samples 100 --output bench/ci_results.json

# Check if all claims pass
python -c "
import json
with open('bench/ci_results.json') as f:
    r = json.load(f)
    summary = r['summary']
    all_pass = (
        summary.get('compression_result', {}).get('meets_claim', False) and
        summary.get('accuracy_result', {}).get('meets_claim', False) and
        all(l.get('meets_claim', False) for l in summary.get('latency_results', {}).values())
    )
    exit(0 if all_pass else 1)
"
```

---

## Future Enhancements

- [ ] GPU time tracking (if GPU available)
- [ ] Real-world dataset testing (conversations, documents, images)
- [ ] Comparison with baseline (raw JSON, gzip, other compression)
- [ ] Throughput testing (writes/sec, reads/sec)
- [ ] Memory footprint measurement
- [ ] Cost analysis (storage + compute)

---

**Status**: ✅ Benchmark tool ready  
**Next**: Run benchmarks and validate claims before patent filing

