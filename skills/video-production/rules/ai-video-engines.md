# AI Video Generation Engines

Reference for all supported AI video generation engines.
Use this when creating video clips from text prompts, images, or reference videos.

## Engine Overview

| Engine | Creator | Max Duration | Max Resolution | Lip-Sync | Open Source | API Host |
|---|---|---|---|---|---|---|
| Seedance 2.0 | ByteDance | 15s/clip | 720p | Native (best) | No | fal.ai |
| LTX 2.3 | Lightricks | 60s/clip | 4K | Native | Yes (OpenRail-M) | Local / fal.ai |
| Kling 3.0 | Kuaishou | 5 min/clip | 4K | Native | No | Kuaishou API |
| Higgsfield | Higgsfield AI | Varies | 1080p | Via models | No | higgsfield.ai |

---

## Seedance 2.0 (ByteDance)

**Best for:** Avatar lip-sync, multi-reference scenes, highest-quality short clips.
**Elo ranking:** 1,269 (beats Veo 3, Sora 2, Runway Gen-4.5 as of Feb 2026).
**Architecture:** Dual-branch DiT (Diffusion Transformer) -- generates video AND audio in a single pass.

### API Endpoints (via fal.ai)

| Endpoint | Model ID | Use Case |
|---|---|---|
| Text-to-Video | `bytedance/seedance-2.0/text-to-video` | Scene from text description |
| Text-to-Video (Fast) | `bytedance/seedance-2.0/fast/text-to-video` | Quick drafts, lower quality |
| Image-to-Video | `bytedance/seedance-2.0/image-to-video` | Animate a still image |
| Image-to-Video (Fast) | `bytedance/seedance-2.0/fast/image-to-video` | Quick image animation |
| Reference-to-Video | `bytedance/seedance-2.0/reference-to-video` | Multi-reference input |
| Reference-to-Video (Fast) | `bytedance/seedance-2.0/fast/reference-to-video` | Quick multi-ref |

### Setup

```bash
pip install fal-client
export FAL_KEY="your-fal-api-key"
```

### Text-to-Video

```python
import fal_client

result = fal_client.subscribe(
    "bytedance/seedance-2.0/text-to-video",
    arguments={
        "prompt": "A confident woman in a dark slate blazer speaks to camera in a modern office. She says: 'AI governance is not optional anymore.' Warm studio lighting, shallow depth of field, cinematic.",
        "duration": "8",          # 4-15 seconds
        "resolution": "720p",     # 480p or 720p
        "aspect_ratio": "9:16"    # 21:9, 16:9, 4:3, 1:1, 3:4, 9:16
    }
)
video_url = result["video"]["url"]
# Download: requests.get(video_url).content -> save to file
```

**Lip-sync trick:** Put dialogue in quotes in the prompt. Seedance will generate phoneme-accurate lip movements.

### Image-to-Video (animate a still)

```python
result = fal_client.subscribe(
    "bytedance/seedance-2.0/image-to-video",
    arguments={
        "prompt": "The cityscape slowly comes alive, cars begin moving, lights flicker on, gentle camera drift right",
        "image_url": "https://example.com/cityscape.jpg",
        "duration": "5",
        "resolution": "720p"
    }
)
```

### Multi-Reference (character consistency)

```python
result = fal_client.subscribe(
    "bytedance/seedance-2.0/reference-to-video",
    arguments={
        "prompt": "Two people discussing AI trends in a conference room, natural gestures, eye contact",
        "reference_images": [face_img_1, face_img_2, room_img],  # Up to 9 images
        "reference_videos": [prev_scene_url],  # Up to 3 videos
        "reference_audios": [voiceover_url],   # Up to 3 audio files
        "duration": "10"
    }
)
```

### Pricing
- Quality mode: ~$0.30/sec (720p with audio)
- Fast mode: ~$0.14/sec (720p, faster but lower quality)
- Aspect ratios: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16

### Seedance 2.0 Prompting Tips
- Start with subject, then action, then environment, then style
- For lip-sync: include spoken text in double quotes
- Specify camera: "slow dolly in", "static medium shot", "handheld tracking"
- Include ambient audio hints: "cafe ambient, soft espresso machine, gentle cup clink"
- Emotion keywords: "confident", "thoughtful", "urgent", "warm"
- Avoid: overly complex multi-action sequences in a single clip (break into beats)

---

## LTX 2.3 (Lightricks)

**Best for:** Self-hosted generation, long clips (60s), fine-tuning with LoRA, budget-conscious production.
**License:** OpenRail-M (commercial use allowed).
**GPU requirement:** RTX 4060+ (8GB VRAM minimum for 2B model, 16GB+ for 13B).

### Model Variants

| Model | Parameters | VRAM | Speed | Quality |
|---|---|---|---|---|
| ltxv-2b-0.9.8-distilled | 2B | 8GB | Fast | Good |
| ltxv-13b-0.9.8-distilled | 13B | 16GB | Medium | Better |
| ltxv-13b-0.9.8-dev | 13B | 16GB | Slow | Best |
| LTX-2.3 | 22B | 24GB+ | Slow | Best + Audio |

### Local Setup

