---
name: consultative-discovery-spin-meddic
description: "Run a discovery call (or review a transcript) using SPIN questioning + MEDDIC qualification + Challenger reframe. Use when the customer has booked a 30-60 min discovery call, or when reviewing a sales call transcript to decide if the deal advances. Outputs a qualification scorecard + next-step recommendation, not an email draft."
department: Sales
cost_tier: medium
tier: T2
requires:
  - prospect_company
  - prospect_role
  - call_transcript_or_notes
staleness_threshold_days: 180
source_refs:
  - "rackham:spin-selling"
  - "dixon-adamson:challenger-sale"
  - "meddic-sales-methodology"
  - "hormozi:100m-leads:cold-to-close-ch-13"
dcp_lenses:
  - senior_enterprise_ae
  - solution_engineer
  - procurement_buyer
---

# Consultative Discovery Framework

Three frameworks stacked. Used together they produce disciplined calls that move deals, not "good chats" that don't close.

* **SPIN** -- the question architecture (Situation, Problem, Implication, Need-payoff)
* **MEDDIC** -- the qualification scorecard (Metrics, Economic buyer, Decision criteria, Decision process, Identify pain, Champion)
* **Challenger** -- the reframe ("teach-tailor-take-control") when the prospect thinks they already understand the problem

## SPIN question ladder

Run in order. Each tier multiplies the urgency of the previous answer.

### 1. Situation (2-3 max)
Gather facts the prospect already knows. Keep brief; situation questions are the lowest-trust-building type. Examples for Daena:
* "Which runtimes is your team using for AI-assisted work today?"
* "Roughly how many agent tool calls per week does your platform handle?"

### 2. Problem (5-8)
Surface the gap between current state and desired state. Listen for emotional language.
* "Where does governance slow your team down the most?"
* "What happens when an audit asks how a model made a decision?"
* "Which actions today require Slack-ping approval that interrupts engineers?"

### 3. Implication (5-8, the highest-leverage tier)
Make the cost of inaction felt. Connect the problem to dollars, headcount, or risk.
* "If a compliance request takes 3 months, what deal slips?"
* "How many engineer-hours per week are spent building governance glue instead of product?"
* "What's the cost of a single failed SOC 2 renewal?"

### 4. Need-payoff (3-5)
Let the prospect articulate the value themselves. Do NOT pitch here.
* "If approvals could happen in under 30 seconds with a full audit chain automatically, what would that unlock?"
* "If you could plug Daena in and have governed agent tool calls the same week, what deadlines move?"

The SPIN discipline: if you haven't run at least one Implication and one Need-payoff question, the call is not a discovery call, it's a demo.

## MEDDIC scorecard (output this verbatim)

```
M - Metrics: Which quantifiable outcome does the prospect need?
             [pull specific numbers the prospect said, not ones you offered]
E - Economic buyer: Who has sign-off authority AND budget?
             [name + title + "confirmed present on this call" / "not identified"]
D - Decision criteria: Which evaluation axes will they score us on?
             [list of 3-7 criteria they named, not our positioning]
D - Decision process: What steps remain between today and signed order?
             [e.g. legal review, security questionnaire, POC, board sign-off]
I - Identify pain: What does inaction cost them, in their words?
             [quote the prospect directly]
C - Champion: Who inside their org will sell this FOR us when we leave?
             [name + why they are motivated to champion; "no champion" is a dealbreaker]
```

Each slot: **confirmed / partial / missing**. A deal is only "qualified" when 5 of 6 are confirmed and Economic Buyer is one of them. Missing EB -> deal stays ambiguous no matter how good the prospect sounds.

## Challenger reframe (use selectively)

If the prospect says "we're already doing this with <X>" -- that's the Challenger trigger. Steps:
1. **Teach** -- give a non-obvious insight they didn't have (e.g. "most <X> tools log AFTER the fact; Daena's audit is tamper-evident at write time -- here's why that matters to your auditor specifically").
2. **Tailor** -- connect the insight to their exact situation (their industry, their team size, their deal).
3. **Take control** -- recommend the next step with authority. Don't ask "what would you like to do next?" -- say "here's what I recommend: <specific action + specific date>."

## Daena-specific prompts to probe

Ask these if not already answered:
* "Which governance mode (UNLEASHED / BALANCED / GOVERNED) matches your internal policy today?"
* "Do you need local-mode, hybrid, or cloud-only? This determines deploy time and integration cost."
* "Who owns the audit chain in your org -- security, compliance, or engineering?"
* "Are agents expected to call external APIs (Gmail, Slack, Drive)? This triggers OAuth setup."

## Output contract

```
## SPIN summary
  ### Situation findings (2-3 bullets)
  ### Core problem
  ### Implication (dollars / time / risk)
  ### Need-payoff (the prospect's own words)

## MEDDIC scorecard
  [6-row table with confirmed/partial/missing per slot]

## Qualification verdict
  [one of: QUALIFIED / PARTIALLY QUALIFIED / DISQUALIFIED]
  [one-line reason]

## Recommended next step
  [specific: meeting with EB by <date>, or POC scoped in <N> weeks, or disqualify now]

## Challenger reframe (if applicable)
  [single-paragraph teach-tailor-take-control script]
```

Never output "let's keep in touch" -- that's the failure mode. Either advance, disqualify, or specify the exact blocker that would unblock advance.
