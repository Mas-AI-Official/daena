/**
 * Browse Modal -- Claude Desktop-style marketplace for connectors and
 * extensions. Same layout for both modes; the underlying catalog +
 * click handler differ.
 *
 * Click flow:
 *   - Already connected -> jump back to that tab and open the row.
 *   - Browsing extensions in cloud mode -> auto-install (fake row).
 *   - Browsing extensions in local mode -> POST /connections/extensions/install.
 *   - Browsing connectors -> startOAuthConnect (Session 10 fix; was
 *     opening the product homepage instead of the OAuth URL).
 */
import { motion, AnimatePresence } from 'framer-motion'
import {
  Puzzle,
  Search,
  CheckCircle2,
  XCircle,
  Plus,
  Globe,
  ExternalLink,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { CONNECTOR_ICONS, EXTENSION_ICONS } from '@/components/icons/BrandIcons'
import { BROWSE_CONNECTORS_CATALOG, BROWSE_EXTENSIONS_CATALOG } from './catalog'
import { startOAuthConnect } from './oauth'
import type { ExtensionData, TabKey } from './types'

export interface BrowseModalProps {
  // Which catalog the modal is browsing right now. `null` = closed.
  mode: 'connectors' | 'extensions' | null
  cloudMode: boolean
  connectorInstances: Record<string, string>
  extensions: ExtensionData[]
  onClose: () => void
  setExtensions: React.Dispatch<React.SetStateAction<ExtensionData[]>>
  setActiveTab: (tab: TabKey) => void
  setExpandedItem: (id: string) => void
  fetchExtensions: () => void
  fetchConnectorInstances: () => void
  onRequestOAuthSetup: (connectorId: string, connectorName: string, missingField: string) => void
}

export default function BrowseModal({
  mode,
  cloudMode,
  connectorInstances,
  extensions,
  onClose,
  setExtensions,
  setActiveTab,
  setExpandedItem,
  fetchExtensions,
  fetchConnectorInstances,
  onRequestOAuthSetup,
}: BrowseModalProps) {
  return (
    <AnimatePresence>
      {mode && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-x-4 top-[5%] bottom-[5%] md:inset-x-[15%] lg:inset-x-[20%] z-50 bg-midnight-300 rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
              <div>
                <h2 className="text-xl font-display font-bold text-starlight-100">
                  {mode === 'connectors' ? 'Connectors' : 'Extensions'}
                </h2>
                <p className="text-xs text-starlight-400 mt-0.5">
                  {mode === 'connectors'
                    ? 'Connect Daena to your apps, files, and services. One click to set up.'
                    : 'Add MCP servers and tools to extend Daena\'s capabilities.'}
                </p>
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-starlight-200 cursor-pointer"
              >
                <XCircle size={20} />
              </button>
            </div>

            {/* Search + Filters */}
            <div className="px-6 py-3 border-b border-white/5 flex items-center gap-3">
              <div className="relative flex-1">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
                <input
                  type="text"
                  placeholder="Search..."
                  className="w-full pl-9 pr-3 py-2 rounded-lg bg-midnight-400 border border-white/5 text-sm text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
                />
              </div>
              <div className="flex gap-2 text-xs text-starlight-400">
                <span className="px-3 py-1.5 rounded-lg bg-white/5 cursor-pointer hover:bg-white/10">Sort</span>
                <span className="px-3 py-1.5 rounded-lg bg-white/5 cursor-pointer hover:bg-white/10">Categories</span>
              </div>
            </div>

            {/* Grid */}
            <div className="flex-1 overflow-y-auto p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {(mode === 'connectors' ? BROWSE_CONNECTORS_CATALOG : BROWSE_EXTENSIONS_CATALOG).map((item) => {
                  const isConnected = mode === 'connectors'
                    ? !!connectorInstances[item.id]
                    : extensions.some(e => e.name.toLowerCase().includes(item.name.toLowerCase()) && e.enabled)
                  const IconComp = mode === 'connectors'
                    ? (CONNECTOR_ICONS[item.id] || (() => <Globe size={24} className="text-starlight-400" />))
                    : (EXTENSION_ICONS[item.id] || (() => <Puzzle size={24} className="text-starlight-400" />))

                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        if (isConnected) {
                          onClose()
                          setActiveTab(mode === 'connectors' ? 'connectors' : 'extensions')
                          setExpandedItem(item.id)
                        } else if (mode === 'extensions' && cloudMode) {
                          // Cloud mode: auto-install the extension
                          setExtensions((prev) => {
                            if (prev.some((e) => e.id === item.id)) return prev
                            return [...prev, {
                              id: item.id,
                              name: item.name,
                              description: item.description,
                              enabled: true,
                              permission: 'ALLOW',
                            }]
                          })
                          toast.success(`${item.name} installed and enabled`)
                        } else if (mode === 'extensions' && !cloudMode) {
                          // Local mode: install via backend API
                          api.post('/connections/extensions/install', {
                            id: item.id,
                            name: item.name,
                            description: item.description,
                          }).then(() => {
                            void fetchExtensions()
                            toast.success(`${item.name} installed`)
                          }).catch(() => {
                            toast.error(`Failed to install ${item.name}. Check MCP server configuration.`)
                          })
                        } else if (mode === 'connectors') {
                          // Session 10: was window.open(item.authUrl, '_blank')
                          // which opened the product homepage (mail.google.com)
                          // instead of the OAuth consent screen. Now goes through
                          // startOAuthConnect which resolves the real Google/
                          // Notion/Slack OAuth URL from the backend and pops it.
                          onClose()
                          void startOAuthConnect({
                            connectorId: item.id,
                            connectorName: item.name,
                            onSuccess: fetchConnectorInstances,
                            onRequestSetup: (missing) =>
                              onRequestOAuthSetup(item.id, item.name, missing),
                          })
                        }
                      }}
                      className="flex items-center gap-3 p-4 rounded-xl border border-white/5 bg-midnight-400/50 hover:bg-white/5 hover:border-white/10 transition-all text-left cursor-pointer group"
                    >
                      <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center shrink-0">
                        <IconComp size={22} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-starlight-100">{item.name}</span>
                          {item.popularity && (
                            <span className="text-[9px] text-starlight-500 bg-white/5 px-1.5 py-0.5 rounded">{item.popularity}</span>
                          )}
                        </div>
                        <p className="text-xs text-starlight-400 truncate mt-0.5">{item.description}</p>
                      </div>
                      <div className="shrink-0">
                        {isConnected ? (
                          <CheckCircle2 size={18} className="text-accent-green" />
                        ) : mode === 'extensions' ? (
                          <span className="text-[10px] font-medium text-primary-400 bg-primary-500/10 px-2 py-1 rounded group-hover:bg-primary-500/20">Install</span>
                        ) : (
                          <Plus size={18} className="text-starlight-500 group-hover:text-primary-400 transition-colors" />
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-3 border-t border-white/5 text-center">
              <a
                href="https://github.com/modelcontextprotocol/servers"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-starlight-500 hover:text-primary-400 transition-colors inline-flex items-center gap-1"
              >
                Browse all MCP servers on GitHub <ExternalLink size={10} />
              </a>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
