---
name: ltx-gpu-config
description: LTX-Video GPU configuration playbook for 8GB laptop GPUs (RTX 4060/4070/etc). Use when setting up LTX-Distilled for AI video generation in the contentops-core pipeline, or debugging VRAM OOMs during diffusion.
---

# LTX-Video on 8GB laptop GPUs — the non-crashing configuration

## When to invoke this skill

- Setting up `contentops.ltx_render` on a new machine
- Debugging `torch.cuda.OutOfMemoryError` during LTX generation
- Tuning speed/quality tradeoffs for the contentops video pipeline
- Porting LTX to a different card (3060 12GB, 4070 8GB, 4080 16GB etc)

## The 5 settings that matter (in order of impact)

### 1. Runtime: PyTorch wheel must match your driver

```bash
# For RTX 40-series / Ada (compute 8.9), CUDA 12.8 toolkit installed:
pip install torch==2.11.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu128

# Verify:
python -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"
```

PyTorch wheels bundle their own CUDA runtime. You do NOT need the matching CUDA toolkit installed on the system, only the driver. Driver 581.x supports CUDA 13 runtime, so cu128 wheels work fine.

### 2. Precision: bf16, not fp16, not fp32

```python
LTXPipeline.from_pretrained(LTX_REPO, torch_dtype=torch.bfloat16)
```

Ada cards have native bf16 — it's as fast as fp16 but with fp32-range exponent, which matters for diffusion stability. fp32 will OOM. fp16 can underflow in VAE decode.

### 3. VAE tiling: decode memory bounded, not video-length-proportional

```python
pipe.vae.enable_tiling()
```

Without this, the VAE decode step holds the entire (B, C, F, H, W) latent volume in memory. For a 5-second 512x896 clip that's ~1.8 GB on top of the transformer — enough to OOM. Tiling decodes in overlapping 2D patches; memory becomes constant.

### 4. Attention slicing: bounded QKV memory

```python
pipe.enable_attention_slicing("auto")
```

The LTX transformer's attention has O(frames²) memory. Slicing breaks the softmax into chunks — ~5% latency hit, ~40% memory savings on the transformer.

### 5. Allocator: expandable segments, not rigid slabs

```python
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:512"
```

Default PyTorch allocator slabs can leave 1-2 GB of VRAM fragmented and unusable between steps. Expandable segments = ~15% effective VRAM reclaim.

## What NOT to do (these are traps)

- **Do not use `enable_model_cpu_offload()`** for the 4060. It swaps modules GPU↔CPU between inference steps. LTX-Distilled is 8 steps, so that's 8× the PCIe transfer cost. With our config above you don't need it — transformer + T5 + VAE all fit on GPU at bf16.
- **Do not torch.compile()** the pipeline for 1-2 clips per video. First-run compile is 90s+; only pays back if you render >50 clips per process lifetime.
- **Do not ask for >5s duration** on an 8GB card. VRAM and time both scale super-linearly.

## Speed expectations (RTX 4060 Laptop 8GB)

| Config | 5s clip @ 512×896, 8 steps |
|---|---|
| CPU-only torch (old) | ~8-15 minutes |
| CPU-offload bf16 | ~90-120 s |
| **Optimized (this skill)** | **~25-40 s** |

## Fallback cascade (in the production code)

1. Try requested resolution
2. On `OOMError`, clear cache and retry at 384×640
3. If still OOM, return `False` → caller falls back to Pexels stock clip
4. If LTX is structurally broken (no CUDA), return `False` immediately — never block the pipeline

## Related files

- `D:/Ideas/contentops-core/contentops/ltx_render.py` — implementation
- `D:/Ideas/contentops-core/contentops/video_render.py` — `render_script()` wires LTX for beats in `LTX_ENABLE_BEATS` env
- `D:/Ideas/contentops-core/.env` — `LTX_ENABLE_BEATS`, `LTX_WIDTH`, `LTX_HEIGHT`, `LTX_STEPS`, `FFMPEG_ENCODER`
