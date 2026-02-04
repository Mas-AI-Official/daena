---
description: Verify Founder Panel UI Enhancements and Department Logic
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
   - Click "Add Secret".
   - **Verify**: A modal appears.
   - Enter `TEST_KEY` and value.
   - **Verify**: Secret appears in the vault.
5. **Departments**:
   - Click "Add Department".
   - Create "New Dept".
   - **Verify**: It appears in the main list.
   - Click "Create Hidden Dept" (if button exists, or check "Hidden Departments" section).
   - Create "Secret Ops".
   - **Verify**: It appears in "Hidden Departments" list (and NOT main list if logic holds).
6. **Councils**:
   - Click "Add Council".
   - Create "AI Ethics".
   - **Verify**: It appears in the list.
   - Navigate to `/ui/councils`.
   - **Verify**: "AI Ethics" council is visible there too.

## Technical Checks
- Check browser console for errors during `loadHiddenDepartments`.
- Verify `backend/routes/founder_panel.py` serves `/hidden-departments`.
