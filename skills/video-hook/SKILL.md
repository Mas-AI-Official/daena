---
name: video-hook
description: Design the opening 0-3 seconds of a short-form vertical video (TikTok / Reels / Shorts) to stop the scroll. Covers visual hooks (text overlays, pattern interrupts, zoom-ins, match-cuts), audio hooks, and the beat-1 retention architecture. Use when generating or critiquing the first beat of a short-form video — especially when a voice-over hook alone won't survive the algorithm's 1.5-second attention test.
---

# Video-Hook -- stop-the-scroll engineering for short-form vertical video

## When to invoke this skill

- Generating beat_01 (or "hook beat") for a short-form video in the contentops pipeline
- Critiquing a rendered video's opening and the reason for low 3-second retention
- Choosing between hook archetypes when a single script could go multiple ways
- Translating a voice-over hook into a complementary visual hook (they are NOT the same thing)

## The problem this skill solves

Voice-over hooks are audio-only. They work only if the viewer has **sound on**. On 2026 short-form feeds:

- **TikTok**: ~40% of auto-play starts are muted in the first second
- **Instagram Reels**: ~55% muted (due to story-hover overlap)
- **YouTube Shorts**: ~45% muted
- **Overall**: assume ~50% of viewers see beat_01 **with NO AUDIO**

If your hook depends on the voice-over, half your audience bounces at frame 1. The video-hook is the visual layer that retains them **until** the voice hook lands — buying you the first 1.5 seconds of algorithm credit.

## The 7 hook archetypes (pick one per video)

Each has a retention mechanism, a visual pattern, and a production recipe.

### 1. **Text-Cold-Open** (strongest for news / developer / AI content)
   - **Mechanism**: huge text overlay loads before any b-roll — forces a READ
   - **Visual**: 1080x1920 black or solid-color background; hook line in Arial Black ~120px, top-third; optional 2-3 word SECOND line in accent color
   - **Duration**: 0.6-1.0 seconds before transitioning to b-roll
   - **Best for**: data stats, quote drops, contrarian claims, breaking news
   - **Example**: "ANTHROPIC LOST CONTROL" → cut to reporter footage

### 2. **Title-Card-Reveal** (viral-news staple)
   - **Mechanism**: title card + date + source cite establishes credibility fast
   - **Visual**: news-graphic style — source logo, date badge, 8-12 word headline, horizontal bar-chart of relevant stat
   - **Duration**: 1.5-2.5 seconds
   - **Best for**: breaking news, earnings drops, data stories
   - **Example**: "Bleeping Computer · Apr 23 · French Gov Breach" overlaid on red alert bar

### 3. **Pattern-Interrupt** (highest retention lift in 2026 TikTok studies)
   - **Mechanism**: visual impossibility or unexpected match-cut in first 0.5s
   - **Visual**: a visual that makes the viewer think "wait, what?" — reverse zoom from extreme close-up, object falling upward, time-reversed footage
   - **Duration**: 0.3-0.8 seconds
   - **Best for**: comedy, tutorials that subvert expectations, "surprising data" stories
   - **Example**: hands typing code → frame freezes → shatters → cut to hacker silhouette

### 4. **Zoom-Hold** (developer / productivity content)
   - **Mechanism**: slow continuous zoom into a specific detail — viewer's attention locks onto whatever's being zoomed toward
   - **Visual**: Ken Burns-style zoom-in on a UI element, tool icon, or hero-image feature
   - **Duration**: full 2-4s (the hook IS the zoom)
   - **Best for**: product demos, "look closer at this" stories, UI spotlights
   - **Example**: wide shot of a server rack → continuous 3s push-in to a single blinking red LED

### 5. **Negation-Hook** ("you've been doing X wrong")
   - **Mechanism**: text overlay asserts a negative with high contrast — viewer's brain MUST check if it applies
   - **Visual**: crossed-out old practice in red + correct practice in green, revealed sequentially
   - **Duration**: 1.2-1.8 seconds
   - **Best for**: tutorials, meta-commentary, mythbusting
   - **Example**: [RED X] "Most devs use OAuth" → [GREEN CHECK] "Pros use API keys"

### 6. **Countdown-Tease** (list content)
   - **Mechanism**: "Here's what's #1" or "5 → 1" — promise of ordered reveal, creates commitment
   - **Visual**: big numeric "5", "4", "3", "2", "1" rolling down or a "#1: [redacted]" teaser
   - **Duration**: 1.0-1.5 seconds
   - **Best for**: listicles, rankings, "top X" videos
   - **Example**: "#1 AI security breach of 2026" with #1 revealed + rest of list blurred

### 7. **Face-Shock-Reaction** (lifestyle / story content)
   - **Mechanism**: open with a pure emotional facial reaction — human brains pre-attentively parse faces within 100ms
   - **Visual**: Pexels or Wan2GP-generated close-up of a shocked / shocked / joyful / confused face
   - **Duration**: 0.5-1.0 second, then intercut to context
   - **Best for**: story-driven videos, reactions to news, relationship content
   - **Example**: face reacting in shock → cut to "Anthropic confirms unauthorized access"

## The retention architecture — beat_01 is NOT just a hook

A hook alone isn't enough. The first 3 seconds must deliver:

```
0.0-0.5s : VISUAL HOOK        (one of the 7 archetypes above)
0.5-1.5s : VOICE HOOK lands   (the line from the script)
1.5-2.5s : PROMISE            ("In this video I'll show you...")
2.5-3.0s : FIRST VALUE DROP   (tease the juiciest content to come)
```

