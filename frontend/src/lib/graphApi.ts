import { api } from '@/lib/api'

export interface GraphNode {
  id: string
  kind: string
  label: string
  status?: string | null
  department_id?: string | null
  sunflower_index?: number | null
  meta?: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  rel: string
  weight: number
}

export interface GraphStats {
  node_count: number
  edge_count: number
  by_kind: Record<string, number>
  generated_at: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: GraphStats
}

export interface GraphQuery {
  kinds?: string
  center?: string
  depth?: number
  limit?: number
}

/**
 * Read-only Mission Control graph projection.
 * The backend envelope is { success, data }, and lib/api.ts does not unwrap,
 * so we reach through res.data.data here.
 */
export async function fetchGraph(params?: GraphQuery): Promise<GraphData> {
  // The /graph response carries `Cache-Control: private, max-age=30` (graph.py),
  // whose "low-write graph" premise is false for the working layer: task and
  // execution statuses flip on a seconds cadence, so a 30s browser cache makes
  // the brain poll replay a stale snapshot and a RUNNING ring never appears
  // (proven: cache-busted fetch sees working=1 while the cached path sees 0).
  // A unique timestamp gives each poll its own URL so the browser cache cannot
  // satisfy it from the 30s entry -- the canvas reads genuinely live state
  // (Rule 17: never narrate stale data as live). The backend ignores the extra
  // param; SSE push remains the eventual best-in-class upgrade.
  const res = await api.get('/graph', { params: { ...params, _: Date.now() } })
  return res.data.data as GraphData
}

export interface GraphSearchCitation {
  chunk_id: string
  source_path: string
  score: number
  snippet: string
  collection: string
}

export interface GraphSearchResponse {
  matched_node_ids: string[]
  citations: GraphSearchCitation[]
  available: boolean
}

/**
 * PR-4 ragx-highlight semantic search. `available=false` means ragx was
 * offline or abstained on every collection; the UI MUST surface that honestly
 * per Rule 17 instead of pretending nothing matched.
 */
export async function searchGraph(q: string): Promise<GraphSearchResponse> {
  const res = await api.post('/graph/search', { q })
  return res.data.data as GraphSearchResponse
}

// --- PR-5: node detail (Activity / AI Access / AI Context tabs) --------------

export interface GraphNeighbor {
  id: string
  kind: string
  label: string
  rel: string
  direction: 'in' | 'out'
}

export interface NodeActivityItem {
  id: string
  action_type: string
  actor_type?: string | null
  result?: string | null
  risk_level?: string | null
  created_at: string
}

export interface NodeToolRef {
  name: string
  description?: string | null
}

export interface NodeAccessApp {
  id: string
  label: string
  status?: string | null
  tool_count: number
}

export interface NodeSkillRef {
  id: string
  title: string
  domain?: string | null
}

export interface NodeAiAccess {
  scope: string // "self" | "tenant" | "none"
  note?: string | null
  mcp_servers: NodeAccessApp[]
  mcp_tools: NodeToolRef[]
  skills: NodeSkillRef[]
}

export interface NodeAiContext {
  available: boolean
  requested: string[]
  citations: GraphSearchCitation[]
}

export interface NodeDetail {
  node: GraphNode
  neighbors: GraphNeighbor[]
  detail: Record<string, unknown>
  activity: NodeActivityItem[]
  ai_access: NodeAiAccess
  ai_context: NodeAiContext
}

/**
 * PR-5 node detail. `fullId` is "{kind}:{raw}" (e.g. "mcp_server:<uuid>" or
 * "daena:root"); we split on the FIRST colon only, because a raw id can itself
 * contain colons. A 404 (cross-tenant id or unknown kind) propagates as a
 * rejected promise for the store to surface honestly (Rule 17).
 */
export async function fetchNodeDetail(fullId: string): Promise<NodeDetail> {
  const idx = fullId.indexOf(':')
  const kind = idx >= 0 ? fullId.slice(0, idx) : fullId
  const raw = idx >= 0 ? fullId.slice(idx + 1) : ''
  const res = await api.get(
    `/graph/node/${encodeURIComponent(kind)}/${encodeURIComponent(raw)}`,
  )
  return res.data.data as NodeDetail
}
