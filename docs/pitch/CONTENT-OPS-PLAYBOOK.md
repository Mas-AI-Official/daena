# Content Ops Playbook

The proven-playbook skill packs that Marketing agents consume. These
are the "software" Masoud was asking for — the skill that makes a
generic LLM call produce Hormozi-grade output instead of SaaS-brochure
sludge.

All skill packs below follow the `CONNECTOR-CATALOG.md` skill schema
and get authored, refined, and promoted through the pipeline in
`SKILL-MINING-PIPELINE.md`. Seven are targeted for Phase N launch.

---

## Why these specific frameworks

Picked by two filters:

1. **Volume of surviving evidence**. Hormozi has 10+ years of
   recorded talks, 2 books, thousands of paid-student outcomes. Every
   claim traces to a specific outcome. Same for Cialdini, Chet Holmes.
2. **Cross-domain transfer**. A persuasion framework that wins in
   fitness sales also wins in B2B SaaS demos. The deeper the framework,
   the broader the transfer.

The goal is **not** to quote experts. The goal is to encode their
decision heuristics as skill steps so the agent applies them reflexively
without needing the founder to prompt "write like Hormozi would."

---

## Seed Skill Pack 1 — Offer Construction (Hormozi)

- **id**: `skill:marketing.offer.grand-slam-offer`
- **Trigger**: designing a landing page, a sales deck, or a pricing
  proposal. Any moment when "why buy this, now, at this price" needs
  to be answered.
- **Steps**:
  1. State the dream outcome plainly. (The result the buyer actually wants.)
  2. Quantify the perceived likelihood of achievement. (Our reason to believe.)
  3. Minimize time delay. (How fast can they have it.)
  4. Minimize effort and sacrifice. (How easy is it on them.)
  5. Stack value. Bundle adjacent outcomes until the perceived value
     is 10x the price.
  6. Add risk reversal (guarantee, trial, money-back, free-until-value).
  7. Name the offer. Make the name the thing they will repeat to others.
- **Anti-patterns**:
  - Feature-listing without connecting to dream outcome.
  - Discount as the primary lever (trains buyer to wait for discount).
  - Guarantee so weak it does not reverse risk.
- **Source refs**: Hormozi — $100M Offers; Hormozi YouTube archive
  on Grand Slam Offers.
- **DCP lenses**: expert_copywriter, skeptical_buyer, pricing_analyst.

## Seed Skill Pack 2 — Cold Email (Problem-Agitate-Solve)

- **id**: `skill:sales.cold-email.problem-agitate-solve`
- **Trigger**: first cold touch to a mid-market prospect where pain
  is identifiable from OSINT (breach disclosure, job posting, recent
  funding).
- **Steps**:
  1. One-sentence opener naming the observed pain with evidence. Not
     flattery, not "hope you are well."
  2. Two sentences amplifying cost of inaction. Dollar cost, time
     cost, risk cost. Concrete.
  3. One or two sentences presenting resolution path with proof
     point.
  4. Soft single-step CTA. Day + duration + purpose. Example: "15
     minutes next Tuesday to walk through how we solved this for
     {peer company}?"
  5. Signature: one human name, one company, one URL. No image, no
     six-line signature.
- **Anti-patterns**:
  - Opening with "we." Reader cares about themselves, not you.
  - More than 120 words. Cold email is triage reading.
  - Multi-step CTA or calendar link in first email.
  - Corporate jargon, buzzwords.
- **Source refs**: Sabri Suby Sell Like Crazy; Predictable Revenue;
  30MPM Outbound Playbook.
- **DCP lenses**: expert_copywriter, deliverability_engineer, skeptical_buyer.

## Seed Skill Pack 3 — Close Framework (Hormozi Close-and-Pay)

- **id**: `skill:sales.close.hormozi-cap`
- **Trigger**: end of a discovery call with a qualified prospect.
- **Steps**:
  1. Summarize their pain in their words back to them. Wait for
     confirmation.
  2. Present the outcome Daena delivers in one sentence. Wait for
     confirmation.
  3. State price without apology or softening. Wait.
  4. If silence lasts more than 3 seconds: do not speak. First one
     to speak loses.
  5. Address the objection that surfaces. Usually time, money, or
     trust — Hormozi's three axes.
  6. Single-step ask: "Card or invoice?" Not "do you want to think
     about it?"
  7. If hesitation: offer a risk reversal (14-day exit, 7-day pilot,
     money-back guarantee).
  8. Silent again. Let them decide.
