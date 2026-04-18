# Daena Roadmap V2 — Sovereign Security Vertical

Supersedes the horizontal roadmap in `docs/LAUNCH-CHECKLIST.md` and the Phase G / Phase H items in earlier session logs. Keep the prior phase-A through phase-F work (all [x] complete). Everything below is additive.

---

## Phase Gate Model

Every phase has (a) a demo deliverable a prospect can see, (b) a codebase deliverable a reviewer can pytest, (c) a revenue-capture mechanism. A phase is not "done" until all three ship.

---

## Phase G — Shield Activation and Demo Kit (Q2 2026, weeks 1 to 6)

**Goal**: prove Daena can replace a $50K pen-test engagement in a reproducible 48-hour run against a consented target.

### Demo deliverable
Reference engagement bundle: PDF report + SHA-256 evidence chain + video replay of the OODA-R loop. Runs against an intentionally vulnerable reference target hosted on the showcase DGX. Prospects see full thinking trace, every tool call, every governance decision.

### Codebase deliverable
- `backend/app/services/departments/security_operations_agent.py` NEW - specialized agent subclassing `DepartmentAgent`. Wraps the existing 7-layer security subsystem with a scheduled engagement driver.
- `backend/app/services/security/engagement_runner.py` NEW - orchestrates scope, OODA-R invocation, evidence capture, report generation. Reuses `cognition/ooda_engine.py` already present.
- `backend/tests/test_engagement_runner.py` NEW - contract tests for scope honoring, evidence chain, report generation.
- Front-end: new `EngagementConsolePage.tsx` with live scan viewer, evidence vault browser, report exporter.

### Revenue mechanism
Paid pilot: fixed-price $25K per engagement on a small target. Goal this phase: 1 paid engagement.

### Exit criteria
- One signed paid pilot
- Reference demo reproducible in under 2 hours
- SOC 2 Type 1 kickoff scheduled

---

## Phase H — Agent Ops Activation (Q2 2026, weeks 4 to 10; overlaps Phase G)

**Goal**: Daena's own agents find, qualify, contact, and book meetings with prospects. No human in the outbound loop.

### Demo deliverable
Dashboard view that shows the pipeline every Daena agent is working on this morning. For each prospect: source, qualification score, last touch, next action, governance tier, approval status. The same dashboard an external buyer will later use for their own agents.

### Codebase deliverable
- `backend/app/services/departments/sales_agent.py` NEW - calls OSINT layer (`security/osint/apollo_adapter.py`, `security/osint/hunter_adapter.py`, already present per `Daena-security/ARCHITECTURE.md` Layer 3) to build a prospect graph from an ICP description.
- `backend/app/services/departments/marketing_agent.py` NEW - content generation + outreach sequence authoring (uses existing LLM router + DCP Quintessence for high-stakes emails).
- `backend/app/services/departments/support_agent.py` NEW - customer support triage, ticket classification, escalation.
- `backend/app/services/crm/` NEW - minimal CRM on top of existing `Contact`, `Account`, `Deal` models (add models to `models/crm.py`).
- Outreach sequencer: each send routes through governance. GOVERNED mode for first 90 days, then BALANCED.
- `frontend/src/pages/PipelinePage.tsx` extended - the existing Pipeline page gets the agent-ops dashboard.

### Revenue mechanism
The agents themselves generate pipeline. Measure: number of qualified meetings booked per week by Daena's own sales agent.

### Exit criteria
- At least 5 qualified demo meetings per week sourced entirely by Daena's sales agent
- Every outreach message has an audit chain entry
- First cold-outbound-to-close measured end-to-end

---

## Phase I — Voice Operator (Q3 2026, weeks 1 to 6)

**Goal**: Daena makes and takes phone calls. Every call is transcribed, scored, governance-audited.

See `VOICE-STACK-PLAN.md` for architecture. Summary here:

### Demo deliverable
- Live outbound demo: operator types "call Jane at Acme, follow up on the pilot MSA." Daena dials, introduces herself, has the conversation, books the followup, logs everything.
- Live inbound demo: prospect dials the Daena number, connects to a voice agent, gets qualified, booked, or routed to a human.

### Codebase deliverable
- `backend/app/services/voice/outbound.py` NEW - VAPI/Retell/Twilio adapter layer. Pluggable provider.
- `backend/app/services/voice/stt_pipeline.py` NEW - faster-whisper (local) with ElevenLabs Conversational fallback.
- `backend/app/services/voice/tts_pipeline.py` NEW - Piper TTS (local) with XTTS and ElevenLabs as fallbacks.
- `backend/app/services/voice/conversation_session.py` NEW - streaming STT to LLM to TTS loop. Respects governance tier on high-stakes utterances (pricing, commitments, data handling).
- Extend `voice_service.py` with provider field (`browser` | `whisper_piper` | `vapi` | `retell` | `elevenlabs_conv`).
- Frontend: `VoiceConsolePage.tsx` NEW - monitor live calls, barge-in, review transcripts, approve high-tier voice actions.

