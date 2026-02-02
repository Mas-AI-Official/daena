# Daena API Usage Examples

**Status**: ✅ **PRODUCTION READY**  
**Date**: 2025-01-XX  
**API Version**: 2.0.0

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [System Endpoints](#system-endpoints)
4. [Agent Management](#agent-management)
5. [Daena Chat](#daena-chat)
6. [Memory & NBMF](#memory--nbmf)
7. [Monitoring](#monitoring)
8. [Council System](#council-system)
9. [Error Handling](#error-handling)
10. [Rate Limiting](#rate-limiting)

---

## Quick Start

### Base URL

- **Production**: `https://daena.mas-ai.co`
- **Local Development**: `http://localhost:8000`

### API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

### Example: Health Check

```bash
# cURL
curl http://localhost:8000/api/v1/system/health

# Python
import requests
response = requests.get("http://localhost:8000/api/v1/system/health")
print(response.json())

# JavaScript
fetch('http://localhost:8000/api/v1/system/health')
  .then(res => res.json())
  .then(data => console.log(data));
```

---

## Authentication

Most endpoints require authentication via API key or Bearer token.

### API Key Authentication

```bash
# cURL
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/monitoring/metrics
```

```python
# Python
import requests

headers = {
    "X-API-Key": "your-api-key"
}

response = requests.get(
    "http://localhost:8000/api/v1/monitoring/metrics",
    headers=headers
)
```

```javascript
// JavaScript
fetch('http://localhost:8000/api/v1/monitoring/metrics', {
  headers: {
    'X-API-Key': 'your-api-key'
  }
})
  .then(res => res.json())
  .then(data => console.log(data));
```

### Bearer Token Authentication

```bash
# cURL
curl -H "Authorization: Bearer your-token" \
  http://localhost:8000/api/v1/agents
```

```python
# Python
headers = {
    "Authorization": "Bearer your-token"
}
response = requests.get("http://localhost:8000/api/v1/agents", headers=headers)
```

```javascript
// JavaScript
fetch('http://localhost:8000/api/v1/agents', {
  headers: {
    'Authorization': 'Bearer your-token'
  }
})
```

---

## System Endpoints

### Health Check

Get system health status.

**Endpoint**: `GET /api/v1/system/health`

```bash
# cURL
curl http://localhost:8000/api/v1/system/health
```

```python
# Python
import requests

response = requests.get("http://localhost:8000/api/v1/system/health")
data = response.json()

print(f"Status: {data['status']}")
print(f"Version: {data['version']}")
print(f"Uptime: {data['system']['uptime']}")
```

```javascript
// JavaScript
async function checkHealth() {
  const response = await fetch('http://localhost:8000/api/v1/system/health');
  const data = await response.json();
  console.log('Status:', data.status);
  console.log('Version:', data.version);
  console.log('Uptime:', data.system.uptime);
}
```

**Response**:
```json
{
  "status": "healthy",
  "message": "Daena AI VP System is running",
  "timestamp": "2025-01-XXT12:00:00",
  "version": "2.0.0",
  "system": {
    "departments": 8,
    "total_agents": 48,
    "active_agents": 48,
    "projects": 12,
    "uptime": "99.7%"
  }
}
```

### System Summary

Get comprehensive system summary.

**Endpoint**: `GET /api/v1/system/summary`

```bash
# cURL
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/system/summary
```

```python
# Python
headers = {"X-API-Key": "your-api-key"}
response = requests.get(
    "http://localhost:8000/api/v1/system/summary",
    headers=headers
)
summary = response.json()
```

### System Metrics

Get system metrics.

**Endpoint**: `GET /api/v1/system/metrics`

```python
# Python
response = requests.get("http://localhost:8000/api/v1/system/metrics")
metrics = response.json()

print(f"Agents: {metrics['agents']}")
print(f"Efficiency: {metrics['efficiency']}%")
print(f"Uptime: {metrics['uptime']}%")
```

---

## Agent Management

### Get All Agents

**Endpoint**: `GET /api/v1/agents`

**Query Parameters**:
- `limit` (int, default: 100): Maximum number of agents
- `offset` (int, default: 0): Pagination offset
- `department_id` (string, optional): Filter by department
- `include_adjacency` (bool, default: false): Include adjacency info

```bash
# cURL - Get all agents
curl http://localhost:8000/api/v1/agents

# cURL - Filter by department
curl "http://localhost:8000/api/v1/agents?department_id=ai&limit=10"

# cURL - With adjacency
curl "http://localhost:8000/api/v1/agents?include_adjacency=true"
```

```python
# Python - Get all agents
response = requests.get("http://localhost:8000/api/v1/agents")
agents_data = response.json()

print(f"Total agents: {agents_data['total_count']}")
for agent in agents_data['agents']:
    print(f"- {agent['name']} ({agent['department_name']})")

# Python - Filter by department
params = {
    "department_id": "ai",
    "limit": 10
}
response = requests.get(
    "http://localhost:8000/api/v1/agents",
    params=params
)
```

```javascript
// JavaScript
async function getAgents(departmentId = null) {
  const url = new URL('http://localhost:8000/api/v1/agents');
  if (departmentId) {
    url.searchParams.append('department_id', departmentId);
  }
  
  const response = await fetch(url);
  const data = await response.json();
  return data.agents;
}
```

**Response**:
```json
{
  "success": true,
  "agents": [
    {
      "agent_id": "agent_001",
      "name": "AI Strategist",
      "department_id": "ai",
      "department_name": "AI Department",
      "role": "strategist",
      "status": "active"
    }
  ],
  "total_count": 48,
  "limit": 100,
  "offset": 0
}
```

### Get Agent by ID

**Endpoint**: `GET /api/v1/agents/{agent_id}`

```python
# Python
agent_id = "agent_001"
response = requests.get(f"http://localhost:8000/api/v1/agents/{agent_id}")
agent = response.json()
```

### Get Agent Metrics

**Endpoint**: `GET /api/v1/monitoring/agent-metrics`

```python
# Python
headers = {"X-API-Key": "your-api-key"}
response = requests.get(
    "http://localhost:8000/api/v1/monitoring/agent-metrics",
    headers=headers
)
metrics = response.json()

for agent_id, agent_metrics in metrics.items():
    print(f"{agent_id}: {agent_metrics['tasks_completed']} tasks")
```

---

## Daena Chat

### Get Daena Status

**Endpoint**: `GET /api/v1/daena/status`

```python
# Python
response = requests.get("http://localhost:8000/api/v1/daena/status")
status = response.json()

print(f"Status: {status['daena_status']}")
print(f"Capabilities: {status['capabilities']}")
```

### Start Chat Session

**Endpoint**: `POST /api/v1/daena/chat/start`

```python
# Python
response = requests.post(
    "http://localhost:8000/api/v1/daena/chat/start",
    json={"user_id": "user_123"}
)
session = response.json()
session_id = session["session_id"]
```

### Send Message

**Endpoint**: `POST /api/v1/daena/chat/message`

```python
# Python
session_id = "session_123"
message_data = {
    "session_id": session_id,
    "message": "What are the current priorities?",
    "context": {}
}

response = requests.post(
    "http://localhost:8000/api/v1/daena/chat/message",
    json=message_data
)
response_data = response.json()
print(response_data["response"])
```

### WebSocket Chat

**Endpoint**: `WS /ws/chat`

```python
# Python (using websockets library)
import asyncio
import websockets
import json

async def chat_with_daena():
    uri = "ws://localhost:8000/ws/chat"
    async with websockets.connect(uri) as websocket:
        # Send message
        message = {
            "type": "user_message",
            "content": "Hello Daena!"
        }
        await websocket.send(json.dumps(message))
        
        # Receive response
        response = await websocket.recv()
        data = json.loads(response)
        print(f"Daena: {data['content']}")

asyncio.run(chat_with_daena())
```

```javascript
// JavaScript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'user_message',
    content: 'Hello Daena!'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Daena:', data.content);
};
```

---

## Memory & NBMF

### Get Memory Metrics

**Endpoint**: `GET /api/v1/monitoring/memory`

```python
# Python
headers = {"X-API-Key": "your-api-key"}
response = requests.get(
    "http://localhost:8000/api/v1/monitoring/memory",
    headers=headers
)
memory_data = response.json()

print(f"L1 Hits: {memory_data.get('l1_hits', 0)}")
print(f"NBMF Reads: {memory_data.get('nbmf_reads', 0)}")
print(f"CAS Hit Rate: {memory_data.get('llm_cas_hit_rate', 0):.2%}")
```

### Get Memory Stats

**Endpoint**: `GET /api/v1/monitoring/memory/stats`

```python
# Python
headers = {"X-API-Key": "your-api-key"}
response = requests.get(
    "http://localhost:8000/api/v1/monitoring/memory/stats",
    headers=headers
)
stats = response.json()
```

### Get Memory Insights

**Endpoint**: `GET /api/v1/monitoring/memory/insights`

```python
# Python
headers = {"X-API-Key": "your-api-key"}
params = {"limit": 20}
response = requests.get(
    "http://localhost:8000/api/v1/monitoring/memory/insights",
    headers=headers,
    params=params
)
insights = response.json()
```

### Prometheus Metrics

**Endpoint**: `GET /api/v1/monitoring/memory/prometheus`

```bash
# cURL
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/monitoring/memory/prometheus
```

---

## Monitoring

### System Metrics

**Endpoint**: `GET /api/v1/monitoring/metrics`

```python
# Python
headers = {"X-API-Key": "your-api-key"}
response = requests.get(
    "http://localhost:8000/api/v1/monitoring/metrics",
    headers=headers
)
metrics = response.json()

print(f"CPU: {metrics['cpu_usage']}%")
print(f"Memory: {metrics['memory_usage']}%")
print(f"Disk: {metrics['disk_usage']}%")
```

### Cost Tracking

**Endpoint**: `GET /api/v1/monitoring/memory/cost-tracking`

```python
# Python
headers = {"X-API-Key": "your-api-key"}
response = requests.get(
    "http://localhost:8000/api/v1/monitoring/memory/cost-tracking",
    headers=headers
)
costs = response.json()

print(f"Total Cost: ${costs['total_cost_usd']:.2f}")
print(f"Savings: ${costs['estimated_savings_usd']:.2f}")
print(f"Savings %: {costs['cost_savings_percentage']:.1f}%")
```

### CAS Diagnostics

**Endpoint**: `GET /api/v1/monitoring/memory/cas`

```python
# Python
headers = {"X-API-Key": "your-api-key"}
response = requests.get(
    "http://localhost:8000/api/v1/monitoring/memory/cas",
    headers=headers
)
cas_data = response.json()

print(f"Hit Rate: {cas_data['metrics']['hit_rate']:.2%}")
print(f"Exact Match: {cas_data['metrics']['exact_match_rate']:.2%}")
```

---

## Council System

### Run Council Debate

**Endpoint**: `POST /api/v1/council/debate`

```python
# Python
headers = {"X-API-Key": "your-api-key"}
debate_data = {
    "topic": "Should we invest in new infrastructure?",
    "context": {
        "budget": 100000,
        "timeline": "Q2 2025"
    }
}

response = requests.post(
    "http://localhost:8000/api/v1/council/debate",
    headers=headers,
    json=debate_data
)
result = response.json()
print(f"Consensus: {result['consensus']}")
print(f"Recommendation: {result['recommendation']}")
```

### Get Council Conclusions

**Endpoint**: `GET /api/v1/council/conclusions`

```python
# Python
headers = {"X-API-Key": "your-api-key"}
params = {"limit": 10, "recent": True}
response = requests.get(
    "http://localhost:8000/api/v1/council/conclusions",
    headers=headers,
    params=params
)
conclusions = response.json()
```

---

## Error Handling

### Common Error Responses

**400 Bad Request**:
```json
{
  "detail": "Invalid request parameters"
}
```

**401 Unauthorized**:
```json
{
  "detail": "Authentication required"
}
```

**403 Forbidden**:
```json
{
  "detail": "Forbidden: Authentication required for monitoring endpoints"
}
```

**404 Not Found**:
```json
{
  "detail": "Agent not found"
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Internal server error"
}
```

### Error Handling Example

```python
# Python
import requests
from requests.exceptions import RequestException

def safe_api_call(url, headers=None, **kwargs):
    try:
        response = requests.get(url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Authentication required")
        elif e.response.status_code == 403:
            print("Access forbidden")
        elif e.response.status_code == 404:
            print("Resource not found")
        else:
            print(f"HTTP Error: {e}")
        return None
    except RequestException as e:
        print(f"Request failed: {e}")
        return None

# Usage
result = safe_api_call(
    "http://localhost:8000/api/v1/agents",
    headers={"X-API-Key": "your-api-key"}
)
```

```javascript
// JavaScript
async function safeApiCall(url, options = {}) {
  try {
    const response = await fetch(url, options);
    
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required');
      } else if (response.status === 403) {
        throw new Error('Access forbidden');
      } else if (response.status === 404) {
        throw new Error('Resource not found');
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    }
    
    return await response.json();
  } catch (error) {
    console.error('API call failed:', error);
    return null;
  }
}

// Usage
const result = await safeApiCall('http://localhost:8000/api/v1/agents', {
  headers: {
    'X-API-Key': 'your-api-key'
  }
});
```

---

## Rate Limiting

Daena API implements rate limiting to ensure fair usage.

### Rate Limit Headers

Responses include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```

### Handling Rate Limits

```python
# Python
import requests
import time

def make_request_with_retry(url, headers=None, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        
        if response.status_code == 429:  # Too Many Requests
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Retrying after {retry_after} seconds...")
            time.sleep(retry_after)
            continue
        
        response.raise_for_status()
        return response.json()
    
    raise Exception("Max retries exceeded")
```

```javascript
// JavaScript
async function makeRequestWithRetry(url, options = {}, maxRetries = 3) {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const response = await fetch(url, options);
    
    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
      console.log(`Rate limited. Retrying after ${retryAfter} seconds...`);
      await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
      continue;
    }
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return await response.json();
  }
  
  throw new Error('Max retries exceeded');
}
```

---

## Complete Python Client Example

```python
import requests
from typing import Optional, Dict, Any

class DaenaClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("headers", {}).update(self.headers)
        
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def get_health(self) -> Dict[str, Any]:
        """Get system health status."""
        return self._request("GET", "/api/v1/system/health")
    
    def get_agents(self, department_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Get all agents."""
        params = {"limit": limit}
        if department_id:
            params["department_id"] = department_id
        return self._request("GET", "/api/v1/agents", params=params)
    
    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get agent by ID."""
        return self._request("GET", f"/api/v1/agents/{agent_id}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics."""
        return self._request("GET", "/api/v1/monitoring/metrics")
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """Get memory metrics."""
        return self._request("GET", "/api/v1/monitoring/memory")
    
    def start_chat(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Start a chat session."""
        return self._request("POST", "/api/v1/daena/chat/start", json={"user_id": user_id})
    
    def send_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Send a message in a chat session."""
        return self._request(
            "POST",
            "/api/v1/daena/chat/message",
            json={
                "session_id": session_id,
                "message": message,
                "context": {}
            }
        )

# Usage
client = DaenaClient(api_key="your-api-key")

# Get health
health = client.get_health()
print(f"Status: {health['status']}")

# Get agents
agents = client.get_agents(department_id="ai")
print(f"Found {agents['total_count']} agents")

# Start chat
session = client.start_chat(user_id="user_123")
response = client.send_message(session["session_id"], "Hello!")
print(response["response"])
```

---

## Complete JavaScript Client Example

```javascript
class DaenaClient {
  constructor(baseUrl = 'http://localhost:8000', apiKey = null) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
    this.headers = {
      'Content-Type': 'application/json'
    };
    if (apiKey) {
      this.headers['X-API-Key'] = apiKey;
    }
  }
  
  async request(method, endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const config = {
      method,
      headers: { ...this.headers, ...options.headers },
      ...options
    };
    
    const response = await fetch(url, config);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return await response.json();
  }
  
  async getHealth() {
    return this.request('GET', '/api/v1/system/health');
  }
  
  async getAgents(departmentId = null, limit = 100) {
    const params = new URLSearchParams({ limit });
    if (departmentId) params.append('department_id', departmentId);
    return this.request('GET', `/api/v1/agents?${params}`);
  }
  
  async getAgent(agentId) {
    return this.request('GET', `/api/v1/agents/${agentId}`);
  }
  
  async getMetrics() {
    return this.request('GET', '/api/v1/monitoring/metrics');
  }
  
  async getMemoryMetrics() {
    return this.request('GET', '/api/v1/monitoring/memory');
  }
  
  async startChat(userId = null) {
    return this.request('POST', '/api/v1/daena/chat/start', {
      body: JSON.stringify({ user_id: userId })
    });
  }
  
  async sendMessage(sessionId, message) {
    return this.request('POST', '/api/v1/daena/chat/message', {
      body: JSON.stringify({
        session_id: sessionId,
        message,
        context: {}
      })
    });
  }
}

// Usage
const client = new DaenaClient('http://localhost:8000', 'your-api-key');

// Get health
const health = await client.getHealth();
console.log('Status:', health.status);

// Get agents
const agents = await client.getAgents('ai');
console.log('Found', agents.total_count, 'agents');

// Start chat
const session = await client.startChat('user_123');
const response = await client.sendMessage(session.session_id, 'Hello!');
console.log(response.response);
```

---

## Related Documentation

- `docs/MONITORING_GUIDE.md` - Monitoring setup
- `docs/PERFORMANCE_TUNING_GUIDE.md` - Performance optimization
- `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` - Deployment guide

---

**Status**: ✅ **PRODUCTION READY**  
**Last Updated**: 2025-01-XX
