# Implementation Plan: Frontend Rebuild & Governance Center

**Goal**: Transform the current monolithic React frontend into a modular, routed application with a professional "Founder OS" structure, while integrating the new Governance and Model Control features.

## User Review Required
> [!IMPORTANT]
> This plan involves a major refactor of the frontend structure, moving from a single-page state switch to `react-router-dom`. This will change how navigation works.

## Proposed Changes

### 1. Frontend Architecture Overhaul (The App Shell)
We will restructure the frontend to match the "Folder Structure" defined in the Audit Doc.

#### [NEW] `frontend/src/Layout.tsx`
- Create a persistent **Sidebar** navigation (left) and **Header** (top).
- Sidebar items: Dashboard, Messages, Departments, Skills, Governance, Brain, Vault.

#### [NEW] `frontend/src/Router.tsx`
- Implement `react-router-dom` v6.
- Define routes:
  - `/` -> Dashboard (Hex Mesh)
  - `/chat` -> Message/Action Center
  - `/departments` -> Department Grid
  - `/departments/:id` -> Detailed Dept View
  - `/brain` -> **BrainStatus (Existing+Updated)**
  - `/governance` -> **ApprovalsInbox (New)**
  - `/vault` -> Secrets Manager

### 2. Governance Center (Priority)
Implement the UI for the "VP Interface" to manage permissions and critical actions.

#### [NEW] `frontend/src/components/governance/ApprovalsInbox.tsx`
- Fetch pending approvals from `GET /api/v1/governance/approvals`.
- UI to "Approve" (Green) or "Block" (Red) actions.
- Show risk levels (High/Critical) and reasoning.

#### [NEW] `frontend/src/components/governance/AuditLog.tsx`
- Read-only view of `GET /api/v1/audit/logs`.
- Filterable table of all system actions.

### 3. Department & Agent Visualization
Visualize the "Sunflower-Honeycomb" structure.

#### [NEW] `frontend/src/components/departments/DepartmentGrid.tsx`
- Render the 8 departments as a grid of interactive cards.
- Show active agent count and status.

### 4. Integration Updates
- Update `App.tsx` to mount the `Router` instead of the current manual switch.
- Ensure `BrainStatus` (our recently polished component) is correctly mounted at `/brain`.

## Verification Plan

### Automated Tests
- `npm run test` (if available) or create basic component rendering tests.

### Manual Verification
1. **Navigation**: Verify clicking Sidebar links changes URL and View without full reload.
2. **Brain Route**: Verify `/brain` loads the new Model Registry and Brain Status we just built.
3. **Governance**: Trigger a "High Risk" mock action (e.g. via a dev tool) and verify it appears in `ApprovalsInbox`.
