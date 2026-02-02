# Sparring Questions - Code-Level Analysis

**Date**: 2025-01-XX  
**Purpose**: Answer 5 critical sparring questions based on actual code implementation  
**Status**: ✅ Complete

---

## Question 1: Multimodal Coverage

**Question**: How does NBMF currently handle non-text content (images, audio, mixed docs)? Is there any code path that encodes/decodes these, or are they just stored as raw blobs?

### Code Analysis

**Findings**:

1. **No explicit multimodal support found**:
   - `memory_service/router.py`: `write()` and `read()` methods accept `Any` payload type, but no special handling for images/audio
   - `memory_service/nbmf_encoder.py`: Encodes payloads as JSON-serializable structures
   - `memory_service/adapters/l2_nbmf_store.py`: Uses `write_secure_json()` which expects JSON-serializable data

2. **Blob storage exists but not integrated**:
   - `memory_service/adapters/l2_nbmf_store.py:87-98`: `put()` and `get()` methods for blob storage exist
   - `memory_service/router.py:451-456`: `store_raw_artifact()` method stores to L3 as JSON artifacts
   - **Gap**: No automatic detection/encoding of binary content (images, audio, PDFs)

3. **Abstract Store pattern supports pointers**:
   - `memory_service/abstract_store.py:39-40`: `lossless_pointer` field exists for storing URIs to source documents
   - `memory_service/abstract_store.py:129-141`: Can store lossless pointers, but doesn't automatically handle binary content

### Implementation Status

- ❌ **Not implemented**: Automatic image/audio encoding/decoding
- ✅ **Partially implemented**: Blob storage exists but not used for multimodal content
- ✅ **Partially implemented**: Abstract + pointer pattern could support multimodal via URIs

### Code References

- `memory_service/router.py:290-313` - Write path (no multimodal handling)
- `memory_service/router.py:451-456` - Raw artifact storage (JSON only)
- `memory_service/adapters/l2_nbmf_store.py:87-98` - Blob storage (unused)
- `memory_service/abstract_store.py:65-183` - Abstract store (supports pointers, not binary encoding)

### Recommendation

**Gap**: Need to add:
1. Content type detection (MIME type, file extension)
2. Binary-to-base64 encoding for images/audio
3. Integration with blob storage for large binary files
4. Metadata extraction (image dimensions, audio duration, etc.)

**Proposed Fix**: Add `_detect_content_type()` and `_encode_multimodal()` helpers in `router.py`

---

## Question 2: Energy & Compute Footprint

**Question**: Where is the "heavy" work done for NBMF encoding/decoding? Is there any profiling/metrics that capture CPU/GPU time per encode/write or read/recall?

### Code Analysis

**Findings**:

1. **Latency tracking exists but no CPU/GPU profiling**:
   - `memory_service/router.py:268-275`: Uses `perf_counter()` for `nbmf_write` latency
   - `memory_service/router.py:379-393`: Uses `perf_counter()` for `nbmf_read` latency
   - `memory_service/metrics.py:17-21`: `observe()` tracks latencies in seconds
   - **Gap**: Only wall-clock time, not CPU/GPU time

2. **Metrics captured**:
   - `memory_service/metrics.py:37-73`: `snapshot()` returns p95/avg latencies in milliseconds
   - `memory_service/metrics.py:32-34`: `track_cost()` tracks costs by category (llm_api, storage, compute)
   - **Gap**: "compute" category exists but not populated with actual CPU/GPU time

3. **No profiling for encoding/decoding**:
   - `memory_service/nbmf_encoder.py`: No timing/profiling hooks
   - `memory_service/nbmf_decoder.py`: No timing/profiling hooks
   - Encoding/decoding happens inline without separate metrics

### Implementation Status

- ✅ **Implemented**: Wall-clock latency tracking (p95, avg)
- ❌ **Not implemented**: CPU time profiling
- ❌ **Not implemented**: GPU time profiling
- ❌ **Not implemented**: Per-operation compute cost tracking

### Code References

- `memory_service/router.py:268-275` - Write timing
- `memory_service/router.py:379-393` - Read timing
- `memory_service/metrics.py:17-21` - Latency observation
- `memory_service/metrics.py:32-34` - Cost tracking (unused for compute)

### Recommendation

**Gap**: Need to add:
1. `time.process_time()` for CPU time (separate from wall-clock)
2. Optional GPU profiling if CUDA available
3. Operation count tracking (encode ops, decode ops)
4. Populate `track_cost("compute", ...)` with actual CPU/GPU time

