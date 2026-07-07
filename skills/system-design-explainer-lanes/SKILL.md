---
name: system-design-explainer-lanes
description: ContentOps motion-diagram lanes inspired by @kodekloud (V1→V2→V3 naive-to-optimized whiteboard) + @__howitworks_ (terminal-aesthetic ASCII comparison tables). Use when the user has a system-design / API-comparison / scaling topic that fits one of these two storytelling shapes.
metadata:
  type: skill
  domain: contentops
  reverse_engineered_from:
    - https://www.instagram.com/kodekloud/
    - https://www.instagram.com/__howitworks_/
  added: 2026-05-26
---

# System Design Explainer Lanes

Two new ContentOps render lanes that capture how two of the highest-engagement system-design IG accounts present technical content. Reverse-engineered from screenshots + post pattern analysis on 2026-05-25.

## When To Pick Each Lane

| Topic shape | Lane | Example |
|---|---|---|
| "How to scale X" / "V1 NAIVE → V2 → V3" progression | `system_design` | "Image Upload Pipeline at 100 users vs 10M users" |
| "X vs Y vs Z" technology comparison with 5-7 axes | `terminal_compare` | "REST vs GraphQL vs gRPC" |
| Single concept explainer | `education` (existing) | "How RAG works" |
| Attack chain / threat path | `security` (existing) | "Prompt injection attack vector" |
| Breaking news | `news` (existing) | "OpenAI launches X" |

## Lane 1: `system_design` (kodekloud style)

**Visual signature**:
- 3-act progression: V1 NAIVE → V2 (fix bottleneck) → V3 (production-grade)
- Real cloud icons (EC2, S3, RDS, Redis, SQS, CDN) NOT generic boxes
- Stick-figure user → service → storage flow diagrams
- Punchline closing frame: `DONE. SHIP IT.` or `That's how you scale to 10M users.`
- Episode numbering: `Q8` / `Episode 9` etc. drives the binge-loop

**Scene type**: `naive_vs_optimized`

**diagram_spec contract** (validated in `gold_explainer_schema.py:naive_vs_optimized`):
```json
{
  "versions": [
    {
      "label": "V1: NAIVE",
      "tagline": "The dumbest thing that works",
      "nodes": [
        {"label": "User", "icon": "user"},
        {"label": "EC2 Server", "icon": "ec2"},
        {"label": "Local Disk", "icon": "db"}
      ]
    },
    {
      "label": "V2: CACHE",
      "tagline": "Add Redis between user and DB",
      "nodes": [
        {"label": "User", "icon": "user"},
        {"label": "Redis", "icon": "redis"},
        {"label": "EC2", "icon": "ec2"},
        {"label": "RDS", "icon": "rds"}
      ],
      "breaks": ["Local disk doesn't scale past 1 server"]
    },
    {
      "label": "V3: ASYNC",
      "tagline": "Pull large blobs via SQS + S3",
      "nodes": [
        {"label": "User", "icon": "user"},
        {"label": "API", "icon": "api"},
        {"label": "SQS Queue", "icon": "sqs"},
        {"label": "Worker", "icon": "worker"},
        {"label": "S3", "icon": "s3"}
      ]
    }
  ],
  "punchline": "DONE. SHIP IT."
}
```

**Angles** (override via `angle_override` param to `build_motion_diagram_item`):
- `naive_to_optimized` — default, the V1→V2→V3 progression
- `bottleneck_walkthrough` — low load works, what breaks at 10x
- `build_vs_buy` — DIY vs managed-service comparison
- `scaling_story` — same product at 100 / 100K / 100M users
- `from_monolith` — what to peel off first

## Lane 2: `terminal_compare` (howitworks style)

**Visual signature**:
- Monospace ASCII table on dark navy background
- Color-coded columns (blue / green / yellow / pink)
- 5-7 comparison rows (Protocol, Format, Schema, Cache, Stream, Best for)
- Closing one-liner heuristic: `Know the trade-offs. Pick the right tool.`
- No voiceover — silent carousel-style (Threads/IG-native)
- Numbered series: `System Design Series - 9` in caption

