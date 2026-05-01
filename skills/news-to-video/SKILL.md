---
name: news-to-video
description: Convert a breaking tech/AI news story into a 30-60s vertical video using multi-source research, virality scoring, entity casting, and evidence screenshots. Use when a scraped news item scores above the virality threshold and the operator wants to produce a news-commentary short for social distribution.
---

# News-to-Video Production Skill

Distilled from 2026 news-commentary channels: Fireship (AI/tech, 3M subs), Morning Brew, ABC News Loop (Australian ABC's social-first explainer service launched 2026), and SaySo (verified-news short-form app launched April 2026). Pair with: `universal-shortform-director`, `scene-generation`, `voice-direction`, `edit-choreography`, `contentops-director`.

## When to invoke

Invoke when a scraped news item crosses the virality threshold. Default threshold inputs:

- Story is < 48 hours old
- Primary source has >= 10k engagements OR is from a named journalist/publication
- Topic fits at least one MAS-AI niche (AI, devtools, cybersecurity, SaaS, finance, startups)
- Either the story has concrete evidence (a screenshot, a diff, a chart) OR a named entity the viewer will recognize

## The 6-stage pipeline

### Stage 1 — Scrape & score virality (automated)

Scrape with `contentops.scraper` / `contentops.ig_scraper` / `contentops.creator_harvest`. Score each item with `contentops.viral` (or implement):

```
virality = (
    0.30 * recency_score         # 1.0 if < 6h, 0.5 if < 24h, 0.0 if > 72h
  + 0.25 * engagement_score      # log10(likes+retweets+comments) / 4
  + 0.20 * source_credibility    # 1.0 for tier-1 publication, 0.7 for journalist, 0.4 for random
  + 0.15 * entity_density        # count of named people/companies / 5, capped 1.0
  + 0.10 * evidence_score        # has a screenshot/chart/diff? 1.0 : 0.0
)
```

Threshold: process stories >= 0.60. Below that, save for digest.

### Stage 2 — Multi-source research (Opus, NOT local LLM)

For any story that passes the threshold, Opus MUST (not delegate):

1. **Fetch 5+ sources** covering the same story:
   - The original source (tweet, blog, filing, etc.)
   - At least 2 tier-1 publications (Reuters, AP, TechCrunch, The Register, Wired, Verge, NYT, Bloomberg, The Information)
   - At least 1 community signal (r/LocalLLaMA, HN, Twitter replies, relevant Discord)
   - The subject's OWN page (e.g. company pricing page, GitHub repo, product changelog)
2. **Extract from each**:
   - What specifically happened (fact)
   - Any NUMBERS (prices, percentages, timestamps, counts)
   - Any direct quotes from named people
   - Any screenshots / charts / evidence images (URLs)
3. **Cross-check**: if two sources contradict, note which one's closer to the primary source
4. **Write research.json** with: `{sources: [{url, title, author, published_at, key_quotes}], facts: [...], evidence_images: [url], entities: [{name, role, wikipedia_url?, headshot_url?}]}`

**Never skip this step.** A video built on one source (like a single tweet) is strictly worse — the viewer feels it.

### Stage 3 — Script writing (Opus, contrarian-stakes house style)

Using research.json, write a 60-90 word script in MAS-AI contrarian-stakes voice:

- **Hook (12-18 words):** name the specific subject + specific action + time hook. Template: "X tried to [do Y]. [Source] caught them in [time]."
- **Receipt (8-12 words):** "Here's the receipt." or "Here's what happened." → primes the viewer for evidence.
- **Facts (30-40 words):** the WHO did WHAT + the SPECIFIC numbers + the KEY QUOTE. Always name the person/company.
- **Translation (10-15 words):** the contrarian interpretation — what the company is REALLY saying
- **CTA (10-15 words):** question that invites a specific action, not "leave a comment"

Hand off the script with:
- 5+ named entities explicitly in the copy (for entity-casting)
- At least ONE direct quote with attribution
- Specific numbers (not "many" or "a lot")
- House style markers: em-dash for dramatic pause, ellipsis for revelation

### Stage 4 — Evidence curation (manual override)

For every major beat, stage the BEST evidence image as `render_dir/research/manual_hero.jpg`:

- Pricing story → before/after pricing table side-by-side (NOT the social post about it)
- Layoff / ship story → the actual filing, email, or commit diff
- Launch story → the product UI screenshot (NOT the marketing page)
- Leak story → the leaked screenshot / document
- CEO quote story → the CEO's face (Wikipedia thumbnail, high-res press kit)

The evidence image is the single most-remembered frame in the video — curate it personally.

### Stage 5 — Pipeline render (automated)

Call `contentops.video_render.render_script(script_id)` which chains:

1. `fetch_research` with manual_hero.jpg Tier-0 override
2. `render_narration` → ElevenLabs v3 > XTTS-Daena > edge-tts Aria chat style
3. `transcribe_words` with proper-noun priming in initial_prompt
4. `plan_beats` / `generate_beat_visuals` with niche-anchor + proper-noun blocklist
5. `plan_entity_casting` — Wikipedia / Clearbit lookups for every named entity
6. Beat-by-beat asset resolution: LTX → entity_cast → hero_burns → Pexels → reuse
7. NVENC final pass with glassy caption style (libass coords in 288-space)
8. Audio-length clamp via ffprobe + `-t`

### Stage 6 — Quality gate (before publish)

Block publish if ANY fails:

- [ ] Video duration matches narration duration within ±0.1s
- [ ] Captions visible and readable on a phone at arm's length (spot-check a frame)
- [ ] Every named person in the script appears as their Wikipedia photo or is gracefully dropped
- [ ] Every named company has a logo or evidence screenshot
- [ ] No Pexels query contains a blocked brand name
- [ ] Hook lands in first 2 seconds
- [ ] At least one pattern interrupt in first 5 seconds
- [ ] Audio engine was Tier-0 or Tier-1 (never falls all the way to Jenny-default)

If any box fails, fix before rendering final.

## News-specific patterns from the creator study

### Fireship (3M subs, AI/tech explainers)
- Pace: 170-190 WPM with aggressive jump cuts
- Structure: cold-open fact → context → timeline → hot take → CTA
- Visuals: screen recordings + terminal + dev faces + logos (rarely stock)
- Captions: Hormozi-style word-pop, gold highlight on numbers/names

### Morning Brew (4M subs, business/tech news)
- Pace: 150-165 WPM, warmer conversational
- Structure: "Here's the deal" cold open → 3 facts → analyst take → CTA
- Visuals: stock market overlays + anchor face + b-roll of named companies
- Captions: minimal corner, brand colors

### ABC News Loop (launched Jan 2026, explainer-first)
- Pace: 140-160 WPM
- Structure: context first, then the claim (not inverted-pyramid)
- Visuals: archival news clips + official documents + animated charts
- Captions: glassy block, neutral blue brand

### SaySo (launched April 2026, verified-news short-form)
- Verification badge overlays on every clip
- Source citation in lower-left throughout
- Community-notes style context overlay on contested claims

## Python helper

```python
from pathlib import Path
from contentops.viral import score_virality          # exists — contentops/viral.py
from contentops.scripts import generate_script       # exists — Opus/Claude via llm.py
from contentops.entity_cast import plan_entity_casting
from contentops.video_render import render_script


def news_to_video(item: dict, min_virality: float = 0.60) -> dict | None:
    """Main entry point. item: a scraped news item dict (from scraper.py).

    Returns the render result dict, or None if the item didn't pass the virality gate.
    """
    score = score_virality(item)
    if score < min_virality:
        return None
    # Multi-source research is done manually by Opus before calling this function.
    # The research step populates <render_dir>/research/manual_hero.jpg and
    # <render_dir>/research/research.json with facts + evidence.
    script_id = generate_script(item, house_style="contrarian_stakes")
    return render_script(script_id)


# The multi-source research step is NOT automated — it's an Opus task driven by
# the /research-news slash command or equivalent. That's a DESIGN CHOICE: news
# accuracy is too important to fully automate away from a human-in-the-loop
# reasoner. Local LLMs hallucinate on entity names and numbers; Opus doesn't.
```

## Contract with other skills

- **Consumes:** scraped news item, plus Opus's multi-source research output (research.json + manual_hero.jpg)
- **Calls:** `universal-shortform-director` for scene-type taxonomy, `voice-direction` for TTS brief, `scene-generation` for any AI-generated scenes (LTX for hero beats), `edit-choreography` for cut cadence
- **Produces:** rendered MP4 + result.json + ready-to-publish caption/hashtags
- **Never:** publishes without the quality gate passing; skips multi-source research; uses a single-source story as its only evidence base

## Anti-patterns to avoid

1. **One-source videos**: "Here's what Ed Zitron tweeted" — this is a repost, not a video. Always at least 3-5 sources with cross-reference.
2. **Hedged hooks**: "Anthropic might be doing X" — if you don't have confidence to state it, you don't have a story yet. Go back to research.
3. **Generic stock when a named person is named**: "Sam Altman said X" over a Pexels developer. Use his Wikipedia photo.
4. **Subtitles off-screen**: check CAPTION_STYLE coords are in libass 288-PlayRes space; verify with `ffmpeg -frames:v 1` before full render.
5. **Audio ≠ video length**: clamp with ffprobe + `-t` on final pass.
6. **No CTA**: every news video ends on either a question the viewer answers, a resource they click, or a next-step they take. Never just end.
