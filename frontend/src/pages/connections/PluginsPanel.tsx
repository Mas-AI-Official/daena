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
import { useGoogleSetupStatus } from '@/hooks/useGoogleSetupStatus'
import { toast } from '@/stores/toastStore'

import PluginCardView from './PluginCardView'
import {
  type PluginCard,
  type PluginStatus,
  pluginCardFromMarketplaceCard,
} from './pluginCard'
// Acceptance fix (Sprint-7): the operator lands on Plugins by default.
// Hoist the acceptance status + first-callable wizard ABOVE the grid so
// the founder sees "Can I use Daena right now?" and the wizard the
// moment the page loads -- they used to be hidden inside Advanced >
// Overview, which is exactly the confusion this PR removes.
import AcceptanceStatusPanel from './AcceptanceStatusPanel'
import FirstCallableWizard from './FirstCallableWizard'
// PR-CONNECTIONS-F1 (2026-05-06): the operator-visible copy in
// AccountStatusLine reads "Open the Plugins tab below and click Connect
// on Gmail" -- but the guide itself was only mounted under
// Advanced > apps. Mount it AT THE TOP of the Plugins tab when Google
// is not yet ready so the UI matches the copy.
import GoogleAccountSetupGuide from './GoogleAccountSetupGuide'

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
  // PR-CONNECTIONS-F1 (2026-05-06): gate the Google setup guide on the
  // live readiness probe. Renders the guide ONLY while Google is not
  // ready -- once both accounts are connected + the OAuth client is
  // configured, the guide self-removes and the operator sees a clean
  // grid. Loading state passes through (status === null) so the page
  // does not flash a guide that disappears half a second later.
  const { status: googleStatus } = useGoogleSetupStatus()
  const showGoogleGuide = googleStatus !== null && !googleStatus.ready
  // PR-CONNECTIONS-FIX-5 (2026-05-06): pull V2 cli_runtime rows so we
  // know which CLI subscriptions (Claude Code / Codex / Gemini CLI)
  // are callable on this machine. AI provider cards consult this and
  // surface the CLI as the primary path when applicable.
  const { rows: cliRows } = useConnectionsV2('cli_runtime')
  const [search, setSearch] = useState('')
  const [activeStatus, setActiveStatus] = useState<'all' | PluginStatus>('all')
  const [activeCategory, setActiveCategory] = useState<'all' | CatalogCategory>('all')
  const [busyId, setBusyId] = useState<string | null>(null)
  // PR-CONNECTIONS-FIX-3 (2026-05-06): hide catalog-only "Coming soon"
  // entries by default. They are roadmap parity (Daena cannot install
  // or probe them yet) and dilute the operator's signal-to-noise on
  // the main grid. Reveal via the inline toggle in the header. Stored
  // per-tab state, not localStorage, so a fresh session starts clean.
  const [showRoadmap, setShowRoadmap] = useState(false)

  // ── PR-CONNECTIONS-FIX-5: CLI subscription map ──
  //
  // Maps the api_provider catalog id (lowercased + dashed) to the
  // paired CLI runtime's display label + callable state. Used by the
  // PluginCardView to flip the AI provider card's primary action from
  // "Configure" (paste API key) to "Use as Main Brain" (deep-link to
  // the Brain tab) when the subscription path is the right one.
  //
  // The mapping is intentionally narrow -- only the three CLI runtimes
  // whose providers a Daena operator typically pays for as a
  // subscription. Adding more later requires explicit catalog work.
  const cliSubscriptionByProviderId = useMemo<
    Record<string, { runtime_id: string; label: string; callable: boolean }>
  >(() => {
    const out: Record<string, { runtime_id: string; label: string; callable: boolean }> = {}
    const RUNTIME_TO_PROVIDER: Record<string, { providerId: string; label: string }> = {
      claude_code: { providerId: 'provider-anthropic', label: 'Claude Code subscription' },
      codex: { providerId: 'provider-openai', label: 'Codex CLI subscription' },
      gemini_cli: { providerId: 'provider-google-gemini', label: 'Gemini CLI subscription' },
    }
    for (const r of cliRows) {
      const config = (r.config ?? {}) as Record<string, unknown>
      const rid = String(
        (typeof config._runtime_id === 'string' && config._runtime_id) || r.slug || '',
      ).toLowerCase()
      const map = RUNTIME_TO_PROVIDER[rid]
      if (!map) continue
      const callable = r.label === 'healthy' || r.label === 'healthy_stale'
      out[map.providerId] = {
        runtime_id: rid,
        label: map.label,
        callable,
      }
    }
    return out
  }, [cliRows])

  // ── Status-priority sort ──
  //
  // Connected first, then needs_auth, installed, available, failed,
  // not_supported, coming_soon (when shown). Inside each band, sort by
  // name. This puts working connections at the top so the operator's
  // first read of the page tells the truth about what they have, not
  // a 57-card alphabetical pile.
  const STATUS_RANK: Record<PluginStatus, number> = {
    connected: 0,
    needs_auth: 1,
    installed: 2,
    available: 3,
    failed: 4,
    not_supported_on_os: 5,
    coming_soon: 6,
  }

  const plugins = useMemo<PluginCard[]>(() => {
    const all = cards.map(pluginCardFromMarketplaceCard)
    const filtered = showRoadmap ? all : all.filter((p) => p.status !== 'coming_soon')
    return filtered.sort((a, b) => {
      const ra = STATUS_RANK[a.status] ?? 99
      const rb = STATUS_RANK[b.status] ?? 99
      if (ra !== rb) return ra - rb
      return a.name.localeCompare(b.name)
    })
  }, [cards, showRoadmap])

  const hiddenRoadmapCount = useMemo(
    () => cards
      .map(pluginCardFromMarketplaceCard)
      .filter((p) => p.status === 'coming_soon').length,
    [cards],
  )

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
    // PR-CONN-PLUGIN-INSTALL-UX-POLISH (2026-05-03):
    // Surface probe outcome with a toast so the operator does not have
    // to read the badge color to know what happened. Look up the plugin
    // by row id so the toast carries the human name. The result of
    // `probe()` is structured (success / outcome with failure_dim+reason
    // / network error) so we match all three branches honestly.
    setBusyId(rowId)
    const target = plugins.find((p) => p.v2_row_id === rowId)
    const name = target?.name ?? 'plugin'
    try {
      const res = await probe(rowId)
      if (res.ok && res.outcome?.success) {
        toast.success(
          `${name} probe succeeded. Skills are ready -- click them to draft a chat.`,
        )
      } else if (res.ok && res.outcome) {
        const dim = res.outcome.failure_dim ?? 'callable'
        const reason = res.outcome.failure_reason ?? 'no reason returned'
        toast.error(`${name} probe failed at ${dim}: ${reason}`)
      } else {
        toast.error(`${name} probe could not run: ${res.error ?? 'unknown error'}`)
      }
      refresh()
    } finally {
      setBusyId(null)
    }
  }

  async function handleEnable(rowId: string) {
    setBusyId(rowId)
    const target = plugins.find((p) => p.v2_row_id === rowId)
    const name = target?.name ?? 'plugin'
    try {
      const res = await enable(rowId)
      if (res.ok) {
        toast.success(`${name} enabled. Probe it next to confirm it works.`)
      } else {
        toast.error(`Could not enable ${name}: ${res.error ?? 'unknown error'}`)
      }
      refresh()
    } finally {
      setBusyId(null)
    }
  }

  // Hoisted from OverviewPanel: the wizard renders only when callable=0.
  // Counts is computed below from the same `cards` we already poll.
  const totalCatalog = cards.length
  const callableNow = counts.connected ?? 0

  return (
    <div className="space-y-4">
      {/* PR-CONNECTIONS-F1 (2026-05-06): Google setup guide -- only when
          activation is incomplete. The copy in AccountStatusLine sends
          the operator HERE; this is the canonical render now. The
          duplicate render in AppsStorePanel was removed in the same PR. */}
      {showGoogleGuide && <GoogleAccountSetupGuide />}

      {/* Acceptance status -- "Can I use Daena right now?" */}
      <AcceptanceStatusPanel />

      {/* First-callable wizard -- only when callable=0 and catalog is loaded. */}
      {callableNow === 0 && totalCatalog > 0 && (
        <FirstCallableWizard catalogTotal={totalCatalog} />
      )}

      <div className="flex flex-wrap items-end justify-between gap-3 rounded-xl border border-white/5 bg-midnight-400/30 px-4 py-3">
        <div>
          <h2 className="text-base font-semibold text-starlight-100">
            {counts.connected} connected · {counts.needs_auth} needs auth ·{' '}
            {counts.installed} installed · {counts.available} available
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-starlight-500">
            Browse plugins. Each card is a real integration -- MCP
            servers, apps, browser tools, local models, LLM providers,
            skill bundles. Click a card for details. A card is
            &ldquo;Connected&rdquo; only when a real probe proves it
            works. Provider keys live in Settings -&gt; API Keys.
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
          {hiddenRoadmapCount > 0 && (
            <label
              className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2.5 py-1.5 text-[11px] text-starlight-400 hover:bg-white/10 cursor-pointer"
              title="Roadmap-only entries are catalog metadata for connectors Daena cannot install or probe yet. Hidden by default to keep the grid focused on actionable cards."
            >
              <input
                type="checkbox"
                checked={showRoadmap}
                onChange={(e) => setShowRoadmap(e.target.checked)}
                className="accent-primary-500"
              />
              Show roadmap ({hiddenRoadmapCount})
            </label>
          )}
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
                  busy={busyId !== null && busyId === plugin.v2_row_id}
                  onProbe={handleProbe}
                  onEnable={handleEnable}
                  cliAlternative={cliSubscriptionByProviderId[plugin.id] ?? null}
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
