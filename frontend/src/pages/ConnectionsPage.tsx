import { useEffect, useState } from 'react'
import { AlertTriangle, BrainCircuit, Layers, Package, Server } from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import { api } from '@/lib/api'
import ConnectionsV2Panel from './connections/ConnectionsV2Panel'
import MainBrainPanel from './connections/MainBrainPanel'
import McpServersPanel from './connections/McpServersPanel'
import McpServersV2Panel from './connections/McpServersV2Panel'
import PluginsCatalogBrowser from './connections/PluginsCatalogBrowser'
import PluginsV2Panel from './connections/PluginsV2Panel'

const tabs = [
  // Phase 5 PR 1: V2 truth-backed listing is the new primary tab.
  { key: 'truth', label: 'All Connections (V2)', icon: Layers },
  { key: 'main-brain', label: 'Main Brain', icon: BrainCircuit },
  { key: 'plugins', label: 'Plugins', icon: Package },
  { key: 'mcp', label: 'MCP Servers', icon: Server },
] as const

type TabKey = typeof tabs[number]['key']

interface FlagInfo {
  v2_enabled: boolean | null
  loading: boolean
}

function useV2Flag(): FlagInfo {
  /**
   * Phase 6: Fetch the V2 flag once. The flag is exposed by the
   * reconciliation status endpoint (FOUNDER+). For non-FOUNDER
   * users, we silently default to OFF (the production-safe
   * assumption).
   */
  const [info, setInfo] = useState<FlagInfo>({ v2_enabled: null, loading: true })

  useEffect(() => {
    let cancelled = false
    api
      .get<{ v2_enabled: boolean }>('/connections/v2/reconciliation/status', {
        silent: true,
      })
      .then((res) => {
        if (cancelled) return
        setInfo({ v2_enabled: !!res.data?.v2_enabled, loading: false })
      })
      .catch(() => {
        if (cancelled) return
        setInfo({ v2_enabled: false, loading: false })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return info
}

export default function ConnectionsPage() {
  usePageTitle('Connections')
  const [activeTab, setActiveTab] = useState<TabKey>('truth')
  const { v2_enabled, loading: flagLoading } = useV2Flag()

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
              live in the V2 registry. MCP import reads real CLI config files
              and persists into Daena's MCP registry.
            </p>
          </div>

          <div className="mt-5 flex gap-2 overflow-x-auto pb-1">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const active = activeTab === tab.key
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`inline-flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                    active
                      ? 'border-primary-500/40 bg-primary-500/15 text-primary-200'
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

      <div className="mx-auto max-w-7xl px-6 py-5">
        {activeTab === 'truth' && <ConnectionsV2Panel />}
        {activeTab === 'main-brain' && <MainBrainPanel />}
        {activeTab === 'plugins' && (
          <PluginsTabRouter v2Enabled={v2_enabled} flagLoading={flagLoading} />
        )}
        {activeTab === 'mcp' && (
          <McpTabRouter v2Enabled={v2_enabled} flagLoading={flagLoading} />
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Phase 6: Tab routers -- pick V2 or legacy panel based on the flag.
// When the flag is OFF, legacy panels render with a banner directing
// the operator to the V2 tab.
// ─────────────────────────────────────────────────────────────────

function PluginsTabRouter({
  v2Enabled, flagLoading,
}: { v2Enabled: boolean | null; flagLoading: boolean }) {
  if (flagLoading) {
    return <PanelLoading label="Resolving V2 flag..." />
  }
  if (v2Enabled) return <PluginsV2Panel />
  return (
    <>
      <LegacyTabBanner kind="Plugins" />
      <PluginsCatalogBrowser />
    </>
  )
}

function McpTabRouter({
  v2Enabled, flagLoading,
}: { v2Enabled: boolean | null; flagLoading: boolean }) {
  if (flagLoading) {
    return <PanelLoading label="Resolving V2 flag..." />
  }
  if (v2Enabled) return <McpServersV2Panel />
  return (
    <>
      <LegacyTabBanner kind="MCP Servers" />
      <McpServersPanel />
    </>
  )
}

function PanelLoading({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] py-12 text-center text-sm text-starlight-400">
      {label}
    </div>
  )
}

function LegacyTabBanner({ kind }: { kind: string }) {
  return (
    <div className="mb-4 flex items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
      <AlertTriangle size={16} className="shrink-0" />
      <div>
        <strong>Legacy {kind} view.</strong>{' '}
        Status here uses the old <code>_status_for_install</code> heuristic
        (credentials present == connected). For real probe-backed truth, see
        the <strong>All Connections (V2)</strong> tab. Enable{' '}
        <code className="text-amber-100">USE_CONNECTION_REGISTRY_V2</code> to
        switch this tab to V2 truth.
      </div>
    </div>
  )
}
