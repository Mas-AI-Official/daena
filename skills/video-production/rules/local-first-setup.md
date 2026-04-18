# Local-First Video Production Setup

Hardware profile: RTX 4060 Laptop (8GB VRAM) + 32GB RAM
Strategy: Remotion primary, local AI gen secondary, cloud APIs only for hero shots

## Hardware Constraints

| Resource | Available | Hard Limit |
|---|---|---|
| GPU VRAM | 8GB (RTX 4060 Laptop) | Models must fit in ~7.5GB usable |
| System RAM | 32GB | Ollama models offload here when GPU full |
| Storage | D:\Ideas\MODELS_ROOT | All models stored here |

**Rule:** Never load a model that exceeds 8GB VRAM. If it OOMs, switch to the next tier down.

## Rendering Priority Stack (cheapest + most reliable first)

### Tier 1: REMOTION (Primary -- No VRAM needed, unlimited)

Remotion runs in Node.js, not on GPU. It is the PRIMARY video creation engine.
Use for: ALL programmatic content -- text animations, data viz, charts, scene compositions,
title cards, lower thirds, progress bars, brand overlays, transitions.

**When to use Remotion:**
- Text-on-screen animations (word-by-word captions, stat reveals, key quotes)
- Data visualizations (bar charts, line charts, stat counters)
- Scene compositions (layering images + text + animations)
- Title sequences and chapter headers
- Split-screen layouts
- Any content that can be described programmatically

**When NOT to use Remotion:**
- Photorealistic scenes (use AI video gen)
- Avatar lip-sync (use Seedance 2.0 API or pre-recorded video)
- Real-world footage (use stock or AI gen)

Load the **remotion-best-practices** skill for Remotion code patterns.

### Tier 2: FFMPEG (Post-Production -- No VRAM needed, free)

FFmpeg handles all post-production compositing. Free, fast, deterministic.
- Concatenating clips, transitions (xfade)
- Avatar overlay (colorkey/alpha compositing)
- Caption burn-in, progress bars, watermarks
- Audio mixing (voice + music)
- Ken Burns on still images
- Format conversion for all platforms

### Tier 3: SadTalker (Local Avatar Lip-Sync -- 2-4GB VRAM)

**Project:** `D:\Ideas\SadTalker\`
**Models:** All downloaded at `D:\Ideas\SadTalker\checkpoints\` (~2GB total)
**VRAM:** ~2-4GB (very lightweight, can run alongside other tasks)
**What it does:** Single portrait image + audio -> talking head video with lip-sync
**Quality:** 7/10 (natural head movement, accurate lip-sync, GFPGAN face enhancement)
**This replaces Seedance 2.0 API for avatar scenes at $0 cost.**

**Usage:**
```bash
cd D:\Ideas\SadTalker
D:\Ideas\SadTalker\venv\Scripts\python.exe inference.py \
  --driven_audio path/to/voiceover.wav \
  --source_image path/to/daena_avatar.png \
  --result_dir data/outputs/ \
  --size 512 \
  --enhancer gfpgan \
  --preprocess full \
  --still
```

**Pipeline integration:**
1. Generate voiceover audio (Kokoro TTS or ElevenLabs)
2. Feed audio + Daena portrait image to SadTalker
3. SadTalker outputs talking head video
4. Composite talking head over scene background using FFmpeg colorkey/overlay

**Key flags:**
- `--size 512` = higher quality (use 256 for faster drafts)
- `--enhancer gfpgan` = face enhancement (recommended for production)
- `--still` = less head movement (more stable for overlay compositing)
- `--preprocess full` = full face extraction and alignment

**Daena avatar image:** Use a clean, front-facing portrait of Daena persona.
Store at: `D:\Ideas\MODELS_ROOT\xtts\voices\daena_avatar.png` (alongside Daena voice clip)

### Tier 4: LTX-Video 2B FP8 (Local AI Scene Gen -- 5GB VRAM)

**Model:** `Lightricks/LTX-Video` (file: `ltxv-2b-0.9.8-distilled-fp8.safetensors`)
**Location:** `D:\Ideas\MODELS_ROOT\ltx-2b-fp8\ltxv-2b-0.9.8-distilled-fp8.safetensors`
**Size:** 4.46GB on disk
**VRAM:** ~4-5GB (FP8 distilled 2B, fits 8GB with headroom)
**Supports:** Text-to-video AND image-to-video
**Quality:** 7/10
**Duration:** Up to 10s per clip at 720p
**Speed:** ~300-400s per clip on RTX 4060
**Steps:** 8 inference steps (distilled), CFG=1

**IMPORTANT:** The newer LTX-2.3 is a 22B model (15-29GB) that does NOT fit 8GB VRAM.
We use the 2B distilled FP8 variant (0.9.8) which is 4.46GB and runs comfortably.

Use for: AI-generated B-roll scenes that match narration.
Example: Avatar says "neural networks" -> LTX generates a glowing neural network visualization.

**Quick generation via ComfyUI (recommended):**
1. Place `ltxv-2b-0.9.8-distilled-fp8.safetensors` in ComfyUI `models/diffusion_models/`
2. Set resolution to 704x480 or 832x480 for 8GB VRAM safety
3. Use 8 inference steps (distilled model is trained for 8 steps)
4. Set CFG=1 (distilled model uses classifier-free)

**Quick generation (standalone):**
```python
# Via diffusers (needs diffusers >= 0.32)
from diffusers import LTXPipeline
import torch

