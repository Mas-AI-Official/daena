"""
Daena Agent Platform - Implementation Framework
Integrates MoltBot and MiniMax capabilities with hierarchical permission control
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
import hashlib
import re


# ============================================================================
# PERMISSION SYSTEM
# ============================================================================

class PermissionLevel(Enum):
    """Permission hierarchy levels"""
    MINIMAL = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


class RiskLevel(Enum):
    """Risk assessment levels"""
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Permission:
    """Individual permission object"""
    category: str  # filesystem, network, system, data, communication, agent_control
    action: str    # read, write, delete, execute, etc.
    scope: Optional[str] = None  # Specific path or resource
    granted_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    granted_by: str = "user"
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def to_dict(self) -> Dict:
        return {
            "category": self.category,
            "action": self.action,
            "scope": self.scope,
            "granted_at": self.granted_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "granted_by": self.granted_by
        }


class PermissionManager:
    """Manages permission granting, checking, and revocation"""
    
    def __init__(self):
        self.permissions: List[Permission] = []
        self.permission_templates: Dict[str, List[Permission]] = {}
        self.audit_log: List[Dict] = []
        
    def grant_permission(
        self,
        category: str,
        action: str,
        scope: Optional[str] = None,
        duration: Optional[int] = None,  # seconds
        granted_by: str = "user"
    ) -> Permission:
        """Grant a new permission"""
        expires_at = None
        if duration:
            expires_at = datetime.now() + timedelta(seconds=duration)
        
        perm = Permission(
            category=category,
            action=action,
            scope=scope,
            expires_at=expires_at,
            granted_by=granted_by
        )
        
        self.permissions.append(perm)
        self.log_permission_change("granted", perm)
        return perm
    
    def has_permission(
        self,
        category: str,
        action: str,
        scope: Optional[str] = None
    ) -> bool:
        """Check if a permission exists and is valid"""
        for perm in self.permissions:
            if perm.is_expired():
                continue
            
            if perm.category == category and perm.action == action:
                if scope and perm.scope:
                    # Check if scope matches (could be path prefix, etc.)
                    if scope.startswith(perm.scope):
                        return True
                elif not scope:
                    return True
        
        return False
    
    def revoke_permission(
        self,
        category: str,
        action: str,
        scope: Optional[str] = None
    ):
        """Revoke a specific permission"""
        self.permissions = [
            p for p in self.permissions
            if not (p.category == category and p.action == action and 
                   (not scope or p.scope == scope))
        ]
        self.log_permission_change("revoked", {
            "category": category,
            "action": action,
            "scope": scope
        })
    
    def cleanup_expired(self):
        """Remove expired permissions"""
        before_count = len(self.permissions)
        self.permissions = [p for p in self.permissions if not p.is_expired()]
        after_count = len(self.permissions)
        
        if before_count > after_count:
            self.log_permission_change("cleanup", {
                "removed": before_count - after_count
            })
    
    def load_template(self, template_name: str) -> List[Permission]:
        """Load a permission template"""
        if template_name not in self.permission_templates:
            raise ValueError(f"Template {template_name} not found")
        
        return self.permission_templates[template_name]
    
    def activate_template(self, template_name: str):
        """Activate all permissions from a template"""
        template_perms = self.load_template(template_name)
        for perm in template_perms:
            self.permissions.append(perm)
        
        self.log_permission_change("template_activated", {
            "template": template_name,
            "count": len(template_perms)
        })
    
    def log_permission_change(self, action: str, data: Any):
        """Log permission changes for audit trail"""
        self.audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "data": data if isinstance(data, dict) else data.to_dict()
        })
    
    def get_all_permissions(self) -> List[Dict]:
        """Get all active permissions"""
        self.cleanup_expired()
        return [p.to_dict() for p in self.permissions]


# ============================================================================
# SAFETY & RISK ASSESSMENT
# ============================================================================

class SafetyMonitor:
    """Monitors operations for safety and risk"""
    
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"sudo\s+.*delete",
        r"DROP\s+DATABASE",
        r"chmod\s+777",
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__",
        # Add more patterns
    ]
    
    RISK_ASSESSMENT_RULES = {
        "filesystem": {
            "read": RiskLevel.MINIMAL,
            "write": RiskLevel.LOW,
            "delete": RiskLevel.MEDIUM,
            "execute": RiskLevel.HIGH,
        },
        "network": {
            "web_search": RiskLevel.MINIMAL,
            "api_access": RiskLevel.LOW,
            "webhook": RiskLevel.MEDIUM,
        },
        "system": {
            "shell_command": RiskLevel.HIGH,
            "process_control": RiskLevel.CRITICAL,
        }
    }
    
    def check_command_safety(self, command: str) -> Dict[str, Any]:
        """Check if a command is safe to execute"""
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    "safe": False,
                    "reason": f"Matches dangerous pattern: {pattern}",
                    "risk_level": RiskLevel.CRITICAL
                }
        
        return {
            "safe": True,
            "risk_level": RiskLevel.LOW
        }
    
    def assess_risk(
        self,
        category: str,
        action: str,
        context: Optional[Dict] = None
    ) -> RiskLevel:
        """Assess the risk level of an action"""
        if category in self.RISK_ASSESSMENT_RULES:
            if action in self.RISK_ASSESSMENT_RULES[category]:
                return self.RISK_ASSESSMENT_RULES[category][action]
        
        # Default to medium risk for unknown actions
        return RiskLevel.MEDIUM


# ============================================================================
# AGENT SYSTEM
# ============================================================================

class AgentStatus(Enum):
    """Agent operational status"""
    IDLE = "idle"
    ACTIVE = "active"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class Task:
    """Task object for agents"""
    task_id: str
    description: str
    required_permissions: List[tuple]  # [(category, action, scope), ...]
    priority: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    assigned_to: Optional[str] = None
    status: str = "pending"
    result: Optional[Any] = None
    
    def to_hash(self) -> str:
        """Generate unique hash for task deduplication"""
        content = f"{self.description}:{self.required_permissions}"
        return hashlib.md5(content.encode()).hexdigest()


class SubAgent:
    """Individual sub-agent with limited permissions"""
    
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        parent_agent: 'DaenaAgent'
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.parent = parent_agent
        self.permissions: List[Permission] = []
        self.status = AgentStatus.IDLE
        self.current_task: Optional[Task] = None
        self.logger = logging.getLogger(f"SubAgent.{agent_id}")
    
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """Execute assigned task with permission checks"""
        self.status = AgentStatus.ACTIVE
        self.current_task = task
        
        try:
            # Check permissions before execution
            for category, action, scope in task.required_permissions:
                if not self.has_permission(category, action, scope):
                    # Request permission from parent
                    granted = await self.request_permission(category, action, scope)
                    if not granted:
                        return {
                            "success": False,
                            "error": "Insufficient permissions",
                            "required": (category, action, scope)
                        }
            
            # Execute task (implement specific logic based on agent_type)
            result = await self._execute_task_logic(task)
            
            self.status = AgentStatus.COMPLETED
            task.status = "completed"
            task.result = result
            
            # Report to parent
            await self.report_to_parent("task_completed", {
                "task_id": task.task_id,
                "result": result
            })
            
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.logger.error(f"Task execution failed: {e}")
            
            await self.report_to_parent("task_error", {
                "task_id": task.task_id,
                "error": str(e)
            })
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_task_logic(self, task: Task) -> Dict[str, Any]:
        """Implement actual task execution (override in subclasses)"""
        # This would be implemented based on agent_type
        # For example: CodeAgent, ResearchAgent, FileAgent, etc.
        
        if self.agent_type == "code_specialist":
            return await self._execute_coding_task(task)
        elif self.agent_type == "research_specialist":
            return await self._execute_research_task(task)
        elif self.agent_type == "file_specialist":
            return await self._execute_file_task(task)
        else:
            return {"success": True, "message": "Task completed"}
    
    async def _execute_coding_task(self, task: Task) -> Dict:
        """Execute coding-related tasks"""
        # Integrate with MiniMax code generation
        return {"success": True, "code_generated": True}
    
    async def _execute_research_task(self, task: Task) -> Dict:
        """Execute research tasks"""
        # Integrate with web search and MCP tools
        return {"success": True, "research_complete": True}
    
    async def _execute_file_task(self, task: Task) -> Dict:
        """Execute file management tasks"""
        # Integrate with filesystem operations
        return {"success": True, "files_processed": True}
    
    def has_permission(
        self,
        category: str,
        action: str,
        scope: Optional[str] = None
    ) -> bool:
        """Check if agent has specific permission"""
        for perm in self.permissions:
            if perm.is_expired():
                continue
            if perm.category == category and perm.action == action:
                if scope and perm.scope:
                    if scope.startswith(perm.scope):
                        return True
                elif not scope:
                    return True
        return False
    
    async def request_permission(
        self,
        category: str,
        action: str,
        scope: Optional[str] = None
    ) -> bool:
        """Request permission from parent agent"""
        return await self.parent.grant_permission_to_subagent(
            agent_id=self.agent_id,
            category=category,
            action=action,
            scope=scope
        )
    
    async def report_to_parent(self, message_type: str, data: Dict):
        """Send message to parent agent"""
        message = {
            "from": self.agent_id,
            "type": message_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self.parent.receive_subagent_message(message)
    
    def terminate(self):
        """Terminate agent and cleanup"""
        self.status = AgentStatus.TERMINATED
        self.permissions.clear()
        self.current_task = None


# ============================================================================
# DAENA - MAIN ORCHESTRATION AGENT
# ============================================================================

class DaenaAgent:
    """Main orchestration agent - VP Interface"""
    
    def __init__(
        self,
        user_id: str,
        config: Optional[Dict] = None
    ):
        self.user_id = user_id
        self.config = config or {}
        
        # Core systems
        self.permission_manager = PermissionManager()
        self.safety_monitor = SafetyMonitor()
        
        # Sub-agents
        self.sub_agents: Dict[str, SubAgent] = {}
        self.agent_counter = 0
        
        # Task management
        self.active_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.task_hashes: set = set()
        
        # Logging
        self.logger = logging.getLogger("DaenaAgent")
        self.audit_log: List[Dict] = []
        
        # Integration modules
        self.moltbot_integration = None
        self.minimax_integration = None
        
    # ------------------------------------------------------------------------
    # Permission Management
    # ------------------------------------------------------------------------
    
    def receive_user_permissions(self, permissions: List[Dict]):
        """Receive initial permissions from user"""
        for perm_dict in permissions:
            self.permission_manager.grant_permission(
                category=perm_dict["category"],
                action=perm_dict["action"],
                scope=perm_dict.get("scope"),
                duration=perm_dict.get("duration"),
                granted_by="user"
            )
        
        self.log_action("permissions_received", {
            "count": len(permissions),
            "from": "user"
        })
    
    async def grant_permission_to_subagent(
        self,
        agent_id: str,
        category: str,
        action: str,
        scope: Optional[str] = None,
        duration: int = 3600  # 1 hour default
    ) -> bool:
        """Delegate permission to sub-agent"""
        
        # Check if Daena has this permission
        if not self.permission_manager.has_permission(category, action, scope):
            # Daena doesn't have permission, request from user
            granted = await self.request_user_permission(
                category=category,
                action=action,
                scope=scope,
                reason=f"Sub-agent {agent_id} requires this permission"
            )
            
            if not granted:
                return False
        
        # Grant to sub-agent with time limit
        if agent_id in self.sub_agents:
            agent = self.sub_agents[agent_id]
            perm = Permission(
                category=category,
                action=action,
                scope=scope,
                expires_at=datetime.now() + timedelta(seconds=duration),
                granted_by=f"daena_to_{agent_id}"
            )
            agent.permissions.append(perm)
            
            self.log_action("permission_delegated", {
                "to": agent_id,
                "permission": perm.to_dict()
            })
            
            return True
        
        return False
    
    async def request_user_permission(
        self,
        category: str,
        action: str,
        scope: Optional[str] = None,
        reason: str = ""
    ) -> bool:
        """Request permission from user"""
        
        # Assess risk
        risk_level = self.safety_monitor.assess_risk(category, action)
        
        # Format request
        request = {
            "category": category,
            "action": action,
            "scope": scope,
            "reason": reason,
            "risk_level": risk_level.value,
            "timestamp": datetime.now().isoformat()
        }
        
        # Log request
        self.log_action("permission_requested", request)
        
        # In real implementation, this would:
        # 1. Send notification to user
        # 2. Wait for user response
        # 3. Process response
        
        # For now, simulate based on risk level
        auto_approve_levels = [RiskLevel.MINIMAL, RiskLevel.LOW]
        
        if risk_level in auto_approve_levels:
            # Auto-approve low-risk actions
            self.permission_manager.grant_permission(
                category=category,
                action=action,
                scope=scope,
                granted_by="user_auto"
            )
            return True
        
        # Higher risk - would need actual user interaction
        # This is where you'd integrate with your UI
        print(f"\n🔐 PERMISSION REQUEST")
        print(f"Action: {category}.{action}")
        print(f"Scope: {scope}")
        print(f"Risk: {risk_level.value}")
        print(f"Reason: {reason}")
        
        # Simulated response
        return True  # In production, wait for actual user input
    
    # ------------------------------------------------------------------------
    # Task Management
    # ------------------------------------------------------------------------
    
    async def execute_task(
        self,
        description: str,
        required_permissions: List[tuple],
        priority: int = 1
    ) -> Dict[str, Any]:
        """Main task execution entry point"""
        
        # Create task
        task = Task(
            task_id=f"task_{len(self.active_tasks) + 1}",
            description=description,
            required_permissions=required_permissions,
            priority=priority
        )
        
        # Check for duplicates
        task_hash = task.to_hash()
        if task_hash in self.task_hashes:
            return {
                "success": False,
                "error": "Duplicate task detected",
                "original_task": "task_id_here"  # Would track actual ID
            }
        
        self.task_hashes.add(task_hash)
        self.active_tasks[task.task_id] = task
        
        # Analyze and decompose task
        subtasks = await self.decompose_task(task)
        
        # Assign to appropriate agents
        results = []
        for subtask in subtasks:
            agent = await self.get_or_create_agent(subtask["agent_type"])
            result = await agent.execute_task(subtask["task"])
            results.append(result)
        
        # Combine results
        final_result = await self.combine_results(results)
        
        # Mark complete
        task.status = "completed"
        task.result = final_result
        self.completed_tasks[task.task_id] = task
        del self.active_tasks[task.task_id]
        
        return final_result
    
    async def decompose_task(self, task: Task) -> List[Dict]:
        """Break down task into subtasks"""
        # This would use LLM reasoning to decompose
        # For now, simple logic based on description
        
        subtasks = []
        
        if "research" in task.description.lower():
            subtasks.append({
                "agent_type": "research_specialist",
                "task": Task(
                    task_id=f"{task.task_id}_research",
                    description=f"Research: {task.description}",
                    required_permissions=[
                        ("network", "web_search", None),
                        ("network", "web_fetch", None)
                    ]
                )
            })
        
        if "code" in task.description.lower():
            subtasks.append({
                "agent_type": "code_specialist",
                "task": Task(
                    task_id=f"{task.task_id}_code",
                    description=f"Code: {task.description}",
                    required_permissions=[
                        ("filesystem", "write", "./workspace"),
                        ("system", "shell_command", None)
                    ]
                )
            })
        
        if "file" in task.description.lower():
            subtasks.append({
                "agent_type": "file_specialist",
                "task": Task(
                    task_id=f"{task.task_id}_file",
                    description=f"File operation: {task.description}",
                    required_permissions=[
                        ("filesystem", "read", None),
                        ("filesystem", "write", None)
                    ]
                )
            })
        
        return subtasks or [{
            "agent_type": "general",
            "task": task
        }]
    
    async def combine_results(self, results: List[Dict]) -> Dict[str, Any]:
        """Combine results from multiple agents"""
        # Simple combination - in production, use LLM to synthesize
        return {
            "success": all(r.get("success", False) for r in results),
            "results": results,
            "combined_at": datetime.now().isoformat()
        }
    
    # ------------------------------------------------------------------------
    # Agent Management
    # ------------------------------------------------------------------------
    
    async def get_or_create_agent(self, agent_type: str) -> SubAgent:
        """Get existing agent or create new one"""
        
        # Check if agent of this type exists and is idle
        for agent_id, agent in self.sub_agents.items():
            if agent.agent_type == agent_type and agent.status == AgentStatus.IDLE:
                return agent
        
        # Create new agent
        self.agent_counter += 1
        agent_id = f"{agent_type}_{self.agent_counter}"
        
        agent = SubAgent(
            agent_id=agent_id,
            agent_type=agent_type,
            parent_agent=self
        )
        
        self.sub_agents[agent_id] = agent
        
        self.log_action("agent_created", {
            "agent_id": agent_id,
            "agent_type": agent_type
        })
        
        return agent
    
    async def receive_subagent_message(self, message: Dict):
        """Process messages from sub-agents"""
        message_type = message["type"]
        data = message["data"]
        
        if message_type == "task_completed":
            self.logger.info(f"Sub-agent completed task: {data['task_id']}")
        
        elif message_type == "task_error":
            self.logger.error(f"Sub-agent error: {data['error']}")
        
        elif message_type == "permission_request":
            # Handle mid-task permission requests
            granted = await self.grant_permission_to_subagent(
                agent_id=message["from"],
                **data
            )
            # Send response back to agent
        
        self.log_action("subagent_message", message)
    
    def terminate_agent(self, agent_id: str):
        """Terminate and cleanup a sub-agent"""
        if agent_id in self.sub_agents:
            agent = self.sub_agents[agent_id]
            agent.terminate()
            del self.sub_agents[agent_id]
            
            self.log_action("agent_terminated", {
                "agent_id": agent_id
            })
    
    def emergency_stop(self):
        """Emergency stop all operations"""
        self.logger.warning("🚨 EMERGENCY STOP INITIATED")
        
        # Terminate all agents
        for agent_id in list(self.sub_agents.keys()):
            self.terminate_agent(agent_id)
        
        # Revoke all delegated permissions
        for agent in self.sub_agents.values():
            agent.permissions.clear()
        
        # Clear active tasks
        self.active_tasks.clear()
        
        self.log_action("emergency_stop", {
            "timestamp": datetime.now().isoformat()
        })
        
        print("✅ All operations halted. System in safe mode.")
    
    # ------------------------------------------------------------------------
    # Integration Methods
    # ------------------------------------------------------------------------
    
    def integrate_moltbot(self, config: Dict):
        """Integrate MoltBot/OpenClaw capabilities"""
        # This would set up WebSocket connection to MoltBot gateway
        # and map MoltBot skills to Daena's permission system
        
        self.moltbot_integration = {
            "gateway_url": config.get("gateway_url"),
            "channels": config.get("channels", []),
            "skills": config.get("skills_enabled", [])
        }
        
        self.log_action("moltbot_integrated", self.moltbot_integration)
    
    def integrate_minimax(self, config: Dict):
        """Integrate MiniMax agent capabilities"""
        # This would set up MiniMax API connection
        # and configure reasoning/planning capabilities
        
        self.minimax_integration = {
            "model": config.get("model"),
            "api_key": config.get("api_key"),
            "reasoning_mode": config.get("reasoning_mode", "ReACT")
        }
        
        self.log_action("minimax_integrated", self.minimax_integration)
    
    # ------------------------------------------------------------------------
    # Logging & Audit
    # ------------------------------------------------------------------------
    
    def log_action(self, action_type: str, data: Any):
        """Log action for audit trail"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action_type,
            "data": data,
            "user_id": self.user_id
        }
        
        self.audit_log.append(log_entry)
        self.logger.info(f"{action_type}: {json.dumps(data, indent=2)}")
    
    def get_audit_log(self, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve audit log"""
        if limit:
            return self.audit_log[-limit:]
        return self.audit_log
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            "active_agents": len(self.sub_agents),
            "agent_details": [
                {
                    "id": aid,
                    "type": agent.agent_type,
                    "status": agent.status.value,
                    "permissions": len(agent.permissions)
                }
                for aid, agent in self.sub_agents.items()
            ],
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "active_permissions": len(self.permission_manager.get_all_permissions()),
            "last_activity": self.audit_log[-1] if self.audit_log else None
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def main():
    """Example usage of Daena system"""
    
    # Initialize Daena
    daena = DaenaAgent(user_id="user_123")
    
    # Grant initial permissions from user
    daena.receive_user_permissions([
        {"category": "filesystem", "action": "read", "scope": "./workspace"},
        {"category": "filesystem", "action": "write", "scope": "./workspace"},
        {"category": "network", "action": "web_search"},
    ])
    
    # Integrate external frameworks
    daena.integrate_moltbot({
        "gateway_url": "ws://127.0.0.1:18789",
        "channels": ["telegram"],
        "skills_enabled": ["filesystem", "browser"]
    })
    
    daena.integrate_minimax({
        "model": "MiniMax-M2.1",
        "api_key": "your_api_key",
        "reasoning_mode": "ReACT"
    })
    
    # Execute a task
    result = await daena.execute_task(
        description="Research latest AI frameworks and create a summary document",
        required_permissions=[
            ("network", "web_search", None),
            ("network", "web_fetch", None),
            ("filesystem", "write", "./workspace")
        ],
        priority=1
    )
    
    print("\nTask Result:")
    print(json.dumps(result, indent=2))
    
    # Check system status
    status = daena.get_system_status()
    print("\nSystem Status:")
    print(json.dumps(status, indent=2))
    
    # View recent audit log
    recent_logs = daena.get_audit_log(limit=5)
    print("\nRecent Activity:")
    for log in recent_logs:
        print(f"  [{log['timestamp']}] {log['action']}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run example
    asyncio.run(main())
