---
title: "Benchmark Methodology"
date: 2025-01-15
lastmod: 2025-01-15
inventor: "Masoud Masoori"
assignee: "Mas-AI Technology Inc."
status: "Draft – For Provisional Filing"
---

# Benchmark Methodology

## Overview

This document describes the methodology used to benchmark the Neural-Backed Memory Fabric (NBMF) system performance, including compression ratios, accuracy metrics, and latency measurements.

## Datasets

### Test Dataset Composition

The benchmark suite uses a diverse set of test documents:

1. **Text Documents**: 20 documents ranging from 100 to 10,000 tokens
   - Conversational transcripts
   - Technical documentation
   - General knowledge articles
   - Mixed content types

2. **Synthetic Loads**: Generated test cases for stress testing
   - Various document sizes
   - Different content types
   - Simulated real-world usage patterns

### Dataset Characteristics

- **Total Documents**: 20 primary test documents
- **Total Tokens (OCR baseline)**: 10,112.25 tokens (mean: 2,528.06 tokens per document)
- **Content Types**: Text, structured data, unstructured content
- **Size Range**: 100 tokens to 10,000 tokens per document

## Measurement Steps

### 1. Encoding Phase

For each document:

1. **Input Preparation**: Load document content
2. **Encoding**: Apply NBMF encoding in both modes:
   - Lossless mode: Deterministic encoding with compression
   - Semantic mode: Neural encoder → latent representation → compression
3. **Size Measurement**: Record original size and compressed size
4. **Latency Measurement**: Measure encoding time (p50, p95, p99, mean, min, max)

### 2. Decoding Phase

For each encoded document:

1. **Decoding**: Decode NBMF bytecode back to original format
2. **Latency Measurement**: Measure decoding time (p50, p95, p99, mean, min, max)
3. **Accuracy Verification**: Compare decoded content with original

### 3. Accuracy Assessment

**Lossless Mode**:
- Exact match rate: Binary comparison of original vs decoded
- Hash match rate: SHA-256 hash comparison
- Target: 100% accuracy

**Semantic Mode**:
- Semantic similarity: Cosine similarity of embeddings
- Meaning preservation: LLM-based semantic comparison
- Target: 95%+ similarity

### 4. Compression Analysis

- **Compression Ratio**: `original_size / compressed_size`
- **Storage Savings**: `(1 - compressed_size / original_size) × 100%`
- **Token Reduction**: Comparison of token counts before and after encoding

## Metrics Collected

### Compression Metrics
- Mean, median, min, max compression ratios
- Standard deviation
- p95 and p99 percentiles
- Storage savings percentage

### Accuracy Metrics
- Exact match rate (lossless)
- Hash match rate (lossless)
- Mean semantic similarity (semantic)
- Min, p95 semantic similarity (semantic)
- Total tests performed

### Latency Metrics
- Encoding latency: mean, p50, p95, p99, min, max (milliseconds)
- Decoding latency: mean, p50, p95, p99, min, max (milliseconds)
- Measured in milliseconds with microsecond precision

### Token Count Metrics
- Original token count (OCR baseline)
- NBMF lossless token count
- NBMF semantic token count
- Token reduction percentage

## Test Execution

### Environment
- See `environment.md` for detailed hardware and software specifications
- Tests executed on 2025-01-15
- Single-threaded execution for consistency
- Warm-up runs excluded from measurements

### Reproducibility

To reproduce these benchmarks:

1. Use the same test dataset (20 documents)
2. Execute on equivalent hardware (see `environment.md`)
3. Use identical NBMF encoder/decoder versions
4. Run in single-threaded mode
5. Exclude warm-up runs from measurements

## Limitations

1. **Dataset Size**: Limited to 20 documents for initial validation
2. **Hardware Dependency**: Results may vary on different hardware configurations
3. **Content Type Bias**: Results may vary for different content types
4. **Temporal Variance**: Results measured on 2025-01-15; performance may improve with future optimizations

## Notes

- All measurements are illustrative and represent performance as measured on 2025-01-15
- Results may vary based on hardware, software versions, and content characteristics
- Compression ratios and latencies are dependent on content type and size
- Accuracy metrics are based on the test dataset and may vary for different content

---

**End of Methodology**










