---
name: social-media-browser-puppeteer
description: Post, reply, and monitor social media platforms (X/Twitter, Instagram, LinkedIn, TikTok, YouTube) through persistent Chromium profiles driven by Playwright + Chrome MCP. Bypasses the API-approval walls (which take weeks for Meta/TikTok) by treating each platform as a web UI we have a logged-in browser for. Use when the operator wants Claude to publish content or surface DMs/comments without locking behind official app reviews.
---

# Browser-Puppeteer Social Media Architecture

## The core insight

Every social platform has a first-party web app. If you have a browser signed into the account, you can do anything a human can — post, reply, DM, follow, react. APIs are gatekeepers for programmatic access; browsers are not.

The 2026 social-automation stack (Postiz, Buffer, Hootsuite internally) already works this way under the hood for platforms where the API is too restricted: they drive headless Chromium with the user's stored session.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Claude Code (orchestrator)                   │
│                                                                 │
│   Reads signals → decides "post this", "reply to that" →       │
│   invokes the right skill → verifies output                     │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
   │   Playwright  │   │   Chrome MCP  │   │   REST API    │
   │   (headless,  │   │   (visible,   │   │   (where      │
   │   scheduled)  │   │    interact.) │   │    available) │
   └───────────────┘   └───────────────┘   └───────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
   ┌──────────────────────────────────────────────────────────┐
   │        Per-platform persistent Chromium user-data dir    │
   │                                                          │
   │   x/          → cookies, localStorage for x.com login    │
   │   instagram/  → cookies, etc. for instagram.com          │
   │   linkedin/   → cookies, etc.                            │
   │   tiktok/     → cookies, etc.                            │
   │   youtube-studio/ → cookies for studio.youtube.com       │
   └──────────────────────────────────────────────────────────┘
```

### Why three execution modes

- **Playwright headless**: scheduled posts, batch DM pulls, comment scraping. No UI overhead. Runs every N minutes.
- **Chrome MCP (visible browser)**: when a human-in-loop needs to approve a reply. Claude drafts in the DOM, you hit "send". Also: MFA flows, account-recovery prompts, captcha fallback.
- **REST API**: for platforms where we DO have a token (X has OAuth1.0a keys in the .env; YouTube Data v3 is free). Use first when it exists — it's faster and less ban-risky than browser actions.

## The one-time setup flow

```
1. Operator creates per-platform user-data dirs:
     D:/Ideas/contentops-core/browser-profiles/x/
     D:/Ideas/contentops-core/browser-profiles/instagram/
     ...

2. Operator runs `ops login <platform>` once per platform.
   This launches a HEADFUL Chromium pointing at the platform's login page with
   --user-data-dir=<profile>. Operator signs in normally (MFA included). When
   the cookie is saved, close the window.

3. From then on: Claude Code runs Playwright with launch_persistent_context()
   pointing at that same user-data dir. Session resumes, no re-login needed.
```

## File layout

```
contentops-core/
├── browser-profiles/            # persistent Chromium user-data dirs (gitignored)
│   ├── x/
│   ├── instagram/
│   ├── linkedin/
│   ├── tiktok/
│   └── youtube-studio/
├── contentops/
│   ├── social/
│   │   ├── __init__.py
│   │   ├── session.py           # launch_persistent_context helpers
│   │   ├── x.py                 # X/Twitter: post, reply, quote, DM, feed
│   │   ├── instagram.py         # IG: post reel, reply, DM, story
│   │   ├── linkedin.py          # LinkedIn: post, react, DM, connection req
│   │   ├── tiktok.py            # TikTok: upload, reply, DM
│   │   ├── youtube.py           # YouTube Studio: upload short, reply, pin
│   │   └── inbox.py             # unified DM/comment inbox across platforms
│   └── video_render.py          # (existing pipeline)
└── scripts/
    ├── social-login.ps1         # guided login runner
    └── social-publish.ps1       # CLI: publish a rendered MP4 to N platforms
