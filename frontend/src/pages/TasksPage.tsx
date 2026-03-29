/**
 * TasksPage — background tasks and autopilot status.
 * Shows running, paused, completed, and failed tasks.
 */
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  Loader2,
  ListTodo,
  RefreshCw,
  Filter,
  Archive,
  Trash2,
  CheckSquare,
  Square,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import type { TaskResponse, TaskStatus, ApiResponse } from '@/types/api'

const STATUS_CONFIG: Record<TaskStatus, { label: string; variant: string; icon: React.ReactNode }> = {
  PENDING:   { label: 'Pending',   variant: 'default',  icon: <Clock size={12} /> },
  RUNNING:   { label: 'Running',   variant: 'info',     icon: <Loader2 size={12} className="animate-spin" /> },
  PAUSED:    { label: 'Paused',    variant: 'warning',  icon: <Pause size={12} /> },
  COMPLETED: { label: 'Done',      variant: 'success',  icon: <CheckCircle2 size={12} /> },
  FAILED:    { label: 'Failed',    variant: 'danger',   icon: <XCircle size={12} /> },
  CANCELLED: { label: 'Cancelled', variant: 'default',  icon: <RotateCcw size={12} /> },
}

export function TasksPage() {
  usePageTitle('Tasks')
  const [tasks, setTasks] = useState<TaskResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<TaskStatus | 'ALL'>('ALL')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [retryingId, setRetryingId] = useState<string | null>(null)

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const params = filter !== 'ALL' ? `?status=${filter}` : ''
      const { data } = await api.get<ApiResponse<TaskResponse[]>>(`/execution/tasks${params}`)
      setTasks(data.data || [])
    } catch {
      setTasks([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchTasks() }, [filter])

  // ── Selection helpers ──
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })
  }
  const toggleSelectAll = () => {
    setSelectedIds(selectedIds.size === tasks.length ? new Set() : new Set(tasks.map((t) => t.id)))
  }

  // ── Retry a failed task (re-enqueue as PENDING) ──
  const handleRetry = async (taskId: string) => {
    setRetryingId(taskId)
    try {
      await api.patch(`/execution/tasks/${taskId}`, { status: 'PENDING' })
      await fetchTasks()
    } catch {
      // Graceful
    } finally {
      setRetryingId(null)
    }
  }

  // ── Batch archive ──
  const handleBatchArchive = async () => {
    for (const id of selectedIds) {
      try { await api.patch(`/execution/tasks/${id}`, { status: 'CANCELLED' }) } catch { /* skip */ }
    }
    setSelectedIds(new Set())
    await fetchTasks()
  }

  // ── Batch delete ──
  const handleBatchDelete = async () => {
    if (!confirm(`Delete ${selectedIds.size} task(s)? This cannot be undone.`)) return
    for (const id of selectedIds) {
      try { await api.delete(`/execution/tasks/${id}`) } catch { /* skip */ }
    }
    setSelectedIds(new Set())
    await fetchTasks()
  }

  const filtered = tasks

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-accent-cyan/15">
              <ListTodo size={22} className="text-accent-cyan" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold text-starlight-100">Task Manager</h1>
              <p className="text-sm text-starlight-400">Background tasks and autopilot status</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={fetchTasks}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </Button>
        </motion.div>

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <Filter size={14} className="text-starlight-500" />
          {['ALL', 'RUNNING', 'PENDING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED'].map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s as TaskStatus | 'ALL')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                filter === s
                  ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                  : 'text-starlight-400 hover:text-starlight-200 border border-transparent'
              }`}
            >
              {s === 'ALL' ? 'All' : STATUS_CONFIG[s as TaskStatus]?.label || s}
            </button>
          ))}
        </div>

        {/* Batch action bar */}
        {tasks.length > 0 && (
          <div className="flex items-center gap-3 px-1">
            <button onClick={toggleSelectAll} className="flex items-center gap-1.5 text-xs text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer">
              {selectedIds.size === tasks.length && tasks.length > 0
                ? <CheckSquare size={14} className="text-primary-400" />
                : <Square size={14} />}
              {selectedIds.size > 0 ? `${selectedIds.size} selected` : 'Select all'}
            </button>
            {selectedIds.size > 0 && (
              <>
                <div className="w-px h-4 bg-white/10" />
                <button onClick={handleBatchArchive} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 transition-colors cursor-pointer">
                  <Archive size={11} /> Archive
                </button>
                <button onClick={handleBatchDelete} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-accent-red/10 text-accent-red hover:bg-accent-red/20 transition-colors cursor-pointer">
                  <Trash2 size={11} /> Delete
                </button>
              </>
            )}
          </div>
        )}

        {/* Task list */}
        {loading ? (
          <Shimmer count={4} layout="list" />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={ListTodo}
            title={filter === 'ALL' ? 'No active tasks' : `No ${STATUS_CONFIG[filter as TaskStatus]?.label.toLowerCase() || ''} tasks`}
            description="Tasks appear here when Daena runs background operations in Autopilot mode"
          />
        ) : (
          <div className="space-y-3">
            <AnimatePresence mode="popLayout">
              {filtered.map((task, i) => {
                const cfg = STATUS_CONFIG[task.status]
                return (
                  <motion.div
                    key={task.id}
                    layout
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                  >
                    <Card variant="glass" padding="md" className="hover:border-white/10 transition-all">
                      <div className="flex items-start gap-3">
                        {/* Checkbox */}
                        <button onClick={() => toggleSelect(task.id)} className="shrink-0 mt-0.5 text-starlight-500 hover:text-primary-400 transition-colors cursor-pointer">
                          {selectedIds.has(task.id) ? <CheckSquare size={14} className="text-primary-400" /> : <Square size={14} />}
                        </button>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant={cfg.variant as 'info' | 'success' | 'danger' | 'warning' | 'default'}>
                              <span className="flex items-center gap-1">{cfg.icon} {cfg.label}</span>
                            </Badge>
                          </div>
                          <p className="text-sm font-medium text-starlight-200 mb-1">{task.name}</p>
                          {task.description && (
                            <p className="text-xs text-starlight-500 mb-2">{task.description}</p>
                          )}

                          {/* Progress bar */}
                          {(task.status === 'RUNNING' || task.status === 'PAUSED') && (
                            <div className="w-full h-1.5 rounded-full bg-midnight-500 overflow-hidden">
                              <motion.div
                                className="h-full rounded-full bg-gradient-to-r from-primary-500 to-accent-cyan"
                                initial={{ width: 0 }}
                                animate={{ width: `${task.progress}%` }}
                                transition={{ duration: 0.5 }}
                              />
                            </div>
                          )}

                          <div className="flex items-center gap-3 mt-2 text-[10px] text-starlight-500">
                            {task.started_at && (
                              <span className="flex items-center gap-1">
                                <Play size={10} />
                                Started {new Date(task.started_at).toLocaleString()}
                              </span>
                            )}
                            {task.completed_at && (
                              <span className="flex items-center gap-1">
                                <CheckCircle2 size={10} />
                                Completed {new Date(task.completed_at).toLocaleString()}
                              </span>
                            )}
                            <span>{task.progress}%</span>
                          </div>

                          {task.error && (
                            <p className="mt-2 text-[11px] text-status-error bg-status-error/5 px-2 py-1 rounded border border-status-error/10">
                              {task.error}
                            </p>
                          )}
                        </div>

                        {/* Retry button for failed tasks */}
                        {task.status === 'FAILED' && (
                          <button
                            onClick={() => handleRetry(task.id)}
                            disabled={retryingId === task.id}
                            className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 transition-colors cursor-pointer disabled:opacity-50"
                          >
                            {retryingId === task.id
                              ? <Loader2 size={12} className="animate-spin" />
                              : <RotateCcw size={12} />}
                            Retry
                          </button>
                        )}
                      </div>
                    </Card>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  )
}

export default TasksPage
