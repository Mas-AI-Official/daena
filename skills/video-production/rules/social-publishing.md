# Social Media Publishing via MCP

How Claude publishes content to each platform using the available MCP tools.
ContentOps prepares packages at `data/publish_queue/{post_id}/{platform}/`.
Claude reads the manifest and uses Chrome MCP to publish.

## Publishing Flow

```
1. ContentOps prepares package → data/publish_queue/{post_id}/{platform}/manifest.json
2. Claude reads manifest (title, caption, hashtags, video_path, platform)
3. Claude uses Chrome MCP to navigate → upload → fill fields → publish
4. Claude calls mark_published() to update status
```

## Platform-Specific Publishing

### YouTube (via Chrome MCP)

```
1. Navigate to https://studio.youtube.com
2. Click "CREATE" → "Upload videos"
3. Use file_upload to upload the video file
4. Fill title, description, tags from manifest
5. Set visibility (Public / Unlisted / Scheduled)
6. Upload thumbnail via file_upload
7. Click through Next → Next → Next → Publish
```

Key: YouTube Studio is already logged in via Google account.

### TikTok (via Chrome MCP)

```
1. Navigate to https://www.tiktok.com/upload
2. Use file_upload on the upload area
3. Fill caption from manifest.json caption.txt
4. Add hashtags (already in caption)
5. Set cover image if thumbnail provided
6. Click "Post" (or "Schedule" if scheduled_at is set)
```

### Instagram Reels (via Chrome MCP)

```
1. Navigate to https://www.instagram.com
2. Click "+" (new post) → "Reel"
3. Use file_upload to upload video
4. Fill caption from manifest
5. Add cover image
6. Click "Share"
```

Note: Instagram web supports Reels upload. Mobile-only features need the app.

### X/Twitter (via Chrome MCP)

```
1. Navigate to https://x.com/compose/post
2. Click media icon, use file_upload for video
3. Type caption (max 280 chars — already truncated in manifest)
4. Click "Post"
```

### LinkedIn (via Chrome MCP)

```
1. Navigate to https://www.linkedin.com
2. Click "Start a post"
3. Click media/video icon, use file_upload
4. Type caption from manifest
5. Click "Post"
```

## Publish Queue Management

```python
from contentops.publishing.platform_publisher import (
    prepare_cross_platform,    # Prepare packages for multiple platforms
    list_publish_queue,        # See what's pending
    mark_published,            # Mark as done after Chrome MCP publishes
)

# Prepare packages for a niche's platforms
packages = prepare_cross_platform(
    post_id="abc123",
    video_path="data/outputs/video.mp4",
    platforms=["tiktok", "youtube", "instagram", "twitter", "linkedin"],
    title="Claude Mythos Explained",
    caption="Here's why Claude Mythos changes everything...",
    hashtags=["ai", "claude", "anthropic", "tech"],
    niche_id="ai_tools",
    social_accounts={
        "youtube": {"handle": "@MAS-AI"},
        "tiktok": {"handle": "@daena_ai"},
        "instagram": {"handle": "@daena_ai"},
        "twitter": {"handle": "@masai_tech"},
        "linkedin": {"handle": "MAS-AI Technologies"},
    },
)

# After publishing via Chrome MCP:
mark_published("abc123", "tiktok", url="https://tiktok.com/@daena_ai/video/123")
```

## Auto vs Manual Publishing

| Mode | Behavior |
|---|---|
| `manual` | Package queued → Claude shows for approval → you say "publish" → Chrome MCP publishes |
| `auto` | Package queued → if qa_score >= threshold → Claude auto-publishes via Chrome MCP |
| `scheduled` | Package queued with scheduled_at → Claude publishes at that time |

**Default is MANUAL** — you review every video before it goes live.
Switch to AUTO only after the pipeline proves reliable.

## Optimal Posting Times (per platform)

| Platform | Best Times (EST) | Best Days |
|---|---|---|
| TikTok | 7-9am, 12-3pm, 7-11pm | Tue, Thu, Fri |
| YouTube | 2-4pm (weekday), 9-11am (weekend) | Thu, Fri, Sat |
| Instagram | 11am-1pm, 7-9pm | Tue, Wed, Fri |
| X/Twitter | 8-10am, 12-1pm | Mon, Wed, Fri |
| LinkedIn | 7-8am, 12pm, 5-6pm | Tue, Wed, Thu |

These are starting points — the learning loop refines per-account based on actual engagement data.
