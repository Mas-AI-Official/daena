# ContentOps Ingest Contract

The wire contract between Masoud's external content scraper
(YouTube + Grabit + NotebookLM + Google search + book extraction)
and Daena's Skill Refinery.

Reference implementation on Daena side:
`backend/app/api/v1/skill_refinery.py::ingest_batch`.
Test coverage:
`backend/tests/test_contentops_ingest.py`.

---

## Endpoint

```
POST /api/v1/skills/refinery/ingest-batch
Authorization: Bearer <JWT>
Content-Type: application/json
```

JWT can be generated for any FOUNDER or OPERATOR account. For the
MAS-AI tenant, use the auto-seeded `masoud.masoori@mas-ai.co` +
the `FOUNDER_DEFAULT_PASSWORD` from `.env` to obtain a token via
`POST /api/v1/auth/login`.

## Request body

```json
{
  "batch_label": "hormozi-2026-Q1",
  "items": [
    {
      "source_type": "youtube",
      "source_url": "https://youtube.com/watch?v=...",
      "creator": "Alex Hormozi",
      "title": "The Offer That Prints Money",
      "published_at": "2026-03-14T10:00:00Z",
      "content": "<full transcript text>",
      "extras": {
        "video_duration_sec": 2840,
        "chapter_marks": [...],
        "notebooklm_summary_url": "..."
      }
    }
  ]
}
```

### Field rules

| Field | Required | Max | Notes |
|---|---|---|---|
| `batch_label` | no | 120 | Groups a scrape run. Defaults to an ISO timestamp. |
| `items` | yes | 1 to 50 | Batch size hard-capped at 50 to keep p95 latency reasonable. |
| `items[].source_type` | yes | 32 | Enum (below). Typos 422 with a valid list. |
| `items[].source_url` | no | 2048 | Canonical link used for de-duplication by `creator` + `url`. |
| `items[].creator` | no | 200 | Channel / author / speaker. Used for rank weighting in the Skill Mining pipeline. |
| `items[].title` | no | 500 | Used only for display / skill-store metadata. |
| `items[].published_at` | no | ISO-8601 | Drives staleness scoring. Omit if unknown. |
| `items[].content` | yes | 10 to 200,000 chars | The transcript / article / chapter. |
| `items[].extras` | no | JSON object | Free-form. Preserved on the persisted skill's `source_metadata`. |

### Allowed `source_type` values

- `youtube` -- YouTube video transcript (Grabit output)
- `podcast` -- Podcast transcript (any Whisper output)
- `rss` -- Blog / Substack / newsletter article
- `book` -- Book chapter or excerpt
- `search` -- Google search result set
- `notebooklm` -- NotebookLM structured summary output
- `manual` -- Human-pasted text
- `other` -- Anything else; use sparingly

Unknown types return 422 with the list of valid ones.

## Response

```json
{
  "success": true,
  "data": {
    "batch_label": "hormozi-2026-Q1",
    "ok": 18,
    "errors": 2,
    "results": [
      {
        "index": 0,
        "status": "ok",
        "skill_id": "skill:sales.cold-email.problem-agitate-solve",
        "source_url": "https://youtube.com/watch?v=...",
        "creator": "Alex Hormozi"
      },
      {
        "index": 7,
        "status": "error",
        "reason": "LLM extraction failed: connection refused",
        "source_url": "..."
      }
    ]
  }
}
```

### Per-item statuses

- `ok` -- skill was extracted and persisted as T1_DRAFT. Includes the
  assigned `skill_id` so the scraper can reference it in future
  refinement or telemetry calls.
- `error` -- extraction failed. The `reason` field is human-readable;
  common causes are Ollama unreachable, content too short, or the LLM
  refused to extract a skill from the content. **The scraper should
  retry only error items**, not the full batch.

A batch with zero successful items still returns HTTP 201 with
`ok: 0, errors: N` -- partial success is the norm, not the exception.

## What happens after ingest

1. Each successful item becomes one `RefinedSkill` row at tier
   T1_DRAFT in the tenant's skill store.
2. `source_metadata` preserves `source_type`, `source_url`, `creator`,
   `published_at`, `batch_label`, and the entire `extras` payload.
3. The skill is NOT retrieved by agents yet. T1_DRAFT is untrusted.
4. Founder or an operator calls `POST /{skill_id}/refine` to run the
   3-pass refinement pipeline. Promotion to T2 happens there.
5. `news_monitor.py` uses `published_at` to compute staleness on a
   90-day rolling window.

Full lifecycle: `docs/pitch/SKILL-MINING-PIPELINE.md`.

## De-duplication

The endpoint does not currently de-duplicate across batches. If the
scraper POSTs the same YouTube video twice, two T1_DRAFT skills
result (each with its own `skill_id` derived from title + domain).
This is deliberate for the first release -- deduplication is part
of the Skill Promotion service (Phase N Stage 4), which runs after
refinement and compares embedded content across tier boundaries.

If you want to enforce no-duplicates up front, have the scraper
track `source_url` locally and skip URLs it already sent.

## Rate limits and governance

- Tenant-scoped. No cross-tenant writes possible.
- No explicit rate limit on this endpoint today. The Skill Refinery
  circuit breaker (MAX_CONCURRENT=3, 100K daily token cap per tenant)
  applies to refinement, not ingest. Ingest is effectively bounded by
  Ollama throughput on the host.
- Scraper should back off if it sees `errors > 0` consistently for
  more than 3 consecutive batches -- means Ollama is overloaded or
  unavailable.

## Example (Python, minimal)

```python
import httpx

JWT = "Bearer eyJ..."
API = "http://localhost:8000/api/v1/skills/refinery/ingest-batch"

payload = {
    "batch_label": "hormozi-weekly-2026-04-18",
    "items": [
        {
            "source_type": "youtube",
            "source_url": "https://youtube.com/watch?v=ABC123",
            "creator": "Alex Hormozi",
            "title": "The Grand Slam Offer",
            "published_at": "2026-04-10T14:00:00Z",
            "content": "<full transcript, 30-60k chars typical>",
        },
        # ... up to 49 more items
    ],
}

with httpx.Client(timeout=300) as client:
    resp = client.post(API, json=payload, headers={"Authorization": JWT})
    resp.raise_for_status()
    body = resp.json()

for r in body["data"]["results"]:
    if r["status"] == "ok":
        print("Ingested", r["skill_id"], "from", r.get("creator"))
    else:
        print("Retry later:", r["source_url"], "--", r["reason"])
```

## Open questions (ask Masoud)

- Should ingest also accept YouTube **comments** as a separate
  `source_type` for pain-mining (complement Reddit sub-mining)?
- Does Masoud's Grabit pipeline include chapter timestamps? If yes,
  store them in `extras.chapter_marks` and the Skill Refinery can
  cite exact timestamps in `source_refs` during T3 promotion.
- NotebookLM outputs can be very long and structured. Should the
  scraper POST the raw transcript AND the NotebookLM summary as two
  items, or merge them into one `content` field? Current design
  accepts either; two items is cleaner for traceability.
