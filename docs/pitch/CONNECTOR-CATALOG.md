# Daena Connector Catalog and Skill-Coverage Map

Single source of truth for every external service Daena's departments
can reach today, should reach next quarter, and why each matters.

The catalog is the **hardware layer**. The skill corpus (see
`SKILL-MINING-PIPELINE.md`) is the **software** that tells each agent
how to use that hardware without producing generic output.

Legend for each connector:
- **Tier**: `CORE` (Phase H/I blocker) / `GROWTH` (needed at 10 deals) / `FUTURE` (post Series A)
- **Access**: how Daena reaches it (MCP / REST / SDK / Browser / CLI)
- **Skill status**: `none` (we can call the API but produce generic output) / `raw` (T0 skill seed exists) / `refined` (T2+ skill pack in the Refinery) / `production` (T3+ proven in live engagements)
- **Department owner**: primary consumer

---

## 1. Customer Relationship (CRM)

Daena's own `crm.py` models (Account, Contact, Deal, OutreachDraft)
are the source of truth. External CRMs are write-through sinks. Pick
one anchor CRM per customer and mirror our state into theirs.

| Vendor | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **Attio** | CORE | REST API + MCP | none | Sales |
| **HubSpot** | CORE | REST API + official MCP | none | Sales |
| **Salesforce** | GROWTH | REST API (Lightning), large object model | none | Sales |
| **Close.io** | GROWTH | REST API, phone-native | none | Sales |
| **Pipedrive** | GROWTH | REST API | none | Sales |
| **Copper** | FUTURE | REST API (Google Workspace native) | none | Sales |
| **Folk** | FUTURE | REST API | none | Sales |

**Skill gap**: none of the CRM connectors ship with skill packs today.
The skills we need: "create contact with enrichment shape that survives
HubSpot's field-count limits," "safely upsert Salesforce leads without
triggering duplicate-detection rules," "map Attio object model to
Daena's Account/Contact schema." These are connector-specific and must
be authored by Skill Governance on first customer install.

## 2. Sales Intelligence + OSINT

Overlap with Daena's Layer 3 security OSINT stack is deliberate --
the providers that find attack surface are the same providers that
find buyers.

| Vendor | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **Apollo.io** | CORE | REST API | raw (stub in security/osint) | Sales / SecOps |
| **Hunter.io** | CORE | REST API | raw (stub in security/osint) | Sales / SecOps |
| **Common Room** | GROWTH | REST API + MCP | none | Sales |
| **Clay** | GROWTH | REST API (waterfall enrichment) | none | Sales |
| **ZoomInfo** | FUTURE | REST API | none | Sales |
| **Lusha** | FUTURE | REST API | none | Sales |
| **LinkedIn Sales Navigator** | FUTURE | unofficial scraping | none | Sales |

**Skill gap**: raw API access without the skill = generic prospect
lists. The skill: firmographic signal chaining, intent-signal weighting,
do-not-contact hygiene, email-verification tier selection, cost-caps
per enrichment tier.

## 3. Email and Messaging

| Vendor | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **Gmail** | CORE | OAuth REST (wired: `integrations/gmail_client.py`) | none | Marketing / Support |
| **Outlook / Microsoft 365** | CORE | Graph API | none | Marketing / Support |
| **SendGrid** | CORE | REST + webhooks | none | Marketing |
| **Resend** | GROWTH | REST API, developer-first | none | Marketing |
| **Mailgun** | GROWTH | REST + event webhooks | none | Marketing |
| **Loops.so** | GROWTH | REST API, warmup-friendly | none | Marketing |
| **Smartlead / Instantly** | GROWTH | REST API, cold-outbound optimized | none | Marketing |
| **Slack** | CORE | Bolt SDK, webhooks, MCP | none | Support / Internal |
| **Discord** | GROWTH | Bot API, webhooks, MCP | none | Marketing (community) |
| **Telegram** | FUTURE | Bot API | none | Support |
| **WhatsApp Business** | FUTURE | Cloud API (Meta) | none | Support |

**Skill gap**: deliverability tuning (SPF/DKIM/DMARC, warm-up schedules,
reply-detection classifiers), multi-channel sequencing, per-domain
throttling, reply-aware stop-rules. See `SKILL-MINING-PIPELINE.md`
for the proven-playbook sources.

## 4. Scraping and Data Sourcing

The layer Masoud highlighted directly. "Find the complaints, find
the gaps, find the buyers who already wrote the pain for us."

