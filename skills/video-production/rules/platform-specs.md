# Platform-Specific Video Requirements

## TikTok
| Spec | Value |
|---|---|
| Resolution | 1080x1920 (9:16 portrait) |
| Frame rate | 30fps |
| Duration | 15s - 10min (optimal: 30-60s) |
| File size | < 287MB |
| Format | MP4 (H.264) |
| Audio | AAC, 192kbps |
| Captions | Always on, word-by-word highlight |
| Hook | First 1-2 seconds must grab |
| Hashtags | 3-5 relevant, trending first |

## YouTube Shorts
| Spec | Value |
|---|---|
| Resolution | 1080x1920 (9:16 portrait) |
| Frame rate | 30fps |
| Duration | 15-60 seconds |
| File size | < 2GB |
| Format | MP4 (H.264) |
| Audio | AAC, 192kbps |
| Captions | Burn in (no YouTube auto-caption control for Shorts) |

## YouTube (Long-Form)
| Spec | Value |
|---|---|
| Resolution | 1920x1080 (16:9 landscape), 4K optional |
| Frame rate | 30fps (cinematic: 24fps) |
| Duration | 8-60 minutes (optimal: 10-20 min) |
| File size | < 256GB |
| Format | MP4 (H.264 or H.265 for 4K) |
| Audio | AAC, 320kbps stereo |
| Chapters | Required (minimum 3) |
| End screen | Last 20 seconds reserved |
| Thumbnail | 1280x720, < 2MB, JPEG/PNG |
| Description | First 2 lines = hook (shown in search) |

## Instagram Reels
| Spec | Value |
|---|---|
| Resolution | 1080x1920 (9:16 portrait) |
| Frame rate | 30fps |
| Duration | 15-90 seconds (optimal: 30-45s) |
| File size | < 250MB |
| Format | MP4 (H.264) |
| Audio | AAC, 192kbps |
| Cover image | 1080x1920, custom (not just first frame) |

## LinkedIn Video
| Spec | Value |
|---|---|
| Resolution | 1920x1080 (16:9) or 1080x1080 (1:1) |
| Frame rate | 30fps |
| Duration | 30s - 10min (optimal: 60-120s) |
| File size | < 5GB |
| Format | MP4 (H.264) |
| Audio | AAC, 192kbps |
| Captions | Always on (most watch muted) |
| Tone | Professional, insight-driven |

## Cross-Platform Export Commands

```bash
# TikTok / Shorts / Reels (9:16 portrait, 1080x1920)
ffmpeg -i input.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:-1:-1:black" \
  -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k -movflags +faststart output_portrait.mp4

# YouTube long-form (16:9 landscape, 1920x1080)
ffmpeg -i input.mp4 -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1:black" \
  -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 320k -movflags +faststart output_landscape.mp4

# LinkedIn square (1:1, 1080x1080)
ffmpeg -i input.mp4 -vf "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:-1:-1:black" \
  -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k -movflags +faststart output_square.mp4

# Trim to platform max duration
ffmpeg -i input.mp4 -t 60 -c copy output_trimmed.mp4
```

## Audio Loudness Standards
- YouTube: -14 LUFS (integrated), -1 dBTP (true peak)
- TikTok/Reels: -16 LUFS recommended
- LinkedIn: -16 LUFS recommended
- Background music: 8-12% volume during speech, 20-30% during visual-only
