# Sabrina Ramonov's Claude Code + Remotion Prompt Library

> Companion to the `remotion-video` skill. Captures the exact prompts and design
> system Sabrina Ramonov (sabrina.dev, @sabrina_ramonov, 500K+ followers, Forbes
> 30 Under 30, founder of Blotato.com) uses for Claude Code + Remotion video
> production. Reverse-engineered 2026-05-01 from her articles and YouTube videos.
>
> Source articles:
> - https://www.sabrina.dev/p/claude-just-changed-content-creation-remotion-video
> - https://www.sabrina.dev/p/5-insane-claude-code-video-prompts
> - https://www.sabrina.dev/p/claude-remotion-unlocks-unlimited
>
> Source videos (YouTube @sabrina_ramonov):
> - xrydO6E3fT0 — "Claude Code Just Changed Videos Forever! (Tutorial)" (28 min)
> - FAeVq2SyIaw — "Make Unlimited AI Video for Free with Claude!" (50 min)
> - rabGqnyd_Zw — "7 Secret Prompts That Make Claude 10x Better" (10 min)

## Setup

```bash
# Create project (choose Blank template, enable TailwindCSS)
npx create-video@latest

# Install Remotion's official Claude Code skills (per-project)
cd <project-name>
npx skills add remotion-dev/skills

# Start Remotion Studio for live preview
npx remotion studio

# Start Claude Code in the project
claude
```

The `remotion-video-skill` (this skill) is also available globally — invoke it
by saying "Remotion", "用代码做视频", or `/remotion-video`. It includes MiniMax
TTS + Edge TTS integration scripts that the per-project install lacks.

## Universal design system (apply to every prompt)

| Spec | Value |
|---|---|
| Resolution | 1080×1920 (9:16 vertical) |
| Frame rate | 30 fps |
| **Top safe zone** | 150px (platform status bars) |
| **Bottom safe zone** | 170px (nav buttons, swipe-up UI) |
| **Side safe zones** | 60px |
| Headlines min size | 56px |
| Body/subtitles min | 36px |
| Labels/small text min | 28px (absolute floor) |
| Entrance animation | `spring({ damping: 200 })` |
| Stagger delay | 8-12 frames between related items |
| Scene transitions | `TransitionSeries` with 12-frame fade |
| Number counters | `interpolate()` + `tabular-nums` font-variant |
| SVG draw effect | `stroke-dashoffset` interpolation |

## Prompt 1 — Education explainer video (30s)

**Use case:** Explain any topic in 30s vertical animated explainer.

**Setup verbatim from Sabrina:**
> "use remotion skill to create a 9:16 30-second explainer video on this topic: <YOUR TOPIC>
> - first 3 seconds = pattern-interrupt hook
> - 5 scenes total: hook → problem → mechanism → proof → CTA
> - dark background #0a0a0a, white text, indigo accent #6366f1, success green #22c55e
> - Inter font (weights 400, 600, 800)
> - SVG diagrams that draw themselves via stroke-dashoffset
> - count-up animations for any numbers using interpolate + tabular-nums
> - particle effect on final CTA scene (10-15 drifting circles)
> - safe zones: 150px top / 170px bottom / 60px sides
> - headlines >= 56px, body >= 36px"

**Output:** Full explainer with self-drawing diagrams, count-up numbers, fade
transitions, particle CTA scene.

## Prompt 2 — Product demo / launch video (25s)

**Use case:** Auto-generated promo from any product URL.

**Setup verbatim:**
> "use remotion skill to create a 9:16 25-second product launch video for <URL>
> - scrape the website for: logo, brand colors, tagline, real product images (NOT screenshots — use the marketing images the site already displays)
> - 6 scenes: hook → product intro → simulated mobile UI demo → real product image showcase → feature callouts → social proof + CTA
> - simulated UI: mobile-sized, 12px white circle cursor with 50% opacity trailing shadow, smooth bezier motion, click ripples, character-by-character text input at 36px, loading spinners, staggered result animations
> - product images displayed at 900px+ width with crossfade transitions
> - feature headlines at 56px
> - safe zones: 150 / 170 / 60"

