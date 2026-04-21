---
name: hackathon-hunter
description: Crawl hackathon platforms weekly, rank by prize × deadline × MAS-AI strength match, output ranked pipeline for human review.
trigger: Run weekly on Sunday night or on-demand when user says "find hackathons".
outputs: D:\Claude-Coworker\hackathons\pipeline.md
requires: web browsing, scheduled-tasks
claude_only: false
---

# Hackathon Hunter

## Purpose

Keep a live pipeline of paying hackathons that match MAS-AI's edge (AI
security, LLM governance, multi-agent systems, RAG safety, agentic AI,
governed AI orchestration).

The hunter does NOT submit. It shortlists. A human reviews the pipeline
weekly and hands selected entries to the `hackathon-submit` skill.

## Sources to crawl

Primary (weekly):
1. **Devpost** — https://devpost.com/hackathons — filter: "AI", "Security", online-eligible, prize ≥ $5k
2. **MLH** — https://mlh.io/seasons/2026/events — filter: open-participation, virtual tracks
3. **lablab.ai** — https://lablab.ai/event — filter: AI/LLM tracks
4. **Dora Hacks** — https://dorahacks.io/hackathon — filter: web3-adjacent + AI
5. **HackerEarth** — https://www.hackerearth.com/challenges/ — filter: AI/ML/Data
6. **Kaggle competitions** — https://www.kaggle.com/competitions — filter: prize ≥ $10k, deadline ≥ 14 days

Secondary (monthly):
7. **Major foundation grants** — DARPA SBIR, NSF SBIR, EU Horizon open calls (these overlap the F6S tracker; coordinate)
8. **Bug bounty challenges with prize cadence** — Pwn2Own Vancouver, DEF CON CTFs (AI-specific tracks when announced)

## Scoring rubric (each hackathon gets a score 0–100)

```
score = (prize_weight × deadline_weight × match_weight) / normalizer
```

- `prize_weight`: log-scaled. $5k = 10, $25k = 25, $100k = 50, $250k = 75, $1M = 100.
- `deadline_weight`: 1.0 if ≥ 14 days to submit, 0.6 if 7–13 days, 0.2 if < 7 days, 0 if past.
- `match_weight`: 0–1 score based on keyword match to MAS-AI strengths:
  - +0.3 "AI security" / "LLM security" / "prompt injection" / "AI red team"
  - +0.3 "AI governance" / "audit trail" / "compliance" / "responsible AI"
  - +0.2 "multi-agent" / "agent orchestration" / "agentic AI"
  - +0.2 "RAG" / "LLM safety" / "hallucination"
  - +0.1 bonus if prize includes cash + API credits + mentorship (triple-benefit)
  - cap at 1.0

Ignore hackathons with score < 30.

## Output format

Write to `D:\Claude-Coworker\hackathons\pipeline.md`:

```markdown
# Hackathon Pipeline — [auto-updated weekly by hackathon-hunter]

Last run: [ISO timestamp]. Next run: [next Sunday ISO].

## This Week's Top 10

| Rank | Event | Prize | Deadline | Match | Score | Notes |
|------|-------|-------|----------|-------|-------|-------|
| 1 | [link] | $25k | 2026-05-10 | AI Security | 87 | Perfect fit — open to global, Masoud can solo. |
| 2 | ... | ... | ... | ... | ... | ... |

## Full ranking (N events, top 50 shown)

[Scored list]

## Excluded (below threshold)

[List with reason for exclusion, e.g., "wrong region", "past deadline", "weak match"]
```

## Execution

1. Run `WebFetch` on each source URL.
2. Parse hackathons (structured extraction).
3. Score each.
4. Write the pipeline file.
5. Emit a 1-line summary to Masoud via Claude-Coworker inbox: "Hackathon hunter: N new, M worth reviewing, top pick = [name] ($X, deadline Y)."

## Safety + governance

- Shield always on (per Daena governance).
- No auto-submission. Human approval gate between hunter and `hackathon-submit`.
- If a source site blocks crawling, mark it as `[UNREACHABLE]` in the output and continue with the rest.
- Rate limit: 1 request per 3 seconds per source.

## Handoff

When Masoud picks an event from the pipeline, the next step is the
`hackathon-submit` skill, which takes the chosen event + a project idea and
generates the submission package.
