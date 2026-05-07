/**
 * ConnectionsPage -- simplified Brain / Plugins / Advanced.
 *
 * Founder pivot 2026-05-02: collapse the marketplace into a 3-tab UX
 * modeled on Codex's plugin marketplace. The previous 9 specialized
 * tabs (MCP / Apps / Browser / Local Models / Skill Packs / etc.) are
 * removed from the user-facing surface; their concerns now live in
 * one "Plugins" grid that maps every internal kind onto a unified
 * PluginCard view-model.
 *
 * Tabs:
 *   1. Brain     -- pick the active primary runtime / provider
 *   2. Plugins   -- one Codex-style marketplace grid
 *   3. Advanced  -- V2 registry, legacy V1 panels, internal kinds,
 *                   raw discovery payload, USE_CONNECTION_REGISTRY_V2
 *
 * Hard rules honored:
 *   - No V1 / V2 terminology in normal-mode UI labels
 *   - "Connected" only when V2 truth says callable=true
 *   - "Install" never appears unless the backend can safely install;
 *     today every install path surfaces as "Setup guide"
 *   - Discovery button NEVER auto-installs anything
 *   - Skill packs render INSIDE Plugins with a clear caption
 *
 * Honesty (project Rule 17):
 *   - Discovery summary toast carries per-source counts
 *   - Empty / failed states call out concrete next actions
 *   - Advanced tab is opt-in (operator must enable Show advanced)
 */

import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  AppWindow,
  BookOpen,
  BrainCircuit,
  Cpu,
  Download,
  Globe,
  Loader2,
  Server,
  Terminal,
  Wrench,
} from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import { toast } from '@/stores/toastStore'
import {
  type DiscoveryReport,
  runDiscoveryRefresh,
} from '@/hooks/useConnectionsV2'

import AppsStorePanel from './connections/AppsStorePanel'
import BrowserComputerUsePanel from './connections/BrowserComputerUsePanel'
import LocalModelsPanel from './connections/LocalModelsPanel'
import MainBrainPanel from './connections/MainBrainPanel'
import McpServersPanel from './connections/McpServersPanel'
import McpStorePanel from './connections/McpStorePanel'
import OverviewPanel from './connections/OverviewPanel'
import PluginsCatalogBrowser from './connections/PluginsCatalogBrowser'
import PluginsPanel from './connections/PluginsPanel'
import RuntimesPanel from './connections/RuntimesPanel'
import SkillPacksPanel from './connections/SkillPacksPanel'

const PRIMARY_TABS = [
  { key: 'brain', label: 'Brain', icon: BrainCircuit },
  { key: 'plugins', label: 'Plugins', icon: AppWindow },
] as const

const ADVANCED_TAB = { key: 'advanced', label: 'Advanced', icon: Wrench } as const

type PrimaryKey = typeof PRIMARY_TABS[number]['key']
type TabKey = PrimaryKey | typeof ADVANCED_TAB.key

const SHOW_ADVANCED_LS_KEY = 'daena.connections.show_advanced'
const LAST_DISCOVERY_LS_KEY = 'daena.connections.last_discovery'
const LAST_DISCOVERY_AT_LS_KEY = 'daena.connections.last_discovery_at'
const ACTIVE_TAB_LS_KEY = 'daena.connections.active_tab'

