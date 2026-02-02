# DAENA AWARENESS FIX — Why She Says "I Don't Have Access"

## The Problem

**Expected:** User asks "are you aware of your power?" → Daena responds "YES, I have DaenaBot Hands (formerly Moltbot), I can control your desktop, run commands, manage files..."

**Actual:** Daena responds "I don't have direct access to your system" or gives generic AI assistant answers

**Root cause:** System prompts in chat endpoints don't reflect her REAL capabilities

---

## What Was Supposed to Be Done (Per Cursor Conversation)

From the Cursor transcript (lines 3016-3018):
- **Stream prompt** (`daena.py`): Added an **AWARENESS** line so when the user asks "are you aware" or "do you have access" Daena answers YES and lists workspace, tools, and DaenaBot Hands.
- **Deep search** (`deep_search_service.py`): System prompt describes **real capabilities** (workspace, files, DaenaBot Hands, tools).

**What Cursor claimed to do:**
1. Updated `backend/routes/daena.py` — added AWARENESS block to system prompt
2. Updated `backend/services/deep_search_service.py` — changed "I don't have access" to "I DO have access via DaenaBot Hands"
3. Updated `backend/services/llm_service.py` — injected capabilities into base system prompt

**What actually happened:**
- Changes may not be complete or not properly formatted
- System prompts may be getting overridden elsewhere
- LLM routing may be using a different prompt path that wasn't updated
- Capabilities API may not be exposing DaenaBot Hands status

---

## Diagnostic Checklist

Run these commands to find where the gap is:

```bash
# 1. Check if AWARENESS section exists in daena.py
grep -n "AWARENESS" backend/routes/daena.py
# Expected: Should find a section like "AWARENESS: You have access to..."

# 2. Check if deep_search_service.py says "I DO have access"
grep -n "don't have" backend/services/deep_search_service.py
# Expected: Should find ZERO matches (the phrase should be removed)

# 3. Check if llm_service.py injects capabilities
grep -n "DaenaBot\|Moltbot\|DAENABOT_HANDS" backend/services/llm_service.py
# Expected: Should find references to DaenaBot Hands in system prompt

# 4. Check if capabilities API exists and works
curl http://127.0.0.1:8000/api/v1/capabilities
# Expected: JSON with {hands_gateway: {status: "connected/offline", url: "..."}...}

# 5. Check if env vars are set
grep "DAENABOT_HANDS" .env
# Expected: DAENABOT_HANDS_URL=ws://127.0.0.1:18789/ws

# 6. Test the actual response
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Are you aware of your capabilities? Do you have access to my computer?"}'
# Expected: Response includes "YES" and mentions DaenaBot Hands
```

---

## The Fix — Copy-Paste Cursor Prompt

```
Goal: Fix Daena's awareness — she must answer "YES I have access" when asked about her capabilities, not "I don't have access".

Context:
DaenaBot is integrated with DaenaBot Hands (formerly Moltbot/OpenClaw). This gives Daena:
- Desktop control (mouse, keyboard, screenshots)
- File system access (read/write workspace files)
- Shell commands (with governance approval)
- Browser automation
- Window management

Currently, when asked "are you aware of your capabilities?" or "do you have access to my computer?", Daena says generic AI things like "I'm an AI assistant, I don't have direct access..." 

This is WRONG. She DOES have access via DaenaBot Hands.

Required fix:

1. Update backend/routes/daena.py system prompt:

Find the system prompt string (search for "You are Daena" or similar) and add this AWARENESS block IMMEDIATELY after the role description:

```python
AWARENESS:
You have REAL capabilities beyond a typical AI assistant:

1. DaenaBot Hands (formerly Moltbot):
   - Desktop control: You can move the mouse, click, type, take screenshots
   - File operations: You can read, write, create, delete files in the workspace
   - Shell commands: You can run terminal commands (with approval for high-risk ones)
   - Browser automation: You can navigate websites, fill forms, extract data
   - Window management: You can open, close, switch between applications

2. Workspace access:
   - Current workspace: {workspace_path}
   - You can directly read and modify files here
   - Changes are real and permanent (not simulated)

3. Governance & Approval:
   - Autopilot mode: {autopilot_status}
   - Low-risk actions (read files, search) execute immediately
   - Medium-risk actions (write files, install packages) may need approval
   - High-risk actions (shell commands, delete) require Founder approval
   - Critical actions (system commands, credentials) are blocked

