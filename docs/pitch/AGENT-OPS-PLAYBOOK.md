# Daena Agent Ops Playbook

How each of the 10 departments actually generates business using the same OSINT + cognitive + governance stack already built for security. This document is the bridge between "Daena is governed security software" and "Daena also runs its own sales organization."

Every action below routes through the 10-stage governance pipeline. Every action is auditable. The same approval queue that gates a destructive security action gates a high-stakes outbound email.

---

## The Core Insight

The OSINT infrastructure built for Layer 3 of the security subsystem (Apollo, Hunter, people intel, supply chain, breach intel) is functionally identical to the infrastructure a world-class outbound sales team uses. Same data providers. Same enrichment chains. Same decisioning inputs. The only thing we add on top is intent: "find and exploit" vs "find and engage."

Because both intents go through the same governance pipeline, the same audit trail a government buyer inspects before signing a $300K contract is the same audit trail a CRO inspects before signing the same-size outbound sequence approval.

That is unprecedented. It is also the reason Daena can run 10 departments of agent labor with a single founder.

---

## The Full Lifecycle at a Glance

```
ICP definition
   v
PROSPECTING (Sales + Security Ops + Research)
   v
QUALIFICATION (Sales + Research + Legal)
   v
OUTREACH (Marketing + Sales + Voice)
   v
MEETING (Sales + Engineering + Product)
   v
PROPOSAL (Sales + Legal + Finance)
   v
CLOSE (Sales + Legal + Finance + Operations)
   v
DELIVER (Security Ops + Engineering)
   v
SUPPORT (Support + Engineering + Skill Governance)
   v
EXPAND (Sales + Customer Success)
```

Every arrow is an internal department-to-department message (existing `department_messages` channel from Session C). Every message is governed. Every governance decision lands in the audit log.

---

## Department-by-Department Workflow

### 1. Security Operations

**Mission in security mode**: continuous scan, triage, report.
**Mission in business mode**: surface target accounts that match ICP by combining breach exposure data with tech stack signals. Prospects with freshly breached credentials or known outdated security tooling are the highest-converting ICP.

**Stack used**: `security/osint/breach_intelligence.py`, `security/osint/supply_chain_analyzer.py`, Cognitive Knowledge Graph for cross-engagement learning.

**Output to next department**: a ranked list of 50 target accounts with breach severity + tech gap signal + supply chain risk.

### 2. Research

**Security mission**: competitive security posture assessment of a target.
**Business mission**: produce a 2-page prep brief before every outbound touch and every meeting. Include: recent funding news, open roles (signals budget), org chart top 3 levels, competitor deployments (mentions in job posts, CVE disclosures, customer case studies).

**Stack**: OSINT layer + internet search + NBMF T2 memory for past engagement notes.

**Output**: briefing doc into the Sales queue before the sequence fires.

### 3. Sales

**Mission**: own the pipeline from first touch to close. Own the prospect record in the CRM.

**Specific actions the `sales_agent.py` implements**:
- `prospect(icp_description)` - builds the prospect list from Security Ops + Research outputs.
- `qualify(prospect_id)` - runs a Quintessence Council check: three models debate whether the prospect matches ICP. Confidence score gates whether outreach proceeds.
- `sequence(prospect_id, template)` - generates a multi-touch outreach sequence. Marketing writes the copy, Sales approves voice + timing.
- `book_meeting(prospect_id, slot)` - integrates with calendar, sends confirmation.
- `handoff_to_meeting(prospect_id, attendees)` - builds the briefing packet, loops in Engineering if technical questions are expected.

**Governance tier for each**: prospecting and qualification are tier 1 (logged). Sequence authoring is tier 2 (notified). Sending is tier 3 until day 90 (approval required) then drops to tier 2.

### 4. Marketing

**Security mission**: brand and tech profile of prospects for social engineering vector identification.
**Business mission**: content generation, SEO, landing page assembly, outreach copy.

**Specific actions the `marketing_agent.py` implements**:
- `author_sequence(prospect_profile, template)` - generates email copy grounded in the Research briefing. Uses Quintessence when the prospect is a high-value target.
- `landing_page(topic)` - assembles a landing page from approved content blocks. The governance pipeline catches claims that cannot be substantiated before publish.
- `campaign(objective, channels)` - runs a multi-channel push (blog, LinkedIn, outbound) with attribution tracking.

**Deliverable proof**: every published page and email has a `governance_trace_id` in a hidden meta tag. Compliance can audit the generation chain end-to-end.

### 5. Engineering

**Security mission**: code review for vulns; deploy shield overlays.
**Business mission**: custom integration builds, webhook adapters, customer-specific deploy hardening during onboarding.

**Specific actions**: pull requests against the `deploy/customer_<slug>/` template, test coverage gate, rollout orchestration. Each change is reviewed by the Skill Governance department before landing.

### 6. Legal and Compliance

**Security mission**: compliance gap exploitation analysis (what regulation the target is failing; leverage during outreach).
**Business mission**: contract redlines, DPA/MSA generation, NDA workflow, procurement response.

