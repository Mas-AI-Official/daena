# Content Scraping & Influencer Monitoring

How to find, scrape, and transform trending content into our own videos.
No paid APIs needed for 80%+ of monitoring -- yt-dlp + RSS feeds handle everything.

## Universal Scraping Strategy

yt-dlp for YouTube, RSS for everything else. Zero API keys for 90%+ of monitoring.

### YouTube Channel Monitoring (yt-dlp -- FREE, no API key)

**YouTube RSS feeds are DEAD as of 2026** (return 404/500 globally).
Use yt-dlp `--flat-playlist` instead -- handles anti-bot, consent, and all edge cases.

```bash
# List 5 latest videos from any channel (metadata only, no download)
yt-dlp --dump-json --flat-playlist --playlist-end 5 "https://www.youtube.com/@Fireship/videos"
```

The channel_id approach also works via yt-dlp:
```bash
yt-dlp --dump-json --flat-playlist --playlist-end 5 "https://www.youtube.com/channel/CHANNEL_ID/videos"
```

To find channel_id: view page source on a channel page, search for "channelId".

**Key AI/Tech influencers to monitor:**

```python
INFLUENCER_FEEDS = {
    # AI/Tech YouTube (high priority)
    "Fireship": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsBjURrPoezykLs9EqgamOA",
    "Two Minute Papers": "https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYPyITQ-7l4upoX8nvctg",
    "Yannic Kilcher": "https://www.youtube.com/feeds/videos.xml?channel_id=UCZHmQk67mSJgfCCTn7xBfew",
    "Matt Wolfe": "https://www.youtube.com/feeds/videos.xml?channel_id=UCJMt_AEarUFhcgFOWVNG6Uw",
    "AI Explained": "https://www.youtube.com/feeds/videos.xml?channel_id=UCNJ1Ymd5yFuUPtn21xtRbbw",
    "TheAIGRID": "https://www.youtube.com/feeds/videos.xml?channel_id=UCJHnlEMOCu0Oh8Tuk-5RSqA",
    "AI Jason": "https://www.youtube.com/feeds/videos.xml?channel_id=UCbltSCg18hp8F3bJiQi5nuQ",
    "NetworkChuck": "https://www.youtube.com/feeds/videos.xml?channel_id=UC9x0AN7BWHpCDHSm9NiJFJQ",
    "Linus Tech Tips": "https://www.youtube.com/feeds/videos.xml?channel_id=UCXuqSBlHAE6Xw-yeJA0Tunw",
    "Marques Brownlee": "https://www.youtube.com/feeds/videos.xml?channel_id=UCBJycsmduvYEL83R_U4JriQ",

    # Startup / Business YouTube
    "Y Combinator": "https://www.youtube.com/feeds/videos.xml?channel_id=UCcefcZRL2oaA_uBNeo5UOWg",
    "a]16z": "https://www.youtube.com/feeds/videos.xml?channel_id=UCNAxymHlEeeqMcFF2MD_aJw",
}
```

### Tech News RSS (FREE)

```python
NEWS_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica AI": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "Hacker News Best": "https://hnrss.org/best?points=100",
    "Hacker News Frontpage": "https://hnrss.org/frontpage",
    "MIT Tech Review AI": "https://www.technologyreview.com/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "The Information": "https://www.theinformation.com/feed",
    "ArXiv CS.AI": "http://export.arxiv.org/rss/cs.AI",
    "ArXiv CS.CL": "http://export.arxiv.org/rss/cs.CL",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Anthropic News": "https://www.anthropic.com/news/rss.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
}
```

### Reddit RSS (FREE, no API needed)

```python
REDDIT_FEEDS = {
    "r/artificial": "https://www.reddit.com/r/artificial/.rss",
    "r/MachineLearning": "https://www.reddit.com/r/MachineLearning/.rss",
    "r/LocalLLaMA": "https://www.reddit.com/r/LocalLLaMA/.rss",
    "r/singularity": "https://www.reddit.com/r/singularity/.rss",
    "r/ChatGPT": "https://www.reddit.com/r/ChatGPT/.rss",
    "r/ClaudeAI": "https://www.reddit.com/r/ClaudeAI/.rss",
    "r/StableDiffusion": "https://www.reddit.com/r/StableDiffusion/.rss",
    "r/comfyui": "https://www.reddit.com/r/comfyui/.rss",
}
```