### Revenue mechanism
Voice-enabled sales and support tier priced per active minute. Voice becomes a premium SKU for enterprise.

### Exit criteria
- Outbound call succeeds end-to-end on a test number
- Transcript stored with audit chain
- Governance tier 3+ spoken actions pause the call for human approval

---

## Phase J — Sovereign Deployment Kit (Q3 2026, weeks 5 to 10)

**Goal**: A government agency can install Daena air-gapped on their hardware and run an engagement without any outbound network call.

### Demo deliverable
USB-deliverable Daena Sovereign Edition: offline installer, local Ollama model bundle, local vLLM image, air-gap-safe documentation set, reference hardware spec sheet.

### Codebase deliverable
- `deploy/sovereign/` NEW - Docker Compose offline bundle generator. Pulls models, embeds, tests, ships tarball.
- `deploy/sovereign/INSTALL_AIRGAP.md` NEW
- Kill-switch verifier: confirms no outbound connection attempt on launch
- Reference hardware profile for on-prem install (workstation tier, rack tier, DGX tier)

### Revenue mechanism
Sovereign Edition licensed per-site per-year. Pricing range $80K to $400K depending on hardware tier and seat count.

### Exit criteria
- Offline bundle boots on an unplugged test box
- One agency evaluation in progress under Sovereign Edition

---

## Phase K — SOC-as-a-Service (Q4 2026)

**Goal**: Continuous security operations, monthly retainer, governed by Daena's own pipeline.

### Demo deliverable
Customer portal showing daily findings, remediation suggestions, trend graphs, evidence chain. The same audit chain used in Phase G engagements, surfaced as a standing dashboard.

### Codebase deliverable
- `backend/app/services/security/continuous_soc.py` NEW - scheduled scan orchestrator
- `backend/app/services/security/finding_triage.py` NEW - classifier with governance hooks
- Customer portal in frontend: `SocPortalPage.tsx` with finding triage, remediation workflow, monthly report export
- Alert routing to customer Slack/Teams/email/voice, each with approval tier

### Revenue mechanism
Monthly retainer. Small-mid: $5K/mo. Mid-enterprise: $20K/mo. Gov pilot: $50K/mo. Goal by end of Q4: 3 retainers.

### Exit criteria
- 3 active monthly retainers
- SOC 2 Type 1 issued
- FedRAMP moderate readiness assessment scheduled

---

## Phase M — Connector Fleet (Q2-Q3 2026, overlaps G/H)

**Goal**: close the biggest gap in the product — Daena can call external APIs but does not produce accurate output because there are no skill packs for most of them. Phase M lands one production connector per CORE category in `CONNECTOR-CATALOG.md`, each paired with a seed skill pack.

### Demo deliverable
Daena responds to "research Acme Corp" by calling the right 4 to 6 connectors (CRM, sales-intel, scraping, breach intel, calendar, signature) and returns a single unified brief in under 60 seconds.

### Codebase deliverable
- One production connector per category: HubSpot (CRM), Apollo + Hunter (sales-intel, reuse Layer 3 stubs), Gmail + SendGrid (email), Firecrawl + Apify (scraping), Google Calendar (deepened), Notion (deepened), DocuSign (signature), Stripe (billing), Linear (deepened).
- Each connector gets 3 to 5 seed skills authored through the Refinery.
- MCP registry poller (Anthropic, Smithery, PulseMCP) polled daily; new candidate connectors flow into Research department triage.

### Revenue mechanism
Enables the agent-ops revenue from Phase H. Bad output blocks conversion; good output compounds it.

### Exit criteria
- 9 CORE-tier connectors live + at least one T2 skill pack each
- MCP registry polling running on Heartbeat schedule
- Weekly connector-health report auto-generated

See `CONNECTOR-CATALOG.md`.

---

## Phase N — Skill Mining (Q3 2026)

**Goal**: the 5-stage continuous loop that keeps skill corpus ahead. Discovery → Extract → Refine → Promote → Monitor. Runs forever.

### Demo deliverable
A dashboard showing today's discovery items (Reddit posts, YouTube uploads, MCP registry adds), yesterday's refinement queue, this week's promotions and demotions. Masoud can see exactly how Daena learned today.

### Codebase deliverable
- `skill_refinery/source_registry.py` + `source_poller.py` NEW with 10 source types wired.
- `extraction_service.py` extended for audio/video via Whisper (from Phase I).
- `skill_promotion_service.py` with telemetry + demotion rules.
- Research department dashboard page.
- 10 production-grade (T3) seed skill packs authored (all seven from `CONTENT-OPS-PLAYBOOK.md` + 3 connector skills).

### Revenue mechanism
Not direct. Multiplies every other revenue line by improving output quality. Without skills, Phase O's autonomous execution produces mediocre results and churns.

### Exit criteria
- 20+ T2 skills live, 10+ T3 skills live
- Staleness monitor auto-triggering re-refinement on Heartbeat
- Daily Research department digest landing in founder inbox

