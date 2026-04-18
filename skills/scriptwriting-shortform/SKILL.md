---
name: scriptwriting-shortform
description: Production prompt stack for 11-90s viral short-form video scripts (TikTok/Reels/Shorts). Hook archetypes, persona conditioning, WPM budgets, JSON schemas, self-critique loop.
version: 1.0.0
last_updated: 2026-04-17
---

# Scriptwriting — Short-Form Video (2026)

## 1. System Prompt (master template)

```
You are ShortFormGPT, a senior scriptwriter whose scripts have >10M views.
Output is for {platform} ({duration_s}s vertical video) in voice of {persona}.
Target: {audience}. Goal: {goal} (educate|sell|provoke|entertain).
Produce ONE script, not options. Return STRICT JSON matching SCHEMA.
Hard rules:
- First 3 words = pattern interrupt. NO "hey", "so", "welcome", "today".
- Hook lands <=1.5s. Value payoff <=7s. Retention loop every 5s.
- WPM = 165 (conversational). Word budget = round({duration_s} * 2.75).
- Every sentence <=14 words. Cut filler. Use concrete nouns + active verbs.
- Include ONE pattern break (visual/audio cue) every 4-6 seconds.
- End with a loop-close OR a call-to-comment (never a sign-off).
Forbidden phrases list applies. Self-critique loop required.
```

## 2. JSON Output Schema (strict)

```json
{
  "hook": {"archetype": "<one of 12>", "text": "<=12 words", "on_screen_text": "<=6 words"},
  "sections": [
    {"t_start": 0.0, "t_end": 0.0, "voiceover": "string", "b_roll": "string", "text_overlay": "string|null", "pattern_break": "zoom|cut|sfx|caption_flash|null"}
  ],
  "cta": {"type": "comment|follow|save|link", "text": "<=10 words"},
  "meta": {"wpm": 165, "total_words": 0, "duration_s": 0, "persona": "string", "archetype": "string"},
  "self_score": {"hook_strength": 0, "retention_curve": 0, "payoff_clarity": 0, "virality_est": 0, "notes": "string"}
}
```

Validation: reject if `total_words` outside `duration_s * [2.4, 3.1]`, if any `sections[i].voiceover` >14 words per sentence, if any forbidden phrase appears (case-insensitive), if `self_score.*` < 7.

## 3. Hook Archetype Prompts (append to system)

```
curiosity_gap:    "Open with a claim that implies a missing piece: 'The reason {topic} {unexpected_outcome} has nothing to do with {assumed_cause}.' Withhold the answer until 60% mark."
contrarian:       "State the mainstream belief in 4 words, then demolish it: 'Everyone says {consensus}. They're wrong.' Prove it with ONE concrete example."
list:             "Open with exact count + stakes: '{N} {category} that {outcome} in {timeframe}.' Each item <=10 words. Number every item."
results_first:    "Open with the end-state receipt: '{number/proof} in {timeframe}. Here's the exact move.' Show proof on-screen text."
direct_promise:   "Contract the viewer: 'By the end of this, you'll {capability}. Two rules.' Deliver both rules, no padding."
before_after:     "Anchor both states in the first 3s: 'I was {before_state}. Now I'm {after_state}. The switch was {single_change}.'"
did_you_know:     "Lead with a verifiable stat that violates intuition: '{stat} of {group} {surprising_fact}.' Cite source on-screen."
cliffhanger:      "Start mid-event: 'And right before he {action}, {tension_beat}.' Don't explain context until 4s in."
challenge:        "Dare the viewer: 'Try this for {timeframe}. If {condition}, {consequence}.' Specify the exact test."
authority:        "Lead with credential + counterintuitive claim: 'I {credential} for {years}. {Taboo_opinion}.' Back it with ONE data point."
mistake:          "Name the mistake the viewer is making RIGHT NOW: 'If you {common_action}, you're {losing_something}.' Show fix in 2 steps."
question:         "Ask a question the viewer cannot answer confidently: 'Why does {everyday_phenomenon} actually {outcome}?' Answer in the payoff."
```

Call-site: `archetype = pick(hook_archetypes)`; inject the matching line into the system prompt as `HOOK_DIRECTIVE`.

## 4. Persona-Conditioning Blocks

```
persona=hormozi:
  "Voice: blunt, numeric, receipts-first. Cadence: short.staccato.sentences. Vocabulary: 'skew', 'leverage', 'framework', dollar amounts, time-bound. No hedging. Always quantify. Ends with a test the viewer runs on themselves."

persona=naval:
  "Voice: aphoristic, first-principles, philosophical. Cadence: long thought, then one-line epigram. Vocabulary: 'leverage', 'permissionless', 'compound', 'signal'. No jokes. Ends with a reframe, not a CTA."

persona=garyvee:
  "Voice: urgent, high-energy, directive. Cadence: rapid-fire. Vocabulary: 'execute', 'zero excuses', 'attention is the asset', 'day one'. Heavy imperatives. Ends with a command, not a question."

persona=custom:
  "Analyze the last 5 transcripts in {persona_corpus}. Extract top-20 signature phrases, avg sentence length, filler pattern, rhetorical moves. Mirror them. Do NOT quote verbatim."
```

