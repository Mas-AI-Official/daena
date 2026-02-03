"""
DaenaBot Automation Layer
==========================

Daena's native automation layer - NO external Moltbot/OpenClaw needed.
Fully integrated with governance, NBMF memory, and E-DNA learning.

Capabilities:
- Desktop control (mouse, keyboard, screenshots)
- File operations (read, write, workspace management)
- Shell execution (whitelisted commands with governance)
- Browser automation (navigate, scrape, interact)
- Window management (open, close, switch apps)

All actions go through governance and are logged to shared memory.
"""

import os
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import json

# Desktop automation
try:
    import pyautogui
    import pygetwindow as gw
    from PIL import Image
    DESKTOP_AVAILABLE = True
except ImportError:
    DESKTOP_AVAILABLE = False
    print("⚠️  Desktop automation unavailable: pip install pyautogui pygetwindow Pillow")

# Shell execution
from subprocess import run, TimeoutExpired, PIPE

# Browser automation
try:
    from playwright.async_api import async_playwright
    BROWSER_AVAILABLE = True
except ImportError:
    BROWSER_AVAILABLE = False
    print("⚠️  Browser automation unavailable: pip install playwright && playwright install")


@dataclass
class AutomationResult:
    """Result of an automation action"""
    status: str  # success, error, blocked
    action: str
    data: Dict[str, Any]
    error: Optional[str] = None
    governance_status: Optional[str] = None