## Scraping Code (already wired into ContentOps-Core)

All scraping is implemented at `src/contentops/ingestion/collector.py` and
`src/contentops/ingestion/influencer_monitor.py`. Key functions:

```python
# YouTube channel monitoring (yt-dlp, not RSS)
from contentops.ingestion.collector import collect_youtube_rss  # uses yt-dlp internally

# News + Reddit RSS (feedparser)
from contentops.ingestion.collector import collect_rss, collect_reddit_rss

# All sources in one call
from contentops.ingestion.collector import collect_all_rss

# YouTube transcript + metadata
from contentops.ingestion.collector import extract_youtube_transcript, get_youtube_metadata

# Article text extraction
from contentops.ingestion.collector import scrape_article

# Influencer react pipeline
from contentops.ingestion.influencer_monitor import (
    check_for_new_videos,      # Poll for new influencer videos
    enrich_detected_video,     # Get metadata + transcript
    react_to_new_videos,       # Full detect → enrich → analyze pipeline
    load_influencer_feeds,     # Load from data/influencer_feeds.json
)

# Orchestrator entry points
from contentops.pipeline.orchestrator import (
    collect_all_signals,              # Aggregate all free sources
    run_influencer_react_pipeline,    # End-to-end react pipeline
)
```

### News + Reddit RSS (feedparser — still works)

```python
import feedparser

def scrape_news_feeds(feed_dict: dict, hours_back: int = 24) -> list[dict]:
    """Scrape RSS feeds. Works for news, blogs, Reddit. NOT YouTube (use yt-dlp)."""
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)
    items = []
    for name, url in feed_dict.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc) if hasattr(entry, 'published_parsed') and entry.published_parsed else datetime.now(tz=timezone.utc)
                if pub > cutoff:
                    items.append({"title": entry.get('title', ''), "url": entry.get('link', ''), "source": name, "published": pub})
        except Exception:
            continue
    return sorted(items, key=lambda x: x["published"], reverse=True)
```

## YouTube Transcript Scraping (yt-dlp -- already installed)

When an influencer drops a video, grab the transcript immediately:

```python
import subprocess
import json

def get_youtube_transcript(video_url: str) -> str:
    """Extract transcript from a YouTube video using yt-dlp."""
    try:
        # Get auto-generated subtitles
        result = subprocess.run([
            "yt-dlp",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--skip-download",
            "--sub-format", "json3",
            "-o", "%(id)s",
            video_url
        ], capture_output=True, text=True, timeout=60)

        # Read the subtitle file
        video_id = video_url.split("v=")[-1].split("&")[0]
        sub_file = f"{video_id}.en.json3"

        with open(sub_file) as f:
            data = json.load(f)

        # Extract text from subtitle events
        transcript = " ".join(
            event.get("segs", [{}])[0].get("utf8", "")
            for event in data.get("events", [])
            if event.get("segs")
        ).strip()

        return transcript
    except Exception as e:
        return f"Transcript extraction failed: {e}"


def get_video_metadata(video_url: str) -> dict:
    """Get full video metadata without downloading the video."""
    result = subprocess.run([
        "yt-dlp",
        "--dump-json",
        "--no-download",
        video_url
    ], capture_output=True, text=True, timeout=30)

    if result.returncode == 0:
        return json.loads(result.stdout)
    return {}
```

## Web Article Scraping (trafilatura + beautifulsoup -- already installed)

```python
import trafilatura
import httpx

def scrape_article(url: str) -> dict:
    """Extract clean article text from any URL."""
    try:
        response = httpx.get(url, follow_redirects=True, timeout=15)
        text = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=True,
            output_format="txt"
        )
        metadata = trafilatura.extract(
            response.text,
            output_format="json",
            include_comments=False
        )
        return {
            "text": text or "",
            "metadata": json.loads(metadata) if metadata else {},
            "url": url
        }
    except Exception:
        return {"text": "", "metadata": {}, "url": url}
```

## Influencer Monitoring Pipeline

### The React-and-Produce Workflow

When an influencer drops a video:

```
1. RSS DETECT     -> YouTube feed shows new video from tracked influencer
2. METADATA GRAB  -> yt-dlp --dump-json (title, views, description, tags)
3. TRANSCRIPT     -> yt-dlp auto-subs (full spoken text)
4. ANALYZE        -> LLM extracts: topic, key claims, data points, angle
5. DIFFERENTIATE  -> LLM generates OUR unique angle (not copy, differentiate)
6. PRODUCE        -> Feed into our voice-over-to-scene-sync pipeline
7. PUBLISH        -> Release within 2-4 hours of influencer's video
```

### Differentiation Strategy (NEVER copy, always add value)

When reacting to influencer content, the LLM must answer:

```
1. What did they MISS? (gaps in their explanation)
2. What can we ADD? (our expertise, Daena's perspective)
3. What's the CONTRARIAN take? (where we respectfully disagree)
4. What's the PRACTICAL angle? (how-to vs. their what-is)
5. What's the DEEPER context? (history, implications they skipped)
```

**Rules:**
- NEVER plagiarize -- always cite the original creator
- ALWAYS add unique value (at least 40% new content)
- Use their video as a STARTING POINT, not the whole script
- Credit them: "As [Creator] pointed out in their latest video..."
- Our Daena persona adds executive/founder perspective they can't

### Speed-to-Market Protocol

| Time After Drop | Action |
|---|---|
| 0-15 min | RSS detects new video, scrape metadata + transcript |
| 15-30 min | LLM analyzes content, finds our angle, writes dual-script |
| 30-60 min | TTS generates voice, beat map created, scenes planned |
| 60-120 min | SadTalker + Remotion + FFmpeg produce the video |
| 120-180 min | QA review, captions, final composite |
| 180-240 min | Published to all platforms |

**Target: 4 hours from influencer drop to our video live.**

### Influencer Tracking Database

```json
{
  "influencers": [
    {
      "name": "Fireship",
      "channel_id": "UCsBjURrPoezykLs9EqgamOA",
      "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsBjURrPoezykLs9EqgamOA",
      "niche": "dev_tools_ai",
      "style": "fast_paced_humor",
      "avg_views": 1500000,
      "react_priority": "high",
      "differentiation": "We add enterprise/governance angle they skip"
    },
    {
      "name": "Matt Wolfe",
      "channel_id": "UCJMt_AEarUFhcgFOWVNG6Uw",
      "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCJMt_AEarUFhcgFOWVNG6Uw",
      "niche": "ai_tools_news",
      "style": "weekly_roundup",
      "avg_views": 200000,
      "react_priority": "medium",
      "differentiation": "We go deeper on fewer tools, show actual use"
    }
  ]
}
```

## Polling Schedule

```python
# Run every 15 minutes for high-priority influencers
# Run every hour for news feeds
# Run every 4 hours for Reddit/blog feeds

POLL_SCHEDULE = {
    "influencer_youtube": {"interval_min": 15, "feeds": INFLUENCER_FEEDS},
    "tech_news": {"interval_min": 60, "feeds": NEWS_FEEDS},
    "reddit_forums": {"interval_min": 240, "feeds": REDDIT_FEEDS},
}
```

## What ContentOps Already Has vs. What's Missing

| Feature | Has? | Library | Gap |
|---|---|---|---|
| RSS parsing | YES | feedparser | Needs more feeds, influencer-specific tracking |
| YouTube metadata | YES | YouTube API | Switch to yt-dlp (no API key needed) |
| YouTube transcripts | NO | yt-dlp (installed) | Wire into pipeline |
| Article extraction | NO | trafilatura (installed) | Wire into pipeline |
| HTML scraping | NO | beautifulsoup4 (installed) | Wire into pipeline |
| Reddit monitoring | YES | httpx + OAuth | Add RSS fallback (no auth needed) |
| Influencer tracking | PARTIAL | TrackedAccount model exists | Need RSS feeds + auto-react pipeline |
| Speed-to-market | NO | N/A | Need the 4-hour react pipeline |
| Cross-platform dedup | NO | N/A | Hardcoded at 0.3, needs clustering |

## Implementation Priority

1. **Wire yt-dlp transcript extraction** into the pipeline (30 min -- library already installed)
2. **Add 20+ influencer YouTube RSS feeds** to feed collection (15 min)
3. **Wire trafilatura** for article scraping (15 min)
4. **Build the react-and-produce trigger** that detects new influencer videos and kicks off production (2 hours)
5. **Add RSS-based Reddit monitoring** as API-free fallback (15 min)
6. **Build cross-platform deduplication** to replace the 0.3 hardcode (1 hour)
