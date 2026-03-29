/**
 * ExecutionPanel (Phase 5): collapsible panel showing real-time
 * task decomposition, runtime assignment, and execution progress.
 *
 * When toggled OFF, the backend still executes and logs everything
 * but skips WebSocket streaming of intermediate steps, saving tokens.
 */
import { useState, memo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  Clock,
  DollarSign,
  Zap,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  PauseCircle,
  ExternalLink,
} from 'lucide-react'
import { Card, Badge } from '@/components/common'
import type { SubTaskResponse, SubTaskStatus } from '@/types/api'

// ── Status config ──

interface StatusConfig {
  label: string
  icon: React.ReactNode
  className: string
  badgeVariant: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple'
}

const STATUS_MAP: Record<SubTaskStatus, StatusConfig> = {
  pending: {
    label: 'Pending',
    icon: <Clock size={14} />,
    className: 'exec-status-pending',
    badgeVariant: 'warning',
  },
  running: {
    label: 'Running',
    icon: <Loader2 size={14} className="animate-spin" />,
    className: 'exec-status-running',
    badgeVariant: 'info',
  },
  complete: {
    label: 'Complete',
    icon: <CheckCircle2 size={14} />,
    className: 'exec-status-complete',
    badgeVariant: 'success',
  },
  failed: {
    label: 'Failed',
    icon: <XCircle size={14} />,
    className: 'exec-status-failed',
    badgeVariant: 'danger',
  },
  rejected: {
    label: 'Approval Required',
    icon: <PauseCircle size={14} />,
    className: 'exec-status-approval',
    badgeVariant: 'purple',
  },
  cancelled: {
    label: 'Cancelled',
    icon: <AlertTriangle size={14} />,
    className: 'exec-status-pending',
    badgeVariant: 'default',
  },
}

// ── SubtaskRow ──

interface SubtaskRowProps {
  subtask: SubTaskResponse
}

const SubtaskRow = memo(function SubtaskRow({ subtask }: SubtaskRowProps) {
  const [expanded, setExpanded] = useState(false)
  const config = STATUS_MAP[subtask.status] ?? STATUS_MAP.pending

  const durationLabel = subtask.duration_ms
    ? subtask.duration_ms < 1000
      ? `${subtask.duration_ms}ms`
      : `${(subtask.duration_ms / 1000).toFixed(1)}s`
    : null

  const costLabel = subtask.actual_cost_usd != null
    ? `$${subtask.actual_cost_usd.toFixed(4)}`
    : subtask.estimated_cost_usd > 0
      ? `~$${subtask.estimated_cost_usd.toFixed(4)}`
      : 'free'

  return (
    <div className="border-b border-white/5 last:border-b-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/[0.02] transition-colors text-left"
      >
        {/* Expand arrow */}
        <span className="text-starlight-400">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>

        {/* Runtime badge */}
        <span className="text-[10px] font-mono text-starlight-300 bg-midnight-400 px-1.5 py-0.5 rounded min-w-[70px] text-center truncate">
          {subtask.assigned_runtime}
        </span>

        {/* Description */}
        <span className="flex-1 text-sm text-starlight-200 truncate">
          {subtask.description}
        </span>

        {/* Status pill */}
        <span className={`exec-status-pill ${config.className}`}>
          {config.icon}
          {config.label}
        </span>

        {/* Duration */}
        {durationLabel && (
          <span className="text-xs text-starlight-400 min-w-[50px] text-right">
            {durationLabel}
          </span>
        )}

        {/* Cost */}
        <span className="text-xs text-starlight-400 min-w-[60px] text-right">
          {costLabel}
        </span>
      </button>

      {/* Expanded output */}
      <AnimatePresence>
        {expanded && subtask.result_data != null && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-3 pl-10">
              <pre className="text-xs text-starlight-300 bg-midnight-900/50 rounded-lg p-3 overflow-x-auto max-h-48 whitespace-pre-wrap">
                {typeof subtask.result_data === 'string'
                  ? subtask.result_data
                  : JSON.stringify(subtask.result_data, null, 2)}
              </pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
})

// ── ExecutionPanel ──

interface ExecutionPanelProps {
  subtasks: SubTaskResponse[]
  taskDescription?: string
  totalCost?: number
  totalTime?: number
  runtimesUsed?: string[]
  visible: boolean
  onToggle: () => void
  className?: string
}

export function ExecutionPanel({
  subtasks,
  taskDescription,
  totalCost = 0,
  totalTime = 0,
  runtimesUsed = [],
  visible,
  onToggle,
  className = '',
}: ExecutionPanelProps) {
  const running = subtasks.filter((s) => s.status === 'running').length
  const complete = subtasks.filter((s) => s.status === 'complete').length
  const failed = subtasks.filter((s) => s.status === 'failed').length
  const total = subtasks.length

  const timeLabel = totalTime < 1000
    ? `${totalTime}ms`
    : `${(totalTime / 1000).toFixed(1)}s`

  return (
    <Card variant="glass" padding="none" className={`overflow-hidden ${className}`}>
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div className="flex items-center gap-3">
          <Zap size={16} className="text-accent-amber" />
          <span className="text-sm font-medium text-starlight-100">
            Execution View
          </span>
          {total > 0 && (
            <span className="text-xs text-starlight-400">
              {running > 0
                ? `Running ${running} of ${total} subtasks across ${runtimesUsed.length} runtime${runtimesUsed.length !== 1 ? 's' : ''}`
                : `${complete}/${total} complete${failed > 0 ? `, ${failed} failed` : ''}`}
            </span>
          )}
        </div>

        <button
          onClick={onToggle}
          className="flex items-center gap-1.5 text-xs text-starlight-400 hover:text-starlight-200 transition-colors"
          title={visible ? 'Hide execution details (saves tokens)' : 'Show execution details'}
        >
          {visible ? <Eye size={14} /> : <EyeOff size={14} />}
          {visible ? 'On' : 'Off'}
        </button>
      </div>

      {/* Task description */}
      {taskDescription && visible && (
        <div className="px-4 py-2 border-b border-white/5 bg-midnight-900/30">
          <p className="text-xs text-starlight-300 truncate">{taskDescription}</p>
        </div>
      )}

      {/* Subtask list */}
      <AnimatePresence>
        {visible && subtasks.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden max-h-80 overflow-y-auto"
          >
            {subtasks.map((subtask) => (
              <SubtaskRow key={subtask.id} subtask={subtask} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Footer stats */}
      {visible && total > 0 && (
        <div className="flex items-center gap-4 px-4 py-2 border-t border-white/5 bg-midnight-900/20">
          <span className="flex items-center gap-1 text-xs text-starlight-400">
            <Clock size={12} />
            {timeLabel}
          </span>
          <span className="flex items-center gap-1 text-xs text-starlight-400">
            <DollarSign size={12} />
            ${totalCost.toFixed(4)}
          </span>
          <span className="flex items-center gap-1 text-xs text-starlight-400">
            <Zap size={12} />
            {total} subtask{total !== 1 ? 's' : ''}
          </span>
          <span className="ml-auto">
            <a
              href="/governance/audit"
              className="flex items-center gap-1 text-[10px] text-starlight-400 hover:text-primary-400 transition-colors"
            >
              <ExternalLink size={10} />
              Full Audit Trail
            </a>
          </span>
        </div>
      )}

      {/* Empty state when visible but no tasks */}
      {visible && total === 0 && (
        <div className="px-4 py-6 text-center">
          <p className="text-xs text-starlight-400">No active execution tasks</p>
        </div>
      )}
    </Card>
  )
}

export default ExecutionPanel
