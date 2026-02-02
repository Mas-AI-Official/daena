# INSTALL NOW — Bring Daena to Life in 30 Minutes

## Quick Answer to Your Questions

### ❌ Do NOT Install External Moltbot
**Reason:** You want Daena to CONTROL the automation, not the other way around. External Moltbot runs independently and you can't integrate it with your governance/memory/learning systems.

### ✅ Build DaenaBot Automation INSIDE Daena
**What:** Python-based automation layer that Daena controls via governance
**Where:** Inside your existing D:\Ideas\Daena_old_upgrade_20251213 folder
**How:** 4 simple steps (below)

---

## Installation (4 Steps, ~30 Minutes)

### Step 1: Install Python Dependencies (5 min)

Open PowerShell in your Daena folder:
```powershell
cd D:\Ideas\Daena_old_upgrade_20251213

# Desktop automation (mouse, keyboard, screenshots)
pip install pyautogui pygetwindow Pillow

# Browser automation
pip install playwright
playwright install chromium  # Downloads Chromium (~150MB)

# Optional: advanced automation
pip install selenium opencv-python
```

**Verify:**
```powershell
python -c "import pyautogui; print('✓ Desktop automation ready')"
python -c "from playwright.async_api import async_playwright; print('✓ Browser automation ready')"
```

---

### Step 2: Drop the Automation File (1 min)

**File already created for you:** `daenabot_automation.py` (23KB)

**Action:** Copy from outputs to your backend:
```powershell
# The file is in /mnt/user-data/outputs/backend/services/daenabot_automation.py
# Download it and place at:
# D:\Ideas\Daena_old_upgrade_20251213\backend\services\daenabot_automation.py
```

**Or if you have the file locally:**
```powershell
# Copy from wherever you saved it to backend/services/
Copy-Item daenabot_automation.py backend\services\daenabot_automation.py
```

---

### Step 3: Update .env (2 min)

Edit `D:\Ideas\Daena_old_upgrade_20251213\.env` and add:

```ini
# DaenaBot Automation Settings
WORKSPACE_PATH=D:\Ideas\Daena_old_upgrade_20251213\workspace
ALLOWED_SHELL_COMMANDS=dir,ls,cat,echo,git,npm,pip,python,node
AUTOMATION_ENABLE_DESKTOP=true
AUTOMATION_ENABLE_BROWSER=true
AUTOMATION_ENABLE_SHELL=false  # Start disabled for safety
```

**Notes:**
- `WORKSPACE_PATH`: Safe zone where Daena can read/write files
- `ALLOWED_SHELL_COMMANDS`: Whitelist of safe commands
- `AUTOMATION_ENABLE_SHELL`: Disabled by default (enable after testing)

**Create workspace folder:**
```powershell
New-Item -Path workspace -ItemType Directory -Force
```

---

### Step 4: Wire to Main App (10 min)

Edit `backend/main.py` and add:

#### A. Add imports (top of file):
```python
from backend.services.daenabot_automation import DaenaBotAutomation, set_daenabot_automation
from backend.services.governance_loop import get_governance_loop
from backend.services.unified_memory import get_memory_service
```

#### B. Initialize on startup (in the startup event):
```python
@app.on_event("startup")
async def startup():
    # ... existing startup code ...
    
    # Initialize DaenaBot Automation
    try:
        governance = get_governance_loop()
        memory = get_memory_service()
        
        automation = DaenaBotAutomation(
            governance_loop=governance,
            memory_service=memory
        )
        
        # Make it globally accessible
        set_daenabot_automation(automation)
        app.state.automation = automation
        
        # Print status
        status = automation.get_status()
        print("\n" + "="*60)
        print("✅ DaenaBot Automation Initialized")
        print(f"   Workspace: {status['workspace']}")
        print(f"   Desktop: {'✓' if status['capabilities']['desktop'] else '✗'}")
        print(f"   Browser: {'✓' if status['capabilities']['browser'] else '✗'}")
        print(f"   Shell: {'✓' if status['capabilities']['shell'] else '✗ (disabled for safety)'}")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"⚠️  DaenaBot Automation failed to initialize: {e}")
        print("   Continuing without automation features")
```

