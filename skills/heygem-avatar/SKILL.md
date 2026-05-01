---
name: heygem-avatar
description: HeyGem — open-source HeyGen alternative for AI avatar + lipsync video. Runs fully offline on Windows with an NVIDIA GPU. Clone a speaker from 10 seconds of reference video, then drive lip movement from arbitrary text or TTS audio. Use when a script needs a talking-head segment (founder-brand content, explainer videos, Daena-branded spokesperson clips) and you want the output local + private.
---

# HeyGem Avatar Skill

## What HeyGem does

HeyGem ([github.com/GuijiAI/HeyGem.ai](https://github.com/GuijiAI/HeyGem.ai), DUIX.com) gives you:
- **Appearance clone**: 10s reference video → photorealistic talking avatar
- **Voice clone**: reference audio → lipsynced speech in the cloned voice
- **Multi-language support**: EN, JA, KO, ZH, FR, DE, AR, ES
- **Fully offline**: runs locally on Windows, NVIDIA GPU required, no data leaves the machine

When to reach for HeyGem vs other options:

| Task | Tool |
|---|---|
| Explainer video with a branded spokesperson (Daena) | HeyGem |
| Cinematic b-roll (server rooms, cityscapes) | Wan2GP (Wan 2.2) |
| Text-to-speech only (no avatar) | ElevenLabs (emotional) OR Chatterbox (cloned) OR edge-tts (free) |
| Data viz / animated captions / brand cards | Remotion |
| Stock b-roll | Pexels |

HeyGem and Wan2GP are complementary: HeyGem for faces speaking, Wan2GP for scenes.

## Install runbook (isolated venv, MODELS_ROOT-safe)

Per the `MODELS_ROOT Convention` in global CLAUDE.md — **weights MUST land on D:\, not C:\**.

```powershell
# 1. Clone
cd D:\Ideas\contentops-core\services
mkdir heygem -ErrorAction SilentlyContinue
cd heygem
git clone https://github.com/GuijiAI/HeyGem.ai.git

# 2. Isolated venv (HeyGem may pin different torch than main pipeline)
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r HeyGem.ai\requirements.txt

# 3. Force models onto D: — CRITICAL, never C:
$env:MODELS_ROOT       = "D:\Ideas\MODELS_ROOT"
$env:HEYGEM_MODELS_DIR = "D:\Ideas\MODELS_ROOT\heygem"
$env:HF_HOME           = "D:\Ideas\MODELS_ROOT\hf"
$env:TORCH_HOME        = "D:\Ideas\MODELS_ROOT\torch_cache"
New-Item -ItemType Directory -Force -Path "D:\Ideas\MODELS_ROOT\heygem" | Out-Null

# 4. First-use downloads the base avatar model (~4-8 GB)
cd HeyGem.ai
..\.venv\Scripts\python.exe download_models.py   # or their equivalent bootstrap

# 5. Verify weights landed on D:
Get-ChildItem D:\Ideas\MODELS_ROOT\heygem -Recurse | Measure-Object -Property Length -Sum

# 6. Start the microservice (write a thin Flask wrapper following services/daena_tts pattern)
..\.venv\Scripts\python.exe ..\server.py   # listens on :9300
```

## Microservice API (to build in `services/heygem/server.py`)

Same pattern as `services/daena_tts/server.py` and `services/wan2gp/server.py`:

```
GET  /health → {installed: bool, avatars_available: [str], default_voice_cloned: bool}
POST /clone_avatar {reference_video_path: str, avatar_id: str}
      → {avatar_id: str, frames_indexed: int, ready: bool}
POST /generate {avatar_id: str, audio_path: str | None, text: str | None,
                duration_cap_s: float, voice_clone: bool}
      → audio/mp4 bytes (the talking-avatar clip)
```

One-time step: clone the brand spokesperson ONCE from `D:\Ideas\daena_voice.wav` (audio) +
a 10s reference clip. Store at `D:\Ideas\MODELS_ROOT\heygem\avatars\daena\`. All subsequent
generates route through `avatar_id=daena`.

## Integration point in the main pipeline

`contentops/video_render.py` — add a new beat type: `talking_head`. When the narration
beat is the hook or a quote-from-source line, route it to HeyGem instead of Pexels:

```python
# Inside render_script's beat-asset resolution:
if beat_type == "talking_head" and os.environ.get("HEYGEM_URL"):
    r = requests.post(f"{HEYGEM_URL}/generate",
                      json={"avatar_id": "daena",
                            "text": beat["text"],
                            "voice_clone": True}, timeout=300)
    if r.ok: save_clip(r.content, beat_clip_path); continue
# Fall through to Pexels / LTX as before
```

Env variables:
- `HEYGEM_URL=http://localhost:9300`
- `HEYGEM_DEFAULT_AVATAR=daena`

Toggle off by clearing `HEYGEM_URL`; pipeline falls through silently.

## VRAM + contention notes for the 4060

HeyGem claims 6-8 GB VRAM for inference. On the 4060 laptop (8 GB total, ~5 GB held by
llama-server), we have the same contention pattern as Wan2GP. Two options:

1. **Sequential**: pause llama-server during HeyGem generate, resume after (needs admin).
2. **Smaller model**: HeyGem supports smaller variants at lower quality. Quantize if they
   publish int8 weights.

Same problem as Wan2GP — solved the same way (microservice orchestration + operator-driven
VRAM handoff).

## Quality gate

Before publishing a video with HeyGem-rendered segments:
- [ ] Lipsync drift ≤ 50ms (human perceptibility threshold for desync)
- [ ] Avatar has same skin tone / lighting as the ambient beats (else jarring cut)
- [ ] No artifacts around mouth / teeth in the 1080p output (zoom to 100% in a player)
- [ ] Voice matches the voice-direction skill's brand-voice profile for the persona

Fails → reject with comment → feedback-loop kicks in (per `approval-feedback-loop` skill).

## Known failure modes

1. **Reference clip too short (<10s)** — output is unstable. Always use at least 12s of
   well-lit, front-facing, neutral-expression reference.
2. **Reference clip with cuts / speaker changes** — HeyGem trains on continuous footage;
   any cut poisons the embedding. Use a single-take reference.
3. **Background music in reference audio** — bleeds into the voice clone. Use a clean mic
   recording with no backing track.
4. **Clothing changes** — the avatar is trained on what the reference wore. If Daena's
   brand evolves wardrobe, re-clone.

## Contract

- **Consumes:** narration beats with `type=talking_head`, reference media in `MODELS_ROOT/heygem/avatars/`
- **Produces:** mp4 clips with lipsynced avatar
- **Calls:** HeyGem microservice on :9300
- **Never:** clones an avatar without operator consent + signed release; publishes a HeyGem
  clip that failed the lipsync quality gate
