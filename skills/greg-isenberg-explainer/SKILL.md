---
name: greg-isenberg-explainer
description: "Greg Isenberg / Late Checkout style for short-form educational explainer videos. Hot-take hook -> problem -> framework -> proof -> CTA. Real B-roll over generated graphics. Dopamine-engineer pacing (visual change every 3-5s). Conversational smart-friend register. Use when the brief is teaching/explaining a tech/AI/startup concept in 15-60s vertical, NOT when it is a hard news take or product demo."
metadata:
  tags: video, short-form, explainer, educational, greg-isenberg, late-checkout, ai, startup, tiktok, reels, shorts, dopamine-engineer, contentops
---

# Greg Isenberg Explainer Skill

Production blueprint for educational AI / startup / tech short-form. Distilled from
Greg Isenberg's own teachings (faceless YouTube formula, Roberto Nickson masterclass,
Late Checkout content ops), the MrBeast hook framework Greg references, and the
2026 short-form playbook (3-second decision window, dopamine-engineer pacing,
authenticity > polish).

## When to invoke

- Brief is **educational**: "explain X", "here's how Y works", "the playbook for Z"
- Topic is in AI / startup / tech / no-code / community / agentic infra
- Target: TikTok, Reels, YouTube Shorts vertical 9:16
- Duration: 15-60s (sweet spot 22-35s)

## When NOT to invoke (route to other skills)

| Brief shape | Use this skill instead |
|---|---|
| Hard news take ("Anthropic just shipped X") | `scriptwriting-shortform` archetype=did_you_know or contrarian |
| Product demo / UGC ad | Higgsfield-style (Marketing Studio prompt format) |
| Quick reaction / hot take | `scriptwriting-shortform` archetype=mistake or contrarian |
| Long-form tutorial | `video-production` long-form pipeline |
| Lifestyle / behind-the-scenes | `daena_lifestyle` lane |

The router skill `video-skills-router` makes this decision automatically.

## 1. The 5-beat structure

Greg's videos (and the wider Late Checkout content ops) follow this beat map:

```
[0-3s]    HOT TAKE       -- tension / contrarian / curiosity. NO greeting.
[3-7s]    PROBLEM SETUP  -- name the pain the viewer is feeling RIGHT NOW
[7-18s]   FRAMEWORK      -- 2-3 named steps. Each step gets its own visual.
[18-26s]  PROOF          -- one concrete example with a number. Real screenshot.
[26-30s]  CTA            -- comment keyword for a follow-up resource (NEVER "like and subscribe")
```

For 22-second target: hook=3s, setup=4s, framework=11s (3 mini-shots), proof=2s, CTA=2s.

## 2. Hot-take hook templates (first 3 words rule)

Greg / Roberto Nickson masterclass: "script for emotion. always start with tension."

```
contrarian:        "Most founders are wrong about <X>."
permissionless:    "You don't need <thing X assumes>."
unfair-advantage:  "<Group A> has an unfair advantage at <X>. Here's why."
hidden-shift:      "<Industry> just changed. Nobody noticed."
trade-off-reveal:  "Cheap <X> beats premium <Y>. The reason isn't quality."
gatekeeper:        "Insiders use <tool>. Everyone else builds the hard way."
ten-x-better:      "<Old approach> takes 10 hours. <New approach> takes 10 minutes. The catch:"
permission-deny:   "Stop building <X>. Build <Y> instead."
```

Hard rules: <= 12 words, first 3 words = pattern interrupt, no
"hey/welcome/today/in this video".

## 3. Voice register (Daena VP profile applied)

```
Tone:          Smart friend across the table, not Wall Street analyst lecturing
Cadence:       Short.staccato.sentences. Then occasionally a longer one for rhythm.
Person:        "You" addressing camera. "I" only when sharing personal observation.
Vocabulary:    Concrete nouns. Named tools. Dollar amounts. Zero hedging.
Forbidden:     "might", "possibly", "kind of", "honestly", "obviously",
               "make sure to", "in this video", "today"
WPM target:    165-180 (faster for hook, slightly slower on framework)
Pause use:     ~250ms after the hot-take, before the framework
```

## 4. Visual layer — REAL footage first, generated last

The defining Greg trait: B-roll is real. Hierarchy of asset sources:

| Priority | Source | When |
|---|---|---|
| 1 | Real screenshot | Tool / dashboard / tweet / news article mentioned by name |
| 2 | Pexels stock video | Concept B-roll: "team meeting", "data center", "code on screen" |
| 3 | Pexels stock photo | Same as above when motion not needed |
| 4 | News clip frame | Recognizable event ("Anthropic launch", "Sam Altman speaks") |
| 5 | AI-generated B-roll | Only when no real asset exists (Kling, Sora, LTX, Veo) |
| 6 | Procedural Remotion graphic | LAST resort -- counter, chart, network diagram |

Never lead with #6. Greg's videos almost never do — they always cut to a real screenshot or real clip showing the thing being discussed.

## 5. Dopamine-engineer pacing

Roberto Nickson's exact prescription Greg endorsed: "every few seconds something
changes -- a jump cut, a caption hit, or a pattern interrupt -- so the brain
stays hooked and never gets to rest."

Concrete cadence at 30fps:

| Section | Visual change frequency | Specific moves |
|---|---|---|
| Hook (0-3s) | Every 18-30 frames (~0.6-1.0s) | Hard cut between 2-3 different shots |
| Framework (3-22s) | Every 60-90 frames (~2-3s) | Cut to new screenshot per named step + caption pop |
| CTA (22-30s) | Every 90-120 frames (~3-4s) | Settle on talking head + CTA card |

Pattern interrupts to layer in: caption flash (1-frame white), zoom punch
(1.0 -> 1.06 in 4 frames), whoosh sound on cut, screenshot annotation drawn-on
(circle, arrow), sudden "wait..." beat with frame freeze.

