---
name: bugcrowd-prospector
description: Identify companies with AI features + active bug bounty programs as outbound targets. Score by AI-product signal × company size × program maturity.
trigger: Weekly on Sunday night or on-demand.
outputs: D:\Claude-Coworker\companies\target-list.md
requires: web browsing, apollo skill (optional), Common Room (optional)
claude_only: false
---

# Bugcrowd-Adjacent Outbound Prospector

## Purpose

Find companies that already care about security (they run bounty programs)
AND have AI features in production (they have the pain) AND have decision-
makers we can reach (the target is reachable). Output a weekly target list
for the architect engagement.

## Ideal customer profile

- **Size:** Series A → Series C SaaS · 20–500 employees
- **Industry:** Fintech, healthtech, legal tech, security tools, devtools,
  infra (high governance bar)
- **AI signal:** They have a live AI feature — a chatbot, an AI-assisted
  workflow, a RAG over their docs, a Copilot-style integration. Public
  changelog mentions AI in the last 12 months.
- **Security signal:** Active bug bounty program on Bugcrowd or HackerOne.
  (This tells us the CISO gets buy-in for security spend.)
- **Reachable:** Decision-maker (CTO / CISO / VP Eng / Head of AI) has a
  Gmail or findable work email.

## Sources

1. **Bugcrowd program directory** — https://bugcrowd.com/programs (public programs)
2. **HackerOne directory** — https://hackerone.com/directory (public programs)
3. **Intigriti** — https://app.intigriti.com/programs (optional)
4. **Apollo** — filter by "AI" keyword + company size + role — via apollo skill
5. **Common Room** (optional) — enrich with engagement signals
6. **GitHub code search** — "prompt_injection" "LLM" "langchain" "OpenAI" in package.json → companies using AI in prod

## Scoring

```
score = ai_signal × company_size × program_maturity × reachability
```

- `ai_signal` (0–1):
  - +0.4 public AI feature launched in last 6 months
  - +0.3 AI-specific security role in job postings
  - +0.2 changelog mentions "AI", "LLM", "RAG", "agent"
  - +0.1 blog posts / talks about AI product
- `company_size` (0–1):
  - 0.8–1.0 for Series A/B (ideal)
  - 1.0 for Series C
  - 0.6 for pre-seed/seed (might be too early)
  - 0.4 for Fortune 500 (too slow to close)
- `program_maturity` (0–1):
  - 0.8 private invite-only programs (serious about security)
  - 0.6 public with critical-severity payouts
  - 0.3 public with <$500 max payout
  - 0 if no program at all
- `reachability` (0–1):
  - 1.0 if decision-maker email found
  - 0.6 if LinkedIn profile found (we can DM via Sales Navigator or warm intro)
  - 0.3 if only generic contact@ email
  - 0 if unreachable

Ignore scores < 0.4.

## Output format

Write to `D:\Claude-Coworker\companies\target-list.md`:

```markdown
# Outbound Target List — [auto-updated weekly by bugcrowd-prospector]

Last run: [ISO timestamp]. Target cadence: 100 new per week.

## This Week's Priority 25

| Rank | Company | AI feature | Program | Contact | Score | Observation |
|------|---------|-----------|---------|---------|-------|-------------|
| 1 | [Company, link] | [their AI feature] | [Bugcrowd URL] | [name, role, email] | 0.91 | [1-line observation for the TODO(Masoud) email line] |
| 2 | ... | ... | ... | ... | ... | ... |

## Weekly batch (full 100)

[Scored list with contact + observation]

## Blacklist / do not contact

[Companies that have previously declined, bounced, or asked to be removed]
```

## Execution

1. Pull the directories via WebFetch.
2. For each company, scrape: program URL, payout range, AI-feature signals.
3. Cross-reference with Apollo for decision-maker + email.
4. Generate a 1-line observation per target (the TODO line from email-template.md).
5. Score + rank.
6. Write the target list.

## Safety + governance

- Respect robots.txt.
- Rate limit: 1 request per 5 seconds per source.
- Never scrape authenticated pages.
- Do NOT send the emails. That&apos;s the `bugcrowd-outreach` skill, which
  requires explicit per-send approval.
- Keep the blacklist honest — if someone asked to be removed, honor it
  forever.

## Handoff

Once the target list is populated, `bugcrowd-outreach` skill generates
emails for human approval + send.