pipe = LTXPipeline.from_single_file(
    "D:/Ideas/MODELS_ROOT/ltx-2b-fp8/ltxv-2b-0.9.8-distilled-fp8.safetensors",
    torch_dtype=torch.float16,
)
pipe.to("cuda")

video = pipe(
    prompt="Glowing neural network nodes connecting with light paths, dark background, cinematic",
    num_frames=75,  # ~3 seconds at 25fps
    width=704, height=480,
    guidance_scale=1.0,  # distilled model uses CFG=1
    num_inference_steps=8,  # distilled model trained for 8 steps
).frames[0]
# Export with imageio or save pipeline output
```

**Via ComfyUI (recommended for workflow iteration):**
1. Install `ComfyUI-LTXVideo` node
2. Load `ltxv-2b-0.9.8-distilled-fp8.safetensors` as diffusion model
3. Set resolution to 704x480 or 832x480 for 8GB safety
4. Use 20-30 inference steps

### Tier 4: Wan 2.1 T2V 1.3B (Backup Local AI Gen -- 8GB VRAM)

**Model:** `Wan-AI/Wan2.1-T2V-1.3B`
**Location:** `D:\Ideas\MODELS_ROOT\wan2.1-1.3b\`
**VRAM:** ~8GB (fits exactly with T5 offloaded to CPU)
**Supports:** Text-to-video only (no image-to-video at 1.3B)
**Quality:** 6/10
**Duration:** ~5 seconds at 480p
**Speed:** ~200-300s per clip

Use for: When LTX is busy or you want a different visual style.

```bash
# Standalone generation
cd D:\Ideas\MODELS_ROOT\wan2.1-1.3b
python generate.py --task t2v-1.3B --size 832*480 \
  --ckpt_dir . --offload_model True --t5_cpu \
  --prompt "Futuristic city at sunset, neon lights reflecting off glass towers"