| Vendor / Source | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **Firecrawl** | CORE | REST API + MCP | none | Research / SecOps |
| **Apify** | CORE | REST API, actor marketplace, MCP | none | Research |
| **Bright Data** | GROWTH | REST API, residential proxies | none | SecOps (OPSEC) |
| **ScrapingBee** | GROWTH | REST API | none | Research |
| **Oxylabs** | FUTURE | REST API | none | SecOps |
| **Reddit API + Pushshift + GummySearch** | CORE | Python SDK (PRAW), REST | none | Research / Marketing |
| **App Store Connect scraping** (AppFollow, Sensor Tower, custom) | CORE | REST API + custom scrapers | none | Research |
| **Google Play reviews** | CORE | Google Play Developer API + scrape | none | Research |
| **Trustpilot** | GROWTH | REST API + scrape | none | Research |
| **G2 / Capterra / SoftwareAdvice** | GROWTH | scrape (anti-bot) | none | Research |
| **Hacker News (Algolia API)** | CORE | REST API, no auth | none | Research |
| **Product Hunt** | CORE | GraphQL API | none | Research |
| **YCombinator launches** | CORE | RSS + scrape | none | Research |
| **Twitter / X firehose** | GROWTH | paid API | none | Research / Marketing |

**Skill gap (largest in the whole catalog)**: the scraping skills
matter more than the scraping providers. Examples:

- **Reddit pain-mining skill**: watch target subreddits for "I wish X existed" / "this sucks" / "why isn't there" patterns. Rank by upvotes x recency x subreddit weight. De-duplicate into structured opportunity signals. Output: ranked gap list with direct quotes + posting context.
- **App Store complaint mining**: pull 1-star + 2-star reviews on target app. Extract "what broke" patterns with Cognitive Knowledge Graph. Output: weighted issue backlog for a competing product pitch.
- **YC launch watcher**: daily digest of YC launches in target verticals. Filter for funding stage + team size + geography. Output: prospect list plus partnership opportunities.

These are not API calls. They are **recipes** that combine API calls,
classifiers, weighting rules, de-duplication, and output formatting.
Each is a skill pack that lives in the Refinery and gets used by
Research and Marketing agents.

## 5. Content and SEO Intelligence

| Vendor | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **Ahrefs** | GROWTH | REST API | none | Marketing |
| **SEMrush** | GROWTH | REST API | none | Marketing |
| **Similarweb** | GROWTH | REST API | none | Research / Marketing |
| **BuzzSumo** | GROWTH | REST API | none | Marketing |
| **Mention / Brand24** | GROWTH | REST API + webhooks | none | Marketing / Support |

## 6. Telephony and Voice (Phase I)

Already planned in `VOICE-STACK-PLAN.md`. Pluggable providers:

| Vendor | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **VAPI** | CORE | REST API | none | Sales / Support |
| **Retell AI** | GROWTH | REST API | none | Sales |
| **Vocode (self-host)** | GROWTH | Python SDK, open source | none | SecOps (SOVEREIGN) |
| **Twilio Programmable Voice** | FUTURE | REST API | none | Internal |
| **Daily.co** | FUTURE | REST API + WebRTC | none | Internal |

## 7. Calendar and Scheduling

| Vendor | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **Google Calendar** | CORE | OAuth REST (wired: `calendar_client.py`) | none | Sales / Ops |
| **Microsoft Graph Calendar** | CORE | OAuth REST | none | Sales / Ops |
| **Cal.com** | GROWTH | REST API, open source | none | Sales |
| **Chili Piper** | GROWTH | REST API, routing-smart | none | Sales |
| **SavvyCal** | FUTURE | REST API | none | Sales |

## 8. Documents, Signatures, Contracts

| Vendor | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **Notion** | CORE | REST API + MCP (wired: `notion_client.py`) | none | Ops / Research |
| **Google Docs / Drive** | CORE | OAuth REST | none | Legal / Ops |
| **DocuSign** | GROWTH | REST API + Connect webhooks | none | Legal |
| **HelloSign / Dropbox Sign** | GROWTH | REST API | none | Legal |
| **Ironclad** | FUTURE | REST API, CLM-grade | none | Legal |
| **Confluence** | GROWTH | REST API | none | Ops |

## 9. Billing and Payments

| Vendor | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **Stripe** | CORE | REST API + webhooks | none | Finance |
| **Paddle** | GROWTH | REST API, merchant-of-record | none | Finance |
| **Chargebee** | GROWTH | REST API, subscription-deep | none | Finance |
| **QuickBooks Online** | FUTURE | OAuth REST | none | Finance |

## 10. Issue Tracking and Engineering

| Vendor | Tier | Access | Skill status | Department |
|---|---|---|---|---|
| **Linear** | CORE | GraphQL + MCP | raw (skill pack seed) | Engineering / Product |
| **GitHub** | CORE | REST + GraphQL + MCP | refined (skill pack exists) | Engineering |
| **Jira** | GROWTH | REST API | none | Engineering |
| **GitLab** | GROWTH | REST API | none | Engineering |

## 11. MCP Marketplaces (meta layer)

These are where Daena **discovers new connectors** without code
changes. The Research + Skill Governance departments poll these to
stay current with the ecosystem.