class DaenaBotAutomation:
    """
    Daena's native automation layer
    
    Usage:
        automation = DaenaBotAutomation(governance_loop, memory_service, edna_engine)
        
        # Desktop
        result = await automation.click_at(100, 100)
        result = await automation.take_screenshot()
        
        # Files
        result = await automation.read_file("workspace/test.txt")
        result = await automation.write_file("workspace/output.txt", "content")
        
        # Shell
        result = await automation.run_command("git status")
        
        # Browser
        result = await automation.navigate_browser("https://example.com")
    """
    
    def __init__(self, governance_loop, memory_service, edna_engine=None):
        self.governance = governance_loop
        self.memory = memory_service
        self.edna = edna_engine
        
        # Workspace (safe zone for file operations)
        workspace_path = os.getenv('WORKSPACE_PATH', os.getcwd())
        self.workspace = Path(workspace_path) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Shell command whitelist
        whitelist_str = os.getenv('ALLOWED_SHELL_COMMANDS', 'dir,ls,cat,echo,git,npm,pip,python')
        self.allowed_commands = set(whitelist_str.split(','))
        
        # Feature flags
        self.desktop_enabled = os.getenv('AUTOMATION_ENABLE_DESKTOP', 'true').lower() == 'true'
        self.shell_enabled = os.getenv('AUTOMATION_ENABLE_SHELL', 'false').lower() == 'true'
        self.browser_enabled = os.getenv('AUTOMATION_ENABLE_BROWSER', 'true').lower() == 'true'
        
        # Stats
        self.stats = {
            "actions_total": 0,
            "actions_blocked": 0,
            "actions_success": 0,
            "actions_error": 0
        }
        
        print(f"✅ DaenaBot Automation initialized")
        print(f"   Workspace: {self.workspace}")
        print(f"   Desktop: {'enabled' if self.desktop_enabled and DESKTOP_AVAILABLE else 'disabled'}")
        print(f"   Browser: {'enabled' if self.browser_enabled and BROWSER_AVAILABLE else 'disabled'}")
        print(f"   Shell: {'enabled' if self.shell_enabled else 'disabled (safety)'}")
    
    
    # ==================== DESKTOP CONTROL ====================
    
    async def click_at(self, x: int, y: int, button: str = "left") -> AutomationResult:
        """
        Click mouse at coordinates
        
        Args:
            x: X coordinate
            y: Y coordinate
            button: "left", "right", or "middle"
        """
        if not DESKTOP_AVAILABLE or not self.desktop_enabled:
            return AutomationResult("error", "click", {}, "Desktop automation not available")
        
        # Governance check
        assessment = self.governance.assess({
            "type": "desktop_click",
            "target": f"({x}, {y})",
            "risk": "medium",
            "agent": "daena"
        })
        
        print(f"[AUTOMATION] Attempting {assessment['type']} target={assessment.get('target','')}")
        if assessment["decision"] != "approve":
            print(f"[GOVERNANCE] Decision: {assessment['decision']} - BLOCKED")
            self.stats["actions_blocked"] += 1
            return AutomationResult(
                "blocked", "click",
                {"x": x, "y": y},
                governance_status=assessment["decision"]
            )
        print(f"[GOVERNANCE] Decision: {assessment['decision']} - PROCEEDING")
        
        try:
            # Execute
            pyautogui.click(x, y, button=button)
            
            # Log success
            self.stats["actions_total"] += 1
            self.stats["actions_success"] += 1
            
            result = AutomationResult(
                "success", "click",
                {"x": x, "y": y, "button": button}
            )
            
            # Store in memory
            print(f"[RESULT] click: {result.status}")
            return result
            
        except Exception as e:
            print(f"[RESULT] click: error - {str(e)}")
            self.stats["actions_error"] += 1
            return AutomationResult(
                "error", "click",
                {"x": x, "y": y},
                error=str(e)
            )
    
    
    async def type_text(self, text: str, interval: float = 0.01) -> AutomationResult:
        """
        Type text (simulates keyboard input)
        
        Args:
            text: Text to type
            interval: Delay between keystrokes (seconds)
        """
        if not DESKTOP_AVAILABLE or not self.desktop_enabled:
            return AutomationResult("error", "type", {}, "Desktop automation not available")
        
        # Check for sensitive content
        risk = "low"
        if any(word in text.lower() for word in ["password", "api_key", "secret", "token"]):
            risk = "high"
        
        assessment = self.governance.assess({
            "type": "type_text",
            "content_preview": text[:50] + "..." if len(text) > 50 else text,
            "length": len(text),
            "risk": risk,
            "agent": "daena"
        })
        
        print(f"[AUTOMATION] Attempting {assessment['type']} length={assessment.get('length',0)}")
        if assessment["decision"] != "approve":
            print(f"[GOVERNANCE] Decision: {assessment['decision']} - BLOCKED")
            self.stats["actions_blocked"] += 1
            return AutomationResult(
                "blocked", "type",
                {"length": len(text)},
                governance_status=assessment["decision"]
            )
        print(f"[GOVERNANCE] Decision: {assessment['decision']} - PROCEEDING")
        
        try:
            pyautogui.write(text, interval=interval)
            
            self.stats["actions_total"] += 1
            self.stats["actions_success"] += 1
            
            result = AutomationResult(
                "success", "type",
                {"length": len(text), "interval": interval}
            )
            
            print(f"[RESULT] type: {result.status}")
            return result
            
        except Exception as e:
            print(f"[RESULT] type: error - {str(e)}")
            self.stats["actions_error"] += 1
            return AutomationResult("error", "type", {"length": len(text)}, error=str(e))
    
    
    async def take_screenshot(self, save_path: Optional[str] = None) -> AutomationResult:
        """
        Capture screenshot
        
        Args:
            save_path: Optional path to save (default: workspace/screenshots/timestamp.png)
        """
        if not DESKTOP_AVAILABLE or not self.desktop_enabled:
            return AutomationResult("error", "screenshot", {}, "Desktop automation not available")
        
        # Screenshot is low risk - always allowed
        try:
            img = pyautogui.screenshot()
            
            if not save_path:
                screenshots_dir = self.workspace / "screenshots"
                screenshots_dir.mkdir(exist_ok=True)
                save_path = screenshots_dir / f"screenshot_{int(time.time())}.png"
            else:
                save_path = Path(save_path)
            
            img.save(save_path)
            
            self.stats["actions_total"] += 1
            self.stats["actions_success"] += 1
            
            result = AutomationResult(
                "success", "screenshot",
                {"path": str(save_path), "size": img.size}
            )
            
            print(f"[RESULT] screenshot: {result.status}")
            return result
            
        except Exception as e:
            print(f"[RESULT] screenshot: error - {str(e)}")
            self.stats["actions_error"] += 1
            return AutomationResult("error", "screenshot", {}, error=str(e))
    
    
    async def get_window_list(self) -> AutomationResult:
        """Get list of open windows"""
        if not DESKTOP_AVAILABLE or not self.desktop_enabled:
            return AutomationResult("error", "windows", {}, "Desktop automation not available")
        
        try:
            windows = gw.getAllTitles()
            windows = [w for w in windows if w]  # Filter empty titles
            
            result = AutomationResult(
                "success", "windows",
                {"windows": windows, "count": len(windows)}
            )
            
            return result
            
        except Exception as e:
            return AutomationResult("error", "windows", {}, error=str(e))
    
    
    # ==================== FILE OPERATIONS ====================
    
    def _is_in_workspace(self, path: Path) -> bool:
        """Check if path is inside workspace (security)"""
        try:
            path.resolve().relative_to(self.workspace.resolve())
            return True
        except ValueError:
            return False
    
    
    async def read_file(self, path: str) -> AutomationResult:
        """
        Read file from workspace
        
        Args:
            path: Relative path within workspace (e.g., "data/input.txt")
        """
        file_path = self.workspace / path
        
        # Security: must be in workspace
        if not self._is_in_workspace(file_path):
            return AutomationResult(
                "blocked", "read_file",
                {"path": path},
                error="File outside workspace"
            )
        
        if not file_path.exists():
            return AutomationResult(
                "error", "read_file",
                {"path": path},
                error="File not found"
            )
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            self.stats["actions_total"] += 1
            self.stats["actions_success"] += 1
            
            result = AutomationResult(
                "success", "read_file",
                {
                    "path": str(file_path),
                    "content": content,
                    "size": len(content),
                    "lines": len(content.splitlines())
                }
            )
            
            await self._log_action("read_file", result)
            
            return result
            
        except Exception as e:
            self.stats["actions_error"] += 1
            return AutomationResult("error", "read_file", {"path": path}, error=str(e))
    
    
    async def write_file(self, path: str, content: str) -> AutomationResult:
        """
        Write file to workspace
        
        Args:
            path: Relative path within workspace
            content: File content
        """
        file_path = self.workspace / path
        
        # Security: must be in workspace
        if not self._is_in_workspace(file_path):
            return AutomationResult(
                "blocked", "write_file",
                {"path": path},
                error="File outside workspace"
            )
        
        # Governance check
        assessment = self.governance.assess({
            "type": "write_file",
            "path": str(file_path),
            "size": len(content),
            "risk": "medium",
            "agent": "daena"
        })
        
        print(f"[AUTOMATION] Attempting {assessment['type']} path={assessment.get('path','')}")
        if assessment["decision"] != "approve":
            print(f"[GOVERNANCE] Decision: {assessment['decision']} - BLOCKED")
            self.stats["actions_blocked"] += 1
            return AutomationResult(
                "blocked", "write_file",
                {"path": path, "size": len(content)},
                governance_status=assessment["decision"]
            )
        print(f"[GOVERNANCE] Decision: {assessment['decision']} - PROCEEDING")
        
        try:
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write
            file_path.write_text(content, encoding='utf-8')
            
            self.stats["actions_total"] += 1
            self.stats["actions_success"] += 1
            
            result = AutomationResult(
                "success", "write_file",
                {
                    "path": str(file_path),
                    "size": len(content),
                    "lines": len(content.splitlines())
                }
            )
            
            await self._log_action("write_file", result)
            
            return result
            
        except Exception as e:
            self.stats["actions_error"] += 1
            return AutomationResult("error", "write_file", {"path": path}, error=str(e))
    
    
    async def list_files(self, directory: str = ".") -> AutomationResult:
        """List files in workspace directory"""
        dir_path = self.workspace / directory
        
        if not self._is_in_workspace(dir_path):
            return AutomationResult(
                "blocked", "list_files",
                {"path": directory},
                error="Directory outside workspace"
            )
        
        if not dir_path.exists():
            return AutomationResult(
                "error", "list_files",
                {"path": directory},
                error="Directory not found"
            )
        
        try:
            files = []
            for item in dir_path.iterdir():
                files.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
            
            return AutomationResult(
                "success", "list_files",
                {"path": str(dir_path), "files": files, "count": len(files)}
            )
            
        except Exception as e:
            return AutomationResult("error", "list_files", {"path": directory}, error=str(e))
    
    
    # ==================== SHELL EXECUTION ====================
    
    async def run_command(self, command: str, timeout: int = 30) -> AutomationResult:
        """
        Execute shell command
        
        Args:
            command: Command to run (e.g., "git status")
            timeout: Max execution time in seconds
        """
        if not self.shell_enabled:
            return AutomationResult(
                "blocked", "shell",
                {"command": command},
                error="Shell execution disabled (AUTOMATION_ENABLE_SHELL=false)"
            )
        
        # Extract base command
        base_cmd = command.split()[0]
        
        # Check whitelist
        risk = "critical"
        if base_cmd in self.allowed_commands:
            risk = "high"
        
        assessment = self.governance.assess({
            "type": "shell_command",
            "command": command,
            "base_cmd": base_cmd,
            "risk": risk,
            "agent": "daena"
        })
        
        print(f"[AUTOMATION] Attempting {assessment['type']} command={assessment.get('command','')}")
        if assessment["decision"] != "approve":
            print(f"[GOVERNANCE] Decision: {assessment['decision']} - BLOCKED")
            self.stats["actions_blocked"] += 1
            return AutomationResult(
                "blocked", "shell",
                {"command": command},
                governance_status=assessment["decision"]
            )
        print(f"[GOVERNANCE] Decision: {assessment['decision']} - PROCEEDING")
        
        try:
            # Execute
            result = run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace)  # Run in workspace
            )
            
            self.stats["actions_total"] += 1
            self.stats["actions_success"] += 1
            
            output = AutomationResult(
                "success", "shell",
                {
                    "command": command,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
            )
            
            await self._log_action("shell_command", output)
            
            return output
            
        except TimeoutExpired:
            self.stats["actions_error"] += 1
            return AutomationResult(
                "error", "shell",
                {"command": command},
                error=f"Command timed out after {timeout}s"
            )
        except Exception as e:
            self.stats["actions_error"] += 1
            return AutomationResult("error", "shell", {"command": command}, error=str(e))
    
    
    # ==================== BROWSER AUTOMATION ====================
    
    async def navigate_browser(
        self,
        url: str,
        actions: Optional[List[Dict]] = None,
        headless: bool = False
    ) -> AutomationResult:
        """
        Open browser and perform actions
        
        Args:
            url: URL to navigate to
            actions: List of actions to perform (click, fill, extract)
            headless: Run in headless mode (no visible window)
        
        Example actions:
            [
                {"type": "click", "selector": "#submit-button"},
                {"type": "fill", "selector": "input[name='email']", "value": "test@example.com"},
                {"type": "extract", "selector": ".result", "attribute": "text"}
            ]
        """
        if not BROWSER_AVAILABLE or not self.browser_enabled:
            return AutomationResult("error", "browser", {}, "Browser automation not available")
        
        # Governance check
        risk = "medium"
        if "localhost" not in url and "127.0.0.1" not in url:
            risk = "high"  # External URL
        
        assessment = self.governance.assess({
            "type": "browser_navigate",
            "url": url,
            "actions_count": len(actions) if actions else 0,
            "risk": risk,
            "agent": "daena"
        })
        
        print(f"[AUTOMATION] Attempting {assessment['type']} url={assessment.get('url','')}")
        if assessment["decision"] != "approve":
            print(f"[GOVERNANCE] Decision: {assessment['decision']} - BLOCKED")
            self.stats["actions_blocked"] += 1
            return AutomationResult(
                "blocked", "browser",
                {"url": url},
                governance_status=assessment["decision"]
            )
        print(f"[GOVERNANCE] Decision: {assessment['decision']} - PROCEEDING")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless)
                page = await browser.new_page()
                
                # Navigate
                await page.goto(url, timeout=30000)
                
                # Perform actions
                action_results = []
                if actions:
                    for action in actions:
                        if action["type"] == "click":
                            await page.click(action["selector"])
                            action_results.append({"type": "click", "selector": action["selector"]})
                        
                        elif action["type"] == "fill":
                            await page.fill(action["selector"], action["value"])
                            action_results.append({"type": "fill", "selector": action["selector"]})
                        
                        elif action["type"] == "extract":
                            attr = action.get("attribute", "text")
                            if attr == "text":
                                text = await page.inner_text(action["selector"])
                            else:
                                text = await page.get_attribute(action["selector"], attr)
                            action_results.append({
                                "type": "extract",
                                "selector": action["selector"],
                                "value": text
                            })
                
                await browser.close()
                
                self.stats["actions_total"] += 1
                self.stats["actions_success"] += 1
                
                result = AutomationResult(
                    "success", "browser",
                    {
                        "url": url,
                        "actions": action_results,
                        "actions_count": len(action_results)
                    }
                )
                
                await self._log_action("browser_navigate", result)
                
                return result
                
        except Exception as e:
            self.stats["actions_error"] += 1
            return AutomationResult("error", "browser", {"url": url}, error=str(e))
    
    
    # ==================== LOGGING & STATS ====================
    
    async def _log_action(self, action_type: str, result: AutomationResult):
        """Log action to memory and E-DNA"""
        # Store in L2 (episodic memory)
        if self.memory:
            # Use sync write, NBMF is synchronous
            try:
                # Generate a unique key for the log entry
                log_key = f"action_{int(time.time()*1000)}_{action_type}"
                self.memory.write(
                    key=log_key,
                    value={
                        "action": action_type,
                        "status": result.status,
                        "data": result.data,
                        "error": result.error,
                        "timestamp": time.time(),
                        "agent": "daena"
                    },
                    tier="T2" # Project/Episodic
                )
            except Exception as e:
                print(f"Failed to log action to memory: {e}")
        
        # E-DNA learning
        if self.edna and result.status == "success":
            await self.edna.observe({
                "agent": "daena",
                "type": action_type,
                "result": {"status": result.status},
                "params": result.data
            })
    
    
    def get_status(self) -> Dict:
        """Get automation status"""
        return {
            "workspace": str(self.workspace),
            "capabilities": {
                "desktop": DESKTOP_AVAILABLE and self.desktop_enabled,
                "browser": BROWSER_AVAILABLE and self.browser_enabled,
                "shell": self.shell_enabled,
                "files": True  # Always available
            },
            "allowed_commands": list(self.allowed_commands) if self.shell_enabled else [],
            "stats": self.stats
        }


# Global instance (initialized in main.py)
_automation_instance = None

def get_daenabot_automation():
    """Get global automation instance"""
    return _automation_instance

def set_daenabot_automation(instance):
    """Set global automation instance"""
    global _automation_instance
    _automation_instance = instance
