/**
 * ConnectionsPage -- product-grade Connections surface.
 *
 * PR-CONN-UX-RESCUE (2026-05-02): drops V1/V2 terminology from the
 * default user-facing labels. The page now renders 7 product tabs
 * (All Connections / Main Brain / Runtimes / MCP Servers / Apps /
 * Skill Packs / Local Models) plus a single Advanced reveal that
 * houses migration / debug / legacy. Default view is the V2-truth
 * surface only; no Legacy plugin cards shown without the operator
 * explicitly opening Advanced.
 *
 * Top-level toolbar carries one canonical action: "Discover installed
 * tools". Per-source summary surfaced via toast + the per-tab empty
 * state so 0-MCP cases now read "checked N paths, 0 had mcpServers"
 * instead of the bare "0 found" the founder called out.
 *
 * Why this layout:
 *   - The founder's complaint was that the page felt duplicated +
 *     migration-internal. The new layout treats V2 as the product;
 *     V1 lives behind one Advanced tab clearly labelled "migration /
 *     debug." No tab uses the word "V2" or "V1" in its label.
 *   - "Skill packs" gets its own tab so capability bundles never
 *     visually compete with callable connectors.
 *   - "Local Models" gets its own tab so vLLM / Ollama unreachability
 *     can carry the Docker/WSL guidance without crowding the global
 *     summary.
 */
import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  AppWindow,
  BookOpen,
  BrainCircuit,
  Cpu,
  Download,
  Layers,
  Loader2,
  Server,
  Terminal,
  Wrench,
} from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import { toast } from '@/stores/toastStore'
import { runDiscoveryRefresh } from '@/hooks/useConnectionsV2'
import type { DiscoveryReport } from '@/hooks/useConnectionsV2'

import AppsPanel from './connections/AppsPanel'
import ConnectionsV2Panel from './connections/ConnectionsV2Panel'
import LocalModelsPanel from './connections/LocalModelsPanel'
import MainBrainPanel from './connections/MainBrainPanel'
import McpServersPanel from './connections/McpServersPanel'
import McpServersV2Panel from './connections/McpServersV2Panel'
import PluginsCatalogBrowser from './connections/PluginsCatalogBrowser'
import RuntimesPanel from './connections/RuntimesPanel'
import SkillPacksPanel from './connections/SkillPacksPanel'

const PRIMARY_TABS = [
  { key: 'all', label: 'All Connections', icon: Layers },
  { key: 'main-brain', label: 'Main Brain', icon: BrainCircuit },
  { key: 'runtimes', label: 'Runtimes', icon: Terminal },
  { key: 'mcp', label: 'MCP Servers', icon: Server },
  { key: 'apps', label: 'Apps', icon: AppWindow },
  { key: 'skill-packs', label: 'Skill Packs', icon: BookOpen },
  { key: 'local-models', label: 'Local Models', icon: Cpu },
] as const

const ADVANCED_TAB = { key: 'advanced', label: 'Advanced', icon: Wrench } as const

type PrimaryKey = typeof PRIMARY_TABS[number]['key']
type TabKey = PrimaryKey | typeof ADVANCED_TAB.key

const SHOW_ADVANCED_LS_KEY = 'daena.connections.show_advanced'
const LAST_DISCOVERY_LS_KEY = 'daena.connections.last_discovery'