If the visual hook lands but the voice hook doesn't arrive by 1.5s, you lose muted-video viewers. If the voice hook lands but there's nothing visually to lock them in, you lose attention-drift viewers. Both must play in the same 0-1.5s window.

## Picking the right hook archetype

Pick by **content type + emotional register**:

| If the content is... | Hook archetype | Why |
|---|---|---|
| Breaking news (security, AI, politics) | **Title-Card-Reveal** or **Text-Cold-Open** | Credibility + urgency |
| Data story or stat-heavy | **Text-Cold-Open** with the stat as hero | Stat IS the hook |
| Tutorial / educational | **Zoom-Hold** or **Negation-Hook** | Focus attention on the detail |
| Comedy / absurd | **Pattern-Interrupt** | Subvert expectation |
| Listicle / ranking | **Countdown-Tease** | Creates commitment to watch |
| Story / narrative | **Face-Shock-Reaction** | Emotional entry |
| Developer / AI / devtool | **Text-Cold-Open** or **Zoom-Hold** | Audience is literal, respects data |

## Implementation in contentops pipeline

The hook beat is **beat_01** in `beats.json`. Its duration should be **3.5-7 seconds** (not the typical 6-10s of middle beats) — tight, front-loaded, high density.

### For Text-Cold-Open in video_render.py

Add to `assemble_beat_timed()` between clip normalization and concat: generate a text-overlay intro clip via ffmpeg's `drawtext` filter, prepend it to beat_01.

```python
# Before concat, prepend a 1.0s text-cold-open:
hook_line = script["hook"][:60]  # 60-char cap fits mobile
ffmpeg_args = [
    "ffmpeg", "-y",
    "-f", "lavfi", "-i", "color=black:s=1080x1920:d=1.0:r=30",
    "-vf", (
        f"drawtext=fontfile='C\\:/Windows/Fonts/ariblk.ttf'"
        f":text='{hook_line}'"
        f":fontcolor=white:fontsize=80"
        f":x=(w-text_w)/2:y=(h-text_h)/2"
        f":enable='between(t,0,1.0)'"
    ),
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    str(workdir / "hook_cold_open.mp4"),
]
```

### For Title-Card-Reveal

Use ffmpeg's `drawtext` + `drawbox` filters to layer:
- Background: beat_01 b-roll at 30% opacity
- Drawbox: red alert bar top
- Drawtext: source + date
- Drawtext: headline

See `references/hook-cold-open.ff.txt` (to be added) for full reusable filter snippets.

### For Pattern-Interrupt (Wan2GP-generated)

Generate a 0.5-1.0s clip via Wan2GP with a prompt like:
```
"Extreme close-up of [subject], sudden reverse zoom out revealing [context],
cinematic lighting, high contrast, 0.5-second duration, 24fps"
```

## Quality gates for a hook beat

Before shipping a video, verify beat_01 passes:

- [ ] **Mute test**: watch the first 3 seconds with audio off — did you want to keep watching?
- [ ] **Text-at-0.5s test**: pause at 0.5 seconds — is there any text visible? If no, half your audience bounced.
- [ ] **Attention-lock test**: does the frame at t=1.0s contain something your eye can't leave? (Face, motion, high-contrast text, numeric tease)
- [ ] **Voice-hook-timing test**: does the voice-over hook LAND before 1.5s? If it takes longer, you've lost algorithm credit.
- [ ] **Payoff-tease test**: by 3.0s, have you promised SOMETHING specific the viewer will get if they keep watching?

## Anti-patterns (never do these)

- ❌ **Slow fade-in** — kills retention; TikTok and Reels penalize quiet first-0.5s
- ❌ **Logo splash** — "brought to you by X" at t=0 is a hard bounce
- ❌ **Ask a question with no visual** — "did you know..." as voice-only with generic b-roll is a muted-viewer-bouncer
- ❌ **Background music hook** — music is not a visual; algo counts your hook-energy from visual + title only
- ❌ **Subtitle-only hook** — tiny captions at bottom don't register as a hook; use a TOP-third 80-120px title overlay

## Related skills

- `scriptwriting-shortform` — authors the voice-over hook (words)
- `scene-generation` — prompts Wan2GP / LTX for visual hooks (Wan 2.2 + Wan 2.1 prompt structure)
- `edit-choreography` — governs cut timing + energy curve across the full video
- `music-direction` — sound-drop synchronization with hook reveal
- `video-qa` — post-render hook-effectiveness checklist

## Related files in the contentops-core codebase

- `D:\Ideas\contentops-core\contentops\video_render.py` — `assemble_beat_timed()` is where hook-cold-open insertion happens (line ~1241)
- `D:\Ideas\contentops-core\contentops\hooks.py` — voice-over hook generation (LLM-driven)
- `D:\Ideas\contentops-core\contentops\scripts.py` — calls hooks.py + composes into full script
- `D:\Ideas\contentops-core\data\renders\<script_id>\beats.json` — inspect beat_01 duration + first-frame composition

## Implementation status (2026-04-23)

The text-cold-open hook is **not yet wired** into `video_render.py`'s default path — it's authored but pending integration. To activate: set `HOOK_STYLE=text_cold_open` in `.env`, then patch `assemble_beat_timed()` to prepend the hook-clip to beat_01 using the ffmpeg `drawtext` snippet above. See `TODO: HUMAN CHOICE` markers in the codebase.
