# Go-Live Checklist

**Date**: 2025-12-13  
**Purpose**: Final verification before declaring "Daena is live"

---

## Pre-Launch Checks

### ✅ Code Quality
- [x] No truncation markers (`verify_no_truncation.py` - PASS)
- [x] No duplicate modules (`verify_no_duplicates.py` - PASS)
- [x] Core files intact (`verify_file_integrity.py` - PASS)
- [x] All core files have protection headers

### ✅ Implementation
- [x] Shared Brain + Governance pipeline implemented
- [x] Bootstrap script created
- [x] Launcher enhanced
- [x] End-to-end tests created
- [x] Brain UI components added
- [x] Documentation created

---

## Launch Verification

### Step 1: Run Launcher
```batch
cd D:\Ideas\Daena_old_upgrade_20251213
START_DAENA.bat
```

**Expected**:
- ✅ Bootstrap completes
- ✅ Guardrails pass
- ✅ Backend starts
- ✅ Health check passes
- ✅ Browser opens

### Step 2: Verify URLs

**UI Pages** (should return 200):
- [ ] http://127.0.0.1:8000/ui/dashboard
- [ ] http://127.0.0.1:8000/ui/agents
- [ ] http://127.0.0.1:8000/ui/departments
- [ ] http://127.0.0.1:8000/ui/health

**API Endpoints** (should return 200):
- [ ] http://127.0.0.1:8000/api/v1/health/
- [ ] http://127.0.0.1:8000/api/v1/agents
- [ ] http://127.0.0.1:8000/api/v1/departments
- [ ] http://127.0.0.1:8000/api/v1/brain/status

### Step 3: Functional Tests

**Daena Chat**:
- [ ] Open dashboard
- [ ] Type message in chat
- [ ] Verify Daena responds (not stub/generic)
- [ ] Response indicates brain processing

**Agent Interaction**:
- [ ] Go to Agents page
- [ ] Click "Chat" on an agent
- [ ] Send message
- [ ] Verify agent responds through canonical brain

**Task Assignment**:
- [ ] Go to Agents page
- [ ] Click "Assign Task" on an agent
- [ ] Fill in task details
- [ ] Submit
- [ ] Verify task is routed through CMP

**Brain Governance**:
- [ ] Click "Brain" button in dashboard
- [ ] Verify brain status loads
- [ ] Verify governance queue loads
- [ ] (Optional) Propose experience via API
- [ ] (Optional) Commit proposal via UI

### Step 4: Run End-to-End Tests
```batch
cd D:\Ideas\Daena_old_upgrade_20251213
call venv_daena_main_py310\Scripts\activate.bat
set DISABLE_AUTH=1
python -m pytest tests\test_daena_go_live.py -v
```

**Expected**: All tests pass

---

## Go-Live Criteria

### ✅ All Must Pass

- [ ] Backend starts with one command (`START_DAENA.bat`)
- [ ] No frontend console errors
- [ ] Daena answers as Daena (not generic)
- [ ] Agents respond through CMP
- [ ] One full workflow test passes
- [ ] No file is being deleted/truncated by Cursor
- [ ] Brain status endpoint returns installed + active model
- [ ] Can chat with Daena and get real response
- [ ] Can assign task to agent and get real response

---

## Final Confirmation

**Statement**: "I can chat with Daena and assign a task to an agent from UI and get a real response."

**Status**: ⏳ **PENDING VERIFICATION**

**Action**: Run launcher and verify all criteria above.

---

**Checklist Created**: 2025-12-13