export default function ConnectionsPage() {
  usePageTitle('Connections')
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    if (typeof window === 'undefined') return 'plugins'
    // PR-CONNECTIONS-FIX-DEEP-LINK (2026-05-06): hash-based deep-links so
    // sibling pages (Provider Keys, AI provider card "Use as Main Brain"
    // button) can route the operator straight to a specific tab.
    // Hash wins over localStorage so a fresh deep-link is never trapped
    // by a previously remembered tab.
    const hash = window.location.hash.replace('#', '').toLowerCase()
    if (hash === 'brain' || hash === 'plugins' || hash === 'advanced') return hash
    const saved = window.localStorage.getItem(ACTIVE_TAB_LS_KEY)
    if (saved === 'brain' || saved === 'plugins' || saved === 'advanced') return saved
    return 'plugins'
  })

  // Clear the URL hash after consuming it so a later interaction (close
  // + reopen / nav back) does not silently re-pin the deep-linked tab.
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!window.location.hash) return
    const h = window.location.hash.replace('#', '').toLowerCase()
    if (h !== 'brain' && h !== 'plugins' && h !== 'advanced') return
    const next = `${window.location.pathname}${window.location.search}`
    window.history.replaceState({}, '', next)
  }, [])
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
  const [lastDiscoveryAt, setLastDiscoveryAt] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null
    return window.localStorage.getItem(LAST_DISCOVERY_AT_LS_KEY)
  })

  // Persist active tab so reload returns to the last view.
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(ACTIVE_TAB_LS_KEY, activeTab)
    }
  }, [activeTab])

  // Show-advanced toggle persists per-browser. Auto-flip ON when the
  // operator deep-links into the advanced tab so they're never trapped.
  //
  // PR-CONNECTIONS-MINI-SIMPLIFY (2026-05-06): one-time migration that
  // clears the prior "true" stickiness. Operators ticked "Show advanced"
  // months ago to debug something, then localStorage trapped them on the
  // V1/V2 debug surface across every session. Plugins tab is the
  // canonical view -- Advanced is opt-in. After this migration runs
  // once, the toggle behaves normally: tick to opt in, untick to opt
  // out, localStorage remembers the choice for the next session.
  const [showAdvanced, setShowAdvanced] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    const MIGRATION_KEY = 'connections.showAdvanced.migrated.2026-05-06'
    if (window.localStorage.getItem(MIGRATION_KEY) !== 'true') {
      window.localStorage.removeItem(SHOW_ADVANCED_LS_KEY)
      window.localStorage.setItem(MIGRATION_KEY, 'true')
    }
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
    if (!next && activeTab === 'advanced') setActiveTab('plugins')
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
      const now = new Date().toISOString()
      setLastDiscoveryAt(now)
      if (report && typeof window !== 'undefined') {
        window.localStorage.setItem(
          LAST_DISCOVERY_LS_KEY,
          JSON.stringify(report),
        )
        window.localStorage.setItem(LAST_DISCOVERY_AT_LS_KEY, now)
      }
      const created = report?.total_created ?? 0
      const failed = report?.total_failed ?? 0
      const pathsSearched = report?.mcp_paths_searched?.length ?? 0
      const mcpFound = report?.sources?.find((s) => s.source === 'mcp_servers')?.total_created ?? 0
      // Honest summary toast -- pull per-source counts from the report
      const sourceSummary = (report?.sources ?? [])
        .map((s) => `${s.source}: +${s.total_created}`)
        .filter((line) => !line.endsWith(': +0'))
        .slice(0, 4)
        .join(' · ')
      const mcpHint =
        mcpFound === 0 && pathsSearched > 0
          ? ` -- No installed MCP configs found (searched ${pathsSearched} paths). Open Advanced for details.`
          : ''
      toast.success(
        `Discovery complete: ${created} new, ${
          report?.total_skipped_existing ?? 0
        } existed${failed > 0 ? `, ${failed} failed` : ''}${
          sourceSummary ? ` -- ${sourceSummary}` : ''
        }${mcpHint}`,
      )
      // Notify any open V2 panel hooks to refetch.
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('daena:retry-pending'))
      }
    } finally {
      setDiscovering(false)
    }
  }

  const visibleTabs: ReadonlyArray<{ key: TabKey; label: string; icon: typeof BrainCircuit }> =
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
                Pick your Brain. Browse Plugins.
              </h1>
              <p className="mt-1 max-w-3xl text-sm text-starlight-400">
                Brain decides who orchestrates your work. Plugins are the
                tools Daena can call -- MCP servers, OAuth apps, browser
                automation, local models, skill packs. Nothing is marked
                &ldquo;Connected&rdquo; until a real probe proves it.
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
                title="Show registry / debug / legacy panels."
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
            {lastDiscoveryAt && (
              <p className="text-[10px] text-starlight-500">
                Last discovery: {new Date(lastDiscoveryAt).toLocaleString()}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-5">
        {activeTab === 'brain' && <MainBrainPanel />}
        {activeTab === 'plugins' && (
          <PluginsPanel onDiscover={runDiscover} discovering={discovering} />
        )}
        {activeTab === 'advanced' && (
          <AdvancedPanel
            discoveryReport={lastReport}
            onDiscover={runDiscover}
            discovering={discovering}
            onBackToPlugins={() => setActiveTab('plugins')}
          />
        )}
      </div>
    </div>
  )
}