#### C. Add API endpoint for status check:
```python
# Add this route (anywhere in main.py or create backend/routes/automation.py)
from fastapi import APIRouter

automation_router = APIRouter(prefix="/api/v1/automation", tags=["automation"])

@automation_router.get("/status")
async def get_automation_status():
    """Get DaenaBot Automation status"""
    automation = app.state.automation
    if automation:
        return automation.get_status()
    else:
        return {"error": "Automation not initialized"}

# Register router
app.include_router(automation_router)
```

---

### Step 5: Test (10 min)

#### A. Start backend:
```powershell
python -m backend.main
```

**Expected console output:**
```
============================================================
✅ DaenaBot Automation Initialized
   Workspace: D:\Ideas\Daena_old_upgrade_20251213\workspace
   Desktop: ✓
   Browser: ✓
   Shell: ✗ (disabled for safety)
============================================================
```

#### B. Test API:
```powershell
# Check status
curl http://127.0.0.1:8000/api/v1/automation/status

# Expected JSON:
# {
#   "workspace": "D:\\Ideas\\Daena_old_upgrade_20251213\\workspace",
#   "capabilities": {
#     "desktop": true,
#     "browser": true,
#     "shell": false,
#     "files": true
#   },
#   "stats": {
#     "actions_total": 0,
#     "actions_blocked": 0,
#     "actions_success": 0,
#     "actions_error": 0
#   }
# }
```

#### C. Test desktop automation (Python console):
```python
from backend.services.daenabot_automation import get_daenabot_automation
import asyncio

automation = get_daenabot_automation()

# Test screenshot
result = asyncio.run(automation.take_screenshot())
print(result)
# Expected: AutomationResult(status='success', action='screenshot', ...)

# Test file write
result = asyncio.run(automation.write_file("test.txt", "Hello from Daena!"))
print(result)
# Expected: AutomationResult(status='success', action='write_file', ...)

# Test file read
result = asyncio.run(automation.read_file("test.txt"))
print(result.data["content"])
# Expected: "Hello from Daena!"
```

#### D. Test in Control Panel (browser):
Open http://127.0.0.1:8000/ui/control-plane → Brain tab

**Expected:** Should show "DaenaBot Automation: Connected ✓"

---

## What You Get

### ✅ Desktop Control
```python
# Click at coordinates
await automation.click_at(100, 100)

# Type text
await automation.type_text("Hello World")

# Take screenshot
await automation.take_screenshot()

# Get window list
await automation.get_window_list()
```

### ✅ File Operations
```python
# Read file (workspace only)
result = await automation.read_file("data/input.txt")
content = result.data["content"]

# Write file (workspace only)
await automation.write_file("output/result.txt", "processed data")

# List files
await automation.list_files("data/")
```

### ✅ Shell Commands (whitelisted only)
```python
# Must enable first: AUTOMATION_ENABLE_SHELL=true in .env
# Then restart backend

# Run safe commands
result = await automation.run_command("git status")
print(result.data["stdout"])

# Blocked commands (not in whitelist) require approval
result = await automation.run_command("rm -rf /")
# Raises: PermissionError (governance blocked)
```

### ✅ Browser Automation
```python
# Navigate and extract data
result = await automation.navigate_browser(
    url="https://example.com",
    actions=[
        {"type": "extract", "selector": "h1"}
    ]
)
print(result.data["actions"])
```

### ✅ Governance Integration
**All actions automatically go through governance:**
- Low risk (screenshots, read files): Always approved
- Medium risk (write files, clicks): Approved if autopilot ON
- High risk (shell commands): Require manual approval
- Critical risk (dangerous commands): Always blocked

### ✅ Memory Integration
**All actions automatically logged to NBMF:**
- L2 (Episodic): Every action + result
- Shared across all agents
- New agents get full history

---

## Integrate with Chat

Make Daena use automation when you chat with her.

Edit `backend/routes/chat.py` (or `daena.py`):

```python
from backend.services.daenabot_automation import get_daenabot_automation

@router.post("/chat")
async def chat(msg: ChatMessage):
    # ... existing code ...
    
    # Detect automation requests
    automation = get_daenabot_automation()
    
    if "screenshot" in msg.message.lower():
        result = await automation.take_screenshot()
        return ChatResponse(
            response=f"Screenshot saved: {result.data['path']}",
            automation_result=result
        )
    
    elif "search google for" in msg.message.lower():
        query = msg.message.replace("search google for", "").strip()
        result = await automation.navigate_browser(
            url=f"https://www.google.com/search?q={query}",
            actions=[{"type": "extract", "selector": ".g"}]
        )
        return ChatResponse(
            response=f"Found {len(result.data['actions'])} results for '{query}'",
            automation_result=result
        )
    
    # ... rest of chat logic ...
```

