---
name: wan2gp-8gb
description: Wan2GP video-generation microservice tuning for 8 GB laptop GPUs (RTX 4060/4070). Use when installing, operating, or debugging the contentops-core wan2gp service, picking between Wan 2.1 / Wan 2.2 / LTX-2 on an 8 GB card, or diagnosing VRAM OOMs / C-drive cache leaks.
---

# Wan2GP on 8 GB laptop GPUs -- tuning + operations playbook

## When to invoke this skill

- Installing `services/wan2gp/` for the first time on a new machine
- Picking which Wan2GP model to use per-beat (Wan 2.1 vs 2.2 vs LTX-2 vs GGUF)
- Debugging `torch.cuda.OutOfMemoryError` during generation
- Cache leaked to C: drive (HuggingFace cache somewhere other than `D:\Ideas\MODELS_ROOT`)
- Porting to a different 8 GB card (RTX 4070 Mobile, RTX 3060 Ti, etc.)

## The hardware constraint

```
RTX 4060 Laptop:  8 GB VRAM, compute 8.9 (Ada)
Driver:           581.x+  (supports CUDA 13 runtime)
System:           Windows 11, 16-32 GB system RAM
```

At 8 GB VRAM, every Wan2GP model needs **profile 4 + quantization** to fit.
Profile 3 (all weights in VRAM) needs 24+ GB and will OOM immediately.

## The 5 settings that matter (in order of impact)

### 1. Profile: must be 4 (mmgp block swap). Never 3.

```bash
--profile 4
```

Profile 4 = "load model parts as needed, most flexible". mmgp (the memory profiler
in `requirements.txt`) uses this to stream transformer blocks between VRAM and
system RAM across denoising steps. For Wan 2.2's two-phase MoE, only one phase's
weights are in VRAM at a time; the switch at `switch_threshold: 875` swaps them.

### 2. Attention: sdpa (safe) or sage2 (40% faster, RTX 40XX only)

```bash
--attention sdpa   # default, works everywhere
--attention sage2  # needs triton-windows + the cu130 wheel below
```

Sage2 install (RTX 40XX/50XX only):
```powershell
pip install triton-windows
pip install "https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post4/sageattention-2.2.0+cu130torch2.9.0andhigher.post4-cp39-abi3-win_amd64.whl"
```

If triton fails to compile on your box, fall back to sdpa. Don't fight it.

### 3. Quantization: INT8 for Wan 2.2, fp8 for LTX-2, bf16 for Wan 2.1

Wan 2.2 ships three checkpoint variants in the same `t2v_2_2.json` config:
- `_mbf16.safetensors` (14 GB, needs 14+ GB VRAM -- skip)
- `_quanto_mbf16_int8.safetensors` (~7 GB, fits in 8 GB with profile 4) <- pick this
- `_quanto_mfp16_int8.safetensors` (alternative INT8 encoding)

Wan2GP auto-picks based on GPU detection, but verify post-download:
```powershell
Get-ChildItem "D:\Ideas\MODELS_ROOT\hf\hub\models--DeepBeepMeep--Wan2.2" -Recurse -Name
# Should contain quanto_mbf16_int8.safetensors, not just _mbf16.safetensors.
```

### 4. Resolution: 512x896 is the 8 GB sweet spot for portrait/social video

Memory cost scales O(W*H*F) for the transformer. 512x896 portrait 9:16 (97 frames
@ 24fps = 4s) fits comfortably with profile 4 + INT8. 768x1344 will OOM on the
14B model even with profile 4.

Frame count must be `8n + 1` for video DiTs. 97, 121, 145, 169 are legal.

### 5. MODELS_ROOT env vars: set BEFORE first torch import

```powershell
# PERSIST to user profile (setx writes to registry):
setx MODELS_ROOT        "D:\Ideas\MODELS_ROOT"
setx HF_HOME            "D:\Ideas\MODELS_ROOT\hf"
setx HF_HUB_CACHE       "D:\Ideas\MODELS_ROOT\hf"
setx TRANSFORMERS_CACHE "D:\Ideas\MODELS_ROOT\hf"
setx TORCH_HOME         "D:\Ideas\MODELS_ROOT\torch_cache"
setx WAN2GP_MODELS_DIR  "D:\Ideas\MODELS_ROOT\wan2gp"
```

Then open a **new** shell -- setx writes to registry, doesn't update the current
session. The service's `server.py` also sets these via `os.environ.setdefault`
before `from shared.api import init` runs, as a belt-and-suspenders measure.

## Model picks cheat sheet

| Friendly ID | model_type | VRAM | 5s clip | Best for |
|---|---|---|---|---|
| `wan2.1` | `t2v_1.3B` | ~4 GB | ~30-45s | Default. Most beats. Iteration. |
| `wan2.2` | `t2v_2_2` | ~7-8 GB | ~90-120s | Cinematic quality. Hero shots. |
| `ltx2` | `ltx2_distilled` | ~7-8 GB | ~60-80s | Strong motion physics. 8 steps. |
| `ltx2_gguf` | `ltx2_22B_distilled_gguf_q4_k_m` | ~6 GB | ~80-100s | Safest fallback. GGUF Q4. |

