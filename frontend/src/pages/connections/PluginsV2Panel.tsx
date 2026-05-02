/**
 * PluginsV2Panel -- Phase 6.
 *
 * V2-truth-backed plugins view. Includes kind=plugin, kind=oauth_app,
 * and kind=provider rows since the legacy "Plugins" tab historically
 * included all three.
 *
 * Honesty rules:
 *   - No row says "connected" unless callable=true
 *   - Status pill matches V2 derive_label exactly
 *   - Per-dim failure reason inline
 *   - Provider rows show whether the API key is configured (V2
 *     truth: imported=True only after a real ConnectionV2 row exists)
 *   - Seeder button (FOUNDER+) materializes provider rows from
 *     settings keys
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, BookOpen, ChevronRight, Download, Loader2,
  Package, RefreshCw, Search, Sparkles,
} from 'lucide-react'

import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import {
  type ConnectionKind,
  type ConnectionV2Row,
  TRUTH_DIM_ORDER,
  labelTone,
  runDiscoveryRefresh,
  useConnectionsV2,
} from '@/hooks/useConnectionsV2'

const PLUGIN_KINDS: ConnectionKind[] = ['plugin', 'oauth_app', 'provider', 'skill_pack']
const KIND_LABELS: Record<ConnectionKind, string> = {
  plugin: 'Plugin',
  oauth_app: 'OAuth App',
  provider: 'API Provider',
  skill_pack: 'Skill Pack',
  cli_runtime: '',
  mcp_server: '',
  local_model: '',
}

interface UseAllKindsResult {
  rows: ConnectionV2Row[]
  loading: boolean
  error: string | null
  refresh: () => void
  probe: (id: string) => Promise<{ ok: boolean; error?: string }>
}

function useAllPluginKinds(): UseAllKindsResult {
  // PR-CONN-V2-SEED-IMPORT: poll four kinds (added skill_pack) and merge.
  // Each hook instance has its own poll timer; merge keeps it cheap.
  const a = useConnectionsV2('plugin')
  const b = useConnectionsV2('oauth_app')
  const c = useConnectionsV2('provider')
  const d = useConnectionsV2('skill_pack')
  const rows = useMemo(
    () => [...a.rows, ...b.rows, ...c.rows, ...d.rows],
    [a.rows, b.rows, c.rows, d.rows],
  )
  const loading = a.loading || b.loading || c.loading || d.loading
  const error = a.error || b.error || c.error || d.error
  function refresh() {
    a.refresh()
    b.refresh()
    c.refresh()
    d.refresh()
  }
  async function probe(id: string) {
    // Probe goes against any kind via the shared /v2/{id}/probe endpoint.
    // We hit each hook's probe in turn until one succeeds (the row will
    // only exist in exactly one of them, so the others fail with 404
    // silently).
    const results = await Promise.all([
      a.probe(id), b.probe(id), c.probe(id), d.probe(id),
    ])
    const ok = results.find((r) => r.ok)
    return ok ?? results[0]
  }
  return { rows, loading, error, refresh, probe }
}

export default function PluginsV2Panel() {
  const { rows, loading, error, refresh, probe } = useAllPluginKinds()
  const [search, setSearch] = useState('')
  const [kindFilter, setKindFilter] = useState<ConnectionKind | 'all'>('all')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [seeding, setSeeding] = useState(false)

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return rows.filter((r) => {
      if (kindFilter !== 'all' && r.kind !== kindFilter) return false
      if (!q) return true
      return (
        r.display_name.toLowerCase().includes(q) ||
        r.slug.toLowerCase().includes(q)
      )
    })
  }, [rows, search, kindFilter])

  const counts = useMemo(() => {
    const out: Record<ConnectionKind, { total: number; healthy: number }> = {
      plugin: { total: 0, healthy: 0 },
      oauth_app: { total: 0, healthy: 0 },
      provider: { total: 0, healthy: 0 },
      cli_runtime: { total: 0, healthy: 0 },
      mcp_server: { total: 0, healthy: 0 },
      local_model: { total: 0, healthy: 0 },
      skill_pack: { total: 0, healthy: 0 },
    }
    for (const r of rows) {
      out[r.kind].total += 1
      if (r.label === 'healthy' || r.label === 'healthy_stale') out[r.kind].healthy += 1
    }
    return out
  }, [rows])

  async function runProbe(id: string) {
    setBusyId(id)
    await probe(id)
    setBusyId(null)
  }

  async function runImport() {
    setSeeding(true)
    try {
      const res = await runDiscoveryRefresh()
      if (!res.ok) {
        toast.error(res.error || 'Discovery refresh failed')
        return
      }
      const summary = res.report?.sources
        .map((s) => `${s.source}: +${s.total_created}`)
        .join(' | ')
      toast.success(`Discovery complete -- ${summary || 'no new rows'}`)
      refresh()
    } finally {
      setSeeding(false)
    }
  }

  async function seedProviders() {
    setSeeding(true)
    try {
      const res = await api.post<{
        success: boolean
        data: { created: string[]; skipped_existing: string[]; skipped_unconfigured: string[] }
      }>('/connections/v2/reconciliation/seed-providers', undefined, { silent: false })
      const d = res.data?.data
      if (d) {
        const created = d.created.length
        const existing = d.skipped_existing.length
        toast.success(
          `Seeder: ${created} new, ${existing} existed, ${d.skipped_unconfigured.length} unconfigured`,
        )
        refresh()
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Seed failed')
    } finally {
      setSeeding(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-white/5 bg-midnight-400/30 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-medium uppercase tracking-[0.2em] text-accent-cyan">
              Plugins (V2 truth)
            </div>
            <h2 className="mt-1 text-base font-semibold text-starlight-100">
              {PLUGIN_KINDS.map((k) => `${counts[k].healthy}/${counts[k].total} ${KIND_LABELS[k]}s callable`).join(' · ')}
            </h2>
            <p className="mt-1 text-xs text-starlight-500">
              Plugins, OAuth apps, and API providers all live in the same
              V2 registry. A row says &ldquo;healthy&rdquo; only after a real
              probe proved callable.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={runImport}
              disabled={seeding}
              className="inline-flex items-center gap-2 rounded-md border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-50"
              title="Import plugins, providers, OAuth apps, skill packs, and MCP servers from real sources. Idempotent. Never reads secrets."
            >
              {seeding ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Download size={12} />
              )}
              Import from detected configs
            </button>
            <button
              onClick={seedProviders}
              disabled={seeding}
              className="inline-flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-200 hover:bg-amber-500/20 disabled:opacity-50"
              title="Seed provider rows from configured API keys (FOUNDER+ only)"
            >
              <Sparkles size={12} />
              Seed providers (FOUNDER+)
            </button>
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
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          <AlertTriangle size={14} />
          <span>Backend error: {error}</span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search plugins, providers, OAuth apps..."
            className="w-full rounded-lg border border-white/5 bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-starlight-100 placeholder:text-starlight-500 focus:border-primary-500/40 focus:outline-none"
          />
        </div>
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value as ConnectionKind | 'all')}
          className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 text-sm text-starlight-200 focus:border-primary-500/40 focus:outline-none"
        >
          <option value="all">All kinds</option>
          {PLUGIN_KINDS.map((k) => (
            <option key={k} value={k}>{KIND_LABELS[k]}</option>
          ))}
        </select>
      </div>

      {loading && rows.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] py-12 text-center text-sm text-starlight-400">
          <Loader2 size={16} className="mr-2 inline animate-spin" />
          Loading plugins from V2 registry...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          <p className="mb-3 text-starlight-300">
            No plugins, providers, OAuth apps, or skill packs in V2 registry yet.
          </p>
          <p className="mx-auto max-w-xl text-xs text-starlight-500">
            Click{' '}
            <strong className="text-starlight-200">Import from detected configs</strong>{' '}
            above to scan your installed CLI runtimes, configured API providers,
            OAuth catalog, and the V1 plugin catalog and materialize them as V2
            rows. Skill packs (capability/instruction bundles) are imported as
            a distinct kind and are never marked callable.
          </p>
          <details className="mx-auto mt-4 max-w-xl text-left">
            <summary className="cursor-pointer text-xs text-starlight-500 hover:text-starlight-300">
              Advanced details
            </summary>
            <p className="mt-2 text-xs text-starlight-500">
              Direct API:{' '}
              <code className="text-starlight-300">
                POST /api/v1/connections/v2/discovery/refresh
              </code>{' '}
              imports across every source for the caller's tenant.{' '}
              <code className="text-starlight-300">
                POST /api/v1/connections/v2/reconciliation/seed-providers
              </code>{' '}
              (FOUNDER+ only) materializes provider rows from configured API
              keys. Both are idempotent and never read secret values.
            </p>
          </details>
        </div>
      ) : (
        <ul className="divide-y divide-white/5 overflow-hidden rounded-lg border border-white/5 bg-midnight-400/20">
          {filtered.map((row) => (
            <PluginRow
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

function PluginRow({
  row, busy, onProbe,
}: { row: ConnectionV2Row; busy: boolean; onProbe: () => void }) {
  const tone = labelTone(row.label)
  const isSkillPack = row.kind === 'skill_pack'
  const callable = row.truth.callable.value
  const failureReason =
    (!callable &&
      (row.truth.callable.failure_reason ||
        row.truth.authenticated.failure_reason ||
        row.truth.reachable.failure_reason)) ||
    null
  const skillCount = isSkillPack
    ? Number((row.config as Record<string, unknown>)?.skill_count ?? 0)
    : 0

  return (
    <li className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${
          isSkillPack ? 'bg-violet-500/15 text-violet-200' : 'bg-white/5'
        }`}
      >
        {isSkillPack ? <BookOpen size={16} /> : <Package size={16} />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-starlight-100">{row.display_name}</span>
          <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-starlight-400">
            {KIND_LABELS[row.kind] || row.kind}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${tone.border} ${tone.bg} ${tone.text}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
            {row.label.replace(/_/g, ' ')}
          </span>
          {isSkillPack && (
            <span
              className="rounded-md bg-violet-500/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-violet-200"
              title="Capability or instruction bundle. Not a callable connector. Skill packs ship docs / prompts / playbooks for the LLM to use as context."
            >
              not callable
            </span>
          )}
          {isSkillPack && skillCount > 0 && (
            <span className="text-[11px] text-starlight-500">
              {skillCount} skill{skillCount === 1 ? '' : 's'}
            </span>
          )}
        </div>
        {isSkillPack ? (
          <p className="mt-1 text-[11px] text-starlight-500">
            Skill pack only. Not a callable connector. The LLM uses the
            packaged skills as context; nothing is invoked over the network.
          </p>
        ) : (
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
        )}
        {!isSkillPack && failureReason && (
          <div className="mt-1 text-xs text-rose-300">
            <ChevronRight size={11} className="inline" />
            {failureReason}
          </div>
        )}
      </div>
      {isSkillPack ? (
        <span
          className="inline-flex items-center gap-1.5 rounded-md border border-violet-500/30 bg-violet-500/5 px-3 py-1.5 text-xs text-violet-200/70"
          title="Skill packs are not callable, so probing returns 'skill_pack: not a callable surface'."
        >
          No probe
        </span>
      ) : (
        <button
          onClick={onProbe}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Activity size={12} />}
          Probe
        </button>
      )}
    </li>
  )
}
