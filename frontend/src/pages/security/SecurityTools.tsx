/**
 * SecurityTools -- the Tools tab.
 *
 * Tool catalog with search + category + installed-status filters,
 * bulk-install-all-missing job runner with live progress polling, and
 * per-tool install / enable cards.
 *
 * Filter state lives on the parent page (so it survives tab switches);
 * the bulk-install + per-card install state stay local to this tab.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Package,
  Terminal,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Wrench,
  Search,
  Loader2,
  PackagePlus,
} from 'lucide-react'
import { Card, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { alertDialog, confirmDialog } from '@/stores/confirmStore'
import {
  type ToolInfo,
  type InstalledFilter,
  CATEGORY_COLORS,
} from './types'

interface Props {
  tools: ToolInfo[]
  allTools: ToolInfo[]
  categories: string[]
  search: string
  onSearchChange: (v: string) => void
  categoryFilter: string
  onCategoryChange: (v: string) => void
  installedFilter: InstalledFilter
  onInstalledChange: (v: InstalledFilter) => void
  onReload: () => void
}

export default function SecurityTools({
  tools, allTools, categories, search, onSearchChange,
  categoryFilter, onCategoryChange, installedFilter, onInstalledChange,
  onReload,
}: Props) {
  // Bulk-install progress state: null when idle, otherwise the latest
  // poll snapshot from /tools/install-all/status/{jobId}.
  const [bulkProgress, setBulkProgress] = useState<{
    jobId: string
    status: 'running' | 'cancelling' | 'cancelled' | 'complete' | 'failed'
    total: number
    done: number
    succeeded: number
    failed: number
    skipped: number
    current: string
  } | null>(null)
  const bulkRunning = bulkProgress?.status === 'running' || bulkProgress?.status === 'cancelling'

  const installAll = async () => {
    const missing = allTools.filter(t => !t.installed)
    const effectiveMissing = categoryFilter
      ? missing.filter(t => t.category === categoryFilter)
      : missing
    if (effectiveMissing.length === 0) {
      await alertDialog({
        title: 'Nothing to install',
        message: 'All tools in the current filter are already installed.',
        confirmLabel: 'OK',
      })
      return
    }
    const confirmed = await confirmDialog({
      title: `Install ${effectiveMissing.length} missing tool(s)?`,
      message: (
        'Daena will run each tool\'s catalog install command as a subprocess ' +
        '(choco / pip / npm / go install / apt, per platform). This runs in ' +
        'the background -- the button shows live progress. Tools whose ' +
        'prerequisite (e.g. Go, Ruby) is missing will be skipped cleanly.'
      ),
      confirmLabel: `Install ${effectiveMissing.length}`,
      cancelLabel: 'Cancel',
      variant: 'warning',
    })
    if (!confirmed) return

    // Kick off the background job. Backend returns immediately with job_id.
    let jobId = ''
    try {
      const { data } = await api.post(
        '/security/tools/install-all',
        null,
        {
          params: {
            ...(categoryFilter ? { category: categoryFilter } : {}),
            confirm: 'install-security-tool',
          },
        },
      )
      jobId = data.job_id
      setBulkProgress({
        jobId,
        status: 'running',
        total: data.total,
        done: 0,
        succeeded: 0,
        failed: 0,
        skipped: 0,
        current: '',
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Install-all failed'
      await alertDialog({
        title: 'Bulk install failed to start',
        message: msg,
        confirmLabel: 'Dismiss',
        variant: 'danger',
      })
      return
    }

    // Poll every 2s until complete; refresh tool list every 10 installs
    // so the UI reflects newly-installed tools without waiting for the
    // full run to finish.
    let lastReloadDone = 0
    while (true) {
      await new Promise(r => setTimeout(r, 2000))
      try {
        const { data } = await api.get(
          `/security/tools/install-all/status/${jobId}`,
        )
        setBulkProgress({
          jobId,
          status: data.status,
          total: data.total,
          done: data.done,
          succeeded: data.succeeded,
          failed: data.failed,
          skipped: data.skipped,
          current: data.current || '',
        })
        if (data.done - lastReloadDone >= 10) {
          lastReloadDone = data.done
          onReload()
        }
        if (data.status !== 'running') {
          onReload()
          break
        }
      } catch {
        // Single poll failure -- keep trying. The user can dismiss the
        // progress banner manually once done.
      }
    }
  }

  const inventoryChecking = allTools.some(
    t => t.install_state === 'pending' || t.install_state === 'stale',
  )
  const missingCount = inventoryChecking
    ? 0
    : allTools.filter(t => !t.installed).length

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
          <input
            type="text"
            value={search}
            onChange={e => onSearchChange(e.target.value)}
            placeholder="Search tools or capabilities..."
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-starlight-800 border border-starlight-700
                       text-sm text-starlight-200 placeholder:text-starlight-600
                       focus:outline-none focus:border-primary-500/50"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={e => onCategoryChange(e.target.value)}
          className="px-3 py-2 rounded-lg bg-starlight-800 border border-starlight-700
                     text-sm text-starlight-300 focus:outline-none"
        >
          <option value="">All categories</option>
          {categories.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <div className="flex items-center rounded-lg border border-starlight-700 overflow-hidden">
          {(['all', 'installed', 'missing'] as const).map(f => (
            <button
              key={f}
              onClick={() => onInstalledChange(f)}
              className={`
                px-3 py-2 text-xs font-medium capitalize transition-colors
                ${installedFilter === f
                  ? 'bg-primary-600 text-white'
                  : 'bg-starlight-800 text-starlight-400 hover:text-starlight-200'}
              `}
            >
              {f}
            </button>
          ))}
        </div>

        <span className="text-xs text-starlight-500">
          {tools.length}/{allTools.length} tools
          {inventoryChecking ? ' · checking installs' : ''}
        </span>

        <button
          onClick={installAll}
          disabled={bulkRunning || missingCount === 0}
          className="ml-auto flex items-center gap-2 px-3 py-2 rounded-lg bg-accent-amber/15 text-accent-amber border border-accent-amber/30 text-xs font-medium hover:bg-accent-amber/25 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          title={inventoryChecking ? 'Waiting for installed-tool inventory' : 'Install every missing tool'}
        >
          {bulkRunning ? <Loader2 size={14} className="animate-spin" /> : <PackagePlus size={14} />}
          {bulkRunning
            ? `Installing ${bulkProgress!.done}/${bulkProgress!.total}`
            : `Install all missing (${missingCount})`}
        </button>
      </div>

      {bulkProgress && (
        <div className={`p-3 rounded-lg border text-xs ${
          bulkProgress.status === 'running'
            ? 'bg-accent-amber/5 border-accent-amber/25 text-accent-amber'
            : bulkProgress.failed > bulkProgress.succeeded
              ? 'bg-status-error/5 border-status-error/25 text-status-error'
              : 'bg-status-success/5 border-status-success/25 text-status-success'
        }`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {bulkProgress.status === 'running' ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <CheckCircle2 size={12} />
              )}
              <span className="font-medium">
                {bulkProgress.status === 'running'
                  ? `Installing ${bulkProgress.done}/${bulkProgress.total}`
                  : `Install finished: ${bulkProgress.succeeded} ok, ${bulkProgress.failed} failed, ${bulkProgress.skipped} skipped`}
              </span>
              {bulkProgress.current && bulkProgress.status === 'running' && (
                <span className="text-starlight-400 font-mono">→ {bulkProgress.current}</span>
              )}
            </div>
            {bulkProgress.status !== 'running' && (
              <button
                onClick={() => setBulkProgress(null)}
                className="text-starlight-500 hover:text-starlight-200 cursor-pointer"
              >
                Dismiss
              </button>
            )}
          </div>
          <div className="w-full h-1 bg-starlight-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-current transition-all"
              style={{
                width: `${bulkProgress.total > 0 ? (bulkProgress.done / bulkProgress.total) * 100 : 0}%`,
              }}
            />
          </div>
          <div className="mt-1.5 flex gap-4 text-[10px] text-starlight-500">
            <span>ok: {bulkProgress.succeeded}</span>
            <span>failed: {bulkProgress.failed}</span>
            <span>skipped: {bulkProgress.skipped}</span>
          </div>
        </div>
      )}

      {/* Tool grid */}
      {tools.length === 0 ? (
        <EmptyState
          icon={<Package className="text-starlight-500" size={40} />}
          title="No tools match"
          description="Try adjusting your filters"
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {tools.map(tool => (
            <ToolCard key={tool.name} tool={tool} onReload={onReload} />
          ))}
        </div>
      )}
    </div>
  )
}