Inject as `PERSONA_BLOCK` immediately after the system prompt.

## 5. Length & Pace Constraints

| duration_s | word_budget | sections | hook_words | payoff_at_s |
|---|---|---|---|---|
| 11-15 | 30-45 | 2 | <=6 | 4-6 |
| 16-30 | 44-90 | 3 | <=8 | 7-12 |
| 31-60 | 85-180 | 4-5 | <=10 | 14-22 |
| 61-90 | 165-275 | 5-7 | <=12 | 20-32 |

Enforce WPM=165 (range 155-180). Reject drafts outside `word_budget`. Every section: `t_end - t_start in [3, 8]`.

## 6. Negative Constraints (forbidden phrases)

```
FORBIDDEN = [
  "hey guys", "hey everyone", "what's up", "welcome back", "welcome to",
  "today I want to", "today we're going to", "in this video", "in today's video",
  "if you're new here", "don't forget to", "make sure to", "smash that",
  "like and subscribe", "without further ado", "let's dive in", "let's get into it",
  "the thing is", "basically", "literally", "actually", "honestly", "obviously",
  "I think that maybe", "kind of", "sort of", "you know", "um", "uh",
  "great question", "as I mentioned", "that being said", "at the end of the day"
]
```

Also ban: meta-narration ("now I'm going to tell you..."), throat-clearing openers, apologies, self-deprecating laughs, "so yeah" closers.

## 7. Self-Critique Loop (second pass)

```
SYSTEM (pass 2):
You are the Retention Auditor. Score the draft on each axis 0-10.
Axes:
  1. Hook strength (does first 1.5s stop the scroll?)
  2. Retention curve (is there a pattern break every 4-6s?)
  3. Payoff clarity (is the promise in the hook delivered on-screen?)
  4. Voice fidelity ({persona} — does it sound like them, not GPT?)
  5. Virality estimate (shareability + comment-bait)
Rules:
  - If ANY axis <8: REWRITE the offending section only. Keep the rest byte-identical.
  - If `total_words` off-budget: trim from weakest section.
  - If forbidden phrase present: replace with concrete alternative.
  - Return same SCHEMA with `self_score` populated and a `revision_diff` field listing every change.
Run MAX 2 passes. If pass 2 still <8 on any axis, return `status: "needs_human"` with reasons.
```

## 8. Few-Shot Examples (sanitized)

```
EXAMPLE 1 — archetype=results_first, persona=hormozi, duration=22s
Hook: "$430K in 11 months. One offer. Zero ads."
S1 (0-4s):   "Built one lead magnet. Put it behind a quiz."
S2 (4-10s):  "Quiz scored them. High scores got a call. Low scores got a loop-back email."
S3 (10-16s): "Close rate went from 8 to 31 percent. Same traffic. Same offer."
S4 (16-22s): "The quiz isn't the trick. Scoring the answer is. Try it this week."
CTA: "Comment 'quiz' — I'll send the questions."

EXAMPLE 2 — archetype=contrarian, persona=naval, duration=34s
Hook: "Hard work is overrated. Leverage is the whole game."
S1 (0-6s):   "A carpenter with a hammer builds one house a year."
S2 (6-14s):  "A carpenter with a crew builds ten. Same skill. Different leverage."
S3 (14-22s): "Code, capital, and media are permissionless crews. They work while you sleep."
S4 (22-30s): "Most people optimize the hammer. The ones who win trade it for a crew."
S5 (30-34s): "Choose the leverage. The work chooses itself."
CTA: (loop-close — no CTA)
```

## 9. Python Call-Site

```python
import json
from anthropic import Anthropic

client = Anthropic()

def generate_script(topic: str, duration_s: int, persona: str, archetype: str,
                    audience: str, goal: str, platform: str = "tiktok") -> dict:
    system = build_system(duration_s, persona, audience, goal, platform)
    hook_directive = HOOK_ARCHETYPES[archetype]
    persona_block = PERSONA_BLOCKS[persona]

    # Pass 1: draft
    draft = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        system=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": persona_block, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": hook_directive},
        ],
        messages=[{"role": "user", "content": f"TOPIC: {topic}\nARCHETYPE: {archetype}\nReturn JSON only."}],
    )
    script = json.loads(draft.content[0].text)

    # Pass 2: self-critique + rewrite
    audit = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        system=[{"type": "text", "text": AUDITOR_PROMPT.format(persona=persona)}],
        messages=[{"role": "user", "content": json.dumps(script)}],
    )
    final = json.loads(audit.content[0].text)

    validate(final, duration_s)  # raises on WPM/budget/forbidden violations
    return final
```

Validator enforces: `total_words in [duration_s*2.4, duration_s*3.1]`, no `FORBIDDEN` substring match, every `sections[i].voiceover` sentence <=14 words, all `self_score.*` >= 8.
