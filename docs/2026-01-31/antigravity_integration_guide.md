# Antigravity Integration Guide for Daena
## Step-by-Step Integration with Your Existing Platform

---

## Prerequisites

Before integrating, ensure you have:
1. Antigravity platform codebase
2. Python 3.8+ environment
3. Access to MoltBot/OpenClaw (optional but recommended)
4. MiniMax API key (optional but recommended)

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Antigravity UI                       │
│              (Your Existing Interface)                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│               Antigravity Core                          │
│         (Your Existing Business Logic)                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Daena Integration Layer                    │
│         (Bridge between Antigravity & Daena)            │
└────────────────────┬────────────────────────────────────┘
                     │
          ┌──────────┴──────────┬──────────────┐
          ▼                     ▼              ▼
┌─────────────────┐   ┌─────────────┐   ┌──────────────┐
│  Daena Agent    │   │  MoltBot    │   │  MiniMax     │
│  (Orchestrator) │   │  Integration│   │  Integration │
└─────────────────┘   └─────────────┘   └──────────────┘
          │                     │              │
          └──────────┬──────────┴──────────────┘
                     ▼
          ┌─────────────────────┐
          │   Sub-Agents        │
          │  (Specialists)      │
          └─────────────────────┘
```

---

## Step 1: Install Daena Module

### Option A: As a Package

```bash
# In your Antigravity project directory
pip install -e /path/to/daena_module

# Or if you've published it
pip install daena-agent
```

### Option B: Direct Integration

Copy the Daena implementation files into your Antigravity project:

```bash
mkdir -p antigravity/agents/daena
cp daena_implementation.py antigravity/agents/daena/core.py
```

---

## Step 2: Create Antigravity-Daena Adapter

Create `antigravity/agents/daena/adapter.py`:

```python
"""
Antigravity-Daena Integration Adapter
Bridges Antigravity's existing systems with Daena's agent framework
"""

from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime

# Import Antigravity's existing modules
from antigravity.core import AntigravityCore
from antigravity.permissions import PermissionSystem as AntigravityPermissions
from antigravity.users import UserManager
from antigravity.events import EventBus

# Import Daena
from .core import DaenaAgent, PermissionManager, Task


