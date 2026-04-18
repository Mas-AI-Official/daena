# Skill Mining Pipeline

The continuous loop that keeps Daena's skill corpus ahead of the
market. Connectors are hardware. Skills are software. Competitors can
buy the same APIs; they cannot buy 10 months of compounded, staleness-
monitored, governed skill packs.

This doc defines the end-to-end pipeline that the Skill Governance
department runs on a daily cadence. It references existing Daena
infrastructure where it exists (`skill_refinery/` package, NBMF
tiers, Research department) and fills the gaps.

---

## The Five-Stage Loop

```
                            +-------------------+
                            |  1. DISCOVER      |
                            |  Research dept    |
                            |  watches sources  |
                            +---------+---------+
                                      |
                                      v
                            +-------------------+
                            |  2. EXTRACT       |
                            |  SkillGovernance  |
                            |  parses content   |
                            |  into skill seeds |
                            +---------+---------+
                                      |
                                      v
                            +-------------------+
                            |  3. REFINE        |
                            |  3-pass: gap /    |
                            |  improve / critic |
                            +---------+---------+
                                      |
                                      v
                            +-------------------+
                            |  4. PROMOTE       |
                            |  T0 -> T2 -> T3   |
                            |  validated in     |
                            |  real engagements |
                            +---------+---------+
                                      |
                                      v
                            +-------------------+
                            |  5. MONITOR       |
                            |  news_monitor     |
                            |  staleness alert  |
                            |  re-refinement    |
                            +---------+---------+
                                      |
                                      v
                           (loop back to DISCOVER
                             when staleness hits)
```

Every stage has existing infrastructure or a well-scoped gap.

---

## Stage 1 — Discover (Research department)

**What already exists**: nothing specific to continuous source-polling.

**Gap to fill** (Phase N.1):

- `backend/app/services/skill_refinery/source_registry.py` NEW
  - Registry of `SourceSubscription` rows: `{source_type, url_or_id,
    cadence_secs, last_polled_at, last_item_at, filter_rules, rank_weight}`
  - Source types: `youtube_channel`, `rss`, `reddit_sub`, `hn_tag`,
    `product_hunt_topic`, `github_trending`, `mcp_registry`,
    `substack`, `podcast_feed`, `app_store_reviews`.
- `backend/app/services/skill_refinery/source_poller.py` NEW
  - Async scheduler (driven by the existing Heartbeat system).
  - One poll function per source type. Returns `DiscoveryItem` dicts
    with standardized shape: `{source, title, url, content_ref,
    published_at, signals: {upvotes, comment_count, author_authority}}`.
  - Respects rate limits + per-source backoff. Reuses the existing
    security OPSEC timing controller where scraping is involved.

**Seed subscriptions (from CONNECTOR-CATALOG Section 12)**:

- YouTube: Alex Hormozi, Sabri Suby, SaaStr, Lenny Rachitsky, Lex
  Fridman (selected episodes by vertical).
- RSS: Paul Graham essays, First Round Review, A Smart Bear, High
  Growth Handbook.
- Reddit: r/sales, r/SaaS, r/startups, r/Entrepreneur, r/cybersecurity,
  r/msp, r/sysadmin (for gap mining).
- HN tags: "Ask HN: what do you wish existed," "Show HN" in target
  verticals.
- Product Hunt topics: AI, Security, Sales.
- MCP registries: Anthropic, Smithery, PulseMCP polled daily.
- GitHub trending: Python + security + AI filters.
- App Store / Play Store: reviews for target-vertical apps via AppFollow
  or custom scraper.

**Output**: `DiscoveryItem` rows written to a new `discovery_items`
table. Research department triages: `PROMOTE_TO_EXTRACTION`,
`DEFER`, `DISMISS` with reason.

## Stage 2 — Extract (Skill Governance department)

**What exists**: `backend/app/services/skill_refinery/extraction_service.py`
already parses content into skill drafts. It accepts text; today's
callers are mostly developer-focused (code review, research).

**Gap to fill** (Phase N.2):

- `extraction_service.py` extended with multi-modal:
  - Video/audio extraction via Whisper (reuse `voice/stt_pipeline.py`
    `FasterWhisperProvider`). Output: timestamped transcript chunks.
  - Longform text segmentation (heading-aware, paragraph-coherent).
  - App-review extraction (star rating + review text + app metadata).
  - Commit / PR extraction (diff + message + author) for security skills.
