/**
 * ConnectionsV2Panel -- Phase 5 PR 1.
 *
 * Renders the V2 truth-backed connections list. Every row shows the
 * 6 truth dimensions (detected/configured/imported/reachable/
 * authenticated/callable). NO row says "connected" unless callable=true.
 * NO dummy buttons: every action calls a real backend endpoint or is
 * disabled with a visible reason.
 *
 * Layout:
 *   - Summary cards strip (one per kind, with healthy/total counters)
 *   - Search + kind filter + refresh
 *   - Grouped table (collapsible per kind)
 *   - Details drawer with truth ladder + per-dim failure reasons
 *
 * Modes:
 *   - V2 flag ON  -> live data via /api/v1/connections/v2
 *   - V2 flag OFF -> "legacy mode" banner; the table still renders V2
 *     rows that exist (for dev exercise) but mutations show a clear
 *     "enable USE_CONNECTION_REGISTRY_V2" hint
 */

import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, ChevronDown, ChevronRight, Download, Loader2, Power, RefreshCw,
  Search, ShieldCheck, Trash2, X, Activity,
} from 'lucide-react'

import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import {
  type ConnectionKind,
  type ConnectionLabel,
  type ConnectionV2Row,
  TRUTH_DIM_ORDER,
  kindLabel,
  kindOrder,
  labelTone,
  runDiscoveryRefresh,
  useConnectionsV2,
} from '@/hooks/useConnectionsV2'

interface FlagInfo {
  v2_enabled: boolean | null
  loading: boolean
}

