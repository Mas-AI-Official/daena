/**
 * PluginsPanel -- Codex-style unified plugin marketplace.
 *
 * Founder pivot 2026-05-02: collapse the 9-tab marketplace into ONE
 * "Plugins" surface that hides backing-type plumbing from the user.
 * Internally each card is still a curated catalog entry overlaid with
 * the V2 truth ladder; externally the user sees one grid of brands.
 *
 * Layout:
 *   - Top: search + status filter + category sidebar (collapsing list)
 *   - Main: card grid sorted by vendor name
 *   - Empty state: explain how to discover or set up
 *
 * Honesty:
 *   - Status pills come from the PluginCard adapter; "Connected" is
 *     gated on V2 callable=true
 *   - Skill packs render inside the Plugins grid with an explicit
 *     "Skill pack. Needs a runtime/tool to execute." caption
 *   - "Setup guide" is the default action when no V2 row exists -- we
 *     never claim to install something we cannot safely install
 */

import { useMemo, useState } from 'react'
import {
  AlertTriangle, Loader2, RefreshCw, Search,
} from 'lucide-react'

import {
  type CatalogCategory,
  useMarketplaceCards,
} from '@/hooks/useMarketplace'
import { useConnectionsV2 } from '@/hooks/useConnectionsV2'

import PluginCardView from './PluginCardView'
import {
  type PluginCard,
  type PluginStatus,
  pluginCardFromMarketplaceCard,
} from './pluginCard'

// Status filter chips (UI ordering)
const STATUS_FILTERS: Array<{ key: 'all' | PluginStatus; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'connected', label: 'Connected' },
  { key: 'needs_auth', label: 'Needs auth' },
  { key: 'installed', label: 'Installed' },
  { key: 'failed', label: 'Failed' },
  { key: 'available', label: 'Available' },
]

// Category sidebar (founder-listed groupings)
const CATEGORY_GROUPS: Array<{
  key: 'all' | CatalogCategory
  label: string
}> = [
  { key: 'all', label: 'All categories' },
  { key: 'cli_runtime', label: 'CLI runtimes' },
  { key: 'ai_provider', label: 'AI providers' },
  { key: 'local_llm', label: 'Local LLM' },
  { key: 'browser', label: 'Browser' },
  { key: 'computer_use', label: 'Computer Use' },
  { key: 'filesystem', label: 'Filesystem' },
  { key: 'code_platform', label: 'Code platforms' },
  { key: 'communication', label: 'Communication' },
  { key: 'productivity', label: 'Productivity' },
  { key: 'design', label: 'Design' },
  { key: 'data_storage', label: 'Data + Storage' },
  { key: 'payment', label: 'Payment' },
  { key: 'research', label: 'Research' },
  { key: 'dev_tools', label: 'Dev tools' },
]

interface PluginsPanelProps {
  onDiscover?: () => void
  discovering?: boolean
}

