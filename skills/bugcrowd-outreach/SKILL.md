---
name: bugcrowd-outreach
description: Generate personalized cold emails from the target list, pass through Daena governance, send via Gmail after human approval.
trigger: User says "draft outreach for [company]" or "send this week's batch".
inputs: D:\Claude-Coworker\companies\target-list.md, outbound/email-template.md
outputs: Daena approval queue entries, Gmail drafts, sent log
requires: gws-gmail-send, Daena governance pipeline, Shield always on
claude_only: false
---

# Bugcrowd-Adjacent Outreach Engine

## Purpose

Turn the target list into sent emails while respecting Masoud's voice and
the governance pipeline. Every email gets:
1. A specific TODO(Masoud) observation — no mail-merge placeholders
2. Shield prompt-injection scan (defensive — on the TARGET's public text we ingested)
3. Approval queue entry (Masoud reviews the final draft before send)
4. Gmail send via `gws-gmail-send` recipe
5. Send log entry for pipeline tracking

## Process (per target)

1. **Pull context** — company name, AI feature, decision-maker, observation
   from `target-list.md`.
2. **Select template** — Template A (architect pitch) is default. Template
   B for AI Act deadline urgency (if company is EU-adjacent). Template C
   only for warm network.
3. **Personalize** — swap placeholders, write the TODO observation line
   using the observation from the prospector.
4. **Governance gate** — Daena Shield scans the email content for:
   - Accidental over-claims (e.g., "Google customer" when Google is just a
     bounty program we're registered on)
   - PII leakage from other prospects (never paste content from other
     emails)
   - Tone check (warm, direct, not salesy)
5. **Approval queue** — email lands in Daena's approval UI. Masoud reviews,
   edits if needed, clicks approve.
6. **Send** — `gws-gmail-send` recipe sends from `masoud.masoori@mas-ai.co`.
7. **Log** — append to
   `D:\Claude-Coworker\companies\outreach-log.md`: `sent_at`,
   `company`, `contact`, `subject`, `template_used`, `thread_id`.
8. **Follow-up tracker** — schedule a 5-day follow-up draft (Template A
   follow-up variant) automatically. Human approves before send.

## Rate limits + deliverability

- Max 30 emails/day from Masoud's Gmail (respect Google's per-day limits
  for unauthenticated domains).
- 2+ hour gap between sends to same domain.
- Never send from a new IP without a warm-up period.
- If SPF/DKIM/DMARC not fully set up for mas-ai.co, flag and block.
- Blacklist honored absolutely: if `target-list.md` blacklist has them,
  the skill refuses to draft.

## Failure modes to handle

- **Gmail bounce**: log as bounced, remove from active list, re-score
  deliverability.
- **Reply: not interested**: remove from list, add to blacklist.
- **Reply: send it**: alert Masoud immediately — he has 48 hours to deliver
  the recon.
- **No reply after 5 days**: queue follow-up (human approves).

## Output format (approval queue entry)

```json
{
  "id": "<uuid>",
  "recipient": "<email>",
  "company": "<name>",
  "subject": "<subject line>",
  "body": "<email body>",
  "template": "A|B|C",
  "observation_line": "<the TODO(Masoud) observation>",
  "shield_flags": ["<any warnings>"],
  "status": "pending_approval"
}
```

Masoud reviews in Daena UI → approves/edits/rejects.

## Safety + governance (critical)

- Shield always on. Never bypass.
- Never send without explicit per-email human approval (this is cold
  outreach to real people — NOT a Daena use case where autopilot is
  acceptable).
- Observation line must reference something the prospect has ACTUALLY
  publicly done — never fabricate. If the prospector couldn&apos;t find a
  real observation, the draft is skipped.
- Unsubscribe link in every email footer (legal requirement for commercial
  email in many jurisdictions).

## Success metric

- 100 personalized sends per week sustained.
- 3–5% reply rate (industry baseline for cold B2B is 1–2% — our
  personalization should beat that).
- 1+ free-recon booked per week from outreach.
- 1+ paid engagement signed per month from outreach alone (the rest come
  from referrals + inbound).
