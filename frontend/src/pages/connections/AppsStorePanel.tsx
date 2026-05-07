/**
 * AppsStorePanel -- OAuth-backed apps marketplace.
 *
 * PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): replaces the legacy
 * AppsPanel. Surfaces the curated catalog of OAuth apps so the
 * operator sees what Daena CAN connect to (Gmail, Calendar, Drive,
 * GitHub, Figma, Slack, Canva, Notion, Stripe, Cloudflare, Sentry)
 * even when they have not configured the OAuth client yet.
 *
 * Honesty:
 *   - "Available" shown when no V2 row exists (no OAuth client_id yet)
 *   - "Configured" / "Reachable" / "Callable" reflects V2 truth
 *   - "coming-soon" entries surface a Setup guide with vendor docs
 *   - No card claims "Connected" without a real OAuth-token probe
 */

import { useMemo, useState } from 'react'
import {
  AlertTriangle, AppWindow, Loader2, RefreshCw, Search,
} from 'lucide-react'

import {
  type LifecycleState,
  useMarketplaceCards,
} from '@/hooks/useMarketplace'
import { useConnectionsV2 } from '@/hooks/useConnectionsV2'

// PR-CONNECTIONS-F1 (2026-05-06): GoogleAccountSetupGuide moved to
// PluginsPanel (the canonical surface operators land on). Keeping a
// duplicate render here would split the source of truth and confuse
// any operator who happens to scroll Advanced -> apps.
import MarketplaceCard from './MarketplaceCard'

export default function AppsStorePanel() {
  const { cards, loading, error, refresh } = useMarketplaceCards()
  const { probe, enable } = useConnectionsV2()
  const [search, setSearch] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const onlyApps = cards.filter((c) => c.catalog.kind === 'oauth_app')
    const q = search.trim().toLowerCase()
    if (!q) return onlyApps
    return onlyApps.filter(
      (c) =>
        c.catalog.display_name.toLowerCase().includes(q) ||
        c.catalog.vendor.toLowerCase().includes(q) ||
        c.catalog.short_description.toLowerCase().includes(q),
    )
  }, [cards, search])

  const callable = filtered.filter((c) => isCallable(c.lifecycle)).length
  const configured = filtered.filter(
    (c) =>
      c.lifecycle === 'configured' ||
      c.lifecycle === 'reachable' ||
      c.lifecycle === 'callable' ||
      c.lifecycle === 'enabled',
  ).length

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
            <AppWindow size={12} className="mr-1 inline" />
            Apps
          </p>
          <h2 className="mt-1 text-base font-semibold text-starlight-100">
            {callable} callable · {configured} configured · {filtered.length} available
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-starlight-500">
            OAuth-backed apps. To connect: paste the OAuth client ID +
            secret in <strong>Settings -&gt; Integrations</strong>, then
            run the OAuth flow. A card is &ldquo;callable&rdquo; only
            after a real OAuth-token probe (refresh + userinfo).
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

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search apps..."
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
          Loading apps catalog...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          No apps match your filter.
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