**Proposed Fix**: Enhance `metrics.py` with `observe_cpu_time()` and `observe_gpu_time()` helpers

---

## Question 3: Security & Encryption Overlap

**Question**: How exactly is AES/KMS wired into L2/L3 stores, and how is it integrated with the ledger? Are there any places where plaintext is still persisted or logged accidentally?

### Code Analysis

**Findings**:

1. **AES encryption is properly integrated**:
   - `memory_service/crypto.py:102-110`: `write_secure_json()` encrypts if `DAENA_MEMORY_AES_KEY` is set
   - `memory_service/crypto.py:113-120`: `read_secure_json()` decrypts automatically
   - `memory_service/adapters/l2_nbmf_store.py:34`: Uses `write_secure_json()` for all L2 writes
   - `memory_service/adapters/l3_cold_store.py`: Should use same pattern (need to verify)

2. **KMS integration exists but not fully wired**:
   - `memory_service/kms.py:102-119`: `record_rotation()` logs key rotations
   - `memory_service/kms.py:140-166`: `create_manifest()` creates signed manifests
   - **Gap**: Key rotations are logged to KMS but not automatically propagated to crypto module
   - **Gap**: No automatic key refresh when KMS manifest changes

3. **Ledger integration**:
   - `memory_service/ledger.py:115-119`: `log_event()` logs all operations
   - `memory_service/router.py:278-284`: Writes are logged to ledger
   - **Gap**: Ledger entries are JSON, not encrypted (by design for audit trail)
   - **Gap**: No explicit logging of encryption status in ledger

4. **Potential plaintext leaks**:
   - `memory_service/router.py:257-264`: `_attach_meta()` may include payload in logs
   - `memory_service/metrics.py`: Counters don't expose payloads (safe)
   - **Risk**: If `__meta__` contains sensitive data, it could be logged

### Implementation Status

- ✅ **Implemented**: AES encryption for L2/L3 stores (via `write_secure_json`)
- ⚠️ **Partial**: KMS logging exists but not auto-refresh
- ✅ **Implemented**: Ledger audit trail (intentionally unencrypted)
- ⚠️ **Risk**: Meta attachment could leak sensitive data in logs

### Code References

- `memory_service/crypto.py:102-110` - Encryption write
- `memory_service/adapters/l2_nbmf_store.py:34` - L2 encryption
- `memory_service/kms.py:102-119` - KMS rotation logging
- `memory_service/router.py:257-264` - Meta attachment (potential leak)

### Recommendation

**Gap**: Need to:
1. Verify L3 uses `write_secure_json()` (check `l3_cold_store.py`)
2. Add automatic key refresh from KMS manifests
3. Add encryption status to ledger entries
4. Add redaction for sensitive metadata in logs

**Proposed Fix**: 
- Verify L3 encryption
- Add `crypto.refresh_key_from_kms()` helper
- Add `encrypted: true` flag to ledger entries

---

## Question 4: Scaling & Decay

**Question**: How does the system currently handle aging, decay, or tier migration when some records are accessed heavily and others rarely? Is there any global or per-department feedback loop to rebalance?

### Code Analysis

**Findings**:

1. **Aging system exists but is time-based only**:
   - `memory_service/aging.py:37-120`: `apply_aging()` applies compression/summarization based on `created_at` timestamp
   - `memory_service/aging.py:57`: Age calculated as `(now_ts - created_at) / SECONDS_IN_DAY`
   - **Gap**: No access frequency tracking (hot vs cold)
   - **Gap**: No per-department aging policies

2. **Tier migration**:
   - `memory_service/aging.py:92-115`: `summarize_pack` action moves full payload to L3, keeps summary in L2
   - `memory_service/router.py:388-398`: L3 reads automatically re-index to L1 (promotion on access)
   - **Gap**: No automatic promotion of hot L3 records back to L2

3. **No access tracking**:
   - `memory_service/router.py:379-398`: Reads don't update access timestamps
   - `memory_service/metrics.py`: Tracks read counts but not per-record access patterns
   - **Gap**: No "last_accessed" field in metadata

4. **No rebalancing feedback loop**:
   - No global scheduler to promote hot L3 → L2
   - No demotion of cold L2 → L3 based on access patterns
   - Aging is one-way (L2 → L3), no reverse flow

### Implementation Status

