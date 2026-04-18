---
name: cold-email-pas
description: "Cold email via Problem-Agitate-Solve. Use when authoring a first cold outreach to a mid-market prospect where a specific pain signal was identified (breach disclosure, tech stack gap, hiring signal, public complaint). Do NOT use for warm intros, event follow-ups, or after a reply."
department: Marketing
cost_tier: low
tier: T1
requires:
  - osint_pain_signal
  - prospect_first_name
  - prospect_company
  - peer_reference_optional
staleness_threshold_days: 90
source_refs:
  - "sabri-suby:sell-like-crazy:ch-6"
  - "predictable-revenue:cold-email-playbook"
  - "30mpm:outbound-playbook"
  - "hormozi:100m-leads:ch-9"
dcp_lenses:
  - expert_copywriter
  - deliverability_engineer
  - skeptical_buyer
---

# Cold Email via Problem-Agitate-Solve

The most validated cold-outbound skill in the corpus. PAS with
evidence-first hooks converts at 4 to 9% reply rate on well-qualified
lists. Generic "hope this finds you well" cold email converts at
0.2 to 1%.

## When to Use

Use this skill **only** when:

- The prospect has an observable pain (public breach, job post
  implying gap, AppStore 1-star review, tech-debt tweet, etc.).
- The send is a first touch, not a follow-up.
- The prospect is a mid-market-or-larger company where there is a
  named decision-maker.

Do **not** use for:

- Warm introductions (use `warm-intro-followup` skill instead).
- Replies (use `inbound-reply` skill).
- Mass-blast to a scraped list with no per-prospect signal.
- Regulated industries where specific compliance-language review
  is required first (route through Legal for redline).

## Structure (120 words hard cap)

1. **Hook** — one sentence naming the observed pain **with evidence**.
   - Example: "Saw the CrowdStrike advisory dropped affects your DC
     config — the CVE-2026-NNNN one."
   - Anti-pattern: "Hope you are doing well / noticed your company
     is doing great things in the space."

2. **Agitate** — two sentences amplifying the cost of inaction.
   Dollar cost, time cost, or risk cost. **Concrete.**
   - Example: "Teams in your size range are averaging 14 days of
     engineering time to ship a clean audit after it. We have seen
     two of your peers get slapped with SOC 2 re-audit fees because
     of it."
   - Anti-pattern: "This could be a real problem for your team."

3. **Solve** — one or two sentences with the resolution path and
   proof point. Name a peer company if possible.
   - Example: "We run governed pen tests that ship the report
     auditors accept. {Peer Company} ran one last month and closed
     the finding in three days."
   - Anti-pattern: "We are the leading platform in the space."

4. **CTA** — single-step, specific, low-friction.
   - Example: "15 minutes Tuesday 10am to walk you through what
     we did for {Peer Company}?"
   - Anti-pattern: "Let me know if you want to hop on a call some
     time this month or next."

5. **Signature** — one human name, one company, one URL. No
   six-line signature, no image, no unsubscribe-link pixel.

## Non-Negotiable Anti-Patterns

The following patterns are forbidden. If the draft contains any of
them, the critic pass MUST request a rewrite before the skill is
allowed to proceed:

- Opens with "I" or "We" (reader cares about themselves).
- Uses any of: "hope this finds you well," "I wanted to reach out,"
  "I noticed you," "circling back," "touching base," "synergy,"
  "leverage," "cutting-edge," "best-in-class."
- Exceeds 120 words (measured excluding signature).
- Multi-step CTA ("let me know if you want to chat, or we can do a
  deck, or I can send info").
- Calendar link in first email (reader has not earned the cost of
  clicking yet).
- Unsubstantiated claim ("we help companies scale 10x," "our AI is
  the most advanced").
- Discount lever as primary motivation.
- Mismatched urgency (made-up scarcity, fake deadlines).

## Governance Tier

This skill is **tier 2** (notified): the draft persists as a DRAFT
in `OutreachDraft`. The **send** is tier 3 (approval required) for
the first 90 days of any customer deployment, then loosens to tier 2
once reply-telemetry shows zero complaints. Mass-send (more than 50
recipients in 24h) stays tier 3 permanently.

## Telemetry Collected

Every draft authored with this skill records:

- `skill_ref: skill:sales.cold-email.problem-agitate-solve`
- `skill_version: {semver}`
- Draft word count
- Signal type used (breach, tech-stack, job-post, app-review, etc.)
- Send outcome: sent, bounced, replied_positive, replied_negative,
  replied_unsubscribe, ignored
- Time-to-reply

Telemetry feeds Skill Governance for promotion / demotion decisions
per `SKILL-MINING-PIPELINE.md` Stage 4.

## Example (Good)

```
Subject: CVE-2026-NNNN and your DC config

Adam,

Saw the CrowdStrike advisory dropped affects Cisco DC 12.5 on 17 --
your team's Github is still on 12.4. Teams your size average 14
engineering-days to clean a re-audit after it, and two of your
peers got slapped with SOC 2 re-audit fees last quarter because of
the timeline gap.

We run governed pen tests that ship reports auditors accept the
first time. Bishop Fox's closest competitor closed their Acme
engagement in three days with our output.

15 minutes Tuesday 10am to walk through what we did for Acme?

Masoud
MAS-AI Technologies
app.daena.mas-ai.co
```

Word count excluding signature: 104. All four sections present.
Evidence-first hook. Concrete cost of inaction. Peer reference.
Single-step CTA.

## Example (Bad, for critic training)

```
Subject: Quick question

Hi Adam,

Hope this email finds you well! I wanted to reach out because I
noticed your company is doing great things in the cybersecurity
space. At MAS-AI Technologies, we are the leading provider of
cutting-edge AI-native governed security solutions. We help
companies scale 10x while reducing compliance burden.

I would love to set up a quick 15-30 minute call this week or next
to explore synergies. Alternatively, I can send you our deck, or
we could do a full demo. Let me know what works!

Looking forward to hearing from you soon,

Masoud Masoori
Founder and CEO
MAS-AI Technologies Inc.
masoud@mas-ai.co | app.daena.mas-ai.co
[linkedin] [twitter] [calendly]

This email is confidential. If received in error, please delete.
Unsubscribe here.
```

Anti-patterns present: "hope this email finds you well," "I wanted
to reach out," "I noticed," "cutting-edge," "leading provider,"
"synergy," unsubstantiated 10x claim, multi-step CTA, 186 words,
six-line signature with links and disclaimer.

The critic pass rejects this draft. The refiner rewrites to the
Good example.

## Promotion Path

This skill is currently **T1** (drafted from reference frameworks).
Promotion to T2 requires 3 real engagements with neutral-or-better
reply telemetry. Promotion to T3 requires 10+ engagements with
measurable reply-rate lift vs. the baseline skill for this domain.

Skill Governance reviews promotion candidates weekly.