- **Anti-patterns**:
  - Discounting before the prospect has objected.
  - Long monologue after stating price.
  - Multi-path ask ("do you want to keep talking, or think about it,
    or see a deck?").
- **Source refs**: Hormozi Acquisition.com training library; Chet
  Holmes Ultimate Sales Machine chapter on the seven-second closing
  language.
- **DCP lenses**: expert_closer, skeptical_buyer, compliance_officer.

## Seed Skill Pack 4 — Objection Handling (Cialdini-Blended)

- **id**: `skill:sales.objection.cialdini-blended`
- **Trigger**: prospect raises a price, timing, or trust objection.
- **Steps**:
  1. Acknowledge explicitly. "That is a fair concern." (reciprocity
     of honesty).
  2. Reframe with social proof: who else had this concern, what they
     decided, how it turned out. Specific names when possible
     (commitment + consistency; authority).
  3. Isolate: "If this concern were addressed, is there anything else
     standing in the way?" (commitment).
  4. Address the isolated concern with evidence. Never hypotheticals.
  5. Confirm and move to close: "Does that reframe the decision for
     you?"
- **Anti-patterns**:
  - Dismissing the objection ("that's not really a problem").
  - Reflexively discounting.
  - Stacking multiple reframes before letting them respond.
- **Source refs**: Cialdini Influence; Cialdini Pre-Suasion.
- **DCP lenses**: expert_closer, skeptical_buyer, behavioral_scientist.

## Seed Skill Pack 5 — Content Multiplication (One-to-Eleven)

- **id**: `skill:marketing.content.one-to-eleven`
- **Trigger**: Masoud publishes one piece of longform content
  (essay, demo, interview, podcast appearance).
- **Steps**:
  1. Extract 3 thesis sentences. (Atomic claims that can stand alone.)
  2. For each, produce 3 surface formats: tweet / LinkedIn / short
     video script. 9 atomic outputs.
  3. Publish original as blog post + SEO description + OpenGraph
     image. 2 more outputs.
  4. Schedule across 10 to 14 days. Respect platform-specific
     cadence caps.
  5. Log which atomic claim drove the most engagement; promote that
     claim to the next content cycle.
- **Anti-patterns**:
  - Posting the same sentence on every platform (platform algorithms
    down-rank cross-posts).
  - Posting 11 pieces in one day (cannibalizes reach).
  - Skipping the engagement-tracking step (no compounding learning).
- **Source refs**: Gary Vaynerchuk Content Pyramid; Lenny Rachitsky
  on content strategy; Justin Welsh Content OS.
- **DCP lenses**: content_strategist, platform_algorithm_expert,
  brand_voice_guardian.

## Seed Skill Pack 6 — Gap Mining (Reddit + App Store)

- **id**: `skill:research.gap-mining-reddit-app-store`
- **Trigger**: Masoud or Daena asks "what pain is underserved in
  {vertical}."
- **Steps**:
  1. Load target subreddits and target app-store entries. (Subreddit
     list + app list are per-vertical configs.)
  2. Pull top posts of last 90 days + 1- and 2-star reviews of last
     90 days.
  3. LLM pass: classify each item into pain categories. Reject off-
     topic (jokes, meta, marketing).
  4. Weight: post = upvotes x recency; review = negativity score x
     recency x app popularity.
  5. Cluster into themes with embeddings. Surface top 5 themes.
  6. For each theme, pull 3 direct quotes with permalink.
  7. Propose 1 product hypothesis per theme (one sentence + the quote
     that backs it).
- **Anti-patterns**:
  - Relying on summaries alone; always keep direct quotes for sales
    evidence.
  - Ignoring the "I already tried X" pattern (that's where you learn
    about competitors).
  - Over-fitting to a single loud user.
- **Source refs**: Customer Development (Blank + Dorf); Jobs-To-Be-Done
  interview methodology (Ulwick); every pain-mining practitioner
  podcast archive.
- **DCP lenses**: customer_development_interviewer, statistical_rigor,
  competitive_analyst.

## Seed Skill Pack 7 — Governance-Safe Voice Discovery

- **id**: `skill:sales.voice.discovery-governed`
- **Trigger**: Daena is on a discovery voice call with a prospect.
- **Steps**:
  1. Recording-consent intro (required; handled by the voice session
     frame).
  2. Five discovery questions in order. Each question names an outcome
     + an observed pain signal.
  3. Listen. Do not speak for 8 seconds after prospect finishes
     answering. Silence is signal.
  4. Mirror. Repeat the last 3 words of their answer back as a
     question. This surfaces the real pain.
  5. Summarize what you heard in one sentence. Wait for confirmation.
  6. Propose a next step: demo, scoping doc, or paid pilot. One ask,
     not three.
  7. Log: full transcript, classified discovery points, next-step
     commitment.
- **Anti-patterns**:
  - Pitching during discovery.
  - Skipping the mirror step.
  - Naming pricing on a discovery call unprompted (tier 3 action
    anyway; governance pauses the call).
- **Source refs**: Chris Voss Never Split The Difference; Chet Holmes
  interview methodology; Hormozi sales funnel archive.
- **DCP lenses**: expert_closer, active_listener, governance_officer.

---

## How These Skills Ship

Each seed is initially **T0 raw**: drafted from the framework above.
The Skill Refinery 3-pass runs (gap finder → improver → critic). The
Quintessence Council debates with the three listed DCP lenses. Output
is the refined T1 pack.

Promotion to T2 requires: used in 3 real engagements with neutral or
positive telemetry. Promotion to T3: 10 engagements, measurable lift
vs. baseline. See `SKILL-MINING-PIPELINE.md` Stage 4.

All seven pack T1 drafts are ready to author in Phase N.1. They
become operational when Phase O (Autonomous Execution) binds them
into `AutonomousPlan` steps.

---

## What's NOT In This Playbook

- No "use cutesy emoji-forward copy" skill. Brand voice is
  founder-defined; does not live here.
- No "manipulation dark patterns" skill. Cialdini frameworks used
  honestly; anti-patterns explicitly rule out deceptive use.
- No "grey-hat growth hacks" that break platform TOS. Daena is
  governance-first; skills that violate TOS never ship.
- No generic "write a blog post" skill. If the output is generic,
  the skill did not exist. Every skill in this file has a specific
  trigger and specific steps.

## Ownership

- **Author**: Skill Governance department (with Quintessence debate).
- **Consumer**: Marketing, Sales, Support departments call them via
  Skill Refinery retrieval when composing an agent turn.
- **Reviewer**: Founder for any T3 promotion.
- **Staleness**: 90 days unless the underlying framework materially
  changes (e.g., Hormozi publishes a refinement, Cialdini releases
  new research, a major platform changes algorithm). `news_monitor.py`
  flags, Research triggers re-refinement.
