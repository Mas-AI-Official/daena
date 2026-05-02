/**
 * LocalModelsPanel -- PR-CONN-UX-RESCUE.
 *
 * Dedicated tab for kind=local_model rows (Ollama, vLLM /
 * llama-server). Shows configured base URL verbatim (config, never
 * secret), surfaces unreachability honestly, and provides Docker / WSL
 * guidance for the most common reachability failure (127.0.0.1 inside
 * the container vs Windows host).
 *
 * Honesty rules:
 *   - "Healthy" only after a successful probe that lists models
 *   - "Configured but unreachable" when configured=true + reachable=false
 *   - Base URL is shown verbatim (not redacted) -- it is config
 */

import { useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ChevronRight, Cpu, Loader2, RefreshCw, Search,
} from 'lucide-react'

import {
  type ConnectionV2Row,
  TRUTH_DIM_ORDER,
  labelTone,
  useConnectionsV2,
} from '@/hooks/useConnectionsV2'

export default function LocalModelsPanel() {
  const { rows, loading, error, refresh, probe } =
    useConnectionsV2('local_model')
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

  async function runProbe(id: string) {
    setBusyId(id)
    await probe(id)
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
              <Cpu size={14} />
              Local Models
            </div>
            <h2 className="mt-1 text-base font-semibold text-starlight-100">
              {callableCount} of {rows.length} local model endpoint
              {rows.length === 1 ? '' : 's'} reachable
            </h2>
            <p className="mt-1 text-xs text-starlight-500">
              Local LLM endpoints (Ollama, vLLM, llama-server). Daena calls
              them via OpenAI-compatible APIs. A row is &ldquo;healthy&rdquo;
              only after a successful model-list probe -- configured but
              unreachable rows surface the URL plus Docker / WSL guidance.
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
          placeholder="Search local models..."
          className="w-full rounded-lg border border-white/5 bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-starlight-100 placeholder:text-starlight-500 focus:border-primary-500/40 focus:outline-none"
        />
      </div>

      {loading && rows.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] py-12 text-center text-sm text-starlight-400">
          <Loader2 size={16} className="mr-2 inline animate-spin" />
          Loading local model endpoints...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          <p className="mb-2 text-starlight-300">
            No local model endpoints configured.
          </p>
          <p className="mx-auto max-w-xl text-xs text-starlight-500">
            Set <code className="text-starlight-300">VLLM_BASE_URL</code> or
            (deprecated) <code className="text-starlight-300">OLLAMA_BASE_URL</code>{' '}
            in <code className="text-starlight-300">backend/.env</code>, then
            click <strong className="text-starlight-200">Discover installed
            tools</strong> in the page header to import the row.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-white/5 overflow-hidden rounded-lg border border-white/5 bg-midnight-400/20">
          {filtered.map((row) => (
            <LocalModelRow
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

function LocalModelRow({
  row, busy, onProbe,
}: { row: ConnectionV2Row; busy: boolean; onProbe: () => void }) {
  const tone = labelTone(row.label)
  const cfg = (row.config || {}) as Record<string, unknown>
  const baseUrl = String(cfg.base_url || '(unset)')
  const defaultModel = cfg.default_model ? String(cfg.default_model) : null
  const reachableFailed =
    !row.truth.reachable.value && !!row.truth.reachable.failure_at
  const isConfiguredButUnreachable =
    row.truth.configured.value && reachableFailed

  return (
    <li className="flex flex-col gap-2 px-4 py-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/5">
          <Cpu size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-starlight-100">{row.display_name}</span>
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${tone.border} ${tone.bg} ${tone.text}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
              {isConfiguredButUnreachable
                ? 'configured, unreachable'
                : row.label.replace(/_/g, ' ')}
            </span>
          </div>
          <div className="mt-1 text-xs text-starlight-500">
            <code className="text-starlight-300">{baseUrl}</code>
            {defaultModel && (
              <span className="ml-3">
                default: <code className="text-starlight-300">{defaultModel}</code>
              </span>
            )}
          </div>
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
        </div>
        <button
          onClick={onProbe}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
        >
          {busy ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Activity size={12} />
          )}
          Probe
        </button>
      </div>

      {isConfiguredButUnreachable && (
        <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-200">
          <div className="flex items-center gap-2 font-semibold">
            <ChevronRight size={12} />
            Configured but unreachable
          </div>
          <p className="mt-1 text-amber-200/90">
            Daena could not reach{' '}
            <code className="text-amber-100">{baseUrl}</code>.
            {row.truth.reachable.failure_reason && (
              <> Last error: {row.truth.reachable.failure_reason}.</>
            )}
          </p>
          <p className="mt-1 text-amber-200/80">
            <strong>Docker / WSL guidance:</strong> if the backend runs in
            WSL or Docker,{' '}
            <code className="text-amber-100">127.0.0.1</code> may refer to
            that environment, not the Windows host. Try{' '}
            <code className="text-amber-100">host.docker.internal</code> or
            the configured bridge IP, or run the backend natively on the
            same host as the local model server.
          </p>
        </div>
      )}
    </li>
  )
}
