/**
 * AppsPanel -- PR-CONN-UX-RESCUE.
 *
 * Apps = OAuth-backed connectors (Google Drive / Calendar / Gmail,
 * GitHub, Figma, Slack, Canva, ...). Distinct from API providers
 * (which use static API keys) and skill packs (capability bundles
 * with no callable target). Filters useConnectionsV2 to kind=oauth_app
 * + kind=plugin so callable third-party apps show up in one place.
 *
 * Honesty rules:
 *   - "Connected" only after a probe proved callable
 *   - Client ID is shown verbatim (config); client_secret is shown as
 *     a yes/no flag (reads existence, never the value)
 *   - Plugin rows mirror App rendering since both represent callable
 *     third-party services
 */

import { useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, AppWindow, ChevronRight, Loader2, Package,
  RefreshCw, Search,
} from 'lucide-react'

import {
  type ConnectionKind,
  type ConnectionV2Row,
  TRUTH_DIM_ORDER,
  labelTone,
  useConnectionsV2,
} from '@/hooks/useConnectionsV2'
import GoogleAccountSetupGuide from './GoogleAccountSetupGuide'

const APP_KINDS: ConnectionKind[] = ['oauth_app', 'plugin']

export default function AppsPanel() {
  // Two kinds in one panel; merge their rows.
  const oauth = useConnectionsV2('oauth_app')
  const plugins = useConnectionsV2('plugin')
  const rows = useMemo(
    () => [...oauth.rows, ...plugins.rows],
    [oauth.rows, plugins.rows],
  )
  const loading = oauth.loading || plugins.loading
  const error = oauth.error || plugins.error
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
    oauth.refresh()
    plugins.refresh()
  }

  async function runProbe(id: string) {
    setBusyId(id)
    // The row exists in exactly one of the two hooks; the other 404s
    // silently per useConnectionsV2's contract.
    const results = await Promise.all([oauth.probe(id), plugins.probe(id)])
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
              <AppWindow size={14} />
              Apps
            </div>
            <h2 className="mt-1 text-base font-semibold text-starlight-100">
              {callableCount} of {rows.length} apps callable
            </h2>
            <p className="mt-1 text-xs text-starlight-500">
              OAuth-backed apps (Gmail, Calendar, Drive, GitHub, Figma, Slack,
              Canva) and other plugin connectors. A row is &ldquo;connected&rdquo;
              only after a real probe proves callable.
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

      {/* Sprint-7 PR-5: explain the founder vs agent Google account split.
          Static informational block; never starts an OAuth flow. */}
      <GoogleAccountSetupGuide />

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search apps..."
          className="w-full rounded-lg border border-white/5 bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-starlight-100 placeholder:text-starlight-500 focus:border-primary-500/40 focus:outline-none"
        />
      </div>

      {loading && rows.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] py-12 text-center text-sm text-starlight-400">
          <Loader2 size={16} className="mr-2 inline animate-spin" />
          Loading apps...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          <p className="mb-2 text-starlight-300">No apps imported yet.</p>
          <p className="mx-auto max-w-xl text-xs text-starlight-500">
            Click <strong className="text-starlight-200">Discover installed
            tools</strong> in the page header. Apps surface OAuth catalog
            entries (Gmail, Calendar, Drive, GitHub, Figma, Slack, Canva)
            whose <code className="text-starlight-300">client_id</code> is
            configured in Settings.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-white/5 overflow-hidden rounded-lg border border-white/5 bg-midnight-400/20">
          {filtered.map((row) => (
            <AppRow
              key={row.id}
              row={row}
              busy={busyId === row.id}
              onProbe={() => runProbe(row.id)}
            />
          ))}
        </ul>
      )}
      <p className="text-[10px] text-starlight-500">
        Showing kinds: {APP_KINDS.join(', ')}.
      </p>
    </div>
  )
}

function AppRow({
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
  const clientId = String(cfg.client_id || '')
  const clientSecretSet = cfg._client_secret_set === true

  return (
    <li className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/5">
        {row.kind === 'oauth_app' ? <AppWindow size={16} /> : <Package size={16} />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-starlight-100">{row.display_name}</span>
          <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-starlight-400">
            {row.kind === 'oauth_app' ? 'OAuth' : 'Plugin'}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${tone.border} ${tone.bg} ${tone.text}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
            {row.label.replace(/_/g, ' ')}
          </span>
        </div>
        {row.kind === 'oauth_app' && clientId && (
          <div className="mt-1 text-xs text-starlight-500">
            Client ID:{' '}
            <code className="text-starlight-300">
              {clientId.length > 32 ? `${clientId.slice(0, 24)}...` : clientId}
            </code>
            <span className="ml-2">
              client_secret:{' '}
              <span className={clientSecretSet ? 'text-emerald-300' : 'text-rose-300'}>
                {clientSecretSet ? 'set' : 'not set'}
              </span>
            </span>
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
