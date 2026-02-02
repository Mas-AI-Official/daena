# Real-Time Collaboration Guide

**Status**: ✅ **PRODUCTION READY**  
**Date**: 2025-01-XX  
**Version**: 1.0.0

## Overview

Daena's Real-Time Collaboration system provides live agent activity tracking, real-time memory updates, collaborative decision-making interfaces, and agent status broadcasting. This enables users to see what agents are doing in real-time and participate in collaborative workflows.

---

## Table of Contents

1. [Features](#features)
2. [WebSocket API](#websocket-api)
3. [REST API](#rest-api)
4. [Activity Types](#activity-types)
5. [Usage Examples](#usage-examples)
6. [Frontend Integration](#frontend-integration)
7. [Best Practices](#best-practices)

---

## Features

### 1. Live Agent Activity Tracking
- Real-time activity feed
- Agent status monitoring (active/idle)
- Activity completion tracking
- Activity history (up to 1000 activities)

### 2. Real-Time Memory Updates
- Memory write notifications
- Memory read notifications
- Memory delete notifications
- Automatic broadcasting to all connected clients

### 3. Collaborative Decision-Making
- Collaboration session management
- Multi-agent collaboration tracking
- Decision point recording
- Session history

### 4. Agent Status Broadcasting
- Real-time status updates (every 2 seconds)
- Active/idle status tracking
- Current activity monitoring
- Collaboration session tracking

---

## WebSocket API

### Connection

**Endpoint**: `ws://localhost:8000/api/v1/collaboration/ws?client_id=YOUR_CLIENT_ID`

**Connection Flow**:
1. Connect to WebSocket endpoint
2. Receive initial state (agent status, active collaborations)
3. Receive real-time updates (activities, memory updates, status changes)
4. Send ping messages to keep connection alive

### Message Types

#### Incoming Messages (Server → Client)

**1. Connection Established**
```json
{
  "type": "connection_established",
  "client_type": "general",
  "timestamp": "2025-01-XXT12:00:00"
}
```

**2. Collaboration State (Initial)**
```json
{
  "type": "collaboration_state",
  "agent_status": {
    "total_agents": 48,
    "active_agents": 12,
    "idle_agents": 36,
    "active_activities": 5,
    "active_collaborations": 2,
    "agents": {
      "agent_1": {
        "status": "active",
        "current_activity": "act_1234567890_agent_1",
        "collaboration_count": 1
      }
    }
  },
  "active_collaborations": [
    {
      "session_id": "collab_1234567890",
      "participants": ["agent_1", "agent_2"],
      "started_at": "2025-01-XXT12:00:00",
      "activity_count": 5,
      "decision_count": 2
    }
  ],
  "timestamp": "2025-01-XXT12:00:00"
}
```

**3. Agent Activity**
```json
{
  "type": "agent_activity",
  "activity": {
    "activity_id": "act_1234567890_agent_1",
    "agent_id": "agent_1",
    "department": "engineering",
    "activity_type": "memory_write",
    "timestamp": 1234567890.0,
    "metadata": {
      "item_id": "item_123",
      "size_bytes": 1024
    },
    "related_agents": ["agent_2"],
    "status": "active"
  },
  "timestamp": "2025-01-XXT12:00:00"
}
```

**4. Activity Completed**
```json
{
  "type": "activity_completed",
  "activity_id": "act_1234567890_agent_1",
  "success": true,
  "timestamp": "2025-01-XXT12:00:00"
}
```

**5. Agent Status Update**
```json
{
  "type": "agent_status_update",
  "timestamp": "2025-01-XXT12:00:00",
  "agents": {
    "agent_1": {
      "status": "active",
      "current_activity": "act_1234567890_agent_1",
      "last_activity": "act_1234567890_agent_1"
    },
    "agent_2": {
      "status": "idle",
      "current_activity": null,
      "last_activity": "act_1234567890_agent_2"
    }
  }
}
```

**6. Memory Update**
```json
{
  "type": "memory_update",
  "update": {
    "operation": "write",
    "item_id": "item_123",
    "agent_id": "agent_1",
    "timestamp": 1234567890.0,
    "metadata": {
      "size_bytes": 1024,
      "compression_ratio": 13.3
    }
  },
  "timestamp": "2025-01-XXT12:00:00"
}
```

**7. Collaboration Started**
```json
{
  "type": "collaboration_started",
  "session": {
    "session_id": "collab_1234567890",
    "participants": ["agent_1", "agent_2"],
    "started_at": "2025-01-XXT12:00:00"
  },
  "timestamp": "2025-01-XXT12:00:00"
}
```

**8. Collaboration Ended**
```json
{
  "type": "collaboration_ended",
  "session_id": "collab_1234567890",
  "timestamp": "2025-01-XXT12:00:00"
}
```

#### Outgoing Messages (Client → Server)

**1. Ping**
```json
{
  "type": "ping"
}
```

**2. Subscribe**
```json
{
  "type": "subscribe",
  "activity_types": ["agent_activity", "memory_update", "agent_status_update"]
}
```

---

## REST API

### Base URL
All endpoints are under `/api/v1/collaboration/`

### Authentication
All endpoints require authentication via `verify_monitoring_auth` (API key or JWT token).

---

### 1. Get Agent Status

**Endpoint**: `GET /api/v1/collaboration/agent-status`

**Response**:
```json
{
  "total_agents": 48,
  "active_agents": 12,
  "idle_agents": 36,
  "active_activities": 5,
  "active_collaborations": 2,
  "agents": {
    "agent_1": {
      "status": "active",
      "current_activity": "act_1234567890_agent_1",
      "collaboration_count": 1
    }
  }
}
```

---

### 2. Get Activity Feed

**Endpoint**: `GET /api/v1/collaboration/activity-feed?agent_id=agent_1&limit=50`

**Parameters**:
- `agent_id` (optional): Filter by agent ID
- `limit` (optional): Maximum number of activities (1-500, default: 50)

**Response**:
```json
{
  "activities": [
    {
      "activity_id": "act_1234567890_agent_1",
      "agent_id": "agent_1",
      "department": "engineering",
      "activity_type": "memory_write",
      "timestamp": 1234567890.0,
      "metadata": {
        "item_id": "item_123"
      },
      "related_agents": ["agent_2"],
      "status": "completed"
    }
  ],
  "total": 50,
  "agent_id": "agent_1"
}
```

---

### 3. Get Active Collaborations

**Endpoint**: `GET /api/v1/collaboration/active-collaborations`

**Response**:
```json
{
  "collaborations": [
    {
      "session_id": "collab_1234567890",
      "participants": ["agent_1", "agent_2"],
      "started_at": "2025-01-XXT12:00:00",
      "activity_count": 5,
      "decision_count": 2
    }
  ],
  "total": 1
}
```

---

### 4. Record Activity

**Endpoint**: `POST /api/v1/collaboration/record-activity`

**Body**:
```json
{
  "agent_id": "agent_1",
  "department": "engineering",
  "activity_type": "memory_write",
  "metadata": {
    "item_id": "item_123",
    "size_bytes": 1024
  },
  "related_agents": ["agent_2"]
}
```

**Response**:
```json
{
  "success": true,
  "activity_id": "act_1234567890_agent_1"
}
```

**Valid Activity Types**:
- `agent_started`
- `agent_completed`
- `memory_write`
- `memory_read`
- `council_debate`
- `council_synthesis`
- `decision_made`
- `task_assigned`
- `task_completed`
- `message_sent`
- `collaboration_started`
- `collaboration_ended`

---

### 5. Complete Activity

**Endpoint**: `POST /api/v1/collaboration/complete-activity`

**Body**:
```json
{
  "activity_id": "act_1234567890_agent_1",
  "success": true
}
```

**Response**:
```json
{
  "success": true,
  "activity_id": "act_1234567890_agent_1"
}
```

---

### 6. Start Collaboration

**Endpoint**: `POST /api/v1/collaboration/start-collaboration`

**Body**:
```json
{
  "participants": ["agent_1", "agent_2"],
  "session_type": "general"
}
```

**Response**:
```json
{
  "success": true,
  "session_id": "collab_1234567890"
}
```

---

### 7. End Collaboration

**Endpoint**: `POST /api/v1/collaboration/end-collaboration`

**Body**:
```json
{
  "session_id": "collab_1234567890"
}
```

**Response**:
```json
{
  "success": true,
  "session_id": "collab_1234567890"
}
```

---

### 8. Record Memory Update

**Endpoint**: `POST /api/v1/collaboration/record-memory-update`

**Body**:
```json
{
  "operation": "write",
  "item_id": "item_123",
  "agent_id": "agent_1",
  "metadata": {
    "size_bytes": 1024,
    "compression_ratio": 13.3
  }
}
```

**Response**:
```json
{
  "success": true
}
```

---

## Activity Types

### Agent Activities
- `agent_started`: Agent started working
- `agent_completed`: Agent completed a task

### Memory Activities
- `memory_write`: Agent wrote to memory
- `memory_read`: Agent read from memory

### Council Activities
- `council_debate`: Agent participated in council debate
- `council_synthesis`: Agent participated in council synthesis
- `decision_made`: Agent made a decision

### Task Activities
- `task_assigned`: Task was assigned to agent
- `task_completed`: Task was completed

### Communication Activities
- `message_sent`: Agent sent a message

### Collaboration Activities
- `collaboration_started`: Collaboration session started
- `collaboration_ended`: Collaboration session ended

---

## Usage Examples

### Python Example

```python
import asyncio
import websockets
import json

async def connect_collaboration():
    uri = "ws://localhost:8000/api/v1/collaboration/ws?client_id=client_1"
    
    async with websockets.connect(uri) as websocket:
        # Receive initial state
        message = await websocket.recv()
        data = json.loads(message)
        print(f"Initial state: {data}")
        
        # Send ping
        await websocket.send(json.dumps({"type": "ping"}))
        
        # Listen for updates
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            
            if data["type"] == "agent_activity":
                print(f"Activity: {data['activity']['activity_type']}")
            elif data["type"] == "memory_update":
                print(f"Memory update: {data['update']['operation']}")
            elif data["type"] == "agent_status_update":
                print(f"Status update: {data['agents']}")

# Run
asyncio.run(connect_collaboration())
```

### JavaScript Example

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/collaboration/ws?client_id=client_1');

ws.onopen = () => {
  console.log('Connected to collaboration WebSocket');
  
  // Send ping
  setInterval(() => {
    ws.send(JSON.stringify({ type: 'ping' }));
  }, 30000); // Every 30 seconds
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'collaboration_state':
      console.log('Initial state:', data);
      break;
    case 'agent_activity':
      console.log('Activity:', data.activity);
      break;
    case 'memory_update':
      console.log('Memory update:', data.update);
      break;
    case 'agent_status_update':
      console.log('Status update:', data.agents);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

### Recording Activities

```python
import requests

# Record an activity
response = requests.post(
    "http://localhost:8000/api/v1/collaboration/record-activity",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "agent_id": "agent_1",
        "department": "engineering",
        "activity_type": "memory_write",
        "metadata": {
            "item_id": "item_123",
            "size_bytes": 1024
        },
        "related_agents": ["agent_2"]
    }
)
print(response.json())

# Complete the activity
response = requests.post(
    "http://localhost:8000/api/v1/collaboration/complete-activity",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "activity_id": response.json()["activity_id"],
        "success": True
    }
)
```

---

## Frontend Integration

### React Example

```jsx
import { useEffect, useState } from 'react';

function CollaborationDashboard() {
  const [activities, setActivities] = useState([]);
  const [agentStatus, setAgentStatus] = useState({});
  const [ws, setWs] = useState(null);

  useEffect(() => {
    const websocket = new WebSocket('ws://localhost:8000/api/v1/collaboration/ws?client_id=client_1');
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'agent_activity':
          setActivities(prev => [data.activity, ...prev].slice(0, 50));
          break;
        case 'agent_status_update':
          setAgentStatus(data.agents);
          break;
      }
    };
    
    setWs(websocket);
    
    return () => {
      websocket.close();
    };
  }, []);

  return (
    <div>
      <h2>Agent Activities</h2>
      <ul>
        {activities.map(activity => (
          <li key={activity.activity_id}>
            {activity.agent_id}: {activity.activity_type}
          </li>
        ))}
      </ul>
      
      <h2>Agent Status</h2>
      <ul>
        {Object.entries(agentStatus).map(([agentId, status]) => (
          <li key={agentId}>
            {agentId}: {status.status}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Best Practices

1. **Connection Management**: Always handle reconnection logic
2. **Ping/Pong**: Send ping messages every 30 seconds to keep connection alive
3. **Error Handling**: Handle WebSocket errors gracefully
4. **Rate Limiting**: Don't record activities too frequently (max 10/second per agent)
5. **Activity Cleanup**: Complete activities when done to avoid memory leaks
6. **Subscription Management**: Subscribe only to needed activity types

---

## Integration with Existing Systems

### Memory Service Integration

To automatically broadcast memory updates:

```python
from backend.services.realtime_collaboration import realtime_collaboration_service

# In memory router after write
realtime_collaboration_service.record_memory_update(
    operation="write",
    item_id=item_id,
    agent_id=agent_id,
    metadata={"size_bytes": size_bytes}
)
```

### Council Service Integration

To track council activities:

```python
from backend.services.realtime_collaboration import realtime_collaboration_service, ActivityType

# When council debate starts
activity_id = realtime_collaboration_service.record_activity(
    agent_id=agent_id,
    department=department,
    activity_type=ActivityType.COUNCIL_DEBATE,
    metadata={"topic": topic, "round": round_number}
)

# When debate completes
realtime_collaboration_service.complete_activity(activity_id, success=True)
```

---

## Related Documentation

- `docs/ADVANCED_ANALYTICS.md` - Analytics features
- `docs/MONITORING_GUIDE.md` - Monitoring setup
- `backend/services/websocket_service.py` - WebSocket manager

---

**Status**: ✅ **PRODUCTION READY**  
**Last Updated**: 2025-01-XX

