---
name: scrapegraphai
description: |
  LLM-powered web scraper. Wraps the open-source ScrapeGraphAI Python
  library (https://github.com/ScrapeGraphAI/Scrapegraph-ai) — extracts
  structured data from a URL given a natural-language prompt. Runs
  entirely on your local Qwen3-8B llama-server. No API key, no cloud
  calls, no per-request cost.
trigger:
  - User asks "scrape", "extract", "pull data from this page".
  - You have a URL + a description of fields to extract.
  - You need structured JSON output from a non-API website.
when_not_to_use:
  - Site has a real API. Use the API.
  - Site requires login + interactive flow. Use Playwright / browser-use.
  - Single static page where regex/CSS selectors are sufficient. Use BeautifulSoup.
last_updated: 2026-05-05
---

# ScrapeGraphAI — local-only install (no API key)

## Architecture chosen 2026-05-05

The user explicitly wanted the OPEN-SOURCE library
(github.com/ScrapeGraphAI/Scrapegraph-ai), not the paid cloud MCP. So:

```
┌─────────────────────┐   stdio JSON-RPC   ┌────────────────────────────┐
│ Claude Code / Codex │ ─────────────────→ │ scrapegraph-local MCP      │
│   .claude.json /    │                    │ FastMCP server (Python)    │
│   config.toml entry │ ←───────────────── │ + scrapegraphai 1.76.0     │
└─────────────────────┘                    └─────────────┬──────────────┘
                                                         │ Playwright + LangChain
                                                         ▼
                                           ┌──────────────────────────┐
                                           │ Local llama-server :8080 │
                                           │ (Qwen3-8B-Q4_K_M.gguf)   │
                                           └──────────────────────────┘
```

No cloud. No API key. Everything runs on the 4060 GPU.

## Five install paths (all done 2026-05-05)

| Path | Where | Cost | Architecture |
|---|---|---|---|
| **A. Daena Python lib** | `D:\Ideas\Daena\venv_daena\` | $0 | Direct import: `from scrapegraphai.graphs import SmartScraperGraph` |
| **B. Claude Code MCP** | `~/.claude.json` mcpServers | $0 | Spawns wrapper at `D:\agents\mcp-servers\scrapegraph-local\server.py` using Daena's venv |
| **C. Codex CLI MCP** | `~/.codex/config.toml` mcp_servers | $0 | Same wrapper as B (auto-synced by `D:\agents\sync\bidi-mcp-sync.py`) |
| **D. Career OPS enricher** | `D:\Ideas\Career OPS\career_ops\enrichers\` | $0 | Direct import in Career OPS's own venv (scrapegraphai also installed there) |
| **E. ContentOps plugin** | `D:\Ideas\contentops-core\contentops\scrapers\` | $0 | **Subprocess-isolated** — shells out to Daena's venv via `D:\agents\mcp-servers\scrapegraph-local\worker.py` because ContentOps's spacy/thinc would conflict with scrapegraphai's numpy>=2 |

**Why path E uses a subprocess:** scrapegraphai pulls `numpy>=2`, but
ContentOps's existing `thinc` and `spacy` were compiled against
`numpy<2`. Installing scrapegraphai directly into ContentOps's venv
breaks `import spacy` with `numpy.dtype size changed... Expected 96,
got 88`. Keeping the deps isolated avoids the conflict and lets each
project's venv stay healthy.

## MCP tools (Path B + C)

| Tool | Args | Returns |
|---|---|---|
| `scrape_url` | `url`, `prompt`, `headless=True` | `{"url": ..., "result": <structured dict from LLM>}` |
| `markdownify` | `url`, `headless=True` | `{"url": ..., "markdown": "..."}` (no LLM call — fast) |
| `scrape_search` | `query`, `prompt`, `num_results=3` | Google-searches then extracts from top N |
| `health_check` | (none) | `{"scrapegraphai_version", "llm_health", "llm_url"}` |

Run `health_check` first to confirm the local llama-server is up.

## Path A — direct Python use inside Daena

```python
# D:\Ideas\Daena\venv_daena\Scripts\python.exe
from scrapegraphai.graphs import SmartScraperGraph

config = {
    "llm": {
        "model": "openai/qwen3-8b",
        "api_key": "not-needed",          # llama-server ignores this
        "base_url": "http://127.0.0.1:8080/v1",
        "temperature": 0.1,
    },
    "verbose": False,
    "headless": True,
}

scraper = SmartScraperGraph(
    prompt="Extract every job posting: title, company, location, salary.",
    source="https://www.linkedin.com/jobs/search/?keywords=AI+Engineer",
    config=config,
)
print(scraper.run())
```

Other graphs available:

| Graph | Input | Use case |
|---|---|---|
| `SmartScraperGraph` | one URL | Default. Single page extraction. |
| `SmartScraperMultiGraph` | list of URLs | Same prompt across many pages. |
| `SearchGraph` | query string | Google → top N → extract from each. |
| `MDScraperGraph` | URL | Page → markdown (no LLM). |
| `JSONScraperGraph` | local JSON file | Extract from a JSON document. |
| `XMLScraperGraph` | local XML file | Extract from XML. |
| `ScreenshotScraperGraph` | URL with images | Vision-LLM extraction. |
| `OmniScraperGraph` | URL with images | Text + image-description extraction. |

## Hardware / runtime requirements

- Python 3.10+ ✓ (Daena venv is 3.11)
- Playwright + Chromium (auto-installed with `pip install scrapegraphai`)
- Local Qwen3-8B llama-server at `127.0.0.1:8080`:
  - Start with `start-career-ops.bat [1]` or directly:
    ```
    D:\Ideas\llama.cpp\llama-server.exe ^
      -m D:\Ideas\MODELS_ROOT\gguf\qwen3-8b\Qwen3-8B-Q4_K_M.gguf ^
      --port 8080 --host 127.0.0.1 -n 4096 -c 8192
    ```
  - Uses ~6 GB VRAM, ~20-50 tok/s on RTX 4060 Laptop.

## Configuration (env vars in MCP entry)

The wrapper reads these from the MCP server's env:

| Env var | Default | Purpose |
|---|---|---|
| `SCRAPEGRAPH_LLM_URL` | `http://127.0.0.1:8080/v1` | OpenAI-compat endpoint |
| `SCRAPEGRAPH_LLM_MODEL` | `openai/qwen3-8b` | Any name; llama-server doesn't care |
| `SCRAPEGRAPH_LLM_TIMEOUT` | `120` | Per-page LLM call timeout (sec) |
| `SCRAPEGRAPH_HEADLESS` | `1` | `0` to show the Chromium window |
| `SCRAPEGRAPH_VERBOSE` | `0` | `1` for noisy ScrapeGraphAI logs to stderr |

Set in `.claude.json`'s `mcpServers.scrapegraph.env` and propagate via
`python D:\agents\sync\bidi-mcp-sync.py`.

## Integration into Career OPS (Path D)

Career OPS's existing search scraping uses **JobSpy** for LinkedIn /
Indeed / Glassdoor — that's untouched. ScrapeGraphAI is added as a
**post-search enricher** for the actual posting page (which after a
LinkedIn click usually redirects to Workday / Greenhouse / Lever / Ashby
/ direct careers page — places JobSpy doesn't read).

```python
from career_ops.enrichers import enrich_job_jd

# After JobSpy returns a job lead with .url pointing at the company ATS:
enrichment = await enrich_job_jd(job.url, timeout_s=90)
if enrichment.error:
    # Fall back to JobSpy's snippet
    pass
else:
    job.full_jd = enrichment.full_jd
    job.salary_band = enrichment.salary_band
    job.work_mode = enrichment.work_mode             # remote | hybrid | onsite
    job.apply_method = enrichment.apply_method       # workday | greenhouse | ...
    if enrichment.posting_status == "closed":
        # Skip — don't waste an Easy Apply attempt on a dead posting
        return
```

`JDEnrichment` dataclass shape:
```
url, full_jd, salary_band, employment_type, work_mode,
apply_method, posting_status, error, raw
```

The orchestrator can call this BEFORE scoring (richer JD = better
score) or BEFORE applying (skip closed; route to right ATS handler).

## Integration into ContentOps (Path E)

ContentOps's plugin architecture (`contentops/scrapers/base.py` defines
`BaseScraper`) already supported "drop in a single file for a new
platform". The new plugin at
`contentops/scrapers/scrapegraphai_scraper.py` registers `TYPE =
"scrapegraphai"`.

**Niches.yaml usage:**
```yaml
- name: anthropic_announcements
  type: scrapegraphai
  url: https://www.anthropic.com/news
  prompt: |
    Extract every news item: title, url, published date if visible,
    one-sentence summary. Return as a JSON list.
  limit: 20
  scrape_interval_minutes: 360       # 6h — slower than RSS by design
```

The plugin's `fetch()` builds a JSON request `{url, prompt, headless,
model, base_url}`, spawns Daena's venv python with worker.py as
subprocess (passes the JSON via stdin), reads JSON from stdout,
normalizes into `ScrapedItem[]`, and returns. ContentOps's own venv
never imports scrapegraphai.

**Use it for** niches without RSS/API/Twitter handle. **Don't use it
for** anything that has an RSS feed (use the rss plugin — faster,
deterministic, no LLM cost).

## Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `health_check`: `llm_health UNREACHABLE` | llama-server not running | `start-career-ops.bat` choice [1] starts it |
| `JSONDecodeError` on result | Qwen returned prose | Add `/no_think` to prompt; lower temp to 0.05 |
| Slow (~30 s per scrape) | Playwright + LLM round-trip | Use `markdownify` first (no LLM), then a separate LLM pass |
| MCP server doesn't load in Claude Code | Daena venv python.exe path moved | Edit the `command` in `.claude.json`, run bidi-sync |
| `browser-use` dep warnings on `pip install` | scrapegraphai bumps minor versions | Harmless — both libs verified working 2026-05-05 |
| Bot detection (Cloudflare / hCaptcha) | Site blocks Playwright | Use `browser-use` stealth mode first, feed rendered HTML to `MDScraperGraph` |

## Files touched on 2026-05-05 install

| File | Change |
|---|---|
| `D:\Ideas\Daena\venv_daena\Lib\site-packages\scrapegraphai\` | NEW — `pip install scrapegraphai==1.76.0` |
| `D:\agents\mcp-servers\scrapegraph-local\server.py` | NEW — FastMCP wrapper exposing 4 tools backed by local Qwen3 |
| `C:\Users\masou\.claude.json` | Added `mcpServers.scrapegraph` → local wrapper |
| `C:\Users\masou\.codex\config.toml` | Auto-synced — `[mcp_servers.scrapegraph]` table |
| `D:\agents\skills\scrapegraphai\SKILL.md` | THIS file. Canonical skill location. |
| `D:\Ideas\Daena\skills\scrapegraphai\SKILL.md` | Mirror per CLAUDE.md SKILLS SYNC RULE |

## Quick smoke test (after restart)

In a new Claude Code or Codex session, ask:

> Use the `scrapegraph health_check` tool.

You should see:
```json
{"scrapegraphai_version": "1.76.0", "llm_health": "OK (200)", "llm_url": "http://127.0.0.1:8080/health"}
```

Then try a real scrape:

> Use `scrape_url` on https://example.com with prompt "Extract the page title and the first paragraph as a dict".

You should get back something like:
```json
{"url": "https://example.com", "result": {"title": "Example Domain", "paragraph": "..."}}
```
