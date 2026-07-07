"""Pydantic schemas for the read-only Mission Control graph projection.

Nodes are existing ORM rows; edges are existing foreign keys. No new
tables back these schemas -- they are the wire shape of
``GraphService.build_graph`` only.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """One entity in the org graph (a projected ORM row or the virtual root)."""

    id: str  # "agent:<uuid>" / "department:<uuid>" / "daena:root"
    kind: str  # daena|department|agent|project|workstream|mcp_server|skill|tool|workflow|sop|document|decision|risk|kpi
    label: str
    status: str | None = None
    department_id: str | None = None
    sunflower_index: int | None = None
    meta: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """One relationship, synthesized from an existing FK or the virtual root."""

    id: str  # "<source>->__<target>__<rel>"
    source: str
    target: str
    rel: str  # contains|employs|owns|runs|provides|defines|documents|stores|records|tracks|measures (EntityLink rels are operator-defined and can be anything)
    weight: float = 1.0


class GraphStats(BaseModel):
    """Summary counts for the StatsRibbon and quick health checks."""

    node_count: int
    edge_count: int
    by_kind: dict[str, int]
    generated_at: datetime


class GraphResponse(BaseModel):
    """Full projection payload returned under the ``data`` envelope key."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: GraphStats


class GraphSearchRequest(BaseModel):
    """Semantic search request body for ``POST /graph/search`` (PR-4)."""

    q: str = Field(..., min_length=1, max_length=512)
    kinds: list[str] | None = None
    k: int = Field(default=10, ge=1, le=50)


class GraphSearchCitation(BaseModel):
    """One ragx evidence row paired with the highlight payload."""

    chunk_id: str
    source_path: str
    score: float
    snippet: str
    collection: str


class GraphSearchResponse(BaseModel):
    """Highlight payload. ``available=False`` means ragx was offline or
    abstained on every collection; the UI MUST surface that honestly per
    Rule 17 rather than hiding the failure behind an empty match set.
    """

    matched_node_ids: list[str]
    citations: list[GraphSearchCitation]
    available: bool


# --- PR-5: node detail (Activity / AI Access / AI Context tabs) ---------------


class GraphNeighbor(BaseModel):
    """A node directly adjacent to the focused node in the detail view."""

    id: str
    kind: str
    label: str
    rel: str
    direction: str  # "in" (edge points at this node) | "out"


class NodeActivityItem(BaseModel):
    """One governance audit event scoped to a node (Activity tab)."""

    id: str
    action_type: str
    actor_type: str | None = None
    result: str | None = None
    risk_level: str | None = None
    created_at: datetime


class NodeToolRef(BaseModel):
    """A single MCP tool a server reported. Empty when none is persisted:
    MCP tools are a runtime listTools result and are never fabricated
    (Rule 17)."""

    name: str
    description: str | None = None


class NodeAccessApp(BaseModel):
    """A connected app (MCP server) in the tenant's shared tool pool."""

    id: str
    label: str
    status: str | None = None
    tool_count: int = 0


class NodeSkillRef(BaseModel):
    """A refined skill available in the tenant's shared pool."""

    id: str
    title: str
    domain: str | None = None


class NodeAiAccess(BaseModel):
    """What tools and skills an entity can draw on (AI Access tab).

    ``scope`` is "self" (an MCP server's own tools), "tenant" (the shared
    pool an agent/department/root can use), or "none". ``note`` carries an
    honest caveat (e.g. tools are runtime-discovered, selection is dynamic).
    """

    scope: str
    note: str | None = None
    mcp_servers: list[NodeAccessApp] = Field(default_factory=list)
    mcp_tools: list[NodeToolRef] = Field(default_factory=list)
    skills: list[NodeSkillRef] = Field(default_factory=list)


class NodeAiContext(BaseModel):
    """Ragx evidence for a node (AI Context tab). ``available=False`` means
    ragx was offline or abstained; the UI shows an honest pill rather than
    fabricating context (Rule 17)."""

    available: bool
    requested: list[str] = Field(default_factory=list)
    citations: list[GraphSearchCitation] = Field(default_factory=list)


class NodeDetailResponse(BaseModel):
    """Full detail payload for GET /graph/node/{kind}/{node_id}."""

    node: GraphNode
    neighbors: list[GraphNeighbor] = Field(default_factory=list)
    detail: dict = Field(default_factory=dict)
    activity: list[NodeActivityItem] = Field(default_factory=list)
    ai_access: NodeAiAccess
    ai_context: NodeAiContext
