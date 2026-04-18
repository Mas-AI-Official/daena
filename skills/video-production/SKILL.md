---
name: video-production
description: "Complete video production skill: AI video generation (Seedance 2.0, LTX, Kling, Higgsfield), FFmpeg compositing, Remotion templates, avatar lip-sync, voice-over-to-scene sync pipeline, short-form + long-form (YouTube), marketing/influencer content. Use for ANY video creation task."
metadata:
  tags: video, seedance, ltx, kling, higgsfield, ffmpeg, remotion, avatar, voiceover, lip-sync, youtube, tiktok, reels, marketing, influencer, content, long-form, short-form, cinematic
---

# Video Production Skill

The complete video creation skill for MAS-AI / ContentOps.
Covers every step from research to rendered video to platform-ready export.

## When to activate

- User asks to create, edit, produce, or render any video
- Working with AI video generation (Seedance 2.0, LTX, Kling, Higgsfield)
- Compositing avatar overlays, B-roll, captions, music
- Voice-over-to-scene sync (avatar says X, visuals must show X)
- Short-form (TikTok, Reels, Shorts) or long-form (YouTube 8-60min)
- Marketing videos, influencer content, product demos, explainers
- Any FFmpeg or Remotion video work

## Rule Files (load as needed)

| Rule File | When to load |
|---|---|
| [rules/ai-video-engines.md](rules/ai-video-engines.md) | Generating video clips with AI (Seedance 2.0, LTX, Kling, Higgsfield) |
| [rules/voiceover-scene-sync.md](rules/voiceover-scene-sync.md) | Syncing avatar speech to matching visuals (the #1 gap this skill fills) |
| [rules/long-form-production.md](rules/long-form-production.md) | YouTube videos, explainers, tutorials (8-60 min) |
| [rules/cinematic-principles.md](rules/cinematic-principles.md) | 2026 filmmaking trends and creative direction |
| [rules/ffmpeg-recipes.md](rules/ffmpeg-recipes.md) | FFmpeg command recipes for compositing and post-production |
| [rules/platform-specs.md](rules/platform-specs.md) | Platform-specific video requirements (TikTok, YouTube, IG, LinkedIn) |
| [rules/quality-gates.md](rules/quality-gates.md) | Provider scoring, slideshow risk, checkpointing, budget governance |
| [rules/local-first-setup.md](rules/local-first-setup.md) | Local hardware setup: RTX 4060 8GB, model locations, VRAM budget |
| [rules/content-scraping.md](rules/content-scraping.md) | RSS feeds, influencer monitoring, YouTube transcript scraping, react pipeline |

For Remotion-specific code patterns, load the **remotion-best-practices** skill instead.

**LOCAL-FIRST STRATEGY:** This system prioritizes Remotion (programmatic) + FFmpeg (compositing)
+ local AI gen (LTX 2B, Wan 2.1) over cloud APIs. Cloud APIs (Seedance, Kling) are last resort
for lip-sync and hero shots only. Load [rules/local-first-setup.md](rules/local-first-setup.md) for details.

## Tool Stack

### AI Video Generation (scene creation)

| Engine | Best For | API | Cost | Max Duration |
|---|---|---|---|---|
| **Seedance 2.0** | Lip-sync, avatar scenes, multi-ref | fal.ai (`bytedance/seedance-2.0/*`) | ~$0.14-0.30/sec | 15s/clip |
| **LTX 2.3** | Open-source, self-hosted, long clips | fal.ai / local (Lightricks) | Free (local) or API | 60s/clip |
| **Kling 3.0** | Longest native gen, cheapest | Kuaishou API | ~$0.10/sec | 5min/clip |
| **Higgsfield** | Multi-model orchestration, character consistency | higgsfield.ai API | Credit-based | Varies |

### Post-Production (compositing + rendering)

| Tool | Role |
|---|---|
| FFmpeg 7.1 | Primary compositor: B-roll, overlay, captions, mux, color grade, transitions |
| Remotion | React-based templates: advanced animations, typed props, programmatic video |
| faster-whisper | Word-level caption timestamps for subtitle sync |

### Audio

| Tool | Role | When |
|---|---|---|
| Kokoro TTS | Free local voice | Draft/test mode |
| ElevenLabs | Premium voice (Matilda voice for Daena) | Production (approved content) |
| Coqui XTTS v2 | Voice cloning, multilingual | Custom voice personas |

### Assets

| Tool | Role |
|---|---|
| Pexels API | Free stock B-roll library |
| AI-generated scenes | Seedance/LTX/Kling for custom visuals matching voiceover |

## Core Pipeline: Voice-Over-to-Scene Sync

This is the critical workflow that was missing. The avatar says something, and the visuals MUST match what is being said -- not random B-roll.

```
1. RESEARCH     -> Gather information on the topic (web search, docs, data)
2. SCRIPT       -> Write narrative script (what avatar says) + production notes
3. VOICE        -> Generate TTS audio from narrative script
4. BEAT MAP     -> Transcribe audio -> word-level timestamps -> segment into beats
5. SCENE PLAN   -> For each beat: describe the VISUAL that matches the spoken content
6. GENERATE     -> Use AI engine to create each scene (Seedance for lip-sync, LTX for B-roll)
7. ALIGN        -> Trim/stretch each generated clip to match its beat duration
8. COMPOSITE    -> Layer: background scene + avatar overlay + captions + music
9. REVIEW       -> Watch full video, check sync, adjust timing
10. EXPORT      -> Render to platform specs
```

**Key rule:** Scene visuals are DERIVED from voiceover content, never independent.
Load [rules/voiceover-scene-sync.md](rules/voiceover-scene-sync.md) for the full pipeline spec.

## Engine Selection Matrix

Choose the right engine per scene type:

| Scene Type | Best Engine | Why |
|---|---|---|
| Avatar talking (lip-sync) | Seedance 2.0 | Native phoneme-level lip-sync, best in class |
| Avatar talking (budget) | LTX 2.3 + FFmpeg overlay | Free local, avatar composited via colorkey |
| B-roll matching narration | Seedance 2.0 or Kling 3.0 | Text-to-video from scene description |
| Long continuous shot (>15s) | Kling 3.0 | 5-minute native generation |
| Data visualization / charts | Remotion | Programmatic, typed props, animations |
| Screen recording / tutorial | FFmpeg + Remotion | Capture + overlay + captions |
| Multi-character scene | Higgsfield (Soul Cast) | Consistent characters across shots |
| Image-to-video animation | Seedance 2.0 (image-to-video) | Best image animation quality |
| Self-hosted / offline | LTX 2.3 local | Open-source, runs on RTX 4060+ |

## Format Quick Reference

### Short-Form (TikTok, Reels, Shorts)
- Resolution: 1080x1920 (9:16 portrait)
- Duration: 15-60 seconds
- Script: 150 words max
- Hook: First 3 seconds must grab (visual + audio simultaneously)
- Captions: Always on, word-by-word highlight

### Long-Form (YouTube)
- Resolution: 1920x1080 (16:9 landscape)
- Duration: 8-60 minutes
- Script: Section-based (intro, chapters, outro)
- Chapters: YouTube chapter markers at each section
- B-roll: Minimum 3 visual changes per minute
- Music: Instrumental, 8-12% volume, genre-matched
- Load [rules/long-form-production.md](rules/long-form-production.md) for full spec

### Marketing / Product Demo
- Resolution: 1920x1080 or 1080x1080 (depends on platform)
- Duration: 30-120 seconds
- Structure: Problem -> Solution -> Demo -> CTA
- Branding: Logo watermark, brand colors in text overlays

## Cinematic Principles (2026)

1. **Less is more** -- One strong shot > many mediocre ones
2. **Avatar talks, text reinforces** -- Voiceover carries content, text highlights keywords only
3. **Everything moves** -- Ken Burns 1.12x+, text slides, elements pulse
4. **Music is not decoration** -- Choose early, match mood, use intentional contradiction
5. **First 3 seconds decide everything** -- Visual + audio hook simultaneously
6. **Scene matches speech** -- If avatar says "neural networks," show neural network visuals, not random stock

Load [rules/cinematic-principles.md](rules/cinematic-principles.md) for full trend analysis.

## Cost Hierarchy (cheapest first)

```
1. LTX 2.3 local          -> FREE (self-hosted video generation, RTX 4060+)
2. Ollama local            -> FREE (script drafts, analysis)
3. Pexels API              -> FREE (stock B-roll clips)
4. Kokoro TTS              -> FREE (test voice, CPU)
5. faster-whisper           -> FREE (caption timing, CPU)
6. FFmpeg                  -> FREE (all post-production)
7. Remotion                -> FREE (open-source video templates)
8. Kling 3.0 API           -> ~$0.10/sec (cheapest cloud AI video)
9. Seedance 2.0 (fast)     -> ~$0.14/sec (fast mode, lower quality)
10. Seedance 2.0 (quality)  -> ~$0.30/sec (full quality, lip-sync)
11. ElevenLabs TTS          -> PAID (production voice only)
12. Higgsfield              -> Credit-based (multi-model orchestration)
```

**Rule:** Use FREE tools for drafts and testing. Only use paid APIs for final production renders after script/voice approval.

## Daena Brand (when producing MAS-AI content)

```
Name:        Daena
Title:       VP of MAS-AI Technologies
Energy:      Luxury executive -- poised, authoritative, magnetic
Tone:        Expert but accessible, founder energy, not corporate
Brand:       Dark slate #0F1419 | Gold #D4A843 | Teal #2DD4BF
Voice:       ElevenLabs Matilda (XrExE9yKIg1WjnnlVkGX)
```
