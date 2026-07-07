---
name: thevibefounder-style
description: "@thevibefounder (Ajay Yadav, 339K) AI-news-magnet style for short-form vertical reels. Comic-illustration b-roll + 11-beat narrative skeleton + DM-magnet CTA wired to ManyChat-style auto-DM funnel. Use when the brief is fast topical AI/tool news that should ride trending IG audio and convert viewers into DM funnel leads via 'Comment X and I'll send you Y'. NOT for educational/teach (use greg-isenberg-explainer) or hard contrarian takes (use scriptwriting-shortform)."
metadata:
  tags: video, short-form, vertical, instagram, reels, ai-news, dm-magnet, comic-illustration, manychat, contentops, thevibefounder, ajay-yadav
  source_handle: thevibefounder
  source_url: https://www.instagram.com/thevibefounder/
  derived_from: data/creator_profiles/thevibefounder_manual_analysis.md
  audience_target: AI builders / vibe-coders / startup founders 25-40
---

# @thevibefounder Style Skill — AI News Magnet

Reverse-engineered from a 36-reel sample (2026-04-30) of @thevibefounder
(Ajay Yadav, 339K followers, LA, co-founder @joinottodotcom). His median reel
clears 60K views; outliers ("spiritual frame" reels) hit 1M+. The format is
**topical AI news + comic-illustration b-roll + DM-magnet CTA** wired to a
ManyChat-style auto-DM funnel.

This is meaningfully different from `greg-isenberg-explainer` (educational,
real B-roll) and `scriptwriting-shortform` (contrarian/news, talking-head
heavy). Vibefounder rides **trending IG audio**, not original music, and
converts via **comment-keyword DM trigger**, not "follow for more."

## When to invoke

- Brief is **a tech/AI/tool announcement** ("X just shipped", "Y is giving free Z")
- The goal is **DM-funnel conversion** — viewer comments a keyword, gets auto-DM with link/asset
- Target: Instagram Reels first, TikTok / YouTube Shorts cross-post, vertical 9:16
- Duration: 22-45s (sweet spot 30s)
- You have a **lead magnet** for the DM responder (link, PDF, sandbox login, newsletter join)

## When NOT to invoke (route to other skills)

| Brief shape | Use this skill instead |
|---|---|
| Teach a framework / playbook | `greg-isenberg-explainer` |
| Hard contrarian take, no DM funnel | `scriptwriting-shortform` (archetype=contrarian) |
| Long-form tutorial 5-30 min | `video-production` long-form |
| Founder lesson / build-in-public | `masoud_founder` lane |
| Lifestyle / day-in-life | `daena_lifestyle` lane |
| Product demo / UGC ad | `higgsfield-marketing` |

## 1. The canonical 11-beat caption template

Triangulated across 4 reels (3 organic + 1 sponsored). Same skeleton, only the
topic varies. Every beat is a separate visual scene in the rendered reel.

