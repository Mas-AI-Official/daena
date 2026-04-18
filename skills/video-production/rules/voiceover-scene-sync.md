# Voice-Over-to-Scene Sync Pipeline

The core problem: avatar says "AI is revolutionizing healthcare" but the screen shows a generic stock office.
This pipeline ensures every visual matches what the avatar is saying at that exact moment.

## The 10-Step Pipeline

### Step 1: RESEARCH
Before writing any script, gather real information about the topic.
- Web search for current data, statistics, expert quotes
- Find reference images/videos that illustrate key concepts
- Identify 3-5 visual metaphors that explain the topic (e.g., "neural network" -> brain with glowing nodes)
- Save research to `data/research/{topic_slug}.json`

```json
{
  "topic": "AI in Healthcare 2026",
  "key_facts": [
    {"fact": "AI diagnostics now 94% accurate", "visual": "medical scan with AI overlay highlighting tumor"},
    {"fact": "Drug discovery reduced from 10 years to 18 months", "visual": "molecular structure rotating, timeline compression"}
  ],
  "visual_metaphors": [
    {"concept": "neural network", "visual": "glowing brain nodes connected by light paths"},
    {"concept": "data analysis", "visual": "flowing streams of medical records transforming into insights"}
  ]
}
```

### Step 2: SCRIPT (Dual-Script System)
Write TWO scripts in parallel:

**Narrative Script** (what the avatar says):
```
[HOOK] "What if I told you AI can now diagnose cancer more accurately than 94% of radiologists?"
[CONTEXT] "In 2026, we've crossed a threshold..."
[VALUE] "Three breakthroughs are making this possible..."
[CTA] "Follow for more AI insights that matter."
```

**Production Script** (what the viewer SEES for each line):
```
[HOOK] VISUAL: Close-up medical scan, AI overlay highlights region, dramatic zoom
[CONTEXT] VISUAL: Hospital corridor, data streams flowing through walls (Seedance 2.0 generation)
[VALUE] VISUAL: Split-screen showing 3 breakthroughs with icons and motion graphics (Remotion)
[CTA] VISUAL: Avatar center frame, Daena brand gradient background, subscribe animation
```

**Rule:** Every line in the narrative script MUST have a corresponding visual description in the production script.

### Step 3: VOICE (TTS Generation)
Generate the voiceover audio from the narrative script.

```python
# Generate TTS per section
sections = ["hook", "context", "value_1", "value_2", "value_3", "cta"]
for section in sections:
    audio = tts_engine.generate(
        text=narrative_script[section],
        voice="Matilda",  # Daena voice
        output=f"data/audio/{topic_slug}/{section}.wav"
    )
```

- Draft mode: Kokoro TTS (free, local)
- Production mode: ElevenLabs Matilda (paid, after approval)

### Step 4: BEAT MAP (Transcription + Segmentation)
Transcribe the audio back with word-level timestamps to create the beat map.

```python
# Use faster-whisper for word-level timestamps
from faster_whisper import WhisperModel
model = WhisperModel("large-v3")

segments, info = model.transcribe(
    "data/audio/topic/full.wav",
    word_timestamps=True
)

beat_map = []
for segment in segments:
    for word in segment.words:
        beat_map.append({
            "word": word.word,
            "start": word.start,
            "end": word.end,
            "confidence": word.probability
        })
```

The beat map is the data backbone. It tells us EXACTLY when each word is spoken.

**Beat grouping:** Group words into visual beats (3-8 second chunks that form a complete visual idea):

```json
{
  "beats": [
    {
      "id": "beat_01",
      "text": "What if I told you AI can now diagnose cancer",
      "start_sec": 0.0,
      "end_sec": 3.2,
      "duration_sec": 3.2,
      "visual_type": "ai_generation",
      "visual_prompt": "Close-up of a medical brain scan, AI overlay highlighting a suspicious region with glowing teal markers, dramatic slow zoom in, cinematic lighting",
      "engine": "seedance_2.0",
      "scene_mood": "dramatic_reveal"
    },
    {
      "id": "beat_02",
      "text": "more accurately than 94% of radiologists",
      "start_sec": 3.2,
      "end_sec": 5.8,
      "visual_type": "data_visualization",
      "visual_prompt": "Animated bar chart showing AI vs radiologist accuracy, teal and gold bars, number counter reaching 94%",
      "engine": "remotion",
      "scene_mood": "impressive_stat"
    }
  ]
}
```

