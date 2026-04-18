---
name: customer-support-empathy-playbook
description: "Draft a customer support response using the LAER (Listen-Acknowledge-Explore-Respond) empathy framework with de-escalation for angry / confused / frustrated customers. Use when a support ticket lands with emotional signal (complaint language, urgency markers, cancellation threat). For routine how-do-I tickets use customer-support:draft-response instead."
department: Customer Support
cost_tier: low
tier: T2
requires:
  - customer_message
  - customer_tenure_or_plan
  - issue_severity_1_to_5
staleness_threshold_days: 365
source_refs:
  - "harvard-business-review:empathy-customer-service-2026"
  - "zendesk:de-escalation-playbook-2026"
  - "servicenow:consumer-empathy-survey-2026"
dcp_lenses:
  - senior_cx_lead
  - brand_voice_editor
  - retention_specialist
---

# LAER Empathy Framework for Support Responses

91% of 2026 customers rank empathy as non-negotiable, even from bots. The trick: empathy that is structural (not performative) + a concrete next step (not a platitude).

```
L  Listen       -- reflect the exact thing they said, not a paraphrase
A  Acknowledge  -- name the feeling + validate it is reasonable
E  Explore      -- one clarifying question OR one explicit path forward
R  Respond      -- the actual resolution or commitment, with a deadline
```

Every response has all four. Missing any one breaks trust.

## The four parts, with concrete templates

### L -- Listen
Quote the customer's exact words (one short phrase) before responding. Signals you actually read. Never "I understand your concern" — that paraphrase is the most trust-destroying support phrase in the English language.

> Right: "You wrote that 'the approval never showed up in the inbox' -- that's the problem we'll solve today."
> Wrong: "I understand you're having trouble with approvals."

### A -- Acknowledge
Name the feeling + a one-sentence reason it is reasonable. Do NOT apologize for the customer's existence ("sorry you feel that way"). Apologize for the specific gap.

> Right: "That is frustrating -- the whole point of the approval system is that it surfaces, not hides."
> Wrong: "I'm sorry you're upset."

### E -- Explore
Either a tight clarifying question (if missing info) OR a "here's what I'm going to do" preview (if you have enough info). Never both. Never "please provide more details" -- ask the one specific question you need.

> Right: "Can you paste the exact timestamp of the first approval request? I'll trace it in our audit log while you reply."
> Wrong: "Please provide more information so we can help."

### R -- Respond
The concrete commitment with a deadline. Deadlines under 24h are the highest trust builder in support. If the fix takes longer, commit to a check-in deadline instead.

> Right: "I'll have the audit trace to you by 3pm your time today. If the fix takes longer than that, you'll hear from me first with a timeline -- not from you chasing us."
> Wrong: "We'll look into this and get back to you."

## De-escalation tier (use when severity >= 4)

If the ticket contains any of:
* cancellation / refund / "cancel my account" language
* profanity or hostile tone
* legal / regulatory escalation threats ("my lawyer", "BBB", "FTC")
* social-media shame threat ("I'm tweeting this")

Then add a de-escalation preamble BEFORE the LAER response:

```
De-escalation opener (3 sentences, in this order):
1. Take ownership personally: "This landed on my desk and I'm going to fix it."
2. Name the stakes: "You're right to be frustrated -- <specific cost> is unacceptable on our side."
3. Set a faster-than-expected deadline: "You'll hear from me in <X hours>, not the usual <Y>."
```

Do not beg. Do not grovel. Ownership + pace + competence de-escalates faster than any apology.

## Retention save-the-customer layer (use when plan >= paid OR tenure >= 6mo)

If the customer is paid and showing churn signal, stack LAER with the retention save-sequence:

1. **Diagnose** the root cause in one sentence (the specific broken expectation, not the surface issue).
2. **Reverse risk** -- offer something asymmetric they'd keep even if they leave (month free, extended trial of the next tier, a deliverable that shows our commitment).
3. **Future-state** -- one sentence about what the relationship looks like in 30 days if they stay, framed around their original job-to-be-done.

Example retention add-on:
> "You signed up for the governance audit chain, and that's exactly what broke on you. To make this right: your next month is on us whether you stay or not, and I'm personally assigning <name> as your point of contact for the next 30 days. In 30 days, the audit trace we're building for this incident will be the tightest one you've ever seen -- that's my commitment."

## Boundaries (do NOT do)

* Don't promise refunds without authority -- escalate to the listed escalation contact.
* Don't share internal root-cause speculation ("our engineer pushed a bad deploy") before confirmation -- say "we're investigating" truthfully.
* Don't match the customer's tone if they're hostile. Stay measured. Hostility matched = escalation; calm competence = de-escalation.
* Don't use the phrase "for security reasons we can't..." unless you follow it with what you CAN do.

## Output contract

```
## L  Listen
  [1-2 sentences quoting their words]

## A  Acknowledge
  [1 sentence naming the feeling + why it is reasonable]

## E  Explore
  [1 clarifying question OR 1 preview of action]

## R  Respond
  [concrete commitment + deadline]

## Escalation / Retention additions
  [only if severity >= 4 or tenure >= 6mo; clearly labeled]

## Send-ready response
  [the 4 blocks above, woven into a natural email or chat-ready paragraph]
```

Never output a support response without the deadline. A support message without a deadline is an announcement, not a commitment.