```
1.  HOOK              <=12 words, ends with "…" or em-dash, present-tense AI verb
                      "Anthropic just changed AI…"
                      "Anthropic is giving you free credits."
                      "Claude just got another upgrade."
                      "One Prompt Replaced My Entire Marketing Stack"
                      → SCENE: Comic illustration of relevant tech CEO/icon

2.  INVERSION         3-line negation block. Each line shorter than the last.
                      "No new model.
                       No billion-dollar training run.
                       Just smarter orchestration."
                      → SCENE: Same character + bold text overlay flicker

3.  NAMED REVEAL      Explicit naming of the company/tool/feature
                      "Anthropic just introduced Advisor Strategy."
                      "The tool is Spoki."
                      → SCENE: Logo/screenshot/product still

4.  MECHANIC          Step-by-step explainer (4-6 short lines, often "Here's how it works:")
                      "The cheapest model — Haiku runs your entire task.
                       When it hits something difficult…
                       It calls Opus for help.
                       Gets the answer.
                       Continues working.
                       That's it."
                      → SCENE: Comic panels showing each step + arrows

5.  EVIDENCE          Concrete numbers with arrow notation, comparison, or stat
                      "19.7 → 41.2 on benchmarks. At 85% lower cost than Sonnet."
                      "Email open rate? ~20%. WhatsApp? Up to 98%."
                      → SCENE: Data viz / chart / comparison table

6.  BULLET-IMPACT     4-5 single-word bullets of "Your X becomes:"
                      "• Cheaper • Smarter • Faster • More scalable"
                      → SCENE: Comic of empowered character + bullet flicker

7.  STAKES HYPER      Big-claim sentence positioning the change as historic
                      "This is the biggest unfair advantage in AI right now."
                      "This isn't a prototype. This is running businesses 24/7."
                      → SCENE: Dramatic comic of "winner" character

8.  NEGATION TRIO     3-line "no/none/nothing" parallelism (simplicity reinforcement)
                      "No dashboards. No funnels. No automation headaches."
                      → SCENE: Slashed-out icons or rejected-stack visual

9.  PUNCH CALLBACK    3-line parallel summary that callbacks the hook
                      "One line of code. Double intelligence. 85% cheaper."
                      → SCENE: Triumphant comic + bold 3-line text card

10. SOFT CONCESSION   Acknowledges legitimacy/competitive context (optional)
                      "Agencies aren't dead. But this just changed the game."
                      → SCENE: Calm wide shot or blank-card transition

11. DM-MAGNET CTA     Comment-trigger that invokes ManyChat auto-DM responder
                      "Comment AI and I'll send you the direct link."
                      "Comment SPOKI and I'll send you the sandbox link."
                      → SCENE: Phone/DM mockup + bold CTA text card
```

For a 30s target: hook=2.5s, inversion=3s, reveal=2s, mechanic=8s (4 mini-shots),
evidence=3s, bullets=3s, stakes=2s, negation=2.5s, punch=2s, concession=1s, CTA=1s.

## 2. Hook formulas — Vibefounder taxonomy

These slot into our existing `hooks.py` library. Add as named formulas if not
already present:

| Pattern | Template | Example |
|---|---|---|
| `just_verb_news` | `[Co/Person] just [verb] [obj]…` | "Anthropic just changed AI…" |
| `inversion_of_tools` | `One [thing] replaced my entire [stack].` | "One Prompt Replaced My Entire Marketing Stack" |
| `free_money_alert` | `[Co] is giving you free [resource].` | "Anthropic is giving you free credits." |
| `status_crash` | `[Tool] just went down. [Error]. Again.` | "Claude just went down. API Error 500. Again." |
| `existential_frame` | (no text — pure visual + 2-word overlay) | "of the night" / "finally listened." |

Picker rules (extend `hooks.py`):
- `_has_company_name(article)` + `_has_recent_announcement(article)` → `just_verb_news` (10)
- `_has_free_offer(article)` → `free_money_alert` (10)
- `_has_outage_keyword(article)` → `status_crash` (10)
- Default fallback when topic is AI tool news → `just_verb_news` (8)

## 3. Voice register

```
Persona:       Indian-American mid-30s male, conversational warm tone
Tone:          Insider with the receipts. Excited but calm. No hedging.
Cadence:       Short declarative (5-12 words). Heavy ellipses for dramatic pauses.
Person:        "You" → audience. "I" → personal experiments only.
Vocabulary:    Named tools, named people, dollar amounts, percentages, arrows.
Forbidden:     "might", "possibly", "kind of", "honestly", "thanks for watching"
WPM:           150-170 (slightly slower than Greg style for revelation feel)
Pause use:     400-600ms after hook ellipsis. 200ms between bullets. 800ms before CTA.
TTS engine:    edge-tts en-US-AndrewMultilingualNeural OR XTTS-v2 fine-tuned
Optional:      Real Ajay-style accent voice via XTTS clone (operator-supplied 30s sample)
```