**Why it works (Sabrina's note):** "Product images the site already displays
look much better than browser screenshots."

## Prompt 3 — Google Reviews testimonial (20s)

**Use case:** Social proof from a Google Business Profile URL.

**Setup verbatim:**
> "use remotion skill to create a 9:16 20-second social proof video from this Google Business Profile: <URL>
> - scrape: business name, star rating, review count, top 3 reviews
> - 5 scenes: hook → animated star-fill → review carousel (3s each card) → social proof counter stack → CTA
> - light theme: bg #f8f9fa, cards #ffffff, gold accent #f59e0b
> - each review card: 5 stars, review text 36px max 3 lines, reviewer name, Google 'G' logo, progress dots
> - safe zones: 150 / 170 / 60"

## Prompt 4 — Avatar overlay video (variable length)

**Use case:** Take a 9:16 talking-head video, overlay synced animated graphics
WITHOUT cropping the original.

**Setup verbatim:**
> "use remotion skill: take ~/Downloads/avatar.mp4 (9:16 talking head)
> - transcribe with Whisper, identify 3-5 topic segments
> - overlay graphics ONLY in the top 35% of the frame (above head space) — original video stays full-frame untouched edge-to-edge
> - per segment: faded background step number ~200px at 8% opacity + topic headline 56-64px + keyword badge with glassmorphism + progress bar
> - optional: word-level captions at bottom 36px, current word highlighted in #6366f1
> - never cover the speaker's face"

**Why it works:** "Original video remains full-frame and untouched while
graphics layer on top."

## Prompt 5 — Data viz dashboard (15s)

**Use case:** CSV → animated dashboard infographic.

**Setup verbatim:**
> "use remotion skill: read ~/Downloads/data.csv
> - identify the most impressive KPI as the hero metric
> - 4 vertically-stacked panels with 30px spacing, top margin 150px
> - panel 1: hero KPI card with count-up animation (interpolate + tabular-nums)
> - panel 2: horizontal bar chart with staggered growth
> - panel 3: donut/pie chart with rotating segment-draw
> - panel 4: line chart with gradient fill reveal
> - glassmorphism cards rgba(255,255,255,0.05), bar gradient #6366f1 → #8b5cf6, line chart #22c55e
> - 15-second total duration, 1080x1920 30fps"

## Sabrina's 4-step iteration workflow

After the initial render, she chains correction prompts:

```
1. (initial generation prompt — one of the 5 above)
2. "update the video: fact check <claim>; one scene per <item>; for each
    take a web screenshot and incorporate it; update CTA to <call to action>"
3. "incorporate my headshot from ~/Downloads in the last screen CTA, add some
    techno/edm/psychedelic background music"
4. "edit the latest video in ~/Downloads, remove mistakes, add a scroll-
    stopping tiktok-style title, add subcaptions but don't cover my face,
    be mindful of 9:16 safe zones"
```

Then publish:
```
"lets schedule the motion graphics video for instagram in 30 minutes using Blotato MCP"
```

## Pro tips (verbatim from her articles)

1. **Always start the prompt with** "Use the Remotion best practices skill" — this
   primes Claude to load the per-project remotion-dev/skills first.
2. **Iterate with correction prompts** after first render: "make bars wider",
   "slow typing", "change color to #FFD700".
3. **Visual control sliders** — for prompts 2 (Product Demo) and 4 (Avatar),
   add a `controls` panel in Remotion Studio for manual tweaking before final render.
4. **Template approach** — "If you're serious about using Remotion for editing
   existing videos, set aside a few days to build a template fitting YOUR style."
5. **Editing limitation** — blooper removal in existing footage is imperfect with
   rough preview transitions (smoother in final renders). Motion graphics
   generation is reliable; editing existing footage requires more iteration.
6. **Always manually approve before publishing** — no auto-post, even with Blotato.

## Render commands

```bash
# Live preview
npx remotion studio

# Render MP4
npx remotion render MyVideo out/video.mp4

# H.264 explicit
npx remotion render --codec=h264 MyVideo out/video.mp4

# Single still frame
npx remotion still MyVideo --frame=30 out/thumbnail.png

# Quality dial
npx remotion render --crf 18 MyVideo out/video.mp4   # lower = better, 18 default
```

## What this gives our pipeline that vibefounder doesn't

| Capability | Vibefounder style | Sabrina/Remotion style |
|---|---|---|
| Visual b-roll engine | Wan2GP / LTX (AI video gen) | Remotion (programmatic React) |
| Style consistency | Per-render prompt drift | Same template = identical brand every time |
| Iteration cost | Re-generate from scratch | Edit React props, instant re-render |
| Determinism | Stochastic | 100% deterministic |
| Hardware load | 4-8 GB VRAM per beat | CPU only — no GPU needed |
| Speed per 30s reel | 3-5 min | 30-60 seconds |
| Cost | GPU electricity | Free (Claude Code subscription) |

**Routing decision:** Use Remotion-style for branded/templated content where
consistency matters (data viz, product demos, news explainers). Use vibefounder/
Wan2GP for stylized "look like Midjourney comic art" reels where AI-gen is the
visual selling point.

## Operator memory hooks

- Sabrina = sabrina.dev = Sabrina Ramonov = Blotato founder = @sabrina_ramonov
- Trigger words: "Sabrina-style", "Remotion", "Sabrina prompt", "use that
  Remotion thing", "the React video thing"
- Default to Prompt 1 (explainer) when topic is "explain X"
- Default to Prompt 2 (product demo) when input is a product URL
- Default to Prompt 3 (testimonials) when input is a Google Business Profile
- Default to Prompt 4 (avatar overlay) when input is a talking-head mp4
- Default to Prompt 5 (data viz) when input is a CSV
