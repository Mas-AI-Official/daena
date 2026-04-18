---
name: hormozi-grand-slam-offer
description: "Construct a Grand Slam Offer via Hormozi's Value Equation (Dream Outcome x Perceived Likelihood / Time Delay x Effort+Sacrifice). Use when packaging Daena tiers, enterprise pilots, launch promos, or any offer where the prospect said 'interesting' and you need to make it undeniable. Do NOT use for pure cold outreach (see cold-email-pas) or pricing spreadsheets (see finance:variance-analysis)."
department: Sales
cost_tier: low
tier: T2
requires:
  - target_segment
  - current_offer_or_price
  - dream_outcome_one_sentence
staleness_threshold_days: 180
source_refs:
  - "hormozi:100m-offers:part-III-IV"
  - "hormozi:value-equation-ch-7"
  - "hormozi:bonuses-guarantees-naming-ch-16-18"
dcp_lenses:
  - expert_copywriter
  - skeptical_buyer
  - finance_unit_economics
---

# Grand Slam Offer Construction

An offer the market cannot say no to, assembled via Hormozi's Value Equation and layered with scarcity, urgency, bonuses, guarantees, and a tested name.

```
                  Dream Outcome  x  Perceived Likelihood of Achievement
Value  =  ─────────────────────────────────────────────────────────────
                  Time Delay     x  Effort & Sacrifice
```

Attack all four levers. Most offers move only the numerator. The levers on the denominator (removing friction and waiting) are where the undeniable moves happen.

## Pipeline for Daena

Run these five steps in order. Output a structured offer card the user can paste into a deck, landing page, or email.

### Step 1 · Dream outcome
Articulate in one sentence what the prospect wakes up wanting. Avoid features. Avoid our product name.

> Wrong: "Daena runs local AI with governance."
> Right: "Your team ships AI-driven work without a security review ever blocking you again."

### Step 2 · List every obstacle
Brainstorm every reason the dream outcome doesn't happen today. Treat each obstacle as a product or bonus opportunity — every obstacle → one deliverable that eliminates it.

Template:
```
Obstacle                  | Deliverable                             | Tier
--------------------------|-----------------------------------------|-----
"audit takes 3 months"    | pre-built SOC 2 evidence pack           | PRO
"I don't know what skills | quarterly skill-refinement report       | ENT
  to give my agents"      |                                         |
```

### Step 3 · Attack the denominator
For each lever, answer:
* **Time delay**: what can we make instant? Hormozi: "speed is a feature." Daena → local-first install in 5 min vs 3-month enterprise SaaS onboarding.
* **Effort & sacrifice**: what can we remove from the buyer? Migration service, done-for-you templates, onboarding concierge.

### Step 4 · Stack bonuses until the unfair feeling
Add bonuses until the prospect's internal voice says "wait, this is too much." Rule: each bonus names the obstacle it removes and has a standalone dollar value. Total bonus value should be >= 5x the price.

Template:
```
Bonus 1: [name]          Removes obstacle: [...]    Value: $X
Bonus 2: [name]          Removes obstacle: [...]    Value: $Y
Bonus 3: [name]          Removes obstacle: [...]    Value: $Z
Total bonus stack value: $(X+Y+Z)    Price: $(X+Y+Z)/5
```

### Step 5 · Risk reversal
Add a guarantee that removes ALL financial risk. Hormozi's taxonomy:
* **Unconditional** (strongest): "30-day no-questions-asked, keep the bonuses."
* **Conditional**: "If you don't hit <outcome> by <date> and you did <X/Y/Z>, we <refund + pay you>."
* **Anti-guarantee** (use sparingly): "All sales final — here's why you still want it."

### Step 6 · Name & urgency
Name the offer so a CMO can repeat it after one hearing. Hormozi's MAGIC formula: **Magnetic reason why · Avatar · Goal · Interval · Container**.

Examples:
* "The 90-Day Governed-AI Launch Package for Regulated Mid-Market Teams"
* "Zero-to-Production Daena Starter: 14 Days, 2 Departments, SOC 2 Evidence Included"

Add urgency via real scarcity: cohort caps, pilot-slot windows, founding-customer pricing that steps up.

## Daena-specific guard-rails

* **Never promise uptime SLAs for local-mode** (it runs on the customer's own hardware).
* **Never bundle GPU compute into a fixed price** without a usage cap.
* **Every bonus must map to an existing Daena capability** — this skill creates the offer, not the roadmap.
* **If governance mode is GOVERNED**, route the offer draft through `legal:review-contract` before sending.

## Output contract

Return a markdown block with these sections, in this order:
```
## Offer name
## One-sentence dream outcome
## Who it is for (avatar)
## What's included (features -> benefits rewording)
## Bonus stack (with individual dollar values)
## Guarantee
## Price + urgency hook
## Total stack value vs price (the "unfair" math)
```

Plus a 3-line elevator pitch an SDR can read on a cold call without choking.