SSML hints for edge-tts:

```xml
<speak version="1.0" xml:lang="en-US">
  <voice name="en-US-AndrewMultilingualNeural">
    <prosody rate="-3%" pitch="+0%">
      Anthropic just changed AI<break time="450ms"/>
      <prosody rate="+5%">With one line of code.</prosody>
      <break time="500ms"/>
      No new model. <break time="180ms"/>
      No billion-dollar training run. <break time="180ms"/>
      Just smarter orchestration.
    </prosody>
  </voice>
</speak>
```

## 4. Visual layer — Comic illustration first

This is THE differentiator. Greg uses real B-roll + screenshots. Vibefounder
uses **stylized comic-illustration panels** of tech CEOs in dramatic poses.

### Engine fingerprint

The look matches **Midjourney v6 / Flux Pro / SDXL with comic-style LoRA**:
- High stylization (painterly, cinematic, dramatic lighting)
- Consistent character likeness (same Sam Altman across panels)
- Saturated palette: cinematic teal/orange, neon magenta, dark backgrounds
- 9:16 vertical, full-bleed, character usually centered

### Prompt template (Flux Pro / Midjourney v6 / Wan2GP image mode)

```
[Subject person/character] [emotional pose/action], [setting],
comic book illustration, painterly digital art, dramatic cinematic lighting,
[color palette], [film grain/style tokens], 9:16 vertical, ultra-detailed,
volumetric god-rays, stylized portrait, Greg Rutkowski + Artgerm style mix.

Examples:
- "Sam Altman with glowing red laser eyes, anxious expression, surrounded by
   monitors showing AI code, comic book illustration, painterly digital art,
   dramatic neon teal and magenta lighting, film grain, 9:16 vertical"
- "Cyberpunk Elon Musk DJing at a holographic mixer, distorted RGB color
   bleed, high-saturation neon palette, comic illustration, 9:16"
- "Two anime warriors fighting in a boxing ring, one labeled 'Midjourney'
   one labeled 'Perplexity', dynamic pose, dramatic lighting, 9:16"
- "Two figures kneeling in prayer in a Buddhist temple, golden god-rays
   from above, anime spiritual style, ethereal warm light, 9:16"

Negative: text overlays, watermarks, distorted hands, extra limbs, low quality,
oversaturated yellow, generic stock photo
```

### Animation strategy

**Vibefounder reels are 80% still images with subtle motion**, not full AI
video gen. Cheaper, faster, more consistent.

Per-panel motion options (apply via ffmpeg or Remotion):
- Ken Burns slow zoom (0.5-1.0x scale over 2s)
- Slow pan (5-10% movement over 2s)
- Static hold + 1-2 caption flickers
- Subtle parallax (foreground/background layer split)
- Quick whip-pan / cut between 2 stills

Reserve actual AI video gen (LTX/Wan2GP) for 1-2 hero scenes per reel only.

### Caption overlay — the meme-poster aesthetic

Every comic panel gets a 2-4 word bold text overlay. This is the **signature
visual element** — without it, the reel doesn't read as vibefounder-style.

```
Font:           Impact / Anton / Bebas Neue (TikTok-default heavy sans)
Size:           1/8 of frame height (240px on 1920 frame)
Color:          White (#FFFFFF) with thick black outline (8px)
Optional:       1-2 words highlighted in yellow (#FFD700) or red
Position:       Center-anchored, vertically near subject's head OR bottom-third
Animation:      Pop-in (0.15s scale 0.8 → 1.0 + fade 0 → 1)
Word count:     2-4 words MAX per panel. Single word > four.
Examples:       "AGENT", "1 PERSON COMPANY", "Sam is slapping",
                "lovable CEO", "watching", "thinking", "finally listened.",
                "of the night", "right now,", "broke", "Ai employee"
```