- Multi-pass LLM extraction:
  1. First pass: segment content into "skill candidates" (action + when +
     why). Heuristic-fast, cheap model.
  2. Second pass: for top N candidates, fetch full context window and
     produce a draft skill spec (see skill schema below).
  3. Third pass: **Quintessence Council** debates each draft with three
     expert lenses (domain expert, skeptic, end user). Disagreements
     surface, lowest-quality drafts get dropped.

**Skill schema (T0 seed shape, stored in `refined_skills` table)**:

```json
{
  "id": "skill:sales.cold-email.problem-agitate-solve",
  "title": "Cold email via Problem-Agitate-Solve",
  "domain": "sales",
  "sub_domain": "cold_email",
  "trigger": "authoring a first cold email to a mid-market prospect with identified pain",
  "steps": [
    { "action": "State the observed pain in 1 sentence with evidence", "example": "..." },
    { "action": "Amplify the cost of inaction in 2 sentences", "example": "..." },
    { "action": "Present the resolution path in 1-2 sentences", "example": "..." },
    { "action": "Soft single-step CTA", "example": "15 min next Tue?" }
  ],
  "anti_patterns": [
    "Opening with company pitch",
    "More than 120 words",
    "Multi-step CTA"
  ],
  "source_refs": ["youtube:hormozi:VID-ID:00:12:30", "book:dotcom-secrets:chapter-4"],
  "dcp_lenses_used": ["expert_copywriter", "skeptical_buyer", "deliverability_engineer"],
  "tier": "T0",
  "validation_count": 0,
  "last_validated_at": null,
  "staleness_threshold_days": 90
}
```

## Stage 3 — Refine (Skill Governance department)

**What exists**: `backend/app/services/skill_refinery/refinement_service.py`
already runs the 3-pass: gap finder → improver → critic. Circuit
breaker in place (`MAX_CONCURRENT=3`, 60s timeout, 100K daily token
budget).

**Gap to fill** (Phase N.3):

- Domain-specific prompt packs for each category (sales, marketing,
  security, support, legal, finance, ops). Reuses DCPs already in
  `dcps.json`.
- **Adversarial refinement pass**: run the draft past a "competitor
  has this" lens and a "user will misuse this" lens. Outputs failure
  modes appended to `anti_patterns`.
- Source-provenance integrity check: every claim in the refined skill
  must trace to a `source_ref`. Unsupported claims are flagged.

## Stage 4 — Promote (Skill Governance + real usage)

**What exists**: NBMF tier model (T0 raw → T1 draft → T2 refined →
T3 institutional → T4 founder-private). Retrieval service at
`retrieval_service.py` already searches skills by domain and semantic
similarity.

**Gap to fill** (Phase N.4):

- `skill_promotion_service.py` NEW
  - Promotion rules:
    - T0 → T1: refinement pass complete, no critic blocker.
    - T1 → T2: used in at least 3 real engagements without negative
      telemetry.
    - T2 → T3: used in 10+ engagements with net-positive conversion
      delta vs. the baseline skill for that domain. Founder approval
      required.
    - T3 → T4: reserved for founder-private tradecraft.
  - Instrumentation: every skill retrieval logs `skill_usage_event`
    rows with outcome fields (reply_received, meeting_booked,
    deal_progressed). These feed promotion thresholds.
  - Demotion rules: if a skill's rolling 30-day conversion falls below
    the baseline, demote T3 → T2 and trigger re-refinement.

## Stage 5 — Monitor (news_monitor + Heartbeat)

**What exists**: `backend/app/services/skill_refinery/news_monitor.py`
with 90-day staleness threshold. Today it is a utility function,
not a scheduled job.

**Gap to fill** (Phase N.5):

- Wire `news_monitor.scan_for_updates` into the Heartbeat daemon on
  a 24-hour cadence. Produces `staleness_alert` rows.
- For each staleness alert, auto-trigger Stage 1 discovery scoped to
  the stale skill's source list. If fresh content found, flow back
  through Stage 2.
- Tool-obsolescence detection: skills reference specific tool names
  and API versions. When an API deprecates, the skill flagged and
  queued for re-refinement with the new tool set.

