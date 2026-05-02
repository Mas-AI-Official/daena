/**
 * ConnectionsPage -- 4 primary tabs + optional Legacy/Advanced reveal.
 *
 * PR-CONNECTIONS-TRUTH-CLEANUP (2026-05-02): V2 truth is now the
 * canonical surface in dev/local. The Plugins and MCP Servers tabs
 * always render the V2 panel, regardless of the
 * USE_CONNECTION_REGISTRY_V2 backend flag. The previous "tab router"
 * (which fell back to V1 panels when the flag was off) is gone --
 * V1 panels live behind a "Show legacy / advanced" toggle that
 * persists per-browser to localStorage and is OFF by default. Direct
 * navigation to the legacy tab via deep link auto-flips the toggle on
 * so the operator is never trapped on a hidden route.
 *
 * Why: at 14 partly-overlapping connection surfaces (provider keys in
 * Settings, V1 plugin browser, V1 MCP browser, V2 truth panel,
 * Main Brain selector, etc.) the "what is connected?" question had no
 * single answer. V2 owns truth now; legacy stays accessible for
 * migration + debugging but never as the default story.
 */
import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  BrainCircuit,
  Layers,
  Package,
  Server,
  Wrench,
} from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import ConnectionsV2Panel from './connections/ConnectionsV2Panel'
import MainBrainPanel from './connections/MainBrainPanel'
import McpServersPanel from './connections/McpServersPanel'
import McpServersV2Panel from './connections/McpServersV2Panel'
import PluginsCatalogBrowser from './connections/PluginsCatalogBrowser'
import PluginsV2Panel from './connections/PluginsV2Panel'

const PRIMARY_TABS = [
  // V2 truth is canonical: Plugins + MCP tabs always render V2 panels.
  { key: 'truth', label: 'All Connections (V2)', icon: Layers },
  { key: 'main-brain', label: 'Main Brain', icon: BrainCircuit },
  { key: 'plugins', label: 'Plugins', icon: Package },
  { key: 'mcp', label: 'MCP Servers', icon: Server },
] as const

const LEGACY_TAB = { key: 'legacy', label: 'Legacy / Advanced', icon: Wrench } as const

type PrimaryKey = typeof PRIMARY_TABS[number]['key']
type TabKey = PrimaryKey | typeof LEGACY_TAB.key

const SHOW_LEGACY_LS_KEY = 'daena.connections.show_legacy'

export default function ConnectionsPage() {
  usePageTitle('Connections')
  const [activeTab, setActiveTab] = useState<TabKey>('truth')

  // Show-legacy toggle: hydrated from localStorage on mount, persists
  // across reloads. Auto-flips ON when the operator deep-links to the
  // legacy tab (mirrors the SettingsPage show-advanced safety net).
  const [showLegacy, setShowLegacy] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(SHOW_LEGACY_LS_KEY) === 'true'
  })
  useEffect(() => {
    if (activeTab === 'legacy' && !showLegacy) {
      setShowLegacy(true)
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(SHOW_LEGACY_LS_KEY, 'true')
      }
    }
  }, [activeTab, showLegacy])

  function handleShowLegacyToggle() {
    const next = !showLegacy
    setShowLegacy(next)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SHOW_LEGACY_LS_KEY, String(next))
    }
    // If turning off while we're sitting on the legacy tab, snap back
    // to the V2 truth tab so the operator is never staring at an empty
    // pane after their own toggle.
    if (!next && activeTab === 'legacy') setActiveTab('truth')
  }

  const visibleTabs: ReadonlyArray<{ key: TabKey; label: string; icon: typeof Layers }> =
    showLegacy ? [...PRIMARY_TABS, LEGACY_TAB] : PRIMARY_TABS

  return (
    <div className="min-h-full bg-midnight-900 text-starlight-100">
      <div className="border-b border-white/5 bg-midnight-400/40">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex flex-col gap-2">
            <div className="text-xs font-medium uppercase tracking-[0.2em] text-accent-cyan">
              Connections
            </div>
            <h1 className="text-2xl font-display font-semibold text-starlight-50">
              Runtime, Plugins, and MCP
            </h1>
            <p className="max-w-3xl text-sm text-starlight-400">
              Main Brain controls routing. Plugins, OAuth apps, and providers
              live in the V2 registry. The V2 panel is the canonical truth
              surface; the legacy V1 panels are kept for migration and
              debugging only.
            </p>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <div className="flex flex-1 flex-wrap gap-2 overflow-x-auto pb-1">
              {visibleTabs.map((tab) => {
                const Icon = tab.icon
                const active = activeTab === tab.key
                const isLegacy = tab.key === 'legacy'
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`inline-flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                      active
                        ? isLegacy
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
            <label
              className="inline-flex items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-[11px] text-starlight-400 cursor-pointer hover:text-starlight-200"
              title="Reveal the legacy V1 connection panels (Plugins catalog, MCP servers). V2 truth is canonical; the legacy panels are kept for migration and debugging."
            >
              <input
                type="checkbox"
                checked={showLegacy}
                onChange={handleShowLegacyToggle}
                className="h-3 w-3 rounded border-white/20 bg-transparent text-primary-500"
              />
              <span>Show legacy / advanced</span>
            </label>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-5">
        {activeTab === 'truth' && <ConnectionsV2Panel />}
        {activeTab === 'main-brain' && <MainBrainPanel />}
        {activeTab === 'plugins' && <PluginsV2Panel />}
        {activeTab === 'mcp' && <McpServersV2Panel />}
        {activeTab === 'legacy' && <LegacyAdvancedPanel />}
      </div>
    </div>
  )
}

// -----------------------------------------------------------------
// Legacy / Advanced -- V1 panels stacked behind the reveal toggle.
// Kept for migration + debugging only. Do not promote into a primary
// tab; do not remove (yet) -- the V1 install/disconnect flows still
// work and operators may rely on them while V2 mutations are still
// gated on USE_CONNECTION_REGISTRY_V2.
// -----------------------------------------------------------------

function LegacyAdvancedPanel() {
  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
        <AlertTriangle size={16} className="mt-0.5 shrink-0" />
        <div>
          <strong>Legacy connection registry.</strong>{' '}
          Kept for migration and debugging. V2 truth is canonical.
          <p className="mt-1 text-[11px] text-amber-200/80">
            The two panels below render the legacy V1 catalog and MCP
            views. Their statuses use the older
            <code className="mx-1 font-mono">_status_for_install</code>
            heuristic (credentials present == connected) and do NOT
            reflect V2 probe truth. Use the V2 panels above for the
            canonical answer to "is this connection actually callable?"
          </p>
        </div>
      </div>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-starlight-100">
          Plugins (V1 catalog)
        </h3>
        <p className="text-[11px] text-starlight-500">
          Legacy plugin browser. Install + disconnect actions still
          function but do not mirror to V2 unless the
          <code className="mx-1 font-mono">USE_CONNECTION_REGISTRY_V2</code>
          backend flag is on.
        </p>
        <PluginsCatalogBrowser />
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-starlight-100">
          MCP Servers (V1)
        </h3>
        <p className="text-[11px] text-starlight-500">
          Legacy MCP detect / probe / import view. The V2 MCP panel
          above is the truth surface for "is this server callable?"
        </p>
        <McpServersPanel />
      </section>
    </div>
  )
}
