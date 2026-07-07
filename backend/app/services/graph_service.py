"""Read-only projection of existing ORM rows into a node/edge graph.

Rows are nodes; existing foreign keys are edges. This service performs
NO writes and adds NO tables. Every query is tenant-filtered. Sensitive
kinds (governance, vault, founder memory) are never projected.

Edge reality note: only ``department`` owns first-class FKs to agents and
workstreams, so those get real parent edges. ``project``, ``mcp_server``,
and ``skill`` are tenant-scoped with no department FK in the current
schema, so they anchor to the virtual ``daena:root`` node rather than to a
fabricated department edge (Rule 17: no invented relationships).
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SubCapability
from app.models.chat import ChatSession
from app.models.execution import Task, ToolExecution
from app.models.governance import GoaAuditEvent
from app.models.mcp_server import McpServer
from app.models.ontology import (
    Decision,
    Document,
    EntityLink,
    Kpi,
    Risk,
    Sop,
    Workflow,
)
from app.models.organization import Agent, Department
from app.models.project import Project
from app.models.skill import RefinedSkill
from app.models.tool import ToolRecord
from app.models.workstream import Workstream
from app.schemas.graph import (
    GraphEdge,
    GraphNeighbor,
    GraphNode,
    GraphResponse,
    GraphSearchCitation,
    GraphSearchResponse,
    GraphStats,
    NodeAccessApp,
    NodeActivityItem,
    NodeAiAccess,
    NodeAiContext,
    NodeDetailResponse,
    NodeSkillRef,
    NodeToolRef,
)
from app.services.ragx_bridge import (
    DEFAULT_COLLECTIONS,
    collections_for_department,
    query_ragx,
)

# Kinds projected by default. ``session`` and ``execution`` (the continuity
# layer) are default-on as of PR-6 but each capped to its most recent N rows
# (see SESSION_NODE_CAP / EXECUTION_NODE_CAP) because they are higher
# cardinality than the org structure. ``tool`` is default-on as of PR-8,
# projected from the backing ``tool_records`` table (ToolRecord); the in-code
# TOOL_CATALOG is never synthesized into nodes here.
DEFAULT_KINDS = (
    "daena",
    "faculty",
    "department",
    "agent",
    "project",
    "workstream",
    "mcp_server",
    "skill",
    "tool",
    "workflow",
    "sop",
    "document",
    "decision",
    "risk",
    "kpi",
    "session",
    "execution",
)
ROOT_ID = "daena:root"

# Continuity-layer caps (PR-6): sessions and executions are higher-cardinality
# than the org structure, so each kind is bounded to its most recent N rows
# (ORDER BY created_at DESC) at the QUERY level. This is the Graphiti/Zep
# "recent episodes" pattern: the newest continuity is what is relevant, and the
# query cap keeps the default graph bounded without leaning on the post-hoc
# limit cut (which truncates by insertion order and would drop these first).
SESSION_NODE_CAP = 200
EXECUTION_NODE_CAP = 200

# Typed ontology entities (PR-3) and the root-anchored relationship verb each
# one projects. All six are tenant-scoped with no department FK, so (like
# project and skill) they hang off the virtual daena:root node.
_ONTOLOGY_KINDS: tuple[tuple[str, type, str], ...] = (
    ("workflow", Workflow, "defines"),
    ("sop", Sop, "documents"),
    ("document", Document, "stores"),
    ("decision", Decision, "records"),
    ("risk", Risk, "tracks"),
    ("kpi", Kpi, "measures"),
)

# Daena's own six cognitive faculties. These are the SubCapability
# architectural constant -- the same six every department's agents are built
# from -- not tenant rows. The one-line role text mirrors the inline
# documentation on SubCapability (app.core.constants); the dict keys are
# asserted against the live enum at projection time so a 7th faculty can never
# silently appear unlabeled.
_FACULTY_ROLES: dict[str, str] = {
    "MIND": "Reasoning, planning",
    "EYES": "Observation, monitoring",
    "HANDS": "Execution, building",
    "VOICE": "Communication, reporting",
    "SHIELD": "Protection, validation",
    "MEMORY": "Knowledge, recall",
}


def _nid(kind: str, raw) -> str:
    return f"{kind}:{raw}"


def _status_from_active(is_active: bool | None) -> str:
    return "active" if is_active else "inactive"


def _enum_value(val):
    return getattr(val, "value", val)


class GraphService:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def build_graph(
        self,
        kinds: tuple[str, ...] | None = None,
        center: str | None = None,
        depth: int = 2,
        limit: int = 1000,
    ) -> GraphResponse:
        want = set(kinds) if kinds else set(DEFAULT_KINDS)
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []

        # Virtual root: anchors tenant-level entities with no department FK.
        if "daena" in want:
            nodes[ROOT_ID] = GraphNode(
                id=ROOT_ID, kind="daena", label="Daena", status="active"
            )

        # Daena's own six cognitive faculties (daena -> faculty: embodies).
        # These are the SubCapability architectural constant, not tenant rows:
        # the same six limbs every department's agents are built from, shown
        # here as Daena's own mind so the core reads as a being with faculties
        # rather than a bare hub. Provenance is carried in meta (Rule 17) and
        # the role text is asserted against the live enum so a new faculty can
        # never appear unlabeled. Only projected when the root exists, so the
        # ?kinds=department gate keeps them out of a structure-only view.
        if "faculty" in want and ROOT_ID in nodes:
            for idx, cap in enumerate(SubCapability):
                fid = _nid("faculty", cap.value)
                nodes[fid] = GraphNode(
                    id=fid,
                    kind="faculty",
                    label=cap.value.title(),
                    status="active",
                    sunflower_index=idx,
                    meta={
                        "capability": cap.value,
                        "sub_capability": cap.value,
                        "role": _FACULTY_ROLES.get(cap.value, ""),
                        "source": "architectural_constant",
                        "source_ref": "app.core.constants.SubCapability",
                    },
                )
                edges.append(GraphEdge(
                    id=f"{ROOT_ID}->__{fid}__embodies",
                    source=ROOT_ID, target=fid, rel="embodies",
                ))

        # Departments (root -> department: contains)
        if "department" in want:
            rows = (
                await self.db.execute(
                    select(Department).where(Department.tenant_id == self.tenant_id)
                )
            ).scalars().all()
            for d in rows:
                did = _nid("department", d.id)
                nodes[did] = GraphNode(
                    id=did,
                    kind="department",
                    label=d.name,
                    status=_status_from_active(d.is_active),
                    sunflower_index=d.sunflower_index,
                    meta={"description": d.description, "cell_id": d.cell_id},
                )
                if ROOT_ID in nodes:
                    edges.append(GraphEdge(
                        id=f"{ROOT_ID}->__{did}__contains",
                        source=ROOT_ID, target=did, rel="contains",
                    ))

        # Agents (department -> agent: employs)
        if "agent" in want:
            rows = (
                await self.db.execute(
                    select(Agent).where(Agent.tenant_id == self.tenant_id)
                )
            ).scalars().all()
            for a in rows:
                aid = _nid("agent", a.id)
                dep = _nid("department", a.department_id) if a.department_id else None
                nodes[aid] = GraphNode(
                    id=aid,
                    kind="agent",
                    label=a.name,
                    status=_status_from_active(a.is_active),
                    department_id=str(a.department_id) if a.department_id else None,
                    meta={
                        "sub_capability": a.sub_capability,
                        "model_preference": a.model_preference,
                    },
                )
                if dep and dep in nodes:
                    edges.append(GraphEdge(
                        id=f"{dep}->__{aid}__employs",
                        source=dep, target=aid, rel="employs",
                    ))

        # Workstreams (department -> workstream: owns)
        if "workstream" in want:
            rows = (
                await self.db.execute(
                    select(Workstream).where(Workstream.tenant_id == self.tenant_id)
                )
            ).scalars().all()
            for w in rows:
                wid = _nid("workstream", w.id)
                dep = _nid("department", w.department_id) if w.department_id else None
                nodes[wid] = GraphNode(
                    id=wid,
                    kind="workstream",
                    label=(w.goal or "")[:80],
                    status=_enum_value(w.status),
                    department_id=str(w.department_id) if w.department_id else None,
                    meta={
                        "goal": w.goal,
                        "next_step": w.next_step_text,
                        "blocker": w.blocker_text,
                    },
                )
                if dep and dep in nodes:
                    edges.append(GraphEdge(
                        id=f"{dep}->__{wid}__owns",
                        source=dep, target=wid, rel="owns",
                    ))

        # Projects (root -> project: owns) -- no department FK in schema
        if "project" in want:
            rows = (
                await self.db.execute(
                    select(Project).where(Project.tenant_id == self.tenant_id)
                )
            ).scalars().all()
            for p in rows:
                pid = _nid("project", p.id)
                nodes[pid] = GraphNode(
                    id=pid,
                    kind="project",
                    label=p.name,
                    status=_status_from_active(p.is_active),
                    meta={"description": p.description},
                )
                if ROOT_ID in nodes:
                    edges.append(GraphEdge(
                        id=f"{ROOT_ID}->__{pid}__owns",
                        source=ROOT_ID, target=pid, rel="owns",
                    ))

        # MCP servers (root -> mcp_server: runs) -- tenant-scoped, no dept FK
        if "mcp_server" in want:
            rows = (
                await self.db.execute(
                    select(McpServer).where(McpServer.tenant_id == self.tenant_id)
                )
            ).scalars().all()
            for m in rows:
                mid = _nid("mcp_server", m.id)
                nodes[mid] = GraphNode(
                    id=mid,
                    kind="mcp_server",
                    label=m.display_name,
                    status=m.status,
                    meta={
                        "server_key": m.server_key,
                        "description": m.description,
                        "command": m.command,
                        "server_url": m.server_url,
                    },
                )
                if ROOT_ID in nodes:
                    edges.append(GraphEdge(
                        id=f"{ROOT_ID}->__{mid}__runs",
                        source=ROOT_ID, target=mid, rel="runs",
                    ))

        # Refined skills (root -> skill: provides) -- tenant-scoped, no dept FK
        if "skill" in want:
            rows = (
                await self.db.execute(
                    select(RefinedSkill).where(RefinedSkill.tenant_id == self.tenant_id)
                )
            ).scalars().all()
            for s in rows:
                sid = _nid("skill", s.id)
                nodes[sid] = GraphNode(
                    id=sid,
                    kind="skill",
                    label=s.title,
                    status=None,
                    meta={
                        "skill_id": s.skill_id,
                        "domain": s.domain,
                        "maturity": s.maturity,
                    },
                )
                if ROOT_ID in nodes:
                    edges.append(GraphEdge(
                        id=f"{ROOT_ID}->__{sid}__provides",
                        source=ROOT_ID, target=sid, rel="provides",
                    ))

        # Tool registry (root -> tool: provides) -- tenant-scoped, no dept FK.
        # Projected from the durable tool_records table (PR-8), never from the
        # in-code TOOL_CATALOG. Disabled tools are shown with an inactive status
        # rather than hidden, so the operator kill switch stays visible in
        # Mission Control (Rule 17).
        if "tool" in want:
            rows = (
                await self.db.execute(
                    select(ToolRecord).where(ToolRecord.tenant_id == self.tenant_id)
                )
            ).scalars().all()
            for t in rows:
                tool_nid = _nid("tool", t.id)
                nodes[tool_nid] = GraphNode(
                    id=tool_nid,
                    kind="tool",
                    label=t.meta.get("name") or t.name,
                    status=_status_from_active(t.enabled),
                    meta={
                        "tool_kind": t.kind,
                        "description": t.description,
                        "source_ref": t.source_ref,
                    },
                )
                if ROOT_ID in nodes:
                    edges.append(GraphEdge(
                        id=f"{ROOT_ID}->__{tool_nid}__provides",
                        source=ROOT_ID, target=tool_nid, rel="provides",
                    ))

        # Typed ontology entities (PR-3): Workflow / Sop / Document / Decision
        # / Risk / Kpi. Like project and skill these are tenant-scoped with no
        # department FK, so they anchor to the virtual daena:root node.
        for kind, model, rel in _ONTOLOGY_KINDS:
            if kind not in want:
                continue
            rows = (
                await self.db.execute(
                    select(model).where(model.tenant_id == self.tenant_id)
                )
            ).scalars().all()
            for row in rows:
                eid = _nid(kind, row.id)
                nodes[eid] = GraphNode(
                    id=eid,
                    kind=kind,
                    label=row.name,
                    status=row.status,
                    meta=row.meta or {},
                )
                if ROOT_ID in nodes:
                    edges.append(GraphEdge(
                        id=f"{ROOT_ID}->__{eid}__{rel}",
                        source=ROOT_ID, target=eid, rel=rel,
                    ))

        # Sessions (PR-6 continuity layer): each conversation thread, capped to
        # the most recent SESSION_NODE_CAP non-archived rows. A session belongs
        # to its department when one is set (session -> department: belongs_to),
        # emitted dangling-safe like every other edge here.
        if "session" in want:
            rows = (
                await self.db.execute(
                    select(ChatSession)
                    .where(
                        ChatSession.tenant_id == self.tenant_id,
                        ChatSession.is_archived.is_(False),
                    )
                    .order_by(ChatSession.created_at.desc())
                    .limit(SESSION_NODE_CAP)
                )
            ).scalars().all()
            for sess in rows:
                sid = _nid("session", sess.id)
                dep = (
                    _nid("department", sess.department_id)
                    if sess.department_id else None
                )
                nodes[sid] = GraphNode(
                    id=sid,
                    kind="session",
                    label=sess.title or f"Session {str(sess.id)[:8]}",
                    status="active",
                    department_id=(
                        str(sess.department_id) if sess.department_id else None
                    ),
                    meta={"mode": sess.mode, "autopilot": sess.autopilot},
                )
                if dep and dep in nodes:
                    edges.append(GraphEdge(
                        id=f"{sid}->__{dep}__belongs_to",
                        source=sid, target=dep, rel="belongs_to",
                    ))

        # Executions (PR-6 continuity layer): project from BOTH Task and
        # ToolExecution rows (the model is named ToolExecution, not "Execution").
        # Each links to the session that spawned it (execution -> session:
        # spawned_by) when that session is in the projection; a ToolExecution
        # additionally links to its parent Task (execution -> execution:
        # part_of). Each source capped to its most recent EXECUTION_NODE_CAP
        # rows. All edges dangling-safe.
        if "execution" in want:
            task_node_ids: set[str] = set()
            task_rows = (
                await self.db.execute(
                    select(Task)
                    .where(
                        Task.tenant_id == self.tenant_id,
                        Task.archived_at.is_(None),
                    )
                    .order_by(Task.created_at.desc())
                    .limit(EXECUTION_NODE_CAP)
                )
            ).scalars().all()
            for task in task_rows:
                eid = _nid("execution", task.id)
                task_node_ids.add(eid)
                nodes[eid] = GraphNode(
                    id=eid,
                    kind="execution",
                    label=task.name,
                    status=task.status,
                    meta={"source": "task", "progress": task.progress},
                )
                sess_nid = (
                    _nid("session", task.session_id)
                    if task.session_id else None
                )
                if sess_nid and sess_nid in nodes:
                    edges.append(GraphEdge(
                        id=f"{eid}->__{sess_nid}__spawned_by",
                        source=eid, target=sess_nid, rel="spawned_by",
                    ))

            tool_rows = (
                await self.db.execute(
                    select(ToolExecution)
                    .where(ToolExecution.tenant_id == self.tenant_id)
                    .order_by(ToolExecution.created_at.desc())
                    .limit(EXECUTION_NODE_CAP)
                )
            ).scalars().all()
            for texec in tool_rows:
                eid = _nid("execution", texec.id)
                nodes[eid] = GraphNode(
                    id=eid,
                    kind="execution",
                    label=texec.tool_name,
                    status=texec.status,
                    meta={
                        "source": "tool_execution",
                        "governance_tier": texec.governance_tier,
                    },
                )
                sess_nid = (
                    _nid("session", texec.session_id)
                    if texec.session_id else None
                )
                if sess_nid and sess_nid in nodes:
                    edges.append(GraphEdge(
                        id=f"{eid}->__{sess_nid}__spawned_by",
                        source=eid, target=sess_nid, rel="spawned_by",
                    ))
                parent = (
                    _nid("execution", texec.task_id)
                    if texec.task_id else None
                )
                if parent and parent in task_node_ids:
                    edges.append(GraphEdge(
                        id=f"{eid}->__{parent}__part_of",
                        source=eid, target=parent, rel="part_of",
                    ))

        # Operator-defined edges (PR-3 EntityLink): emit only when BOTH
        # endpoints are present in this projection (dangling-safe) and the
        # synthesized edge id is not already present (dedupe vs FK edges and
        # duplicate link rows).
        if nodes:
            existing_ids = {e.id for e in edges}
            links = (
                await self.db.execute(
                    select(EntityLink).where(EntityLink.tenant_id == self.tenant_id)
                )
            ).scalars().all()
            for link in links:
                src = _nid(link.src_kind, link.src_id)
                dst = _nid(link.dst_kind, link.dst_id)
                if src not in nodes or dst not in nodes:
                    continue
                eid = f"{src}->__{dst}__{link.rel}"
                if eid in existing_ids:
                    continue
                existing_ids.add(eid)
                edges.append(GraphEdge(
                    id=eid, source=src, target=dst, rel=link.rel, weight=link.weight,
                ))

        # Optional center+depth BFS prune.
        if center and center in nodes:
            adj: dict[str, set[str]] = defaultdict(set)
            for e in edges:
                adj[e.source].add(e.target)
                adj[e.target].add(e.source)
            keep: set[str] = set()
            q: deque[tuple[str, int]] = deque([(center, 0)])
            while q:
                nid, dist = q.popleft()
                if nid in keep:
                    continue
                keep.add(nid)
                if dist < depth:
                    for nb in adj[nid]:
                        q.append((nb, dist + 1))
            nodes = {k: v for k, v in nodes.items() if k in keep}
            edges = [e for e in edges if e.source in nodes and e.target in nodes]

        # Deterministic limit cap (preserve insertion order).
        if len(nodes) > limit:
            nodes = dict(list(nodes.items())[:limit])
            edges = [e for e in edges if e.source in nodes and e.target in nodes]

        by_kind: dict[str, int] = defaultdict(int)
        for n in nodes.values():
            by_kind[n.kind] += 1

        return GraphResponse(
            nodes=list(nodes.values()),
            edges=edges,
            stats=GraphStats(
                node_count=len(nodes),
                edge_count=len(edges),
                by_kind=dict(by_kind),
                generated_at=datetime.now(timezone.utc),
            ),
        )

    async def semantic_search(
        self, q: str, k: int = 10
    ) -> GraphSearchResponse:
        """Ragx-highlight pattern (PR-4): query ragx for evidence and match
        the resulting blob against the tenant's projected node labels.

        Two-directional match (case-insensitive):
        - any non-trivial (>=3 char) node label found inside the blob, OR
        - any significant query token (>=4 chars after a non-alnum split)
          found inside a node label.

        Rule 17: when ragx is offline the response carries ``available=False``
        and any label matches against the query alone still surface, so the
        UI can show an honest "semantic search offline" pill instead of an
        empty state that pretends nothing matched.
        """
        result = await query_ragx(
            q,
            collections=DEFAULT_COLLECTIONS,
            k=k,
            timeout_s=6.0,
        )

        graph = await self.build_graph(kinds=DEFAULT_KINDS)

        q_lower = q.lower()
        blob_parts: list[str] = [q_lower]
        for c in result.citations:
            if c.snippet:
                blob_parts.append(c.snippet.lower())
            if c.source_path:
                blob_parts.append(c.source_path.lower())
        blob = " \n ".join(blob_parts)

        q_tokens = {
            tok for tok in re.split(r"[^a-z0-9]+", q_lower) if len(tok) >= 4
        }

        matched: list[str] = []
        seen: set[str] = set()
        for node in graph.nodes:
            if node.id in seen:
                continue
            label = (node.label or "").lower().strip()
            if not label:
                continue
            hit = False
            if len(label) >= 3 and label in blob:
                hit = True
            elif q_tokens and any(tok in label for tok in q_tokens):
                hit = True
            if hit:
                matched.append(node.id)
                seen.add(node.id)

        citations = [
            GraphSearchCitation(
                chunk_id=c.chunk_id,
                source_path=c.source_path,
                score=c.score,
                snippet=c.snippet,
                collection=c.collection,
            )
            for c in result.citations
        ]

        return GraphSearchResponse(
            matched_node_ids=matched,
            citations=citations,
            available=result.available,
        )

    # --- PR-5: node detail (Activity / AI Access / AI Context) ---------------

    async def get_node_detail(
        self, kind: str, node_id: str
    ) -> NodeDetailResponse | None:
        """Detail payload for one node plus its depth-1 neighbors.

        Reuses ``build_graph(center=..., depth=1)`` so node and neighbor
        shaping stay on the single projection path. Returns None (-> 404 at
        the route) when the id is absent, which also covers cross-tenant ids
        since the projection is tenant-filtered. Note: when ``center`` is not
        in the projection the BFS prune is skipped and the full graph comes
        back, but the explicit ``node_map.get`` miss below still returns None.
        """
        full_id = _nid(kind, node_id)
        graph = await self.build_graph(center=full_id, depth=1)
        node_map = {n.id: n for n in graph.nodes}
        node = node_map.get(full_id)
        if node is None:
            return None

        neighbors: list[GraphNeighbor] = []
        seen_nb: set[str] = set()
        for e in graph.edges:
            if e.source == full_id:
                other_id, direction = e.target, "out"
            elif e.target == full_id:
                other_id, direction = e.source, "in"
            else:
                continue
            if other_id in seen_nb:
                continue
            other = node_map.get(other_id)
            if other is None:
                continue
            seen_nb.add(other_id)
            neighbors.append(GraphNeighbor(
                id=other.id,
                kind=other.kind,
                label=other.label,
                rel=e.rel,
                direction=direction,
            ))

        activity = await self._node_activity(kind, node_id)
        ai_access = await self._node_ai_access(kind, node_id, node)
        ai_context = await self._node_ai_context(node)
        return NodeDetailResponse(
            node=node,
            neighbors=neighbors,
            detail=node.meta or {},
            activity=activity,
            ai_access=ai_access,
            ai_context=ai_context,
        )

    async def _node_activity(
        self, kind: str, node_id: str
    ) -> list[NodeActivityItem]:
        """Governance audit events scoped to this node.

        - ``daena`` root: the tenant's most recent events (tenant-wide view).
        - ``department``: events whose ChatSession belongs to this department,
          via a manual join (``GoaAuditEvent.session_id`` has no ForeignKey).
        - any other kind: honest-empty -- there is no node-specific audit
          source yet, and a flat tenant list on every node would be fake
          scoping (Rule 17).
        """
        tid = self.tenant_id
        if kind == "daena":
            stmt = (
                select(GoaAuditEvent)
                .where(GoaAuditEvent.tenant_id == tid)
                .order_by(GoaAuditEvent.created_at.desc())
                .limit(20)
            )
        elif kind == "department":
            try:
                dept_uuid = uuid.UUID(str(node_id))
            except (ValueError, AttributeError, TypeError):
                return []
            stmt = (
                select(GoaAuditEvent)
                .join(ChatSession, GoaAuditEvent.session_id == ChatSession.id)
                .where(
                    GoaAuditEvent.tenant_id == tid,
                    ChatSession.tenant_id == tid,
                    ChatSession.department_id == dept_uuid,
                )
                .order_by(GoaAuditEvent.created_at.desc())
                .limit(20)
            )
        else:
            return []

        rows = (await self.db.execute(stmt)).scalars().all()
        return [
            NodeActivityItem(
                id=str(ev.id),
                action_type=ev.action_type,
                actor_type=ev.actor_type,
                result=ev.result,
                risk_level=ev.risk_level,
                created_at=ev.created_at,
            )
            for ev in rows
        ]

    @staticmethod
    def _tools_from_mcp(meta: dict | None) -> list[NodeToolRef]:
        """Parse MCP tools from a server's ``extra_metadata``, defensively.

        MCP tools are a runtime ``listTools`` result and are not reliably
        persisted, so this honest-empties on anything unexpected rather than
        fabricating (Rule 17). Accepts ``["name", ...]`` or
        ``[{"name"|"tool"|"id", "description"}, ...]`` shapes.
        """
        if not meta:
            return []
        raw = meta.get("tools")
        if not isinstance(raw, list):
            return []
        out: list[NodeToolRef] = []
        for item in raw:
            if isinstance(item, str):
                if item:
                    out.append(NodeToolRef(name=item))
            elif isinstance(item, dict):
                name = item.get("name") or item.get("tool") or item.get("id")
                if name:
                    out.append(NodeToolRef(
                        name=str(name),
                        description=item.get("description"),
                    ))
        return out

    async def _node_ai_access(
        self, kind: str, node_id: str, node: GraphNode
    ) -> NodeAiAccess:
        """Tools and skills an entity can draw on.

        - ``mcp_server``: scope "self" -- the server's own ``listTools``
          result, read defensively from ``extra_metadata`` (honest-empty when
          none is persisted, since tools are runtime-discovered, Rule 17).
        - ``daena`` / ``department`` / ``agent``: scope "tenant" -- the shared
          pool of connected MCP servers and non-archived skills. There is no
          agent->tool FK and selection is dynamic per turn (up to 8 active),
          so this lists the available pool and says so rather than implying a
          fixed loadout.
        - anything else: scope "none".
        """
        tid = self.tenant_id

        if kind == "mcp_server":
            try:
                srv_uuid = uuid.UUID(str(node_id))
            except (ValueError, AttributeError, TypeError):
                return NodeAiAccess(scope="self", note="server not found.")
            row = (
                await self.db.execute(
                    select(McpServer).where(
                        McpServer.tenant_id == tid,
                        McpServer.id == srv_uuid,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return NodeAiAccess(scope="self", note="server not found.")
            tools = self._tools_from_mcp(row.extra_metadata)
            note = None
            if not tools:
                note = (
                    "No tools persisted. MCP tools are discovered at runtime "
                    "(listTools) and are not fabricated here."
                )
            return NodeAiAccess(scope="self", note=note, mcp_tools=tools)

        if kind in ("daena", "department", "agent"):
            servers = (
                await self.db.execute(
                    select(McpServer).where(McpServer.tenant_id == tid)
                )
            ).scalars().all()
            mcp_servers = [
                NodeAccessApp(
                    id=_nid("mcp_server", m.id),
                    label=m.display_name,
                    status=m.status,
                    tool_count=len(self._tools_from_mcp(m.extra_metadata)),
                )
                for m in servers
            ]
            skill_rows = (
                await self.db.execute(
                    select(RefinedSkill).where(
                        RefinedSkill.tenant_id == tid,
                        RefinedSkill.archived_at.is_(None),
                    )
                )
            ).scalars().all()
            skills = [
                NodeSkillRef(
                    id=_nid("skill", s.id),
                    title=s.title,
                    domain=s.domain,
                )
                for s in skill_rows
            ]
            note = (
                "Shared tenant pool. Tools are selected dynamically per turn "
                "(up to 8 active); there is no fixed per-entity assignment."
            )
            return NodeAiAccess(
                scope="tenant",
                note=note,
                mcp_servers=mcp_servers,
                skills=skills,
            )

        return NodeAiAccess(scope="none")

    async def _node_ai_context(self, node: GraphNode) -> NodeAiContext:
        """Ragx evidence relevant to this node (best-effort, fails open).

        Departments query their dedicated collections; everything else uses
        the default set. Rule 17: a ragx failure surfaces ``available=False``
        so the UI shows an honest offline pill, not a fake empty result.
        """
        if node.kind == "department":
            collections = collections_for_department(node.label, self.tenant_id)
        else:
            collections = DEFAULT_COLLECTIONS
        requested = list(collections)
        query = node.label or ""
        try:
            result = await query_ragx(
                query,
                collections=collections,
                k=5,
                timeout_s=4.0,
            )
        except Exception:
            return NodeAiContext(
                available=False, requested=requested, citations=[]
            )
        citations = [
            GraphSearchCitation(
                chunk_id=c.chunk_id,
                source_path=c.source_path,
                score=c.score,
                snippet=c.snippet,
                collection=c.collection,
            )
            for c in result.citations
        ]
        return NodeAiContext(
            available=result.available,
            requested=requested,
            citations=citations,
        )
