---
name: scene-generation
description: "2026 prompt engineering for AI video and scene generation. Covers Veo 3/3.1, Sora 2, Kling 2/3, Runway Gen-4/4.5, LTX-Video, Wan 2.2, HunyuanVideo, and Remotion. Gives generator-specific templates, a shared cinematic vocabulary, and a compose_scene_prompt() helper. Load when the task is writing a prompt for any video/scene generator."
metadata:
  tags: video, veo, sora, kling, runway, ltx, wan, hunyuan, remotion, prompt-engineering, cinematic
---

# Scene Generation - 2026 Prompt Engineering Skill

Templates first. Every generator below lists its optimal prompt schema, a canonical boardroom example, hard limits, negatives that work, and cost/VRAM. Skip to the engine you are driving.

Canonical scene used across all examples:
> "Dark cinematic boardroom, long walnut table, Toronto skyline at dusk through floor-to-ceiling glass, slow dolly push-in toward the head chair."

---

## 1. Veo 3 / 3.1 (Google, Vertex AI)

Docs: Vertex AI `veo-3.1-generate-preview` prompt guide, Sep 2025. Veo 3.1 adds native audio, reference-image continuity, and scene extension up to 148s.

**Structure (field order matters):** `Subject -> Action -> Scene -> Camera -> Composition -> Ambience/Audio -> Style`. Use full sentences. Veo responds well to explicit audio cues in-prompt ("ambient HVAC hum, distant traffic").

**Example:**
```
A sole executive silhouette standing at the head of a long polished walnut boardroom table.
The camera performs a slow dolly push-in from 6 meters away to a medium shot over 8 seconds.
Floor-to-ceiling glass wall reveals the Toronto skyline at dusk, CN Tower dim on the right.
Low-key teal-and-amber practical lighting, deep shadows, shallow depth of field, 35mm anamorphic lens, 2.39:1.
Ambient sound: HVAC hum, faint distant traffic, no dialogue.
Style: prestige-drama cinematography, Roger Deakins reference, subtle film grain.
```

**Limits:** 8s (Veo 3), 8s + extend to 148s (3.1), 720p/1080p, 16:9 or 9:16. **Negatives:** put "no text, no captions, no warped hands, no extra fingers, no lens flare" in the `negative_prompt` field (separate from prompt). **Price:** ~$0.50/sec (1080p) on Vertex AI, audio included.

---

## 2. Sora 2 (OpenAI)

Docs: OpenAI `platform.openai.com/docs/guides/video`, Oct 2025. Sora 2 adds synchronized audio, improved physics, and 20s clips.

**Structure:** short paragraph, then bullet attributes. Sora 2 parses JSON-ish structured blocks reliably - use `{shot, subject, action, setting, lighting, lens, motion, audio, mood}`.

**Example:**
```
A cinematic boardroom scene at dusk. One silhouetted executive at the head of a long walnut table.

{
  "shot": "medium, eye-level, slow dolly-in",
  "subject": "single executive, silhouette only, no face visible",
  "setting": "modern Toronto corner office, floor-to-ceiling glass, CN Tower background",
  "lighting": "low-key, teal key + amber practical table lamps, deep shadows",
  "lens": "35mm anamorphic, shallow DOF, 2.39:1",
  "motion": "dolly push-in over 8s, no pan, no tilt",
  "audio": "HVAC hum, faint city traffic, no speech",
  "mood": "tense, prestige-drama, contemplative"
}
```

**Limits:** 4/8/12/20s, up to 1080p, 16:9 / 9:16 / 1:1. **Negatives:** Sora has no negative field - prepend "AVOID:" line inside the prompt. **Price:** ~$0.10/sec (720p) to $0.50/sec (1080p Pro).

---

## 3. Kling 2 / 3 (Kuaishou)

Docs: `klingai.com/api-docs`, 2026. Kling 3 supports 10s native, Pro mode for physics, and camera-motion tokens.

**Structure:** `[Scene] + [Subject + action] + [Camera: type, movement, speed] + [Style tags]`. Kling is keyword-weighted - use comma-separated tags after the sentence.

