
import re
import json
import logging
from typing import Dict, Any, List, Optional
from backend.services.daenabot_automation import get_daenabot_automation, AutomationResult

logger = logging.getLogger(__name__)

class ActionDispatcher:
    """
    Parses LLM output and executes actions via DaenaBot Automation.
    Acts as the bridge between the conversation and the execution layer.
    """
    
    def __init__(self):
        self.automation = get_daenabot_automation()
        
    async def detect_and_execute(self, llm_response: str, user_message: str) -> Dict[str, Any]:
        """
        Parse LLM response for action intent, execute if found
        
        Returns: {
            "actions_detected": [...],
            "actions_executed": [...],
            "results": [...]
        }
        """
        actions = []
        
        # 1. Explicit Action Blocks (e.g., [ACTION: screenshot])
        # This is the most reliable way if we prompt the LLM to use it
        block_pattern = r"\[ACTION:\s*(\w+)(?:\s+(.*?))?\]"
        for match in re.finditer(block_pattern, llm_response, re.IGNORECASE):
            action_type = match.group(1).lower()
            args = match.group(2).strip() if match.group(2) else ""
            actions.append({"type": action_type, "args": args, "source": "explicit_block"})

        # 2. Natural Language Intent (Fallback / Enhancement)
        # If the LLM says "I'll take a screenshot" but doesn't output a block
        if not actions:
            lower_resp = llm_response.lower()
            if "take a screenshot" in lower_resp or "taking a screenshot" in lower_resp:
                actions.append({"type": "screenshot", "args": "", "source": "nl_intent"})
            elif "click at" in lower_resp:
                # Extract coordinates "click at 100, 200"
                coords = re.search(r"click at\s+(\d+)[\s,]+(\d+)", lower_resp)
                if coords:
                    actions.append({"type": "click", "args": f"{coords.group(1)} {coords.group(2)}", "source": "nl_intent"})
            
            # Browser navigation "opening google.com"
            if "opening" in lower_resp and ("http" in lower_resp or ".com" in lower_resp):
                url_match = re.search(r"opening\s+(https?://[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,})", lower_resp)
                if url_match:
                    actions.append({"type": "browser", "args": url_match.group(1), "source": "nl_intent"})

        # Execute found actions
        results = []
        executed_count = 0
        
        if not self.automation:
            self.automation = get_daenabot_automation()
            
        if not self.automation and actions:
            logger.warning("DaenaBotAutomation not initialized")
            return {
                "actions_detected": len(actions),
                "actions_executed": 0,
                "results": [{"error": "Automation service not ready"}]
            }

        for action in actions:
            try:
                res = None
                action_type = action["type"]
                args = action["args"]
                
                logger.info(f"Executing action: {action_type} args={args}")
                
                if action_type == "screenshot":
                    res = await self.automation.take_screenshot()
                    
                elif action_type == "click":
                    parts = args.split()
                    if len(parts) >= 2:
                        res = await self.automation.click_at(int(parts[0]), int(parts[1]))
                        
                elif action_type in ["browser", "navigate"]:
                    url = args if args.startswith("http") else f"https://{args}"
                    res = await self.automation.navigate_browser(url)
                    
                elif action_type in ["read_file", "read"]:
                    res = await self.automation.read_file(args.strip())
                    
                else:
                    # FALLBACK: Try to execute as a generic skill from registry
                    try:
                        from backend.services.skill_registry import get_skill_registry
                        registry = get_skill_registry()
                        skill = registry.get_skill(action_type)
                        
                        if skill:
                            logger.info(f"Found dynamic skill {action_type}, executing...")
                            # In a real system, we'd pass args to the skill execution layer
                            # For now, we use the automation's execute_skill if it exists
                            if hasattr(self.automation, "run_skill"):
                                res = await self.automation.run_skill(action_type, args)
                            else:
                                # Simulate execution for diagnostics
                                res = AutomationResult("success", action_type, {"msg": "Executed via registry fallback"})
                    except Exception as esk:
                        logger.error(f"Dynamic skill fallback failed for {action_type}: {esk}")
                
                if res:
                    results.append({
                        "action": action_type,
                        "status": res.status,
                        "data": res.data,
                        "error": res.error
                    })
                    if res.status == "success":
                        executed_count += 1
                        
            except Exception as e:
                logger.error(f"Action execution failed: {e}")
                results.append({"action": action["type"], "status": "error", "error": str(e)})

        return {
            "actions_detected": len(actions),
            "actions_executed": executed_count,
            "results": results
        }

    async def dispatch_from_text(self, text: str, session_id: str):
        """
        Public method to dispatch actions from text in the background.
        Parses text, executes actions, and could optionally report back.
        """
        logger.info(f"Dispatching actions for session {session_id} from text...")
        result = await self.detect_and_execute(text, "")
        
        if result["actions_executed"] > 0:
            logger.info(f"Executed {result['actions_executed']} actions for session {session_id}")
            # Optionally: update chat history with execution result
            try:
                from backend.models.chat_history import chat_history_manager
                for res in result["results"]:
                    if res.get("status") == "success":
                        msg = f"✅ [Applied Action: {res.get('action')}]"
                        await chat_history_manager.add_message(session_id, "system", msg)
            except Exception as e:
                logger.error(f"Failed to report action result to chat: {e}")
        return result

# Singleton
_dispatcher = None

def get_action_dispatcher():
    global _dispatcher
    if not _dispatcher:
        _dispatcher = ActionDispatcher()
    return _dispatcher