This sits ON TOP of the comic panel, distinct from the lower-third subtitle
caption (which transcribes the voice-over).

## 5. Audio strategy — ride trending IG sounds

Vibefounder does NOT use original music. He picks:

1. **Trending IG sounds** (`Ogryzek · AURA`, viral tracks of the week).
   Riding sound waves boosts reach. Audio is named in reel attribution.
2. **Cinematic-orchestral underscore** for spiritual/emotional reels (1M+ outliers).
3. **Voiceover-only with foley** when voice carries the reel.

### Implementation

For a clean automated pipeline:

| Mode | Source | When |
|---|---|---|
| Trending IG sound | Manual ingest (operator picks weekly top-3) | Default for news takes |
| Cinematic orchestral | Local Suno-style gen OR royalty-free library (Epidemic Sound / Artlist) | Spiritual/emotional reels |
| Voiceover-only | edge-tts / XTTS direct | Talking-head reels |

VO sits on top, music ducked to ~60-70% under VO with sidechain compression.
Drop music intensity to 20% during HOOK and CTA for emphasis.

### Audio asset library plan

Build `data/audio/trending_ig/<week>/` — ingest top-10 trending IG sounds weekly.
Each entry:
```
{
  "id": "ogryzek_aura",
  "name": "Ogryzek · AURA",
  "duration_s": 27.0,
  "bpm": 92,
  "mood": "uplifting-tech",
  "added_week": "2026-W17",
  "uses": 4,
  "best_for": ["news_take", "free_alert"]
}
```

Music selection picks the best matching mood per beat-1 hook.

## 6. The DM-magnet CTA — the conversion engine

This is what separates vibefounder reels from all our current skills.

### How it works

1. Reel ends with **"Comment KEYWORD and I'll send you the link"**
2. Viewer comments the keyword (e.g. "AI", "OPUS", "SPOKI")
3. ManyChat / Pally / similar bot auto-DMs them the promised resource
4. Viewer is now in a **DM funnel** — bot can ask qualifying questions, drop
   newsletter signup, push paid product

### Why it works

- IG algorithm treats comments as engagement gold (rewards reach)
- DM-conversion is 5-10x higher than bio-link clicks
- Bypasses 1-link-in-bio limit (each reel is its own funnel)
- Builds owned audience (DMs feed into newsletter / Whop community)

### Pipeline integration plan

ContentOps must ship a **DM-magnet keyword** with every script in this style.
The keyword feeds two systems:

**A. Caption rendering** — `Comment {KEYWORD} and I'll send you the {ASSET}.`
appended verbatim to caption + last beat voiceover.

**B. ManyChat / Pally auto-DM rule** — REST API call posted at publish time:
```json
POST https://api.manychat.com/fb/sending/sendContent
{
  "subscriber_keyword": "OPUS",
  "ig_account": "thevibefounder_or_yours",
  "message": {
    "text": "Here's the Opus 4.7 deep-dive I promised: {LINK}",
    "buttons": [{"type": "url", "label": "Read", "url": "{LINK}"}]
  },
  "expires_at": "{NOW + 14d}"
}
```

Tracked in DB:
```sql
ALTER TABLE scripts ADD COLUMN dm_magnet_keyword TEXT;
ALTER TABLE scripts ADD COLUMN dm_magnet_asset_url TEXT;
ALTER TABLE scripts ADD COLUMN dm_magnet_provider TEXT; -- "manychat" | "pally" | "rule"
```

If no auto-DM provider is configured, fall back to manual DM via the social
publishing browser (the `social-media-browser-puppeteer` skill stack).

## 7. Production brief schema (extends scriptwriting-shortform)

