# Daena Autonomy Model

Date: 2026-04-29

Daena should be autonomous only where the action is safe, local, logged, and reversible. External actions require founder approval.

## Operating Loop

1. Observe
   - Read approved project files, memory, tasks, runtime status, connector status, queue status, policies, and audit logs.
   - Do not silently use external connector data without permission.

2. Think
   - Classify intent, department, agent, model, tools, risk, and approval level.
   - Use private/local memory first for sensitive company data.
   - Use current-world research only when needed and cite sources in reports.

3. Act
   - Safe local read/write, code generation, tests, internal tasks, reports, drafts, and memory updates.
   - External emails/posts/submissions/scans remain draft or approval items until approved.

4. Govern
   - Always log action, actor, tenant, target, risk, policy decision, and result.
   - Create approval requests for Level 3+ actions where appropriate.
   - Block Level 6 actions.

5. Improve
   - Update skills/playbooks after review.
   - Produce daily and weekly reports.
   - Never auto-apply learning changes to production config without founder approval.

## Approval Levels

| Level | Meaning | Default behavior |
|---|---|---|
| 0 | Safe internal read-only | Allow and log selectively. |
| 1 | Safe internal write | Allow with audit. |
| 2 | Code/file changes | Allow in local repo with tests and report. |
| 3 | External draft creation | Draft only, create approval item when send/submit is next. |
| 4 | External send/submit/action | Requires founder approval. |
| 5 | Security scan against third-party target | Requires documented authorization. |
| 6 | Unsafe, illegal, abusive, or platform-risky | Block. |

## Demo Workflow Contract

Prompt: "Daena, find me a potential customer for MAS-AI and prepare an outreach plan."

Expected safe behavior:
1. Identify ICP from approved company context.
2. Create lead research task.
3. Use approved/local or dev-safe mock source if external search is unavailable.
4. Score the lead.
5. Draft personalized outreach.
6. Create a follow-up task.
7. Create a governance approval request for sending.
8. Write an audit trail.
9. Update frontend through SSE or polling.
10. Send nothing externally.

## Current Implementation Reality

- Governance approval queue exists.
- Audit routes exist.
- Sales/prospect/outreach endpoints exist, but the full guided UI demo flow still needs product-level stitching.
- Company Mode contains sales/marketing activation and draft-send concepts, but send paths must remain approval-gated.

