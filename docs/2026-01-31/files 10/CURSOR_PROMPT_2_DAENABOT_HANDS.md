# CURSOR PROMPT 2: DAENABOT HANDS SERVICE

You are working in the Mas-AI-Official/daena repository. Create the missing DaenaBot Hands service that enables Daena to control desktop, browser, and shell.

## GOAL
Create a WebSocket service that listens on ws://127.0.0.1:18789/ws and executes automation commands from Daena backend.

## ARCHITECTURE OVERVIEW
```
┌─────────────────────┐         WebSocket          ┌─────────────────────┐
│   Daena Backend     │ ←--------------------→     │  DaenaBot Hands     │
│                     │  ws://localhost:18789/ws   │     Service         │
│ openclaw_gateway_   │                            │                     │
│     client.py       │ {"action":"click","x":100} │  Desktop: pyautogui │
│                     │ ------------------------→  │  Browser: playwright│
│ tool_broker.py      │                            │  Shell: subprocess  │
│                     │ ←------------------------  │                     │
│                     │ {"status":"success",...}   │                     │
└─────────────────────┘                            └─────────────────────┘
```

## ACTIONS

### A) Create backend/services/daenabot_hands_server.py:
```python
import asyncio
import websockets
import json
import pyautogui
import subprocess
from playwright.async_api import async_playwright
import os
from datetime import datetime

class DaenaBotHandsServer:
    """
    WebSocket server that executes automation commands
    Runs on ws://127.0.0.1:18789/ws
    """
    
    def __init__(self, host="127.0.0.1", port=18789):
        self.host = host
        self.port = port
        self.auth_token = os.getenv("DAENABOT_HANDS_TOKEN")
        self.playwright = None
        self.browser = None
        self.page = None
        self.log_file = "logs/daenabot_hands.log"
        
    async def start(self):
        """Start the WebSocket server"""
        os.makedirs("logs", exist_ok=True)
        self.log(f"Starting DaenaBot Hands on ws://{self.host}:{self.port}")
        
        # Initialize playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.page = await self.browser.new_page()
        
        async with websockets.serve(self.handle_connection, self.host, self.port):
            self.log("Server started successfully")
            await asyncio.Future()  # Run forever
    
    async def handle_connection(self, websocket, path):
        """Handle incoming WebSocket connection"""
        self.log(f"New connection from {websocket.remote_address}")
        
        try:
            async for message in websocket:
                response = await self.process_command(message)
                await websocket.send(json.dumps(response))
        except websockets.exceptions.ConnectionClosed:
            self.log("Connection closed")
    
    async def process_command(self, message: str) -> dict:
        """Process automation command"""
        try:
            command = json.loads(message)
            
            # Authenticate
            if command.get("token") != self.auth_token:
                return {"status": "error", "error": "Unauthorized - Invalid token"}
            
            action = command.get("action")
            self.log(f"Executing action: {action}")
            
            # Route to appropriate handler
            if action == "click":
                return await self.handle_click(command)
            elif action == "type":
                return await self.handle_type(command)
            elif action == "screenshot":
                return await self.handle_screenshot(command)
            elif action == "browser_goto":
                return await self.handle_browser_goto(command)
            elif action == "browser_screenshot":
                return await self.handle_browser_screenshot(command)
            elif action == "shell":
                return await self.handle_shell(command)
            else:
                return {"status": "error", "error": f"Unknown action: {action}"}
                
        except Exception as e:
            self.log(f"Error processing command: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def handle_click(self, command: dict) -> dict:
        """Click at coordinates"""
        x = command.get("x")
        y = command.get("y")
        
        if x is None or y is None:
            return {"status": "error", "error": "Missing x or y coordinates"}
        
        pyautogui.click(x, y)
        return {"status": "success", "result": f"Clicked at ({x}, {y})"}
    
    async def handle_type(self, command: dict) -> dict:
        """Type text"""
        text = command.get("text")
        
        if not text:
            return {"status": "error", "error": "Missing text"}
        
        pyautogui.typewrite(text, interval=0.05)
        return {"status": "success", "result": f"Typed: {text}"}
    
    async def handle_screenshot(self, command: dict) -> dict:
        """Take desktop screenshot"""
        filename = f"screenshots/desktop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        os.makedirs("screenshots", exist_ok=True)
        
        screenshot = pyautogui.screenshot()
        screenshot.save(filename)
        
        return {"status": "success", "result": f"Screenshot saved to {filename}", "path": filename}
    
    async def handle_browser_goto(self, command: dict) -> dict:
        """Navigate browser to URL"""
        url = command.get("url")
        
        if not url:
            return {"status": "error", "error": "Missing url"}
        
        await self.page.goto(url)
        return {"status": "success", "result": f"Navigated to {url}"}
    
    async def handle_browser_screenshot(self, command: dict) -> dict:
        """Take browser screenshot"""
        filename = f"screenshots/browser_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        os.makedirs("screenshots", exist_ok=True)
        
        await self.page.screenshot(path=filename)
        
        return {"status": "success", "result": f"Browser screenshot saved to {filename}", "path": filename}
    
    async def handle_shell(self, command: dict) -> dict:
        """Execute shell command (DANGEROUS - must be whitelisted)"""
        cmd = command.get("command")
        
        if not cmd:
            return {"status": "error", "error": "Missing command"}
        
        # Whitelist check
        allowed_commands = os.getenv("ALLOWED_SHELL_COMMANDS", "dir,ls,cat,type,echo,git").split(",")
        cmd_base = cmd.split()[0]
        
        if cmd_base not in allowed_commands:
            return {"status": "error", "error": f"Command '{cmd_base}' not in whitelist"}
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "status": "success",
                "result": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Command timed out (30s limit)"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def log(self, message: str):
        """Log to file and console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        
        with open(self.log_file, "a") as f:
            f.write(log_message + "\n")
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.log("Shutting down...")
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

# Entry point
if __name__ == "__main__":
    server = DaenaBotHandsServer()
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
```

