# Intelligence Orchestration Map

Date: 2026-04-29

| Runtime/tool | Availability check | Best use | Risk/cost | Fallback | UI status |
|---|---|---|---|---|---|
| Claude Code / Claude CLI | runtime registry and auth probes | architecture, codebase reasoning, writing | paid/local CLI dependency | Codex/Gemini/local | `/runtimes` |
| Codex CLI | runtime registry adapters | code repair, review, tests | paid/CLI dependency | Claude/local | `/runtimes` |
| Gemini CLI | runtime registry or explicit CLI check | grounded research and second opinion | paid/account dependency | Perplexity/search | `/runtimes` if configured |
| Perplexity API | env/API availability | current-world market/investor research | paid/external data | web search/manual citations | not first-class UI |
| Ollama/local LLM | runtime registry/llama server | private low-cost tasks | local GPU/latency | cloud runtime | `/runtimes` |
| llama-server GGUF | `start-daena.bat` checks port 8080 | local OpenAI-compatible inference | model availability | Ollama/cloud | launch script output |
| RAG/NBMF memory | `/memory/*`, memory services | private company context | stale if not indexed | docs/code search | partial |
| Obsidian/graphify/Axon | docs and graph artifacts | project navigation and shared memory | stale index risk | rebuild graph | not first-class UI |
| MCP servers | Claude config plus DB `mcp_servers` | real-world tool calls | connector permission risk | disabled/not connected | Connections/MCP |
| Skills | `skills` folder plus skill-refinery | reusable operating playbooks | prompt injection if untrusted | quarantine/review | Skills page |

## Routing Policy

- Simple admin tasks: cheap/fast local or primary runtime.
- Code repair: Codex workflow plus tests.
- Architecture decisions: primary runtime, optionally Council/Quintessence if high-risk.
- Current research: Perplexity/Gemini/search-capable tool with citations.
- Investor writing: best writing/reasoning model plus claims ledger.
- Security: defensive security agent only after scope confirmation.
- Private company memory: local/RAG first.
- External actions: draft first, approval before send/submit/action.

## Gaps

- No single "intelligence status" page combines runtime, RAG, graph, MCP, and skill health.
- Perplexity/Gemini availability is not clearly surfaced to the founder.
- RAG/Obsidian status needs a first-class honest endpoint.

