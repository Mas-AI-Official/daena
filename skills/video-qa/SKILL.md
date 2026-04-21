---
name: video-qa
description: "Post-render QA agent for short-form vertical videos. Verifies layout (avatar/text non-overlap), audio presence + LUFS + silence ratio, captions readable, video spec (resolution/fps/duration), extracts sample frames for human review. Pairs with edit-choreography (consumes edit_plan.json regions) and contentops-director (gates videos before approval queue). Run AFTER every render."
metadata:
  tags: video, qa, quality-assurance, ffmpeg, ffprobe, layout-verification, audio-loudness, captions, contentops, daena
---

# Video QA Skill

Deterministic post-render checks. Every video produced by ContentOps / video-production must pass these gates BEFORE it reaches the approval queue. Failures route back to the choreography stage with a structured reason.

## When to invoke

- Immediately after any `npx remotion render` or FFmpeg-based mux
- Before `POST /api/render-queue/jobs/:id/approve`
- Before `POST /api/dashboard/approvals/:id/approve`
- Before any social publisher (TikTok / IG / YT)

## Required inputs

```
video_path:   Path to the rendered .mp4
script_json:  scriptwriting-shortform output (for caption text + duration target)
edit_plan:    edit-choreography output (for shot regions + caption style)
layout_spec:  optional — lets the QA know where avatar / captions are EXPECTED
```

## Checks performed

### 1. Spec checks (deterministic — ffprobe)

| Check | Pass criteria |
|---|---|
| Video codec | `h264` |
| Audio codec | `aac` (presence required — fail if no audio stream) |
| Resolution | matches target (1080x1920 for short-form vertical) |
| Frame rate | 30 fps ±0.5 |
| Duration | within ±0.5s of `script.meta.duration_s` |
| Bitrate | video ≥ 1 Mbps |

### 2. Audio quality (ffmpeg-based)

| Check | Pass criteria |
|---|---|
| Stream present | yes |
| Mean LUFS | between -20 and -12 (TikTok/Reels safe range) |
| True peak | ≤ -1 dBTP |
| Silence ratio | < 5% of duration (gaps allowed; full silence = TTS failed) |
| Audio duration vs video duration | within ±0.3s |

### 3. Layout / overlap (PIL frame analysis)

Sample 5 frames at 5%, 25%, 50%, 75%, 95% of duration. For each:

| Check | Pass criteria |
|---|---|
| Avatar region non-empty | the rect declared in `layout_spec.avatar_bbox` has variance > 200 (not flat color) |
| Caption region non-empty | text-region rect has variance > 800 (text is rendering) |
| **Avatar / caption non-overlap** | IoU between `avatar_bbox` and `caption_bbox` < 0.05 |
| Caption contrast | text region mean luminance vs surrounding bg differs by ≥ 60 (Lab L*) |
| No solid-black blank | < 80% of frame at luminance < 20 (catches "blank page" failures) |

### 4. Caption legibility

| Check | Pass criteria |
|---|---|
| Caption inside TikTok safe zone | bbox top ≥ 270px AND bbox bottom ≤ 1920-340 |
| Font size sufficient | inferred glyph height ≥ 56px (1080x1920) |
| No clipping | bbox right < 1080 - 40 AND bbox left > 40 |

### 5. Persona consistency (optional — if `face_ref` provided)

| Check | Pass criteria |
|---|---|
| Detected avatar matches persona | cosine sim > 0.7 against persona face embedding |

## Output schema (`qa_report.json`)

```json
{
  "video": "path/to/file.mp4",
  "verdict": "PASS|FAIL|WARN",
  "score": 0.92,
  "checks": {
    "spec.codec_video":  {"status": "PASS", "value": "h264"},
    "spec.codec_audio":  {"status": "PASS", "value": "aac"},
    "spec.resolution":   {"status": "PASS", "value": "1080x1920"},
    "spec.duration":     {"status": "PASS", "value": 30.00, "target": 30.0},
    "audio.lufs":        {"status": "PASS", "value": -16.4},
    "audio.silence_pct": {"status": "PASS", "value": 0.8},
    "layout.overlap_iou":{"status": "FAIL", "value": 0.31, "threshold": 0.05,
                          "frames": ["t=15s", "t=22s"], "remediation": "shrink avatar to ≤30% width OR move caption to upper third"},
    "layout.blank_pct":  {"status": "PASS", "value": 0.42},
    "caption.safe_zone": {"status": "PASS", "value": true},
    "persona.match":     {"status": "SKIP", "reason": "no face_ref provided"}
  },
  "sample_frames": ["qa/frames/t005.jpg", "qa/frames/t025.jpg", "qa/frames/t050.jpg", "qa/frames/t075.jpg", "qa/frames/t095.jpg"],
  "audio_waveform": "qa/waveform.png",
  "remediation_summary": [
    "Shrink avatar bbox to bottom-right corner ≤ 30% width — currently overlapping captions on 2 of 5 sample frames"
  ]
}
```

## Verdict rules

- `PASS` — all checks PASS (warnings allowed)
- `WARN` — non-blocking issues (e.g., LUFS slightly outside ideal range, but within tolerance)
- `FAIL` — any of: missing audio, codec wrong, resolution wrong, layout overlap > 0.05, blank > 80%, silence > 5%

A `FAIL` BLOCKS publication. A `WARN` proceeds with note logged.

## Integration contract

- Called by `contentops-director` after every render
- Failed verdicts feed back to `edit-choreography` with the remediation text in the `feedback` field of the next iteration
- Sample frames + waveform get persisted to `data/outputs/<batch>/qa/<slug>/` for human spot-check

## Implementation reference

See `scripts/qa-video.py` (consumed by render queue post-stage hook). The Python is self-contained — only deps are `ffmpeg`, `ffprobe`, `pillow`, `numpy`. Run standalone:

```bash
python scripts/qa-video.py video.mp4 --script script.json --edit-plan edit_plan.json --out qa/
```

## Negative space — what this skill does NOT do

- Speech-to-text round-trip (would need Whisper — separate skill)
- Sentiment analysis on audio
- Brand-color verification (delegated to `brand-voice` skill)
- Engagement prediction (delegated to `contentops-director` learning loop)

Keep this skill DETERMINISTIC. Add new probabilistic checks behind a `--ml` flag, never as default.
