---
name: rag-core
description: Universal RAG + anti-hallucination service for all MAS-AI projects. Use when you need grounded retrieval with citations across Daena, WorldSignal, ContentOps, Polybet, Claude-Coworker, or any new project.
metadata:
  type: skill
  port: 8100
  service_url: http://127.0.0.1:8100
---

# ragx — Universal RAG

Single HTTP service (port 8100, registered in `D:\agents\ports.yaml`) that
every project calls. Returns answers with mandatory citations and a strict
abstention contract.

## What it does

```
sources → chunk → embed (bge-large-en-v1.5)
        → ChromaDB + BM25 + sqlite (per-collection)
query  → dense + sparse → RRF fuse → top-50
        → bge-reranker-v2-m3 (4060 GPU) → top-8
        → CRAG critic (local llama-server) grades chunks
        → NLI verifier (deberta-v3-mnli) entailment check
        → response: { answer, citations[], confidence, abstained, reason }
```

## Universal response contract

Every project consuming ragx receives this JSON shape:

```json
{
  "answer": "Daena uses Shield as its always-on governance pipeline. [chunk_id=..., ...]",
  "citations": [
    {"chunk_id": "ab12...", "source_path": "D:/Ideas/Daena/...", "score": 0.91, "snippet": "..."}
  ],
  "confidence": 0.91,
  "abstained": false,
  "reason": null,
  "stats": {"dense_hits": 50, "sparse_hits": 50, "fused": 50, "reranked": 8,
            "grade_correct": 7, "grade_ambiguous": 1, "grade_wrong": 0},
  "timing_ms": {"embed_ms": 18, "dense_ms": 32, "sparse_ms": 11,
                "fuse_ms": 1, "rerank_ms": 84, "total_ms": 162}
}
```

When evidence is weak the response abstains:

```json
{ "answer": null, "abstained": true,
  "reason": "insufficient evidence: only 1 chunk above threshold",
  "citations": [], "confidence": 0.0 }
```

## When to use

Trigger when the user wants any of:

- "search my projects for X"
- "ground this answer in our docs"
- "what did we decide about X"
- "build a RAG for project Y"
- "stop the model hallucinating about our codebase"
- Anything that should be grounded in MAS-AI internal knowledge rather
  than the model's training data.

## How to use — CLI

```powershell
# Start the service (only needed once per session; runs on :8100)
cd D:\Ideas\_tools\rag-core
.\.venv\Scripts\python.exe -m ragx.cli serve

# In another shell:
ragx health
ragx index "D:\Ideas\Daena\backend" --collection daena-code --project daena
ragx query "How does Shield enforce policies?" --collection daena-code
ragx stats daena-code
```

## How to use — HTTP

```python
import httpx
r = httpx.post("http://127.0.0.1:8100/query", json={
    "collection": "daena-code",
    "q": "How does the orchestrator route to QUINTESSENCE?",
    "k": 8,
})
data = r.json()
if data["abstained"]:
    handle_no_evidence(data["reason"])
else:
    use_with_citations(data["answer"], data["citations"])
```

## Hardware requirements

- **Embedder** (bge-large-en-v1.5): ~1.3 GB VRAM, CPU OK (slower)
- **Reranker** (bge-reranker-v2-m3): ~2.3 GB VRAM, GPU strongly preferred
- **NLI** (deberta-v3-mnli): ~1.7 GB VRAM
- **CRAG critic**: piggybacks on local llama-server at :8080 (already running)

Total GPU footprint on the 4060 Laptop: ~5 GB. Fits.

## Collections

One per logical bucket. Conventions:

| Collection            | Source                          | Owner project    |
|-----------------------|---------------------------------|------------------|
| `daena-code`          | D:/Ideas/Daena/backend          | Daena            |
| `daena-docs`          | D:/Ideas/Daena/Doc              | Daena            |
| `worldsignal-code`    | D:/Ideas/WorldSignal            | WorldSignal      |
| `contentops-scripts`  | D:/Ideas/contentops-core        | ContentOps       |
| `claude-coworker`     | D:/Claude-Coworker              | Bridge           |
| `agents-docs`         | D:/agents                       | Cross-cutting    |

## Auto-update (P4)

A watchdog observer is registered per collection. Source changes debounce
30 s → SHA-256 dedupe → selective re-embed. Git post-commit hooks fire an
immediate delta. Daily RAGAS eval scores logged to `data/eval/`.

## Anti-hallucination guarantees

1. **Citation-mandatory** — every answer sentence references chunk_ids.
2. **Abstention** when:
   - fewer than `min_recall` chunks above rerank threshold
   - top rerank score below `min_rerank_score`
   - CRAG marks >50% of chunks Wrong
   - NLI entailment for any claim below `min_nli_score`
3. **Versioned embeddings** — model upgrades trigger selective re-embed,
   not a full rebuild.

## Files (orientation)

- `ragx/api.py`        — FastAPI routes
- `ragx/ingest.py`     — chunk → embed → store
- `ragx/retrieve.py`   — dense + sparse + RRF + rerank
- `ragx/rerank.py`     — bge-reranker-v2-m3
- `ragx/verify.py`     — CRAG + NLI (P3)
- `ragx/storage.py`    — ChromaDB + BM25 + sqlite
- `ragx/settings.py`   — env config (MODELS_ROOT-aware)
- `ragx/cli.py`        — `ragx` typer command
- `ragx/server.py`     — entrypoint with port_registry reserve

## Related

- [[axon]] — code symbol graph (D:/Ideas/_tools/axon)
- [[mempalace]] — human-decision memory (MCP)
- [[codebase-memory]] — ADRs + architecture
- ragx is the **retrieval + generation gate** that sits ABOVE these
  symbol/memory layers. Axon/mempalace are sources; ragx is the
  universal query API any project hits.
