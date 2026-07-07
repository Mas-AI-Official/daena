/**
 * Grounded fallback brain -- a client-side GraphData built from Daena's
 * architectural constants (the 10 DEFAULT_DEPARTMENTS + the 6 SubCapability
 * limbs in app/core/constants.py), shape-identical to the backend's
 * graph_service.py projection.
 *
 * WHY: the live org graph comes from GET /api/v1/graph. When that endpoint is
 * unreachable (backend down) the Brain would otherwise render only a red error
 * and the founder cannot see the org at all. This module lets the canvas paint
 * the *architecture* (root -> 6 faculties -> 10 departments -> 6 limb-agents
 * each -> representative MCP synapses) so the Brain is always legible.
 *
 * HONESTY (Rule 17): this is the STATIC architecture, not live telemetry. The
 * caller MUST surface that distinction (MissionControlPage renders a
 * "representative architecture -- backend offline" banner over the canvas).
 * The instant /graph returns real data, the store replaces this and the banner
 * disappears -- so the degrade is honest and self-clearing.
 *
 * BYTE-COMPATIBILITY: node ids use the backend `{kind}:{raw}` form and edges
 * use the `{source}->__{target}__{rel}` id format and the same `rel` vocabulary
 * (embodies / contains / employs / runs) so GraphCanvas's edge-driven parent
 * derivation, capIndex ordering, and per-kind coloring all behave exactly as
 * they do for the live projection. Source of truth:
 *   backend/app/core/constants.py  (SubCapability, DEFAULT_DEPARTMENTS)
 *   backend/app/services/graph_service.py  (projection shape)
 */
import type { GraphData, GraphEdge, GraphNode } from '@/lib/graphApi'

const ROOT_ID = 'daena:root'

/** The 6 sub-capabilities every department agent has (constants.SubCapability). */
const SUB_CAPABILITIES: ReadonlyArray<{ cap: string; role: string }> = [
  { cap: 'MIND', role: 'Reasoning, planning' },
  { cap: 'EYES', role: 'Observation, monitoring' },
  { cap: 'HANDS', role: 'Execution, building' },
  { cap: 'VOICE', role: 'Communication, reporting' },
  { cap: 'SHIELD', role: 'Protection, validation' },
  { cap: 'MEMORY', role: 'Knowledge, recall' },
]

/** The 10 default departments (constants.DEFAULT_DEPARTMENTS), ordered by index. */
const DEPARTMENTS: ReadonlyArray<{ name: string; description: string }> = [
  { name: 'Engineering', description: 'Code generation, testing, debugging, deployment, and repository management' },
  { name: 'Product', description: 'Feature definition, backlog prioritization, spec writing, and metric tracking' },
  { name: 'Marketing', description: 'Content creation, SEO optimization, social media, and email campaigns' },
  { name: 'Sales', description: 'Lead generation, outreach, CRM updates, pipeline tracking, and proposals' },
  { name: 'Finance', description: 'Budgets, expense tracking, invoicing, forecasting, and grant applications' },
  { name: 'Operations', description: 'Project management, scheduling, process automation, and vendor coordination' },
  { name: 'Research', description: 'Market research, competitive analysis, tech scouting, and deep search' },
  { name: 'Legal & Compliance', description: 'Contract review, IP tracking, regulatory compliance, and privacy' },
  { name: 'Skill Governance', description: 'Skill extraction, refinement, quality scoring, and knowledge curation' },
  { name: 'Security Operations', description: 'Threat detection, access control, vulnerability scanning, and incident response' },
]

/**
 * Representative MCP synapses Daena integrates. These are root-level resources
 * (ROOT -[runs]-> mcp_server), matching graph_service, so they land in the
 * outer phyllotaxis band. Labelled representative -- the live registry replaces
 * them when /graph returns.
 */
