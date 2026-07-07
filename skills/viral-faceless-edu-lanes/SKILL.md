---
name: viral-faceless-edu-lanes
description: Three viral content lanes reverse-engineered from the top faceless educational IG accounts in 2026 Q2. Each lane maps to ONE specific algorithm signal (saves / shares / comments) that IG and Threads weight heaviest. Trigger when the user wants viral-format content, countdowns, stats, or myth-busting posts.
metadata:
  type: skill
  domain: contentops
  reverse_engineered_from:
    - https://www.instagram.com/theaiengineer/
    - https://www.instagram.com/ai_curious/
    - https://www.instagram.com/futurepedia/
    - https://www.instagram.com/dailydoseofdata_science/
    - https://www.instagram.com/growthmindsetbusinesss/
    - https://www.instagram.com/bytebytego/
  added: 2026-05-26
---

# Viral Faceless-Edu Lanes

Three viral content lanes plus their scene types. Reverse-engineered from cross-account pattern analysis of the top faceless educational IG accounts. Each lane is engineered for ONE specific algorithm signal:

| Lane | Primary Signal | Why It Wins | Best For |
|---|---|---|---|
| `viral_list` | **Saves** | Lists are screenshotable + bookmarkable | Tool roundups, top-5 frameworks, skill ladders |
| `stat_shock` | **Shares** | Single quotable stat = tweetable | Industry data, % shifts, growth stats |
| `myth_vs_reality` | **Comments** | Debate-bait by design (algo weight ~5×) | Common misconceptions, buzzword decoding |

## Lane Selection Guide

| Topic shape | Pick |
|---|---|
| "Top 5 / 10 X" / "Best AI tools" / "5 ways to" | `viral_list` |
| "87% of devs..." / "By the numbers..." / "1 in 4..." | `stat_shock` |
| "The myth of..." / "What beginners think..." / "Buzzword decoded" | `myth_vs_reality` |
| "X vs Y vs Z" 3-way compare | `terminal_compare` (existing) |
| "V1 NAIVE → V2 → V3 scaling story" | `system_design` (existing) |
| Single concept explainer | `education` (existing) |

## Lane 1: `viral_list` (countdown)

**Visual signature**:
- 3-7 ranked items revealed as a countdown (5→4→3→2→1)
- Huge number (50% of frame) per item, bold sans-serif
- Neon accent color per rank
- "#1" reveal at the end with a payoff
- Closing CTA drives SAVES ("Save this for later") or COMMENTS ("Which #1 surprised you?")

**Scene type**: `numbered_list_countdown`

**diagram_spec contract**:
```json
{
  "items": [
    {"rank": 5, "title": "Cursor",     "blurb": "AI-first code editor, free tier strong"},
    {"rank": 4, "title": "Claude Code", "blurb": "Agentic CLI for whole-project work"},
    {"rank": 3, "title": "Codex",       "blurb": "GPT-5.5 in your terminal"},
    {"rank": 2, "title": "Replit",      "blurb": "Browser IDE + AI agent built in"},
    {"rank": 1, "title": "v0",          "blurb": "UI-first prompting — design → working app"}
  ],
  "countdown_direction": "down",
  "cta_line": "Which #1 surprised you?"
}
```

**Angles** (override via `angle_override` param):
- `countdown_5_to_1` — default, save-driver
- `top_5_tools` — tool roundup with icons + use cases
- `skills_progression` — beginner-to-expert ladder
- `do_this_not_that` — wrong/right pairs

## Lane 2: `stat_shock` (single huge stat)

**Visual signature**:
- ONE giant number fills 60% of frame (e.g. `87%`, `$1.2B`, `10x`)
- 1-line setup ABOVE the number
- 3-line context BELOW
- Small source citation (credibility)
- Minimal decoration — the number IS the content

**Scene type**: `stat_shock_card`

**diagram_spec contract**:
```json
{
  "big_number": "87%",
  "setup": "Out of every 100 software engineers we surveyed...",
  "context": "...87 use an AI coding assistant daily. Just 18 months ago it was 28%. The shift isn't coming — it already happened.",
  "source": "Stack Overflow Developer Survey 2026",
  "implication": "If you're not using one yet, you're already behind."
}
```

**Angles**:
- `single_giant_stat` — default
- `before_after_stat` — 2 numbers with delta
- `shock_percentile` — surprising %
- `growth_curve` — 2-point trend

## Lane 3: `myth_vs_reality` (2-panel debate-bait)