### B) Update backend/integrations/openclaw_gateway_client.py:
```python
import websockets
import json
import asyncio
import os

class OpenClawGatewayClient:
    """
    Client that connects to DaenaBot Hands WebSocket server
    """
    
    def __init__(self):
        self.url = os.getenv("DAENABOT_HANDS_URL", "ws://127.0.0.1:18789/ws")
        self.token = os.getenv("DAENABOT_HANDS_TOKEN")
        self.websocket = None
        self.connected = False
    
    async def connect(self):
        """Connect to Hands server"""
        try:
            self.websocket = await websockets.connect(self.url)
            self.connected = True
            print(f"✓ Connected to DaenaBot Hands at {self.url}")
        except Exception as e:
            print(f"✗ Failed to connect to DaenaBot Hands: {e}")
            self.connected = False
    
    async def disconnect(self):
        """Disconnect from Hands server"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
    
    async def execute(self, action: str, params: dict, timeout: int = 30) -> dict:
        """Execute automation action"""
        if not self.connected:
            await self.connect()
        
        if not self.connected:
            return {"status": "error", "error": "Not connected to DaenaBot Hands"}
        
        # Build command
        command = {
            "token": self.token,
            "action": action,
            **params
        }
        
        try:
            # Send command
            await self.websocket.send(json.dumps(command))
            
            # Wait for response
            response = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=timeout
            )
            
            return json.loads(response)
        except asyncio.TimeoutError:
            return {"status": "error", "error": f"Timeout after {timeout}s"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

# Singleton instance
_client = OpenClawGatewayClient()

async def get_client() -> OpenClawGatewayClient:
    """Get or create client instance"""
    return _client
```

### C) Create scripts/start_daenabot_hands.py:
```python
#!/usr/bin/env python3
"""
Startup script for DaenaBot Hands service
Run this in a separate terminal/process
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.daenabot_hands_server import DaenaBotHandsServer
import asyncio

def main():
    print("""
╔══════════════════════════════════════════╗
║      DAENABOT HANDS SERVICE v1.0         ║
║  Automation Layer for Desktop Control    ║
╚══════════════════════════════════════════╝
""")
    
    # Check for required environment variables
    if not os.getenv("DAENABOT_HANDS_TOKEN"):
        print("❌ ERROR: DAENABOT_HANDS_TOKEN not set in .env")
        print("   Please add a strong random token to .env:")
        print("   DAENABOT_HANDS_TOKEN=<your-secret-token>")
        return
    
    print("✓ Configuration loaded")
    print(f"✓ Listening on ws://127.0.0.1:18789/ws")
    print(f"✓ Log file: logs/daenabot_hands.log")
    print(f"✓ Screenshots will be saved to: screenshots/")
    print("\nPress Ctrl+C to stop\n")
    
    server = DaenaBotHandsServer()
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n\n✓ Shutting down gracefully...")
        asyncio.run(server.shutdown())

if __name__ == "__main__":
    main()
```

### D) Update .env (add if not present):
```env
# DaenaBot Hands Configuration
DAENABOT_HANDS_URL=ws://127.0.0.1:18789/ws
DAENABOT_HANDS_TOKEN=<generate a strong 64-character random token>
```