```bash
git clone https://github.com/Lightricks/LTX-Video.git
cd LTX-Video
python -m venv env && source env/bin/activate  # or .\env\Scripts\activate on Windows
python -m pip install -e ".[inference]"

# Download model
huggingface-cli download Lightricks/ltxv-13b-0.9.8-distilled --local-dir models/ltx-13b
```

### Local Generation

```python
from ltx_video import LTXVideoPipeline

pipe = LTXVideoPipeline.from_pretrained("models/ltx-13b")
pipe.to("cuda")

video = pipe(
    prompt="Aerial shot of a futuristic city at sunset, flying cars, neon lights reflecting off glass towers",
    negative_prompt="blurry, low quality, distorted",
    num_frames=120,  # 5 seconds at 24fps
    width=1280,
    height=720,
    guidance_scale=7.5,
    num_inference_steps=30
)
video.save("output.mp4")
```

### Via API (fal.ai)

```python
result = fal_client.subscribe(
    "fal-ai/ltx-video/image-to-video",
    arguments={
        "prompt": "Scene description",
        "image_url": "https://example.com/start_frame.jpg",
        "num_frames": 120
    }
)
```

### LoRA Fine-Tuning (custom style)
LTX supports LoRA for training custom visual styles:
```bash
# Train a LoRA on your brand's visual style
python train_lora.py --base-model ltxv-13b --data ./brand_videos/ --output ./lora/daena_style.safetensors
```

---

## Kling 3.0 (Kuaishou)

**Best for:** Longest native generation (5 min), cheapest per-second, 4K native.
**Access:** Kuaishou API or via aggregators (Higgsfield, VidSpotAI).

### Generation

```python
# Via Kuaishou API
result = kling_client.create_video(
    prompt="Documentary-style footage of a modern AI research lab, scientists collaborating around holographic displays, warm overhead lighting, steady camera tracking shot",
    duration=60,        # Up to 300 seconds (5 minutes)
    resolution="4k",
    style="cinematic",
    camera_control="tracking_right"
)
```

### When to Use Kling over Seedance
- Need clips > 15 seconds (Kling does up to 5 min)
- Need 4K resolution (Seedance maxes at 720p)
- Budget-sensitive: ~$0.10/sec vs Seedance's ~$0.30/sec
- Don't need lip-sync (Seedance is better for that)

---

## Higgsfield (Multi-Model Orchestrator)

**Best for:** Character consistency across scenes, multi-model orchestration, team workflows.
**What it is:** Not a model itself -- orchestrates Kling 3.0, Veo 3.1, Sora 2, Seedance 2.0 through a unified interface.

### Key Features
- **Soul Cast:** Consistent AI actors across scenes (up to 3 characters)
- **AI Storyboard Generator:** Multi-scene planning with automatic shot sequencing
- **Cinematic logic layer:** GPT-4.1/GPT-5 plans shots, pacing, camera angles before dispatching to video models

### When to Use
- Multi-character scenes needing consistency across 5+ clips
- When you want to A/B test different models for the same scene
- Enterprise content with SOC2/GDPR compliance needs

### Pricing (credit-based)
| Plan | Price |
|---|---|
| Starter | $15/mo |
| Plus | $34/mo |
| Ultra | $84/mo |
| Business | $49/seat/mo |

---

## Engine Selection Decision Tree

```
Need lip-sync?
  YES -> Seedance 2.0 (text-to-video with quoted dialogue)
  NO ->
    Clip > 15 seconds?
      YES -> Kling 3.0 (up to 5 min)
      NO ->
        Need to run locally/free?
          YES -> LTX 2.3 (self-hosted)
          NO ->
            Need character consistency across many scenes?
              YES -> Higgsfield (Soul Cast)
              NO ->
                Budget-sensitive?
                  YES -> Kling 3.0 (~$0.10/sec) or LTX local (free)
                  NO -> Seedance 2.0 (highest quality)
```

## Batch Generation Pattern

For a full video with many beats, generate scenes in parallel:

```python
import asyncio
import fal_client

async def generate_all_scenes(beat_map):
    tasks = []
    for beat in beat_map["beats"]:
        if beat["engine"] == "seedance_2.0":
            task = generate_seedance(beat)
        elif beat["engine"] == "ltx_2.3":
            task = generate_ltx_local(beat)
        elif beat["engine"] == "kling_3.0":
            task = generate_kling(beat)
        elif beat["engine"] == "remotion":
            task = render_remotion_scene(beat)
        else:
            task = fetch_stock_broll(beat)
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    for beat, result in zip(beat_map["beats"], results):
        beat["generated_file"] = result
        beat["status"] = "generated"
    return beat_map
```

## Environment Variables

```bash
# Required for cloud engines
FAL_KEY=fal-xxxxxxxxxxxx           # Seedance 2.0, LTX API
KLING_API_KEY=kling-xxxxxxxxxxxx    # Kling 3.0
HIGGSFIELD_API_KEY=hf-xxxxxxxxxxxx  # Higgsfield

# Required for audio
ELEVENLABS_API_KEY=sk-xxxxxxxxxxxx  # ElevenLabs TTS

# Required for stock footage
PEXELS_API_KEY=xxxxxxxxxx           # Pexels B-roll

# Local models path
MODELS_ROOT=D:\Ideas\MODELS_ROOT    # LTX weights, whisper models
```
