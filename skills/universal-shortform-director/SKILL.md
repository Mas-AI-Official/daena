---
name: universal-shortform-director
description: Directs short-form video production end-to-end for any subject. Covers entity casting (show the person/company when named), voice-scene energy matching, caption style selection (glassy/Hormozi/minimal), hook structure, and cut cadence. Use when producing 30-60s vertical videos from research or scripts.
---

# Universal Short-Form Director

Distilled from 2026 patterns studied across Hormozi, MrBeast, Ali Abdaal, Greg Isenberg, Cody Sanchez, Marques Brownlee, Fireship, and the top 5 vertical-video agencies (Viral Nation, LYFE Marketing, InBeat, Venture Media, Ubiquitous). Pair with: `scene-generation`, `voice-direction`, `edit-choreography`, `scriptwriting-shortform`.

## 1. The 6 non-negotiable rules

1. **Show the entity when you name it.** The instant narration says a specific person, company, or product, the visual MUST be that entity (their photo, their logo, their UI). Stock-video of "a developer at a laptop" when you say "Dario Amodei" is amateur. Use Wikipedia for people, Clearbit for company domains, press kits for products.
2. **Video length = voice length.** Not approximate. Exact. Use `ffprobe -i narration.mp3` to get the audio duration, then `-t <duration>` on the final ffmpeg pass. No trailing silent video, no video ending before narration.
3. **Niche-anchor every stock query.** Topic is AI? Every Pexels query must contain an AI/tech word. Topic is finance? Every query contains a finance word. Otherwise "dashboard" returns a car dashboard.
4. **Blocklist brand names from stock queries.** Pexels returns *brand imagery* when you query "Bluesky" — you get actual Bluesky screenshots, not topical visuals. Replace brand mentions with generic descriptors ("tech news feed", "social media post").
5. **Caption style matches energy, not default.** Hook / comedy / high-energy → Hormozi word-pop gold highlight. Explainer / news / measured → glassy block (BorderStyle=4). Tutorial / how-to → minimal corner. Never mix styles within one video.
6. **Cut cadence matches voice energy.** Hook: 2-7 frames per shot (pattern interrupts). Body: 15-45 frames. CTA: 24-60 frames. Snap cuts to vocal stress (within ±3 frames).

## 2. Scene-type taxonomy

Every beat in a video is one of these seven types. The pipeline should pick a type per beat based on the narration:

| Type | Trigger | Source | Duration range |
|---|---|---|---|
| **evidence** | Hook makes a claim; this is the proof | Screenshot of article / document / pricing page / commit diff | 4-8s Ken-Burns |
| **entity_headshot** | Narration names a person | Wikipedia infobox / press kit / podcast still | 3-6s push-in |
| **entity_logo** | Narration names a company | Clearbit (`logo.clearbit.com/<domain>`) / official SVG | 2-3s static with subtle scale |
| **data_viz** | Narration cites a number, %, or growth | Custom chart / matrix / table screenshot | 3-5s reveal animation |
| **ambient_broll** | Narration is abstract / metaphorical | Pexels (niche-anchored, no brand names) | 2-4s |
| **reaction** | Hook/punchline needs emphasis | Creator face / reaction GIF / meme still | 1-2s whip-cut |
| **cta_terminal** | CTA / call to action | Terminal / Claude console / app UI | 3-4s ending shot |

## 3. Voice-scene energy match table

Ignore this at your peril — a monotone voice over a high-motion scene is jarring.

| Voice state | Scene motion | Camera move | Caption |
|---|---|---|---|
| Whispered / conspiratorial | Slow | Static or micro-zoom | Minimal corner |
| Measured / authoritative | Slow-medium | Slow dolly-in 1.0→1.04 | Glassy block |
| Excited / punchy | Medium-fast | Push-in 1.0→1.10 on stress | Hormozi word-pop |
| Frantic / sarcastic | Fast | Crash zoom or whip pan | Hormozi + shock LUT |

Map narration words to voice state using `voice-direction` skill's persona/emotion table, then pick the scene row.

## 4. Entity casting resolution order (for any name)

```
  person(name):
    1. ~/MODELS_ROOT/entities/<slug>.jpg   # local curated cache
    2. Wikipedia REST API summary.originalimage.source
    3. Wikipedia REST API summary.thumbnail.source
    4. Google Knowledge Graph (if API key set)
    5. null → fall through to ambient b-roll

  company(name):
    1. ~/MODELS_ROOT/entities/<slug>_logo.png  # local cache
    2. logo.clearbit.com/<mapped_domain>?size=512
    3. google.com/s2/favicons?domain=<domain>&sz=256
    4. null → fall through

  product(name):
    1. ~/MODELS_ROOT/entities/<slug>_product.png
    2. Parent company's logo (products usually use the corporate mark)
    3. null → fall through
```

Never use a person's photo for a company name, and vice versa. Misattribution on video is a legal exposure.

## 5. Caption style library (ASS force_style strings)

