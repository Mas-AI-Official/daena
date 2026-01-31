"""
CMP Graph API - Node graph persistence and execution

Part D: CMP Page Redesign (n8n-like node graph)
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cmp/graph", tags=["CMP Graph"])


# ═══════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════

class NodePosition(BaseModel):
    """Position on canvas"""
    x: float
    y: float


class NodeConfig(BaseModel):
    """Node configuration"""
    credentials_required: List[str] = []
    parameters: Dict[str, Any] = {}
    rate_limit: Optional[int] = None  # requests per minute


class Node(BaseModel):
    """A node in the CMP graph"""
    id: str
    name: str
    type: str  # tool, agent, workflow, trigger
    category: str  # crm, email, calendar, llm, storage, qa, security, etc.
    position: NodePosition
    config: NodeConfig = Field(default_factory=NodeConfig)
    enabled: bool = True
    health: str = "unknown"  # healthy, unhealthy, unknown


class EdgeCondition(BaseModel):
    """Condition for edge execution"""
    field: Optional[str] = None
    operator: Optional[str] = None  # eq, neq, gt, lt, contains
    value: Optional[Any] = None
    always: bool = True  # Execute always if true


class EdgePolicy(BaseModel):
    """Policy for edge execution"""
    allow: bool = True
    rate_limit: Optional[int] = None
    requires_approval: bool = False
    data_redaction: List[str] = []  # fields to redact


class EdgeConfig(BaseModel):
    """Edge configuration"""
    trigger_type: str = "on_success"  # on_success, on_error, on_complete, manual
    data_mapping: Dict[str, str] = {}  # source_field -> target_field
    condition: EdgeCondition = Field(default_factory=EdgeCondition)
    policy: EdgePolicy = Field(default_factory=EdgePolicy)


class Edge(BaseModel):
    """An edge connecting two nodes"""
    id: str
    source_node_id: str
    source_output: str = "default"
    target_node_id: str
    target_input: str = "default"
    config: EdgeConfig = Field(default_factory=EdgeConfig)


class Graph(BaseModel):
    """A complete CMP graph"""
    id: str
    name: str
    description: Optional[str] = None
    nodes: List[Node] = []
    edges: List[Edge] = []
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    owner_id: Optional[str] = None
    is_template: bool = False
    enabled: bool = True


class ExecutionLog(BaseModel):
    """Log entry for graph execution"""
    execution_id: str
    graph_id: str
    node_id: str
    status: str  # running, completed, failed, skipped
    input_data: Dict[str, Any] = {}
    output_data: Dict[str, Any] = {}
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════════════
# Category Registry
# ═══════════════════════════════════════════════════════════════════════

CATEGORIES = {
    "trigger": {"name": "Triggers", "color": "#10b981", "icon": "⚡"},
    "email": {"name": "Email", "color": "#3b82f6", "icon": "📧"},
    "crm": {"name": "CRM", "color": "#8b5cf6", "icon": "👥"},
    "calendar": {"name": "Calendar", "color": "#f59e0b", "icon": "📅"},
    "llm": {"name": "LLM/AI", "color": "#6366f1", "icon": "🧠"},
    "storage": {"name": "Storage", "color": "#64748b", "icon": "💾"},
    "qa": {"name": "QA/Testing", "color": "#22c55e", "icon": "✅"},
    "security": {"name": "Security", "color": "#ef4444", "icon": "🔒"},
    "analytics": {"name": "Analytics", "color": "#0ea5e9", "icon": "📊"},
    "deploy": {"name": "Deployment", "color": "#f97316", "icon": "🚀"},
    "communication": {"name": "Communication", "color": "#ec4899", "icon": "💬"},
    "workflow": {"name": "Workflow", "color": "#84cc16", "icon": "🔄"},
    "agent": {"name": "Agents", "color": "#a855f7", "icon": "🤖"},
    "other": {"name": "Other", "color": "#94a3b8", "icon": "📦"},
}


# ═══════════════════════════════════════════════════════════════════════
# Graph Storage
# ═══════════════════════════════════════════════════════════════════════

class GraphStorage:
    """Persistent storage for CMP graphs"""
    
    def __init__(self):
        self.storage_path = Path(__file__).parent.parent.parent / "data" / "cmp_graphs"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.graphs: Dict[str, Graph] = {}
        self._load_all()
    
    def _load_all(self):
        """Load all graphs from disk"""
        for file in self.storage_path.glob("*.json"):
            try:
                with open(file) as f:
                    data = json.load(f)
                    graph = Graph(**data)
                    self.graphs[graph.id] = graph
            except Exception as e:
                logger.error(f"Failed to load graph {file}: {e}")
    
    def _save(self, graph: Graph):
        """Save a graph to disk"""
        file = self.storage_path / f"{graph.id}.json"
        with open(file, "w") as f:
            json.dump(graph.model_dump(), f, default=str, indent=2)
    
    def create(self, graph: Graph) -> Graph:
        """Create a new graph"""
        if graph.id in self.graphs:
            raise ValueError(f"Graph {graph.id} already exists")
        self.graphs[graph.id] = graph
        self._save(graph)
        return graph
    
    def get(self, graph_id: str) -> Optional[Graph]:
        """Get a graph by ID"""
        return self.graphs.get(graph_id)
    
    def update(self, graph: Graph) -> Graph:
        """Update an existing graph"""
        if graph.id not in self.graphs:
            raise ValueError(f"Graph {graph.id} not found")
        graph.updated_at = datetime.utcnow()
        graph.version += 1
        self.graphs[graph.id] = graph
        self._save(graph)
        return graph
    
    def delete(self, graph_id: str):
        """Delete a graph"""
        if graph_id in self.graphs:
            del self.graphs[graph_id]
            file = self.storage_path / f"{graph_id}.json"
            if file.exists():
                file.unlink()
    
    def list_all(self) -> List[Graph]:
        """List all graphs"""
        return list(self.graphs.values())
    
    def list_templates(self) -> List[Graph]:
        """List template graphs"""
        return [g for g in self.graphs.values() if g.is_template]


# Global storage instance
graph_storage = GraphStorage()


# ═══════════════════════════════════════════════════════════════════════
# Routes - Categories
# ═══════════════════════════════════════════════════════════════════════

@router.get("/categories")
async def get_categories():
    """Get all node categories"""
    return {
        "categories": [
            {"id": k, **v}
            for k, v in CATEGORIES.items()
        ]
    }


# ═══════════════════════════════════════════════════════════════════════
# Routes - Graphs CRUD
# ═══════════════════════════════════════════════════════════════════════

@router.get("")
async def list_graphs(include_templates: bool = False):
    """List all graphs"""
    graphs = graph_storage.list_all()
    if not include_templates:
        graphs = [g for g in graphs if not g.is_template]
    
    return {
        "graphs": [
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "node_count": len(g.nodes),
                "edge_count": len(g.edges),
                "enabled": g.enabled,
                "is_template": g.is_template,
                "updated_at": g.updated_at.isoformat()
            }
            for g in graphs
        ]
    }


@router.post("")
async def create_graph(graph: Graph):
    """Create a new graph"""
    try:
        created = graph_storage.create(graph)
        return {"success": True, "graph_id": created.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{graph_id}")
async def get_graph(graph_id: str):
    """Get a graph by ID"""
    graph = graph_storage.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    return graph.model_dump()


@router.put("/{graph_id}")
async def update_graph(graph_id: str, graph: Graph):
    """Update a graph"""
    if graph.id != graph_id:
        raise HTTPException(status_code=400, detail="Graph ID mismatch")
    
    try:
        updated = graph_storage.update(graph)
        return {"success": True, "version": updated.version}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{graph_id}")
async def delete_graph(graph_id: str):
    """Delete a graph"""
    graph_storage.delete(graph_id)
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════
# Routes - Nodes
# ═══════════════════════════════════════════════════════════════════════

@router.post("/{graph_id}/nodes")
async def add_node(graph_id: str, node: Node):
    """Add a node to a graph"""
    graph = graph_storage.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    # Check for duplicate ID
    if any(n.id == node.id for n in graph.nodes):
        raise HTTPException(status_code=400, detail="Node ID already exists")
    
    graph.nodes.append(node)
    graph_storage.update(graph)
    
    return {"success": True, "node_id": node.id}


@router.put("/{graph_id}/nodes/{node_id}")
async def update_node(graph_id: str, node_id: str, node: Node):
    """Update a node"""
    graph = graph_storage.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    for i, n in enumerate(graph.nodes):
        if n.id == node_id:
            graph.nodes[i] = node
            graph_storage.update(graph)
            return {"success": True}
    
    raise HTTPException(status_code=404, detail="Node not found")


@router.delete("/{graph_id}/nodes/{node_id}")
async def delete_node(graph_id: str, node_id: str):
    """Delete a node and its connected edges"""
    graph = graph_storage.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    # Remove node
    graph.nodes = [n for n in graph.nodes if n.id != node_id]
    
    # Remove connected edges
    graph.edges = [
        e for e in graph.edges
        if e.source_node_id != node_id and e.target_node_id != node_id
    ]
    
    graph_storage.update(graph)
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════
# Routes - Edges
# ═══════════════════════════════════════════════════════════════════════

@router.post("/{graph_id}/edges")
async def add_edge(graph_id: str, edge: Edge):
    """Add an edge to a graph"""
    graph = graph_storage.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    # Validate nodes exist
    node_ids = {n.id for n in graph.nodes}
    if edge.source_node_id not in node_ids:
        raise HTTPException(status_code=400, detail="Source node not found")
    if edge.target_node_id not in node_ids:
        raise HTTPException(status_code=400, detail="Target node not found")
    
    # Check for duplicate edge
    if any(e.id == edge.id for e in graph.edges):
        raise HTTPException(status_code=400, detail="Edge ID already exists")
    
    graph.edges.append(edge)
    graph_storage.update(graph)
    
    return {"success": True, "edge_id": edge.id}


@router.delete("/{graph_id}/edges/{edge_id}")
async def delete_edge(graph_id: str, edge_id: str):
    """Delete an edge"""
    graph = graph_storage.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    graph.edges = [e for e in graph.edges if e.id != edge_id]
    graph_storage.update(graph)
    
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════
# Routes - Execution
# ═══════════════════════════════════════════════════════════════════════

@router.post("/{graph_id}/execute")
async def execute_graph(
    graph_id: str,
    start_node_id: Optional[str] = Body(None),
    input_data: Dict[str, Any] = Body(default={})
):
    """
    Execute a graph or subgraph.
    
    If start_node_id is provided, execution starts from that node.
    Otherwise, starts from trigger nodes.
    """
    graph = graph_storage.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    if not graph.enabled:
        raise HTTPException(status_code=400, detail="Graph is disabled")
    
    execution_id = f"exec_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    # TODO: Implement actual execution
    # For now, return a mock execution result
    
    return {
        "execution_id": execution_id,
        "graph_id": graph_id,
        "status": "started",
        "start_node": start_node_id,
        "started_at": datetime.utcnow().isoformat()
    }


@router.get("/{graph_id}/validate")
async def validate_graph(graph_id: str):
    """Validate a graph for execution readiness"""
    graph = graph_storage.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    issues = []
    
    # Check for orphan nodes (no connections)
    connected_nodes = set()
    for edge in graph.edges:
        connected_nodes.add(edge.source_node_id)
        connected_nodes.add(edge.target_node_id)
    
    orphans = [n.id for n in graph.nodes if n.id not in connected_nodes]
    if orphans and len(graph.nodes) > 1:
        issues.append({"type": "warning", "message": f"Orphan nodes: {orphans}"})
    
    # Check for trigger nodes
    trigger_nodes = [n for n in graph.nodes if n.type == "trigger"]
    if not trigger_nodes:
        issues.append({"type": "warning", "message": "No trigger nodes found"})
    
    # Check for cycles (simple detection)
    # TODO: Full cycle detection
    
    return {
        "valid": len([i for i in issues if i["type"] == "error"]) == 0,
        "issues": issues
    }


# ═══════════════════════════════════════════════════════════════════════
# Routes - Templates
# ═══════════════════════════════════════════════════════════════════════

@router.get("/templates")
async def list_templates():
    """List available graph templates"""
    templates = graph_storage.list_templates()
    
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "node_count": len(t.nodes),
                "categories": list(set(n.category for n in t.nodes))
            }
            for t in templates
        ]
    }


@router.post("/templates/{template_id}/instantiate")
async def instantiate_template(template_id: str, name: str = Body(...)):
    """Create a new graph from a template"""
    template = graph_storage.get(template_id)
    if not template or not template.is_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create new graph from template
    new_id = f"graph_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    new_graph = Graph(
        id=new_id,
        name=name,
        description=f"Based on template: {template.name}",
        nodes=template.nodes.copy(),
        edges=template.edges.copy(),
        is_template=False
    )
    
    graph_storage.create(new_graph)
    
    return {"success": True, "graph_id": new_id}


# ═══════════════════════════════════════════════════════════════════════
# Initialize Sample Template
# ═══════════════════════════════════════════════════════════════════════

def create_sample_template():
    """Create a sample CRM + Email + Calendar workflow template"""
    template_id = "template_crm_email_calendar"
    
    if graph_storage.get(template_id):
        return  # Already exists
    
    template = Graph(
        id=template_id,
        name="CRM + Email + Calendar Workflow",
        description="Example workflow: New CRM lead → Send welcome email → Schedule follow-up",
        is_template=True,
        nodes=[
            Node(
                id="trigger_new_lead",
                name="New Lead Trigger",
                type="trigger",
                category="crm",
                position=NodePosition(x=100, y=200),
                config=NodeConfig(parameters={"event": "lead.created"})
            ),
            Node(
                id="action_send_email",
                name="Send Welcome Email",
                type="action",
                category="email",
                position=NodePosition(x=350, y=200),
                config=NodeConfig(
                    credentials_required=["SENDGRID_API_KEY"],
                    parameters={"template": "welcome"}
                )
            ),
            Node(
                id="action_create_event",
                name="Schedule Follow-up",
                type="action",
                category="calendar",
                position=NodePosition(x=600, y=200),
                config=NodeConfig(
                    credentials_required=["GOOGLE_API_KEY"],
                    parameters={"delay_days": 3}
                )
            ),
            Node(
                id="action_create_ticket",
                name="Create Support Ticket",
                type="action",
                category="crm",
                position=NodePosition(x=600, y=350),
                config=NodeConfig(parameters={"priority": "normal"})
            ),
        ],
        edges=[
            Edge(
                id="edge_1",
                source_node_id="trigger_new_lead",
                target_node_id="action_send_email"
            ),
            Edge(
                id="edge_2",
                source_node_id="action_send_email",
                target_node_id="action_create_event",
                config=EdgeConfig(trigger_type="on_success")
            ),
            Edge(
                id="edge_3",
                source_node_id="action_send_email",
                target_node_id="action_create_ticket",
                config=EdgeConfig(trigger_type="on_error")
            ),
        ]
    )
    
    try:
        graph_storage.create(template)
        logger.info("Created sample CRM + Email + Calendar template")
    except ValueError:
        pass  # Already exists


# Initialize sample template on module load
create_sample_template()
