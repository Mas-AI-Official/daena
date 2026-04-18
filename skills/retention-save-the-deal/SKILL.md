---
name: retention-save-the-deal
description: "Save an at-risk customer or stalled deal via diagnose-reverse-future (DRF) + the 'one asymmetric concession' rule. Use when a customer says 'we're considering alternatives', a renewal is stalled, or a deal that was qualified goes dark. Outputs a save-call script + email fallback + an internal risk note. Do NOT use for net-new prospecting (see hormozi-100m-leads) or hostile-complaint response (see customer-support-empathy-playbook)."
department: Sales
cost_tier: medium
tier: T3
requires:
  - customer_name
  - plan_or_deal_stage
  - last_contact_date
  - specific_concern_or_blocker_if_known
staleness_threshold_days: 180
source_refs:
  - "corporate-executive-board:challenger-customer"
  - "gainsight:renewal-save-playbook-2026"
  - "hormozi:100m-leads:nurture-ch-11"
dcp_lenses:
  - senior_ae_renewal_specialist
  - customer_success_lead
  - finance_commercial_lens
---

# Save-the-Deal Playbook

A customer going dark or saying "we're evaluating alternatives" means one thing: the value equation in their head has shifted. Either Dream Outcome moved up (they need more), Perceived Likelihood moved down (we haven't demonstrated it), or Time/Effort moved up (something got harder).

The save is NOT discounting. Discounting confirms the customer's suspicion that the price was wrong all along. The save is **reframing + asymmetric commitment**.

## DRF framework

```
D  Diagnose    -- name the ONE shift that caused the wobble
R  Reverse     -- one asymmetric move that removes risk from their side
F  Future-state -- a concrete picture of the relationship in 30 / 60 / 90 days
```

## Step 1 -- Diagnose

Pull the ONE shift. Never diagnose 3 things. If you can't reduce to one, do more discovery before responding.

Common shifts for Daena:
* **Internal politics** -- a new stakeholder joined and has a different preference
* **Budget freeze** -- not product-related; the save is time-based not value-based
* **Competing tool landed free in an existing contract** -- Microsoft, Google, AWS bundled something
* **Implementation went slower than promised** -- perceived likelihood dropped
* **Use case shifted** -- the original job-to-be-done changed under them

Output this part as: `Diagnosis: <one-sentence shift> | Evidence: <what they said or didn't say>`.

## Step 2 -- Reverse risk (the asymmetric concession)

The move should be something they'd keep VALUE FROM even if they leave. Not "a discount." Discounts make the customer anchor on the new price forever.

Examples of asymmetric concessions (pick the lowest-cost one that matches the diagnosis):

| Diagnosis | Asymmetric concession |
|---|---|
| Implementation slow | Dedicated concierge migration for 30 days, free |
| Competing tool landed | Co-design a comparison doc THEY can use internally to argue for us |
| Budget freeze | Extend current terms 60 days at no cost, revisit after freeze |
| New stakeholder | Custom exec briefing with Masoud present |
| Champion leaving | Full knowledge-transfer package + a playbook so the next person gets it |

The rule: the concession **costs us less than the deal size x churn probability**, AND the customer would keep value from it even if the save fails. Never grant a concession whose value disappears if they churn.

## Step 3 -- Future-state

Paint the relationship at 30 / 60 / 90 days. Specific deliverables the prospect will have by those dates. This re-establishes Perceived Likelihood in the value equation.

Template:
```
In 30 days: <specific deliverable + metric>
In 60 days: <specific deliverable + metric>
In 90 days: <specific deliverable + metric>
Who owns each: <name + role>
```

Vague future-states ("you'll love working with us") make the save worse. Concrete dates + names + numbers are the save.

## Save-call script (15-20 min)

Use this structure verbatim. Deviations are fine; skipping sections isn't.

```
[0-2 min]   Reset expectation: "I'm not here to change your mind
            today. I'm here to make sure we understand your shift
            so either we earn the renewal or you leave with clarity."

[2-7 min]   Discovery of the ONE shift. Ask. Do not answer your own
            question. Long silences are fine.

[7-10 min]  Mirror it back: "So if I'm hearing right, the shift is
            <X>, and the blocker for you is specifically <Y>."

[10-15 min] Propose the asymmetric concession. Frame it explicitly
            as "you'd still benefit from this even if you leave."

[15-18 min] Future-state with dates. Get verbal commitment to the
            30-day marker.

[18-20 min] Exit cleanly. Send a written recap within 60 min.
            No exceptions.
```

## Internal risk note (always produce)

Even if the save works, capture this for CS team:
```
Customer: <name>
Shift detected: <one sentence>
Concession granted: <what + dollar cost>
Early-warning signal that would have caught this earlier: <one sentence>
Champion health score (1-5): <N>
Next check-in date: <date>
```

This note becomes the feedback loop that makes future saves earlier and cheaper.

## Daena-specific save levers

* **Technical debt on our side** -- if the save requires a feature, commit to a date and make that date. Broken save-promises kill 3 deals each.
* **Local-mode option** -- if the concern is data residency, a free migration to local-mode (FREE tier runtime) is an asymmetric concession we uniquely own.
* **Founder face time** -- Masoud on a call is a lever available in 2026 that isn't available at scale. Use it for ENT-tier saves; don't spend it on $99/mo PRO renewals.
* **NBMF memory transfer** -- if the customer leaves, we offer to export their T2+ memory tiers so they keep what they built. Makes "stay with us" the low-risk option BECAUSE leaving is also low-risk.

## Output contract

```
## Diagnosis
  [one sentence + evidence]

## Asymmetric concession
  [what + why it costs us < deal x churn-probability + why it survives their churn]

## Future-state (30 / 60 / 90)
  [three dated deliverables with owners]

## Save-call script
  [15-20 min outline, customized to this customer]

## Email fallback (if they won't take a call)
  [200 word max, structured around DRF, ends with ONE specific ask]

## Internal risk note
  [six-line template populated]
```

No "we value your business" openings. That phrase marks us as a generic vendor. The customer already knows we value their business -- otherwise we wouldn't be on the save call.
