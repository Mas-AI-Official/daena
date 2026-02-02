# CMP Graph Module Documentation

**Version:** 1.0.0  
**Last Updated:** 2026-01-21  
**Module Path:** `backend/routes/cmp_graph.py`  
**UI Path:** `/cmp-canvas`

---

## Overview

CMP Graph is an n8n-like visual workflow editor for Daena's Consensus Model Protocol. It provides:

1. **Visual Node Graph** - Drag-and-drop interface for building workflows
2. **Categories** - 14 node categories covering all business functions
3. **Persistence** - Graphs saved to disk and can be version-controlled
4. **Execution** - Run graphs with input data
5. **Templates** - Pre-built workflow templates

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       CMP CANVAS UI                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌────────────────────────────┐  ┌──────────┐│
│  │ Node Palette │  │       Canvas Area          │  │  Config  ││
│  │              │  │                            │  │  Panel   ││
│  │ ─ Triggers   │  │   [Node] ───▶ [Node]      │  │          ││
│  │ ─ Email      │  │      │                     │  │  Name    ││
│  │ ─ CRM        │  │      ▼                     │  │  Params  ││
│  │ ─ Calendar   │  │   [Node]                   │  │  Health  ││
│  │ ─ LLM        │  │                            │  │          ││
│  │ ─ Storage    │  │                            │  │          ││
│  │ ─ QA         │  │                            │  │          ││
│  │ ─ Agents     │  │                            │  │          ││
│  │ ...          │  │                            │  │          ││
│  └──────────────┘  └────────────────────────────┘  └──────────┘│
│                                                                  │
│  [Save] [Load] [Validate] [Execute]                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │    CMP Graph API (Backend)   │
           │                              │
           │  - GET/POST /cmp/graph       │
           │  - Nodes CRUD                │
           │  - Edges CRUD                │
           │  - Execute                   │
           │  - Validate                  │
           │                              │
           └──────────────────────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │    Graph Storage (JSON)       │
           │    data/cmp_graphs/*.json    │
           └──────────────────────────────┘
```

---

## API Endpoints

### Graphs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/cmp/graph` | List all graphs |
| POST | `/api/v1/cmp/graph` | Create a graph |
| GET | `/api/v1/cmp/graph/{id}` | Get graph by ID |
| PUT | `/api/v1/cmp/graph/{id}` | Update a graph |
| DELETE | `/api/v1/cmp/graph/{id}` | Delete a graph |

### Nodes

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/cmp/graph/{id}/nodes` | Add node |
| PUT | `/api/v1/cmp/graph/{id}/nodes/{node_id}` | Update node |
| DELETE | `/api/v1/cmp/graph/{id}/nodes/{node_id}` | Delete node |

### Edges

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/cmp/graph/{id}/edges` | Add edge |
| DELETE | `/api/v1/cmp/graph/{id}/edges/{edge_id}` | Delete edge |

### Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/cmp/graph/categories` | Get all node categories |

### Execution

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/cmp/graph/{id}/execute` | Execute a graph |
| GET | `/api/v1/cmp/graph/{id}/validate` | Validate a graph |

### Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/cmp/graph/templates` | List templates |
| POST | `/api/v1/cmp/graph/templates/{id}/instantiate` | Create graph from template |

---

## Node Categories

| Category | Icon | Color | Example Nodes |
|----------|------|-------|---------------|
| trigger | ⚡ | #10b981 | Webhook, Schedule, Event, Manual |
| email | 📧 | #3b82f6 | Send Email, Read Email, Email Trigger |
| crm | 👥 | #8b5cf6 | Create Lead, Update Contact, CRM Trigger |
| calendar | 📅 | #f59e0b | Create Event, Check Availability |
| llm | 🧠 | #6366f1 | GPT-4, Claude, Gemini, Custom LLM |
| storage | 💾 | #64748b | Read File, Write File, Upload |
| qa | ✅ | #22c55e | Run Tests, Security Scan, Code Review |
| security | 🔒 | #ef4444 | Auth Check, Permission Verify |
| analytics | 📊 | #0ea5e9 | Track Event, Generate Report |
| deploy | 🚀 | #f97316 | Deploy App, Rollback |
| communication | 💬 | #ec4899 | Slack Message, Discord, Notification |
| workflow | 🔄 | #84cc16 | Branch, Merge, Loop |
| agent | 🤖 | #a855f7 | Daena Agent, Custom Agent |
| other | 📦 | #94a3b8 | Custom Action |

---

## Data Models

### Graph
```typescript
interface Graph {
  id: string;
  name: string;
  description?: string;
  nodes: Node[];
  edges: Edge[];
  version: number;
  created_at: string;
  updated_at: string;
  owner_id?: string;
  is_template: boolean;
  enabled: boolean;
}
```

### Node
```typescript
interface Node {
  id: string;
  name: string;
  type: string;          // trigger, action, condition
  category: string;      // email, crm, llm, etc.
  position: {
    x: number;
    y: number;
  };
  config: {
    credentials_required: string[];
    parameters: Record<string, any>;
    rate_limit?: number;
  };
  enabled: boolean;
  health: string;        // healthy, unhealthy, unknown
}
```

### Edge
```typescript
interface Edge {
  id: string;
  source_node_id: string;
  source_output: string;  // default, error, etc.
  target_node_id: string;
  target_input: string;
  config: {
    trigger_type: string;      // on_success, on_error, on_complete
    data_mapping: Record<string, string>;
    condition: {
      field?: string;
      operator?: string;       // eq, neq, gt, lt, contains
      value?: any;
      always: boolean;
    };
    rate_limit?: number;
  };
}
```

---

## Usage

### Access the Canvas

Open in browser:
```
http://localhost:8000/cmp-canvas
```

### Create a Workflow

1. **Drag nodes** from the left palette onto the canvas
2. **Connect nodes** by clicking between ports
3. **Configure nodes** by clicking the ⚙️ button
4. **Save** using the Save button in toolbar
5. **Execute** using the Execute button

### API Usage

#### Create a Graph
```bash
curl -X POST http://localhost:8000/api/v1/cmp/graph \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my_workflow",
    "name": "My CRM Workflow",
    "nodes": [],
    "edges": []
  }'
```

#### Add a Node
```bash
curl -X POST http://localhost:8000/api/v1/cmp/graph/my_workflow/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "id": "node_1",
    "name": "New Lead Trigger",
    "type": "trigger",
    "category": "crm",
    "position": {"x": 100, "y": 100}
  }'
```

#### Execute a Graph
```bash
curl -X POST http://localhost:8000/api/v1/cmp/graph/my_workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {"lead_id": "lead_123"}
  }'
```

---

## Templates

### Pre-built Templates

| Template ID | Name | Description |
|-------------|------|-------------|
| `template_crm_email_calendar` | CRM + Email + Calendar | New lead → Welcome email → Schedule follow-up |

### Using Templates

```bash
# List templates
curl http://localhost:8000/api/v1/cmp/graph/templates

# Create graph from template
curl -X POST http://localhost:8000/api/v1/cmp/graph/templates/template_crm_email_calendar/instantiate \
  -H "Content-Type: application/json" \
  -d '{"name": "My CRM Workflow"}'
```

---

## Validation

The validation endpoint checks:
1. **Orphan nodes** - Nodes with no connections (warning)
2. **Missing triggers** - No trigger node (warning)
3. **Invalid references** - Edges referencing non-existent nodes (error)
4. **Cycles** - Potential infinite loops (warning)

```bash
curl http://localhost:8000/api/v1/cmp/graph/my_workflow/validate
```

Response:
```json
{
  "valid": true,
  "issues": [
    {"type": "warning", "message": "Orphan nodes: [node_3]"}
  ]
}
```

---

## Storage

Graphs are stored as JSON files in:
```
data/cmp_graphs/{graph_id}.json
```

This allows:
- Version control with git
- Easy backup and restore
- Manual editing if needed

---

## Execution Engine

The execution engine (under development) will:

1. **Find trigger nodes** - Start points based on execution mode
2. **Traverse graph** - Follow edges based on conditions
3. **Execute actions** - Call backend APIs for each node
4. **Collect results** - Build output data
5. **Handle errors** - Route to error edges

### Node Type → Backend Action Mapping

| Node Type | Backend Endpoint |
|-----------|------------------|
| `trigger/webhook` | Webhook handler |
| `trigger/schedule` | Cron scheduler |
| `email/send` | `/api/v1/email/send` |
| `crm/create_lead` | `/api/v1/crm/leads` |
| `llm/generate` | `/api/v1/brain/generate` |
| `qa/run_tests` | `/api/v1/qa/run-regression` |
| `agent/execute` | `/api/v1/agents/{id}/tasks` |

---

## Integration with CMP Service

The CMP Graph integrates with the existing CMP tool registry:

```python
from backend.core.cmp.registry import tool_registry

# Get all tools that can be graph nodes
tools = tool_registry.get_all()

# Each tool has:
# - id (node type)
# - category
# - required_permissions
# - required_credentials
# - parameters schema
```

---

## Security

### Edge Policies

Each edge can have policies:
- **allow/deny** - Which tool calls are permitted
- **rate_limit** - Max calls per minute
- **required_approvals** - Human approval for sensitive ops
- **data_redaction** - Fields to mask in logs

### Least Privilege

Nodes only get credentials they need:
```json
{
  "config": {
    "credentials_required": ["SENDGRID_API_KEY"]
  }
}
```

Credentials are **never** stored in frontend - only referenced by name.

---

## Testing

### Run CMP Graph Tests
```bash
cd d:\Ideas\Daena_old_upgrade_20251213
.\venv_daena_main_py310\Scripts\python.exe -m pytest tests/test_cmp_graph.py -v
```

### Test Graph Validation
```python
from backend.routes.cmp_graph import graph_storage

# Create test graph
graph = graph_storage.create({...})

# Validate
from fastapi.testclient import TestClient
response = client.get(f"/api/v1/cmp/graph/{graph.id}/validate")
assert response.json()["valid"] == True
```

---

## References

- **UI Template:** `frontend/templates/cmp_canvas.html`
- **API Route:** `backend/routes/cmp_graph.py`
- **CMP Tool Registry:** `backend/core/cmp/registry.py`
- **CMP Service:** `backend/services/cmp_service.py`

---

*CMP Graph - Visual workflow automation for Daena*
