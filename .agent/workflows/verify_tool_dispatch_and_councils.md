---
description: Verify DaenaBot Tool Dispatch and Council UI Functionality
---

This workflow validates that the "Dyspatch failed" error is resolved and that the Councils UI is fully wired to the backend.

1. **Verify Tool Dispatch (Control Panel)**
   - Open `http://localhost:8000/ui/control-pannel#tools` (or Navigate to Control Panel -> DaenaBot Tools).
   - Locate the **Test Tools** card.
   - Click **Screenshot** (or "Browser Screenshot").
   - **Expected**: 
     - Toast notification: "Dispatching..."
     - Then: "Queued for approval" (if medium/high risk) OR "Executed: Success" (if low risk).
     - No "Dispatch failed" error.

2. **Verify Councils Page**
   - Open `http://localhost:8000/ui/councils`.
   - **Expected**: A grid of councils (Finance, Tech, Strategy, etc.) loaded from the database.

3. **Verify Council Creation**
   - Click the **"Add New Council"** card.
   - Enter Name: "Test Council", Description: "Testing creation", Icon: "fa-flask".
   - Click **Create Council**.
   - **Expected**:
     - Toast: "Council created successfully".
     - The modal closes.
     - The page refreshes (or list updates) to show "Test Council".

4. **Verify Council Debate**
   - Click **Start Debate** on any council card.
   - **Expected**:
     - Redirects to `/ui/council-debate?council=...`
     - The debate interface loads.
     - You can type a topic and start a debate.

5. **Verify Backend Logs**
   - Check the backend console for `GET /api/v1/council/list` and `POST /api/v1/tools/submit` logs.