**Example:**
```
Dark cinematic boardroom at dusk, a lone executive silhouette at a long walnut table, slow dolly-in camera movement from wide to medium over 8 seconds, Toronto skyline through floor-to-ceiling windows, CN Tower visible,
cinematic, teal and amber color grade, low-key lighting, anamorphic 2.39:1, shallow depth of field, volumetric light, film grain, prestige drama, Roger Deakins style
```

Camera tokens that work: `dolly in, truck left, crane up, arc shot, handheld, static`. **Limits:** 5s or 10s native, Pro extend to 3min, 1080p. **Negatives:** `--neg text, subtitles, distorted hands, extra limbs, cartoon, low quality`. **Price:** ~$0.05-0.10/sec (Std), $0.20/sec (Pro).

---

## 4. Runway Gen-4 / 4.5

Docs: `docs.runwayml.com/gen-4`, 2026. Gen-4.5 is image-to-video-first; text prompts act as *motion direction* on a reference image.

**Structure:** Upload still -> text prompt describes ONLY motion and temporal change, not scene content. Format: `[Camera move] + [subject motion] + [temporal phrase]`.

**Example (with boardroom still image uploaded):**
```
Camera slowly dollies in from wide to medium over 8 seconds.
Executive silhouette remains still at head of table; subtle breathing only.
Outside the glass, city lights in the distance twinkle softly; a single aircraft light drifts right-to-left.
Interior practical lamps flicker faintly once around frame 96.
```

**Limits:** 5s or 10s, 720p/1080p, 16:9/9:16/1:1. **Negatives:** `--no text, hands, distortion, duplicate faces`. **Price:** ~$0.05/sec (Gen-4), ~$0.12/sec (Gen-4.5 Turbo).

---

## 5. LTX-Video (Lightricks, local)

Docs: `github.com/Lightricks/LTX-Video`, v0.9.7 (2026). DiT-based, very fast, runs on 12GB VRAM.

**Structure:** Long dense paragraph, concrete physical nouns, verbs, and lighting terms. LTX is literal - abstract moods do worse than "warm amber light bouncing off polished wood".

**Example:**
```
A cinematic slow dolly push-in shot of a dimly lit modern boardroom at dusk. A long polished dark walnut conference table stretches toward the camera, reflecting warm amber pools of light from overhead pendant fixtures. A single executive figure stands in silhouette at the far head of the table, hands resting on the back of a leather chair. Floor-to-ceiling windows along the right wall reveal the Toronto skyline with the CN Tower dim against a deep blue dusk sky. Teal and orange color grade pushed dark, shallow depth of field, 35mm film grain, anamorphic lens flare suppressed. Camera moves forward smoothly at a constant slow speed for 8 seconds.
```

**Limits:** up to 257 frames (~10s @ 24fps), 768x512 or 1216x704. **Negatives:** `worst quality, low quality, blurry, deformed, cartoon, watercolor, extra fingers, text, watermark`. **VRAM/time:** 12GB (bf16), ~30s for 5s clip on RTX 4090; runs on RTX 4060 8GB with `--offload`.

---

## 6. Wan 2.2 (local)

Docs: `github.com/Wan-Video/Wan2.2`, 2026. MoE diffusion, best open-source quality Q4 2026; T2V-A14B and I2V variants.

**Structure:** English or Chinese, structured `[Scene description]. [Camera]. [Style].` Wan 2.2 responds to explicit physics words ("gravity, weight, inertia").

**Example:**
```
Dark cinematic boardroom at dusk. A lone executive silhouette stands at the head of a long polished walnut table. Floor-to-ceiling glass wall shows Toronto skyline with CN Tower. The camera slowly pushes in from a wide shot to a medium shot over 8 seconds, smooth dolly movement with realistic inertia. Low-key lighting, teal and amber palette, volumetric haze, shallow depth of field, 35mm anamorphic cinematography, prestige drama style, subtle film grain.
```

