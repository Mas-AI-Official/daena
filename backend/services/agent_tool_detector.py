"""
Agent Tool Detector for Daena AI VP

Detects tool intents from agent messages and routes to appropriate tools:
- Browser automation (navigate, search, screenshot)
- Code operations (scan, analyze, modify)
- Database operations (query, list, update)
- MCP connections (external AI assistants)
- File operations (read, write, list)

Uses the intelligent router for complex decisions.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Categories of tools available to agents"""
    BROWSER = "browser"
    CODE = "code"
    DATABASE = "database"
    FILE = "file"
    MCP = "mcp"
    API = "api"
    SYSTEM = "system"
    NONE = "none"


@dataclass
class ToolIntent:
    """Detected tool intent from a message"""
    category: ToolCategory
    action: str
    args: Dict[str, Any]
    confidence: float
    raw_match: str


# Tool patterns for detection
TOOL_PATTERNS = {
    ToolCategory.BROWSER: [
        (r"(?:go to|navigate to|open|visit)\s+(.+)", "navigate", ["url"]),
        (r"search\s+(?:for\s+)?(.+)", "search", ["query"]),
        (r"screenshot\s*(?:of\s+)?(.+)?", "screenshot", ["url"]),
        (r"click\s+(?:on\s+)?(.+)", "click", ["selector"]),
        (r"type\s+['\"](.+)['\"]\s+(?:in|into)\s+(.+)", "type", ["text", "selector"]),
        (r"browse\s+(.+)", "navigate", ["url"]),
    ],
    ToolCategory.CODE: [
        (r"scan\s+(.+)", "scan", ["path"]),
        (r"analyze\s+(?:code\s+)?(?:in\s+)?(.+)", "analyze", ["path"]),
        (r"search\s+(?:code\s+)?(?:for\s+)?['\"](.+)['\"]\s+(?:in\s+)?(.+)", "search", ["pattern", "path"]),
        (r"find\s+(?:files?\s+)?(?:matching\s+)?(.+)", "find", ["pattern"]),
        (r"list\s+(?:files?\s+)?(?:in\s+)?(.+)", "list", ["path"]),
        (r"read\s+(?:file\s+)?(.+)", "read", ["path"]),
    ],
    ToolCategory.DATABASE: [
        (r"show\s+tables", "show_tables", []),
        (r"show\s+columns\s+(?:in|from)\s+(.+)", "show_columns", ["table"]),
        (r"query\s+(.+)", "query", ["sql"]),
        (r"select\s+.+\s+from\s+(.+)", "query", ["sql"]),
        (r"count\s+(?:rows?\s+)?(?:in\s+)?(.+)", "count", ["table"]),
        (r"list\s+(?:all\s+)?agents", "list_agents", []),
        (r"list\s+(?:all\s+)?departments", "list_departments", []),
    ],
    ToolCategory.MCP: [
        (r"discover\s+(?:mcp\s+)?servers?", "discover", []),
        (r"connect\s+(?:to\s+)?(.+)", "connect", ["server_id"]),
        (r"disconnect\s+(?:from\s+)?(.+)", "disconnect", ["server_id"]),
        (r"list\s+(?:mcp\s+)?connections?", "list_connections", []),
        (r"ask\s+(\w+)\s+(.+)", "ask", ["server_id", "question"]),
    ],
    ToolCategory.FILE: [
        (r"read\s+(?:file\s+)?(.+)", "read", ["path"]),
        (r"write\s+(?:to\s+)?(.+)", "write", ["path"]),
        (r"create\s+(?:file\s+)?(.+)", "create", ["path"]),
        (r"delete\s+(?:file\s+)?(.+)", "delete", ["path"]),
        (r"list\s+(?:files?\s+)?(?:in\s+)?(.+)", "list", ["path"]),
    ],
    ToolCategory.API: [
        (r"call\s+(?:api\s+)?(.+)", "call", ["endpoint"]),
        (r"get\s+(.+)", "get", ["url"]),
        (r"post\s+(?:to\s+)?(.+)", "post", ["url"]),
        (r"health\s+check\s+(.+)?", "health_check", ["service"]),
    ],
    ToolCategory.SYSTEM: [
        (r"status", "status", []),
        (r"restart\s+(.+)", "restart", ["service"]),
        (r"stop\s+(.+)", "stop", ["service"]),
        (r"start\s+(.+)", "start", ["service"]),
    ],
}


