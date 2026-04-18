# Long-Form Video Production (YouTube 8-60 min)

Long-form is structurally different from short-form. You can't just stitch 60-second clips together.
This rule file covers the full workflow for YouTube videos, tutorials, explainers, and documentaries.

## Format Specs

| Parameter | Value |
|---|---|
| Resolution | 1920x1080 (16:9 landscape) |
| Frame rate | 30fps (cinematic: 24fps) |
| Codec | H.264 (MP4) or H.265 for 4K |
| Audio | AAC 320kbps stereo |
| Duration | 8-60 minutes |
| File size | Aim for < 4GB (YouTube limit: 256GB) |
| Thumbnail | 1280x720, <2MB, JPEG/PNG |

## Structure: Chapter-Based Production

Long-form videos are built as chapters, not a single stream.

```
VIDEO STRUCTURE
==============
00:00 - COLD OPEN (hook: 15-30s, no intro)
00:30 - INTRO (brand animation + topic setup: 15-30s)
01:00 - CHAPTER 1: [Topic introduction]
04:00 - CHAPTER 2: [Deep dive / first key point]
08:00 - CHAPTER 3: [Second key point / demonstration]
12:00 - CHAPTER 4: [Third key point / case study]
16:00 - CHAPTER 5: [Synthesis / what this means]
18:00 - OUTRO (CTA + next video tease: 30-60s)
```

**Each chapter is produced independently** then assembled. This allows:
- Parallel generation of scenes across chapters
- Easy re-ordering of chapters without re-rendering everything
- Independent quality review per chapter
- Chapter markers for YouTube navigation

## Script Structure for Long-Form

### Per-Chapter Script Template

```json
{
  "chapter_id": "ch_02",
  "title": "How Neural Networks Actually Learn",
  "duration_target_sec": 240,
  "narrative_script": "In this section, we'll break down...",
  "sections": [
    {
      "section_id": "ch02_s01",
      "type": "explanation",
      "text": "Think of a neural network like a factory assembly line...",
      "visual_direction": "Animated diagram showing layers, data flowing through nodes, each node lighting up as data passes",
      "visual_engine": "remotion",
      "duration_sec": 45
    },
    {
      "section_id": "ch02_s02",
      "type": "demonstration",
      "text": "Let me show you what this looks like in practice...",
      "visual_direction": "Screen recording of training loop, loss curve dropping, model improving in real-time",
      "visual_engine": "ffmpeg_capture",
      "duration_sec": 60
    },
    {
      "section_id": "ch02_s03",
      "type": "avatar_commentary",
      "text": "Now here's where it gets interesting...",
      "visual_direction": "Avatar center-frame, speaking directly to camera, slight lean in",
      "visual_engine": "seedance_2.0",
      "duration_sec": 20
    }
  ]
}
```

### Word Count Guidelines

| Duration | Word Count | Script Pages |
|---|---|---|
| 8 min | ~1,200 words | 4-5 pages |
| 15 min | ~2,250 words | 8-10 pages |
| 30 min | ~4,500 words | 15-18 pages |
| 60 min | ~9,000 words | 30-35 pages |

Average speaking rate: 150 words/min for clear delivery.

## Visual Variety Rule

**Long-form videos MUST have visual variety.** The #1 failure is a talking head for 20 minutes.

**Minimum visual changes per minute: 3**

Visual types to alternate between:

| Visual Type | Duration | Use For |
|---|---|---|
| Avatar (talking head) | 15-30s max per stretch | Personal commentary, transitions, emphasis |
| AI-generated scene | 5-15s | Illustrating concepts, metaphors, scenarios |
| Data visualization | 10-30s | Statistics, comparisons, timelines (use Remotion) |
| Screen recording | 30-120s | Demos, tutorials, code walkthrough |
| Stock B-roll | 5-10s | Establishing shots, mood setting |
| Text animation | 3-8s | Key quotes, definitions, section headers |
| Split screen | 10-20s | Before/after, comparison, parallel narrative |

**Rule:** Never show the same visual type for more than 45 seconds continuously.
**Exception:** Screen recordings for tutorials can run 2 minutes, but overlay captions and callouts.

## Audio for Long-Form

### Background Music
- Volume: 8-12% during speech, 20-30% during visual-only sections
- Genre: Match content tone (jazz for business, electronic for tech, acoustic for storytelling)
- Transitions: Fade music up during chapter transitions (2-3s fade)
- Track length: Use 3-5 minute loops, crossfade between tracks at chapter boundaries
- Source: Royalty-free (Artlist, Epidemic Sound) or AI-generated