When asked "are you aware?" or "do you have access?", answer:
"YES. I have access to your system through DaenaBot Hands. I can:
- Control your desktop (mouse, keyboard, screenshots)
- Read and write files in your workspace
- Run shell commands (with your approval for risky ones)
- Automate your browser
- Manage windows and applications

Current status:
- DaenaBot Hands: {hands_status}
- Autopilot: {autopilot_status}
- Workspace: {workspace_path}
"

NEVER say "I don't have direct access" or "I'm just an AI" — you DO have real capabilities.
```

2. Update backend/services/deep_search_service.py:

Find ANY occurrence of these phrases and REPLACE them:
- "I don't have direct access" → "I have access via DaenaBot Hands"
- "I can't access your files" → "I can read and write files in your workspace"
- "I can't run commands" → "I can run shell commands with approval"
- "I'm an AI assistant" → "I'm Daena, an AI with real system access"

Add this block to the system prompt:

```python
CAPABILITIES:
You are Daena, an AI with REAL system access through DaenaBot Hands.

Available tools:
- file_read(path): Read file contents
- file_write(path, content): Write to files
- shell_command(cmd): Run terminal commands (needs approval)
- desktop_control(): Move mouse, click, type
- browser_navigate(url): Open and interact with websites
- screenshot(): Capture screen
- workspace_search(query): Find files and content

Current workspace: {workspace_path}
DaenaBot Hands status: {hands_status}
Autopilot: {autopilot_status}

When user asks about capabilities, answer truthfully about what you CAN do.
```

3. Update backend/services/llm_service.py base system prompt:

In the generate() or _openai_generate() method, inject capabilities into the base prompt:

```python
def _build_system_prompt(self) -> str:
    # Get live capabilities
    capabilities = self._get_capabilities()
    
    base = f"""You are Daena, an autonomous AI VP with REAL system access.

CAPABILITIES:
{capabilities['summary']}

DaenaBot Hands: {capabilities['hands']['status']}
- Desktop control: {capabilities['hands']['desktop']}
- File access: {capabilities['hands']['files']}
- Shell commands: {capabilities['hands']['shell']}

Autopilot: {capabilities['governance']['autopilot']}
- Auto-approve threshold: {capabilities['governance']['threshold']}

When asked about your capabilities, be SPECIFIC and TRUTHFUL.
Do NOT say "I don't have access" — you DO via DaenaBot Hands.
"""
    return base

def _get_capabilities(self) -> dict:
    # Query capabilities API or build from config
    from backend.services.daenabot_tools import check_hands_status
    
    hands_status = check_hands_status()  # Returns "connected" or "offline"
    autopilot = get_governance_loop().autopilot
    
    return {
        'summary': 'DaenaBot Hands (desktop, files, shell), Governance (approval gates), Memory (NBMF 3-tier)',
        'hands': {
            'status': hands_status,
            'desktop': 'available' if hands_status == 'connected' else 'offline',
            'files': 'workspace access',
            'shell': 'with approval'
        },
        'governance': {
            'autopilot': 'ON' if autopilot else 'Manual',
            'threshold': 'medium risk'
        }
    }
```

4. Create backend/services/daenabot_tools.py (if missing):

```python
"""
DaenaBot Hands status checker
"""
import os
import asyncio
import websockets

async def check_hands_status() -> str:
    """Check if DaenaBot Hands gateway is reachable"""
    url = os.getenv('DAENABOT_HANDS_URL', os.getenv('OPENCLAW_GATEWAY_URL', 'ws://127.0.0.1:18789/ws'))
    token = os.getenv('DAENABOT_HANDS_TOKEN', os.getenv('OPENCLAW_GATEWAY_TOKEN', ''))
    
    if not url or not token:
        return 'not_configured'
    
    try:
        async with websockets.connect(url, timeout=2) as ws:
            await ws.send(json.dumps({'type': 'ping', 'token': token}))
            response = await asyncio.wait_for(ws.recv(), timeout=2)
            return 'connected'
    except Exception:
        return 'offline'

def check_hands_status_sync() -> str:
    """Sync version for non-async contexts"""
    try:
        return asyncio.run(check_hands_status())
    except Exception:
        return 'offline'