function useV2Flag(): FlagInfo {
  /**
   * Fetch the V2 flag once via the reconciliation status endpoint
   * (v2_enabled is included in its response). FOUNDER+ gated -- if the
   * caller isn't FOUNDER, the request returns 403; we then fall back
   * to assuming the flag is OFF (the production-safe assumption).
   */
  const [info, setInfo] = useState<FlagInfo>({ v2_enabled: null, loading: true })

  useEffect(() => {
    let cancelled = false
    api
      .get<{ v2_enabled: boolean }>('/connections/v2/reconciliation/status', {
        silent: true,
      })
      .then((res) => {
        if (cancelled) return
        setInfo({ v2_enabled: !!res.data?.v2_enabled, loading: false })
      })
      .catch(() => {
        if (cancelled) return
        // 403 (non-founder) or any other failure -- assume OFF.
        setInfo({ v2_enabled: false, loading: false })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return info
}

export default function ConnectionsV2Panel() {
  const { v2_enabled, loading: flagLoading } = useV2Flag()
  const { rows, loading, error, refresh, probe, enable, disable, archive } =
    useConnectionsV2()
  const [search, setSearch] = useState('')
  const [activeKind, setActiveKind] = useState<ConnectionKind | 'all'>('all')
  const [openIds, setOpenIds] = useState<Set<string>>(new Set())
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [discovering, setDiscovering] = useState(false)

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return rows.filter((r) => {
      if (activeKind !== 'all' && r.kind !== activeKind) return false
      if (!q) return true
      return (
        r.display_name.toLowerCase().includes(q) ||
        r.slug.toLowerCase().includes(q) ||
        r.kind.toLowerCase().includes(q)
      )
    })
  }, [rows, search, activeKind])

  const grouped = useMemo(() => {
    const m = new Map<ConnectionKind, ConnectionV2Row[]>()
    for (const k of kindOrder()) m.set(k, [])
    for (const r of filtered) {
      const list = m.get(r.kind) || []
      list.push(r)
      m.set(r.kind, list)
    }
    return m
  }, [filtered])

  const summaryByKind = useMemo(() => {
    const out: Record<string, { total: number; healthy: number; failed: number }> = {}
    for (const k of kindOrder()) out[k] = { total: 0, healthy: 0, failed: 0 }
    for (const r of rows) {
      const bucket = out[r.kind] || { total: 0, healthy: 0, failed: 0 }
      bucket.total += 1
      if (r.label === 'healthy' || r.label === 'healthy_stale') bucket.healthy += 1
      if (r.label === 'failed') bucket.failed += 1
      out[r.kind] = bucket
    }
    return out
  }, [rows])

  const selected = useMemo(
    () => (selectedId ? rows.find((r) => r.id === selectedId) || null : null),
    [selectedId, rows],
  )

  function toggleGroup(k: ConnectionKind) {
    const next = new Set(openIds)
    if (next.has(k)) next.delete(k)
    else next.add(k)
    setOpenIds(next)
  }

  async function runProbe(id: string) {
    setBusyId(id)
    await probe(id)
    setBusyId(null)
  }

  async function runEnable(id: string) {
    setBusyId(id)
    await enable(id)
    setBusyId(null)
  }

  async function runDisable(id: string) {
    setBusyId(id)
    await disable(id)
    setBusyId(null)
  }

  async function runArchive(id: string) {
    setBusyId(id)
    await archive(id)
    setBusyId(null)
    if (selectedId === id) setSelectedId(null)
  }

  async function runImport() {
    setDiscovering(true)
    try {
      const res = await runDiscoveryRefresh()
      if (!res.ok) {
        toast.error(res.error || 'Discovery refresh failed')
        return
      }
      const summary = res.report?.sources
        .map((s) => `${s.source}: +${s.total_created}`)
        .filter((s) => !s.endsWith('+0'))
        .join(' | ')
      toast.success(
        summary ? `Discovery -- ${summary}` : 'Discovery complete -- no new rows',
      )
      refresh()
    } finally {
      setDiscovering(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Mode banner */}
      {!flagLoading && v2_enabled === false && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          <AlertTriangle size={16} className="shrink-0" />
          <div>
            <strong>V2 read-only mode.</strong>{' '}
            <code className="text-amber-100">USE_CONNECTION_REGISTRY_V2</code>{' '}
            is off. You can list, probe, and inspect V2 rows here, but
            legacy mutations (install / disconnect from the
            <strong>Show legacy / advanced</strong> reveal) will NOT
            mirror back to V2. Flip the backend flag in dev to enable
            full V2 mutation mirroring.
          </div>
        </div>
      )}
      {!flagLoading && v2_enabled === true && (
        <div className="flex items-center gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          <ShieldCheck size={16} className="shrink-0" />
          <div>
            <strong>V2 truth mode.</strong> Status reflects real probe
            results. A row is &ldquo;healthy&rdquo; only after a successful
            round-trip.
          </div>
        </div>
      )}

      {/* Summary strip */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {kindOrder().map((k) => {
          const s = summaryByKind[k] || { total: 0, healthy: 0, failed: 0 }
          return (
            <button
              key={k}
              type="button"
              onClick={() => setActiveKind(activeKind === k ? 'all' : k)}
              className={`rounded-lg border px-3 py-3 text-left transition-colors ${
                activeKind === k
                  ? 'border-primary-500/40 bg-primary-500/15 text-primary-200'
                  : 'border-white/5 bg-white/[0.03] text-starlight-300 hover:bg-white/5'
              }`}
            >
              <div className="text-xs font-medium uppercase tracking-wider text-starlight-400">
                {kindLabel(k)}
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-semibold text-starlight-100">
                  {s.total}
                </span>
                <span className="text-xs text-starlight-400">total</span>
              </div>
              <div className="mt-1 text-xs">
                <span className="text-emerald-400">{s.healthy} healthy</span>
                {s.failed > 0 && (
                  <span className="ml-2 text-rose-400">{s.failed} failed</span>
                )}
              </div>
            </button>
          )
        })}
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500"
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, slug, or kind"
            className="w-full rounded-lg border border-white/5 bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-starlight-100 placeholder:text-starlight-500 focus:border-primary-500/40 focus:outline-none"
          />
        </div>
        <select
          value={activeKind}
          onChange={(e) => setActiveKind(e.target.value as ConnectionKind | 'all')}
          className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 text-sm text-starlight-200 focus:border-primary-500/40 focus:outline-none"
        >
          <option value="all">All kinds</option>
          {kindOrder().map((k) => (
            <option key={k} value={k}>{kindLabel(k)}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={runImport}
          disabled={discovering}
          className="inline-flex items-center gap-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-50"
          title="Walk every real source (CLI MCP configs, runtime binaries, local models, providers, OAuth catalog, V1 plugin catalog) and import any new rows. Idempotent. Never reads secret values."
        >
          {discovering ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Download size={12} />
          )}
          Import from detected sources
        </button>
        <button
          type="button"
          onClick={refresh}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 text-xs font-medium text-starlight-200 hover:bg-white/5 disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          <AlertTriangle size={14} />
          <span>Backend error: {error}</span>
        </div>
      )}

      {/* Loading */}
      {loading && rows.length === 0 && (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] py-12 text-center text-sm text-starlight-400">
          Loading connections...
        </div>
      )}

      {/* Empty */}
      {!loading && rows.length === 0 && !error && (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          <p className="mb-3 text-starlight-300">
            No V2 connections imported yet.
          </p>
          <p className="mx-auto max-w-xl text-xs text-starlight-500">
            Click{' '}
            <strong className="text-starlight-200">
              Import from detected sources
            </strong>{' '}
            above to scan installed CLI runtimes, MCP server configs, local
            model endpoints, configured API providers, OAuth catalog, and the
            V1 plugin catalog. The import is idempotent and never reads
            secret values.
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
              walks every source for the caller's tenant. For per-row inserts,
              use{' '}
              <code className="text-starlight-300">
                POST /api/v1/connections/v2
              </code>{' '}
              with{' '}
              <code className="text-starlight-300">kind=&lt;...&gt;</code>.
              Truth ladder rules are unchanged: a row is &ldquo;healthy&rdquo;
              only after a real probe round-trip.
            </p>
          </details>
        </div>
      )}

      {/* Grouped table */}
      {filtered.length > 0 && (
        <div className="space-y-3">
          {kindOrder().map((k) => {
            const list = grouped.get(k) || []
            if (list.length === 0) return null
            const isOpen = !openIds.has(k)  // default open
            return (
              <section
                key={k}
                className="overflow-hidden rounded-lg border border-white/5 bg-midnight-400/30"
              >
                <button
                  type="button"
                  onClick={() => toggleGroup(k)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-starlight-200 hover:bg-white/[0.03]"
                >
                  <span className="inline-flex items-center gap-2">
                    {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    {kindLabel(k)}
                    <span className="text-xs text-starlight-500">({list.length})</span>
                  </span>
                </button>
                {isOpen && (
                  <ul className="divide-y divide-white/5">
                    {list.map((row) => (
                      <ConnectionRow
                        key={row.id}
                        row={row}
                        busy={busyId === row.id}
                        onProbe={() => runProbe(row.id)}
                        onEnable={() => runEnable(row.id)}
                        onDisable={() => runDisable(row.id)}
                        onArchive={() => runArchive(row.id)}
                        onSelect={() => setSelectedId(row.id)}
                      />
                    ))}
                  </ul>
                )}
              </section>
            )
          })}
        </div>
      )}

      {/* Details drawer */}
      {selected && (
        <DetailsDrawer
          row={selected}
          onClose={() => setSelectedId(null)}
          onProbe={() => runProbe(selected.id)}
          busy={busyId === selected.id}
        />
      )}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────
// Row
// ──────────────────────────────────────────────────────────────────

interface RowProps {
  row: ConnectionV2Row
  busy: boolean
  onProbe: () => void
  onEnable: () => void
  onDisable: () => void
  onArchive: () => void
  onSelect: () => void
}

function ConnectionRow({
  row, busy, onProbe, onEnable, onDisable, onArchive, onSelect,
}: RowProps) {
  const tone = labelTone(row.label as ConnectionLabel)
  const failingDim = TRUTH_DIM_ORDER.find((d) => {
    const x = row.truth[d]
    return x?.failure_reason && x.failure_at
  })

  return (
    <li className="grid grid-cols-1 gap-3 px-4 py-3 sm:grid-cols-[1fr_auto] sm:items-center">
      <div className="min-w-0">
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${tone.border} ${tone.bg} ${tone.text}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
            {row.label.replace(/_/g, ' ')}
          </span>
          <button
            type="button"
            onClick={onSelect}
            className="truncate text-sm font-medium text-starlight-100 hover:underline"
          >
            {row.display_name}
          </button>
          {row.disabled && (
            <span className="rounded bg-slate-500/15 px-1.5 py-0.5 text-[10px] text-slate-300">
              disabled
            </span>
          )}
          {row.archived && (
            <span className="rounded bg-slate-500/15 px-1.5 py-0.5 text-[10px] text-slate-300">
              archived
            </span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-starlight-400">
          <span className="font-mono">{row.slug}</span>
          <span>auth: {row.auth_method}</span>
          <span>{row.capabilities_count} capabilities</span>
          {failingDim && (
            <span className="text-rose-300">
              {failingDim} failure: {row.truth[failingDim].failure_reason}
            </span>
          )}
        </div>
        {/* Truth ladder mini */}
        <div className="mt-2 flex flex-wrap gap-1.5">
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
      <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
        {row.kind === 'skill_pack' ? (
          <span
            className="inline-flex items-center gap-1 rounded border border-violet-500/30 bg-violet-500/5 px-2 py-1 text-[11px] text-violet-200/80"
            title="Skill packs are capability/instruction bundles, not callable surfaces. Probe always returns 'skill_pack: not a callable surface'."
          >
            Skill pack
          </span>
        ) : (
          <RowButton
            onClick={onProbe}
            busy={busy}
            icon={<Activity size={12} />}
            label="Probe"
            tone="primary"
            tooltip="Run a real round-trip probe (alias of Test)"
          />
        )}
        {row.disabled ? (
          <RowButton
            onClick={onEnable}
            busy={busy}
            icon={<Power size={12} />}
            label="Enable"
            tone="neutral"
          />
        ) : (
          <RowButton
            onClick={onDisable}
            busy={busy}
            icon={<Power size={12} />}
            label="Disable"
            tone="neutral"
          />
        )}
        <RowButton
          onClick={onArchive}
          busy={busy}
          icon={<Trash2 size={12} />}
          label="Archive"
          tone="danger"
          confirm
        />
      </div>
    </li>
  )
}

// ──────────────────────────────────────────────────────────────────
// Row button
// ──────────────────────────────────────────────────────────────────

interface RowButtonProps {
  onClick: () => void
  busy: boolean
  icon: React.ReactNode
  label: string
  tone: 'primary' | 'neutral' | 'danger'
  confirm?: boolean
  tooltip?: string
}

function RowButton({ onClick, busy, icon, label, tone, confirm, tooltip }: RowButtonProps) {
  const [confirming, setConfirming] = useState(false)
  const cls =
    tone === 'primary'
      ? 'border-primary-500/30 bg-primary-500/10 text-primary-200 hover:bg-primary-500/20'
      : tone === 'danger'
        ? 'border-rose-500/30 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20'
        : 'border-white/10 bg-white/[0.04] text-starlight-200 hover:bg-white/[0.08]'

  function handleClick() {
    if (confirm && !confirming) {
      setConfirming(true)
      window.setTimeout(() => setConfirming(false), 3000)
      return
    }
    setConfirming(false)
    onClick()
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      title={tooltip}
      className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] font-medium transition-colors disabled:opacity-50 ${cls}`}
    >
      {icon}
      {confirming ? 'Click again to confirm' : label}
    </button>
  )
}

// ──────────────────────────────────────────────────────────────────
// Details drawer
// ──────────────────────────────────────────────────────────────────

interface DrawerProps {
  row: ConnectionV2Row
  onClose: () => void
  onProbe: () => void
  busy: boolean
}

function DetailsDrawer({ row, onClose, onProbe, busy }: DrawerProps) {
  const tone = labelTone(row.label as ConnectionLabel)
  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button
        type="button"
        aria-label="Close details"
        onClick={onClose}
        className="flex-1 bg-black/40 backdrop-blur-sm"
      />
      <aside className="flex h-full w-full max-w-md flex-col overflow-y-auto border-l border-white/10 bg-midnight-900 p-5 shadow-2xl">
        <header className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-wider text-starlight-400">
              {row.kind.replace(/_/g, ' ')}
            </div>
            <h2 className="mt-1 text-lg font-semibold text-starlight-100">
              {row.display_name}
            </h2>
            <span
              className={`mt-2 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${tone.border} ${tone.bg} ${tone.text}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
              {row.label.replace(/_/g, ' ')}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-starlight-400 hover:bg-white/5 hover:text-starlight-100"
          >
            <X size={16} />
          </button>
        </header>

        <dl className="mt-5 space-y-2 text-xs">
          <DrawerRow label="Slug" value={<code className="text-starlight-200">{row.slug}</code>} />
          <DrawerRow label="Auth method" value={row.auth_method} />
          <DrawerRow label="Trust tier" value={row.trust_tier} />
          <DrawerRow label="Capabilities" value={`${row.capabilities_count} discovered`} />
          <DrawerRow label="Healthy ratio" value={(row.healthy_call_ratio * 100).toFixed(0) + '%'} />
          <DrawerRow label="Governance tier" value={`T${row.governance_tier}`} />
          <ConfigDrawerRows row={row} />
        </dl>

        {/* PR-CONN-V2-SEED-IMPORT: local-model truth + Docker/WSL guidance.
            For local_model rows whose probe failed on the reachable dim,
            show the configured base_url verbatim plus the common cause
            (127.0.0.1 inside Docker / WSL refers to the container, not
            the Windows host). The base URL is config, not secret -- safe
            to print. */}
        {row.kind === 'local_model' &&
          row.truth.reachable.failure_at &&
          !row.truth.reachable.value && (
            <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle size={12} />
                Local endpoint unreachable
              </div>
              <p className="mt-1.5 text-amber-200/90">
                Configured base URL:{' '}
                <code className="text-amber-100">
                  {String((row.config as Record<string, unknown>)?.base_url || '(unset)')}
                </code>
              </p>
              <p className="mt-1.5 text-amber-200/80">
                If the backend runs in Docker / WSL,{' '}
                <code className="text-amber-100">127.0.0.1</code> resolves to
                the container, not the Windows host. Try{' '}
                <code className="text-amber-100">host.docker.internal</code> or
                the configured bridge IP, or run the backend natively.
              </p>
            </div>
          )}

        <h3 className="mt-6 text-xs font-semibold uppercase tracking-wider text-starlight-400">
          Truth ladder
        </h3>
        <div className="mt-2 divide-y divide-white/5 rounded-lg border border-white/5 bg-white/[0.02]">
          {TRUTH_DIM_ORDER.map((d) => {
            const v = row.truth[d]
            return (
              <div key={d} className="flex items-start gap-3 px-3 py-2">
                <span
                  className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                    v?.value
                      ? 'bg-emerald-400'
                      : v?.failure_reason
                        ? 'bg-rose-400'
                        : 'bg-slate-500'
                  }`}
                />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-starlight-200">
                    {d}
                  </div>
                  {v?.at && (
                    <div className="mt-0.5 text-[10px] text-starlight-500">
                      proven at {new Date(v.at).toLocaleString()}
                    </div>
                  )}
                  {v?.failure_at && (
                    <div className="mt-0.5 text-[10px] text-rose-300">
                      failed at {new Date(v.failure_at).toLocaleString()}
                    </div>
                  )}
                  {v?.failure_reason && (
                    <div className="mt-1 text-[11px] text-rose-200">
                      {v.failure_reason}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <button
          type="button"
          onClick={onProbe}
          disabled={busy}
          className="mt-5 inline-flex items-center justify-center gap-2 rounded-lg bg-primary-500/20 px-4 py-2 text-sm font-medium text-primary-100 hover:bg-primary-500/30 disabled:opacity-50"
        >
          <Activity size={14} />
          {busy ? 'Probing...' : 'Run live probe'}
        </button>
      </aside>
    </div>
  )
}

function DrawerRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-white/5 pb-1">
      <dt className="text-starlight-400">{label}</dt>
      <dd className="text-starlight-200">{value}</dd>
    </div>
  )
}

// PR-CONN-V2-SEED-IMPORT: kind-specific config rows. Only renders
// fields that are config (not secret) -- never reads vault material.
function ConfigDrawerRows({ row }: { row: ConnectionV2Row }) {
  const cfg = (row.config || {}) as Record<string, unknown>

  if (row.kind === 'local_model') {
    return (
      <>
        <DrawerRow
          label="Base URL"
          value={
            <code className="text-starlight-200">
              {String(cfg.base_url || '(unset)')}
            </code>
          }
        />
        {cfg.default_model ? (
          <DrawerRow label="Default model" value={String(cfg.default_model)} />
        ) : null}
      </>
    )
  }

  if (row.kind === 'mcp_server') {
    const envCount = Number(cfg.env_var_count ?? 0)
    return (
      <>
        {cfg.command ? (
          <DrawerRow
            label="Command"
            value={
              <code className="text-starlight-200">
                {String(cfg.command)} {Array.isArray(cfg.args) ? (cfg.args as unknown[]).join(' ') : ''}
              </code>
            }
          />
        ) : cfg.url ? (
          <DrawerRow
            label="URL"
            value={<code className="text-starlight-200">{String(cfg.url)}</code>}
          />
        ) : null}
        {cfg._source_cli ? (
          <DrawerRow label="Detected in" value={String(cfg._source_cli)} />
        ) : null}
        {envCount > 0 ? (
          <DrawerRow
            label="Env vars expected"
            value={
              <span
                title={(cfg.env_var_names as string[] | undefined)?.join(', ') || ''}
              >
                {envCount} (names only -- values never read by Daena)
              </span>
            }
          />
        ) : null}
      </>
    )
  }

  if (row.kind === 'oauth_app') {
    return (
      <>
        <DrawerRow
          label="Client ID"
          value={
            <code className="text-starlight-200">
              {String(cfg.client_id || '(unset)')}
            </code>
          }
        />
        <DrawerRow
          label="Client secret configured"
          value={cfg._client_secret_set ? 'yes' : 'no (set in Settings)'}
        />
        {Array.isArray(cfg.scopes) && (cfg.scopes as string[]).length > 0 ? (
          <DrawerRow
            label="Scopes"
            value={(cfg.scopes as string[]).length + ' requested'}
          />
        ) : null}
      </>
    )
  }

  if (row.kind === 'cli_runtime') {
    return (
      <>
        {cfg.binary ? (
          <DrawerRow
            label="Binary"
            value={<code className="text-starlight-200">{String(cfg.binary)}</code>}
          />
        ) : null}
        {cfg._runtime_id ? (
          <DrawerRow label="Runtime ID" value={String(cfg._runtime_id)} />
        ) : null}
        {cfg._provider_enum ? (
          <DrawerRow label="Provider slot" value={String(cfg._provider_enum)} />
        ) : null}
      </>
    )
  }

  if (row.kind === 'skill_pack') {
    return (
      <>
        {cfg.source_plugin_id ? (
          <DrawerRow label="Source plugin" value={String(cfg.source_plugin_id)} />
        ) : null}
        {cfg._category ? (
          <DrawerRow label="Category" value={String(cfg._category)} />
        ) : null}
        <DrawerRow label="Skills bundled" value={String(cfg.skill_count ?? 0)} />
        <DrawerRow
          label="Callable"
          value={
            <span className="text-violet-200">
              No (capability bundle, not a connector)
            </span>
          }
        />
      </>
    )
  }

  if (row.kind === 'provider' && cfg._provider_enum) {
    return <DrawerRow label="Provider" value={String(cfg._provider_enum)} />
  }

  return null
}