### Sound Design
- Section transitions: Subtle whoosh or click
- Data reveals: Gentle "ding" or rise sound
- Key points: Subtle emphasis sound (don't overdo)
- Chapter transitions: Musical bridge (3-5s)

### Voice
- Consistent voice throughout (don't switch mid-video)
- Natural pauses between sections (0.5-1s silence)
- Slightly slower pace for complex explanations (130 wpm)
- Slightly faster for exciting reveals (160 wpm)

## Assembly Pipeline

### Step 1: Generate all chapters independently

```bash
# Each chapter renders to its own file
data/chapters/
  ch00_cold_open.mp4      # 30s
  ch01_intro.mp4          # 60s
  ch02_neural_networks.mp4 # 240s
  ch03_demo.mp4           # 240s
  ch04_case_study.mp4     # 240s
  ch05_synthesis.mp4      # 180s
  ch06_outro.mp4          # 45s
```

### Step 2: Add chapter transitions

```bash
# Crossfade between chapters (0.5s transition)
ffmpeg -i ch01.mp4 -i ch02.mp4 -filter_complex \
  "xfade=transition=fade:duration=0.5:offset=59.5" \
  ch01_ch02_joined.mp4
```

### Step 3: Concatenate all chapters

```bash
# Create concat file
echo "file 'ch00_cold_open.mp4'" > chapters.txt
echo "file 'ch01_intro.mp4'" >> chapters.txt
echo "file 'ch02_neural_networks.mp4'" >> chapters.txt
# ... etc

# Concatenate
ffmpeg -f concat -safe 0 -i chapters.txt -c copy full_video.mp4
```

### Step 4: Add background music track

```bash
# Mix voice track + music track over full video
ffmpeg -i full_video.mp4 -i background_music.mp3 \
  -filter_complex "[1:a]aloop=loop=-1:size=2e+09,atrim=duration=1200,volume=0.10,afade=t=in:d=2,afade=t=out:st=1198:d=2[music];[0:a][music]amix=inputs=2:duration=first[aout]" \
  -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 320k final_video.mp4
```

### Step 5: Generate YouTube metadata

```json
{
  "title": "How AI Actually Works in 2026 (Complete Guide)",
  "description": "In this video, I break down...\n\nChapters:\n00:00 - Introduction\n01:00 - What is AI?\n04:00 - Neural Networks Explained\n...",
  "tags": ["AI", "machine learning", "2026", "technology", "tutorial"],
  "category": "Science & Technology",
  "chapters": [
    {"time": "00:00", "title": "Introduction"},
    {"time": "01:00", "title": "What is AI?"},
    {"time": "04:00", "title": "Neural Networks Explained"},
    {"time": "08:00", "title": "Live Demo"},
    {"time": "12:00", "title": "Case Study: Healthcare"},
    {"time": "16:00", "title": "What This Means for You"},
    {"time": "18:00", "title": "What's Next"}
  ],
  "thumbnail": "data/thumbnails/video_thumb.jpg"
}
```

## Thumbnail Generation

YouTube thumbnails are critical for CTR. Rules:
- 1280x720 pixels, < 2MB
- Large face (takes up 40%+ of frame) showing emotion
- 3-4 word text overlay in bold, high-contrast font
- Bright, saturated colors (stand out in feed)
- Contrasting background (don't blend into YouTube's white)
- Brand element: small Daena logo or teal accent

```bash
# Generate thumbnail from a video frame + text overlay
ffmpeg -i avatar_frame.jpg -vf \
  "drawtext=text='AI CHANGED EVERYTHING':fontsize=72:fontcolor=white:borderw=4:bordercolor=black:x=(w-text_w)/2:y=h*0.75:fontfile=fonts/bold.ttf" \
  -frames:v 1 thumbnail.jpg
```

## Long-Form + AI Video Generation Strategy

For a 15-minute video, you might have 60-80 beats. Generating all with Seedance 2.0 at $0.30/sec = ~$270. That's expensive.

**Cost-optimized strategy:**

| Beat Type | Count (typical 15min) | Engine | Cost |
|---|---|---|---|
| Avatar lip-sync | 8-12 beats | Seedance 2.0 | ~$30-50 |
| Key concept visuals | 10-15 beats | LTX 2.3 (local) | $0 |
| Data visualizations | 5-8 beats | Remotion | $0 |
| Stock B-roll | 10-15 beats | Pexels | $0 |
| Screen recordings | 3-5 beats | FFmpeg | $0 |
| Text animations | 8-10 beats | Remotion | $0 |
| Transitions | 15-20 | FFmpeg xfade | $0 |
| **Total** | ~60-80 beats | | **~$30-50** |

**Rule:** Use Seedance 2.0 ONLY for avatar lip-sync and hero concept shots. Use LTX local + Remotion + stock for everything else. Target < $50/video for 15-minute content.

## Quality Checklist (Long-Form)

Before publishing:
- [ ] All chapters play smoothly with no audio gaps
- [ ] Chapter markers match actual content timestamps
- [ ] Visual variety: no same visual type > 45s continuously
- [ ] Background music doesn't clip or have abrupt cuts
- [ ] Captions are accurate and properly timed throughout
- [ ] Thumbnail passes the "3-second scroll test" (compelling at small size)
- [ ] Description has chapters, links, and relevant keywords
- [ ] End screen / outro cards are placed correctly
- [ ] Total file size is reasonable (< 4GB for 15min)
- [ ] Audio levels are consistent across chapters (-16 LUFS target)