**Visual signature**:
- LEFT panel: red tint, "MYTH" headline
- RIGHT panel: green tint, "REALITY" headline
- Each panel has 4-8 word headline + 2-line elaboration
- Closing line: "Tag someone who needs this" OR "Comment if you disagree"
- Drives comments because both factions argue (half defend myth, half defend reality)

**Scene type**: `myth_vs_reality`

**diagram_spec contract**:
```json
{
  "myth": {
    "headline": "More data = better AI model",
    "elaboration": "People think the path to better AI is feeding it more text. It's the lazy belief."
  },
  "reality": {
    "headline": "Curation beats quantity 10x",
    "elaboration": "The top models train on FEWER but higher-quality tokens. A clean 500GB beats a noisy 5TB."
  },
  "closing_line": "Comment if you've seen this play out in your own projects."
}
```

**Angles**:
- `common_misconception` — default
- `industry_lie` — marketing vs reality
- `beginner_vs_pro` — naive vs scale-aware view
- `buzzword_decoded` — marketing term → plain meaning

## How To Invoke

CLI:
```bash
# viral_list lane
python -m contentops.motion_diagram_pipeline \
  --lane viral_list \
  --topic "5 AI Tools That Make You 10x Faster" \
  --angle countdown_5_to_1

# stat_shock lane
python -m contentops.motion_diagram_pipeline \
  --lane stat_shock \
  --topic "87% of devs now use AI assistants daily"

# myth_vs_reality lane
python -m contentops.motion_diagram_pipeline \
  --lane myth_vs_reality \
  --topic "The biggest myth about RAG"
```

Python:
```python
from contentops.motion_diagram_planner import build_motion_diagram_item

item = build_motion_diagram_item(
    lane="viral_list",
    topic="Top 5 AI Coding Tools in 2026",
    angle_override="top_5_tools",
)
```

## Auto-Routing (Lane Router)

The router classifies topics by keyword:

- `viral_list` triggers on: `top 5 / 7 / 10`, `best 5`, `5 tools`, `5 ways`, `ranked from`, `tier list`
- `stat_shock` triggers on: `% of`, `1 in `, `study finds`, `survey shows`, `doubled`, `tripled`, `10x`
- `myth_vs_reality` triggers on: `myth vs`, `biggest myth`, `common misconception`, `people think`, `debunked`, `buzzword`

The router gives viral lanes FIRST refusal so they don't get scooped by `education` for borderline topics like "5 ways to learn RAG".

## Inspiration Sources Auto-Scrape

Six new sources added to `data/inspiration_sources.yaml` with `lane_hint`:

- `theaiengineer` → viral_list
- `ai_curious` → viral_list
- `growthmindsetbusinesss` → viral_list
- `futurepedia` → stat_shock
- `dailydoseofdata_science` → stat_shock
- `prompt.engineer` → education

The scheduled task `ContentOps_Inspiration_Scrape` pulls captions from each and queues viral_queue items with the right `lane_hint` pre-set.

## Algorithm Signal Weights (2026 Q2)

This is why each lane targets a specific signal:

| Signal | IG ranking weight | Threads weight | TikTok weight |
|---|---|---|---|
| Comments | ~5× | ~3× | ~2× |
| Shares | ~3× | ~4× | ~3× |
| Saves | ~2.5× | ~1.5× | (less important) |
| Likes | 1× | 1× | 1× |

Comments are the biggest lever on IG. That's why `myth_vs_reality` is the highest-engagement-potential of the three lanes — it's literally engineered to start arguments. Use it sparingly so the audience doesn't feel manipulated.

## Combining With Existing Lanes

You can run a SERIES across lanes. Example campaign on "AI Coding Tools":

| Week 1 | `viral_list` | "Top 5 AI Coding Tools" — drives saves + follows |
| Week 2 | `stat_shock` | "87% of devs use AI coding daily" — drives shares |
| Week 3 | `myth_vs_reality` | "Myth: AI replaces devs. Reality: it 10x's good devs" — drives comments |
| Week 4 | `terminal_compare` | "Cursor vs Claude Code vs Codex — 6-axis comparison" — drives saves + deep engagement |

Each week reuses the same topic-cluster but in a different format, so the algorithm sees diverse signal types from your account — exactly what triggers "boost" boost from the IG algo.

## Brand Voice Constraint

Per `publish_now.py _enforce_brand_voice()`, all generated copy across these lanes is filtered through the GenAI-with-vision brand frame:
- Standalone "bot" → "agent"
- "chatbot" → "generative AI"
- First "AI agent" → "AI agent with vision" (unless vision cue already present)

This applies to titles, body, CTAs in every lane.
