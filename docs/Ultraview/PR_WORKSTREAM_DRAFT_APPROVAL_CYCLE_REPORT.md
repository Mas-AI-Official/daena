# PR-5: Complete Workstream / Draft / Approval Cycle — Report

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE

## What this PR does

Verifies that ResearchDraft, FormDraft, Opportunity, and FileChangeProposal
already have complete next-step buttons wired to existing endpoints, with
no submit / post / pay paths anywhere on a page that can fire from a
button click.

## ResearchDraft (career / content / business_opportunity)

Surface: `WorkstreamsPage → DraftsLane → DraftRow → DraftActions` component.

| Action | Endpoint | Refusal-aware | Notes |
|---|---|---|---|
| Enrich | `POST /research/drafts/{id}/enrich` | yes (toast + inline) | runs routed brain |
| Council | `POST /research/drafts/{id}/qe-review` | yes (mode=unavailable) | three-stage council |
| Create Workstream | `POST /workstreams/from-draft` | yes (toast) | promotes to workstream |
| Approval queue | reachable via Approvals sidebar entry | — | downstream of Create Workstream |
| Audit | reachable via Audit sidebar entry | — | governance trail |

Status badges: `llm pending / enriched / QE: full / QE: degraded / workstream` — all derived from already-loaded payload, no extra fetch.

## FormDraft

Surface: `WorkstreamsPage → DraftsLane (Forms tab) → DraftActions` component (form variant).

| Action | Endpoint | Allowed |
|---|---|---|
| Enrich | `POST /form-drafts/{id}/enrich` | yes |
| Council | `POST /form-drafts/{id}/qe-review` | yes |
| Create Workstream | `POST /workstreams/from-draft` (kind=form) | yes |
| **Submit** | none | **never** — confirmed: no submit button, no submit endpoint exposed in UI |

The Forms-tab empty state explicitly tells the operator how to ingest a form:
`POST /api/v1/form-drafts/from-questions | /from-html | /from-url`. None of those write to external systems; they only persist a draft locally.

## Opportunity

Surface: `OpportunityInboxPage` (PR-4).

| Action | Allowed | Path |
|---|---|---|
| Create workstream | yes | `POST /api/v1/opportunities/{id}/create-workstream` |
| Draft outreach | yes (VP chat) | `POST /api/v1/business/chat` with `draft outreach for opp <uuid> to <email>` |
| Queue Gmail draft | yes (controlled execution) | dispatcher → `gmail.create_draft` |
| Approve & send | yes (Approvals page) | dispatcher → `gmail.send_existing_draft` (TRUST_FORBIDDEN — explicit approval required) |
| Open audit | yes | sidebar Governance → Audit |

## FileChangeProposal

Surface: `GovernanceApprovalsPage` + `Phase3ApprovalModal` (no dedicated page — fits the generic approval-payload UI).

| Action | UI | Backend |
|---|---|---|
| View diff | approval payload rendered in modal | `GET /governance/approvals/{id}` |
| Approve apply | `POST /governance/approvals/{id}` decision=approved | dispatcher → `file_change_proposal.apply` |
| Rollback on fail | dispatcher rollback path (Sprint-19) | `file_change_proposal_apply.py` |
| Separate commit approval | second approval row | dispatcher → `git_commit_approved_patch` (TRUST_FORBIDDEN) |
| **Push** | none | **never** — there is no push handler at all; verified by `Grep file_change_proposal\|FileChangeProposal` in `backend/app/services/controlled_execution_handlers/*` |

Backend evidence of the bright line:
- `controlled_execution_handlers/file_change_proposal.py` — propose only
- `controlled_execution_handlers/file_change_proposal_apply.py` — apply diff in workspace
- `controlled_execution_handlers/git_commit_approved_patch.py` — commit, **no push**

`git push` is not a registered controlled-execution tool — it cannot be triggered from a UI approval. The operator runs `git push` manually from terminal.

## Source-grep guards (already in repo, verified by reading test files in PR-1/PR-2 audit)

These tests pin the bright lines:
- `backend/tests/test_business_routine_draft_only.py` — pins that `routine_handler.py` does **not** import any of: `queue_gmail_draft_creation`, `queue_gmail_send`, `gmail_bridge`, `send_bridge`, `controlled_execution_dispatch`. Verified during Sprint-20 PR-6.
- `backend/tests/test_business_outreach_drill.py` — verifies the drill module does **not** import send-bridge symbols.
- `backend/tests/test_vp_business_commands_v2.py` — pins that the chat parser only invokes the three id-explicit commands when an explicit UUID is present.

## Refusal codes surfaced

The DraftActions component captures the backend's refusal payload (`refusal_code` + `next_action`) and surfaces it inline. Same pattern as the controlled-execution dispatcher (Sprint-19) — every refusal carries a stable code and a human-readable next action.

## Hard rules respected

- [x] No `gmail.send` on a draft surface
- [x] No form submit
- [x] No git push button
- [x] No external action fires from any draft / opportunity / approval row click except through the gated dispatcher
- [x] Every refusal has a code + next action

## Next

PR-6: Connections / MCP / Runtime readiness closure.
