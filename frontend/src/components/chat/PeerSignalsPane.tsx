/**
 * PeerSignalsPane -- right-side pane inside a department's chat room.
 *
 * Renders the live feed from the department's BorderAgent: relevance-
 * filtered events from peer departments + Daena's own observations.
 * Replaces the deleted DepartmentInbox page (which was a separate
 * route, violating the "capabilities live in the department room"
 * principle).
 *
 * Design notes:
 * - Newest first; the hook already sorts that way.
 * - Signals are read-only. Clicking could future-expand to a drawer
 *   with the full payload, but for now we render a compact card.
 * - Empty state explicitly names the department so the user knows
 *   the pane is scoped to this room, not company-wide.
 * - Styling uses the same Badge + time-ago helpers the rest of the
 *   chat surface uses for visual coherence.
 */
import { useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  Flag,
  TrendingUp,
  DollarSign,
  FileCheck,
  Signal as SignalIcon,
  Radio,
} from 'lucide-react'
import { Badge } from '@/components/common'
import { useDepartmentSignals, type PeerSignal } from '@/hooks/useDepartmentSignals'

interface PeerSignalsPaneProps {
  departmentName: string | undefined
  collapsed?: boolean
  /**
   * Optional title override. Defaults to "Peer Signals" which fits
   * department rooms (Sales / Legal / etc.). Main ChatPage passes
   * "Company-wide" since the mounted department is Daena's wildcard
   * inbox and "peer" is misleading at the VP lens.
   */
  title?: string
}

// Event-type -> (icon, variant) mapping for the badge next to each
// signal. Defaults to "info" + Activity when the event is unknown.
const EVENT_ICON: Record<string, { icon: React.ReactNode; variant: 'default' | 'info' | 'warning' | 'success' | 'danger' }> = {
  'department.task_started':      { icon: <Activity size={11} />,       variant: 'info' },
  'department.task_completed':    { icon: <CheckCircle2 size={11} />,   variant: 'success' },
  'department.task_rejected':     { icon: <XCircle size={11} />,        variant: 'danger' },
  'department.task_failed':       { icon: <AlertTriangle size={11} />,  variant: 'warning' },
  'department.flagged_risk':      { icon: <Flag size={11} />,           variant: 'warning' },
  'department.needs_input':       { icon: <Flag size={11} />,           variant: 'info' },
  'Sales.proposal_sent':          { icon: <TrendingUp size={11} />,     variant: 'info' },
  'Sales.closed_deal':            { icon: <TrendingUp size={11} />,     variant: 'success' },
  'Sales.lost_deal':              { icon: <XCircle size={11} />,        variant: 'default' },
  'Legal.contract_signed':        { icon: <FileCheck size={11} />,      variant: 'success' },
  'Legal.compliance_flag':        { icon: <ShieldAlert size={11} />,    variant: 'warning' },
  'Finance.expense_proposal':     { icon: <DollarSign size={11} />,     variant: 'info' },
  'Finance.expense_approved':     { icon: <DollarSign size={11} />,     variant: 'success' },
  'SecurityOps.threat_detected':  { icon: <ShieldAlert size={11} />,    variant: 'danger' },
  'SecurityOps.incident':         { icon: <ShieldAlert size={11} />,    variant: 'danger' },
  'Governance.tier_high':         { icon: <ShieldAlert size={11} />,    variant: 'warning' },
}

function formatRelativeTime(epochSeconds: number): string {
  const diff = Math.max(0, Date.now() / 1000 - epochSeconds)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function summarizePayload(payload: Record<string, unknown>): string {
  // Prefer human-readable task_summary when present; otherwise pick the
  // first two string/number fields to avoid rendering a JSON blob.
  if (typeof payload.task_summary === 'string') return payload.task_summary
  const entries: string[] = []
  for (const [k, v] of Object.entries(payload)) {
    if (k.startsWith('_')) continue
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
      entries.push(`${k}: ${v}`)
    }
    if (entries.length >= 2) break
  }
  return entries.join(' -- ')
}

export function PeerSignalsPane({
  departmentName,
  collapsed = false,
  title = 'Peer Signals',
}: PeerSignalsPaneProps) {
  const { signals, loading, error } = useDepartmentSignals(departmentName, 50)

  const grouped = useMemo(() => signals, [signals])

  if (collapsed) return null

  // Self-explanatory title hover so first-time viewers don't have to
  // guess what "Company-wide" means. The wildcard "Daena" department
  // shows cross-team events; a real department name shows just-that-
  // room's events. (See module docstring + audit 2026-04-23.)
  const headerHelp =
    departmentName === 'Daena' || !departmentName
      ? 'Cross-department activity feed: scans, approvals, drafts, and other events from every team. Updates in real time as work happens anywhere in Daena.'
      : `Activity feed scoped to the ${departmentName} department. Events from peer departments that match this department's relevance lens also appear here.`

  return (
    <div className="h-full w-80 shrink-0 border-l border-white/5 bg-midnight-300/20 flex flex-col">
      <div
        className="shrink-0 flex items-center gap-2 px-3 py-2.5 border-b border-white/5"
        title={headerHelp}
      >
        <Radio size={14} className="text-accent-cyan" />
        <p className="text-xs font-medium text-starlight-100">{title}</p>
        <span className="text-[10px] text-starlight-500 ml-auto">
          {loading ? '...' : `${signals.length} visible`}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {error && (
          <p className="text-[11px] text-status-error px-2">Poll error: {error}</p>
        )}
        {!loading && signals.length === 0 && !error && (
          <div className="text-[11px] text-starlight-500 text-center py-6 leading-relaxed">
            No peer signals yet for <strong>{departmentName || 'this department'}</strong>.
            <br />
            Events from peer departments that match this department's
            relevance lens will appear here in real time.
          </div>
        )}
        <AnimatePresence initial={false}>
          {grouped.map((sig: PeerSignal) => {
            const meta = EVENT_ICON[sig.event_type] ?? {
              icon: <SignalIcon size={11} />,
              variant: 'info' as const,
            }
            return (
              <motion.div
                key={sig.id}
                initial={{ opacity: 0, x: 6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 6 }}
                transition={{ duration: 0.12 }}
                className="p-2 rounded-md bg-midnight-400/40 border border-white/5"
              >
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={meta.variant}>
                    <span className="flex items-center gap-1">
                      {meta.icon}
                      {sig.source_department}
                    </span>
                  </Badge>
                  <span className="text-[10px] text-starlight-500 ml-auto">
                    {formatRelativeTime(sig.created_at)}
                  </span>
                </div>
                <p className="text-[11px] text-starlight-200 leading-snug">
                  {summarizePayload(sig.payload) || sig.event_type}
                </p>
                {sig.relevant_because && (
                  <p className="text-[10px] text-starlight-500 mt-1 italic truncate" title={sig.relevant_because}>
                    matched {sig.relevant_because}
                  </p>
                )}
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </div>
  )
}

export default PeerSignalsPane