## 6. Caption style (greg / hormozi-pop hybrid)

```
Font:          Inter Black 900 or Montserrat Black 900, 60-72pt
Position:      Bottom-third (NOT covered by avatar card on right)
Color:         #FFFFFF default, #FFD500 or #D4A843 on stressed words
Reveal:        Word-by-word, 6-frame reveal, spring scale 0.5 -> 1.05 -> 1.0
Backdrop:      Semi-opaque dark slate (rgba(15,20,25,0.6)) behind text + 8px blur
Stress rule:   Numbers, named tools, named people, power verbs
Density:       2-4 words on screen at a time (NOT a wall of text)
```

## 7. Avatar overlay (talking-head card)

Greg's faceless videos have NO avatar. But for branded persona explainers
(Daena VP), use a small bottom-right corner card:

```
Position:  bottom-right, 360x460 px (1080x1920 frame)
Border:    2px solid gold (#D4A843), radius 20px
Lipsync:   SadTalker 256px from face crop + voice mp3 (cheap, GPU-friendly)
Cutout:    Use TRUE alpha-cutout PNG as source. >= 30% transparent pixels.
```

## 8. Sound design

```
Background:  Subtle ambient bed -8 dB to -12 dB beneath voice
SFX library: whoosh (cuts), tick (caption pop on number), ding (revelation),
             low boom (problem statement), sparkle (CTA card pop)
SFX volume:  -16 dB (felt, not heard)
End fade:    300ms audio fade-out matches video fade-out
```

## 9. Tools mentioned by Greg (for B-roll generation when needed)

| Tool | Use case | Cost |
|---|---|---|
| Pexels API | Stock video/photo | FREE |
| Kling 3 | Concept B-roll, 5-10s | ~$0.10/sec |
| Sora 2 | Concept B-roll, 4-20s + audio | ~$0.10-0.50/sec |
| Nano Banana (Gemini Flash Image) | Quick stylized stills | ~$0.04/image |
| Higgsfield | Product-link to ad pipeline | ~$0.20-1.00/clip |
| LTX-Video local | Concept B-roll, 5-10s | FREE (8-12 GB VRAM) |
| Wan 2.2 local | Concept B-roll, ~5s | FREE (16-24 GB) |
| ElevenLabs | Premium voiceover | PAID |
| edge-tts (AriaNeural) | Free voiceover | FREE |
| SadTalker | Face lipsync | FREE |
| LatentSync | Face lipsync (better quality) | FREE (24 GB) |

## 10. JSON output schema (drop into ContentOps pipeline)

```json
{
  "slug": "string",
  "duration_s_target": 28,
  "persona": "daena|hormozi|naval|custom",
  "hook": {
    "archetype": "contrarian|permissionless|unfair-advantage|hidden-shift|trade-off-reveal|gatekeeper|ten-x-better|permission-deny",
    "voiceover": "<= 12 words, no forbidden phrases",
    "on_screen_text": "<= 6 words"
  },
  "sections": [
    {
      "beat": "problem_setup|framework_step|proof|cta",
      "t_start": 0.0, "t_end": 0.0,
      "voiceover": "string, sentences <= 14 words",
      "visual_layer": {
        "primary_source": "screenshot|pexels_video|pexels_photo|news_clip|ai_gen|procedural",
        "asset_query": "string — what to fetch (Pexels query OR URL OR AI prompt)",
        "fallback_chain": ["pexels_video","pexels_photo","procedural"],
        "annotation": "circle|arrow|highlight|none",
        "annotation_target": "string — what to circle/point at"
      },
      "caption": {"text": "<= 6 words", "stress_words": ["..."]},
      "pattern_break": "cut|caption_flash|zoom_punch|whoosh|freeze|ding|none"
    }
  ],
  "cta": {
    "type": "comment_keyword|save|follow",
    "voiceover": "<= 10 words",
    "keyword": "string — the comment-bait keyword if applicable",
    "card_text": "<= 5 words"
  }
}
```

## 11. Self-critique gate (before leaving the skill)

Score each axis 0-10. Reject if any < 8.

- **Hook tension**: does the first 3 words stop the scroll without trying to be cute?
- **Real-asset density**: is the B-roll mostly screenshots / real footage, NOT procedural graphics?
- **Pattern-break cadence**: visual change every 3-5s confirmed?
- **Concrete-noun density**: every sentence anchors on a named tool / number / person?
- **Voice register**: smart-friend, not Wall Street analyst, not infomercial?
- **CTA gravity**: is the comment keyword something the viewer would actually type?

If any axis < 8, REWRITE that section only. Max 2 rewrite passes.

## 12. Anti-patterns (auto-FAIL)

```
- Procedural Remotion graphic as primary visual when a real screenshot exists
- Avatar card center-bottom blocking captions
- Caption text that just repeats the voiceover word-for-word
- Static gradient background for >5 consecutive seconds
- Voice with per-section <mstts:express-as> style switches (sounds robotic)
- "In this video / today / make sure to / like and subscribe"
- Hook longer than 1.5s before payoff starts
- Same visual style 5 sections in a row (slideshow effect)
```

## Contract with contentops-director

```
Input:  topic_seed, persona, target_platform, duration_s_target, niche_id
Output: JSON matching schema in section 10 + research.json with citations
        + pexels_query_list ready for the asset fetcher
```

The director hands the JSON to:
1. `voice-direction` skill -> generates voice brief + edge-tts mp3
2. `pexels-broll-fetcher` script -> downloads real assets per section
3. `edit-choreography` skill -> beat map for cuts
4. SadTalker -> lipsync mp4
5. Remotion composition -> final mux
6. `video-qa` skill -> gate before approval queue
