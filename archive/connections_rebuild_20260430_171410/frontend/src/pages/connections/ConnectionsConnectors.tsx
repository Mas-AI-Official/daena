/**
 * Connectors ("Plugins") tab for the Connections page.
 *
 * Renders:
 *   - The Browse plugins button (opens BrowseModal)
 *   - The plugin search box
 *   - The batch-action toolbar (currently "Clear selection" only)
 *   - Plugins grouped by category, each with the ConnectorRow component
 *
 * ConnectorRow itself owns:
 *   - OAuth / API-key / token auth flows (via shared startOAuthConnect)
 *   - Per-tool permission overrides (Advanced disclosure, off by default)
 *   - "Switch account" + "Disconnect" three-dot actions
 *   - The Live MCP badge driven by the parent's mcpRegistry hook
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plug,
  Puzzle,
  Search,
  MoreVertical,
  CheckCircle2,
  XCircle,
  Loader2,
  Plus,
  ChevronDown,
  ChevronUp,
  Key,
  Globe,
  Shield,
  Terminal,
  Save,
  ExternalLink,
  Wrench,
  RefreshCw,
  UserCircle,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { CONNECTOR_ICONS } from '@/components/icons/BrandIcons'
import { CONNECTORS, SKILL_DESCRIPTIONS } from './catalog'
import { startOAuthConnect } from './oauth'
import { ConfigPanel, ContextMenu, PermissionSelect } from './shared'
import type { AuthMethod, ConnectorDef, Permission } from './types'
import ConnectorInstallDialog from '@/components/connections/ConnectorInstallDialog'

// ── Connector Row with expandable config ──

function ConnectorRow({ connector, connected, instanceId, accountIdentity, expanded, onToggleExpand, onInstall, onDisconnect, fetchInstances, selected, onSelect, onRequestOAuthSetup, isLive }: {
  connector: ConnectorDef
  connected: boolean
  instanceId: string | null
  accountIdentity?: string
  expanded: boolean
  onToggleExpand: () => void
  // Open the unified install dialog (Codex-style) for this connector.
  // The dialog reads enriched catalog metadata from the backend and
  // dispatches the right auth flow (oauth_managed / mcp_remote_oauth /
  // api_token / none).
  onInstall: () => void
  onDisconnect: (instanceId: string) => void
  fetchInstances?: () => void
  selected?: boolean
  onSelect?: (id: string, checked: boolean) => void
  onRequestOAuthSetup?: (missingField: string) => void
  // When true, the plugin's MCP adapter is in the live bootstrap
  // registry -- i.e. chat can dispatch plugin.call_tool to it right
  // now without any restart. Shown as a green "Live" dot next to
  // the skill/category pills.
  isLive?: boolean
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [apiKeyValue, setApiKeyValue] = useState('')
  const [saving, setSaving] = useState(false)
  // Advanced mode = expose per-tool Allow/Ask/Block controls inside
  // the capabilities list. Off by default (per TICKET-S16 UX rework)
  // because account-level auth already gates tool access; per-tool
  // controls are defense-in-depth for power users only.
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [toolPermissions, setToolPermissions] = useState<Record<string, Permission>>(() => {
    const init: Record<string, Permission> = {}
    for (const t of connector.tools) init[t] = 'ASK_EACH_TIME'
    return init
  })
  const Icon = CONNECTOR_ICONS[connector.id] || Plug

  const authLabels: Record<AuthMethod, string> = {
    oauth: 'OAuth 2.0',
    api_key: 'API Key',
    token: 'Access Token',
  }

  const handleSaveApiKey = async () => {
    if (!apiKeyValue.trim()) return
    setSaving(true)
    try {
      // Attempt to create a connection instance with the provided key
      await api.post('/connections/instances', {
        connector_id: connector.id,
        credentials: { api_key: apiKeyValue.trim() },
      })
      toast.success(`${connector.name} connected successfully`)
      setApiKeyValue('')
    } catch {
      toast.error(`Failed to connect ${connector.name}. Check your key and try again.`)
    } finally {
      setSaving(false)
    }
  }

  const handleOAuthConnect = async () => {
    // Session 10: delegates to shared startOAuthConnect. The on-missing-
    // creds path now signals the parent page to open an inline setup
    // modal instead of navigating to /settings (which was confusing --
    // the operator clicked "Connect with Google" and ended up on a
    // Daena settings page).
    await startOAuthConnect({
      connectorId: connector.id,
      connectorName: connector.name,
      onSuccess: () => { void fetchInstances?.() },
      onRequestSetup: onRequestOAuthSetup,
    })
  }

  return (
    <div>
      <div
        className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg group cursor-pointer"
        onClick={onToggleExpand}
      >
        {/* Batch select checkbox */}
        {onSelect && (
          <input
            type="checkbox"
            checked={selected || false}
            onChange={(e) => { e.stopPropagation(); onSelect(connector.id, e.target.checked) }}
            onClick={(e) => e.stopPropagation()}
            className="w-3.5 h-3.5 rounded border-white/20 bg-transparent accent-primary-500 cursor-pointer shrink-0"
          />
        )}
        <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-starlight-100">{connector.name}</span>
            {/* Skill count badge -- echoes the Codex plugin header
                format so the user knows how many skills this plugin
                brings before expanding. */}
            {/* Codex-style: prefer the bundled-skills count when present.
                "Cloudflare 9 skills" reads more honestly than "Cloudflare
                4 tools" because each Codex skill is a curated playbook
                (Wrangler, Workers Best Practices, Agents SDK, ...). */}
            <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/5 text-starlight-400 font-medium">
              {(() => {
                const bundledCount = connector.included_skills?.length || 0
                const totalSkills = bundledCount > 0 ? bundledCount : connector.tools.length
                return `${totalSkills} ${totalSkills === 1 ? 'skill' : 'skills'}`
              })()}
            </span>
            {connector.included_mcp && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-primary-500/10 text-primary-400 font-medium uppercase tracking-wider">
                + MCP
              </span>
            )}
            <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/[0.03] text-starlight-500 uppercase tracking-wider">
              {connector.category}
            </span>
            {/* "Live" pill -- green dot + label when the plugin's
                MCP adapter is currently in the stdio bootstrap
                registry. Means plugin.call_tool can dispatch to
                this plugin right now without a server restart. */}
            {isLive && (
              <span
                className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-accent-green/10 text-accent-green font-medium"
                title="Plugin MCP is loaded and spawnable now"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
                Live
              </span>
            )}
          </div>
          {/* Connected-account identity strip. Answers the "which
              Google account is Daena linked to?" question at a glance.
              Shows email + avatar-glyph when we have it, falls back to
              the connector subtitle otherwise. TICKET-S16 promoted
              this from a muted subtitle line to a dedicated pill so
              the identity is the FIRST thing the operator sees after
              connecting -- matches Slack / Notion / Zapier norm. */}
          {connected && accountIdentity ? (
            <div className="flex items-center gap-1.5 mt-1">
              <UserCircle size={12} className="text-accent-green shrink-0" />
              <span className="text-[11px] text-starlight-300 truncate">
                <span className="text-starlight-500">Signed in as </span>
                <span className="text-accent-green font-medium">{accountIdentity}</span>
              </span>
            </div>
          ) : (
            <p className="text-xs text-starlight-500 truncate mt-0.5">
              {connector.subtitle}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
          {connected ? (
            <span className="flex items-center gap-1 text-xs text-accent-green font-medium">
              <CheckCircle2 size={12} /> Connected
            </span>
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); onInstall() }}
              className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-primary-500/15 text-primary-300 hover:bg-primary-500/25 cursor-pointer border border-primary-500/20"
            >
              <Wrench size={11} /> Install
            </button>
          )}
          {expanded ? <ChevronUp size={14} className="text-starlight-400" /> : <ChevronDown size={14} className="text-starlight-400" />}
          <div className="relative">
            <button onClick={() => setMenuOpen(!menuOpen)} className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer">
              <MoreVertical size={14} />
            </button>
            <AnimatePresence>
              {menuOpen && (
                <ContextMenu
                  onClose={() => setMenuOpen(false)}
                  items={[
                    { label: 'View docs', icon: <ExternalLink size={12} />, onClick: () => toast.info(`Documentation for ${connector.name}`) },
                    // Session 11: "Switch account" disconnects the
                    // current instance then restarts OAuth. Google's
                    // consent screen shows the account picker again
                    // because we don't pass login_hint, so the user
                    // lands on "Choose an account" naturally.
                    ...(connected && instanceId ? [{
                      label: 'Switch account',
                      icon: <RefreshCw size={12} />,
                      onClick: async () => {
                        onDisconnect(instanceId)
                        // Small delay so the disconnect toast lands
                        // before the popup opens.
                        setTimeout(() => {
                          void startOAuthConnect({
                            connectorId: connector.id,
                            connectorName: connector.name,
                            onSuccess: () => { void fetchInstances?.() },
                            onRequestSetup: onRequestOAuthSetup,
                          })
                        }, 400)
                      },
                    }] : []),
                    ...(connected && instanceId ? [{
                      label: 'Disconnect',
                      icon: <XCircle size={12} />,
                      onClick: () => onDisconnect(instanceId),
                      danger: true,
                    }] : []),
                  ]}
                />
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Expandable config panel */}
      <ConfigPanel expanded={expanded}>
        {/* Auth section */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Shield size={12} className="text-starlight-400" />
            <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">Authentication</span>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="text-starlight-500">Method:</span>
            <span className="text-starlight-200 font-medium">{authLabels[connector.auth]}</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${connected ? 'bg-accent-green/10 text-accent-green' : 'bg-white/5 text-starlight-400'}`}>
              {connected ? 'Connected' : 'Not connected'}
            </span>
          </div>

          {/* OAuth connect button */}
          {connector.auth === 'oauth' && !connected && (
            <button
              onClick={handleOAuthConnect}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium bg-primary-500/15 text-primary-400 hover:bg-primary-500/25 cursor-pointer border border-primary-500/20"
            >
              <Globe size={14} /> Connect with {connector.name.split(' ')[0]}
            </button>
          )}

          {/* API key / Token input */}
          {(connector.auth === 'api_key' || connector.auth === 'token') && !connected && (
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Key size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-starlight-500" />
                <input
                  type="password"
                  value={apiKeyValue}
                  onChange={(e) => setApiKeyValue(e.target.value)}
                  placeholder={connector.auth === 'api_key' ? 'Enter API key...' : 'Enter access token...'}
                  className="w-full glass-input pl-8 pr-3 py-2 rounded-lg text-xs text-starlight-200 placeholder:text-starlight-500"
                  onKeyDown={(e) => { if (e.key === 'Enter') void handleSaveApiKey() }}
                />
              </div>
              <button
                onClick={() => void handleSaveApiKey()}
                disabled={!apiKeyValue.trim() || saving}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs bg-accent-green/10 text-accent-green hover:bg-accent-green/20 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />} Save
              </button>
            </div>
          )}

          {/* Disconnect button */}
          {connected && instanceId && (
            <button
              onClick={() => onDisconnect(instanceId)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-accent-red/80 hover:bg-accent-red/10 cursor-pointer"
            >
              <XCircle size={12} /> Disconnect
            </button>
          )}
        </div>

        {/* Codex-style "Includes" — when this connector bundles official
            skills + an MCP server, surface them so the user knows that a
            single auth wires up the whole skill pack (Cloudflare =
            Wrangler + Workers Best Practices + Agents SDK + ... + the
            Cloudflare API MCP, configured by one OAuth). */}
        {(connector.included_skills?.length || connector.included_mcp) && (
          <div className="space-y-2 pt-2 border-t border-white/5">
            <div className="flex items-center gap-2">
              <Puzzle size={12} className="text-primary-400" />
              <span className="text-[10px] text-primary-400 uppercase tracking-wider font-semibold">
                Includes
              </span>
            </div>
            <div className="rounded-lg border border-primary-500/15 divide-y divide-white/5 bg-primary-500/[0.03]">
              {connector.included_mcp && (
                <div className="flex items-start gap-2.5 px-3 py-2">
                  <div className="shrink-0 mt-0.5 p-1 rounded bg-primary-500/15">
                    <Globe size={11} className="text-primary-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs text-starlight-200 font-medium">{connector.included_mcp.name}</span>
                      <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-primary-500/15 text-primary-400 font-semibold">
                        MCP server
                      </span>
                      <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/5 text-starlight-400">
                        {connector.included_mcp.scope}
                      </span>
                    </div>
                    {connector.included_mcp.package && (
                      <code className="text-[10px] text-starlight-600 font-mono mt-0.5 inline-block">
                        {connector.included_mcp.package}
                      </code>
                    )}
                  </div>
                </div>
              )}
              {connector.included_skills?.map((skill) => (
                <div key={skill.id} className="flex items-start gap-2.5 px-3 py-2">
                  <div className="shrink-0 mt-0.5 p-1 rounded bg-white/5">
                    <Terminal size={11} className="text-starlight-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs text-starlight-200 font-medium">{skill.name}</span>
                      <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/5 text-starlight-400 font-semibold">
                        Skill
                      </span>
                    </div>
                    <p className="text-[11px] text-starlight-500 mt-0.5 leading-relaxed">
                      {skill.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Capabilities -- informational list of tools the connector
            brings. NOT per-tool CTAs. The 2026-04-18 UX rework
            (TICKET-S16) demoted these from "Skill with Ask dropdown"
            to read-only capability entries: the connector-level
            Connect / Disconnect / Switch-account action above is the
            primary contract. Once connected, the whole capability
            surface is available to Daena and the agents in scope --
            per-tool gating on a connected app is redundant with
            account-level auth and adds clutter.
            For users who still want fine-grained per-tool control,
            the "Advanced" disclosure below reveals the legacy
            Allow/Ask/Block controls on demand. */}
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Puzzle size={12} className="text-starlight-400" />
              <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">
                Capabilities ({connector.tools.length})
              </span>
              {connected && (
                <span className="text-[10px] text-starlight-500">
                  available to Daena + agents in scope
                </span>
              )}
            </div>
            <button
              onClick={() => setShowAdvanced((v) => !v)}
              className="text-[10px] text-starlight-500 hover:text-starlight-300 flex items-center gap-1 cursor-pointer"
              title="Per-tool Allow / Ask / Block controls (rarely needed)"
            >
              <Wrench size={10} /> {showAdvanced ? 'Hide advanced' : 'Advanced'}
            </button>
          </div>
          <div className="rounded-lg border border-white/5 divide-y divide-white/5 bg-midnight-400/20">
            {connector.tools.map((tool) => {
              const skillName = tool
                .split('_')
                .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                .join(' ')
              const description =
                SKILL_DESCRIPTIONS[tool] ||
                `Capability exposed by ${connector.name}.`
              return (
                <div
                  key={tool}
                  className="flex items-start justify-between gap-3 px-3 py-2.5"
                >
                  <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <div className="shrink-0 mt-0.5 p-1 rounded bg-white/5">
                      <Terminal size={11} className="text-starlight-400" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-xs text-starlight-200 font-medium">
                          {skillName}
                        </span>
                        <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/5 text-starlight-400 font-semibold">
                          Tool
                        </span>
                      </div>
                      <p className="text-[11px] text-starlight-500 mt-0.5 leading-relaxed">
                        {description}
                      </p>
                      <code className="text-[10px] text-starlight-600 font-mono mt-0.5 inline-block">
                        {tool}
                      </code>
                    </div>
                  </div>
                  {/* Advanced: per-tool permission controls, hidden by
                      default. Defense-in-depth pattern -- connector
                      auth is the primary gate; these are the
                      secondary override for power users. */}
                  {showAdvanced && (
                    <div className="shrink-0">
                      <PermissionSelect
                        value={toolPermissions[tool] || 'ASK_EACH_TIME'}
                        onChange={(v) =>
                          setToolPermissions((prev) => ({ ...prev, [tool]: v }))
                        }
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Codex-style information footer — Developer, Capabilities,
            Website, Privacy, Terms. Only renders when at least one
            metadata field is present. */}
        {(connector.developer || connector.built_by || connector.capabilities?.length || connector.website) && (
          <div className="space-y-2 pt-2 border-t border-white/5">
            <div className="flex items-center gap-2">
              <Shield size={12} className="text-starlight-400" />
              <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">
                Information
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
              <div>
                <span className="text-starlight-500">Category</span>
                <p className="text-starlight-200 mt-0.5">
                  {connector.built_by ? `${connector.built_by}, ${connector.category}` : connector.category}
                </p>
              </div>
              {connector.capabilities && connector.capabilities.length > 0 && (
                <div>
                  <span className="text-starlight-500">Capabilities</span>
                  <p className="text-starlight-200 mt-0.5">{connector.capabilities.join(', ')}</p>
                </div>
              )}
              {connector.developer && (
                <div>
                  <span className="text-starlight-500">Developer</span>
                  <p className="text-starlight-200 mt-0.5">{connector.developer}</p>
                </div>
              )}
              {connector.website && (
                <div>
                  <span className="text-starlight-500">Website</span>
                  <a href={connector.website} target="_blank" rel="noopener noreferrer"
                     className="text-primary-400 hover:text-primary-300 underline mt-0.5 inline-block">
                    {connector.website.replace(/^https?:\/\//, '')}
                  </a>
                </div>
              )}
              {connector.privacy_policy && (
                <div>
                  <span className="text-starlight-500">Privacy Policy</span>
                  <a href={connector.privacy_policy} target="_blank" rel="noopener noreferrer"
                     className="text-primary-400 hover:text-primary-300 underline mt-0.5 inline-block">
                    Open
                  </a>
                </div>
              )}
              {connector.terms_url && (
                <div>
                  <span className="text-starlight-500">Terms of service</span>
                  <a href={connector.terms_url} target="_blank" rel="noopener noreferrer"
                     className="text-primary-400 hover:text-primary-300 underline mt-0.5 inline-block">
                    Open
                  </a>
                </div>
              )}
            </div>
          </div>
        )}
      </ConfigPanel>
    </div>
  )
}

// ── Tab body ──

export interface ConnectionsConnectorsProps {
  connectorSearch: string
  onConnectorSearchChange: (q: string) => void
  connectorInstances: Record<string, string>
  connectorIdentities: Record<string, string>
  selectedConnectors: Set<string>
  expandedItem: string | null
  liveMcpCount: number
  isLiveConnector: (mcpId: string) => boolean
  onToggleExpand: (id: string) => void
  onSelectConnector: (id: string, checked: boolean) => void
  onClearConnectorSelection: () => void
  onSelectAll: (filteredIds: string[]) => void
  onDisconnect: (instanceId: string) => void
  fetchConnectorInstances: () => void
  onRequestOAuthSetup: (connectorId: string, connectorName: string, missingField: string) => void
  onOpenBrowse: () => void
}

export default function ConnectionsConnectors({
  connectorSearch,
  onConnectorSearchChange,
  connectorInstances,
  connectorIdentities,
  selectedConnectors,
  expandedItem,
  liveMcpCount,
  isLiveConnector,
  onToggleExpand,
  onSelectConnector,
  onClearConnectorSelection,
  onSelectAll,
  onDisconnect,
  fetchConnectorInstances,
  onRequestOAuthSetup,
  onOpenBrowse,
}: ConnectionsConnectorsProps) {
  const filteredConnectors = connectorSearch
    ? CONNECTORS.filter(c => c.name.toLowerCase().includes(connectorSearch.toLowerCase()) || c.category.toLowerCase().includes(connectorSearch.toLowerCase()))
    : CONNECTORS

  // The Codex-style install dialog. One slug at a time. When the user
  // clicks Install on a row we set this; the dialog fetches enriched
  // metadata from /connectors/{slug}/install/info and drives the auth
  // flow. On success we refresh the connected list so the row's pill
  // flips to "Connected" without a manual reload.
  const [installSlug, setInstallSlug] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      {/* Session 10: Claude Desktop parity -- removed the
          "Connectors" H2 (tab label is already "Services")
          and the AGI Mode banner for visual cleanup. Kept
          the Browse button right-aligned. */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-xs text-starlight-400">
            Plugins bundle related skills so Daena can read and write across
            apps you already use -- Gmail, Drive, GitHub, and more. Expand
            a plugin to see its individual skills.
          </p>
          {/* Live MCP counter -- mirrors the bootstrap
              registry. Gives at-a-glance feedback that the
              install loop actually worked (vs stuck on
              0 as it used to before the refresh fix). */}
          {liveMcpCount > 0 && (
            <p className="text-[11px] text-accent-green mt-1 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
              {liveMcpCount} {liveMcpCount === 1 ? 'plugin' : 'plugins'} live and callable right now
            </p>
          )}
        </div>
        <button
          onClick={onOpenBrowse}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer shrink-0"
        >
          <Plus size={12} /> Browse plugins
        </button>
      </div>

      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
        <input
          type="text"
          value={connectorSearch}
          onChange={(e) => onConnectorSearchChange(e.target.value)}
          placeholder="Search plugins..."
          className="w-full glass-input pl-9 pr-4 py-2.5 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500"
        />
      </div>

      {/* Batch action toolbar */}
      {selectedConnectors.size > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-primary-500/10 border border-primary-500/20"
        >
          <span className="text-xs text-primary-400 font-medium">{selectedConnectors.size} selected</span>
          <div className="flex-1" />
          <button
            onClick={() => { onClearConnectorSelection(); toast.info('Batch operations for connectors require individual setup') }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
          >
            Clear selection
          </button>
        </motion.div>
      )}

      {/* Select all link */}
      <div className="flex justify-end px-4">
        <button
          onClick={() => {
            if (selectedConnectors.size === filteredConnectors.length) {
              onSelectAll([])
            } else {
              onSelectAll(filteredConnectors.map((c) => c.id))
            }
          }}
          className="text-[10px] text-starlight-500 hover:text-primary-400 cursor-pointer"
        >
          {selectedConnectors.size === filteredConnectors.length ? 'Deselect all' : 'Select all'}
        </button>
      </div>

      {/* Codex-style grouping: plugins clustered under their
          category so the directory reads like a curated shelf
          instead of a flat alphabetical dump. Preserves the
          single-column Codex look with breathing room
          between sections. */}
      {(() => {
        // Group preserving original category order of first
        // occurrence (so "Productivity" stays near the top if
        // it was first in CONNECTORS).
        const groups: Record<string, typeof filteredConnectors> = {}
        const order: string[] = []
        for (const c of filteredConnectors) {
          if (!groups[c.category]) {
            groups[c.category] = []
            order.push(c.category)
          }
          groups[c.category].push(c)
        }
        return (
          <div className="space-y-5">
            {order.map((category) => (
              <div key={category} className="space-y-2">
                <div className="flex items-center gap-2 px-1">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-starlight-400">
                    {category}
                  </span>
                  <span className="text-[10px] text-starlight-600">
                    {groups[category].length}
                  </span>
                  <div className="flex-1 h-px bg-white/5" />
                </div>
                <div className="rounded-xl border border-white/5 divide-y divide-white/5">
                  {groups[category].map((c) => (
                    <ConnectorRow
                      key={c.id}
                      connector={c}
                      connected={!!connectorInstances[c.id]}
                      instanceId={connectorInstances[c.id] || null}
                      accountIdentity={connectorIdentities[c.id] || ''}
                      expanded={expandedItem === c.id}
                      onToggleExpand={() => onToggleExpand(c.id)}
                      onInstall={() => setInstallSlug(c.id)}
                      onDisconnect={onDisconnect}
                      fetchInstances={fetchConnectorInstances}
                      selected={selectedConnectors.has(c.id)}
                      onSelect={onSelectConnector}
                      onRequestOAuthSetup={(missing) => onRequestOAuthSetup(c.id, c.name, missing)}
                      isLive={isLiveConnector(`mcp-${c.id}`)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )
      })()}

      {/* Codex-style install dialog. Driven by /connectors/{slug}/
          install/info, dispatches auth via /install/start +
          /install/complete. */}
      <ConnectorInstallDialog
        slug={installSlug}
        open={installSlug !== null}
        onClose={() => setInstallSlug(null)}
        onConnected={() => fetchConnectorInstances()}
      />
    </div>
  )
}