---

## The Content-Ops Meta-Source

Masoud highlighted Hormozi-style content as a premium skill input.
One expert's 10 years of distilled wisdom is denser signal than 100
random blog posts. The Skill Mining pipeline treats these as
**anchored sources** with heavier rank weights:

| Anchor | Domain | Rank weight | Extraction mode |
|---|---|---|---|
| Alex Hormozi (YouTube + podcasts) | Offers + sales + ops | 1.0 | Full transcript + chapter-aware segmentation |
| Sabri Suby (King Kong) | Cold outbound + paid direct response | 0.9 | Same |
| Chet Holmes (Ultimate Sales Machine) | Enterprise sales fundamentals | 0.85 | Book + transcripts |
| Robert Cialdini | Persuasion frameworks | 0.95 | Book + talks |
| Steve Blank (Customer Development) | Early-stage product validation | 0.85 | Book + blog |
| Paul Graham | Startup fundamentals | 0.9 | Essay RSS |
| Lenny Rachitsky | PM + growth benchmarks | 0.8 | Substack |

Anchored sources get re-scanned on every publish and their extracted
skills propagate through the refinement pipeline automatically.

## Connector-Specific Skills

For each connector in `CONNECTOR-CATALOG.md`, Skill Governance
authors a dedicated skill pack. Example for HubSpot:

- `skill:hubspot.contact.upsert` — field mapping + dedup + error handling
- `skill:hubspot.deal.stage-progression` — governance-gated stage moves
- `skill:hubspot.property-limit` — field-count-safe enrichment writes
- `skill:hubspot.workflow.trigger` — kick off marketing flows from Daena
- `skill:hubspot.import.bulk` — rate-limit-aware bulk loader

Raw API access is cheap. These 5 skills per connector are what turn
cheap access into accurate output.

## Ownership and Cadence

| Stage | Department | Cadence | Typical volume |
|---|---|---|---|
| 1. Discover | Research | Hourly (per source cadence) | 50 to 500 items/day |
| 2. Extract | Skill Governance | Daily batch | 5 to 50 drafts/day |
| 3. Refine | Skill Governance | On-extract + on-stale | 2 to 20 refined/day |
| 4. Promote | Skill Governance + founder | Weekly review | 0 to 5 T3 promotions/week |
| 5. Monitor | Skill Governance via Heartbeat | Daily | 1 to 10 staleness alerts/day |

## Governance

Every stage routes through the 10-stage pipeline:
- Discovery polls respect SecurityGate (scraping allowed targets only).
- Extraction LLM calls cost-capped by the Refinery circuit breaker.
- Promotion to T3 or T4 requires approval (founder for T4).
- Every source ingestion and every refined skill writes an audit
  chain entry.

## Metrics That Matter

- **Fresh skills per week**: target 3 new T2+ skills/week by end of
  Phase N.
- **Staleness backlog**: target below 10 open alerts at any time.
- **Tier distribution**: target 60% T2, 30% T3, 10% T4 among skills
  used in live customer work.
- **Conversion delta**: skills retrieved for an engagement must show
  >= 15% improvement on the primary metric (reply rate, meeting
  conversion, close rate) vs. no-skill baseline. Otherwise demote.
- **Source coverage**: at least one fresh (under 90 days) skill per
  CORE-tier connector category.

## What Ships in Phase N (6 weeks)

1. `source_registry.py` + seed subscriptions populated.
2. `source_poller.py` for YouTube, RSS, Reddit, Hacker News, MCP
   registries (5 source types).
3. `extraction_service.py` multi-modal extension (Whisper already
   available from Phase I).
4. Quintessence Council lens pack for the 7 top skill domains.
5. 10 production-grade (T3) skill packs seeded from Hormozi + Suby +
   Cialdini + HubSpot docs + Apollo docs.
6. `skill_promotion_service.py` with telemetry + demotion rules.
7. Heartbeat-wired staleness monitor.
8. Research department dashboard showing discovery items + triage queue.

Out of scope for Phase N (lands in Phase O):
- Autonomous "find a gap, build a product, ship it" full automation.
- Cross-tenant skill sharing.
- Skill marketplace (Daena sells skill packs to other orgs).
