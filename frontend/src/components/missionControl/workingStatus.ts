import type { GraphData, GraphNode } from '@/lib/graphApi'

/**
 * Single source of truth for "is this node actively working right now".
 *
 * Shared by the BrainCanvas working-ring, the StatsRibbon "N working" pill, and
 * the adaptive poll cadence on /brain so all three agree BY CONSTRUCTION -- one
 * copy means the count can never claim work the ring does not show, nor the poll
 * speed up for work nothing else reflects (Rule 5: no second copy that drifts;
 * Rule 17 / ADR-001: the UI must not narrate live activity it cannot back).
 *
 * 'active' is deliberately excluded: the grounded architecture fallback marks
 * every node 'active', and that must read as IDLE, not working -- otherwise a
 * representative diagram would masquerade as a fully-busy live org.
 */
export const WORKING_STATUS = new Set([
  'running',
  'executing',
  'in_progress',
  'in-progress',
  'working',
  'processing',
  'busy',
])

/** True only when the node carries a genuine working status (case-insensitive). */
export function isWorking(node: Pick<GraphNode, 'status'>): boolean {
  return WORKING_STATUS.has(String(node.status ?? '').toLowerCase())
}

/** How many nodes in this projection are actively working (0 under fallback). */
export function countWorking(data: GraphData | null): number {
  if (!data?.nodes) return 0
  let n = 0
  for (const node of data.nodes) if (isWorking(node)) n++
  return n
}