const MCP_SERVERS: ReadonlyArray<{ key: string; label: string; description: string }> = [
  { key: 'ragx', label: 'ragx', description: 'Grounded retrieval over Daena code, docs, and shared memory' },
  { key: 'filesystem', label: 'filesystem', description: 'Sandboxed read/write access to the workspace' },
  { key: 'context7', label: 'context7', description: 'Up-to-date library and framework documentation' },
  { key: 'web-search', label: 'web-search', description: 'Live web search and page fetch' },
  { key: 'gmail', label: 'gmail', description: 'Email read, search, and draft' },
  { key: 'calendar', label: 'calendar', description: 'Calendar read and event scheduling' },
  { key: 'notion', label: 'notion', description: 'Notion workspace pages and databases' },
  { key: 'slack', label: 'slack', description: 'Team channel messaging' },
]

const edgeId = (source: string, target: string, rel: string): string =>
  `${source}->__${target}__${rel}`

const edge = (source: string, target: string, rel: string): GraphEdge => ({
  id: edgeId(source, target, rel),
  source,
  target,
  rel,
  weight: 1,
})

/**
 * Build the grounded architecture graph. Pure + deterministic (no network).
 * Node/edge counts: 1 root + 6 faculties + 10 departments + 60 limb-agents +
 * 8 mcp servers = 85 nodes; 6 + 10 + 60 + 8 = 84 edges.
 */
export function buildGroundedBrain(): GraphData {
  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []

  // Root -- Daena herself.
  nodes.push({ id: ROOT_ID, kind: 'daena', label: 'Daena', status: 'active', meta: { source: 'architectural_constant' } })

  // Daena's own six faculties (her mind), an inner ring around the core.
  SUB_CAPABILITIES.forEach(({ cap, role }, idx) => {
    const id = `faculty:${cap}`
    nodes.push({
      id,
      kind: 'faculty',
      label: cap.charAt(0) + cap.slice(1).toLowerCase(), // MIND -> Mind
      status: 'active',
      sunflower_index: idx,
      meta: { sub_capability: cap, role, source: 'architectural_constant', source_ref: 'app.core.constants.SubCapability' },
    })
    edges.push(edge(ROOT_ID, id, 'embodies'))
  })

  // 10 departments on the golden-angle ring, each with its 6 limb-agents.
  DEPARTMENTS.forEach((dept, deptIdx) => {
    const deptId = `department:${deptIdx}`
    nodes.push({
      id: deptId,
      kind: 'department',
      label: dept.name,
      status: 'active',
      sunflower_index: deptIdx,
      meta: { description: dept.description, source: 'architectural_constant' },
    })
    edges.push(edge(ROOT_ID, deptId, 'contains'))

    // Six limb-agents per department (one per sub-capability). Representative
    // of the "department with agents" model -- the live projection swaps in the
    // tenant's real agent rows.
    SUB_CAPABILITIES.forEach(({ cap, role }) => {
      const agentId = `agent:${deptIdx}-${cap}`
      const capTitle = cap.charAt(0) + cap.slice(1).toLowerCase()
      nodes.push({
        id: agentId,
        kind: 'agent',
        label: `${dept.name} ${capTitle}`,
        status: 'active',
        department_id: deptId,
        meta: { sub_capability: cap, role, representative: true },
      })
      edges.push(edge(deptId, agentId, 'employs'))
    })
  })

  // Representative MCP synapses (root-level resources).
  MCP_SERVERS.forEach(({ key, label, description }) => {
    const id = `mcp_server:${key}`
    nodes.push({
      id,
      kind: 'mcp_server',
      label,
      status: 'active',
      meta: { server_key: key, description, representative: true },
    })
    edges.push(edge(ROOT_ID, id, 'runs'))
  })

  const by_kind: Record<string, number> = {}
  for (const n of nodes) by_kind[n.kind] = (by_kind[n.kind] ?? 0) + 1

  return {
    nodes,
    edges,
    stats: {
      node_count: nodes.length,
      edge_count: edges.length,
      by_kind,
      generated_at: new Date().toISOString(),
    },
  }
}
