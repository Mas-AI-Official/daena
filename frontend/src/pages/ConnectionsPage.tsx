/**
 * ConnectionsPage -- Claude Desktop style layout with 3 tabs:
 *   1. Runtimes (AI CLIs with real detection + expandable config)
 *   2. Extensions (MCP servers with tool permissions)
 *   3. Connectors (external services with OAuth/API key config)
 *
 * Each item expands inline to show a configuration panel when clicked,
 * matching Claude Desktop's pattern for MCP server configuration.
 */
import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plug,
  Puzzle,
  Cpu,
  Search,
  RefreshCw,
  MoreVertical,
  CheckCircle2,
  XCircle,
  Settings,
  Eye,
  Crown,
  Loader2,
  Plus,
  ChevronDown,
  ChevronUp,
  Key,
  Globe,
  Shield,
  Zap,
  Terminal,
  ToggleLeft,
  ToggleRight,
  Save,
  ExternalLink,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { CONNECTOR_ICONS, RUNTIME_ICONS, EXTENSION_ICONS } from '@/components/icons/BrandIcons'

// ── Types ──

interface RuntimeData {
  runtime_id: string
  display_name: string
  installed: boolean
  status: string
  subscription: {
    is_authenticated: boolean
    plan_name: string | null
    user_display: string | null
  } | null
}

interface ExtensionData {
  id: string
  name: string
  description: string
  enabled: boolean
  permission: string
}

// Auth methods for connectors
type AuthMethod = 'oauth' | 'api_key' | 'token'

// ── Connector definitions (Claude Desktop style) ──