```json
{
  "style": "thevibefounder",
  "duration_sec": 30,
  "hook_formula": "just_verb_news",
  "trending_audio_id": "ogryzek_aura",
  "dm_magnet": {
    "keyword": "OPUS",
    "asset_url": "https://letter.example.com/opus-deep-dive",
    "provider": "manychat",
    "expires_days": 14
  },
  "scenes": [
    {
      "beat": 1,
      "name": "hook",
      "voiceover": "Anthropic just changed AI…",
      "text_overlay": "JUST CHANGED",
      "image_prompt": "Sam Altman wide-eyed at desk, dramatic neon teal lighting, comic illustration, 9:16",
      "image_engine": "flux_pro",
      "motion": "ken_burns_zoom_in",
      "duration_s": 2.5
    },
    {
      "beat": 2,
      "name": "inversion",
      "voiceover": "No new model. No billion-dollar training run. Just smarter orchestration.",
      "text_overlay": "JUST ORCHESTRATION",
      "image_prompt": "Same Sam Altman, intercut with crossed-out training rack, comic illustration",
      "image_engine": "flux_pro",
      "motion": "static_with_text_flicker",
      "duration_s": 3.0
    }
    // ...beats 3-11
  ],
  "edit_plan": {
    "caption_style": "vibefounder_meme_poster",
    "color_grade": "cinematic_teal_magenta",
    "music_intensity_default": 0.65,
    "music_intensity_hook": 0.20,
    "music_intensity_cta": 0.20,
    "cut_cadence": "hook_2.5s_body_2.5-3s_cta_1s",
    "subtitle_style_id": "vibefounder_subtitle"
  },
  "publish": {
    "platforms": ["instagram", "tiktok", "youtube_shorts"],
    "manychat_rule_id": null,
    "scheduled_for": null
  }
}
```

## 8. House style constants

```python
VIBEFOUNDER_DURATION_RANGE = (22, 45)
VIBEFOUNDER_BEAT_COUNT = (8, 11)        # CTA-only short can drop concession + bullet beats
VIBEFOUNDER_WPM = 160
VIBEFOUNDER_HOOK_MAX_WORDS = 12
VIBEFOUNDER_TEXT_OVERLAY_MAX_WORDS = 4
VIBEFOUNDER_BULLET_MAX = 5
VIBEFOUNDER_FONT = "Impact"             # falls back to Anton, Bebas Neue
VIBEFOUNDER_TEXT_OVERLAY_COLOR = "#FFFFFF"
VIBEFOUNDER_TEXT_OVERLAY_HIGHLIGHT = "#FFD700"
VIBEFOUNDER_OUTLINE_PX = 8
VIBEFOUNDER_VOICE = "en-US-AndrewMultilingualNeural"  # edge-tts default
VIBEFOUNDER_DUCKING_DB = -10            # music ducked under VO
```

## 9. Reel grading rubric (for video-qa)

A reel ships only if:

- [ ] Hook is <=12 words, ends with `…` or `—`, no banned filler ("hey", "today", "in this", "welcome")
- [ ] All 11 beats present (or documented skip with reason in metadata)
- [ ] Every beat has a unique image prompt (no duplicate scenes)
- [ ] Comic illustration engine consistency: same engine for all beats (no Flux + LTX mix mid-reel)
- [ ] Caption overlay max 4 words per scene, Impact-style font, white + black outline
- [ ] DM-magnet CTA present, keyword = single word UPPERCASE, asset URL valid
- [ ] Trending audio ID resolvable, ducked properly under VO
- [ ] Total duration in 22-45s window
- [ ] Subtitle SRT word-level timed (Whisper-tiny)
- [ ] Caption text in IG-publish payload ends with the DM-magnet line

Mode-A talking-head variants relax the comic-engine rule but must still hit
the 11-beat caption skeleton and DM-magnet CTA.

## 10. Step-by-step pipeline (production runbook)

