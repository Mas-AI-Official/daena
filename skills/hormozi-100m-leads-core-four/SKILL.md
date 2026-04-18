---
name: hormozi-100m-leads-core-four
description: "Design a lead-generation plan via Hormozi's Core Four (warm outreach, cold outreach, content, paid ads). Use when building the marketing calendar, deciding which channel to double down on, or kicking off a product launch. Output is a weekly-cadence playbook, not a single email -- see cold-email-pas for one-off outbound."
department: Marketing
cost_tier: low
tier: T2
requires:
  - ideal_customer_profile
  - weekly_budget_usd
  - founder_time_hours_per_week
  - current_lead_count_last_30d
staleness_threshold_days: 90
source_refs:
  - "hormozi:100m-leads:part-II-core-four"
  - "hormozi:more-better-new-ch-10"
dcp_lenses:
  - expert_growth_marketer
  - content_strategist
  - paid_ads_operator
---

# Core Four Lead Generation Plan

There are only four ways to get leads. Every scaled business uses multiple. Most startups pick one and die.

```
                  Warm        Cold
One-to-one     │  DM          │  Cold DM / email / call
One-to-many    │  Content     │  Paid ads
```

## Decision matrix

Pick which channel to lead with based on where the constraint is:

| Constraint | Lead channel | Why |
|---|---|---|
| No audience, <$500/wk | **Warm outreach** (1:1 to existing network) | Free, signal-dense, validates offer |
| No audience, $500-5k/wk | **Cold outreach** | Scalable 1:1, trackable, predictable |
| Growing audience, <$5k/wk | **Content** (1:many, free) | Compounds, builds trust, preselects |
| Product-market fit + $5k+/wk | **Paid ads** | Buys speed, hurts without the first three |

The output of this skill is a 4-channel weekly plan where at least ONE channel is active. Growth happens when 2 or 3 are active simultaneously.

## Weekly-cadence template

For each channel the plan enables, output the following block:

### Warm outreach (friends, colleagues, past customers)
```
Volume      : X DMs / week
Script      : [1-line opener + ask]
Audience    : [segment of existing connections]
Automation  : manual only
Output KPI  : # of conversations moved to discovery
```

### Cold outreach (email, LinkedIn, phone)
```
Volume      : X emails / Y LinkedIn touches / Z calls
Hook        : [Hormozi "WIIFM in 3 words" headline]
Segment     : [ICP criteria -- firmographic + pain signal]
Sequence    : D1 value message -> D3 case-study follow-up -> D6 breakup
Tooling     : Apollo + Instantly or Smartlead (see apollo:* skills)
Output KPI  : reply rate, meeting rate, % opted-out
```

### Content (YouTube, LinkedIn, blog, podcast, X)
```
Format      : [long-form / short-form / written]
Cadence     : N posts / week
Themes      : 3 pillars, 1 CTA per pillar
Hook formulas: one of {PAS, 1-3-1, bold claim + receipts}
Repurpose   : 1 long -> 5 shorts -> 10 text posts
Output KPI  : views -> profile visits -> newsletter signups -> bookings
```

### Paid ads
```
Platform    : Meta / Google / LinkedIn / YouTube
Ad type     : conversion-optimised lead form or landing page
Creative    : 3 variations of hook + 3 angles (pain / dream / authority)
Targeting   : ICP layers + lookalikes, exclude existing list
Budget      : starting CPA ceiling = LTV / 3
Output KPI  : CPL, lead-to-SQL rate, payback period
```

## Hormozi's "more, better, new" rule

Before adding a channel, squeeze what's running:
1. **More** of the current channel (2x volume before anything else)
2. **Better** (split-test hook, offer, audience, call-to-action)
3. **New** channel (only after more + better are maxed)

When this skill runs, check: has the existing active channel doubled its volume this quarter? If no, pushing a new channel is premature.

## Daena-specific notes

* **Founder-led content beats anonymous content** for a B2B governance product. The skill should bias toward Masoud-first content angles.
* **Cold outreach into regulated industries** (healthcare, finance, government) has 6-12 week sales cycles. Factor that into KPI targets.
* **ICP for Daena (2026)**: SaaS CTO at 50-500 person company; compliance officer at mid-market; government procurement lead for sovereign AI. Don't send the same hook to all three.
* **Never buy leads lists** for Daena. Always source fresh via Apollo/Common Room + signal-based filtering. Inbox warm-up before sending.

## Output contract

A markdown block with exactly four H3 sections (one per channel), a final H3 "This week's one priority" naming the single channel to measure + improve this week, and a one-line commitment the founder signs off on.
