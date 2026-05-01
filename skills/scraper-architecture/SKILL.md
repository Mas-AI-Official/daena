---
name: scraper-architecture
description: Pluggable scraper architecture for contentops — how to add a new platform, how to pick between direct API / commercial scraper / Playwright / yt-dlp, how to wire background scheduling with APScheduler, and how the viral-queue handoff to Claude Code works. Use when adding a new source, diagnosing a stuck scheduler job, or deciding whether to buy a scraping API or roll a Playwright plugin.
---

# Scraper Architecture (contentops/scrapers/)

## The 4-tier scraping decision tree

When someone asks "can you scrape X?" — pick the cheapest viable tier. Don't jump to Playwright if an API exists.

**Tier 1 — Direct platform API (free / near-free)**
Use when: the platform gives free or cheap official API access.
Examples: HackerNews Firebase API, Reddit RSS, GitHub trending HTML, any site with RSS/Atom, Anthropic blog feed.
Cost: $0. Rate: usually unlimited for reasonable use.
Code: just HTTP + parse. Plugin lives in `contentops/scrapers/<platform>.py` implementing `BaseScraper`.

**Tier 2 — Commercial scraper API (cheap, legal)**
Use when: platform's official API is expensive or gate-kept, but a third-party data broker offers the same data cheaper.
Examples, current pricing 2026:
- **TwitterAPI.io** — $0.15 per 1000 tweets; drop-in for X/Twitter. ~3% of official X API Pro cost.
- **Apify** — 1500+ actors, $39/mo Starter. Pre-built IG / TikTok / LinkedIn / Amazon scrapers with proxies + solvers bundled.
- **ScrapingBee** — $49/mo; proxy + JS-render + CAPTCHA solve for arbitrary sites.
- **Bright Data** — enterprise; use only when contracts require it.
- **SerpAPI** — Google/Bing/YouTube search results; $50/mo.
Cost: $30-500/mo depending on volume. Rate: predictable per plan.
Code: `requests.get(<their endpoint>, headers={"api-key": KEY})` — they handle proxies / rotation / solvers.
Pattern: one plugin per commercial API, set `REQUIRES_AUTH=True` and `AUTH_ENV_KEY="FOO_API_KEY"`.

**Tier 3 — yt-dlp (universal URL ingest)**
Use when: any video / podcast / social post URL needs to be pulled in for ingest — especially when we want transcript + thumbnail + metadata.
Covers: YouTube, TikTok, Instagram, Twitter videos, LinkedIn, Facebook, Reddit, Vimeo, SoundCloud, podcast RSS, ~1000 more extractors.
Cost: $0 (open source). Rate: whatever the origin site allows; lie about UA + add sleeps.
Code: our `link_ingest.py` plugin wraps it.
Pattern: pass any URL, get a normalized ScrapedItem with `evidence_image_url` (best thumb) and `extras.local_path` (when `ingest_full=True` downloads the MP4).

**Tier 4 — Custom Playwright (last resort)**
Use when: data is locked behind login, has anti-bot JS, or no API/commercial option exists. Examples: niche Discord servers, private Notion pages, locked Instagram DMs, specific-company internal tools.
Cost: $0 in API, but ongoing maintenance (selectors break). High ban risk.
Code: Playwright with persistent user-data-dir per platform (see `social-media-browser-puppeteer` skill).
Rate: heavily limited by hygiene (mobile UA, random delays, no follow-unfollow).

**Do NOT** build a custom Playwright scraper when a Tier 2 API exists for <$50/mo. Your time + maintenance cost will exceed the API fee in one week.

## The BaseScraper contract

Every plugin is a single file in `contentops/scrapers/` implementing:

```python
from .base import BaseScraper, ScrapedItem, register_scraper

@register_scraper
class MyPlatform(BaseScraper):
    TYPE = "my_platform"                 # matches `type:` in niches.yaml
    REQUIRES_AUTH = True                 # dashboard shows API-key field
    AUTH_ENV_KEY = "MY_PLATFORM_KEY"     # env var the plugin reads
    CONFIG_SCHEMA = {
        "handle": {"type": "string", "required": True},
        "limit":  {"type": "int", "default": 20},
    }

    def fetch(self, src_cfg: dict, since: datetime | None) -> list[ScrapedItem]:
        # Return ScrapedItems NEWER than `since`. Empty list on error.
        # NEVER raise — the scheduler swallows errors but logging is your job.
        ...
```

Then add to `contentops/scrapers/__init__.py`:
```python
from . import my_platform   # registers itself on import
```

Dashboard UI picks up the new type automatically via `/api/scheduler/plugins`.

## ScrapedItem shape

Normalized output every plugin returns — downstream code doesn't care which platform:

```python
ScrapedItem(
    source="twitter:@edzitron",                    # e.g. "reddit:r/LocalLLaMA"
    title="Anthropic removed Claude Code from Pro",
    url="https://x.com/edzitron/status/123",
    summary="Full text / description (up to 1500 chars)",
    published_at="2026-04-21T21:55:23Z",           # ISO-8601 UTC or None
    author="@edzitron",
    evidence_image_url="https://...",               # best single image for hero
    extras={"likes": 4500, "retweets": 1200, ...}  # per-platform signals
)
```

The `extras` dict is where platform-specific signals live (HN `score`, Twitter `likes`, yt-dlp `views`). The **virality scorer** checks these optionally — missing fields never break it.

## Background scheduling

`contentops/scheduler.py` runs APScheduler inside the dashboard FastAPI process. Why in-process not Celery:
- Single-node machine (RTX 4060 laptop), no distributed work
- Dashboard is already a long-running process; piggybacking saves an executable
- Scheduler jobs are rebuilt from `niches.yaml` on boot — no persistence layer needed

Per-niche flow every `scrape_interval_minutes`:
1. For each `source` in the niche, look up the plugin by `type`, call `fetch()`
2. Keyword filter → db dedup
3. Score via `contentops.viral`
4. Items above `viral_threshold` → write `data/viral_queue/<niche>_<item_id>.json`

When the scheduler is running, the dashboard's "Scheduler" tab shows:
- Running/stopped status + count of scheduled jobs
- Per-niche next-run time + last-run telemetry
- Viral queue preview (top 100 pending)
- Manual ▶ Run now button per niche

## Viral-queue handoff to Claude Code

The viral queue is a file-drop protocol:

- Scheduler writes `data/viral_queue/<niche>_<item_id>.json` when score ≥ threshold
- Claude Code (or a second APScheduler job) picks up queue files
- For each: runs the `news-to-video` skill pipeline → renders MP4 → posts via `social-media-browser-puppeteer`
- On success: `DELETE /api/viral-queue/<filename>` removes the queue entry

The advantage of file-drop over an in-process queue: Claude can watch the directory via `Monitor` tool, inspect files before acting, and the pipeline is resumable across restarts.

## Dashboard control surface

New endpoints (2026-04 addition):

| Endpoint | Purpose |
|---|---|
| `GET /api/scheduler/status` | Running state + jobs + last_runs + viral_queue_size + plugins list |
| `GET /api/scheduler/plugins` | All registered plugin types + schemas (drives form gen) |
| `POST /api/scheduler/run/{niche}` | Manual trigger — runs outside the schedule |
| `POST /api/scheduler/reload` | Re-read niches.yaml and reconcile jobs |
| `GET /api/viral-queue` | List queued items (top 100) |
| `DELETE /api/viral-queue/{file}` | Remove after successful render |

The niches API (`POST /api/niches/{name}`) auto-reloads the scheduler when `scrape_interval_minutes` or `sources` change — no dashboard restart.

## Anti-ban hygiene (for Tier 3 + 4)

1. **Mobile user-agent**: platforms are WAY more tolerant of "unusual" behavior from mobile UAs than desktop. Use iPhone Safari string.
2. **Random delays**: between URL fetches, `random.uniform(2, 8)` seconds. Never batch 50 fetches in 5 seconds.
3. **Respect origin**: for sites without explicit rate limits, cap at one request per 2 seconds.
4. **Session rotation**: Tier 4 Playwright plugins should rotate UAs every 60 days.
5. **No follow / no unfollow ever**: automating social graph actions = instant ban on every major platform.