### Glassy block (default for explainer / news)
```
FontName=Arial Black,FontSize=58,PrimaryColour=&H00FFFFFF,
OutlineColour=&H00000000,BackColour=&H60000000,
BorderStyle=4,Outline=2,Shadow=0,
Alignment=2,MarginV=360,Bold=1
```
`BorderStyle=4` = rounded filled box. `&H60000000` = ~62% opaque black. Reads on any b-roll.

### Hormozi word-pop (hook / comedy / high-energy)
```
FontName=Arial Black,FontSize=72,PrimaryColour=&H00FFFFFF,
SecondaryColour=&H0000D5FF,
OutlineColour=&H00000000,BorderStyle=1,Outline=6,Shadow=3,
Alignment=2,MarginV=520,Bold=1,ScaleX=105,ScaleY=105
```
Use with word-by-word SRT generation (not phrase-level). Yellow highlight color `&H0000D5FF` = `#FFD500` in ASS BGR order.

### Minimal corner (cinematic / luxury)
```
FontName=Inter,FontSize=44,PrimaryColour=&H00FFFFFF,
OutlineColour=&H00000000,BackColour=&H00000000,
BorderStyle=1,Outline=0,Shadow=2,
Alignment=1,MarginL=80,MarginV=200
```
Lower-left corner, subtle shadow only. For measured, artistic content.

## 6. Hook structures that retain (pick ONE per video)

From the 10-creator pattern study:

1. **Contrarian claim** (Hormozi): "X is destroying Y. Here's why." — MAS-AI house style default
2. **Caught red-handed** (Zitron): "[Company] tried to [do bad thing]. [Journalist] caught them in [short time]." — works for news stories
3. **Curiosity pain-point** (Ali Abdaal): "You're probably doing X wrong. Here's the fix." — works for tutorial content
4. **Number-stakes** (MrBeast): "I [verb] [number] times to [outcome]." — works for challenge / data content
5. **Authority quote** (Greg Isenberg): "[Known person] just said [surprising thing]." — works for commentary
6. **Pattern interrupt** (Cody Sanchez): "Everyone says X. They're lying." — works for myth-busting

## 7. Cut cadence reference

For 30 fps vertical:

| Section | Seconds | Shots | Frames per shot |
|---|---|---|---|
| Hook | 0-3s | 3-8 | 15-30 |
| Setup | 3-8s | 2-3 | 60-75 |
| Payoff body | 8-22s | 6-10 | 45-75 |
| Reveal | 22-26s | 1-2 | 60-120 |
| CTA | 26-30s | 1 | 120 |

Cuts at phrase boundaries (silence > 200ms) win. Cuts at vocal stress (dB > mean+6) win harder. Never cut mid-word.

## 8. Python helper — universal director

```python
def direct_shortform(script: dict, research: dict, render_dir: Path) -> dict:
    """Returns an edit plan: for each beat, the scene_type + source + camera move + caption.

    Integrates:
      - entity_cast.plan_entity_casting() for entity_headshot/logo beats
      - video_render.generate_beat_visuals() for ambient_broll / data_viz queries (niche-anchored)
      - voice-direction skill for voice_state per beat
      - edit-choreography skill for caption style + cut cadence
    """
    from contentops.entity_cast import plan_entity_casting
    from contentops.video_render import plan_beats, generate_beat_visuals, transcribe_words

    words, duration = transcribe_words(render_dir / "narration.mp3")
    beats = plan_beats(words)
    beats = generate_beat_visuals(beats, script, research=research)
    entities, entity_beat_map = plan_entity_casting(script, beats, render_dir, research=research)

    for b in beats:
        if b["id"] in entity_beat_map:
            b["scene_type"] = "entity_headshot"
            b["asset_path"] = str(entity_beat_map[b["id"]])
        elif b.get("asset_source") == "hero_burns":
            b["scene_type"] = "evidence"
        else:
            b["scene_type"] = "ambient_broll"
        b["caption_style"] = "glassy" if b["scene_type"] in ("evidence", "entity_headshot") else "hormozi"
    return {"duration_s": duration, "beats": beats, "entities": entities}
```

## 9. Contract with other skills

- **Consumes:** `script` (hook/body/CTA), `research` (title/description/body_snippet + hero image URL), `render_dir`
- **Calls:** `voice-direction` for TTS brief, `scene-generation` for LTX prompts (optional AI scenes), `edit-choreography` for final cut plan
- **Produces:** `edit_plan.json` (scene_type per beat, caption style, cut cadence) + curated asset list
- **Never:** shows a generic stock clip when a named entity has a known image; uses Pexels when the beat mentions a brand; cuts mid-word; lets video outrun narration

## 10. Quality gate

Before shipping a video, verify:

- [ ] Video duration matches narration duration within ±0.1s
- [ ] Every named entity has a visual (or is gracefully dropped to b-roll)
- [ ] No Pexels query contains a blocked brand name (Bluesky, Twitter, Anthropic, Claude, etc.)
- [ ] Caption style is one consistent choice (not mixed)
- [ ] First 3s has ≥3 pattern interrupts (cuts, captions landing, or scene shifts)
- [ ] Final 4s settles on one CTA with no more cuts
- [ ] Niche anchor present in every ambient-broll query

If any box fails, fix before rendering final.