class AntigravityDaenaAdapter:
    """
    Adapter that integrates Daena into Antigravity platform
    Handles translation between Antigravity's patterns and Daena's requirements
    """
    
    def __init__(
        self,
        antigravity_core: AntigravityCore,
        user_manager: UserManager,
        event_bus: EventBus
    ):
        self.ag_core = antigravity_core
        self.user_manager = user_manager
        self.event_bus = event_bus
        
        # User-specific Daena instances
        self.daena_instances: Dict[str, DaenaAgent] = {}
        
        # Permission mapping
        self.permission_mapper = self._create_permission_mapper()
        
        # Event handlers
        self._setup_event_handlers()
    
    # ------------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------------
    
    def _create_permission_mapper(self) -> Dict[str, Dict]:
        """
        Map Antigravity permission levels to Daena permissions
        Adjust these mappings based on your actual Antigravity permission system
        """
        return {
            "antigravity_read": {
                "daena_category": "filesystem",
                "daena_action": "read",
                "risk_level": "minimal"
            },
            "antigravity_write": {
                "daena_category": "filesystem",
                "daena_action": "write",
                "risk_level": "low"
            },
            "antigravity_execute": {
                "daena_category": "system",
                "daena_action": "shell_command",
                "risk_level": "high"
            },
            "antigravity_network": {
                "daena_category": "network",
                "daena_action": "api_access",
                "risk_level": "medium"
            },
            "antigravity_admin": {
                "daena_category": "agent_control",
                "daena_action": "spawn_sub_agents",
                "risk_level": "high"
            }
        }
    
    def _setup_event_handlers(self):
        """Register Antigravity event handlers for Daena integration"""
        
        # Listen for user actions that should trigger Daena
        self.event_bus.on("user.command", self.handle_user_command)
        self.event_bus.on("user.login", self.initialize_daena_for_user)
        self.event_bus.on("user.logout", self.cleanup_daena_for_user)
        
        # Listen for permission changes
        self.event_bus.on("permissions.updated", self.sync_permissions_to_daena)
    
    # ------------------------------------------------------------------------
    # User Management
    # ------------------------------------------------------------------------
    
    async def initialize_daena_for_user(self, event: Dict):
        """Initialize Daena instance when user logs in"""
        user_id = event["user_id"]
        
        if user_id in self.daena_instances:
            return  # Already initialized
        
        # Create Daena instance for user
        daena = DaenaAgent(
            user_id=user_id,
            config=self._get_user_config(user_id)
        )
        
        # Sync initial permissions from Antigravity to Daena
        ag_permissions = self.ag_core.get_user_permissions(user_id)
        daena_permissions = self._convert_permissions(ag_permissions)
        daena.receive_user_permissions(daena_permissions)
        
        # Configure integrations if enabled
        user_settings = self.user_manager.get_settings(user_id)
        
        if user_settings.get("moltbot_enabled"):
            daena.integrate_moltbot(user_settings.get("moltbot_config", {}))
        
        if user_settings.get("minimax_enabled"):
            daena.integrate_minimax(user_settings.get("minimax_config", {}))
        
        self.daena_instances[user_id] = daena
        
        # Emit event
        self.event_bus.emit("daena.initialized", {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def cleanup_daena_for_user(self, event: Dict):
        """Cleanup Daena instance when user logs out"""
        user_id = event["user_id"]
        
        if user_id in self.daena_instances:
            daena = self.daena_instances[user_id]
            
            # Emergency stop all operations
            daena.emergency_stop()
            
            # Save state if needed
            self._save_daena_state(user_id, daena)
            
            # Remove instance
            del self.daena_instances[user_id]
            
            self.event_bus.emit("daena.cleaned_up", {
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            })
    
    def _get_user_config(self, user_id: str) -> Dict:
        """Load user-specific Daena configuration"""
        settings = self.user_manager.get_settings(user_id)
        
        return {
            "risk_tolerance": settings.get("daena_risk_tolerance", "medium"),
            "auto_approve_low_risk": settings.get("daena_auto_approve", True),
            "max_concurrent_agents": settings.get("daena_max_agents", 5)
        }
    
    # ------------------------------------------------------------------------
    # Permission Management
    # ------------------------------------------------------------------------
    
    def _convert_permissions(
        self,
        ag_permissions: List[Dict]
    ) -> List[Dict]:
        """Convert Antigravity permissions to Daena format"""
        daena_permissions = []
        
        for ag_perm in ag_permissions:
            perm_type = ag_perm["type"]
            
            if perm_type in self.permission_mapper:
                mapping = self.permission_mapper[perm_type]
                daena_permissions.append({
                    "category": mapping["daena_category"],
                    "action": mapping["daena_action"],
                    "scope": ag_perm.get("scope"),
                    "duration": ag_perm.get("duration")
                })
        
        return daena_permissions
    
    async def sync_permissions_to_daena(self, event: Dict):
        """Sync permission changes from Antigravity to Daena"""
        user_id = event["user_id"]
        
        if user_id not in self.daena_instances:
            return
        
        daena = self.daena_instances[user_id]
        
        # Get updated permissions
        ag_permissions = self.ag_core.get_user_permissions(user_id)
        daena_permissions = self._convert_permissions(ag_permissions)
        
        # Update Daena's permissions
        daena.permission_manager.permissions.clear()
        daena.receive_user_permissions(daena_permissions)
    
    # ------------------------------------------------------------------------
    # Command Handling
    # ------------------------------------------------------------------------
    
    async def handle_user_command(self, event: Dict):
        """
        Handle user commands that should be processed by Daena
        This is the main entry point for Antigravity -> Daena communication
        """
        user_id = event["user_id"]
        command = event["command"]
        context = event.get("context", {})
        
        # Ensure Daena is initialized
        if user_id not in self.daena_instances:
            await self.initialize_daena_for_user({"user_id": user_id})
        
        daena = self.daena_instances[user_id]
        
        # Analyze command to determine if Daena should handle it
        if self._should_daena_handle(command):
            result = await self._process_with_daena(
                user_id=user_id,
                command=command,
                context=context
            )
            
            # Emit result back to Antigravity
            self.event_bus.emit("daena.command_completed", {
                "user_id": user_id,
                "command": command,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
            
            return result
        else:
            # Let Antigravity handle it normally
            return None
    
    def _should_daena_handle(self, command: str) -> bool:
        """
        Determine if command should be handled by Daena
        You can customize this logic based on your needs
        """
        daena_keywords = [
            "agent", "automate", "research", "code", "analyze",
            "create", "build", "generate", "organize", "manage"
        ]
        
        command_lower = command.lower()
        return any(keyword in command_lower for keyword in daena_keywords)
    
    async def _process_with_daena(
        self,
        user_id: str,
        command: str,
        context: Dict
    ) -> Dict[str, Any]:
        """Process command using Daena"""
        daena = self.daena_instances[user_id]
        
        # Parse command to extract requirements
        task_description, permissions = self._parse_command(command, context)
        
        # Execute through Daena
        result = await daena.execute_task(
            description=task_description,
            required_permissions=permissions,
            priority=context.get("priority", 1)
        )
        
        # Format result for Antigravity
        return self._format_result_for_antigravity(result)
    
    def _parse_command(
        self,
        command: str,
        context: Dict
    ) -> tuple[str, List[tuple]]:
        """
        Parse command to extract task description and required permissions
        This is a simplified version - you'd want more sophisticated parsing
        """
        
        # Default permissions based on command keywords
        permissions = []
        
        if "research" in command.lower() or "search" in command.lower():
            permissions.extend([
                ("network", "web_search", None),
                ("network", "web_fetch", None)
            ])
        
        if "code" in command.lower() or "script" in command.lower():
            permissions.extend([
                ("filesystem", "write", "./workspace"),
                ("system", "shell_command", None)
            ])
        
        if "file" in command.lower() or "document" in command.lower():
            permissions.extend([
                ("filesystem", "read", None),
                ("filesystem", "write", None)
            ])
        
        # Default fallback
        if not permissions:
            permissions = [
                ("filesystem", "read", None),
                ("network", "web_search", None)
            ]
        
        return command, permissions
    
    def _format_result_for_antigravity(self, daena_result: Dict) -> Dict:
        """Format Daena result for Antigravity consumption"""
        return {
            "success": daena_result.get("success", False),
            "data": daena_result.get("results", []),
            "metadata": {
                "processed_by": "daena",
                "timestamp": daena_result.get("combined_at"),
                "agents_used": len(daena_result.get("results", []))
            }
        }
    
    # ------------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------------
    
    def _save_daena_state(self, user_id: str, daena: DaenaAgent):
        """Save Daena state for user (for session recovery)"""
        state = {
            "audit_log": daena.get_audit_log(),
            "completed_tasks": list(daena.completed_tasks.keys()),
            "permissions": daena.permission_manager.get_all_permissions()
        }
        
        # Save to Antigravity's database or file system
        self.ag_core.save_user_data(
            user_id=user_id,
            key="daena_state",
            value=state
        )
    
    # ------------------------------------------------------------------------
    # API Methods for Antigravity
    # ------------------------------------------------------------------------
    
    def get_daena_status(self, user_id: str) -> Optional[Dict]:
        """Get Daena system status for a user"""
        if user_id not in self.daena_instances:
            return None
        
        daena = self.daena_instances[user_id]
        return daena.get_system_status()
    
    async def emergency_stop_user_agents(self, user_id: str):
        """Emergency stop all Daena agents for a user"""
        if user_id in self.daena_instances:
            daena = self.daena_instances[user_id]
            daena.emergency_stop()
            
            self.event_bus.emit("daena.emergency_stop", {
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            })
    
    def get_audit_log(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get Daena audit log for a user"""
        if user_id not in self.daena_instances:
            return []
        
        daena = self.daena_instances[user_id]
        return daena.get_audit_log(limit=limit)


# ============================================================================
# Usage in Antigravity
# ============================================================================

class AntigravityWithDaena:
    """
    Example of how to use the adapter in your Antigravity application
    """
    
    def __init__(self):
        # Your existing Antigravity components
        self.core = AntigravityCore()
        self.user_manager = UserManager()
        self.event_bus = EventBus()
        
        # Initialize Daena adapter
        self.daena_adapter = AntigravityDaenaAdapter(
            antigravity_core=self.core,
            user_manager=self.user_manager,
            event_bus=self.event_bus
        )
    
    async def process_user_request(
        self,
        user_id: str,
        request: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Main request processing method
        Automatically routes to Daena when appropriate
        """
        
        # Emit command event
        self.event_bus.emit("user.command", {
            "user_id": user_id,
            "command": request,
            "context": context or {}
        })
        
        # The adapter's event handler will process this
        # Wait for result
        result = await self._wait_for_result(user_id, request)
        
        return result
    
    async def _wait_for_result(self, user_id: str, request: str) -> Dict:
        """Wait for command result (implement based on your event system)"""
        # This is a placeholder - implement based on your actual event system
        return {"success": True, "message": "Processed by Daena"}


# ============================================================================
# Configuration Template
# ============================================================================

"""
Add this to your Antigravity configuration file (e.g., config.yaml):

daena:
  enabled: true
  
  # Default settings for all users
  defaults:
    risk_tolerance: medium
    auto_approve_low_risk: true
    max_concurrent_agents: 5
  
  # Integration settings
  integrations:
    moltbot:
      enabled: false  # Enable per-user
      gateway_url: "ws://127.0.0.1:18789"
      default_channels: ["telegram"]
    
    minimax:
      enabled: false  # Enable per-user
      model: "MiniMax-M2.1"
      api_base: "https://api.minimax.io"
  
  # Permission mapping
  permission_mapping:
    antigravity_read: 
      category: filesystem
      action: read
      risk: minimal
    
    antigravity_write:
      category: filesystem
      action: write
      risk: low
    
    antigravity_execute:
      category: system
      action: shell_command
      risk: high
  
  # Safety settings
  safety:
    dangerous_pattern_detection: true
    max_file_size: "1GB"
    max_api_calls_per_hour: 1000
"""
```

---

## Step 3: Update Antigravity Initialization

Modify your main Antigravity initialization (e.g., `antigravity/app.py`):

```python
from antigravity.agents.daena.adapter import AntigravityDaenaAdapter

class AntigravityApp:
    def __init__(self):
        # ... existing initialization ...
        
        # Initialize Daena adapter
        self.daena = AntigravityDaenaAdapter(
            antigravity_core=self.core,
            user_manager=self.user_manager,
            event_bus=self.event_bus
        )
        
        self.logger.info("Daena integration initialized")
    
    async def startup(self):
        # ... existing startup logic ...
        
        # Initialize Daena for existing logged-in users
        for user in self.get_active_users():
            await self.daena.initialize_daena_for_user({
                "user_id": user.id
            })
```

---

## Step 4: Add UI Controls

Add Daena controls to your Antigravity UI:

### Dashboard Widget

```javascript
// antigravity_ui/components/DaenaDashboard.jsx

import React, { useState, useEffect } from 'react';

export const DaenaDashboard = ({ userId }) => {
  const [status, setStatus] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  
  useEffect(() => {
    // Fetch Daena status
    fetch(`/api/daena/status/${userId}`)
      .then(res => res.json())
      .then(data => setStatus(data));
    
    // Fetch audit log
    fetch(`/api/daena/audit/${userId}?limit=10`)
      .then(res => res.json())
      .then(data => setAuditLog(data));
  }, [userId]);
  
  const handleEmergencyStop = () => {
    fetch(`/api/daena/emergency-stop/${userId}`, {
      method: 'POST'
    });
  };
  
  return (
    <div className="daena-dashboard">
      <h2>Daena Agent System</h2>
      
      {status && (
        <div className="status">
          <p>Active Agents: {status.active_agents}</p>
          <p>Active Tasks: {status.active_tasks}</p>
          <p>Completed Tasks: {status.completed_tasks}</p>
          
          <div className="agents">
            {status.agent_details.map(agent => (
              <div key={agent.id} className="agent-card">
                <h4>{agent.type}</h4>
                <p>Status: {agent.status}</p>
                <p>Permissions: {agent.permissions}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      
      <button onClick={handleEmergencyStop} className="emergency-stop">
        🚨 Emergency Stop
      </button>
      
      <div className="audit-log">
        <h3>Recent Activity</h3>
        {auditLog.map((log, idx) => (
          <div key={idx} className="log-entry">
            <span className="timestamp">{log.timestamp}</span>
            <span className="action">{log.action}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
```

### Permission Manager

```javascript
// antigravity_ui/components/PermissionManager.jsx

export const PermissionManager = ({ userId }) => {
  const [templates, setTemplates] = useState([]);
  const [activePermissions, setActivePermissions] = useState([]);
  
  const activateTemplate = (templateName) => {
    fetch(`/api/daena/permissions/activate-template/${userId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template: templateName })
    });
  };
  
  return (
    <div className="permission-manager">
      <h3>Permission Templates</h3>
      {templates.map(template => (
        <button
          key={template.name}
          onClick={() => activateTemplate(template.name)}
        >
          {template.name}
        </button>
      ))}
      
      <h3>Active Permissions</h3>
      <ul>
        {activePermissions.map((perm, idx) => (
          <li key={idx}>
            {perm.category}.{perm.action}
            {perm.scope && ` (${perm.scope})`}
          </li>
        ))}
      </ul>
    </div>
  );
};
```

---

## Step 5: Add API Endpoints

Add Daena API endpoints to your Antigravity backend:

```python
# antigravity/api/daena_routes.py

from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/api/daena", tags=["daena"])

@router.get("/status/{user_id}")
async def get_daena_status(user_id: str):
    """Get Daena system status for user"""
    status = app.daena.get_daena_status(user_id)
    if not status:
        raise HTTPException(404, "Daena not initialized for user")
    return status

@router.get("/audit/{user_id}")
async def get_audit_log(user_id: str, limit: Optional[int] = 10):
    """Get audit log for user"""
    log = app.daena.get_audit_log(user_id, limit=limit)
    return log

@router.post("/emergency-stop/{user_id}")
async def emergency_stop(user_id: str):
    """Emergency stop all agents for user"""
    await app.daena.emergency_stop_user_agents(user_id)
    return {"success": True, "message": "All agents stopped"}

@router.post("/permissions/activate-template/{user_id}")
async def activate_template(user_id: str, template: dict):
    """Activate permission template"""
    # Implementation depends on your permission system
    return {"success": True}
```

---

## Step 6: Testing

Create test script:

```python
# tests/test_daena_integration.py

import asyncio
import pytest
from antigravity.agents.daena.adapter import AntigravityDaenaAdapter

@pytest.mark.asyncio
async def test_daena_initialization():
    """Test Daena initializes correctly"""
    adapter = AntigravityDaenaAdapter(mock_core, mock_user_manager, mock_event_bus)
    
    await adapter.initialize_daena_for_user({"user_id": "test_user"})
    
    assert "test_user" in adapter.daena_instances

@pytest.mark.asyncio
async def test_command_processing():
    """Test command is processed by Daena"""
    adapter = AntigravityDaenaAdapter(mock_core, mock_user_manager, mock_event_bus)
    
    result = await adapter.handle_user_command({
        "user_id": "test_user",
        "command": "Research AI frameworks and create a report"
    })
    
    assert result["success"] == True

@pytest.mark.asyncio
async def test_permission_sync():
    """Test permissions sync correctly"""
    # Test implementation
    pass
```

---

## Step 7: Deployment

### Production Checklist

- [ ] Environment variables set
- [ ] Database migrations run (if needed)
- [ ] Permission templates configured
- [ ] MoltBot/MiniMax credentials added (if using)
- [ ] Audit logging enabled
- [ ] Emergency stop tested
- [ ] User documentation updated

### Environment Variables

```bash
# .env
DAENA_ENABLED=true
DAENA_RISK_TOLERANCE=medium
DAENA_AUTO_APPROVE=true
DAENA_MAX_AGENTS=5

# Optional integrations
MOLTBOT_GATEWAY_URL=ws://127.0.0.1:18789
MINIMAX_API_KEY=your_api_key_here
MINIMAX_MODEL=MiniMax-M2.1
```

---

## Troubleshooting

### Issue: Daena not initializing

**Check:**
1. Event bus is connected
2. User permissions are being passed correctly
3. Check logs: `tail -f logs/daena.log`

### Issue: Permission conflicts

**Solution:**
Review permission mapping in adapter:
```python
self.permission_mapper = self._create_permission_mapper()
```

### Issue: Commands not being routed to Daena

**Check:**
```python
def _should_daena_handle(self, command: str) -> bool:
    # Verify your keywords are triggering correctly
    pass
```

---

## Next Steps

1. **Customize for your needs**: Adjust permission mappings, command parsing, etc.
2. **Add more integrations**: MoltBot skills, MiniMax tools, etc.
3. **Enhance UI**: Add more controls, visualizations, etc.
4. **Monitor performance**: Set up metrics and logging
5. **Iterate**: Gather user feedback and improve

---

## Support

For issues or questions:
1. Check logs in `logs/daena.log`
2. Review audit trail
3. Test with `python -m pytest tests/test_daena_integration.py`

---

You now have Daena fully integrated into your Antigravity platform with hierarchical permission control and all the capabilities of MoltBot and MiniMax agents!
