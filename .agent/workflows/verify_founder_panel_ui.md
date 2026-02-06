---
description: Verify Founder Panel UI Enhancements and Functionality
---

# Founder Panel Verification

1. **Start Daena**: Run `main.py` or the startup script.
2. **Access Founder Panel**: Navigate to `/ui/founder-panel`.
3. **Policies**:
   - Click "Add Policy".
   - **Verify**: A modal appears (not a browser prompt).
   - Enter details and submit.
   - **Verify**: Policy appears in the list.
4. **Secrets**:
   - Access "Secure Vault" tab.
   - Click "Add Secret".
   - **Verify**: A modal appears.
   - Enter `TEST_KEY` and value.
   - **Verify**: Secret appears in the vault.
5. **Departments**:
   - Access "Departments" tab.
   - Fill in "Register Dept" form (Name: "Test Ops", Color: Orange).
   - Click "Provision Sector".
   - **Verify**: "Test Ops" appears in the departments list on the right.
6. **Councils**:
   - Access "Councils" tab.
   - (Manual verification of Council creation if button available, currently visual).

## Verification of CMO Graph and Integrations

1. **Rename Verification**:
   - Check that Sidebar shows "CMO" instead of "CMP Graph".

2. **Integration Linking**:
   - In Founder Panel > Integrations (or Dashboard grid if visible).
   - Click "Slack" (or similar messaging service).
   - **Verify**: A browser prompt appears asking for "Slack Bot Token".
   - Enter a dummy token `xoxb-test-123`.
   - **Verify**: The card status updates to "connected" (green checkmark).
   - Click "Slack" again.
   - **Verify**: It asks if you want to disconnect or informs you to go to the Vault.

3. **Backend Key Check**:
   - Verify `GET /api/v1/founder/integrations/status` returns `connected` for the service you just added.

## Technical Checks
- Check browser console for network errors during form submissions.
- Verify `backend/routes/founder_api.py` handles requests correctly.
