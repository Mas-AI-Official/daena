/**
 * TasksPage — background tasks and autopilot status.
 * Shows running, paused, completed, and failed tasks.
 */
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
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
import { toast } from '@/stores/toastStore'
import type { TaskResponse, TaskStatus, ApiResponse } from '@/types/api'

const STATUS_CONFIG: Record<TaskStatus, { label: string; variant: string; icon: React.ReactNode }> = {
  PENDING:   { label: 'Pending',   variant: 'default',  icon: <Clock size={12} /> },
  RUNNING:   { label: 'Running',   variant: 'info',     icon: <Loader2 size={12} className="animate-spin" /> },
  PAUSED:    { label: 'Paused',    variant: 'warning',  icon: <Pause size={12} /> },
  COMPLETED: { label: 'Done',      variant: 'success',  icon: <CheckCircle2 size={12} /> },
  FAILED:    { label: 'Failed',    variant: 'danger',   icon: <XCircle size={12} /> },
  CANCELLED: { label: 'Cancelled', variant: 'default',  icon: <RotateCcw size={12} /> },
}

const VALID_FILTERS: ReadonlyArray<TaskStatus | 'ALL'> = [
  'ALL', 'PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED',
]

interface BackgroundQueueStatus {
  worker_running: boolean
  persistent: boolean
  storage: 'database' | 'memory_only' | string
  queued_count: number
  active_count: number
  restart_policy: string
}

function readFilterFromUrl(searchParams: URLSearchParams): TaskStatus | 'ALL' {
  const raw = searchParams.get('status')
  if (raw && (VALID_FILTERS as ReadonlyArray<string>).includes(raw)) {
    return raw as TaskStatus | 'ALL'
  }
  return 'ALL'
}

