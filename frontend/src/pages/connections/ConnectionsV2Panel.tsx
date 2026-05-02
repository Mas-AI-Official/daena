/**
 * ConnectionsV2Panel -- All Connections (canonical truth surface).
 *
 * PR-CONN-UX-RESCUE: now accepts discoveryReport + onDiscover from the
 * page-level toolbar so the per-source summary lives here without
 * duplicating the Discover button. Internal Discover + V2-flag banner
 * removed (the page header owns Discover; the V2-flag banner is
 * developer noise and lives only in Advanced now).
 *
 * Renders the canonical truth-backed connections list. Every row shows
 * the 6 truth dimensions (detected/configured/imported/reachable/
 * authenticated/callable). NO row says "connected" unless callable=true.
 * NO dummy buttons: every action calls a real backend endpoint or is
 * disabled with a visible reason.
 */

import { useMemo, useState } from 'react'
import {
  AlertTriangle, ChevronDown, ChevronRight, Loader2, Power, RefreshCw,
  Search, Trash2, X, Activity, Download, FolderSearch,
} from 'lucide-react'

import {
  type ConnectionKind,
  type ConnectionLabel,
  type ConnectionV2Row,
  type DiscoveryReport,
  TRUTH_DIM_ORDER,
  kindLabel,
  kindOrder,
  labelTone,
  useConnectionsV2,
} from '@/hooks/useConnectionsV2'

interface ConnectionsV2PanelProps {
  /** Last discovery report from the page-level toolbar; used to render
   *  the per-source summary card + MCP path debug list. */
  discoveryReport?: DiscoveryReport | null
  /** Trigger the page-level discovery action; rendered as a CTA inside
   *  the empty state when no rows exist yet. */
  onDiscover?: () => void
  /** Page-level discovery in progress (so the empty-state CTA can spin). */
  discovering?: boolean
}