// -----------------------------------------------------------------
// Advanced -- V2 registry / debug / legacy panels.
// Houses the per-kind specialized panels (renamed for clarity), the
// V1 plugin browser + MCP detector, the discovery payload viewer, and
// internal endpoint references.
// -----------------------------------------------------------------

const ADVANCED_SECTIONS = [
  { key: 'overview', label: 'Registry overview', icon: Wrench },
  { key: 'runtimes', label: 'Runtimes (V2)', icon: Terminal },
  { key: 'mcp', label: 'MCP servers (V2)', icon: Server },
  { key: 'apps', label: 'OAuth apps (V2)', icon: AppWindow },
  { key: 'browser', label: 'Browser tools (V2)', icon: Globe },
  { key: 'local', label: 'Local models (V2)', icon: Cpu },
  { key: 'skill_packs', label: 'Skill packs (V2)', icon: BookOpen },
  { key: 'legacy_v1', label: 'Legacy V1 panels', icon: AlertTriangle },
  { key: 'debug', label: 'Discovery + endpoints', icon: Wrench },
] as const

type AdvancedKey = typeof ADVANCED_SECTIONS[number]['key']

function AdvancedPanel({
  discoveryReport, onDiscover, discovering, onBackToPlugins,
}: {
  discoveryReport: DiscoveryReport | null
  onDiscover: () => void
  discovering: boolean
  onBackToPlugins: () => void
}) {
  const [section, setSection] = useState<AdvancedKey>('overview')

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
        <AlertTriangle size={16} className="mt-0.5 shrink-0" />
        <div className="flex-1">
          <strong>Advanced registry / debug view.</strong>{' '}
          Internal V2 / V1 surfaces. Normal users should use the Plugins
          tab; this view exposes the per-kind catalog (mcp_server,
          oauth_app, skill_pack, local_model, provider, cli_runtime),
          the legacy V1 panels, and the raw discovery payload.
        </div>
        <button
          onClick={onBackToPlugins}
          className="shrink-0 rounded-md border border-amber-400/40 bg-amber-400/10 px-3 py-1 text-[11px] font-medium text-amber-100 hover:bg-amber-400/20"
        >
          Back to Plugins marketplace
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[200px_1fr]">
        <aside>
          <p className="mb-2 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
            Registry sections
          </p>
          <ul className="space-y-0.5">
            {ADVANCED_SECTIONS.map((s) => {
              const Icon = s.icon
              const active = section === s.key
              return (
                <li key={s.key}>
                  <button
                    onClick={() => setSection(s.key)}
                    className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[11px] ${
                      active
                        ? 'bg-amber-500/15 text-amber-200'
                        : 'text-starlight-400 hover:bg-white/[0.03] hover:text-starlight-200'
                    }`}
                  >
                    <Icon size={11} />
                    {s.label}
                  </button>
                </li>
              )
            })}
          </ul>
        </aside>

        <div>
          {section === 'overview' && (
            <OverviewPanel
              onNavigateTab={(tab) => {
                // Map old tab keys to advanced sections.
                if (tab === 'mcp') setSection('mcp')
                else if (tab === 'apps') setSection('apps')
                else if (tab === 'browser') setSection('browser')
                else if (tab === 'local-models') setSection('local')
                else if (tab === 'skill-packs') setSection('skill_packs')
                else if (tab === 'runtimes') setSection('runtimes')
              }}
              lastDiscoveryAt={null}
            />
          )}
          {section === 'runtimes' && <RuntimesPanel />}
          {section === 'mcp' && (
            <McpStorePanel onDiscover={onDiscover} discovering={discovering} />
          )}
          {section === 'apps' && <AppsStorePanel />}
          {section === 'browser' && <BrowserComputerUsePanel />}
          {section === 'local' && <LocalModelsPanel />}
          {section === 'skill_packs' && <SkillPacksPanel />}
          {section === 'legacy_v1' && (
            <div className="space-y-6">
              {/* Sprint-7 acceptance fix (2026-05-04): clear top-of-section
                  warning so an operator who clicked here cannot mistake the
                  legacy panels for the canonical install path. */}
              <div className="flex items-start gap-3 rounded-md border border-rose-500/30 bg-rose-500/5 px-3 py-2 text-xs text-rose-200">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                <div>
                  <strong>Legacy / debug only.</strong>{' '}
                  Normal users should use the Plugins tab. Anything you
                  install or connect from here writes to the OLD V1
                  registry and may not mirror to the canonical V2 truth
                  ladder. Use this view ONLY for migration debugging or
                  reading legacy state.
                </div>
              </div>
              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-starlight-100">
                  Legacy plugin browser
                </h3>
                <p className="text-[11px] text-starlight-500">
                  Older catalog used for migration debugging. Install +
                  disconnect actions still function but do not mirror to
                  the canonical registry unless the backend migration
                  flag is on.
                </p>
                <PluginsCatalogBrowser />
              </section>
              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-starlight-100">
                  Legacy MCP detector
                </h3>
                <p className="text-[11px] text-starlight-500">
                  Original detect / probe / import view. The Plugins tab
                  is the canonical user surface; this panel is kept for
                  migration debugging.
                </p>
                <McpServersPanel />
              </section>
            </div>
          )}
          {section === 'debug' && (
            <DebugSection
              discoveryReport={discoveryReport}
              onDiscover={onDiscover}
              discovering={discovering}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function DebugSection({
  discoveryReport, onDiscover, discovering,
}: {
  discoveryReport: DiscoveryReport | null
  onDiscover: () => void
  discovering: boolean
}) {
  return (
    <div className="space-y-4">
      <details
        open
        className="rounded-lg border border-white/5 bg-white/[0.02] px-4 py-3 text-xs text-starlight-400"
      >
        <summary className="cursor-pointer text-starlight-300 hover:text-starlight-100">
          Discovery report payload (last run)
        </summary>
        <div className="mt-2 space-y-2">
          {!discoveryReport ? (
            <div className="text-starlight-500">
              No discovery has been run yet this session.{' '}
              <button
                onClick={onDiscover}
                disabled={discovering}
                className="ml-1 rounded border border-accent-cyan/30 bg-accent-cyan/10 px-2 py-0.5 text-[11px] text-accent-cyan disabled:opacity-50"
              >
                {discovering ? 'Discovering...' : 'Run discovery'}
              </button>
            </div>
          ) : (
            <>
              <p className="text-[11px] text-starlight-500">
                Last run: {discoveryReport.total_created} new ·{' '}
                {discoveryReport.total_skipped_existing} existed ·{' '}
                {discoveryReport.total_failed} failed ·{' '}
                {discoveryReport.mcp_paths_searched?.length ?? 0} MCP paths searched
              </p>
              <pre className="overflow-x-auto rounded-md border border-white/5 bg-midnight-900/40 p-2 text-[10px] text-starlight-400">
                {JSON.stringify(discoveryReport, null, 2)}
              </pre>
            </>
          )}
        </div>
      </details>

      <details className="rounded-lg border border-white/5 bg-white/[0.02] px-4 py-3 text-xs text-starlight-400">
        <summary className="cursor-pointer text-starlight-300 hover:text-starlight-100">
          Internal endpoints + flags
        </summary>
        <div className="mt-2 space-y-1 text-[11px] text-starlight-500">
          <div>
            Catalog API:{' '}
            <code className="text-starlight-300">
              GET /api/v1/connections/v2/catalog
            </code>
          </div>
          <div>
            Marketplace cards:{' '}
            <code className="text-starlight-300">
              GET /api/v1/connections/v2/marketplace/cards
            </code>
          </div>
          <div>
            Install plan:{' '}
            <code className="text-starlight-300">
              GET /api/v1/connections/v2/marketplace/install-plan/&lt;id&gt;
            </code>
          </div>
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
          <div className="mt-2">
            <strong>Internal kind labels:</strong> mcp_server, oauth_app,
            skill_pack, local_model, provider, cli_runtime, browser_tool,
            computer_use, api_provider
          </div>
          <div className="mt-2">
            Backend migration flag:{' '}
            <code className="text-starlight-300">
              USE_CONNECTION_REGISTRY_V2
            </code>{' '}
            (default OFF in dev + production). When on, the V2 registry
            is the source of truth for the chat orchestrator. When off,
            V2 is read-only and the V1 connection_service still drives
            install/probe writes. Do not flip without a migration plan.
          </div>
        </div>
      </details>
    </div>
  )
}
