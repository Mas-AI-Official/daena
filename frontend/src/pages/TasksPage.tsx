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
import { batchDeleteWithToast } from '@/lib/mutations'
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

  // Auto-refresh when running tasks exist
  useEffect(() => {
    const hasRunning = tasks.some(t => t.status === 'RUNNING')
    if (!hasRunning) return
    const interval = setInterval(() => { void fetchTasks() }, 15000)
    return () => clearInterval(interval)
  }, [tasks])

  // ── Selection helpers ──
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })
  }
  const toggleSelectAll = () => {
    setSelectedIds(selectedIds.size === tasks.length ? new Set() : new Set(tasks.map((t) => t.id)))
  }

  // ── Run a PENDING task immediately (new endpoint) ──
  //
  // Before this ticket tasks sat in PENDING forever because there was
  // no worker. /execution/tasks/{id}/run flips the task to RUNNING
  // and spawns an async background runner that drives it to COMPLETED
  // or FAILED. The UI shows progress via existing 15s auto-refresh.

  const handleRun = async (taskId: string) => {
    setRetryingId(taskId)
    try {
      await api.post(`/execution/tasks/${taskId}/run`)
      await fetchTasks()
    } catch {
      // Graceful
    } finally {
      setRetryingId(null)
    }
  }

  // ── Retry a failed/completed/cancelled task ──
  //
  // Chain: PATCH -> PENDING, then POST -> /run. Before the /run
  // endpoint existed, flipping to PENDING did nothing because no
  // worker picked PENDING tasks up -- retry felt like it was "working"
  // but the task never left PENDING. Now retry actually restarts.

  const handleRetry = async (taskId: string) => {
    setRetryingId(taskId)
    try {
      await api.patch(`/execution/tasks/${taskId}`, { status: 'PENDING' })
      await api.post(`/execution/tasks/${taskId}/run`)
      await fetchTasks()
    } catch {
      // Graceful
    } finally {
      setRetryingId(null)
    }
  }

  // ── Batch run (kick off every selected PENDING task) ──
  const handleBatchRun = async () => {
    const runnable = tasks.filter(
      (t) => selectedIds.has(t.id) &&
        ['PENDING', 'FAILED', 'CANCELLED', 'PAUSED'].includes(t.status),
    )
    if (runnable.length === 0) return
    for (const t of runnable) {
      try {
        if (t.status !== 'PENDING') {
          await api.patch(`/execution/tasks/${t.id}`, { status: 'PENDING' })
        }
        await api.post(`/execution/tasks/${t.id}/run`)
      } catch { /* continue */ }
    }
    setSelectedIds(new Set())
    await fetchTasks()
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
  // Uses the centralized batchDeleteWithToast helper so the success/
  // partial-failure/total-failure feedback matches FilesPage,
  // ProjectsPage, and anywhere else that deletes in bulk.
  const handleBatchDelete = async () => {
    const result = await batchDeleteWithToast(
      selectedIds,
      (id) => `/execution/tasks/${id}`,
      { entity: 'task' },
    )
    if (result.succeeded > 0) {
      setSelectedIds(new Set())
      await fetchTasks()
    }
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

        {/* Stats summary */}
        {!loading && tasks.length > 0 && (
          <div className="flex items-center gap-4 px-4 py-3 rounded-xl bg-midnight-400/20 border border-white/5">
            {[
              { status: 'RUNNING', label: 'Running', color: 'text-accent-cyan' },
              { status: 'PENDING', label: 'Queued', color: 'text-starlight-400' },
              { status: 'COMPLETED', label: 'Done', color: 'text-status-success' },
              { status: 'FAILED', label: 'Failed', color: 'text-status-error' },
            ].map(({ status, label, color }) => {
              const count = tasks.filter(t => t.status === status).length
              return (
                <div key={status} className="flex items-center gap-1.5">
                  <span className={`text-lg font-bold ${color}`}>{count}</span>
                  <span className="text-[10px] text-starlight-500">{label}</span>
                </div>
              )
            })}
            <div className="ml-auto text-[10px] text-starlight-500">
              Last updated: {new Date().toLocaleTimeString()}
            </div>
          </div>
        )}

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
                <button onClick={handleBatchRun} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-status-success/10 text-status-success hover:bg-status-success/20 transition-colors cursor-pointer">
                  <Play size={11} /> Run
                </button>
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

                          {task.error ? (
                            <p className="mt-2 text-[11px] text-status-error bg-status-error/5 px-2 py-1 rounded border border-status-error/10">
                              {String(task.error)}
                            </p>
                          ) : null}

                          {task.status === 'COMPLETED' && task.result != null && (
                            <details className="mt-2">
                              <summary className="text-[10px] text-primary-400 cursor-pointer hover:text-primary-300">
                                View result
                              </summary>
                              <pre className="mt-1 text-[10px] text-starlight-400 bg-midnight-900/50 rounded-lg p-2 overflow-x-auto max-h-32 whitespace-pre-wrap font-mono">
                                {typeof task.result === 'string' ? task.result : JSON.stringify(task.result as Record<string, unknown>, null, 2)}
                              </pre>
                            </details>
                          )}
                        </div>

                        {/* Run: PENDING or PAUSED tasks haven't started
                            (or were paused mid-flight). POST to /run
                            kicks off the minimal task runner which
                            flips RUNNING -> COMPLETED with progress
                            reporting. Without this button PENDING
                            tasks sat forever because no autopilot
                            worker picked them up. */}
                        {['PENDING', 'PAUSED'].includes(task.status) && (
                          <button
                            onClick={() => handleRun(task.id)}
                            disabled={retryingId === task.id}
                            title={
                              task.status === 'PENDING'
                                ? 'Start this pending task now'
                                : 'Resume this paused task'
                            }
                            className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors cursor-pointer disabled:opacity-50 bg-status-success/10 text-status-success hover:bg-status-success/20"
                          >
                            {retryingId === task.id
                              ? <Loader2 size={12} className="animate-spin" />
                              : <Play size={12} />}
                            {task.status === 'PENDING' ? 'Run' : 'Resume'}
                          </button>
                        )}

                        {/* Re-run / Retry: FAILED / COMPLETED / CANCELLED
                            flips back to PENDING and immediately POSTs
                            /run so the task actually restarts. Before
                            the /run endpoint existed this button only
                            flipped status and looked stuck. */}
                        {['FAILED', 'COMPLETED', 'CANCELLED'].includes(task.status) && (
                          <button
                            onClick={() => handleRetry(task.id)}
                            disabled={retryingId === task.id}
                            title={
                              task.status === 'FAILED'
                                ? 'Retry this failed task (flips to PENDING + kicks off /run)'
                                : task.status === 'COMPLETED'
                                  ? 'Re-run with the same parameters'
                                  : 'Re-submit this cancelled task'
                            }
                            className={
                              'shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors cursor-pointer disabled:opacity-50 ' +
                              (task.status === 'FAILED'
                                ? 'bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20'
                                : 'bg-primary-500/10 text-primary-400 hover:bg-primary-500/20')
                            }
                          >
                            {retryingId === task.id
                              ? <Loader2 size={12} className="animate-spin" />
                              : <RotateCcw size={12} />}
                            {task.status === 'FAILED' ? 'Retry' : 'Re-run'}
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
