---
name: remotion-composition
description: Remotion as a deterministic composition layer on top of our generative pipeline. Remotion composes React components into frames — perfect for animated lower-thirds, brand intro/outro cards, word-by-word caption reveals, data-viz overlays, and any scripted UI animation. Use when the video needs motion graphics that FFmpeg can't do natively (word-pop captions, animated charts, typewriter text, sticker reveals). Complementary to Wan2GP (generative pixels) and LTX (local generative).
---

# Remotion Composition Skill

## The role of Remotion in the stack

Three layers of video creation — one tool per job:

| Layer | Tool | Output | What it does |
|---|---|---|---|
| **Generative** | Wan2GP / LTX / HeyGem | AI-generated pixels | Hero scenes, cinematic b-roll, talking avatars |
| **Compositional** | **Remotion** | Deterministic React → frames | Lower-thirds, caption animation, brand cards, data viz |
| **Assembly/Encode** | FFmpeg + NVENC | MP4 file | Concat, encode, audio mux |

Wan2GP paints scenes. HeyGem animates faces. Remotion animates UI. FFmpeg glues them together.

Right now we have no Remotion in the pipeline — captions are burned via libass (static,
hard to animate). Adding Remotion unlocks the Hormozi word-pop style, MrBeast staggered
drops, animated lower-thirds for source citations, and branded intro/outro cards.

## When to add a Remotion beat vs pure FFmpeg overlay

Use Remotion when:
- Captions need word-by-word animation timing (Hormozi pop, gold highlight on stressed word)
- You want a brand intro card with your logo + tagline animating in
- A data point in narration needs an animated chart ("72% of SaaS companies…")
- Stickers / emoji motion in the corner (SaySo-style verification badge, News Loop-style source cite)

Use FFmpeg (what we have now) when:
- Caption is simple block text that sits still
- Burn-in during the final encode pass is enough
- No per-word timing needed

## Install runbook (when we get to it — not today)

```powershell
# Node ecosystem, not Python. Lives alongside contentops-core.
cd D:\Ideas\contentops-core
mkdir remotion
cd remotion
npm init video@latest          # Remotion's scaffolding CLI, picks a template
# Pick "Hello World" as base, we'll replace with our components
npm install

# Remotion needs a Chromium for rendering
npx remotion chrome            # downloads the bundled Chromium to D:\ if HOME is D:
```

After scaffold, the directory looks like:
```
contentops-core/remotion/
├── src/
│   ├── Root.tsx                 # composition registry
│   ├── Video.tsx                # root video component
│   └── components/
│       ├── HookCaption.tsx      # Hormozi word-pop
│       ├── LowerThird.tsx       # source citation animated band
│       ├── BrandCard.tsx        # intro/outro with Daena logo
│       └── DataViz.tsx          # animated bar/line chart
├── remotion.config.ts
├── package.json
└── tsconfig.json
```

## Integration with the contentops pipeline

Add a new beat type: `composed`. When the beat-planner sees a data point or a brand moment,
it emits `beat.type = "composed"` with a `composition_id` and `props` (JSON data the React
component consumes).

`contentops/video_render.py` gets a new beat resolver:

```python
if b["type"] == "composed":
    # Render the composition to MP4 via Remotion CLI
    props_json = json.dumps(b["props"])
    subprocess.run([
        "npx", "remotion", "render",
        "src/Video.tsx", b["composition_id"],
        "--props", props_json,
        "--output", str(beat_clip_path),
        "--codec", "h264", "--crf", "20",
    ], cwd="remotion", check=True, timeout=120)
```

Or — cleaner — wrap as a Flask microservice at `services/remotion/server.py` following
the same pattern as Daena TTS + Wan2GP:
```
POST /render {composition_id, props, duration_s} → MP4 bytes
```

## Component design guidelines

### HookCaption.tsx (Hormozi word-pop)
```tsx
import {useCurrentFrame, interpolate, spring, AbsoluteFill} from 'remotion';

export const HookCaption: React.FC<{words: {text: string; start: number; end: number}[]}> = ({words}) => {
  const frame = useCurrentFrame();
  const fps = 30;
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      {words.map((w, i) => {
        const startFrame = w.start * fps;
        if (frame < startFrame || frame > w.end * fps + 10) return null;
        const scale = spring({fps, frame: frame - startFrame, config: {damping: 8}});
        return <span key={i} style={{
          fontFamily: 'Montserrat Black', fontSize: 72,
          color: i === 2 ? '#FFD500' : 'white',  // gold highlight every 3rd word
          transform: `scale(${scale})`,
          textShadow: '0 4px 0 black',
        }}>{w.text}</span>;
      })}
    </AbsoluteFill>
  );
};
```

Timing data comes from our existing Whisper word-level transcripts. Pipeline flow:
1. Whisper transcribes narration → word-level timestamps (already happens)
2. `beat_plan` emits caption beats as `composed` with `composition_id=HookCaption`
3. Remotion renders → transparent-bg MP4 with captions only
4. FFmpeg overlays that MP4 on top of the b-roll MP4 (alpha blend)

### LowerThird.tsx (source citation)
Band at the bottom showing "Source: wheresyoured.at" sliding in. 30-frame slide-in from the
left via `interpolate()`, holds for the beat's duration, slides out.

### BrandCard.tsx (intro/outro)
Daena logo assembles from particles → reveals tagline → cuts to black. Reusable as both the
first 1.5s and the last 2s of every video. Props: `{mode: 'intro' | 'outro', tagline?: string}`.

## VRAM / GPU notes

Remotion renders via Chromium — this is CPU/GPU-via-browser, NOT the diffusion GPU.
So Remotion render can run SIMULTANEOUSLY with Wan2GP or HeyGem without VRAM contention.
That's a big win on the 4060 where VRAM is our bottleneck. Render compositions during
the Wan2GP beats, not sequential.

## Quality gate

- [ ] Composition renders at 1080×1920 9:16
- [ ] Frame rate matches pipeline (30 fps default)
- [ ] Alpha channel preserved when overlaying on generative b-roll (use `-pix_fmt yuva420p`)
- [ ] Timing matches Whisper word-level transcript within 1 frame
- [ ] Brand colors match MAS-AI design system: `#0F1419 / #D4A843 / #2DD4BF`
- [ ] Safe zones respected: 270px top + 340px bottom reserved for platform UI

## Contract

- **Consumes:** beat plan with `type=composed`, Whisper word timings, MAS-AI brand tokens
- **Produces:** 1080×1920 MP4 clips (typically with alpha) that FFmpeg overlays on other layers
- **Calls:** `npx remotion render` or Remotion HTTP service
- **Never:** renders a composition larger than the beat's visual duration; ignores brand palette
- **Pairs with:** `edit-choreography` (caption style selection), `universal-shortform-director`
  (scene type routing), `news-to-video` (beat type emission)

## Why not implement today

Remotion is Node + React, a different ecosystem from our current Python pipeline. Adding it
right is ~6-8 hours:
1. Scaffold the Remotion project (~1h)
2. Write 3 core components: HookCaption, LowerThird, BrandCard (~3h)
3. Microservice wrapper at services/remotion/server.py (~1h)
4. Pipeline integration — new beat type + resolver in video_render.py (~1h)
5. Test + tune timing alignment against Whisper transcripts (~2h)

Schedule this AFTER Wan2GP is installed + producing cinematic beats. At that point
captions become the biggest remaining quality gap, and Remotion is the correct fix.