## How to add a new source — worked example

Task: scrape Apify's TikTok Scraper actor.

1. Look up the actor ID at https://apify.com/apify/tiktok-scraper (e.g. `apify/tiktok-scraper`)
2. Create `contentops/scrapers/apify_actor.py`:
   ```python
   @register_scraper
   class ApifyActorScraper(BaseScraper):
       TYPE = "apify"
       REQUIRES_AUTH = True
       AUTH_ENV_KEY = "APIFY_API_TOKEN"
       CONFIG_SCHEMA = {
           "actor_id": {"type": "string", "required": True, "hint": "e.g. apify/tiktok-scraper"},
           "input":    {"type": "object", "required": True, "hint": "Actor-specific input JSON"},
       }

       def fetch(self, src_cfg, since=None):
           import os, requests
           token = os.environ.get(self.AUTH_ENV_KEY, "")
           if not token: return []
           actor = src_cfg["actor_id"]
           input_data = src_cfg.get("input", {})
           # Synchronous actor run — for async, use .../runs instead
           r = requests.post(
               f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items",
               params={"token": token}, json=input_data, timeout=300,
           )
           if r.status_code != 200:
               self.log(f"apify {actor}: {r.status_code}"); return []
           # Map Apify output fields → ScrapedItem (per-actor mapping; check their schema)
           return [
               ScrapedItem(source=f"apify:{actor}", title=d.get("title") or d.get("text", "")[:140],
                           url=d.get("url") or d.get("postUrl"), ...)
               for d in r.json()
           ]
   ```
3. Add `from . import apify_actor` in `contentops/scrapers/__init__.py`
4. In `niches.yaml`:
   ```yaml
   sources:
     - type: apify
       actor_id: apify/tiktok-scraper
       input:
         hashtags: ["anthropic", "claudecode"]
         resultsPerPage: 30
   ```
5. Dashboard auto-shows the new type. Set `APIFY_API_TOKEN` in `.env`.

No changes to scheduler or dispatcher. That's the architecture paying back.

## Integration with Wan2GP (video-generation microservice)

Follow the same microservice pattern we use for Daena TTS (`services/daena_tts/server.py`):

```
D:/Ideas/contentops-core/services/wan2gp/
├── .venv/                  # isolated venv with their torch 2.10 + cu130
├── wan2gp/                 # git clone https://github.com/deepbeepmeep/Wan2GP
└── server.py               # thin Flask wrapper: POST /generate → MP4 bytes
```

Why isolated: Wan2GP pins torch 2.7-2.10, we run torch 2.11+cu128 in the main pipeline.

`ltx_render.py` becomes tier-aware:
```python
# Tier 0: Wan2GP microservice (Wan 2.2 / Hunyuan / Flux / Qwen Image / LTX-2)
if os.environ.get("WAN2GP_URL"):
    r = requests.post(f"{WAN2GP_URL}/generate",
                      json={"model": "wan2.2", "prompt": prompt, ...}, timeout=300)
    if r.ok: return write_mp4(r.content, out_path)
# Tier 1: local LTX (the current path)
return local_ltx_generate(prompt, out_path, ...)
```

Operator toggles with `WAN2GP_URL` env. When service is running, all video-gen routes through it. Multiple models selectable per-beat via `model` field.

## Contract with other skills

- **Consumes:** niches.yaml, .env keys for authenticated plugins
- **Produces:** `data/viral_queue/*.json` files + db `items` rows
- **Called by:** dashboard (`/api/scheduler/*`), manual ad-hoc tests
- **Calls:** `contentops.viral` for scoring, `contentops.db.insert_items` for dedup, per-platform APIs / yt-dlp
- **Never:** raises uncaught exceptions (they'd take down the daemon); rate-violates an origin; skips dedup