export default function ConnectionsPage() {
  usePageTitle('Connections')
  const [activeTab, setActiveTab] = useState<TabKey>('all')
  const [discovering, setDiscovering] = useState(false)
  const [lastReport, setLastReport] = useState<DiscoveryReport | null>(() => {
    if (typeof window === 'undefined') return null
    const raw = window.localStorage.getItem(LAST_DISCOVERY_LS_KEY)
    if (!raw) return null
    try {
      return JSON.parse(raw) as DiscoveryReport
    } catch {
      return null
    }
  })

  // Show-advanced toggle persists per-browser. Auto-flip ON when the
  // operator deep-links into the advanced tab so they're never trapped.
  const [showAdvanced, setShowAdvanced] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(SHOW_ADVANCED_LS_KEY) === 'true'
  })
  useEffect(() => {
    if (activeTab === 'advanced' && !showAdvanced) {
      setShowAdvanced(true)
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(SHOW_ADVANCED_LS_KEY, 'true')
      }
    }
  }, [activeTab, showAdvanced])

  function handleShowAdvancedToggle() {
    const next = !showAdvanced
    setShowAdvanced(next)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SHOW_ADVANCED_LS_KEY, String(next))
    }
    if (!next && activeTab === 'advanced') setActiveTab('all')
  }

  async function runDiscover() {
    setDiscovering(true)
    try {
      const res = await runDiscoveryRefresh()
      if (!res.ok) {
        toast.error(res.error || 'Discovery failed')
        return
      }
      const report = res.report ?? null
      setLastReport(report)
      if (report && typeof window !== 'undefined') {
        window.localStorage.setItem(
          LAST_DISCOVERY_LS_KEY,
          JSON.stringify(report),
        )
      }
      const created = report?.total_created ?? 0
      const failed = report?.total_failed ?? 0
      toast.success(
        `Discovery complete: ${created} new, ${
          report?.total_skipped_existing ?? 0
        } existed${failed > 0 ? `, ${failed} failed` : ''}`,
      )
      // Notify any open V2 panel hooks to refetch.
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('daena:retry-pending'))
      }
    } finally {
      setDiscovering(false)
    }
  }

  const visibleTabs: ReadonlyArray<{ key: TabKey; label: string; icon: typeof Layers }> =
    showAdvanced ? [...PRIMARY_TABS, ADVANCED_TAB] : PRIMARY_TABS

  return (
    <div className="min-h-full bg-midnight-900 text-starlight-100">
      <div className="border-b border-white/5 bg-midnight-400/40">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-xs font-medium uppercase tracking-[0.2em] text-accent-cyan">
                Connections
              </div>
              <h1 className="text-2xl font-display font-semibold text-starlight-50">
                Runtimes, MCP Servers, Apps, and Local Models
              </h1>
              <p className="mt-1 max-w-3xl text-sm text-starlight-400">
                Daena routes work through whatever you connect here. Click
                Discover to scan installed CLIs and configured providers --
                nothing is marked &ldquo;callable&rdquo; until a real probe
                proves it.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={runDiscover}
                disabled={discovering}
                title="Scan installed CLIs (Claude Code, Codex, Gemini), configured API providers, OAuth catalog, local model endpoints, and the skill-pack catalog. Idempotent. Never reads secret values."
                className="inline-flex items-center gap-2 rounded-lg border border-accent-cyan/30 bg-accent-cyan/10 px-3 py-2 text-xs font-medium text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
              >
                {discovering ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Download size={14} />
                )}
                Discover installed tools
              </button>
              <label
                className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-[11px] text-starlight-400 hover:text-starlight-200"
                title="Show migration / debug / legacy panels. The Advanced tab is operator-only; the live product surface is the primary tabs above."
              >
                <input
                  type="checkbox"
                  checked={showAdvanced}
                  onChange={handleShowAdvancedToggle}
                  className="h-3 w-3 rounded border-white/20 bg-transparent text-primary-500"
                />
                <span>Show advanced</span>
              </label>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <div className="flex flex-1 flex-wrap gap-2 overflow-x-auto pb-1">
              {visibleTabs.map((tab) => {
                const Icon = tab.icon
                const active = activeTab === tab.key
                const isAdvanced = tab.key === 'advanced'
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`inline-flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                      active
                        ? isAdvanced
                          ? 'border-amber-500/40 bg-amber-500/15 text-amber-200'
                          : 'border-primary-500/40 bg-primary-500/15 text-primary-200'
                        : 'border-white/5 bg-white/[0.03] text-starlight-400 hover:bg-white/5 hover:text-starlight-200'
                    }`}
                  >
                    <Icon size={14} />
                    {tab.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-5">
        {activeTab === 'all' && (
          <ConnectionsV2Panel discoveryReport={lastReport} onDiscover={runDiscover} discovering={discovering} />
        )}
        {activeTab === 'main-brain' && <MainBrainPanel />}
        {activeTab === 'runtimes' && <RuntimesPanel />}
        {activeTab === 'mcp' && (
          <McpServersV2Panel discoveryReport={lastReport} onDiscover={runDiscover} discovering={discovering} />
        )}
        {activeTab === 'apps' && <AppsPanel />}
        {activeTab === 'skill-packs' && <SkillPacksPanel />}
        {activeTab === 'local-models' && <LocalModelsPanel />}
        {activeTab === 'advanced' && <AdvancedPanel />}
      </div>
    </div>
  )
}

// -----------------------------------------------------------------
// Advanced -- migration / debug / legacy reveal.
// Houses both the previous V1 connections panels and any "internal"
// developer-facing copy. Never the default view; never visually
// dominant.
// -----------------------------------------------------------------

function AdvancedPanel() {
  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
        <AlertTriangle size={16} className="mt-0.5 shrink-0" />
        <div>
          <strong>Advanced migration / debug view.</strong> Not the live
          connection truth.
          <p className="mt-1 text-[11px] text-amber-200/80">
            The panels below are the legacy plugin browser and MCP detect /
            install flow. They use the older &ldquo;credentials present ==
            connected&rdquo; heuristic and do NOT reflect real probe truth.
            Use the primary tabs (All Connections / MCP Servers / Apps /
            Local Models) for the canonical answer to &ldquo;is this actually
            callable?&rdquo;
          </p>
        </div>
      </div>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-starlight-100">
          Legacy plugin browser
        </h3>
        <p className="text-[11px] text-starlight-500">
          Older catalog used for migration debugging. Install + disconnect
          actions still function but do not mirror to the canonical
          registry unless the backend migration flag is on.
        </p>
        <PluginsCatalogBrowser />
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-starlight-100">
          Legacy MCP detector
        </h3>
        <p className="text-[11px] text-starlight-500">
          Original detect / probe / import view. The MCP Servers tab above
          is the canonical truth surface; this panel is kept for migration
          debugging.
        </p>
        <McpServersPanel />
      </section>

      <details className="rounded-lg border border-white/5 bg-white/[0.02] px-4 py-3 text-xs text-starlight-400">
        <summary className="cursor-pointer text-starlight-300 hover:text-starlight-100">
          Internal endpoints + flags
        </summary>
        <div className="mt-2 space-y-1 text-[11px] text-starlight-500">
          <div>
            Discovery API:{' '}
            <code className="text-starlight-300">
              POST /api/v1/connections/v2/discovery/refresh
            </code>
          </div>
          <div>
            Per-row insert:{' '}
            <code className="text-starlight-300">
              POST /api/v1/connections/v2
            </code>
          </div>
          <div>
            Provider seeder (FOUNDER+):{' '}
            <code className="text-starlight-300">
              POST /api/v1/connections/v2/reconciliation/seed-providers
            </code>
          </div>
          <div>
            Backend migration flag:{' '}
            <code className="text-starlight-300">
              USE_CONNECTION_REGISTRY_V2
            </code>{' '}
            (default OFF in dev + production; do not flip without
            migration plan).
          </div>
        </div>
      </details>
    </div>
  )
}