```

## Core module: `contentops/social/session.py`

```python
"""Persistent-session Playwright helpers for each platform."""
from pathlib import Path
from playwright.sync_api import sync_playwright, BrowserContext

PROFILES_ROOT = Path("D:/Ideas/contentops-core/browser-profiles")

def ctx_for(platform: str, headless: bool = True) -> BrowserContext:
    """Open a persistent Chromium context for the given platform.

    Uses the SAME user-data directory every time, so cookies/localStorage persist
    across runs. Operator signs in ONCE (headful) and Claude reuses the session.
    """
    profile = PROFILES_ROOT / platform
    profile.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(profile),
        headless=headless,
        viewport={"width": 430, "height": 932},    # iPhone-ish vertical for mobile sites
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
        ),
        args=["--disable-blink-features=AutomationControlled"],  # hide headless fingerprint
    )
    # Store the playwright handle so caller can close both
    ctx._pw_handle = pw
    return ctx
```

## Platform module skeleton: `contentops/social/x.py`

```python
from .session import ctx_for
from pathlib import Path

def post(text: str, video_path: Path | None = None, headless: bool = True) -> dict:
    """Publish a tweet (with optional video attachment) via x.com web.
    Returns: {"tweet_id": str, "url": str} on success."""
    ctx = ctx_for("x", headless=headless)
    try:
        page = ctx.new_page()
        page.goto("https://x.com/compose/post", wait_until="networkidle")
        page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=15000)
        page.click('[data-testid="tweetTextarea_0"]')
        page.keyboard.type(text, delay=15)  # human-ish typing speed
        if video_path:
            with page.expect_file_chooser() as fc:
                page.click('[data-testid="fileInput"]')
            fc.value.set_files(str(video_path))
            # Wait for upload progress bar to disappear
            page.wait_for_selector('[data-testid="progressBar"]', state="detached", timeout=120000)
        page.click('[data-testid="tweetButtonInline"]')
        page.wait_for_url(r"^https://x\.com/\w+/status/\d+$", timeout=30000)
        return {"tweet_id": page.url.rsplit("/", 1)[-1], "url": page.url}
    finally:
        ctx.close()
        ctx._pw_handle.stop()


def pull_new_mentions(since_id: str | None = None) -> list[dict]:
    """Scrape the Notifications tab for unseen @mentions. Returns list of
    {"id", "author", "text", "timestamp", "url"} dicts."""
    ctx = ctx_for("x", headless=True)
    try:
        page = ctx.new_page()
        page.goto("https://x.com/notifications/mentions", wait_until="networkidle")
        # Scroll, extract data-testid="cellInnerDiv" blocks, parse each
        # ... (implementation omitted for brevity; follows same pattern)
        return []
    finally:
        ctx.close()
        ctx._pw_handle.stop()