class AgentToolDetector:
    """
    Detects tool intents from agent messages.
    
    Uses pattern matching for common commands and can fall back
    to LLM-based detection for complex cases.
    """
    
    def __init__(self):
        self.detection_history: List[Dict] = []
        
    def detect(self, message: str) -> Optional[ToolIntent]:
        """
        Detect tool intent from a message.
        
        Args:
            message: The agent message to analyze
            
        Returns:
            ToolIntent if a tool is detected, None otherwise
        """
        message_clean = message.strip().lower()
        
        # Try pattern matching first (fast)
        intent = self._pattern_detect(message_clean, message)
        
        if intent:
            self._log_detection(message, intent)
            return intent
            
        # If no pattern match, could use LLM for complex detection
        # (disabled for performance, enable if needed)
        # intent = await self._llm_detect(message)
        
        return None
    
    def _pattern_detect(self, message_lower: str, original: str) -> Optional[ToolIntent]:
        """Detect tool using regex patterns"""
        
        for category, patterns in TOOL_PATTERNS.items():
            for pattern, action, arg_names in patterns:
                match = re.search(pattern, message_lower, re.IGNORECASE)
                if match:
                    # Extract arguments
                    args = {}
                    groups = match.groups()
                    for i, arg_name in enumerate(arg_names):
                        if i < len(groups) and groups[i]:
                            args[arg_name] = groups[i].strip()
                    
                    # Calculate confidence based on match quality
                    confidence = self._calculate_confidence(match, message_lower)
                    
                    return ToolIntent(
                        category=category,
                        action=action,
                        args=args,
                        confidence=confidence,
                        raw_match=match.group(0)
                    )
                    
        return None
    
    def _calculate_confidence(self, match: re.Match, message: str) -> float:
        """Calculate confidence score for a match"""
        # Base confidence
        confidence = 0.7
        
        # Higher confidence if match covers more of the message
        coverage = len(match.group(0)) / len(message)
        confidence += coverage * 0.2
        
        # Higher confidence if match is at the start
        if match.start() < 5:
            confidence += 0.1
            
        return min(confidence, 1.0)
    
    async def detect_with_llm(self, message: str) -> Optional[ToolIntent]:
        """
        Use LLM to detect tool intent for complex messages.
        
        This is slower but more accurate for ambiguous cases.
        """
        try:
            from backend.services.intelligent_router import intelligent_router, TaskType
            from backend.services.llm_service import llm_service
            
            # Check if this is a tool-related task
            routing = await intelligent_router.route(message)
            
            if routing.model_name == "offline":
                return None
                
            # Use LLM to parse intent
            prompt = f"""Analyze this message and detect if it's requesting a tool action.
            
Message: {message}

Available tools:
- browser: navigate, search, screenshot, click
- code: scan, analyze, search, read
- database: query, show_tables, show_columns
- file: read, write, list, delete
- mcp: connect, disconnect, ask
- api: call, get, post

If this is a tool request, respond with JSON:
{{"category": "tool_name", "action": "action_name", "args": {{"arg1": "value1"}}}}

If NOT a tool request, respond with:
{{"category": "none"}}

JSON response:"""

            response = await llm_service.generate_response(
                prompt=prompt,
                provider=routing.provider,
                model=routing.model_name,
                temperature=0.1,
                max_tokens=200
            )
            
            # Parse JSON response
            import json
            try:
                result = json.loads(response.strip())
                if result.get("category") != "none":
                    return ToolIntent(
                        category=ToolCategory(result["category"]),
                        action=result.get("action", "execute"),
                        args=result.get("args", {}),
                        confidence=0.85,
                        raw_match=message
                    )
            except json.JSONDecodeError:
                logger.warning(f"Could not parse LLM tool detection response: {response}")
                
        except Exception as e:
            logger.error(f"LLM tool detection failed: {e}")
            
        return None
    
    def _log_detection(self, message: str, intent: ToolIntent):
        """Log detection for learning"""
        from datetime import datetime
        
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message[:100],
            "category": intent.category.value,
            "action": intent.action,
            "args": intent.args,
            "confidence": intent.confidence,
        }
        
        self.detection_history.append(entry)
        
        # Keep only last 100
        if len(self.detection_history) > 100:
            self.detection_history = self.detection_history[-100:]
            
        logger.info(f"Tool detected: {intent.category.value}.{intent.action} (conf: {intent.confidence:.2f})")
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """Get detection statistics"""
        if not self.detection_history:
            return {"total_detections": 0}
            
        category_counts = {}
        action_counts = {}
        
        for entry in self.detection_history:
            cat = entry.get("category", "unknown")
            act = entry.get("action", "unknown")
            
            category_counts[cat] = category_counts.get(cat, 0) + 1
            action_counts[f"{cat}.{act}"] = action_counts.get(f"{cat}.{act}", 0) + 1
            
        return {
            "total_detections": len(self.detection_history),
            "by_category": category_counts,
            "by_action": action_counts,
        }


# Global singleton
agent_tool_detector = AgentToolDetector()


async def detect_and_route_tool(message: str, agent_id: str = "daena") -> Optional[Dict[str, Any]]:
    """
    Convenience function to detect tool and prepare for execution.
    
    Args:
        message: The message to analyze
        agent_id: The requesting agent's ID
        
    Returns:
        Dict with tool info if detected, None otherwise
    """
    intent = agent_tool_detector.detect(message)
    
    if not intent:
        # Try LLM detection for complex cases
        intent = await agent_tool_detector.detect_with_llm(message)
        
    if not intent:
        return None
        
    return {
        "tool_name": intent.category.value,
        "action": intent.action,
        "args": intent.args,
        "confidence": intent.confidence,
        "agent_id": agent_id,
        "ready_to_execute": intent.confidence > 0.6,
    }
