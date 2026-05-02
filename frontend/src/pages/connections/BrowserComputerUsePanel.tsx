/**
 * BrowserComputerUsePanel -- Browser + Computer Use connectors.
 *
 * PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): the founder asked for
 * Browser / Computer Use as a first-class tab. Includes:
 *   - Playwright (Microsoft, low-risk web automation)
 *   - Chrome DevTools MCP (Google, inspect-and-observe)
 *   - Browserbase (cloud browser, paid, coming-soon)
 *   - Desktop Commander (high-risk: terminal + filesystem)
 *   - Windows MCP (Windows-only, high-risk)
 *
 * Honest copy at the top:
 *   "Browser tools let Daena open pages, inspect UI, click, fill
 *    forms, test flows, and observe results. They require explicit
 *    permission and run in your local / runtime environment. Daena
 *    does not bypass anti-bot systems and never claims to evade
 *    detection."
 */

import { useMemo, useState } from 'react'
import {
  AlertTriangle, Globe, Loader2, RefreshCw, Search, ShieldAlert,
} from 'lucide-react'

import {
  type LifecycleState,
  useMarketplaceCards,
} from '@/hooks/useMarketplace'
import { useConnectionsV2 } from '@/hooks/useConnectionsV2'

import MarketplaceCard from './MarketplaceCard'

export default function BrowserComputerUsePanel() {
  const { cards, loading, error, refresh } = useMarketplaceCards()
  const { probe, enable } = useConnectionsV2()
  const [search, setSearch] = useState('')
  const [activeKind, setActiveKind] = useState<'all' | 'browser_tool' | 'computer_use'>('all')
  const [busyId, setBusyId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const onlyBrowser = cards.filter(
      (c) => c.catalog.kind === 'browser_tool' || c.catalog.kind === 'computer_use',
    )
    const q = search.trim().toLowerCase()
    return onlyBrowser.filter((c) => {
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
            <Globe size={12} className="mr-1 inline" />
            Browser &amp; Computer Use
          </p>
          <h2 className="mt-1 text-base font-semibold text-starlight-100">
            {callable} of {filtered.length} browser tool{filtered.length === 1 ? '' : 's'} callable
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-starlight-500">
            Browser tools let Daena open pages, inspect UI, click, fill
            forms, test flows, and observe results. They require
            explicit permission and run in your local / runtime
            environment. Daena does not bypass anti-bot systems and
            never claims to evade detection.
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

      <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-200">
        <ShieldAlert size={12} className="mr-1 inline" />
        <strong>Computer Use connectors carry HIGH risk.</strong> They can
        run shell commands, manage processes, and modify files. Asset
        Shield + governance gates still apply, but enable only when you
        understand the operator-consent surface. This PR ships catalog
        cards + Setup guides; Daena does not run live browser /
        computer-use sessions yet.
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
          All ({cards.filter((c) => c.catalog.kind === 'browser_tool' || c.catalog.kind === 'computer_use').length})
        </button>
        <button
          onClick={() => setActiveKind('browser_tool')}
          className={`rounded-md border px-2.5 py-1 text-[11px] ${
            activeKind === 'browser_tool'
              ? 'border-primary-500/40 bg-primary-500/15 text-primary-200'
              : 'border-white/5 bg-white/[0.03] text-starlight-400 hover:bg-white/5'
          }`}
        >
          Browser ({cards.filter((c) => c.catalog.kind === 'browser_tool').length})
        </button>
        <button
          onClick={() => setActiveKind('computer_use')}
          className={`rounded-md border px-2.5 py-1 text-[11px] ${
            activeKind === 'computer_use'
              ? 'border-rose-500/40 bg-rose-500/15 text-rose-200'
              : 'border-white/5 bg-white/[0.03] text-starlight-400 hover:bg-white/5'
          }`}
        >
          Computer Use ({cards.filter((c) => c.catalog.kind === 'computer_use').length})
        </button>
      </div>

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search browser / computer use tools..."
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
          Loading browser catalog...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          No browser tools match your filter.
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