See `SKILL-MINING-PIPELINE.md` and `CONTENT-OPS-PLAYBOOK.md`.

---

## Phase O — Autonomous Execution (Q3-Q4 2026)

**Goal**: the accept-and-go loop. User describes a goal, Daena returns a plan with cost + time + gate estimates, user hits Accept, the plan runs end-to-end.

### Demo deliverable
Masoud types "find 20 mid-market fintech SOC 2 gaps, qualify top 10, draft governed cold emails, pause for my approval before sending." Plan renders. He clicks Accept. 7 minutes later 10 emails sit in the approval queue, full audit chain visible.

### Codebase deliverable
- `backend/app/services/autopilot/` NEW package: `autonomous_plan.py`, `autopilot_planner.py`, `autopilot_executor.py`.
- SSE events: `step_started`, `step_progress`, `step_approval_pending`, `step_complete`, `plan_complete`.
- Frontend: `AutopilotPlanPage.tsx` (review + accept) + `AutopilotRunPage.tsx` (live execution monitor).
- Pause / Resume / Cancel controls with correct semantics on in-flight steps.
- Auto-pause on budget-cap overrun or failed dependencies.

### Revenue mechanism
The **experiential step-change** that sells the platform. Demo converts.

### Exit criteria
- Founder-click reduction: top 10 plays drop from ~30 clicks to ~2 clicks
- 1 external customer running at least one autonomous plan per week

See `AUTONOMOUS-EXECUTION.md`.

---

## Phase P — Content Ops Engine (Q4 2026)

**Goal**: Daena publishes content that compounds brand gravity without founder authoring each piece. Grounded in `CONTENT-OPS-PLAYBOOK.md` skill packs.

### Demo deliverable
A monthly report showing: 11 pieces published from 1 founder-authored essay, platform-by-platform engagement, top-performing atomic claim, content-to-pipeline attribution.

### Codebase deliverable
- `backend/app/services/marketing/content_multiplier.py` NEW — invokes the `one-to-eleven` skill, produces scheduled posts.
- Platform adapters: Twitter / LinkedIn / YouTube shorts / Substack.
- Engagement telemetry loop feeding Skill Governance (reply rate, click rate, conversion rate per atomic claim).
- Governance: tier 2 for standard publish, tier 3 for anything claiming revenue or customer metrics.

### Revenue mechanism
Drives top-of-funnel. Compounding brand asset.

### Exit criteria
- 5 originals multiplied to 50+ publishable pieces
- Attribution tracking live
- At least 10% of Phase O autonomous plan prospects sourced from content engagement

---

## Phase L — Federal and Regulated Ramp (Q1 2027 onward)

**Goal**: Convert readiness into the first federal procurement vehicle.

Activities:
- FedRAMP moderate authorization pursued via a sponsor agency or FedRAMP tailored path
- StateRAMP or IL2/IL4 depending on mission fit
- Contracting: CIO-SP4, SEWP VI, GSA IT Schedule 70 evaluation
- Prime and sub-prime partnerships with existing federal integrators
- Reference customer case study for public release

---

## What Falls Off the Old Roadmap

From the earlier horizontal roadmap, the following items are de-prioritized or removed:

- Generic consumer "governed ChatGPT" positioning
- Per-seat $29 to $99 indie-dev tier remains but no longer drives growth; it is a top-of-funnel feeder only
- Marketing to r/LocalLLaMA and HN stays but is secondary to agency and channel outreach
- Open-sourcing Laevateinn: defer until Phase K. Publishing the intelligence layer before the paid security practice is established gives away differentiation for attention that is not converting

## What Stays Locked

- Dark slate + gold + teal brand system
- Governance is always on, never optional
- Sunflower-honeycomb internal codename for PhiLattice
- NBMF internal codename
- Daena never deploys to production without Masoud explicit go-ahead (CLAUDE.md rule 14)

## Dependencies Between Phases

```
G (security demo) ── enables ──> K (continuous SOC)
                 ── feeds ────> L (federal ramp)

H (agent ops) ── drives ─────> revenue during G/I/J
             ── validates ───> Phase K customer portal UX

I (voice) ── amplifies ──────> H outreach (call + email not just email)
         ── upgrades ───────> K (SOC alert routing voice channel)

J (sovereign) ── unblocks ───> L (federal, agencies buy only what runs air-gapped)

M (connectors) ── feeds ──────> H (agents need APIs that return useful data)
              ── feeds ──────> N (connector-specific skills live here)

N (skill mining) ── multiplies ──> H, K, P output quality
              ── required-for ──> O (plans bind to specific skills)

O (autonomous execution) ── sells ──> everything. The "accept-and-go"
                                       demo is the step-change that
                                       converts pipeline to revenue.

P (content ops) ── feeds ─────> Phase H pipeline via inbound
              ── depends-on ──> N skills (Hormozi-grade output quality)
```

Parallel tracks are fine. Phase I can start before Phase H ships if the voice engineer is hired early. M and N are the **force-multipliers**: everything past them is better because they shipped.
