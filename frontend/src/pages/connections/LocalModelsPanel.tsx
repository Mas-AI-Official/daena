/**
 * LocalModelsPanel -- local LLM endpoints (Ollama, vLLM, llama-server).
 *
 * PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): rewritten to use the
 * Marketplace card system. The catalog always lists Ollama + vLLM
 * even when not configured (operator sees "Available" + Setup guide
 * with the env var name they need).
 *
 * Honesty:
 *   - "Reachable" only after a successful HTTP probe of /v1/models or
 *     /api/tags. Configured but unreachable surfaces a Failed badge.
 *   - Base URL shown in the card body (config, not secret).
 *   - Setup guide explains Docker / WSL bridging hazards inline.
 */

import { useMemo, useState } from 'react'
import {
  AlertTriangle, Cpu, Loader2, RefreshCw, Search,
} from 'lucide-react'

import {
  type LifecycleState,
  useMarketplaceCards,
} from '@/hooks/useMarketplace'
import { useConnectionsV2 } from '@/hooks/useConnectionsV2'

import MarketplaceCard from './MarketplaceCard'

export default function LocalModelsPanel() {
  const { cards, loading, error, refresh } = useMarketplaceCards()
  const { probe, enable } = useConnectionsV2()
  const [search, setSearch] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const onlyLocal = cards.filter((c) => c.catalog.kind === 'local_model')
    const q = search.trim().toLowerCase()
    if (!q) return onlyLocal
    return onlyLocal.filter(
      (c) =>
        c.catalog.display_name.toLowerCase().includes(q) ||
        c.catalog.vendor.toLowerCase().includes(q) ||
        c.catalog.short_description.toLowerCase().includes(q),
    )
  }, [cards, search])

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
            <Cpu size={12} className="mr-1 inline" />
            Local Models
          </p>
          <h2 className="mt-1 text-base font-semibold text-starlight-100">
            {callable} of {filtered.length} local endpoint{filtered.length === 1 ? '' : 's'} reachable
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-starlight-500">
            Local LLM endpoints (Ollama, vLLM, llama-server). Daena calls
            them via OpenAI-compatible APIs. A row is &ldquo;callable&rdquo;
            only after a successful model-list probe. Note: Daena prefers
            llama-server (vLLM) by default; Ollama is supported but
            deprecated.
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
        <strong>Docker / WSL gotcha:</strong> if Daena runs in WSL or Docker,{' '}
        <code className="text-amber-100">127.0.0.1</code> may not resolve to
        the Windows host. Use{' '}
        <code className="text-amber-100">host.docker.internal</code> or the
        bridge IP, or run Daena natively on the same host as the local model
        server.
      </div>

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search local models..."
          aria-label="Search local models"
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
          Loading local model catalog...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          No local model endpoints match your filter.
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