**Never on 8 GB** (would need 12+ GB even optimized):
- hunyuan_1_5_t2v (13B)
- wan2.2 a14b non-quantized bf16
- ltx2 22B bf16

## The GPU-poor architecture

Wan2GP's secret is `mmgp==3.7.6` -- a memory profiler that:
1. Tracks which transformer blocks are needed for the current denoising step
2. Keeps "upcoming" blocks in pinned system RAM (fast transfer)
3. Streams them into VRAM just before they're called
4. Evicts "past" blocks to reclaim VRAM

For Wan 2.2's two-phase MoE:
- **Phase 1 (high-noise, steps 0..threshold)**: high-noise expert weights in VRAM
- **Switch at step = switch_threshold (875 by default for t2v_2_2)**
- **Phase 2 (low-noise, steps threshold..end)**: low-noise expert weights swap in

This is the ONLY way a 14B model fits on 8 GB VRAM. It costs a ~15-25% latency
hit vs having all weights resident (profile 3), but profile 3 needs a 24 GB card.

## Common failure modes

### HuggingFace cache leaking to C:
Sign: `dir "C:\Users\<you>\.cache\huggingface"` shows multi-GB files.
Cause: `HF_HOME` wasn't set when torch/diffusers first imported.
Fix:
1. Kill any running Wan2GP processes: `Get-Process python | Stop-Process -Force`
2. Move leaked cache: `Move-Item "$env:USERPROFILE\.cache\huggingface\*" "D:\Ideas\MODELS_ROOT\hf\" -Force`
3. Nuke the empty dir: `Remove-Item "$env:USERPROFILE\.cache\huggingface" -Recurse -Force`
4. Verify env vars: `setx HF_HOME "D:\Ideas\MODELS_ROOT\hf"` (re-run if needed)
5. **Open a fresh shell** and restart the service.

### OOM during Wan 2.2 generation
Sign: `torch.cuda.OutOfMemoryError` at step 0 or the phase-switch point.
Cause: wrong checkpoint variant downloaded (bf16 instead of int8).
Fix: delete `D:\Ideas\MODELS_ROOT\hf\hub\models--DeepBeepMeep--Wan2.2` and
re-trigger download; Wan2GP should pick INT8 based on available VRAM.

### `session init failed: ImportError`
Cause: `mmgp` or `onnxruntime-gpu` failed to install (common with numpy 2.1.2 mismatch).
Fix: `.\.venv\Scripts\python.exe -m pip install -r Wan2GP\requirements.txt --force-reinstall --no-deps mmgp onnxruntime-gpu`

### Install script hangs at "Building wheels for insightface"
Cause: insightface on Windows uses a pre-built wheel hosted on
github.com/deepbeepmeep/insightface. If GitHub is slow, pip falls through to
sdist build which needs MSVC.
Fix: retry; if still hanging, download the wheel directly:
```powershell
$wheel = "https://github.com/deepbeepmeep/insightface/releases/download/insightface/insightface-0.7.3-cp311-cp311-win_amd64.whl"
Invoke-WebRequest $wheel -OutFile insightface.whl
.\.venv\Scripts\python.exe -m pip install insightface.whl
```

## Integration with contentops pipeline

`contentops/ltx_render.py` has a Tier-0 check for `WAN2GP_URL`. When set, it
POSTs to the wan2gp service; on any failure, it falls through to local LTX.

```python
# In contentops/ltx_render.py (existing pattern):
if os.environ.get("WAN2GP_URL"):
    try:
        r = requests.post(
            f"{os.environ['WAN2GP_URL']}/generate",
            json={
                "model":      os.environ.get("WAN2GP_MODEL", "wan2.1"),
                "prompt":     prompt,
                "duration_s": duration_s,
                "width":      width, "height": height, "fps": fps, "steps": 8,
            },
            timeout=600,
        )
        if r.ok:
            return r.content  # video/mp4 bytes
    except Exception:
        pass  # fall through to local LTX
# Existing LTX local path follows...
```

## Speed expectations (RTX 4060 Laptop 8 GB, profile 4)

| Model | Attention | 5s clip @ 512x896 | Notes |
|---|---|---|---|
| wan2.1 (t2v_1.3B) | sdpa | ~35s | Fastest; lowest quality |
| wan2.1 (t2v_1.3B) | sage2 | ~22s | 40% faster, small quality cost |
| wan2.2 (t2v_2_2 INT8) | sdpa | ~110s | Best quality at 8 GB |
| wan2.2 (t2v_2_2 INT8) | sage2 | ~70s | Sweet spot for hero shots |
| ltx2_distilled fp8 | sdpa | ~75s | Strong motion, 8 steps |
| ltx2_gguf_q4_k_m | sdpa | ~95s | Conservative fallback |

## Related files
- `D:/Ideas/contentops-core/services/wan2gp/server.py` -- HTTP wrapper
- `D:/Ideas/contentops-core/services/wan2gp/install_rtx4060.ps1` -- install script
- `D:/Ideas/contentops-core/services/wan2gp/README.md` -- user-facing install runbook
- `D:/Ideas/contentops-core/services/wan2gp/Wan2GP/docs/API.md` -- upstream API docs
- `C:/Users/masou/.claude/skills/ltx-gpu-config/SKILL.md` -- companion skill for pure LTX tuning