const CONNECTORS = [
  { id: 'google-drive', name: 'Google Drive', subtitle: 'Access files, folders, and shared drives', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['search_files', 'read_file', 'upload_file', 'list_folders'] },
  { id: 'github', name: 'GitHub', subtitle: 'Repositories, issues, pull requests', category: 'Development', auth: 'token' as AuthMethod, tools: ['search_repos', 'read_file', 'list_issues', 'create_issue', 'create_pr'] },
  { id: 'figma', name: 'Figma', subtitle: 'Design files and components', category: 'Design', auth: 'token' as AuthMethod, tools: ['get_file', 'get_components', 'export_assets'] },
  { id: 'gmail', name: 'Gmail', subtitle: 'Read, send, and manage email', category: 'Communication', auth: 'oauth' as AuthMethod, tools: ['search_emails', 'read_email', 'send_email', 'create_draft'] },
  { id: 'google-calendar', name: 'Google Calendar', subtitle: 'Events, scheduling, availability', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_events', 'create_event', 'update_event', 'find_free_time'] },
  { id: 'hugging-face', name: 'Hugging Face', subtitle: 'Models, datasets, spaces', category: 'Development', auth: 'api_key' as AuthMethod, tools: ['search_models', 'model_info', 'run_inference'] },
  { id: 'notion', name: 'Notion', subtitle: 'Pages, databases, workspaces', category: 'Productivity', auth: 'token' as AuthMethod, tools: ['search_pages', 'read_page', 'create_page', 'query_database'] },
  { id: 'slack', name: 'Slack', subtitle: 'Channels, messages, notifications', category: 'Communication', auth: 'oauth' as AuthMethod, tools: ['search_messages', 'send_message', 'list_channels', 'read_channel'] },
  { id: 'canva', name: 'Canva', subtitle: 'Design, templates, brand kit', category: 'Design', auth: 'oauth' as AuthMethod, tools: ['list_designs', 'create_design', 'export_design'] },
  { id: 'paypal', name: 'PayPal', subtitle: 'Payments and invoicing', category: 'Finance', auth: 'api_key' as AuthMethod, tools: ['list_transactions', 'create_invoice', 'send_payment'] },
  { id: 'stripe', name: 'Stripe', subtitle: 'Payment processing, subscriptions', category: 'Finance', auth: 'api_key' as AuthMethod, tools: ['list_charges', 'list_subscriptions', 'create_invoice'] },
  { id: 'atlassian', name: 'Atlassian', subtitle: 'Jira, Confluence, Bitbucket', category: 'Development', auth: 'token' as AuthMethod, tools: ['search_issues', 'create_issue', 'search_pages', 'read_page'] },
  { id: 'linear', name: 'Linear', subtitle: 'Issue tracking, project management', category: 'Development', auth: 'api_key' as AuthMethod, tools: ['list_issues', 'create_issue', 'update_issue', 'list_projects'] },
  { id: 'intercom', name: 'Intercom', subtitle: 'Customer messaging platform', category: 'Communication', auth: 'token' as AuthMethod, tools: ['list_conversations', 'send_message', 'search_contacts'] },
]

// ── Permission Select (Allow / Ask each time / Block) ──

type Permission = 'ALLOW' | 'ASK_EACH_TIME' | 'BLOCK'

function PermissionSelect({ value, onChange }: { value: Permission; onChange: (v: Permission) => void }) {
  const [open, setOpen] = useState(false)
  const colors: Record<Permission, { text: string; bg: string; border: string; dot: string }> = {
    ALLOW: { text: 'text-accent-green', bg: 'bg-accent-green/5', border: 'border-accent-green/30', dot: 'bg-accent-green' },
    ASK_EACH_TIME: { text: 'text-accent-amber', bg: 'bg-accent-amber/5', border: 'border-accent-amber/30', dot: 'bg-accent-amber' },
    BLOCK: { text: 'text-accent-red', bg: 'bg-accent-red/5', border: 'border-accent-red/30', dot: 'bg-accent-red' },
  }
  const labels: Record<Permission, string> = { ALLOW: 'Allow', ASK_EACH_TIME: 'Ask', BLOCK: 'Block' }
  const options: Permission[] = ['ALLOW', 'ASK_EACH_TIME', 'BLOCK']
  const c = colors[value]

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 text-[10px] font-medium px-2.5 py-1 rounded border cursor-pointer ${c.text} ${c.bg} ${c.border}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
        {labels[value]}
        <ChevronDown size={10} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.1 }}
              className="absolute right-0 top-full mt-1 w-28 rounded-lg bg-midnight-200 border border-white/10 shadow-xl z-50 py-1"
            >
              {options.map((opt) => {
                const oc = colors[opt]
                return (
                  <button
                    key={opt}
                    onClick={() => { onChange(opt); setOpen(false) }}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 text-[10px] font-medium text-left transition-colors cursor-pointer hover:bg-white/5 ${
                      value === opt ? oc.text : 'text-starlight-300'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${oc.dot}`} />
                    {labels[opt]}
                    {value === opt && <CheckCircle2 size={10} className="ml-auto" />}
                  </button>
                )
              })}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Expandable Config Panel wrapper ──

function ConfigPanel({ expanded, children }: { expanded: boolean; children: React.ReactNode }) {
  return (
    <AnimatePresence>
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
          className="overflow-hidden"
        >
          <div className="px-4 pb-4 pt-1 ml-14 border-t border-white/5 space-y-3">
            {children}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ── Three-dot menu ──

function ContextMenu({ items, onClose }: { items: { label: string; icon: React.ReactNode; onClick: () => void; danger?: boolean }[]; onClose: () => void }) {
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="absolute right-0 top-full mt-1 w-48 rounded-lg bg-midnight-200 border border-white/10 shadow-xl z-50 py-1"
      >
        {items.map((item) => (
          <button
            key={item.label}
            onClick={() => { item.onClick(); onClose() }}
            className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors cursor-pointer ${
              item.danger ? 'text-accent-red hover:bg-accent-red/10' : 'text-starlight-300 hover:bg-white/5'
            }`}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </motion.div>
    </>
  )
}

// ── Runtime Row with expandable config ──

function RuntimeRow({ runtime, isPrimary, expanded, onToggleExpand, onSetPrimary, onTest }: {
  runtime: RuntimeData
  isPrimary: boolean
  expanded: boolean
  onToggleExpand: () => void
  onSetPrimary: () => void
  onTest: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [testing, setTesting] = useState(false)
  const Icon = RUNTIME_ICONS[runtime.runtime_id] || Cpu

  const isOnline = runtime.status === 'online'
  const isInstalled = runtime.installed
  const isAuthenticated = runtime.subscription?.is_authenticated ?? true

  const handleTest = async () => {
    setTesting(true)
    onTest()
    setTimeout(() => setTesting(false), 5000)
  }

  return (
    <div>
      <div
        className="flex items-center gap-4 px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg group cursor-pointer"
        onClick={onToggleExpand}
      >
        <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-starlight-100">{runtime.display_name}</span>
            {isPrimary && <Crown size={12} className="text-accent-amber" aria-label="Primary Mind" />}
          </div>
          <p className="text-xs text-starlight-500 truncate">
            {isOnline && runtime.subscription?.is_authenticated
              ? `Connected${runtime.subscription.plan_name ? ` (${runtime.subscription.plan_name})` : ''}`
              : isInstalled ? 'Installed, not authenticated'
              : 'Not installed'}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
          {isOnline && isAuthenticated ? (
            <span className="text-xs text-accent-green font-medium">Connected</span>
          ) : isOnline && !isAuthenticated ? (
            <span className="text-xs text-accent-amber font-medium">Not authenticated</span>
          ) : isInstalled ? (
            <span className="text-xs text-accent-amber">Offline</span>
          ) : (
            <button
              onClick={() => toast.info(`Visit the ${runtime.display_name} website for setup instructions.`)}
              className="px-3 py-1 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer"
            >
              Setup
            </button>
          )}
          {expanded ? <ChevronUp size={14} className="text-starlight-400" /> : <ChevronDown size={14} className="text-starlight-400" />}
          {isOnline && (
            <div className="relative">
              <button onClick={() => setMenuOpen(!menuOpen)} className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer">
                <MoreVertical size={14} />
              </button>
              <AnimatePresence>
                {menuOpen && (
                  <ContextMenu
                    onClose={() => setMenuOpen(false)}
                    items={[
                      { label: 'Test connection', icon: testing ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />, onClick: handleTest },
                      { label: isPrimary ? 'Primary Mind' : 'Set as Primary Mind', icon: <Crown size={12} />, onClick: onSetPrimary },
                    ]}
                  />
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>

      {/* Expandable config panel */}
      <ConfigPanel expanded={expanded}>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
          <div>
            <span className="text-starlight-500">Status</span>
            <p className="text-starlight-200 font-medium flex items-center gap-1.5 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-accent-green' : 'bg-accent-red'}`} />
              {isOnline ? 'Online' : isInstalled ? 'Offline' : 'Not installed'}
            </p>
          </div>
          <div>
            <span className="text-starlight-500">Authentication</span>
            <p className="text-starlight-200 font-medium mt-0.5">
              {isAuthenticated ? (runtime.subscription?.user_display || 'Authenticated') : 'Not authenticated'}
            </p>
          </div>
          {runtime.subscription?.plan_name && (
            <div>
              <span className="text-starlight-500">Plan</span>
              <p className="text-starlight-200 font-medium mt-0.5">{runtime.subscription.plan_name}</p>
            </div>
          )}
          <div>
            <span className="text-starlight-500">Primary Mind</span>
            <p className="text-starlight-200 font-medium mt-0.5">{isPrimary ? 'Yes (active)' : 'No'}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 pt-2">
          {!isPrimary && isOnline && (
            <button
              onClick={onSetPrimary}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 cursor-pointer"
            >
              <Crown size={12} /> Set as Primary Mind
            </button>
          )}
          {isOnline && (
            <button
              onClick={handleTest}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
            >
              {testing ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />} Test connection
            </button>
          )}
        </div>
      </ConfigPanel>
    </div>
  )
}

// ── Connector Row with expandable config ──

function ConnectorRow({ connector, connected, instanceId, expanded, onToggleExpand, onDisconnect }: {
  connector: typeof CONNECTORS[0]
  connected: boolean
  instanceId: string | null
  expanded: boolean
  onToggleExpand: () => void
  onDisconnect: (instanceId: string) => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [apiKeyValue, setApiKeyValue] = useState('')
  const [saving, setSaving] = useState(false)
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
        config: { api_key: apiKeyValue.trim() },
      })
      toast.success(`${connector.name} connected successfully`)
      setApiKeyValue('')
    } catch {
      toast.error(`Failed to connect ${connector.name}. Check your key and try again.`)
    } finally {
      setSaving(false)
    }
  }

  const handleOAuthConnect = () => {
    // In production, this would redirect to the OAuth provider
    toast.info(`${connector.name} OAuth flow will open in a new window. Configure your OAuth credentials in Settings > Developer first.`)
  }

  return (
    <div>
      <div
        className="flex items-center gap-4 px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg group cursor-pointer"
        onClick={onToggleExpand}
      >
        <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-starlight-100">{connector.name}</span>
          <p className="text-xs text-starlight-500 truncate">{connector.subtitle}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
          {connected ? (
            <span className="text-xs text-accent-green font-medium">Connected</span>
          ) : (
            <button
              onClick={onToggleExpand}
              className="px-3 py-1 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer"
            >
              Configure
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

        {/* Tools & Permissions */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Settings size={12} className="text-starlight-400" />
            <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">Tool Permissions</span>
          </div>
          <div className="rounded-lg border border-white/5 divide-y divide-white/5">
            {connector.tools.map((tool) => (
              <div key={tool} className="flex items-center justify-between px-3 py-2">
                <div className="flex items-center gap-2">
                  <Terminal size={11} className="text-starlight-500" />
                  <span className="text-xs text-starlight-300 font-mono">{tool}</span>
                </div>
                <PermissionSelect
                  value={toolPermissions[tool] || 'ASK_EACH_TIME'}
                  onChange={(v) => setToolPermissions((prev) => ({ ...prev, [tool]: v }))}
                />
              </div>
            ))}
          </div>
        </div>
      </ConfigPanel>
    </div>
  )
}

// ── Extension Row with expandable config ──

function ExtensionRow({ ext, expanded, onToggleExpand, onToggle }: {
  ext: ExtensionData
  expanded: boolean
  onToggleExpand: () => void
  onToggle: (id: string, enabled: boolean) => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [permission, setPermission] = useState<Permission>(ext.permission as Permission || 'ASK_EACH_TIME')
  const Icon = EXTENSION_ICONS[ext.id] || Puzzle

  return (
    <div>
      <div
        className="flex items-center gap-4 px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg group cursor-pointer"
        onClick={onToggleExpand}
      >
        <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-starlight-100">{ext.name}</span>
          <p className="text-xs text-starlight-500 truncate">{ext.description}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
          <span className={`text-xs font-medium ${ext.enabled ? 'text-accent-green' : 'text-starlight-500'}`}>
            {ext.enabled ? 'Enabled' : 'Disabled'}
          </span>
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
                    { label: ext.enabled ? 'Disable' : 'Enable', icon: <Settings size={12} />, onClick: () => onToggle(ext.id, !ext.enabled) },
                  ]}
                />
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Expandable config panel */}
      <ConfigPanel expanded={expanded}>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
          <div>
            <span className="text-starlight-500">Source</span>
            <p className="text-starlight-200 font-medium mt-0.5">MCP Server (local)</p>
          </div>
          <div>
            <span className="text-starlight-500">Status</span>
            <p className="text-starlight-200 font-medium flex items-center gap-1.5 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${ext.enabled ? 'bg-accent-green' : 'bg-starlight-500'}`} />
              {ext.enabled ? 'Running' : 'Stopped'}
            </p>
          </div>
        </div>

        {/* Permission control */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Shield size={12} className="text-starlight-400" />
            <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">Default Permission</span>
          </div>
          <div className="flex items-center gap-3">
            <PermissionSelect value={permission} onChange={setPermission} />
            <span className="text-[10px] text-starlight-500">
              {permission === 'ALLOW' ? 'All tools run without asking' : permission === 'ASK_EACH_TIME' ? 'Daena asks before each tool use' : 'All tools blocked'}
            </span>
          </div>
        </div>

        {/* Enable/Disable toggle */}
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={() => onToggle(ext.id, !ext.enabled)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer ${
              ext.enabled
                ? 'bg-accent-red/10 text-accent-red hover:bg-accent-red/20'
                : 'bg-accent-green/10 text-accent-green hover:bg-accent-green/20'
            }`}
          >
            {ext.enabled ? <><ToggleRight size={14} /> Disable</> : <><ToggleLeft size={14} /> Enable</>}
          </button>
        </div>
      </ConfigPanel>
    </div>
  )
}

// ── Main Page ──

type TabKey = 'runtimes' | 'extensions' | 'connectors'

export function ConnectionsPage() {
  usePageTitle('Connections')
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = (searchParams.get('tab') as TabKey) || 'runtimes'
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab)
  const [runtimes, setRuntimes] = useState<RuntimeData[]>([])
  const [primaryRuntime, setPrimaryRuntime] = useState<string>('claude_code')
  const [loading, setLoading] = useState(true)
  const [connectorSearch, setConnectorSearch] = useState('')
  const [connectorInstances, setConnectorInstances] = useState<Record<string, string>>({})
  const [extensions, setExtensions] = useState<ExtensionData[]>([])
  const [extLoading, setExtLoading] = useState(true)
  // Track which item is expanded (only one at a time per tab)
  const [expandedItem, setExpandedItem] = useState<string | null>(null)

  const toggleExpand = (id: string) => setExpandedItem((prev) => prev === id ? null : id)

  const fetchRuntimes = useCallback(async () => {
    try {
      const res = await api.get('/runtimes')
      const data = res.data?.data?.runtimes || []
      setRuntimes(data)
      const persistedPrimary = res.data?.data?.primary_runtime
      if (persistedPrimary) setPrimaryRuntime(persistedPrimary)
    } catch { /* graceful */ }
    finally { setLoading(false) }
  }, [])

  const fetchConnectorInstances = useCallback(async () => {
    try {
      const [connRes, instRes] = await Promise.allSettled([
        api.get('/connections/connectors'),
        api.get('/connections/instances'),
      ])
      const dbConnectors = connRes.status === 'fulfilled' ? connRes.value.data?.data || [] : []
      const instances = instRes.status === 'fulfilled' ? instRes.value.data?.data || [] : []
      const map: Record<string, string> = {}
      for (const inst of instances) {
        if (inst.status !== 'CONNECTED') continue
        const dbConnector = dbConnectors.find((c: Record<string, string>) => c.id === inst.connector_id)
        if (dbConnector) {
          const slug = (dbConnector.name || '').toLowerCase().replace(/\s+/g, '-')
          map[slug] = inst.id
        }
      }
      setConnectorInstances(map)
    } catch { /* graceful */ }
  }, [])

  const fetchExtensions = useCallback(async () => {
    setExtLoading(true)
    try {
      const res = await api.get('/connections/extensions')
      const data = res.data?.data || []
      setExtensions(data.map((e: Record<string, unknown>) => {
        const name = String(e.name || '')
        const slug = name.toLowerCase().replace(/[\s_]+/g, '-').replace(/[^a-z0-9-]/g, '')
        return {
          id: slug || String(e.id || ''),
          name,
          description: String(e.description || ''),
          enabled: e.enabled !== false,
          permission: 'ASK_EACH_TIME',
        }
      }))
    } catch { /* graceful */ }
    finally { setExtLoading(false) }
  }, [])

  useEffect(() => {
    void fetchRuntimes()
    void fetchConnectorInstances()
    void fetchExtensions()
  }, [fetchRuntimes, fetchConnectorInstances, fetchExtensions])

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab)
    setSearchParams({ tab })
    setExpandedItem(null) // collapse when switching tabs
  }

  const handleSetPrimary = async (runtimeId: string) => {
    try {
      await api.put('/runtimes/primary', { runtime_id: runtimeId })
      setPrimaryRuntime(runtimeId)
      toast.success(`Primary Mind set to ${runtimeId}`)
    } catch { toast.error('Failed to set primary runtime') }
  }

  const handleTestRuntime = async (runtimeId: string) => {
    try {
      const res = await api.post(`/runtimes/${runtimeId}/test`)
      const data = res.data?.data
      if (data?.test_passed) {
        toast.success(`${runtimeId}: OK (${data.latency_ms}ms)`)
      } else {
        toast.error(`${runtimeId}: Test failed`)
      }
    } catch { toast.error('Test failed') }
  }

  const handleDisconnectConnector = async (instanceId: string) => {
    try {
      await api.post(`/connections/instances/${instanceId}/disconnect`)
      toast.success('Disconnected')
      await fetchConnectorInstances()
    } catch {
      toast.error('Failed to disconnect')
    }
  }

  const filteredConnectors = connectorSearch
    ? CONNECTORS.filter(c => c.name.toLowerCase().includes(connectorSearch.toLowerCase()) || c.category.toLowerCase().includes(connectorSearch.toLowerCase()))
    : CONNECTORS

  const tabs: { key: TabKey; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: 'runtimes', label: 'AI Runtimes', icon: <Cpu size={16} />, count: runtimes.filter(r => r.status === 'online').length },
    { key: 'extensions', label: 'Extensions', icon: <Puzzle size={16} />, count: extensions.length },
    { key: 'connectors', label: 'Connectors', icon: <Plug size={16} />, count: CONNECTORS.length },
  ]

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Tab bar */}
        <div className="flex items-center gap-1 border-b border-white/5 pb-0">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => handleTabChange(tab.key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-all cursor-pointer ${
                activeTab === tab.key
                  ? 'border-primary-500 text-primary-400'
                  : 'border-transparent text-starlight-400 hover:text-starlight-200'
              }`}
            >
              {tab.icon}
              {tab.label}
              {tab.count != null && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-white/5">{tab.count}</span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
          >
            {/* ── Runtimes ── */}
            {activeTab === 'runtimes' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-display font-bold text-starlight-100">AI Runtimes</h2>
                    <p className="text-xs text-starlight-400">AI models and CLI tools that power Daena's intelligence</p>
                  </div>
                  <button onClick={() => { setLoading(true); void fetchRuntimes() }} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer">
                    <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
                  </button>
                </div>
                <div className="rounded-xl border border-white/5 divide-y divide-white/5">
                  {runtimes.map((rt) => (
                    <RuntimeRow
                      key={rt.runtime_id}
                      runtime={rt}
                      isPrimary={primaryRuntime === rt.runtime_id}
                      expanded={expandedItem === rt.runtime_id}
                      onToggleExpand={() => toggleExpand(rt.runtime_id)}
                      onSetPrimary={() => void handleSetPrimary(rt.runtime_id)}
                      onTest={() => void handleTestRuntime(rt.runtime_id)}
                    />
                  ))}
                  {runtimes.length === 0 && !loading && (
                    <div className="px-4 py-8 text-center text-xs text-starlight-500">No runtimes detected. Click Refresh to scan.</div>
                  )}
                </div>
              </div>
            )}

            {/* ── Extensions ── */}
            {activeTab === 'extensions' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-display font-bold text-starlight-100">Extensions</h2>
                    <p className="text-xs text-starlight-400">Allow Daena to directly interact with apps, data, and tools on your computer</p>
                  </div>
                  <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer">
                    <Plus size={12} /> Browse extensions
                  </button>
                </div>

                <div>
                  <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold px-4 mb-2">Installed on your computer</p>
                  <div className="rounded-xl border border-white/5 divide-y divide-white/5">
                    {extensions.map((ext) => (
                      <ExtensionRow
                        key={ext.id}
                        ext={ext}
                        expanded={expandedItem === ext.id}
                        onToggleExpand={() => toggleExpand(ext.id)}
                        onToggle={(id, enabled) => {
                          setExtensions((prev) => prev.map((e) => e.id === id ? { ...e, enabled } : e))
                          toast.success(`${ext.name} ${enabled ? 'enabled' : 'disabled'}`)
                        }}
                      />
                    ))}
                    {extensions.length === 0 && !extLoading && (
                      <div className="px-4 py-8 text-center text-xs text-starlight-500">No extensions installed. Install MCP servers to add extensions.</div>
                    )}
                  </div>
                </div>

                <div className="border-2 border-dashed border-white/10 rounded-xl p-6 text-center">
                  <p className="text-xs text-starlight-500">Drag .MCPB or .DXT files here to install</p>
                </div>
              </div>
            )}

            {/* ── Connectors ── */}
            {activeTab === 'connectors' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-display font-bold text-starlight-100">Connectors</h2>
                    <p className="text-xs text-starlight-400">Allow Daena to reference other apps and services for more context</p>
                  </div>
                  <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer">
                    <Plus size={12} /> Browse connectors
                  </button>
                </div>

                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
                  <input
                    type="text"
                    value={connectorSearch}
                    onChange={(e) => setConnectorSearch(e.target.value)}
                    placeholder="Search connectors..."
                    className="w-full glass-input pl-9 pr-4 py-2.5 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500"
                  />
                </div>

                <div className="rounded-xl border border-white/5 divide-y divide-white/5">
                  {filteredConnectors.map((c) => (
                    <ConnectorRow
                      key={c.id}
                      connector={c}
                      connected={!!connectorInstances[c.id]}
                      instanceId={connectorInstances[c.id] || null}
                      expanded={expandedItem === c.id}
                      onToggleExpand={() => toggleExpand(c.id)}
                      onDisconnect={handleDisconnectConnector}
                    />
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

export default ConnectionsPage
