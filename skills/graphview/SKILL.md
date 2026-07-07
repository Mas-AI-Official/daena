---
name: graphview
description: Unified 3D code-graph viewer at http://127.0.0.1:8120. Brain-like visualization of every indexed project, with project-colored clusters, mouse rotate/zoom/pan, RAGx-driven highlighting, and live status of axon + ragx. The primary visual entry point to the MAS-AI knowledge stack.
metadata:
  type: skill
  port: 8120
  service_url: http://127.0.0.1:8120
---

# graphview — the 3D knowledge frontend

The visual layer over the entire MAS-AI knowledge stack. Browser-based,
WebGL, ThreeJS under the hood. Open it instead of axon's 2D explorer
when you want to actually *see* the code.

## When to use

- "show me the codebase" / "give me a map of the code"
- "what does X connect to?"
- "where is the cluster about <feature>?"
- "highlight everything related to <natural-language query>"
- Whenever you'd otherwise open axon's web UI Explorer tab.

## Service

| | |
|---|---|
| URL  | http://127.0.0.1:8120 |
| Path | `D:\Ideas\_tools\graphview\` |
| Port | 8120 (reserved in `D:\agents\ports.yaml`) |
| Auto-start | Yes — `Startup\graphview-serve.bat` |

## Architecture

```
┌──────────────────────┐
│ graphview (8120)     │  ← 3D WebGL frontend (this skill)
│  • aggregates        │
│  • category-colors   │
│  • RAGx hooks        │
└─────┬────────────────┘
      │ /api/graph proxied + enriched
      ▼
┌──────────────────────┐         ┌─────────────────────┐
│ axon (8420)          │         │ ragx (8100)         │
│  • indexer + kuzu DB │         │  • Chroma + BM25    │
│  • symbol graph      │         │  • rerank + CRAG    │
│  • CLI + MCP         │         │  • NLI + citations  │
└──────────────────────┘         └─────────────────────┘
            │                              │
            └────── llama-server (8080) ───┘
                    (Qwen3-8B Q4_K_M)
```

## Mouse controls (native OrbitControls)

- **drag** → rotate around the cloud
- **scroll** → zoom (no MIN_ZOOM ceiling — fly out to see the whole brain)
- **right-drag** → pan
- **click a node** → camera flies in + right-side detail panel opens

## Left-panel features

- Live search (instant whitens matching nodes)
- Category filters (toggle individual node types on/off)
- Filters: dead code, archive/, draw-edges
- Node-count cap (500 / 1500 / 3000 / 6000 / 10000 / all)
- Reset camera button
- **RAGx panel**: type a natural-language question → ragx returns
  citations → graphview whitens the nodes whose `filePath` matches.
  You literally see *which part of the code answers your question.*

## Right-panel (status)

- Live ✓/✗ for axon and ragx
- Stats: nodes shown / total, edges shown / total
- Hosted project + list of all indexed projects

## API surface

```
GET  /api/health                  liveness + dependency checks
GET  /api/projects                all .axon indexes detected on disk
GET  /api/graph                   3d-force-graph payload + category colors
                                  ?include_dead, ?include_archive,
                                  ?max_nodes (0 = all)
GET  /api/node/{id:path}          per-node detail (proxies axon)
POST /api/ragx-highlight          {q, collection?} → matching paths
```

## Relationship to other tools

| Tool | What it does | When to invoke instead |
|---|---|---|
| **graphview** (this) | visual exploration, RAGx-aware highlighting | default visual entry |
| **axon** (`mcp__axon__*`) | symbol queries, dead-code reports, CLI, Cypher | from Claude/Codex via MCP, or for analysis tabs |
| **ragx** (`/query`) | retrieve-rerank-grade-cite for any question | when you need text answers, not visuals |
| **mempalace** (`mcp__mempalace__*`) | human decisions, timeline | for context like "why did we…" |
| **codebase-memory** (`mcp__codebase-memory__*`) | ADRs, architecture snapshots | for "what did we decide about…" |

## Multi-project (P2 — pending)

Currently shows the axon-hosted project (Daena by default). The
`/api/projects` endpoint already lists all `.axon` indexes on disk
(5 detected at writing). Switching the hosted project requires
restarting axon with a different `AXON_HOST_ROOT`. Cross-project
edges from graphify wikilinks come in the next iteration.

## Performance

- WebGL via ThreeJS — easily renders 10k nodes, can push 20k with
  the "max_nodes" cap raised.
- Default cap: 3000 (gives a smooth experience on laptops).
- The force layout settles in ~160 ticks (`cooldownTicks=160`) so
  CPU drops to idle once the spring relaxation finishes.

## Failure modes

- **axon down** → `/api/graph` returns 503. Restart with
  `D:\agents\sync\axon-start.ps1`.
- **ragx down** → status pane shows ✗, the highlight button reports
  "ragx unreachable" but the graph still works.
- **Empty graph** → axon hasn't analyzed the project; run
  `cd <project>; axon analyze .`

## Files (orientation)

- `graphview/api.py` — FastAPI routes
- `graphview/server.py` — uvicorn entry with shared port reservation
- `static/index.html` — single-page 3D viewer (CDN-only, no build step)

## Related

- [[axon]] — data layer; graphview consumes its `/api/graph`
- [[rag-core]] — semantic layer; graphview's "highlight cluster"
  feature calls ragx's `/query` endpoint