function ToolCard({ tool, onReload }: { tool: ToolInfo; onReload: () => void }) {
  const [showCmd, setShowCmd] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [installError, setInstallError] = useState('')
  // Optimistic local copy of ``enabled`` so the toggle feels instant
  // while the POST is in flight. Rolled back on failure.
  const [localEnabled, setLocalEnabled] = useState(tool.enabled)
  const [toggling, setToggling] = useState(false)
  const catColor = CATEGORY_COLORS[tool.category] || 'text-starlight-400 bg-starlight-800 border-starlight-700'
  const installState = tool.install_state || 'unknown'
  const installPending = installState === 'pending' || installState === 'stale'

  const handleInstall = async () => {
    const confirmed = await confirmDialog({
      title: `Install ${tool.name}?`,
      message: (
        `Daena will run this tool's catalog install command as a local ` +
        `subprocess: ${tool.install_cmd}`
      ),
      confirmLabel: 'Run install',
      cancelLabel: 'Cancel',
      variant: 'warning',
    })
    if (!confirmed) return

    setInstalling(true)
    setInstallError('')
    try {
      const { data } = await api.post(
        `/security/tools/install/${tool.name}`,
        null,
        { params: { confirm: 'install-security-tool' } },
      )
      if (data.installed_after || data.success || data.already_installed) {
        onReload()
      } else {
        setInstallError(
          (data.stderr || data.error || 'Install reported failure').slice(0, 300),
        )
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Install failed'
      setInstallError(msg.slice(0, 300))
    } finally {
      setInstalling(false)
    }
  }

  const handleToggle = async () => {
    const next = !localEnabled
    setLocalEnabled(next)       // optimistic
    setToggling(true)
    try {
      await api.post(`/security/tools/${tool.name}/enable`, { enabled: next })
    } catch {
      setLocalEnabled(!next)    // rollback
    } finally {
      setToggling(false)
    }
  }

  return (
    <Card className={`p-3 space-y-2 ${tool.installed && !localEnabled ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Wrench size={14} className="text-starlight-400 flex-shrink-0" />
          <span className="text-sm font-medium text-starlight-200">{tool.name}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {tool.offensive_only && (
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-accent-amber/10
                             text-accent-amber border border-accent-amber/20">
              Founder
            </span>
          )}
          {installPending ? (
            <Loader2 size={14} className="text-starlight-500 animate-spin" />
          ) : tool.installed ? (
            <CheckCircle2 size={14} className="text-status-success" />
          ) : installState === 'failed' ? (
            <AlertTriangle size={14} className="text-status-warning" />
          ) : (
            <XCircle size={14} className="text-starlight-600" />
          )}
          {tool.installed && (
            <button
              onClick={handleToggle}
              disabled={toggling}
              title={localEnabled
                ? 'Tool is ON — Daena will dispatch it on scans'
                : 'Tool is OFF — Daena will skip it on scans'}
              className={`
                relative inline-flex h-[18px] w-[32px] items-center rounded-full
                transition-colors cursor-pointer
                ${localEnabled
                  ? 'bg-status-success/70 hover:bg-status-success'
                  : 'bg-starlight-700 hover:bg-starlight-600'}
                ${toggling ? 'opacity-60' : ''}
              `}
            >
              <span
                className={`
                  inline-block h-[14px] w-[14px] rounded-full bg-white transition-transform
                  ${localEnabled ? 'translate-x-[16px]' : 'translate-x-[2px]'}
                `}
              />
            </button>
          )}
        </div>
      </div>

      <p className="text-xs text-starlight-500 line-clamp-2">{tool.description}</p>

      <div className="flex items-center gap-1.5 flex-wrap">
        <span className={`px-1.5 py-0.5 text-[10px] rounded border ${catColor}`}>
          {tool.category}
        </span>
        {tool.capabilities.slice(0, 3).map(cap => (
          <span
            key={cap}
            className="px-1.5 py-0.5 text-[10px] rounded
                       bg-starlight-800 text-starlight-500 border border-starlight-700"
          >
            {cap.replace(/_/g, ' ')}
          </span>
        ))}
        {tool.capabilities.length > 3 && (
          <span className="text-[10px] text-starlight-600">
            +{tool.capabilities.length - 3}
          </span>
        )}
      </div>

      {!tool.installed && (
        <div className="flex items-center gap-2 mt-1">
          <button
            onClick={handleInstall}
            disabled={installing || installPending}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-xs bg-accent-amber/15 text-accent-amber border border-accent-amber/25 hover:bg-accent-amber/25 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            {installing ? <Loader2 size={11} className="animate-spin" /> : <PackagePlus size={11} />}
            {installing ? 'Installing' : installPending ? 'Checking' : 'Install'}
          </button>
          <button
            onClick={() => setShowCmd(!showCmd)}
            className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300 transition-colors cursor-pointer"
          >
            <Terminal size={11} />
            {showCmd ? 'Hide cmd' : 'Show cmd'}
          </button>
        </div>
      )}

      {installError && (
        <p className="text-[10px] text-status-error flex items-start gap-1 mt-1">
          <AlertTriangle size={10} className="mt-0.5 flex-shrink-0" />
          <span className="line-clamp-3">{installError}</span>
        </p>
      )}

      <AnimatePresence>
        {showCmd && !tool.installed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <pre className="text-[10px] text-accent-cyan bg-starlight-900 rounded p-2 overflow-x-auto
                            border border-starlight-800">
              {tool.install_cmd}
            </pre>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}