### E) Create backend/services/hands_approval_queue.py:
```python
import asyncio
from datetime import datetime
from typing import List, Dict
import json

class HandsApprovalQueue:
    """
    Queue for automation actions awaiting founder approval
    """
    
    def __init__(self):
        self.queue: List[Dict] = []
        self.approved: List[Dict] = []
        self.rejected: List[Dict] = []
    
    async def add(self, action: dict) -> str:
        """Add action to approval queue"""
        request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        action_request = {
            "request_id": request_id,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        self.queue.append(action_request)
        return request_id
    
    async def get_pending(self) -> List[Dict]:
        """Get all pending approvals"""
        return [req for req in self.queue if req["status"] == "pending"]
    
    async def approve(self, request_id: str, founder_token: str) -> bool:
        """Approve an action"""
        # Verify founder token
        if founder_token != os.getenv("FOUNDER_APPROVAL_TOKEN"):
            return False
        
        for req in self.queue:
            if req["request_id"] == request_id:
                req["status"] = "approved"
                req["approved_at"] = datetime.now().isoformat()
                self.approved.append(req)
                return True
        
        return False
    
    async def reject(self, request_id: str, founder_token: str, reason: str = "") -> bool:
        """Reject an action"""
        # Verify founder token
        if founder_token != os.getenv("FOUNDER_APPROVAL_TOKEN"):
            return False
        
        for req in self.queue:
            if req["request_id"] == request_id:
                req["status"] = "rejected"
                req["rejected_at"] = datetime.now().isoformat()
                req["rejection_reason"] = reason
                self.rejected.append(req)
                return True
        
        return False
    
    async def get_approved_action(self, request_id: str) -> dict:
        """Get approved action for execution"""
        for req in self.approved:
            if req["request_id"] == request_id and req["status"] == "approved":
                return req["action"]
        return None

# Singleton
_approval_queue = HandsApprovalQueue()

def get_approval_queue() -> HandsApprovalQueue:
    return _approval_queue
```

### F) Create tests/test_daenabot_hands.py:
```python
import pytest
import asyncio
from backend.services.daenabot_hands_server import DaenaBotHandsServer
from backend.integrations.openclaw_gateway_client import OpenClawGatewayClient

@pytest.mark.asyncio
async def test_connection():
    """Test WebSocket connection"""
    client = OpenClawGatewayClient()
    await client.connect()
    assert client.connected == True
    await client.disconnect()

@pytest.mark.asyncio
async def test_click_action():
    """Test click action"""
    client = OpenClawGatewayClient()
    await client.connect()
    
    response = await client.execute("click", {"x": 100, "y": 100})
    assert response["status"] == "success"
    
    await client.disconnect()

@pytest.mark.asyncio
async def test_screenshot():
    """Test screenshot action"""
    client = OpenClawGatewayClient()
    await client.connect()
    
    response = await client.execute("screenshot", {})
    assert response["status"] == "success"
    assert "path" in response
    
    await client.disconnect()

@pytest.mark.asyncio
async def test_shell_command():
    """Test shell command execution"""
    client = OpenClawGatewayClient()
    await client.connect()
    
    response = await client.execute("shell", {"command": "echo test"})
    assert response["status"] == "success"
    
    await client.disconnect()

@pytest.mark.asyncio
async def test_unauthorized():
    """Test that wrong token is rejected"""
    client = OpenClawGatewayClient()
    client.token = "wrong_token"
    await client.connect()
    
    response = await client.execute("click", {"x": 100, "y": 100})
    assert response["status"] == "error"
    assert "Unauthorized" in response["error"]
    
    await client.disconnect()
```

## CONSTRAINTS
- All desktop automation must be SANDBOXED (no destructive actions without approval)
- Browser automation must run in a separate profile
- Shell commands must be whitelisted (check ALLOWED_SHELL_COMMANDS)
- Log every action with timestamp and result to logs/daenabot_hands.log

## INSTALLATION REQUIREMENTS
Add to requirements.txt:
```
websockets==12.0
pyautogui==0.9.54
playwright==1.40.0
```

Install:
```bash
pip install websockets pyautogui playwright
playwright install chromium
```

## STARTUP INSTRUCTIONS
1. Set DAENABOT_HANDS_TOKEN in .env (use `python -c "import secrets; print(secrets.token_hex(32))"`)
2. Start Hands service: `python scripts/start_daenabot_hands.py`
3. Start backend: `python backend/main.py`
4. Test from frontend or API

## DELIVERABLE
Provide:
1. All new files created
2. Integration with existing backend (tool_broker should route through Hands)
3. Startup instructions
4. Test results from tests/test_daenabot_hands.py

## TESTING CHECKLIST
- [ ] Start Hands service → Should show "Listening on ws://127.0.0.1:18789/ws"
- [ ] Start backend → Should show "Connected to DaenaBot Hands"
- [ ] Click "Test Screenshot" in frontend → Should take screenshot
- [ ] Click "Test Browser" → Should open browser and navigate
- [ ] Check logs/daenabot_hands.log → Should show all actions
- [ ] Try action without token → Should get "Unauthorized"
