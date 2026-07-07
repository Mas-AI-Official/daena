/**
 * McpStorePanel -- curated MCP server marketplace.
 *
 * PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): the founder asked for
 * MCP servers as first-class. This panel renders the catalog
 * (~14 entries: filesystem / browser / code-platform / db / payment /
 * dev-tools) as marketplace cards with lifecycle overlay from the V2
 * truth ladder.
 *
 * Empty + 0-callable states honestly explain what to do next:
 *   - Run Discover to import detected MCPs
 *   - Pick a card and follow the Setup guide for one not yet installed
 */

import { useMemo, useState } from 'react'
import {
  AlertTriangle, Loader2, RefreshCw, Search, Server,
} from 'lucide-react'

import {
  type CatalogCategory,
  type LifecycleState,
  type MarketplaceCard as MarketplaceCardType,
  useMarketplaceCards,
} from '@/hooks/useMarketplace'
import { useConnectionsV2 } from '@/hooks/useConnectionsV2'

import MarketplaceCard from './MarketplaceCard'

const MCP_CATEGORIES: CatalogCategory[] = [
  'filesystem',
  'code_platform',
  'communication',
  'productivity',
  'design',
  'data_storage',
  'payment',
  'research',
  'dev_tools',
]

const CATEGORY_LABEL: Partial<Record<CatalogCategory, string>> = {
  filesystem: 'Filesystem',
  code_platform: 'Code platforms',
  communication: 'Communication',
  productivity: 'Productivity',
  design: 'Design',
  data_storage: 'Data + Storage',
  payment: 'Payment',
  research: 'Research',
  dev_tools: 'Dev tools',
}

interface McpStorePanelProps {
  onDiscover?: () => void
  discovering?: boolean
}

export default function McpStorePanel({ onDiscover, discovering }: McpStorePanelProps) {
  const { cards, loading, error, refresh } = useMarketplaceCards()
  const { probe, enable } = useConnectionsV2()
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState<CatalogCategory | 'all'>('all')
  const [busyId, setBusyId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const onlyMcp = cards.filter(
      (c) => c.catalog.kind === 'mcp_server',
    )
    const q = search.trim().toLowerCase()
    return onlyMcp.filter((c) => {
      if (activeCategory !== 'all' && c.catalog.category !== activeCategory) return false
      if (!q) return true
      return (
        c.catalog.display_name.toLowerCase().includes(q) ||
        c.catalog.vendor.toLowerCase().includes(q) ||
        c.catalog.short_description.toLowerCase().includes(q) ||
        c.catalog.capabilities.some((cap) => cap.toLowerCase().includes(q))
      )
    })
  }, [cards, search, activeCategory])

  const callable = filtered.filter((c) => isCallable(c.lifecycle)).length

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
          <p className="text-[10px] uppercase tracking-[0.18em] text-accent-cyan">
            <Server size={12} className="mr-1 inline" />
            MCP Store
          </p>
          <h2 className="mt-1 text-base font-semibold text-starlight-100">
            {callable} of {filtered.length} MCP server{filtered.length === 1 ? '' : 's'} callable
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-starlight-500">
            Curated MCP catalog. Each card is a real Anthropic / vendor
            server -- click <strong>Setup guide</strong> for installation
            steps, then <strong>Discover</strong> to import what you
            install. A server is &ldquo;callable&rdquo; only after a real
            JSON-RPC handshake with Daena's MCP probe.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {onDiscover && (
            <button
              onClick={onDiscover}
              disabled={discovering}
              className="inline-flex items-center gap-2 rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-3 py-1.5 text-xs text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
            >
              {discovering ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              Discover
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

      <div className="flex flex-wrap items-center gap-2">
        <button
          key="all"
          onClick={() => setActiveCategory('all')}
          className={`rounded-md border px-2.5 py-1 text-[11px] ${
            activeCategory === 'all'
              ? 'border-primary-500/40 bg-primary-500/15 text-primary-200'
              : 'border-white/5 bg-white/[0.03] text-starlight-400 hover:bg-white/5'
          }`}
        >
          All ({cards.filter((c) => c.catalog.kind === 'mcp_server').length})
        </button>
        {MCP_CATEGORIES.map((cat) => {
          const count = cards.filter(
            (c) => c.catalog.kind === 'mcp_server' && c.catalog.category === cat,
          ).length
          if (count === 0) return null
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`rounded-md border px-2.5 py-1 text-[11px] ${
                activeCategory === cat
                  ? 'border-primary-500/40 bg-primary-500/15 text-primary-200'
                  : 'border-white/5 bg-white/[0.03] text-starlight-400 hover:bg-white/5'
              }`}
            >
              {CATEGORY_LABEL[cat] ?? cat} ({count})
            </button>
          )
        })}
      </div>

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search MCP servers..."
          aria-label="Search MCP servers"
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
          Loading MCP catalog...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          No MCP servers match your filter.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((card) => (
            <MarketplaceCard
              key={card.catalog.id}
              card={card}
              busy={busyId === card.v2_row_id}
              onProbe={handleProbe}
              onEnable={handleEnable}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function isCallable(state: LifecycleState): boolean {
  return state === 'callable' || state === 'enabled'
}