**Scene type**: `terminal_compare`

**diagram_spec contract** (validated in `gold_explainer_schema.py:terminal_compare`):
```json
{
  "columns": ["REST", "GraphQL", "gRPC"],
  "rows": [
    {"dimension": "Protocol", "values": ["HTTP/1.1+", "HTTP POST", "HTTP/2"]},
    {"dimension": "Format",   "values": ["JSON",      "JSON",      "Binary"]},
    {"dimension": "Schema",   "values": ["None",      "Strict",    "Strict"]},
    {"dimension": "Cache",    "values": ["Easy",      "Hard",      "Manual"]},
    {"dimension": "Stream",   "values": ["No",        "Subscribe", "Built-in"]},
    {"dimension": "Best for", "values": ["Public API","Complex data","Microsvcs"]}
  ],
  "heuristic": "Know the trade-offs. Pick the right tool."
}
```

**Angles**:
- `three_way_compare` — default, 3 columns + 5-7 axes
- `tradeoff_matrix` — rows are properties, highlight tie-breaker row
- `pick_the_right_tool` — same task, 3 tools, when each wins
- `decision_tree` — if-this-then-that rendered as terminal text

## How To Invoke

From CLI:
```bash
# system_design lane
python -m contentops.motion_diagram_pipeline \
  --lane system_design \
  --topic "Image Upload Pipeline at 10M users" \
  --angle naive_to_optimized

# terminal_compare lane
python -m contentops.motion_diagram_pipeline \
  --lane terminal_compare \
  --topic "REST vs GraphQL vs gRPC" \
  --angle three_way_compare
```

From Python (programmatic):
```python
from contentops.motion_diagram_planner import build_motion_diagram_item
from contentops.gold_explainer_pipeline import render_explainer

item = build_motion_diagram_item(
    lane="system_design",
    topic="Build a URL shortener",
    angle_override="bottleneck_walkthrough",
)
render_explainer(item)
```

## Series Numbering (Retention Loop)

Both source creators use episode numbering to drive binge-watching: viewers see `Episode 9` and check if 1-8 exist. We adopt the same — set in `spec.json`:

```json
{
  "series_label": "Q8",                          // kodekloud style
  // OR
  "series_name": "System Design Series",
  "series_episode": 9                            // howitworks style: "System Design Series · 9"
}
```

The publisher's `_series_label()` helper at `publish_now.py` prepends this to the caption title automatically.

## Hashtag Pattern

Both lanes use the standard `#Mas-AI` brand tag + topic-keyword tags. The publisher's `_hashtags_for_spec()` routes based on title keywords:
- `system_design` → adds `#SystemDesign`, `#Architecture`, `#Scalability`
- `terminal_compare` → adds `#API`, `#SoftwareEngineering`, lane-specific tech tags

## Inspiration Sources Auto-Scrape

Both source accounts are registered in `data/inspiration_sources.yaml` with `lane_hint`:

```yaml
- platform: instagram
  handle: kodekloud
  niche: system_design
  lane_hint: system_design
  enabled: true

- platform: instagram
  handle: __howitworks_
  niche: system_design
  lane_hint: terminal_compare
  enabled: true
```

The scheduled task `ContentOps_Inspiration_Scrape` pulls captions from both daily and queues them as viral_queue items with the right lane_hint pre-set. The motion_diagram_router honors lane_hint to override its keyword classifier.

## What This Skill Replaces / Complements

- **Replaces nothing** — these are ADDITIVE lanes alongside news/education/security
- **Complements** `news-to-video`, `infographic-video-pipeline`, `motion-diagram-router` skills
- **Cross-references** `inspiration-sources.yaml` for source curation pattern

## Future Iterations

If the IG accounts evolve their style (they ship ~3-5 posts/week), re-scrape their recent posts every 2 weeks and update the angles / `diagram_spec` examples in this skill. The lane infrastructure stays stable; the prompt directives + scene type validators are where style updates land.
