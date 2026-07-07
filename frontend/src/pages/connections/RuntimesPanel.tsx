/**
 * RuntimesPanel -- CLI runtimes + cloud API providers marketplace.
 *
 * PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): rewritten to use the
 * Marketplace card system. Surfaces every CLI runtime (Claude Code,
 * Codex, Gemini) and every cloud LLM provider (Anthropic, OpenAI,
 * Gemini, Perplexity, Groq, OpenRouter, Together) regardless of
 * whether the operator has authenticated yet.
 *
 * Honesty:
 *   - "Available" cards have no V2 row yet (binary not on PATH OR
 *     API key not set). Setup guide explains how to fix that.
 *   - "Callable" only after a real probe.
 *   - This view shows everything Daena CAN route to. The Main Brain
 *     tab is where the operator picks the active primary runtime.
 */

import { useMemo, useState } from 'react'
import {
  AlertTriangle, Globe, Loader2, RefreshCw, Search, Terminal,
} from 'lucide-react'

import {
  type LifecycleState,
  useMarketplaceCards,
} from '@/hooks/useMarketplace'
import { useConnectionsV2 } from '@/hooks/useConnectionsV2'

import MarketplaceCard from './MarketplaceCard'

export default function RuntimesPanel() {
  const { cards, loading, error, refresh } = useMarketplaceCards()
  const { probe, enable } = useConnectionsV2()
  const [search, setSearch] = useState('')
  const [activeKind, setActiveKind] = useState<'all' | 'cli_runtime' | 'api_provider'>('all')
  const [busyId, setBusyId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const onlyRuntimes = cards.filter(
      (c) => c.catalog.kind === 'cli_runtime' || c.catalog.kind === 'api_provider',
    )
    const q = search.trim().toLowerCase()
    return onlyRuntimes.filter((c) => {
      if (activeKind !== 'all' && c.catalog.kind !== activeKind) return false
      if (!q) return true
      return (
        c.catalog.display_name.toLowerCase().includes(q) ||
        c.catalog.vendor.toLowerCase().includes(q) ||
        c.catalog.short_description.toLowerCase().includes(q)
      )
    })
  }, [cards, search, activeKind])

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
            <Terminal size={12} className="mr-1 inline" />
            Runtimes
          </p>
          <h2 className="mt-1 text-base font-semibold text-starlight-100">
            {callable} of {filtered.length} runtime{filtered.length === 1 ? '' : 's'} callable
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-starlight-500">
            CLI runtimes (subscription-backed: Claude Code, Codex, Gemini)
            and cloud LLM API providers (Anthropic, OpenAI, ...). Pick the
            active one in <strong>Main Brain</strong>; this view shows
            everything Daena can route to.
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-200 hover:bg-white/10 disabled:opacity-50"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          Refresh
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setActiveKind('all')}
          className={`rounded-md border px-2.5 py-1 text-[11px] ${
            activeKind === 'all'
              ? 'border-primary-500/40 bg-primary-500/15 text-primary-200'
              : 'border-white/5 bg-white/[0.03] text-starlight-400 hover:bg-white/5'
          }`}
        >
          All ({cards.filter((c) => c.catalog.kind === 'cli_runtime' || c.catalog.kind === 'api_provider').length})
        </button>
        <button
          onClick={() => setActiveKind('cli_runtime')}
          className={`rounded-md border px-2.5 py-1 text-[11px] ${
            activeKind === 'cli_runtime'
              ? 'border-primary-500/40 bg-primary-500/15 text-primary-200'
              : 'border-white/5 bg-white/[0.03] text-starlight-400 hover:bg-white/5'
          }`}
        >
          <Terminal size={10} className="mr-1 inline" />
          CLI ({cards.filter((c) => c.catalog.kind === 'cli_runtime').length})
        </button>
        <button
          onClick={() => setActiveKind('api_provider')}
          className={`rounded-md border px-2.5 py-1 text-[11px] ${
            activeKind === 'api_provider'
              ? 'border-primary-500/40 bg-primary-500/15 text-primary-200'
              : 'border-white/5 bg-white/[0.03] text-starlight-400 hover:bg-white/5'
          }`}
        >
          <Globe size={10} className="mr-1 inline" />
          API ({cards.filter((c) => c.catalog.kind === 'api_provider').length})
        </button>
      </div>

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search runtimes..."
          aria-label="Search runtimes"
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
          Loading runtimes catalog...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          No runtimes match your filter.
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
