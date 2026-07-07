/**
 * Governance signal -- the single source of truth for Daena's moat overlay,
 * shared by BOTH Brain lenses (the GraphCanvas physics view and the
 * GraphListView triage table). Extracted from GraphCanvas so the two lenses
 * can never disagree about what counts as "needs attention": one function,
 * one colour convention, two renderers.
 *
 * Every signal binds to a REAL projected field (Rule 17): execution
 * meta.governance_tier, workstream meta.blocker, status. Colours follow
 * Daena's documented tier convention (0-1 logged, 2 notified, 3+ approval).
 */

export const GOV_APPROVAL = '#ef4444' // tier 3+ approval gate, or failed/blocked status
export const GOV_NOTIFY = '#eab308' // tier 2 notified
export const GOV_BLOCKER = '#f59e0b' // workstream/session carrying an open blocker_text

export const SETTLED_STATUS = new Set([
  'completed', 'complete', 'done', 'closed', 'cancelled', 'canceled', 'archived', 'expired',
])
export const ATTENTION_STATUS = new Set(['blocked', 'failed'])

export interface GovSignal {
  /** Ring/glow colour for this signal. */
  ring: string
  /** Paint a glow halo under the node (canvas lens). */
  glow: boolean
  /** Pull to full alpha + glow so a live signal is never hidden by LOD (canvas lens). */
  force: boolean
  /** Dashed ring (open blocker) (canvas lens). */
  dashed: boolean
  /** 0-4, higher = more operator attention. The list lens sorts on this. */
  severity: number
  /** Short human meaning for the list governance cell. */
  label: string
}

/** Minimal structural shape both a force-graph node and a GraphNode satisfy. */
interface GovNode {
  status?: string | null
  meta?: Record<string, unknown> | null
}

/**
 * Returns the loudest governance signal for a node, or null. A SETTLED tier-3+
 * node returns a quiet ring (no glow/force, low severity) so finished work does
 * not glow red forever; only live attention forces full visibility and sorts to
 * the top of the triage list.
 */
export function govSignal(node: GovNode): GovSignal | null {
  const status = String(node.status ?? '').toLowerCase()
  const tier = node.meta?.governance_tier
  if (ATTENTION_STATUS.has(status)) {
    return { ring: GOV_APPROVAL, glow: true, force: true, dashed: false, severity: 4, label: status === 'failed' ? 'Failed' : 'Blocked' }
  }
  if (node.meta?.blocker) {
    return { ring: GOV_BLOCKER, glow: true, force: true, dashed: true, severity: 3, label: 'Open blocker' }
  }
  if (typeof tier === 'number' && tier >= 3) {
    const settled = SETTLED_STATUS.has(status)
    return {
      ring: GOV_APPROVAL,
      glow: !settled,
      force: !settled,
      dashed: false,
      severity: settled ? 1 : 3,
      label: settled ? `Tier ${tier} (settled)` : `Tier ${tier} approval`,
    }
  }
  if (typeof tier === 'number' && tier === 2) {
    return { ring: GOV_NOTIFY, glow: false, force: false, dashed: false, severity: 2, label: 'Tier 2 notify' }
  }
  return null
}