```

Same shape for `instagram.py`, `linkedin.py`, `tiktok.py`. Each has `post()`, `pull_new_comments()`, `pull_new_dms()`, `reply()`.

## Autonomy gradient (maps to CLAUDE.md)

Per platform, per action, pick one of:

| Level | Behavior | Example |
|---|---|---|
| 🟢 Auto | Claude executes without prompt | Posting a rendered video at a pre-approved slot |
| 🟡 Brief pause | Claude states intent, waits 10s, then proceeds | Replying to a positive comment |
| 🟠 Approve | Claude drafts, waits for explicit "go" | Replying to a critical comment; quote-tweet |
| 🔴 Never | Claude declines the action | Sending a financial offer in DMs; following new accounts |

Recommended starting policy (conservative, earns trust):

| Action | X | IG | LinkedIn | TikTok | YouTube |
|---|---|---|---|---|---|
| Schedule a post | 🟡 | 🟡 | 🟡 | 🟠 | 🟡 |
| Reply to positive comment | 🟡 | 🟡 | 🟡 | 🟠 | 🟡 |
| Reply to critical comment | 🟠 | 🟠 | 🟠 | 🟠 | 🟠 |
| Send a DM | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| Follow/unfollow | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |

After 2 weeks with 0 drafts rejected, graduate 🟡 → 🟢.

## Interaction notifications

Claude doesn't need a push-notification system — we use **polling + Monitor tool**:

```bash
# Background monitor that watches for new mentions across platforms every 5 min,
# emits one line per new interaction. Each line becomes a Claude Code notification.
Monitor({
  description: "social inbox",
  persistent: true,
  command: "while true; do python -m contentops.social.inbox since_last_seen; sleep 300; done
            | grep --line-buffered '^[NEW]'"
})
```

The inbox module writes the "last seen" per platform to `var/social_cursor.json` so we don't duplicate-fire on the same comment.

## Anti-ban hygiene (critical)

1. **Human-ish typing speed**: 15-30ms per keystroke, random ±5ms. Never 0ms (instant paste).
2. **Random delays**: between actions, `random.uniform(2, 8)` seconds. Don't post 10 things in 10 seconds.
3. **Mobile user-agent**: platforms are WAY more tolerant of "unusual behavior" from mobile than desktop. Use the iPhone Safari UA string (in `session.py` above).
4. **Respect rate limits**: X = 50 tweets/day max for automation. IG = 3 posts/hour max. LinkedIn = 1 post/day is safest.
5. **Session rotation**: if a platform flags the session (CAPTCHA, weird login email), immediately stop and alert the operator. Never auto-solve a CAPTCHA.
6. **No follow-unfollow**: this is the #1 auto-ban trigger across all platforms.

## Why Chrome MCP for the human-in-loop path

The `claude-in-chrome` MCP (tools named `mcp__Claude_in_Chrome__*`) is the visible-browser alternative. When a reply needs your eyes on it:

1. Claude opens the X reply composer via `mcp__Claude_in_Chrome__navigate`
2. Claude drafts the reply via `mcp__Claude_in_Chrome__form_input`
3. Waits for the operator to hit "send" (doesn't click it itself)
4. Screenshots the posted result for the log

Pair with Playwright (scheduled, headless) for throughput + Chrome MCP (interactive) for sensitive cases.

## Integration with news-to-video

When a rendered video is ready:

```python
from contentops.video_render import render_script
from contentops.social.x import post as x_post
from contentops.social.instagram import post as ig_post
from pathlib import Path

result = render_script(script_id=15)
video_path = Path(result["render_path"])
caption = result["notes"]  # or pull from script metadata

# Publish order: X first (fastest feedback), then IG, then LinkedIn
published = []
published.append(x_post(text=caption[:280], video_path=video_path))
# Wait 10 min for X metrics to establish baseline
time.sleep(600)
published.append(ig_post(text=caption[:2200], video_path=video_path))
```

## Quality gate before publish

Same as news-to-video quality gate, plus:

- [ ] Video duration is platform-compliant (X: <140s, IG Reels: <90s, TikTok: <10min, Shorts: <60s)
- [ ] Aspect is 9:16 for Reels/TikTok/Shorts, or 16:9 for YouTube standard
- [ ] Captions aren't clipped by platform UI safe zones (top 270px / bottom 340px on Reels)
- [ ] First 3s has the hook (platform algorithms watch this window)
- [ ] No music copyrighted beyond fair use

If any check fails, re-render before publishing. Never let a bad publish stand — it becomes the algorithm's baseline for your account.

## Security / account hygiene

- User-data dirs live outside git (add `browser-profiles/` to .gitignore)
- Never log cookies or tokens. Log only public URLs + IDs.
- If an account flags (unusual login location warning), **stop all automation** for 48h and have the operator log in manually to reset trust score.
- Rotate the mobile UA string every 60 days (platforms fingerprint UA).

## Contract with other skills

- **Consumes:** rendered MP4 + caption text + scheduling metadata
- **Calls:** `brand-voice:brand-voice-enforcement` on the caption before publish, `universal-shortform-director` for the quality gate
- **Produces:** platform post URLs, interaction-event stream, performance metrics (scraped from analytics tabs)
- **Never:** publishes without quality-gate pass; fights a CAPTCHA; follows/unfollows autonomously; sends DMs autonomously
