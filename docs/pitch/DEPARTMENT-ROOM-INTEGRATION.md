# Department Room Integration

The department room (`/departments/{id}` in the frontend, backed by
`DepartmentChatPage.tsx`) is the canonical UX where users consume
department capabilities. Specialized agent actions (prospect,
qualify, draft, run scan, take call) surface inside the room that
owns them, not on standalone pages.

This document is the contract between the backend capabilities
already shipped and the department rooms that should expose them.

---

## Principle

One department, one room. Every capability that belongs to a
department lives in its room. No parallel pages. No ghost features.

When I shipped `/crm` and `/voice` as top-level pages, I violated
this principle. Those are deleted. This doc shows where each
backend capability actually belongs.

---

## Capability <-> Department Map

### Sales department

**Room**: `/departments/sales` (or the UUID variant).

**Backend capabilities the room consumes**:

| Endpoint | Purpose | Triggered by |
|---|---|---|
| `POST /api/v1/sales/prospect` | Build Account + Contact rows from an ICP description | Chat command `/prospect <icp>` or a "Prospect" button |
| `POST /api/v1/sales/qualify` | Score + advance a contact NEW -> QUALIFIED | Chat command `/qualify <contact>` or inline action on a contact card |
| `GET /api/v1/crm/accounts` | List accounts for the tenant | Pipeline pane inside the room |
| `GET /api/v1/crm/contacts` | List contacts, filterable by stage / account | Same pane, with stage columns |
| `GET /api/v1/crm/deals` | List deals, filterable by stage | Deals pane |

**UI pattern**: the Sales department room has a Kanban pane under
the chat feed showing contacts grouped by stage. The chat and the
Kanban share the same session -- an agent action in chat updates
the Kanban in real time.

### Marketing department

**Room**: `/departments/marketing`.

**Capabilities**:

| Endpoint | Purpose | Trigger |
|---|---|---|
| `POST /api/v1/marketing/author-outreach` | Draft an email grounded in a Contact record | Button on a contact card in Sales room OR chat command `/draft <contact>` |
| `GET /api/v1/crm/outreach-drafts` | List drafts pending approval | Drafts pane inside Marketing room |
| `POST /api/v1/skills/refinery/ingest-batch` | Receive ContentOps scraper output | Admin / automated, not user-triggered |

The draft pane is Marketing's responsibility even though Sales
created the contact. This matches the playbook: Sales owns the
pipeline record, Marketing owns the words.

### Customer Service department

**Room**: `/departments/customer-service`.

**Capabilities**:

| Endpoint | Purpose |
|---|---|
| `WebSocket /api/v1/voice/ws/{session_id}` | Live inbound or outbound call channel |
| Voice provider selection (browser / faster-whisper / Piper / VAPI) | Per-agent config in the department settings |

**UI pattern**: the Customer Service room has a "Live Calls" pane
showing active calls routed to this department. Each call row
expands to a live transcript with approval controls. This is where
the Voice Console page I built should have been -- scoped to the
department that owns inbound phone calls.

See `CALL-CENTER-PATTERN.md` for the full telephony architecture
(IVR, skill routing, per-department voice identities).

### Security Operations department

**Room**: `/departments/security-operations`.

**Capabilities**:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/engagements` | Launch a scan |
| `GET /api/v1/engagements` | List scans |
| `GET /api/v1/engagements/{id}` | Poll one scan |
| `GET /api/v1/engagements/{id}/report` | Fetch completed report |
| `GET /api/v1/engagements/shield-status` | T5 tier unlock check |

**Current state**: `/engagements` still exists as a standalone page
(I did not delete it this session because the scan UI has meaningful
stateful complexity -- launch forms, live progress, report viewer).
The right long-term home is `/departments/security-operations` with
the same components embedded as panes in the room. Flagged for
Phase I.2 alongside the voice work.

### Legal & Compliance department

**Room**: `/departments/legal-and-compliance`.

**Capabilities** (mostly future, called out for completeness):

- Contract redline (uses existing LLM router + Quintessence).
- NDA generation.
- Procurement response drafting.

### Finance department

**Room**: `/departments/finance`.

**Capabilities**:

- Quote generation from an opportunity.
- Invoice generation on close.
- Dunning workflow.

### Research department

**Room**: `/departments/research`.

**Capabilities**:

- Prep briefing generation (consumes OSINT + NBMF T2).
- Source discovery polling (future Phase N Stage 1).
- `GET /api/v1/skills/refinery/catalog` consumed here for skill
  visibility.

### Operations, Product, Skill Governance, Engineering

All follow the same pattern. Their capabilities are authored as
method calls on the respective specialized department agent
(`sales_agent.py` pattern) and consumed through the department room.

---

## What the Frontend Needs (Phase I.2 work, scoped)

1. **`DepartmentChatPage.tsx` extension**: add a right-side pane
   slot that each department populates with its own component
   (Kanban for Sales, Live Calls for Customer Service, Engagement
   List for Security Operations, etc.).

2. **`DepartmentPanes/` directory**: one component per department
   that consumes its backend endpoints. Lazy-loaded so a user in
   Sales does not pay the bundle cost of Security Operations' live
   scan viewer.

3. **Slash-command registry extension**: the existing chat slash
   commands (see `frontend/src/components/chat/SlashCommands.tsx`)
   gain per-department entries. In Sales' room, `/prospect` works.
   In Security Operations' room, `/scan <target>` works.

4. **Router policy**: going to `/crm` / `/voice` (legacy URLs)
   redirects to `/departments/sales` and `/departments/customer-
   service` respectively so any bookmarks survive.

---

## Why This Is the Right Architecture

- **Departments are the organizing metaphor** (`company we have as
  departments`). Breaking that metaphor with standalone pages
  dilutes the model.
- **Context lives where the work happens**. A sales rep pulling up
  a contact wants CRM data + chat + approval queue in one place.
  Jumping to `/crm` then back to chat fragments focus.
- **Governance stays coherent**. One approval surface per room
  (the InlineApprovalBanner shipped earlier) catches every tier-3
  action regardless of capability type.
- **Per-department identity**: each room carries the department's
  voice, color palette, and agent personalities. Generic pages
  dissolve identity.

## What NOT to Build

- No `/crm` page (deleted this session).
- No `/voice` page (deleted this session).
- No `/calls` page. Calls live in the department room they routed to.
- No `/contacts` page. Contacts live under their department's room.
- No `/drafts` page. Drafts live in Marketing's room.
- No "unified inbox" for customer messages. Each department has its
  own inbound queue in its own room. The Founder's roll-up is the
  existing `/company` Company Dashboard.

If it sounds like a separate page, first ask which department owns
it. The answer is always the right home.