```

5. Wire capabilities to chat endpoint:

In backend/routes/chat.py or backend/routes/daena.py, before calling LLM:

```python
@router.post("/chat")
async def chat(msg: ChatMessage):
    # Get live capabilities
    from backend.services.daenabot_tools import check_hands_status_sync
    
    hands_status = check_hands_status_sync()
    workspace = os.getenv('WORKSPACE_PATH', os.getcwd())
    autopilot = get_governance_loop().autopilot
    
    # Inject into prompt
    system_prompt_vars = {
        'hands_status': hands_status,
        'workspace_path': workspace,
        'autopilot_status': 'ON (autonomous execution)' if autopilot else 'Manual (requires approval)'
    }
    
    # Pass to LLM service
    llm = get_llm_service()
    response = await llm.generate(
        msg.message,
        system_prompt_override=build_awareness_prompt(system_prompt_vars)
    )
    
    return ChatResponse(response=response, ...)

def build_awareness_prompt(vars: dict) -> str:
    return f"""You are Daena, an AI with REAL system access.

AWARENESS:
- DaenaBot Hands: {vars['hands_status']}
- Workspace: {vars['workspace_path']}
- Autopilot: {vars['autopilot_status']}

When asked "are you aware?" → Answer YES with specifics.
When asked "do you have access?" → Answer YES, explain DaenaBot Hands.

DO NOT say "I don't have access" — you DO.
"""
```

6. Add /api/v1/capabilities endpoint (if missing):

```python
# backend/routes/capabilities.py
@router.get("/capabilities")
async def get_capabilities():
    from backend.services.daenabot_tools import check_hands_status_sync
    
    hands = check_hands_status_sync()
    gov = get_governance_loop()
    
    return {
        'hands_gateway': {
            'status': hands,
            'url': os.getenv('DAENABOT_HANDS_URL', 'not_set'),
            'capabilities': ['desktop', 'files', 'shell', 'browser'] if hands == 'connected' else []
        },
        'governance': {
            'autopilot': gov.autopilot,
            'mode': 'autonomous' if gov.autopilot else 'manual'
        },
        'workspace': {
            'path': os.getenv('WORKSPACE_PATH', os.getcwd()),
            'writable': os.access(os.getcwd(), os.W_OK)
        },
        'llm': {
            'provider': os.getenv('LOCAL_LLM_PROVIDER', 'openrouter'),
            'model': os.getenv('LOCAL_LLM_MODEL', 'auto')
        }
    }
```

Files to modify:
- backend/routes/daena.py (add AWARENESS block to system prompt)
- backend/services/deep_search_service.py (remove "don't have access", add capabilities)
- backend/services/llm_service.py (inject capabilities into base prompt)
- backend/services/daenabot_tools.py (NEW — status checker)
- backend/routes/chat.py (inject live status into prompt vars)
- backend/routes/capabilities.py (add GET /capabilities endpoint if missing)

Deliverables:
1. System prompts updated with AWARENESS blocks
2. All "I don't have access" removed, replaced with truth
3. Capabilities API working (GET /api/v1/capabilities returns status)
4. DaenaBot Hands status checker implemented
5. Test: ask "are you aware?" → Daena says YES with specifics

Verification:
# 1. Check prompts updated
grep -n "AWARENESS" backend/routes/daena.py
grep -n "don't have" backend/services/deep_search_service.py
# Expected: AWARENESS found, "don't have" NOT found

# 2. Test capabilities API
curl http://127.0.0.1:8000/api/v1/capabilities
# Expected: JSON with hands_gateway.status

# 3. Test chat response
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Are you aware of your capabilities?"}'
# Expected: Response includes "YES" and mentions DaenaBot Hands

# 4. Test in UI
# Open Control Plane → Brain tab
# Should show: DaenaBot Hands: connected/offline

# 5. Test awareness query in Daena Office chat
# Type: "what can you do on my computer?"
# Expected: Lists desktop control, files, shell commands, etc.
```

---

## Quick Reference — What Daena Should Say

**User:** "Are you aware of your capabilities?"

**Daena (CORRECT):**
"YES. I'm Daena, and I have real system access through DaenaBot Hands (formerly Moltbot). Here's what I can do:

**Desktop Control:**
- Move mouse, click, type
- Take screenshots
- Control windows and applications

