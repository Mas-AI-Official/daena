---
description: Verify Founder Policy Center functionality
---

# Founder Policy Center Verification

1. **Start Daena**: Run `main.py` or the startup script.
2. **Access Founder Panel**: Navigate to `/ui/founder-panel` (or the configured URL).
3. **Policies**:
   - Create a new policy: "No Treasury Spend" (Rule Type: payment, Enforcement: block).
   - Verify it appears in the list.
4. **Secrets**:
   - Add a secret: `TEST_SECRET` -> `supersecretvalue`.
   - Verify it appears in the vault (masked).
5. **Approvals**:
   - Trigger a high-risk action (or one blocked by policy).
   - If blocked, verify immediate rejection.
   - If requiring approval, verify it appears in "Approval Inbox".
   - Click "Approve" and verify the action proceeds (log check).

## Technical Checks
- Verify `founder_policies`, `secrets`, `pending_approvals` tables are populated in SQLite.
- Check `backend.services.governance_loop` logs for "Flagged by Founder Policy" messages.