```
1. INGEST            scrapers pick a fresh AI-tool announcement
                     (HN top story, Anthropic blog, OpenAI ship, MiniMax, etc.)
2. ROUTE             video-skills-router classifies: "AI tool news + DM magnet" → thevibefounder-style
3. SCRIPT            scripts.py + this skill → 11-beat JSON brief (above)
4. RESEARCH          research_topic() grounds names + numbers (Perplexity)
5. KEYWORD PICK      DM-magnet keyword: ALL-CAPS, single word, semantically tied to topic
                     (Anthropic credits → "CREDITS"; Opus 4.7 → "OPUS"; Spoki ad → "SPOKI")
6. AUDIO PICK        pick best trending audio from data/audio/trending_ig/<this_week>/
                     fallback: cinematic underscore from local library
7. PER-BEAT IMAGE    for each of 11 beats:
                     - generate image via Flux Pro / SDXL / Wan2GP image mode
                     - or: cached entity headshot for "named reveal" beat
                     - or: data viz card for "evidence" beat
8. PER-BEAT MOTION   apply Ken Burns / pan / parallax — single still produces a 2-4s clip
                     reserve LTX/Wan2GP video gen for 1-2 hero clips only
9. PER-BEAT OVERLAY  bold 2-4 word text card, Impact font, white + black outline,
                     pop-in animation, near subject head or bottom-third
10. VOICEOVER        edge-tts → narration.mp3 (or XTTS clone if Ajay-voice configured)
11. SUBTITLES        Whisper-tiny → narration.srt → ASS burn-in lower-third
12. ASSEMBLE         ffmpeg concat clips + duck music + burn captions + apply color grade
13. QA               video-qa skill grades against the rubric above
14. PUBLISH          social/instagram.py → reel + caption + DM-magnet keyword line
                     social/tiktok.py → cross-post (drop the IG-specific audio attribution)
                     social/youtube.py → cross-post as Short
15. WIRE DM RULE     POST to ManyChat/Pally with keyword + asset URL + 14d expiry
16. TRACK            DB updates: dm_magnet_keyword, dm_magnet_asset_url,
                     post_url, scheduled_for, manychat_rule_id
17. FEEDBACK         24h after publish, scrape comment count + DM-magnet hit count
                     into rejections.jsonl + scripts table for learning loop
```

## 11. Reference reels (hard examples for prompt grounding)

When generating the next reel, the system prompt should ground itself with
1-2 of these as exemplars (verbatim captions in `data/creator_profiles/thevibefounder_manual_analysis.md`):

| Reel ID | Topic | Pattern | Views | Why it's a good exemplar |
|---|---|---|---|---|
| DW8waJqDe8G | Anthropic Advisor Strategy | `just_verb_news` + DM-magnet "AI" | ~40K | All 11 beats present, clean punch callback |
| DXn8oE5EkDp | Spoki sponsored #ad | `inversion_of_tools` + DM-magnet "SPOKI" | ~62K | Sponsored variant — proves template handles ads |
| DWw3IVNDrDs | Anthropic free credits | `free_money_alert` + soft CTA "Did you get yours?" | 193K | Numbered-list variant, lighter CTA |
| DXM-QDFEvbP | Opus 4.7 launch | `just_verb_news` + DM-magnet "OPUS" | ~60K | Bullet-impact section is textbook |

## 12. Anti-patterns (do not do)

- ❌ Original music (vibefounder rides trends — original music DOES NOT match)
- ❌ Real-life Pexels stock B-roll (this is greg-isenberg territory)
- ❌ Generic "Follow for more" CTA (vibefounder uses comment-keyword DM-magnet exclusively)
- ❌ Greeting starters ("hey guys", "today I want to talk about")
- ❌ Long sentences in voiceover (>14 words = breaks the punchy cadence)
- ❌ Mixing AI engines mid-reel (Flux + LTX in same reel = visual jarring)
- ❌ Skipping the inversion/negation triad (kills the rhythm)
- ❌ Using the talking-head variant for tool-launch news (doesn't sell as well as comic)
- ❌ More than 4 words in a text overlay (becomes unreadable in 2-second scene)