export default function PluginsPanel({
  onDiscover, discovering = false,
}: PluginsPanelProps) {
  const { cards, loading, error, refresh } = useMarketplaceCards()
  const { probe, enable } = useConnectionsV2()
  const [search, setSearch] = useState('')
  const [activeStatus, setActiveStatus] = useState<'all' | PluginStatus>('all')
  const [activeCategory, setActiveCategory] = useState<'all' | CatalogCategory>('all')
  const [busyId, setBusyId] = useState<string | null>(null)

  const plugins = useMemo<PluginCard[]>(() => {
    return cards
      .map(pluginCardFromMarketplaceCard)
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [cards])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return plugins.filter((p) => {
      if (activeStatus !== 'all' && p.status !== activeStatus) return false
      if (activeCategory !== 'all' && p.category !== activeCategory) return false
      if (!q) return true
      return (
        p.name.toLowerCase().includes(q) ||
        p.vendor.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.included_skills.some((s) => s.toLowerCase().includes(q)) ||
        p.category_label.toLowerCase().includes(q)
      )
    })
  }, [plugins, search, activeStatus, activeCategory])

  const counts = useMemo(() => {
    const out: Record<'all' | PluginStatus, number> = {
      all: plugins.length,
      available: 0, installed: 0, needs_auth: 0,
      connected: 0, failed: 0, not_supported_on_os: 0,
    }
    for (const p of plugins) {
      out[p.status] += 1
    }
    return out
  }, [plugins])

  const categoryCounts = useMemo(() => {
    const out: Record<string, number> = { all: plugins.length }
    for (const p of plugins) {
      out[p.category] = (out[p.category] ?? 0) + 1
    }
    return out
  }, [plugins])

  async function handleProbe(rowId: string) {
    setBusyId(rowId)
    try {
      await probe(rowId)
      refresh()
    } finally {
      setBusyId(null)
    }
  }

  async function handleEnable(rowId: string) {
    setBusyId(rowId)
    try {
      await enable(rowId)
      refresh()
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3 rounded-xl border border-white/5 bg-midnight-400/30 px-4 py-3">
        <div>
          <h2 className="text-base font-semibold text-starlight-100">
            {counts.connected} of {counts.all} plugins connected
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-starlight-500">
            Browse what Daena can connect to. Each card is a real tool
            (MCP server, OAuth app, browser automation, local model, ...)
            wrapped behind a single &ldquo;Plugin&rdquo; concept. A card
            shows &ldquo;Connected&rdquo; only after a real probe proves
            it works.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {onDiscover && (
            <button
              onClick={onDiscover}
              disabled={discovering}
              className="inline-flex items-center gap-2 rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-3 py-1.5 text-xs text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
            >
              {discovering ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              Discover installed tools
            </button>
          )}
          <button
            onClick={refresh}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-200 hover:bg-white/10 disabled:opacity-50"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Refresh
          </button>
        </div>
      </div>

      {/* Status filter row */}
      <div className="flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((s) => {
          const active = activeStatus === s.key
          const count = counts[s.key] ?? 0
          if (s.key !== 'all' && count === 0) return null
          return (
            <button
              key={s.key}
              onClick={() => setActiveStatus(s.key)}
              className={`rounded-md border px-2.5 py-1 text-[11px] ${
                active
                  ? 'border-primary-500/40 bg-primary-500/15 text-primary-200'
                  : 'border-white/5 bg-white/[0.03] text-starlight-400 hover:bg-white/5'
              }`}
            >
              {s.label} ({count})
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[200px_1fr]">
        {/* Category sidebar */}
        <aside>
          <p className="mb-2 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
            Category
          </p>
          <ul className="space-y-0.5">
            {CATEGORY_GROUPS.map((g) => {
              const count = categoryCounts[g.key] ?? 0
              if (g.key !== 'all' && count === 0) return null
              const active = activeCategory === g.key
              return (
                <li key={g.key}>
                  <button
                    onClick={() => setActiveCategory(g.key)}
                    className={`flex w-full items-center justify-between rounded-md px-2 py-1 text-[11px] ${
                      active
                        ? 'bg-primary-500/15 text-primary-200'
                        : 'text-starlight-400 hover:bg-white/[0.03] hover:text-starlight-200'
                    }`}
                  >
                    <span>{g.label}</span>
                    <span className="text-[10px] text-starlight-500">{count}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </aside>

        {/* Main grid */}
        <div className="space-y-4">
          <div className="relative max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search plugins..."
              className="w-full rounded-lg border border-white/5 bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-starlight-100 placeholder:text-starlight-500 focus:border-primary-500/40 focus:outline-none"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 px-3 py-2 text-xs text-rose-200">
              <AlertTriangle size={12} className="mt-0.5" />
              <span>Backend error: {error}</span>
            </div>
          )}

          {loading && cards.length === 0 ? (
            <div className="rounded-lg border border-white/5 bg-white/[0.02] py-12 text-center text-sm text-starlight-400">
              <Loader2 size={16} className="mr-2 inline animate-spin" />
              Loading plugin marketplace...
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState onDiscover={onDiscover} discovering={discovering} />
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {filtered.map((plugin) => (
                <PluginCardView
                  key={plugin.id}
                  plugin={plugin}
                  busy={busyId === plugin.v2_row_id}
                  onProbe={handleProbe}
                  onEnable={handleEnable}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function EmptyState({
  onDiscover, discovering,
}: { onDiscover?: () => void; discovering: boolean }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
      <p className="text-starlight-300">No plugins match the active filters.</p>
      <p className="mx-auto mt-1 max-w-xl text-xs text-starlight-500">
        Click <strong className="text-starlight-200">Discover installed tools</strong>{' '}
        to import what Daena finds on disk, or open a card and follow its
        <strong className="text-starlight-200"> Setup guide</strong>.
      </p>
      {onDiscover && (
        <button
          onClick={onDiscover}
          disabled={discovering}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-2 text-xs font-medium text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
        >
          {discovering ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Discover installed tools
        </button>
      )}
    </div>
  )
}