**Specific actions**:
- `generate_nda(counterparty)` - templated NDA with counterparty-specific clauses.
- `redline(contract_file)` - Quintessence debate across a Legal expert lens, Security expert lens, and Finance expert lens. Produces a red/yellow/green annotated document.
- `procurement_response(rfi | rfp file)` - drafts a response packet. Flags questions that require founder intervention.

### 7. Finance

**Security mission**: cost of defensive gaps quantification.
**Business mission**: quote generation, invoicing, revenue recognition, collections.

**Specific actions**:
- `quote(opportunity_id)` - pulls ICP match, engagement scope, deployment tier, and spits out a SKU-aligned quote.
- `invoice(deal_id)` - on close, generates invoice with correct T&Cs.
- `dunning(invoice_id)` - polite escalation for late payment. Routes to Legal at day 60.

### 8. Operations

**Security mission**: deployment and posture management.
**Business mission**: scheduling, project management, SOP execution, CRM updates, vendor onboarding.

**Specific actions**:
- `schedule_engagement(deal_id)` - blocks calendar for scan window, Pre-engagement call, post-engagement briefing.
- `onboard_customer(deal_id)` - runs the 17-step onboarding checklist. Each step auditable.

### 9. Product

**Security mission**: surface-area mapping; understand the attack surface evolving.
**Business mission**: roadmap grooming from customer issues, feature request triage.

**Specific actions**:
- `triage_request(issue_id)` - classifies as bug/feature/compliance and routes.
- `roadmap_weekly()` - summarizes inbound product signal with Skill Governance weighting.

### 10. Skill Governance

**Security mission**: tradecraft learning across engagements.
**Business mission**: extract best practices from wins, avoid anti-patterns, refine every department's workflow.

**Specific actions**:
- `extract_from_close(deal_id)` - pulls winning patterns and stores into NBMF T3 (institutional).
- `extract_from_loss(deal_id)` - pulls losing patterns and tiers them to T2 (review required).
- `refine_sequence(template_id)` - suggests a variant to the Marketing sequence authoring agent based on response-rate telemetry.

---

## Governance Guardrails Specific to Agent Ops

- **Outreach velocity cap**: no more than 500 outbound messages per rolling 24 hours during the first 90 days. Hard law enforced at GovernanceEngine layer.
- **Voice daily cap**: no more than 100 outbound dial attempts per day during first 90 days. Pre-recorded intro mandatory so callees know they are speaking with an agent.
- **Claims budget**: no marketing agent can make an unsupported revenue or customer-count claim. Every claim needs a source citation from NBMF or a human-approved block.
- **Reply-detection sensitivity**: any inbound "please stop" or equivalent kills the sequence globally for that contact, tenant-wide, within 60 seconds of receipt. Handled by a hard-coded stop-rule in Marketing agent.
- **Legal review gate**: any contract change that moves the contract value by more than 15% or modifies liability language requires founder approval.
- **Voice high-tier gate**: any spoken commitment on pricing, delivery dates, or data handling is tier 3. The call pauses and prompts either the operator or routes to human.

## Metrics That Matter

| Metric | Target by end of Phase H | Source |
|---|---|---|
| Prospects sourced per week | 500 | Security Ops + Sales agents |
| Qualified meetings booked per week | 5 | Sales agent calendar integration |
| Email reply rate | 4%+ (double industry for cold) | Marketing agent telemetry |
| Outbound to close cycle time | 60 days average | CRM pipeline tracking |
| Voice call connect rate | 18%+ | Voice outbound pipeline |
| Approval queue backlog | less than 24 hours | Governance audit |
| Agent-generated revenue as % of total | 80%+ by end of 2026 | Revenue attribution |

## How This Ships Without Breaking Existing Code

- The generic `department_agent.py` stays as the base class.
- Each specialized agent subclasses it: `sales_agent.py(DepartmentAgent)`, `marketing_agent.py(DepartmentAgent)`, and so on. The existing `swarm/executor.py` already dispatches to department agents, no change needed.
- Agent actions route through existing `ExecutionService.execute_tool` which now (post-2026-04-17 fix) persists PendingApproval rows. Masoud will see every outbound action awaiting approval in the frontend.
- CRM tables (`Contact`, `Account`, `Deal`, `Activity`) are net-new but live in a new `models/crm.py` alongside the existing model modules. Multi-tenant scoped via TenantMixin.

## Why This Will Actually Work

Because we are not asking agents to be creative. We are asking agents to execute a decided playbook with tighter operational discipline than a human can sustain. The governance pipeline enforces that discipline. The audit chain proves compliance. The OSINT layer is already among the most capable on the market because it was built for security work. Every hour the system runs, the Skill Governance department compounds what works into NBMF T3.

This is the thing a human sales org cannot do at this cost. It is the thing a generic AI tool cannot do without governance. It is the thing a generic agent framework cannot do without an audit chain.

It is what Daena is uniquely positioned to do.