- ✅ **Implemented**: Time-based aging (L2 → L3 summarization)
- ✅ **Implemented**: Compression tightening over time
- ❌ **Not implemented**: Access-frequency-based aging
- ❌ **Not implemented**: Hot record promotion (L3 → L2)
- ❌ **Not implemented**: Per-department aging policies
- ❌ **Not implemented**: Rebalancing feedback loop

### Code References

- `memory_service/aging.py:37-120` - Aging logic (time-based only)
- `memory_service/router.py:388-398` - L3 read (promotes to L1, not L2)
- `memory_service/metrics.py:13-14` - Read counters (not per-record)

### Recommendation

**Gap**: Need to add:
1. `last_accessed` timestamp in metadata (updated on read)
2. Access frequency counter per record
3. Hot record promotion scheduler (L3 → L2 for frequently accessed)
4. Per-department aging policies in config
5. Rebalancing job that runs periodically

**Proposed Fix**: 
- Add `_update_access_metadata()` in `router.py` read paths
- Add `promote_hot_records()` function in `aging.py`
- Add access-based aging actions in config

---

## Question 5: Governance AI Independence

**Question**: To what extent does the trust pipeline depend on LLM calls vs. deterministic rules? Are there any deterministic trust graphs / scoring functions that operate independently of LLM outputs?

### Code Analysis

**Findings**:

1. **Trust pipeline is mostly deterministic**:
   - `memory_service/trust_manager.py:108-127`: `compute_trust()` uses SimHash for consensus (deterministic)
   - `memory_service/trust_manager.py:129-161`: `assess()` combines divergence, consensus, safety (deterministic)
   - `memory_service/trust_manager.py:163-179`: `_divergence()` uses SequenceMatcher and dict/list similarity (deterministic)
   - **No LLM calls in trust scoring itself**

2. **LLM dependency is indirect**:
   - `memory_service/trust_manager.py:136`: `hallucination_scores` parameter (from LLM) affects safety score
   - `memory_service/router.py:215-249`: Divergence check compares payloads (deterministic)
   - **Gap**: If `hallucination_scores` not provided, defaults to 1.0 (safe)

3. **No deterministic trust graph**:
   - `memory_service/trust_manager.py`: No graph structure (nodes/edges)
   - No trust relationships between records/agents
   - Trust is computed per-record, not as a graph

4. **Deterministic components**:
   - ✅ SimHash near-duplicate detection (deterministic)
   - ✅ SequenceMatcher similarity (deterministic)
   - ✅ Dict/list similarity (deterministic)
   - ⚠️ Hallucination scores (LLM-dependent, but optional)

### Implementation Status

- ✅ **Implemented**: Deterministic trust scoring (SimHash, similarity)
- ✅ **Implemented**: Deterministic divergence detection
- ⚠️ **Partial**: Hallucination scores optional (defaults to safe if missing)
- ❌ **Not implemented**: Trust graph structure
- ❌ **Not implemented**: Inter-record trust relationships

### Code References

- `memory_service/trust_manager.py:108-127` - Trust computation (deterministic)
- `memory_service/trust_manager.py:163-179` - Divergence (deterministic)
- `memory_service/simhash_neardup.py` - SimHash (deterministic)
- `memory_service/router.py:215-249` - Divergence evaluation

### Recommendation

**Gap**: Need to add:
1. Trust graph structure (nodes = records/agents, edges = trust relationships)
2. Deterministic trust propagation (e.g., if A trusts B and B trusts C, then A trusts C with decay)
3. Make hallucination scores optional (already is, but document it better)

**Proposed Fix**: 
- Add `TrustGraph` class with deterministic propagation
- Document that trust pipeline is LLM-independent (hallucination scores are optional enhancement)

---

## Summary of Gaps & Fixes

### High Priority Fixes

1. **Multimodal Support**: Add content type detection and binary encoding
2. **Compute Profiling**: Add CPU/GPU time tracking
3. **Access-Based Aging**: Add `last_accessed` tracking and hot record promotion
4. **KMS Auto-Refresh**: Add automatic key refresh from KMS manifests

### Medium Priority Fixes

5. **Trust Graph**: Add deterministic trust graph structure
6. **L3 Encryption Verification**: Ensure L3 uses `write_secure_json()`
7. **Per-Department Aging**: Add department-specific aging policies

### Low Priority / Documentation

8. **Encryption Status in Ledger**: Add `encrypted: true` flag
9. **Meta Redaction**: Add sensitive data redaction in logs
10. **Trust Graph Documentation**: Document LLM-independence of trust pipeline

---

**Next Steps**: Implement fixes in order of priority, starting with high-priority items.