| Source | Tier | Access | Why it matters |
|---|---|---|---|
| **Anthropic MCP registry** | CORE | HTTP / doc feed | First-party, highest trust |
| **Smithery.ai** | CORE | REST API + catalog | Broadest selection |
| **PulseMCP** | CORE | REST API + catalog | Rankings + usage signals |
| **Apify MCP marketplace** | GROWTH | REST API | Scraping-specialized |
| **Claude Connectors catalog** | GROWTH | Anthropic registry | Premium partners |

**Skill gap**: the skill for *selecting* which MCP to adopt. Factors:
auth model (OAuth vs API key), rate limits, data-retention policy,
governance-tier classification. A Research agent should classify every
candidate MCP and hand a ranked shortlist to Skill Governance.

## 12. Expert Content Sources (Skill Mining)

Not connectors in the traditional sense. These are where domain
expertise lives and where the Skill Governance department mines
proven playbooks. See `CONTENT-OPS-PLAYBOOK.md`.

| Source | Tier | Access | Skill extraction target |
|---|---|---|---|
| **Alex Hormozi YouTube + podcasts** | CORE | YouTube API + transcript tools | Offers, cold outreach, close |
| **Sabri Suby (King Kong)** | CORE | YouTube + blog | Cold email, paid direct-response |
| **Chet Holmes archive** | GROWTH | PDF + transcripts | Enterprise sales fundamentals |
| **Jason Lemkin / SaaStr** | GROWTH | YouTube + blog | SaaS GTM benchmarks |
| **Patrick Campbell / ProfitWell** | GROWTH | YouTube + research | Pricing psychology |
| **Robert Cialdini** | CORE | Books + talks | Persuasion frameworks |
| **Steve Blank / Bob Dorf** | GROWTH | Books + Startup Tools | Customer development |
| **Paul Graham essays** | GROWTH | paulgraham.com RSS | YC-aligned startup thinking |
| **Lenny Rachitsky newsletter** | GROWTH | Substack | PM and growth benchmarks |
| **Growth.design case studies** | GROWTH | website | UX / conversion skill input |
| **Sean Ellis / Hiten Shah** | FUTURE | varied | Growth process frameworks |

**Skill mining skill**: the meta-skill that converts video/audio/
longform text into refined skill packs. Whisper transcription +
structural segmentation + DCP Council debate for signal extraction +
human-in-loop validation for T3 promotion.

---

## Coverage Scorecard (current state)

| Category | Have connector | Have skill pack | Production-grade skill |
|---|---|---|---|
| CRM | 0/7 | 0/7 | 0/7 |
| Sales Intelligence | 2/7 (stubs) | 0/7 | 0/7 |
| Email + Messaging | 3/11 | 0/11 | 0/11 |
| Scraping | 0/15 | 0/15 | 0/15 |
| Content SEO | 0/5 | 0/5 | 0/5 |
| Voice | 0/5 | 0/5 | 0/5 |
| Calendar | 1/5 | 0/5 | 0/5 |
| Docs / Contracts | 1/6 | 0/6 | 0/6 |
| Billing | 0/4 | 0/4 | 0/4 |
| Issue tracking | 2/4 | 1/4 | 0/4 |
| MCP marketplaces | 0/5 | 0/5 | 0/5 |
| Expert content sources | 0/11 | 0/11 | 0/11 |
| **Total** | **9/85** | **1/85** | **0/85** |

The skill gap is not a bug. It is the **single largest lever** Daena
has. Every connector we add without a skill pack is a connector that
produces generic output. Every skill pack we author that has no
corresponding connector is wasted preparation. The two layers must
advance together; Phase N (Skill Mining) is where they do.

## What "production-grade skill" means

A skill pack is production-grade when all of the following are true:

1. Authored by a DCP Quintessence Council (3 expert perspectives debated).
2. Validated against at least 10 real engagements.
3. Refined through the 3-pass Skill Refinery (extraction, improvement, critic).
4. Stored in NBMF T3 (institutional tier).
5. Staleness-monitored: re-validated every 90 days by `news_monitor.py`.
6. Versioned: each skill has a semantic version and a change log.
7. Instrumented: telemetry on acceptance rate, reply rate, conversion.

Today: zero skills meet all seven. By end of Phase N: 20+ in the
CORE categories.

## Phase M deliverable (Connector Fleet)

Not "add all 85 connectors." Add **one per category in CORE tier**,
with a minimum-viable skill pack, end-to-end tested with a real
tenant. Exit criteria:

- 1 CRM connector live with CRUD + bidirectional sync skill
- 1 sales-intelligence provider live with prospect-chaining skill
- 1 outbound email provider live with deliverability skill
- 1 scraping provider live with pain-mining skill
- 1 calendar connector deeper than current Google integration
- 1 contract / signature connector live with redline-to-sign skill
- 1 billing connector live with quote-to-invoice skill
- 1 MCP marketplace polled continuously

See `ROADMAP-V2.md` Phase M for sequencing.
