/**
 * GovernanceEventStrip -- inline cards for governance events in chat.
 *
 * Subscribes to ``chatStore.governanceEvents`` and renders a stacked
 * column of actionable cards:
 *
 * - ``approval_pending`` -> amber card with Approve / Reject buttons.
 *   Clicking either calls ``/governance/approvals/{id}/decide`` and
 *   removes the card on success.
 * - ``tool_blocked``     -> red notice showing the reason. Dismissible.
 * - ``vp_plan``          -> informational pill showing routed depts.
 * - ``vp_subtasks_created`` -> pill with a "View tasks" link to /tasks.
 *
 * Mount once near the chat input. It auto-hides when the event list
 * is empty. State is Zustand so it survives stream finalize and is
 * shared across the chat view and any other surface that wants to
 * react to the same events.
 */
import { AnimatePresence, motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { Shield, Check, X, AlertTriangle, Compass, ListTodo } from 'lucide-react'
import { useChatStore, type GovernanceEvent } from '@/stores/chatStore'

export function GovernanceEventStrip() {
  const events = useChatStore((s) => s.governanceEvents)
  const dismiss = useChatStore((s) => s.dismissGovernanceEvent)
  const resolveApproval = useChatStore((s) => s.resolveApproval)

  if (events.length === 0) return null

  return (
    <div className="flex flex-col gap-2 mb-2">
      <AnimatePresence mode="popLayout">
        {events.map((evt) => (
          <motion.div
            key={evt.id}
            layout
            initial={{ opacity: 0, y: 8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.95 }}
            transition={{ duration: 0.18 }}
          >
            <GovernanceCard
              event={evt}
              onDismiss={() => dismiss(evt.id)}
              onDecide={resolveApproval}
            />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

interface CardProps {
  event: GovernanceEvent
  onDismiss: () => void
  onDecide: (
    approvalId: string,
    decision: 'APPROVED' | 'REJECTED',
    reason?: string,
  ) => Promise<void>
}

function GovernanceCard({ event, onDismiss, onDecide }: CardProps) {
  if (event.kind === 'approval_pending') {
    const { tool, approvalId, reason, riskTier } = event
    return (
      <div className="flex items-start gap-3 px-4 py-3 rounded-lg border border-accent-amber/40 bg-accent-amber/10 backdrop-blur-sm">
        <Shield size={18} className="text-accent-amber shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs font-medium text-starlight-100">
              Approval needed to run{' '}
              <span className="font-mono text-accent-amber">{tool}</span>
            </p>
            {typeof riskTier === 'number' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-accent-amber/20 text-accent-amber font-medium">
                tier {riskTier}
              </span>
            )}
          </div>
          {reason && (
            <p className="text-[11px] text-starlight-400 mt-1 leading-relaxed">
              {reason}
            </p>
          )}
          <div className="flex items-center gap-2 mt-2">
            <button
              disabled={!approvalId}
              onClick={() => approvalId && onDecide(approvalId, 'APPROVED')}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium bg-status-success/20 text-status-success hover:bg-status-success/30 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Check size={12} />
              Approve
            </button>
            <button
              disabled={!approvalId}
              onClick={() => approvalId && onDecide(approvalId, 'REJECTED')}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium bg-status-error/20 text-status-error hover:bg-status-error/30 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <X size={12} />
              Reject
            </button>
            <Link
              to="/governance/approvals"
              className="text-[11px] text-starlight-400 hover:text-starlight-100 transition-colors px-1"
            >
              View details
            </Link>
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="text-starlight-500 hover:text-starlight-200 transition-colors cursor-pointer shrink-0"
          title="Dismiss"
        >
          <X size={14} />
        </button>
      </div>
    )
  }

  if (event.kind === 'tool_blocked') {
    return (
      <div className="flex items-start gap-3 px-4 py-2.5 rounded-lg border border-status-error/40 bg-status-error/10 backdrop-blur-sm">
        <AlertTriangle size={16} className="text-status-error shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-starlight-100">
            Blocked: <span className="font-mono text-status-error">{event.tool}</span>
          </p>
          {event.reason && (
            <p className="text-[11px] text-starlight-400 mt-0.5 leading-relaxed">
              {event.reason}
            </p>
          )}
        </div>
        <button
          onClick={onDismiss}
          className="text-starlight-500 hover:text-starlight-200 transition-colors cursor-pointer shrink-0"
          title="Dismiss"
        >
          <X size={14} />
        </button>
      </div>
    )
  }

  if (event.kind === 'vp_plan') {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-accent-cyan/30 bg-accent-cyan/5">
        <Compass size={14} className="text-accent-cyan shrink-0" />
        <p className="text-[11px] text-starlight-300 flex-1">
          VP routed to{' '}
          <span className="font-medium text-accent-cyan">
            {event.departments.join(' + ')}
          </span>
        </p>
        <button
          onClick={onDismiss}
          className="text-starlight-500 hover:text-starlight-200 transition-colors cursor-pointer"
          title="Dismiss"
        >
          <X size={12} />
        </button>
      </div>
    )
  }

  if (event.kind === 'vp_subtasks_created') {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-status-info/30 bg-status-info/5">
        <ListTodo size={14} className="text-status-info shrink-0" />
        <p className="text-[11px] text-starlight-300 flex-1">
          <span className="font-medium text-status-info">
            {event.count} task{event.count === 1 ? '' : 's'} queued
          </span>{' '}
          across {event.departments.join(', ')}
        </p>
        <Link
          to="/tasks"
          className="text-[11px] text-accent-cyan hover:text-accent-cyan/80 transition-colors px-1"
        >
          View
        </Link>
        <button
          onClick={onDismiss}
          className="text-starlight-500 hover:text-starlight-200 transition-colors cursor-pointer"
          title="Dismiss"
        >
          <X size={12} />
        </button>
      </div>
    )
  }

  return null
}

export default GovernanceEventStrip