**Limits:** 5s @ 720p or 480p, 81 frames. **Negatives:** `色调艳丽, 过曝, 静态, 细节模糊, 字幕, 风格化, 画质差, JPEG artifacts, 多余手指, 畸形, 水印` (official Wan 2.2 negative - keep verbatim). **VRAM/time:** 80GB for A14B full; quantized GGUF Q4 runs on 16-24GB in ~4min per 5s clip.

---

## 7. HunyuanVideo (Tencent, local)

Docs: `github.com/Tencent/HunyuanVideo`, v1.5 (2026). 13B DiT, strong text alignment.

**Structure:** 75-150 word paragraph, **subject first**, then action, then scene, then camera, then style. Hunyuan has a known preference for complete sentences over tag lists.

**Example:**
```
A single executive stands in silhouette at the head of a long polished walnut boardroom table. The camera performs a smooth slow dolly push-in from a wide establishing shot to a medium shot over eight seconds, holding steady horizontally. Behind the subject, floor-to-ceiling windows reveal the Toronto skyline at dusk with the CN Tower visible against a deep blue sky. The scene is lit with a low-key teal and amber color grade, warm practical pendant lights above the table cast pools of amber on the wood, shadows are deep and contrasted, a subtle volumetric haze softens distant light sources. Shot on 35mm anamorphic, shallow depth of field, fine film grain, prestige-drama cinematography.
```

**Limits:** 129 frames @ 720p (~5s), or 5s @ 1280x720. **Negatives:** `blurry, low quality, distorted, cartoon, text, watermark, extra limbs, duplicate characters`. **VRAM/time:** 60GB full, FP8 quantized 24GB, ~6min per 5s on RTX 4090.

---

## 8. Remotion (programmatic JSX/React)

Docs: `remotion.dev/docs`, v5 (2026). Not generative - **composes** layers deterministically.

**Structure:** React component with `<Composition>`, `useCurrentFrame()`, `interpolate()`, `spring()`. "Prompt" = Zod schema + props.

**Example:**
```tsx
export const Boardroom: React.FC<Props> = ({skylineSrc, avatarSrc}) => {
  const frame = useCurrentFrame();
  const zoom = interpolate(frame, [0, 240], [1.0, 1.15], {extrapolateRight: "clamp"});
  const vignette = interpolate(frame, [0, 60], [0, 0.6]);
  return (
    <AbsoluteFill style={{background: "#0F1419", transform: `scale(${zoom})`}}>
      <Img src={skylineSrc} style={{filter: "brightness(0.4) hue-rotate(180deg)"}}/>
      <Img src={avatarSrc} style={{position: "absolute", bottom: 0, opacity: 0.9}}/>
      <AbsoluteFill style={{boxShadow: `inset 0 0 400px rgba(0,0,0,${vignette})`}}/>
    </AbsoluteFill>
  );
};
```

**Limits:** any duration, any resolution, deterministic - pairs well with generated clips as `<OffthreadVideo>` layers.

---

## GENERAL PRINCIPLES (applies to all generators)

**Cinematic vocabulary:** shot types = `extreme wide / wide / medium / close-up / extreme close-up / over-the-shoulder / two-shot`. Lenses = `14mm / 24mm / 35mm / 50mm / 85mm / 100mm macro / anamorphic`. Camera moves = `dolly in/out, truck, pan, tilt, crane, jib, handheld, Steadicam, whip pan, crash zoom, parallax, orbit/arc`. Lighting = `low-key / high-key / Rembrandt / rim / practicals / motivated / volumetric / god rays`. Color = `teal-and-orange, day-for-night, bleach bypass, pastel, desaturated, filmic LUT`.

**Composition:** rule of thirds, leading lines, negative space, lead room, depth layers (foreground / midground / background), 2.39:1 for cinema, 16:9 broadcast, 9:16 mobile, 1:1 social.

**Palette hooks that land:** "teal and orange grade pushed dark", "muted Scandinavian pastels", "high-contrast noir with single amber practical", "Kodak Portra 400 reference".