export default function ConnectionsV2Panel({
  discoveryReport = null,
  onDiscover,
  discovering = false,
}: ConnectionsV2PanelProps = {}) {
  const { rows, loading, error, refresh, probe, enable, disable, archive } =
    useConnectionsV2()
  const [search, setSearch] = useState('')
  const [activeKind, setActiveKind] = useState<ConnectionKind | 'all'>('all')
  const [openIds, setOpenIds] = useState<Set<string>>(new Set())
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

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

  return (
    <div className="space-y-4">
      {discoveryReport && (
        <DiscoverySummary report={discoveryReport} />
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
            No connections imported yet.
          </p>
          <p className="mx-auto max-w-xl text-xs text-starlight-500">
            Daena scans your installed CLI runtimes, MCP configs, local model
            endpoints, configured API providers, OAuth catalog, and skill-pack
            catalog when you click <strong className="text-starlight-200">Discover
            installed tools</strong> above. The scan is idempotent and never
            reads secret values.
          </p>
          {onDiscover && (
            <button
              type="button"
              onClick={onDiscover}
              disabled={discovering}
              className="mt-4 inline-flex items-center gap-2 rounded-lg border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-2 text-xs font-medium text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
            >
              {discovering ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Download size={14} />
              )}
              Discover installed tools
            </button>
          )}
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

// ──────────────────────────────────────────────────────────────────
// PR-CONN-UX-RESCUE: discovery summary card
// ──────────────────────────────────────────────────────────────────
//
// Renders the per-source breakdown from the most recent discovery run,
// plus a collapsible "MCP paths checked" debug list. Only the path
// metadata is shown -- never env values or secrets. Lives at the top
// of the All Connections tab so the operator sees discovery context
// without having to dig.

const SOURCE_LABELS: Record<string, string> = {
  mcp_servers: 'MCP Servers',
  cli_runtimes: 'CLI Runtimes',
  local_models: 'Local Models',
  providers: 'API Providers',
  oauth_apps: 'OAuth Apps',
  skill_packs: 'Skill Packs',
}

function DiscoverySummary({ report }: { report: DiscoveryReport }) {
  const mcpReport = report.sources.find((s) => s.source === 'mcp_servers')
  const mcpPathCount = report.mcp_paths_searched.length
  const mcpPathsExisting = report.mcp_paths_searched.filter((p) => p.exists).length
  const mcpPathsWithBlock = report.mcp_paths_searched.filter((p) => p.has_mcp_block).length
  const mcpServersFound = mcpReport ? mcpReport.total_created + mcpReport.total_skipped_existing : 0
  const mcpEmpty = mcpServersFound === 0

  return (
    <div className="rounded-lg border border-accent-cyan/20 bg-accent-cyan/5 px-4 py-3">
      <div className="flex items-start gap-3">
        <FolderSearch size={16} className="mt-0.5 shrink-0 text-accent-cyan" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="text-xs font-medium uppercase tracking-[0.16em] text-accent-cyan">
              Last discovery
            </span>
            <span className="text-[11px] text-starlight-500">
              {report.total_created} new, {report.total_skipped_existing} existed,
              {' '}{report.total_skipped_unconfigured} unconfigured,
              {' '}{report.total_failed} failed
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {report.sources.map((s) => {
              const label = SOURCE_LABELS[s.source] || s.source
              const tone =
                s.total_failed > 0
                  ? 'bg-rose-500/15 text-rose-200'
                  : s.total_created > 0
                    ? 'bg-emerald-500/15 text-emerald-200'
                    : 'bg-slate-500/15 text-slate-300'
              return (
                <span
                  key={s.source}
                  className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] ${tone}`}
                  title={
                    s.total_failed > 0
                      ? `${s.total_failed} failures`
                      : s.total_created > 0
                        ? `${s.total_created} new rows`
                        : 'no changes this run'
                  }
                >
                  {label}: +{s.total_created}
                </span>
              )
            })}
          </div>
          {mcpEmpty && mcpPathCount > 0 && (
            <p className="mt-2 text-[11px] text-starlight-400">
              <strong className="text-starlight-200">
                No MCP servers found in detected config paths.
              </strong>{' '}
              Checked {mcpPathCount} path{mcpPathCount === 1 ? '' : 's'} across
              Claude Code, Codex, and Gemini CLI -- {mcpPathsExisting} existed,{' '}
              {mcpPathsWithBlock} contained a{' '}
              <code className="text-starlight-300">mcpServers</code> block.
            </p>
          )}
          {mcpPathCount > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-[11px] text-starlight-500 hover:text-starlight-300">
                Searched MCP config paths ({mcpPathCount})
              </summary>
              <ul className="mt-2 space-y-1 text-[10px]">
                {report.mcp_paths_searched.map((p) => (
                  <li
                    key={`${p.cli}:${p.path}`}
                    className="flex items-start gap-2 rounded border border-white/5 bg-white/[0.02] px-2 py-1"
                  >
                    <span
                      className={`mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                        p.has_mcp_block
                          ? 'bg-emerald-400'
                          : p.exists
                            ? 'bg-amber-400'
                            : 'bg-slate-500'
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-mono text-starlight-300" title={p.path}>
                        [{p.cli}] {p.path}
                      </div>
                      <div className="text-starlight-500">
                        {p.exists ? 'exists' : 'not found'}
                        {p.exists && (
                          <>
                            {p.parse_ok ? ' / parse_ok' : ' / parse_error'}
                            {p.has_mcp_block ? ` / ${p.mcp_count} mcpServer entries` : ' / no mcpServers block'}
                          </>
                        )}
                        {p.skip_reason && p.skip_reason !== 'not_found' && (
                          <span className="ml-2 text-rose-300">
                            {p.skip_reason}
                          </span>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[10px] text-starlight-500">
                Path entries carry only existence + parse status + count + server
                names. Daena does not read env values from these files.
              </p>
            </details>
          )}
        </div>
      </div>
    </div>
  )
}
