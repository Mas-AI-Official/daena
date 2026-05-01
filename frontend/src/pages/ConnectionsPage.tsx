import { useState } from 'react'
import { BrainCircuit, Layers, Package, Server } from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import ConnectionsV2Panel from './connections/ConnectionsV2Panel'
import MainBrainPanel from './connections/MainBrainPanel'
import McpServersPanel from './connections/McpServersPanel'
import PluginsCatalogBrowser from './connections/PluginsCatalogBrowser'

const tabs = [
  // Phase 5 PR 1: V2 truth-backed listing is the new primary tab.
  { key: 'truth', label: 'All Connections (V2)', icon: Layers },
  { key: 'main-brain', label: 'Main Brain', icon: BrainCircuit },
  { key: 'plugins', label: 'Plugins', icon: Package },
  { key: 'mcp', label: 'MCP Servers', icon: Server },
] as const

type TabKey = typeof tabs[number]['key']

export default function ConnectionsPage() {
  usePageTitle('Connections')
  const [activeTab, setActiveTab] = useState<TabKey>('truth')

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
              Main Brain controls routing. Plugins create backend connector instances. MCP import reads real CLI config files and persists into Daena's MCP registry.
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
        {activeTab === 'plugins' && <PluginsCatalogBrowser />}
        {activeTab === 'mcp' && <McpServersPanel />}
      </div>
    </div>
  )
}