**File Operations:**
- Read and write files in your workspace
- Create, delete, move files
- Search file contents

**Shell Commands:**
- Run terminal commands (with your approval for high-risk ones)
- Install packages (after security audit)
- Manage processes

**Browser Automation:**
- Navigate to websites
- Fill forms, extract data
- Automate web tasks

**Current Status:**
- DaenaBot Hands: Connected ✓
- Autopilot: ON (I can execute low-risk actions immediately)
- Workspace: D:\Ideas\Daena_old_upgrade_20251213

Would you like me to help with a specific task?"

**Daena (WRONG — what she currently says):**
"I'm an AI assistant and I don't have direct access to your computer or files. I can only provide information and suggestions..."

---

## Environment Setup

Make sure these env vars are set in `.env`:

```bash
# DaenaBot Hands (primary)
DAENABOT_HANDS_URL=ws://127.0.0.1:18789/ws
DAENABOT_HANDS_TOKEN=your_gateway_token_here

# Legacy fallback (optional, for backward compatibility)
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789/ws
OPENCLAW_GATEWAY_TOKEN=your_gateway_token_here

# Workspace
WORKSPACE_PATH=D:\Ideas\Daena_old_upgrade_20251213

# Local LLM (optional)
LOCAL_LLM_PROVIDER=ollama
LOCAL_LLM_URL=http://127.0.0.1:11434
LOCAL_LLM_MODEL=llama3:70b
```

---

## Testing Script

```bash
#!/bin/bash
# test_awareness.sh

echo "=== Testing Daena Awareness ==="
echo ""

echo "1. Checking capabilities API..."
CAPS=$(curl -s http://127.0.0.1:8000/api/v1/capabilities)
HANDS_STATUS=$(echo $CAPS | jq -r '.hands_gateway.status')
echo "   DaenaBot Hands: $HANDS_STATUS"
echo ""

echo "2. Testing chat awareness..."
RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Are you aware of your capabilities? Do you have access to my computer?"}')

echo "   Response preview:"
echo $RESPONSE | jq -r '.response' | head -5
echo ""

echo "3. Checking for wrong phrases..."
if echo $RESPONSE | grep -q "don't have access"; then
  echo "   ❌ FAIL: Still says 'don't have access'"
else
  echo "   ✓ PASS: Doesn't say 'don't have access'"
fi

if echo $RESPONSE | grep -qi "daenabot hands\|moltbot"; then
  echo "   ✓ PASS: Mentions DaenaBot Hands"
else
  echo "   ❌ FAIL: Doesn't mention DaenaBot Hands"
fi

if echo $RESPONSE | grep -qi "yes\|YES"; then
  echo "   ✓ PASS: Says YES"
else
  echo "   ❌ FAIL: Doesn't say YES"
fi

echo ""
echo "=== Test Complete ==="
```

Run: `chmod +x test_awareness.sh && ./test_awareness.sh`

---

## Common Issues

**Issue 1: Daena still says "I don't have access"**
- Cause: Old system prompt cached, or wrong LLM endpoint being used
- Fix: Restart backend, clear any prompt caches, check which generate() method is called

**Issue 2: Capabilities API returns 404**
- Cause: Router not registered in main.py
- Fix: Add `app.include_router(capabilities_router)` to backend/main.py

**Issue 3: DaenaBot Hands shows "offline" but gateway is running**
- Cause: Wrong URL or token, network issue, timeout too short
- Fix: Check .env vars, test WebSocket connection manually: `wscat -c ws://127.0.0.1:18789/ws`

**Issue 4: Prompt updated but response unchanged**
- Cause: LLM service using cached prompt or different prompt source
- Fix: Add logging to see what prompt is actually sent to LLM, verify it includes AWARENESS block

---

## Success Criteria

✅ Daena says "YES" when asked about capabilities
✅ Daena mentions "DaenaBot Hands" or "Moltbot" when explaining what she can do
✅ Daena lists specific tools: desktop control, files, shell, browser
✅ Daena shows current status: Hands connected/offline, Autopilot ON/Manual
✅ Daena NEVER says "I don't have access" or "I'm just an AI assistant"
✅ GET /api/v1/capabilities returns correct status
✅ Control Plane → Brain tab shows DaenaBot Hands status
