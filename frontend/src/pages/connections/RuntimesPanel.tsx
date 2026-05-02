/**
 * RuntimesPanel -- PR-CONN-UX-RESCUE.
 *
 * CLI runtime tab: surfaces kind=cli_runtime + kind=provider rows so
 * the operator sees one place for "which AI brains can Daena route
 * to?" Distinct from Main Brain (which picks ONE primary). Distinct
 * from Local Models (which targets local-endpoint rows).
 *
 * Honesty rules:
 *   - "Healthy" only after a probe proved callable
 *   - Failure reasons inline + per-dim truth chips
 */

import { useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ChevronRight, Globe, Loader2, RefreshCw, Search,
  Terminal,
} from 'lucide-react'

import {
  type ConnectionV2Row,
  TRUTH_DIM_ORDER,
  labelTone,
  useConnectionsV2,
} from '@/hooks/useConnectionsV2'

export default function RuntimesPanel() {
  const cli = useConnectionsV2('cli_runtime')
  const providers = useConnectionsV2('provider')
  const rows = useMemo(
    () => [...cli.rows, ...providers.rows],
    [cli.rows, providers.rows],
  )
  const loading = cli.loading || providers.loading
  const error = cli.error || providers.error
  const [search, setSearch] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return rows
    return rows.filter(
      (r) =>
        r.display_name.toLowerCase().includes(q) ||
        r.slug.toLowerCase().includes(q),
    )
  }, [rows, search])

  function refresh() {
    cli.refresh()
    providers.refresh()
  }

  async function runProbe(id: string) {
    setBusyId(id)
    const results = await Promise.all([cli.probe(id), providers.probe(id)])
    const ok = results.find((r) => r.ok)
    void ok
    setBusyId(null)
  }

  const callableCount = filtered.filter(
    (r) => r.label === 'healthy' || r.label === 'healthy_stale',
  ).length

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-white/5 bg-midnight-400/30 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-accent-cyan">
              <Terminal size={14} />
              Runtimes
            </div>
            <h2 className="mt-1 text-base font-semibold text-starlight-100">
              {callableCount} of {rows.length} runtime
              {rows.length === 1 ? '' : 's'} callable
            </h2>
            <p className="mt-1 text-xs text-starlight-500">
              CLI runtimes (Claude Code, Codex, Gemini) plus configured API
              providers (OpenAI, Anthropic, ...). Pick the active brain in
              the Main Brain tab; this view shows everything Daena can route
              to.
            </p>
          </div>
          <button
            onClick={refresh}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-200 hover:bg-white/10 disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          <AlertTriangle size={14} />
          <span>Backend error: {error}</span>
        </div>
      )}

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search runtimes..."
          className="w-full rounded-lg border border-white/5 bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-starlight-100 placeholder:text-starlight-500 focus:border-primary-500/40 focus:outline-none"
        />
      </div>

      {loading && rows.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] py-12 text-center text-sm text-starlight-400">
          <Loader2 size={16} className="mr-2 inline animate-spin" />
          Loading runtimes...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          <p className="mb-2 text-starlight-300">
            No runtimes detected yet.
          </p>
          <p className="mx-auto max-w-xl text-xs text-starlight-500">
            Click <strong className="text-starlight-200">Discover installed
            tools</strong> in the page header. Runtime rows appear when
            Daena finds the matching CLI binary on your PATH (claude, codex,
            gemini) or when an API provider key is configured in Settings.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-white/5 overflow-hidden rounded-lg border border-white/5 bg-midnight-400/20">
          {filtered.map((row) => (
            <RuntimeRow
              key={row.id}
              row={row}
              busy={busyId === row.id}
              onProbe={() => runProbe(row.id)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function RuntimeRow({
  row, busy, onProbe,
}: { row: ConnectionV2Row; busy: boolean; onProbe: () => void }) {
  const tone = labelTone(row.label)
  const cfg = (row.config || {}) as Record<string, unknown>
  const failureReason =
    (!row.truth.callable.value &&
      (row.truth.callable.failure_reason ||
        row.truth.authenticated.failure_reason ||
        row.truth.reachable.failure_reason)) ||
    null

  return (
    <li className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/5">
        {row.kind === 'cli_runtime' ? <Terminal size={16} /> : <Globe size={16} />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-starlight-100">{row.display_name}</span>
          <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-starlight-400">
            {row.kind === 'cli_runtime' ? 'CLI' : 'API Provider'}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${tone.border} ${tone.bg} ${tone.text}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
            {row.label.replace(/_/g, ' ')}
          </span>
        </div>
        {row.kind === 'cli_runtime' && cfg.binary && (
          <div className="mt-1 text-xs text-starlight-500">
            Binary:{' '}
            <code className="text-starlight-300">{String(cfg.binary)}</code>
          </div>
        )}
        <div className="mt-1 flex flex-wrap gap-1.5">
          {TRUTH_DIM_ORDER.map((d) => {
            const v = row.truth[d]
            const ok = v?.value === true
            const failed = !!v?.failure_at && (!v.at || v.failure_at >= v.at)
            return (
              <span
                key={d}
                title={v?.failure_reason || (ok ? `${d} ok` : `${d} not yet proven`)}
                className={`rounded px-1.5 py-0.5 text-[10px] ${
                  ok
                    ? 'bg-emerald-500/15 text-emerald-200'
                    : failed
                      ? 'bg-rose-500/15 text-rose-200'
                      : 'bg-slate-500/15 text-slate-300'
                }`}
              >
                {d}
              </span>
            )
          })}
        </div>
        {failureReason && (
          <div className="mt-1 text-xs text-rose-300">
            <ChevronRight size={11} className="inline" />
            {failureReason}
          </div>
        )}
      </div>
      <button
        onClick={onProbe}
        disabled={busy}
        className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
      >
        {busy ? <Loader2 size={12} className="animate-spin" /> : <Activity size={12} />}
        Probe
      </button>
    </li>
  )
}