**Motion descriptors:** "slow push-in at constant velocity", "parallax between foreground and skyline", "micro-handheld (3% jitter)", "whip pan right-to-left 0.3s", "crash zoom to close-up on frame 72".

**What to NEVER ask any 2026 generator for:** legible small text, readable signage, more than ~8 seconds of coherent narrative in one clip, two identical faces in frame, precise hands manipulating small objects, accurate brand logos, readable screens, counts above ~6 of identical things, physically interacting twins. Split into multiple clips instead.

---

## Helper: `compose_scene_prompt`

```python
from typing import Literal, Dict

Engine = Literal["veo3", "sora2", "kling3", "runway4.5", "ltx", "wan2.2", "hunyuan", "remotion"]

def compose_scene_prompt(
    scene_description: str,
    persona_brand_palette: Dict[str, str],
    motion_intensity: Literal["still", "subtle", "moderate", "dynamic"],
    engine: Engine = "veo3",
) -> str:
    """Compose an engine-specific prompt from a unified scene spec."""
    palette = f"{persona_brand_palette.get('primary','#0F1419')} base, {persona_brand_palette.get('accent','#D4A843')} accents, {persona_brand_palette.get('secondary','#2DD4BF')} highlights"
    motion_map = {
        "still":    "locked-off camera, no movement, subjects nearly still",
        "subtle":   "slow dolly push-in at constant velocity over the full clip, micro-parallax",
        "moderate": "smooth dolly-in combined with slight arc, gentle parallax across depth layers",
        "dynamic":  "aggressive crash zoom or whip pan with motion blur, handheld feel",
    }
    motion = motion_map[motion_intensity]
    style = f"cinematic, low-key lighting, {palette}, 35mm anamorphic, 2.39:1, shallow depth of field, film grain, prestige-drama reference"
    neg_universal = "no text, no captions, no warped hands, no extra fingers, no duplicate faces, no watermark"

    if engine == "veo3":
        return (f"{scene_description}\nCamera: {motion}.\nStyle: {style}.\n"
                f"Audio: ambient room tone, no dialogue.\nNegative: {neg_universal}.")
    if engine == "sora2":
        return (f"{scene_description}\n\n"
                f'{{"motion":"{motion}","style":"{style}","audio":"ambient room tone, no speech",'
                f'"avoid":"{neg_universal}"}}')
    if engine == "kling3":
        return f"{scene_description}, {motion}, {style} --neg {neg_universal}, low quality, cartoon"
    if engine == "runway4.5":
        return f"{motion}. Subjects hold pose with subtle breathing. Ambient micro-motion in background. --no {neg_universal}"
    if engine == "ltx":
        return (f"{scene_description} {motion}. {style}. "
                f"Negative: worst quality, low quality, blurry, deformed, {neg_universal}.")
    if engine == "wan2.2":
        return (f"{scene_description} Camera: {motion}. Style: {style}. "
                f"Negative: 色调艳丽, 过曝, 静态, 字幕, 画质差, JPEG artifacts, 多余手指, 畸形, 水印.")
    if engine == "hunyuan":
        return (f"{scene_description} The camera {motion}. Lit with {palette}, {style}. "
                f"Negative: blurry, low quality, distorted, cartoon, {neg_universal}.")
    if engine == "remotion":
        return (f"// Remotion composition spec\n"
                f"scene: {scene_description!r}\npalette: {persona_brand_palette}\n"
                f"motion: {motion_intensity} // {motion}\n"
                f"// Implement via <Composition>, interpolate() zoom, <OffthreadVideo> for generated layers")
    raise ValueError(f"Unknown engine: {engine}")
```

**Usage:**
```python
compose_scene_prompt(
    scene_description="Dark cinematic boardroom, lone executive silhouette at long walnut table, Toronto skyline through floor-to-ceiling glass at dusk, CN Tower visible.",
    persona_brand_palette={"primary": "#0F1419", "accent": "#D4A843", "secondary": "#2DD4BF"},
    motion_intensity="subtle",
    engine="veo3",
)
```