export function TasksPage() {
  usePageTitle('Tasks')
  const [searchParams, setSearchParams] = useSearchParams()
  const [tasks, setTasks] = useState<TaskResponse[]>([])
  const [loading, setLoading] = useState(true)
  // Filter state syncs to URL ?status=... so refreshing or sharing the page
  // preserves the operator's view. Bookmarkable filtered task lists.
  const [filter, _setFilter] = useState<TaskStatus | 'ALL'>(() => readFilterFromUrl(searchParams))
  const setFilter = (next: TaskStatus | 'ALL') => {
    _setFilter(next)
    setSearchParams((prev) => {
      const sp = new URLSearchParams(prev)
      if (next === 'ALL') sp.delete('status')
      else sp.set('status', next)
      return sp
    }, { replace: true })
  }
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [retryingId, setRetryingId] = useState<string | null>(null)
  // Busy guard for the batch action bar (run/archive/delete). Without it the
  // buttons stay enabled mid-flight -- a second click fires a duplicate batch
  // (double-fire) before the first round-trip clears the selection. Reset in
  // finally so a failed batch re-enables the bar instead of sticking disabled.
  const [batchBusy, setBatchBusy] = useState(false)
  const [queueStatus, setQueueStatus] = useState<BackgroundQueueStatus | null>(null)
  const [queueStatusError, setQueueStatusError] = useState<string | null>(null)
  // Inline fetch-error state for the main task list. Without this, a rejected
  // /execution/tasks call falls through to setTasks([]) and the list renders the
  // "No active tasks" empty state -- a load FAILURE pixel-identical to a genuinely
  // empty list (the Rule-17 "looks empty when it actually failed" lie). Mirrors the
  // queueStatusError pattern below so the render can distinguish failure from empty.
  const [tasksError, setTasksError] = useState<string | null>(null)
  // Wall-clock of the last SUCCESSFUL /execution/tasks fetch so "Last updated"
  // reflects when the data was actually refreshed, not render time. A bare
  // new Date() in the render asserts false freshness on every re-render
  // (filter/selection/batch toggles) with no refetch -- the Rule-17 TIME-
  // dimension visibility lie. Mirrors modelRegistryStore.lastFetchedAt /
  // securityModeStore.lastFetched (fetch-time, set only on success).
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null)

  // Sync state when URL changes externally (back/forward buttons, deep link).
  useEffect(() => {
    const fromUrl = readFilterFromUrl(searchParams)
    if (fromUrl !== filter) _setFilter(fromUrl)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  // When deep-linked from /projects/<id>?tab=tasks via #task-<id>, scroll to
  // and highlight that row once tasks load. Guarded to fire exactly once per
  // mount: the 15s auto-refresh poll flips `loading` and can change
  // `tasks.length`, which would otherwise re-run this effect and yank a user
  // who has scrolled away back to the deep-linked row on every refetch.
  const didDeepLinkScrollRef = useRef(false)
  useEffect(() => {
    if (loading) return
    if (didDeepLinkScrollRef.current) return
    if (window.location.hash.startsWith('#task-')) {
      const id = window.location.hash.slice('#task-'.length)
      const t = setTimeout(() => {
        const el = document.getElementById(`task-${id}`)
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
          didDeepLinkScrollRef.current = true
        }
      }, 100)
      return () => clearTimeout(t)
    }
  }, [loading, tasks.length])

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const params = filter !== 'ALL' ? `?status=${filter}` : ''
      const { data } = await api.get<ApiResponse<TaskResponse[]>>(`/execution/tasks${params}`)
      setTasks(data.data || [])
      setTasksError(null)
      setLastUpdatedAt(new Date())
    } catch {
      setTasks([])
      setTasksError('The task service is unreachable. Retry to refresh.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchTasks() }, [filter])

  const fetchQueueStatus = async () => {
    try {
      const { data } = await api.get<ApiResponse<BackgroundQueueStatus>>('/autopilot/queue/status')
      setQueueStatus(data.data)
      setQueueStatusError(null)
    } catch {
      setQueueStatus(null)
      setQueueStatusError('Background queue status unavailable')
    }
  }

  useEffect(() => { void fetchQueueStatus() }, [])

  // Auto-refresh when running tasks exist — paused while tab is hidden
  // so background tabs don't burn rate-limit budget polling for status
  // updates the operator can't see.
  useEffect(() => {
    const hasRunning = tasks.some(t => t.status === 'RUNNING')
    if (!hasRunning) return

    let interval: ReturnType<typeof setInterval> | null = null
    const start = () => { if (!interval) interval = setInterval(() => { void fetchTasks() }, 15000) }
    const stop = () => { if (interval) { clearInterval(interval); interval = null } }

    if (!document.hidden) start()

    const onVisibility = () => {
      if (document.hidden) stop()
      else { void fetchTasks(); start() }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    } catch (err) {
      // F-TASKS-CATCH fix: empty catch hid failures from the operator.
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Failed to run task. Check backend logs.')
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
    } catch (err) {
      // F-TASKS-CATCH fix: empty catch hid failures.
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Failed to retry task. Check backend logs.')
    } finally {
      setRetryingId(null)
    }
  }

  // ── Batch run (kick off every selected PENDING task) ──
  // Parallelized — a 50-task batch was previously 50 sequential round-trips.
  // Promise.allSettled lets the slowest one set the wall-clock floor.
  const handleBatchRun = async () => {
    if (batchBusy) return
    const runnable = tasks.filter(
      (t) => selectedIds.has(t.id) &&
        ['PENDING', 'FAILED', 'CANCELLED', 'PAUSED'].includes(t.status),
    )
    if (runnable.length === 0) return
    setBatchBusy(true)
    try {
      // allSettled keeps one failure from aborting the rest, but its results
      // were previously discarded -- a batch where every request 500'd cleared
      // the selection with zero feedback (Rule 17 "ran but did nothing"). Count
      // the rejections and surface them through the existing toast.
      const results = await Promise.allSettled(
        runnable.map(async (t) => {
          if (t.status !== 'PENDING') {
            await api.patch(`/execution/tasks/${t.id}`, { status: 'PENDING' })
          }
          await api.post(`/execution/tasks/${t.id}/run`)
        }),
      )
      const failed = results.filter((r) => r.status === 'rejected').length
      const plural = runnable.length === 1 ? '' : 's'
      if (failed > 0) {
        toast.error(`${failed} of ${runnable.length} task${plural} failed to start. Check backend logs.`)
      } else {
        toast.success(`${runnable.length} task${plural} started`)
      }
      setSelectedIds(new Set())
      await fetchTasks()
    } finally {
      setBatchBusy(false)
    }
  }

  // ── Batch archive (parallelized) ──
  const handleBatchArchive = async () => {
    if (batchBusy) return
    const ids = [...selectedIds]
    if (ids.length === 0) return
    setBatchBusy(true)
    try {
      const results = await Promise.allSettled(
        ids.map((id) =>
          api.patch(`/execution/tasks/${id}`, { status: 'CANCELLED' }),
        ),
      )
      const failed = results.filter((r) => r.status === 'rejected').length
      if (failed > 0) {
        toast.error(`${failed} of ${ids.length} task${ids.length === 1 ? '' : 's'} could not be archived.`)
      }
      setSelectedIds(new Set())
      await fetchTasks()
    } finally {
      setBatchBusy(false)
    }
  }

  // ── Cancel a running task ──
  const handleCancel = async (taskId: string) => {
    try {
      await api.patch(`/execution/tasks/${taskId}`, { status: 'CANCELLED' })
      await fetchTasks()
    } catch {
      const { toast } = await import('@/stores/toastStore')
      toast.error('Could not cancel task')
    }
  }

  // ── Batch delete ──
  // Uses the centralized batchDeleteWithToast helper so the success/
  // partial-failure/total-failure feedback matches FilesPage,
  // ProjectsPage, and anywhere else that deletes in bulk.
  const handleBatchDelete = async () => {
    if (batchBusy) return
    setBatchBusy(true)
    try {
      const result = await batchDeleteWithToast(
        selectedIds,
        (id) => `/execution/tasks/${id}`,
        { entity: 'task' },
      )
      if (result.succeeded > 0) {
        setSelectedIds(new Set())
        await fetchTasks()
      }
    } finally {
      setBatchBusy(false)
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
          <Button variant="ghost" size="sm" onClick={() => { void fetchTasks(); void fetchQueueStatus() }}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </Button>
        </motion.div>

        <Card variant="glass" padding="sm" className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Badge variant={queueStatus?.persistent ? 'success' : queueStatusError ? 'danger' : 'warning'}>
              {queueStatus?.persistent ? 'DB-backed queue' : queueStatusError ? 'Queue unknown' : 'Memory-only queue'}
            </Badge>
            <span className="text-xs text-starlight-400">
              {queueStatus
                ? queueStatus.restart_policy
                : queueStatusError || 'Checking background queue persistence...'}
            </span>
          </div>
          {queueStatus && (
            <span className="text-[11px] text-starlight-500">
              worker {queueStatus.worker_running ? 'running' : 'stopped'} · {queueStatus.active_count} active · {queueStatus.queued_count} queued
            </span>
          )}
        </Card>

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
              {lastUpdatedAt && `Last updated: ${lastUpdatedAt.toLocaleTimeString()}`}
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
                <button onClick={handleBatchRun} disabled={batchBusy} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-status-success/10 text-status-success hover:bg-status-success/20 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed">
                  <Play size={11} /> Run
                </button>
                <button onClick={handleBatchArchive} disabled={batchBusy} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed">
                  <Archive size={11} /> Archive
                </button>
                <button onClick={handleBatchDelete} disabled={batchBusy} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-accent-red/10 text-accent-red hover:bg-accent-red/20 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed">
                  <Trash2 size={11} /> Delete
                </button>
              </>
            )}
          </div>
        )}

        {/* Task list */}
        {loading ? (
          <Shimmer count={4} layout="list" />
        ) : tasksError ? (
          <EmptyState
            icon={XCircle}
            title="Could not load tasks"
            description={tasksError}
            action={{ label: 'Retry', onClick: () => { void fetchTasks() } }}
          />
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
                    id={`task-${task.id}`}
                    layout
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                  >
                    <Card
                      variant="glass"
                      padding="md"
                      className={`hover:border-white/10 transition-all ${
                        typeof window !== 'undefined' && window.location.hash === `#task-${task.id}`
                          ? 'border-primary-500/40 bg-primary-500/5'
                          : ''
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Checkbox */}
                        <button onClick={() => toggleSelect(task.id)} aria-label={`Select task ${task.name}`} className="shrink-0 mt-0.5 text-starlight-500 hover:text-primary-400 transition-colors cursor-pointer">
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

                        {/* Cancel a RUNNING task. Operators previously had no
                            way to stop a runaway task — only autopilot or
                            timeout would end it. */}
                        {task.status === 'RUNNING' && (
                          <button
                            onClick={() => handleCancel(task.id)}
                            title="Cancel this running task"
                            className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors cursor-pointer bg-status-error/10 text-status-error hover:bg-status-error/20"
                          >
                            <XCircle size={12} />
                            Cancel
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
