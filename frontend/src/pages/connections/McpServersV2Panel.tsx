/**
 * McpServersV2Panel -- canonical MCP servers tab.
 *
 * PR-CONN-UX-RESCUE: header tagline drops "V2 truth" terminology.
 * Internal Discover button removed (page header owns it). Empty state
 * + "0 servers" cases now read the per-path debug from the last
 * discovery report so the operator sees "checked N paths, 0 had
 * mcpServers" instead of a bare "0 found."
 *
 * Honesty rules:
 *   - No row says "running" / "ready" / "active" unless callable=true
 *   - Each row shows the real failure_reason from the last probe
 *   - Tools count comes from real capability discovery, not catalog
 */

import { useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ChevronRight, Download, FolderSearch, Loader2,
  RefreshCw, Search, Server,
} from 'lucide-react'

import {
  type ConnectionV2Row,
  type DiscoveryReport,
  type McpPathProbe,
  TRUTH_DIM_ORDER,
  labelTone,
  useConnectionsV2,
} from '@/hooks/useConnectionsV2'

interface McpServersV2PanelProps {
  /** Last discovery report from the page-level toolbar; used to render
   *  the per-path debug list when no MCP servers were found. */
  discoveryReport?: DiscoveryReport | null
  /** Trigger the page-level discovery action; rendered as a CTA inside
   *  the empty state when no rows exist yet. */
  onDiscover?: () => void
  /** Page-level discovery in progress (so the empty-state CTA can spin). */
  discovering?: boolean
}

export default function McpServersV2Panel({
  discoveryReport = null,
  onDiscover,
  discovering = false,
}: McpServersV2PanelProps = {}) {
  const { rows, loading, error, refresh, probe } =
    useConnectionsV2('mcp_server')
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
  const mcpPaths = discoveryReport?.mcp_paths_searched ?? []

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-white/5 bg-midnight-400/30 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-accent-cyan">
              <Server size={14} />
              MCP Servers
            </div>
            <h2 className="mt-1 text-base font-semibold text-starlight-100">
              {callableCount} of {rows.length} server
              {rows.length === 1 ? '' : 's'} callable
            </h2>
            <p className="mt-1 text-xs text-starlight-500">
              A server is &ldquo;callable&rdquo; only after a successful{' '}
              <code className="font-mono text-starlight-300">initialize</code> +{' '}
              <code className="font-mono text-starlight-300">tools/list</code>{' '}
              JSON-RPC handshake. Binary present is not the same as callable.
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
          placeholder="Search MCP servers..."
          className="w-full rounded-lg border border-white/5 bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-starlight-100 placeholder:text-starlight-500 focus:border-primary-500/40 focus:outline-none"
        />
      </div>

      {loading && rows.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] py-12 text-center text-sm text-starlight-400">
          <Loader2 size={16} className="mr-2 inline animate-spin" />
          Loading MCP servers...
        </div>
      ) : filtered.length === 0 ? (
        <McpEmptyState
          discoveryReport={discoveryReport}
          mcpPaths={mcpPaths}
          onDiscover={onDiscover}
          discovering={discovering}
        />
      ) : (
        <ul className="divide-y divide-white/5 overflow-hidden rounded-lg border border-white/5 bg-midnight-400/20">
          {filtered.map((row) => (
            <McpRow
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

function McpEmptyState({
  discoveryReport, mcpPaths, onDiscover, discovering,
}: {
  discoveryReport: DiscoveryReport | null
  mcpPaths: McpPathProbe[]
  onDiscover?: () => void
  discovering: boolean
}) {
  const hasRunDiscovery = discoveryReport !== null
  const pathsExisting = mcpPaths.filter((p) => p.exists).length
  const pathsWithBlock = mcpPaths.filter((p) => p.has_mcp_block).length

  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-sm text-starlight-400">
      {hasRunDiscovery ? (
        <div>
          <p className="mb-2 text-center font-medium text-starlight-200">
            No MCP servers found in detected config paths.
          </p>
          <p className="mx-auto max-w-2xl text-center text-xs text-starlight-500">
            Daena checked <strong className="text-starlight-300">{mcpPaths.length}</strong>{' '}
            path{mcpPaths.length === 1 ? '' : 's'} across Claude Code, Codex,
            and Gemini CLI.{' '}
            <strong className="text-starlight-300">{pathsExisting}</strong>{' '}
            existed,{' '}
            <strong className="text-starlight-300">{pathsWithBlock}</strong>{' '}
            contained a <code className="text-starlight-300">mcpServers</code>{' '}
            block. Configure MCP servers in any of the supported CLIs and run
            Discover again.
          </p>
        </div>
      ) : (
        <div className="text-center">
          <p className="mb-2 text-starlight-300">No MCP servers imported yet.</p>
          <p className="mx-auto max-w-xl text-xs text-starlight-500">
            Daena scans Claude Code, Codex, and Gemini CLI configs and
            imports the MCP servers it finds. Click{' '}
            <strong className="text-starlight-200">Discover installed
            tools</strong> in the page header to start.
          </p>
        </div>
      )}
      {onDiscover && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={onDiscover}
            disabled={discovering}
            className="inline-flex items-center gap-2 rounded-lg border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-2 text-xs font-medium text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
          >
            {discovering ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Download size={14} />
            )}
            {hasRunDiscovery ? 'Re-run discovery' : 'Discover installed tools'}
          </button>
        </div>
      )}
      {mcpPaths.length > 0 && (
        <details className="mx-auto mt-4 max-w-2xl text-left">
          <summary className="cursor-pointer text-xs text-starlight-500 hover:text-starlight-300">
            <FolderSearch size={11} className="mr-1 inline" />
            Show searched paths ({mcpPaths.length})
          </summary>
          <ul className="mt-2 space-y-1 text-[10px]">
            {mcpPaths.map((p) => (
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
                        {p.has_mcp_block
                          ? ` / ${p.mcp_count} mcpServer entries`
                          : ' / no mcpServers block'}
                      </>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] text-starlight-500">
            Daena reads only path metadata + server names from these files;
            env values stay in the source config and are never copied.
          </p>
        </details>
      )}
    </div>
  )
}

function McpRow({
  row, busy, onProbe,
}: { row: ConnectionV2Row; busy: boolean; onProbe: () => void }) {
  const tone = labelTone(row.label)
  const callable = row.truth.callable.value
  const failureReason =
    (!callable &&
      (row.truth.callable.failure_reason ||
        row.truth.authenticated.failure_reason ||
        row.truth.reachable.failure_reason)) ||
    null
  const cfg = (row.config || {}) as Record<string, unknown>
  const sourceCli = cfg._source_cli ? String(cfg._source_cli) : ''

  return (
    <li className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/5">
        <Server size={16} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-starlight-100">{row.display_name}</span>
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${tone.border} ${tone.bg} ${tone.text}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
            {row.label.replace(/_/g, ' ')}
          </span>
          {sourceCli && (
            <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-starlight-400">
              from {sourceCli}
            </span>
          )}
          <span className="text-[11px] text-starlight-500">
            {row.capabilities_count} tools discovered
          </span>
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
        {busy ? (
          <Loader2 size={12} className="animate-spin" />
        ) : (
          <Activity size={12} />
        )}
        Probe
      </button>
    </li>
  )
}
