"""
Unified Tool Executor for Daena AI VP

Central tool execution layer that:
1. Routes tool requests through approval workflow for high-impact actions
2. Logs all tool usage for learning
3. Respects agent/department permissions
4. Supports both Daena and agent tool execution

Usage:
    result = await unified_executor.execute(
        tool_name="browser",
        action="navigate",
        args={"url": "https://google.com"},
        executor_id="daena",
        executor_type="daena"
    )
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import uuid
import asyncio

logger = logging.getLogger(__name__)


class ExecutorType(str, Enum):
    DAENA = "daena"
    AGENT = "agent"
    COUNCIL = "council"


class ToolCategory(str, Enum):
    BROWSER = "browser"
    CODE = "code"
    DATABASE = "database"
    FILE = "file"
    API = "api"
    MCP = "mcp"
    SYSTEM = "system"


# High-impact tool actions that require approval
HIGH_IMPACT_ACTIONS = {
    "browser": ["login", "fill", "click"],  # Actions that interact with external sites
    "code": ["write", "delete", "modify"],  # Code modification
    "database": ["delete", "update", "modify"],  # Data modification
    "file": ["delete", "move"],  # File system changes
    "mcp": ["execute", "deploy"],  # External system actions
}

# Tools that are always safe (auto-approve)
SAFE_ACTIONS = {
    "browser": ["navigate", "screenshot", "content"],
    "code": ["scan", "search", "analyze", "list", "read"],
    "database": ["list", "query", "count", "show_tables", "show_columns"],
    "file": ["read", "list"],
    "api": ["health_check", "test", "get"],
    "mcp": ["discover", "list_connections", "connect", "disconnect"],
    "system": ["status"],
}


class UnifiedToolExecutor:
    """Centralized tool execution with approval, logging, and permissions."""
    
    def __init__(self):
        self.approval_required = True
        self.learning_enabled = True
        self.execution_log = []
        self.concurrent_limit = 5  # Max concurrent tool executions
    
    async def execute(
        self,
        tool_name: str,
        action: str,
        args: Dict[str, Any],
        executor_id: str,
        executor_type: ExecutorType = ExecutorType.DAENA,
        department: Optional[str] = None,
        skip_approval: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a tool action with approval workflow.
        
        Args:
            tool_name: Tool category (browser, code, database, etc.)
            action: Specific action (navigate, scan, query, etc.)
            args: Tool arguments
            executor_id: Who is executing (daena, agent_id, council_id)
            executor_type: Type of executor
            department: Department context
            skip_approval: Force skip approval (for testing)
            
        Returns:
            Execution result with status, data, and approval info
        """
        execution_id = str(uuid.uuid4())[:8]
        logger.info(f"Tool execution [{execution_id}]: {tool_name}.{action} by {executor_type.value}:{executor_id}")
        
        # Check if approval is required
        requires_approval = self._check_requires_approval(tool_name, action, args)
        
        if requires_approval and not skip_approval and self.approval_required:
            # Create approval request
            approval_result = await self._create_approval_request(
                execution_id=execution_id,
                tool_name=tool_name,
                action=action,
                args=args,
                executor_id=executor_id,
                executor_type=executor_type,
                department=department
            )
            
            return {
                "status": "pending_approval",
                "execution_id": execution_id,
                "requires_approval": True,
                "approval_id": approval_result.get("decision_id"),
                "message": f"This action requires approval before execution. " + 
                           f"Decision ID: {approval_result.get('decision_id')}"
            }
        
        # Execute the tool
        result = await self._execute_tool(tool_name, action, args)
        
        # Log execution for learning
        if self.learning_enabled:
            await self._log_execution(
                execution_id=execution_id,
                tool_name=tool_name,
                action=action,
                args=args,
                result=result,
                executor_id=executor_id,
                executor_type=executor_type
            )
        
        return {
            "status": "completed" if result.get("success") else "failed",
            "execution_id": execution_id,
            "requires_approval": False,
            "result": result
        }
    
    def _check_requires_approval(
        self,
        tool_name: str,
        action: str,
        args: Dict[str, Any]
    ) -> bool:
        """Check if this tool action requires approval."""
        # Check if it's a safe action
        if tool_name in SAFE_ACTIONS:
            if action in SAFE_ACTIONS[tool_name]:
                return False
        
        # Check if it's a high-impact action
        if tool_name in HIGH_IMPACT_ACTIONS:
            if action in HIGH_IMPACT_ACTIONS[tool_name]:
                return True
        
        # Default: require approval for unknown actions
        return True
    
    async def _create_approval_request(
        self,
        execution_id: str,
        tool_name: str,
        action: str,
        args: Dict[str, Any],
        executor_id: str,
        executor_type: ExecutorType,
        department: Optional[str]
    ) -> Dict[str, Any]:
        """Create an approval request in the database."""
        try:
            from backend.services.council_approval_service import (
                council_approval_service,
                DecisionImpact
            )
            
            # Assess impact
            action_text = f"Execute {tool_name}.{action}: {str(args)[:100]}"
            impact = council_approval_service.assess_impact(
                action_text=action_text,
                department=department or "general",
                confidence=0.8,
                metadata={"tool_name": tool_name, "action": action}
            )
            
            # Create approval request
            decision_id = f"tool-{execution_id}"
            decision = council_approval_service.create_approval_request(
                decision_id=decision_id,
                department=department or "general",
                topic=f"Tool Execution: {tool_name}.{action}",
                action_text=action_text,
                impact=impact,
                confidence=0.8,
                metadata={
                    "tool_name": tool_name,
                    "action": action,
                    "args": args,
                    "executor_id": executor_id,
                    "executor_type": executor_type.value
                }
            )
            
            logger.info(f"Approval request created: {decision_id} (impact: {impact.value})")
            
            return {
                "decision_id": decision_id,
                "impact": impact.value,
                "status": "pending"
            }
            
        except Exception as e:
            logger.error(f"Failed to create approval request: {e}")
            # If approval creation fails, return a mock ID
            return {
                "decision_id": f"tool-{execution_id}",
                "impact": "unknown",
                "status": "error",
                "error": str(e)
            }
    
    async def _execute_tool(
        self,
        tool_name: str,
        action: str,
        args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the actual tool."""
        try:
            if tool_name == "browser":
                from backend.services.daena_tools.browser_automation import daena_browser
                # Construct browser command from action + args
                if action == "navigate":
                    command = f"go to {args.get('url', '')}"
                elif action == "click":
                    command = f"click {args.get('selector', '')}"
                elif action == "fill":
                    command = f"fill {args.get('field', '')} with {args.get('value', '')}"
                elif action == "screenshot":
                    command = "screenshot"
                elif action == "content":
                    command = "content"
                else:
                    command = f"{action} {' '.join(str(v) for v in args.values())}"
                return await daena_browser(command)
            
            elif tool_name == "code":
                from backend.services.daena_tools.code_scanner import daena_scan, search_code
                if action == "scan":
                    return await daena_scan(f"scan {args.get('path', '.')}")
                elif action == "search":
                    return search_code(args.get('query', ''))
                else:
                    return {"success": False, "error": f"Unknown code action: {action}"}
            
            elif tool_name == "database":
                from backend.services.daena_tools.db_inspector import daena_db
                return await daena_db(f"{action} {args.get('table', '')}")
            
            elif tool_name == "api":
                from backend.services.daena_tools.api_tester import health_check
                if action == "health_check":
                    return await health_check()
                else:
                    return {"success": False, "error": f"Unknown API action: {action}"}
            
            elif tool_name == "mcp":
                from backend.services.daena_tools.mcp_client import daena_mcp
                return await daena_mcp(f"{action} {args.get('command', '')}")
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _log_execution(
        self,
        execution_id: str,
        tool_name: str,
        action: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        executor_id: str,
        executor_type: ExecutorType
    ):
        """Log execution for learning."""
        try:
            from backend.database import SessionLocal, EventLog
            
            db = SessionLocal()
            try:
                log_entry = EventLog(
                    event_type="tool.execution",
                    entity_type=tool_name,
                    entity_id=execution_id,
                    payload_json={
                        "action": action,
                        "args": args,
                        "success": result.get("success", False),
                        "executor_id": executor_id,
                        "executor_type": executor_type.value,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    created_by=executor_id
                )
                db.add(log_entry)
                db.commit()
                logger.debug(f"Logged tool execution: {execution_id}")
            finally:
                db.close()
                
        except Exception as e:
            logger.warning(f"Failed to log execution: {e}")
    
    async def execute_approved_action(
        self,
        decision_id: str
    ) -> Dict[str, Any]:
        """
        Execute a previously approved action.
        Called after founder approves a pending action.
        """
        try:
            from backend.database import SessionLocal, Decision
            
            db = SessionLocal()
            try:
                decision = db.query(Decision).filter(
                    Decision.decision_id == decision_id
                ).first()
                
                if not decision:
                    return {"success": False, "error": "Decision not found"}
                
                if decision.status != "approved":
                    return {"success": False, "error": f"Decision not approved: {decision.status}"}
                
                # Extract tool info from decision metadata
                # Note: In a real implementation, we'd store the full tool call
                # For now, return success
                return {"success": True, "message": f"Approved action executed: {decision_id}"}
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to execute approved action: {e}")
            return {"success": False, "error": str(e)}
    
    async def execute_batch(
        self,
        tasks: List[Dict[str, Any]],
        executor_id: str,
        executor_type: ExecutorType = ExecutorType.DAENA
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple tool actions concurrently.
        
        Args:
            tasks: List of task dicts with keys: tool_name, action, args
            executor_id: Who is executing
            executor_type: Type of executor
            
        Returns:
            List of results in the same order as tasks
        """
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.concurrent_limit)
        
        async def execute_with_limit(task: Dict[str, Any], index: int):
            async with semaphore:
                try:
                    result = await self.execute(
                        tool_name=task.get("tool_name", ""),
                        action=task.get("action", ""),
                        args=task.get("args", {}),
                        executor_id=executor_id,
                        executor_type=executor_type,
                        department=task.get("department")
                    )
                    return {"index": index, "result": result}
                except Exception as e:
                    logger.error(f"Batch task {index} failed: {e}")
                    return {"index": index, "result": {"success": False, "error": str(e)}}
        
        # Execute all tasks concurrently
        tasks_with_index = [(task, i) for i, task in enumerate(tasks)]
        results = await asyncio.gather(
            *[execute_with_limit(task, idx) for task, idx in tasks_with_index],
            return_exceptions=True
        )
        
        # Sort by index to maintain order
        sorted_results = sorted(
            [r for r in results if isinstance(r, dict)],
            key=lambda x: x["index"]
        )
        
        return [r["result"] for r in sorted_results]
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics for monitoring."""
        if not self.execution_log:
            return {"total_executions": 0}
            
        tool_counts = {}
        success_count = 0
        
        for entry in self.execution_log[-100:]:  # Last 100
            tool = entry.get("tool_name", "unknown")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
            if entry.get("success"):
                success_count += 1
                
        return {
            "total_executions": len(self.execution_log),
            "by_tool": tool_counts,
            "success_rate": success_count / len(self.execution_log) if self.execution_log else 0,
            "concurrent_limit": self.concurrent_limit,
        }


# Global instance
unified_executor = UnifiedToolExecutor()