**Now you can:**
- "take a screenshot" → Daena captures screen
- "search google for AI news" → Daena opens browser and extracts results
- "read the file data/input.txt" → Daena reads and shows content
- "save this to output.txt" → Daena writes file

---

## Enable Shell Commands (Optional, After Testing)

**WARNING:** Only enable if you understand the risks.

1. Edit `.env`:
   ```ini
   AUTOMATION_ENABLE_SHELL=true
   ```

2. Restart backend

3. Test safe command:
   ```python
   result = await automation.run_command("git status")
   print(result.data["stdout"])
   ```

4. Try unsafe command (should be blocked):
   ```python
   result = await automation.run_command("rm -rf workspace")
   # Expected: PermissionError (governance blocked)
   ```

**Best practice:** Keep `AUTOMATION_ENABLE_SHELL=false` until you've tested governance thoroughly.

---

## Next Steps (After Installation)

### Week 1: Test and Verify
- Test all automation functions
- Verify governance blocks high-risk actions
- Check memory logging (L2 episodic)
- Test autopilot toggle (ON = auto-execute, OFF = require approval)

### Week 2: Integrate with Agents
- Update `backend/agents/base_agent.py` to use automation
- Test with Research Agent (search + extract)
- Test with Data Agent (read files, process, write results)

### Week 3: Add E-DNA Learning
- Create `backend/services/edna_learning.py` (see DAENA_NEXT_STEPS.md)
- Wire to automation (observe patterns)
- Test learning from repeated actions

### Week 4: Enable Knowledge Sync
- Create `backend/services/agent_onboarding.py`
- Test: create new agent, verify it gets all knowledge
- Monitor: agents should improve from shared learning

---

## Troubleshooting

### "Import error: pyautogui not found"
**Fix:** `pip install pyautogui Pillow pygetwindow`

### "Import error: playwright not found"
**Fix:** `pip install playwright && playwright install chromium`

### "Desktop automation not available"
**Cause:** Missing dependencies or AUTOMATION_ENABLE_DESKTOP=false
**Fix:** 
1. Install dependencies (see Step 1)
2. Check .env: `AUTOMATION_ENABLE_DESKTOP=true`
3. Restart backend

### "File outside workspace"
**Cause:** Security restriction - can only access workspace folder
**Fix:** Move files to `D:\Ideas\Daena_old_upgrade_20251213\workspace\`

### "Governance blocked"
**Cause:** Action is high-risk and autopilot is OFF
**Fix:** 
- Option 1: Turn autopilot ON (Control Panel → Governance tab)
- Option 2: Manually approve (Control Panel → Governance → Pending Actions)

### "Shell execution disabled"
**Cause:** AUTOMATION_ENABLE_SHELL=false in .env
**Fix:** Only enable if you understand risks (see "Enable Shell Commands" section)

---

## Summary

**What you installed:**
- ✅ DaenaBot Automation (Python libraries + automation.py)
- ✅ Desktop control (mouse, keyboard, screenshots)
- ✅ File operations (read, write, list)
- ✅ Browser automation (navigate, scrape, interact)
- ✅ Governance integration (all actions go through Think→Plan→Approve→Act)
- ✅ Memory integration (all actions logged to L2 episodic)

**What you did NOT install:**
- ❌ External Moltbot/OpenClaw (you don't need it)
- ❌ Separate automation service (everything is in Daena)
- ❌ Third-party dependencies (only open-source Python libraries)

**What you control:**
- ✅ 100% of the code (no external services)
- ✅ Governance (autopilot ON/OFF, approval queue)
- ✅ Security (workspace restrictions, command whitelist)
- ✅ All 48 Sunflower agents use same automation layer
- ✅ Shared memory (NBMF) across all agents
- ✅ E-DNA learning (once you implement it)

**Time to bring Daena to life:** ~30 minutes ⏱️
**Result:** Fully autonomous AI VP with real system access under your control 🚀