### Step 5: SCENE PLAN (Visual Description per Beat)
For each beat, write the exact visual prompt that will be sent to the AI video engine.

**Prompt engineering rules for AI video generation:**
- Be specific about camera movement: "slow dolly in", "static wide shot", "tracking left"
- Specify lighting: "warm golden hour", "cool clinical fluorescent", "dramatic side-lit"
- Include motion: "smoke rising", "data particles flowing left to right", "gentle camera drift"
- Match emotional tone to the spoken content
- For Seedance 2.0 lip-sync: put dialogue in quotes within the prompt
- For scenes without avatar: describe exactly what concept should be visualized

**Scene type classification:**

| Scene Type | Engine | When to Use |
|---|---|---|
| `avatar_lipsync` | Seedance 2.0 | Avatar speaking directly to camera |
| `ai_generation` | Seedance 2.0 / LTX | Generated B-roll matching narration |
| `data_visualization` | Remotion | Charts, stats, comparisons |
| `screen_recording` | FFmpeg capture | Software demos, tutorials |
| `stock_broll` | Pexels + FFmpeg | Generic establishing shots |
| `text_animation` | Remotion | Key phrases, quotes, callouts |
| `transition` | FFmpeg xfade | Between major sections |

### Step 6: GENERATE (AI Video Generation)
Generate each scene using the assigned engine.

**Seedance 2.0 (via fal.ai):**
```python
import fal_client

# For avatar lip-sync scenes
result = fal_client.subscribe(
    "bytedance/seedance-2.0/text-to-video",
    arguments={
        "prompt": beat["visual_prompt"],
        "duration": str(min(beat["duration_sec"], 15)),  # Max 15s per clip
        "resolution": "720p",
        "aspect_ratio": "9:16"  # Portrait for short-form
    }
)
video_url = result["video"]["url"]

# For image-to-video (animate a reference image)
result = fal_client.subscribe(
    "bytedance/seedance-2.0/image-to-video",
    arguments={
        "prompt": beat["visual_prompt"],
        "image_url": reference_image_url,
        "duration": "5"
    }
)

# For multi-reference (up to 9 images, 3 videos, 3 audio)
result = fal_client.subscribe(
    "bytedance/seedance-2.0/reference-to-video",
    arguments={
        "prompt": beat["visual_prompt"],
        "reference_images": [img1_url, img2_url],
        "reference_videos": [vid1_url],
        "duration": "10"
    }
)
```

**LTX 2.3 (local, free):**
```python
# Self-hosted on RTX 4060+
from ltx_video import LTXVideoPipeline

pipe = LTXVideoPipeline.from_pretrained("Lightricks/ltxv-13b-0.9.8-distilled")
video = pipe(
    prompt=beat["visual_prompt"],
    num_frames=int(beat["duration_sec"] * 24),
    width=720, height=1280
)
video.save(f"data/scenes/{beat['id']}.mp4")
```

**Kling 3.0 (for long continuous shots):**
```python
# Via Kuaishou API -- best for shots > 15 seconds
result = kling_client.generate(
    prompt=beat["visual_prompt"],
    duration=beat["duration_sec"],  # Up to 5 minutes
    resolution="4k",
    style="cinematic"
)
```

### Step 7: ALIGN (Trim/Stretch to Match Audio)
Each generated clip must be EXACTLY the duration of its corresponding beat.

```bash
# Trim to exact beat duration
ffmpeg -i scene_beat_01.mp4 -t 3.2 -c:v libx264 -crf 18 beat_01_aligned.mp4

# If clip is too short, slow it down slightly (max 0.85x)
ffmpeg -i scene_beat_01.mp4 -filter:v "setpts=1.15*PTS" -t 3.2 beat_01_aligned.mp4

# If clip is too long, trim from the end (keep the opening)
ffmpeg -i scene_beat_01.mp4 -t 3.2 -c copy beat_01_aligned.mp4
```