```

**Via ComfyUI:**
1. Download `wan2.1_t2v_1.3B_fp16.safetensors` into `models/diffusion_models/`
2. Use `umt5_xxl_fp8_e4m3fn_scaled.safetensors` for text encoder (FP8 to save VRAM)
3. Set `--offload_model True --t5_cpu` flags

### Tier 5: AnimateDiff Lightning + SD 1.5 (Stylized Video -- 6-8GB VRAM)

**Model:** `ByteDance/AnimateDiff-Lightning` + your existing SD 1.5
**Location:** SD 1.5 already at `D:\Ideas\MODELS_ROOT\hf\hub\models--stable-diffusion-v1-5--stable-diffusion-v1-5`
**VRAM:** ~6-8GB
**Supports:** Text-to-video (stylized)
**Quality:** 5/10 (stylized, depends on LoRAs)
**Duration:** 2-8 seconds
**Speed:** Fast (1-8 inference steps with Lightning)

Use for: Stylized/artistic scenes, rapid iteration, LoRA-based custom styles.

### Tier 6: Stock Footage (Pexels API -- No VRAM, free)

Use for: Generic establishing shots, mood-setting B-roll, transitions.
Not for: Specific concept visuals that match narration.

### Tier 7: Cloud APIs (Seedance 2.0, Kling -- PAID, last resort)

Use ONLY for:
- Avatar lip-sync (Seedance 2.0 is irreplaceable for this)
- Hero shots in premium content
- When local gen quality is insufficient for the scene

## Ollama Models for Scripting & Scene Planning

Your best models for the scripting/planning pipeline:

| Model | Size | Best For | Load Command |
|---|---|---|---|
| **qwen3.5:9b** | 6.6GB | Script writing, scene planning, creative direction | `ollama run qwen3.5:9b` |
| **gemma4:e4b** | 9.6GB | Analysis, research synthesis, quality scoring | `ollama run gemma4:e4b` |
| **deepseek-r1:8b** | 5.2GB | Complex reasoning, chain-of-thought planning | `ollama run deepseek-r1:8b` |
| **gemma3:4b** | 3.3GB | Quick drafts, cheap labor (script iterations) | `ollama run gemma3:4b` |
| **qwen2.5:1.5b** | 986MB | Ultra-fast classification, tagging, short tasks | `ollama run qwen2.5:1.5b` |

**Recommended pipeline assignment:**
- Script first draft: `gemma3:4b` (fast, free, good enough for drafts)
- Script QA scoring: `qwen3.5:9b` (better judgment for quality gates)
- Scene plan descriptions: `qwen3.5:9b` (needs creativity + specificity)
- Research synthesis: `gemma4:e4b` (best at combining multiple sources)
- Beat map visual prompts: `deepseek-r1:8b` (reasoning about what visual matches what speech)

**WARNING:** Do NOT load a 27B+ model (qwen3.5:27b, gemma4:26b, qwen3-coder:30b) while running
local video generation. They consume 17GB+ RAM and compete with the GPU for memory bandwidth.
Use them only when GPU is idle.

## VRAM Budget Rule

Never run two GPU-heavy tasks simultaneously:
- Video generation: uses full 8GB VRAM
- Ollama large models on GPU: uses 4-8GB VRAM
- Remotion rendering: uses 0 VRAM (CPU/Node.js)
- FFmpeg: uses 0 VRAM (CPU)

**Safe concurrent combos:**
- Remotion + FFmpeg + Ollama (any size) -- all CPU, no VRAM conflict
- LTX video gen + Kokoro TTS -- TTS is CPU, video gen is GPU
- FFmpeg compositing + Ollama script writing -- both CPU

**Unsafe combos (will OOM):**
- LTX video gen + large Ollama model on GPU
- Two video gen tasks simultaneously
- Video gen + SD image gen simultaneously

## Model Locations (canonical)

```
D:\Ideas\MODELS_ROOT\
  ltx-2b\          # LTX-Video 2B distilled FP8 (primary local video gen)
  wan2.1-1.3b\     # Wan 2.1 T2V 1.3B (backup local video gen)
  ltx\             # LTX-2 19B (TOO LARGE for 8GB - keep for reference only)
  whisper\         # faster-whisper-base (caption timestamps)
  xtts\            # Coqui XTTS v2 + Daena voice clone
  hf\hub\
    models--Kokoro-82M\             # Kokoro TTS (free draft voice)
    models--stable-diffusion-v1-5\  # SD 1.5 (AnimateDiff base)
    models--faster-whisper-base\    # Whisper (captions)
  ollama\          # Ollama model blobs
```

## Scene Type -> Engine Mapping (Local-First)

| Scene Type | Engine | VRAM | Cost |
|---|---|---|---|
| Text animation | Remotion | 0 | Free |
| Data visualization | Remotion | 0 | Free |
| Title/chapter cards | Remotion | 0 | Free |
| Split screen | Remotion | 0 | Free |
| Transitions | FFmpeg xfade | 0 | Free |
| Avatar overlay | FFmpeg colorkey | 0 | Free |
| Audio mixing | FFmpeg | 0 | Free |
| Caption burn-in | FFmpeg | 0 | Free |
| Ken Burns on image | FFmpeg | 0 | Free |
| Avatar lip-sync | SadTalker (local) | 3GB | Free |
| AI B-roll (concept) | LTX 2.3 FP8 | 6GB | Free |
| AI B-roll (backup) | Wan 2.1 1.3B | 8GB | Free |
| Stylized scenes | AnimateDiff + SD1.5 | 7GB | Free |
| Stock establishing | Pexels API | 0 | Free |
| Hero lip-sync (premium) | Seedance 2.0 API | 0 | ~$0.30/sec (last resort) |
| Draft voice | Kokoro TTS | 0 (CPU) | Free |
| Production voice | ElevenLabs API | 0 | Paid |
| Captions/timestamps | faster-whisper | 0 (CPU) | Free |

**Budget target with local-first: $0-5 per short video, $5-15 per long video.**
(Only paying for Seedance lip-sync scenes and ElevenLabs production voice.)