**Alignment rules:**
- Never stretch more than 15% (looks unnatural)
- Never speed up more than 20%
- If a scene is drastically wrong duration, regenerate it with correct timing
- Add 0.1s overlap between beats for crossfade transitions

### Step 8: COMPOSITE (Layer Everything)
Assemble all aligned scenes with avatar overlay, captions, and music.

```
Layer stack (bottom to top):
1. Generated scene / B-roll (full frame)
2. Dark cinematic overlay (20-30% opacity)
3. Avatar overlay (bottom-right, colorkey/alpha, only during avatar_lipsync beats)
4. Captions (center-bottom, word-by-word highlight synced to beat map)
5. Brand elements (progress bar, watermark)
6. Background music (8-12% volume)
```

### Step 9: REVIEW (Sync Verification)
Watch the full composite and check:

- [ ] Every beat's visual matches the spoken content
- [ ] Lip-sync is accurate (for avatar scenes)
- [ ] Captions are correctly timed (word-by-word)
- [ ] Transitions between beats are smooth (no jarring cuts)
- [ ] Music doesn't overpower voice
- [ ] Total duration matches platform limit
- [ ] Brand colors and elements are consistent

**If sync is off:**
1. Identify which beats are misaligned
2. Regenerate only those specific scenes
3. Re-align and re-composite
4. Never regenerate the entire video for a single bad beat

### Step 10: EXPORT (Platform-Ready)
Export to all required platform formats.

```bash
# Short-form (TikTok, Reels, Shorts) -- 9:16, 1080x1920, max 60s
ffmpeg -i composite.mp4 -vf "scale=1080:1920" -c:v libx264 -crf 18 -c:a aac -b:a 192k -movflags +faststart output_shorts.mp4

# Long-form (YouTube) -- 16:9, 1920x1080
ffmpeg -i composite.mp4 -vf "scale=1920:1080" -c:v libx264 -crf 18 -c:a aac -b:a 320k -movflags +faststart output_youtube.mp4

# Square (LinkedIn, Feed) -- 1:1, 1080x1080
ffmpeg -i composite.mp4 -vf "scale=1080:1080,crop=1080:1080" -c:v libx264 -crf 18 output_linkedin.mp4
```

## Beat Map JSON Schema (canonical format)

```json
{
  "$schema": "beat-map-v1",
  "topic": "string",
  "total_duration_sec": 0.0,
  "format": "short_form | long_form",
  "beats": [
    {
      "id": "beat_01",
      "section": "hook | context | value | cta | chapter_N",
      "text": "The spoken words for this beat",
      "start_sec": 0.0,
      "end_sec": 3.5,
      "duration_sec": 3.5,
      "visual_type": "avatar_lipsync | ai_generation | data_visualization | stock_broll | text_animation | screen_recording | transition",
      "visual_prompt": "Detailed description of what the viewer should see",
      "engine": "seedance_2.0 | ltx_2.3 | kling_3.0 | higgsfield | remotion | ffmpeg | pexels",
      "scene_mood": "dramatic_reveal | impressive_stat | calm_explanation | energy_burst | emotional_peak",
      "generated_file": "data/scenes/beat_01.mp4",
      "aligned_file": "data/scenes/beat_01_aligned.mp4",
      "status": "pending | generated | aligned | approved | rejected"
    }
  ]
}
```

## Common Sync Problems and Fixes

| Problem | Cause | Fix |
|---|---|---|
| Avatar talks about X, screen shows Y | Visual prompt doesn't match narration | Rewrite visual_prompt to describe the concept being spoken |
| Lip-sync is off by 0.5s | Audio/video alignment drift | Re-align with FFmpeg `-itsoffset` or regenerate with Seedance 2.0 |
| Captions appear too early/late | Beat map timestamps wrong | Re-run faster-whisper transcription, check word boundaries |
| Jump cut between beats | No transition overlap | Add 0.1s crossfade between adjacent beats |
| Music drowns voice at peak | Music volume too high | Lower to 8% during speech, allow 15% during pauses |
| Scene too short for beat | AI generated shorter than requested | Slow down 10-15% or add Ken Burns on last frame |
| Scene doesn't match mood | Prompt missing emotional direction | Add mood keywords: "warm," "dramatic," "urgent," "peaceful" |
