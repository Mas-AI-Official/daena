/**
 * Runtimes ("Mind Control") tab for the Connections page.
 *
 * Renders:
 *   - The cloud-mode banner + API providers list (when applicable)
 *   - The CLI Bridge card (connect a local CLI to the Daena cloud)
 *   - The detected-runtimes list with expandable per-runtime config
 *     (status / authentication / plan / Set as Primary / Test / Disconnect)
 *
 * The Primary Mind picker lives inside each row's expanded panel and
 * via the three-dot menu — this is the canonical place to choose which
 * runtime orchestrates the others (per Daena's locked product identity:
 * "the Primary Mind setting determines which runtime orchestrates all
 * others").
 */
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Cpu,
  RefreshCw,
  MoreVertical,
  CheckCircle2,
  Loader2,
  Crown,
  ChevronDown,
  ChevronUp,
  Key,
  Globe,
  Shield,
  Zap,
  Terminal,
  ExternalLink,
  Unplug,
  AlertTriangle,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { confirmDialog } from '@/stores/confirmStore'
import { RUNTIME_ICONS } from '@/components/icons/BrandIcons'
import { ConfigPanel, ContextMenu } from './shared'
import type { RuntimeData } from './types'

// ── CLI Bridge Card (connects user's local CLI tools to Daena cloud) ──

function CLIBridgeCard() {
  const [expanded, setExpanded] = useState(false)
  const [bridgeToken, setBridgeToken] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [bridgeStatus, setBridgeStatus] = useState<{active_bridges: number} | null>(null)

  useEffect(() => {
    api.get('/bridge/status').then(res => {
      setBridgeStatus(res.data?.data || null)
    }).catch(() => {/* graceful */})
  }, [])

  const isConnected = (bridgeStatus?.active_bridges ?? 0) > 0

  const generateToken = async () => {
    setGenerating(true)
    try {
      const res = await api.post('/bridge/token', { label: 'CLI Bridge' })
      const token = res.data?.data?.token
      if (token) {
        setBridgeToken(token)
        toast.success('Bridge token generated! Follow the setup instructions below.')
      }
    } catch {
      toast.error('Failed to generate bridge token')
    } finally {
      setGenerating(false)
    }
  }

  const copyCommand = (cmd: string) => {
    navigator.clipboard.writeText(cmd).then(() => {
      toast.success('Copied to clipboard!')
    }).catch(() => {
      toast.info(`Command: ${cmd}`)
    })
  }

  return (
    <div className="rounded-xl border-2 border-primary-500/30 bg-gradient-to-r from-primary-500/5 to-accent-teal/5 p-4 space-y-3">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-primary-500/20 flex items-center justify-center">
          <Zap size={20} className="text-primary-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-starlight-100">Daena CLI Bridge</span>
            {isConnected ? (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-accent-green/20 text-accent-green font-semibold">CONNECTED</span>
            ) : (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-primary-500/20 text-primary-400 font-semibold">RECOMMENDED</span>
            )}
          </div>
          <p className="text-xs text-starlight-400 mt-0.5">
            Connect your local CLI tools (Claude Code, Gemini CLI, Codex) to Daena.
            Your subscriptions stay on your machine -- Daena adds governance, departments, and audit.
          </p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="px-4 py-2 rounded-lg text-xs font-semibold bg-primary-500 text-white hover:bg-primary-600 cursor-pointer whitespace-nowrap"
        >
          {expanded ? 'Close' : 'Set Up'}
        </button>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden space-y-4"
          >
            {/* Security info */}
            <div className="flex items-start gap-2 bg-accent-green/5 border border-accent-green/20 rounded-lg px-3 py-2">
              <Shield size={14} className="text-accent-green mt-0.5 shrink-0" />
              <p className="text-[11px] text-starlight-300">
                <strong className="text-accent-green">Your keys never leave your machine.</strong>{' '}
                Daena sends task descriptions. Your CLI executes them with your own credentials.
                Results are returned to Daena for audit logging only.
              </p>
            </div>

            {/* Step 1: Generate token */}
            <div className="space-y-2">
              <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">Step 1: Generate Bridge Token</p>
              {bridgeToken ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="password"
                      value={bridgeToken}
                      readOnly
                      className="flex-1 glass-input px-3 py-2 rounded-lg text-xs text-starlight-200 font-mono"
                    />
                    <button
                      onClick={() => copyCommand(bridgeToken)}
                      className="px-3 py-2 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
                    >
                      Copy
                    </button>
                  </div>
                  <p className="text-[10px] text-starlight-500">Token expires in 30 days. You can generate a new one anytime.</p>
                </div>
              ) : (
                <button
                  onClick={() => void generateToken()}
                  disabled={generating}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-primary-500/15 text-primary-400 hover:bg-primary-500/25 cursor-pointer border border-primary-500/20 disabled:opacity-50"
                >
                  {generating ? <Loader2 size={12} className="animate-spin" /> : <Key size={12} />}
                  Generate Token
                </button>
              )}
            </div>

            {/* Step 2: Install & connect */}
            <div className="space-y-2">
              <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">Step 2: Install & Connect</p>

              {/* Claude Code method */}
              <div className="rounded-lg border border-white/10 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <Terminal size={12} className="text-primary-400" />
                  <span className="text-xs font-medium text-starlight-200">Claude Code (recommended)</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-[10px] text-starlight-400 bg-midnight-800/60 rounded px-2 py-1.5 font-mono overflow-x-auto">
                    claude mcp add daena -- npx @mas-ai/daena-mcp{bridgeToken ? ` --token ${bridgeToken.slice(0, 20)}...` : ' --token YOUR_TOKEN'}
                  </code>
                  <button
                    onClick={() => copyCommand(`claude mcp add daena -- npx @mas-ai/daena-mcp${bridgeToken ? ` --token ${bridgeToken}` : ' --token YOUR_TOKEN'}`)}
                    className="px-2 py-1 rounded text-[10px] bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer shrink-0"
                  >
                    Copy
                  </button>
                </div>
              </div>

              {/* npm method */}
              <div className="rounded-lg border border-white/10 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <Globe size={12} className="text-accent-teal" />
                  <span className="text-xs font-medium text-starlight-200">npm (standalone)</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-[10px] text-starlight-400 bg-midnight-800/60 rounded px-2 py-1.5 font-mono">
                    npm install -g @mas-ai/daena-mcp
                  </code>
                  <button
                    onClick={() => copyCommand('npm install -g @mas-ai/daena-mcp')}
                    className="px-2 py-1 rounded text-[10px] bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer shrink-0"
                  >
                    Copy
                  </button>
                </div>
              </div>

              {/* pip method */}
              <div className="rounded-lg border border-white/10 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <Globe size={12} className="text-accent-amber" />
                  <span className="text-xs font-medium text-starlight-200">pip (Python)</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-[10px] text-starlight-400 bg-midnight-800/60 rounded px-2 py-1.5 font-mono">
                    pip install daena-mcp
                  </code>
                  <button
                    onClick={() => copyCommand('pip install daena-mcp')}
                    className="px-2 py-1 rounded text-[10px] bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer shrink-0"
                  >
                    Copy
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Runtime Row with expandable config ──

function RuntimeRow({ runtime, isPrimary, expanded, onToggleExpand, onSetPrimary, onTest, onRefreshAuth }: {
  runtime: RuntimeData
  isPrimary: boolean
  expanded: boolean
  onToggleExpand: () => void
  onSetPrimary: () => void
  onTest: () => void
  onRefreshAuth?: () => void
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

  // 2026-04-29 stabilization: removed the duplicate "Connected" chip that
  // sat next to the runtime name -- the action button on the right already
  // communicates auth state (green when connected, amber when needs connect,
  // primary when not installed). Keeping two sources of "are we connected?"
  // signal made the row feel cluttered. Status now lives in ONE place per row.

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
            <button
              onClick={async (e) => {
                e.stopPropagation()
                // REAL disconnect — previously this was a fake toast that
                // never hit the backend, leaving Daena thinking the runtime
                // was still online. Now confirm + POST + refresh.
                const ok = await confirmDialog({
                  title: `Disconnect ${runtime.display_name}?`,
                  message: 'Daena will stop routing to this runtime. You can reconnect anytime.',
                  confirmLabel: 'Disconnect',
                  variant: 'warning',
                })
                if (!ok) return
                try {
                  const res = await api.post(`/runtimes/${runtime.runtime_id}/disconnect`)
                  const promoted = res.data?.data?.primary_promoted_to
                  if (promoted) {
                    toast.success(
                      `${runtime.display_name} disconnected. Primary Mind auto-promoted to ${promoted}.`,
                      8000,
                    )
                  } else {
                    toast.success(`${runtime.display_name} disconnected`)
                  }
                  onRefreshAuth?.()
                } catch {
                  toast.error(`Failed to disconnect ${runtime.display_name}`)
                }
              }}
              className="px-3 py-1 rounded-lg text-xs bg-accent-green/10 text-accent-green hover:bg-status-error/10 hover:text-status-error cursor-pointer transition-colors group/conn"
            >
              <span className="group-hover/conn:hidden">Connected</span>
              <span className="hidden group-hover/conn:inline">Disconnect</span>
            </button>
          ) : isOnline && !isAuthenticated ? (
            <div className="flex items-center gap-1.5">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  const urls: Record<string, string> = {
                    'claude_code': 'https://docs.anthropic.com/en/docs/claude-code',
                    'codex': 'https://github.com/openai/codex',
                    'gemini_cli': 'https://github.com/google-gemini/gemini-cli',
                    'grok_cli': 'https://docs.x.ai/overview',
                    'ollama': 'https://ollama.ai',
                  }
                  const url = urls[runtime.runtime_id] || runtime.subscription?.login_url
                  const cmds: Record<string, string> = {
                    'claude_code': 'claude login',
                    'codex': 'codex login',
                    'gemini_cli': 'gemini auth',
                    'grok_cli': 'grok auth',
                    'ollama': 'ollama serve',
                  }
                  const cmd = cmds[runtime.runtime_id]
                  if (url) window.open(url, '_blank')
                  // Actionable nudge: tell the user the exact command to run
                  // and remind them to click Re-check when done.
                  toast.info(
                    cmd
                      ? `Opened ${runtime.display_name} docs. Run \`${cmd}\` in a terminal, then click "Re-check" here.`
                      : `Run the auth command for ${runtime.display_name} in your terminal, then click "Re-check".`,
                    12000,
                  )
                }}
                className="px-3 py-1 rounded-lg text-xs bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 cursor-pointer"
              >
                Connect
              </button>
              <button
                onClick={async (e) => {
                  e.stopPropagation()
                  // Re-check after the user finishes external login. Calls
                  // /refresh-auth directly so we re-probe THIS runtime
                  // without doing a full page-wide rescan.
                  try {
                    const res = await api.post(`/runtimes/${runtime.runtime_id}/refresh-auth`)
                    const isAuth = res.data?.data?.subscription?.is_authenticated
                    if (isAuth) {
                      toast.success(`${runtime.display_name} is now authenticated.`)
                      onRefreshAuth?.()
                    } else {
                      toast.info(`${runtime.display_name} still not authenticated. Finish the login in the docs tab.`)
                    }
                  } catch {
                    toast.error('Re-check failed')
                  }
                }}
                title="Re-check after you finish external login"
                className="px-2 py-1 rounded-lg text-xs bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer"
              >
                Re-check
              </button>
            </div>
          ) : isInstalled ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                const urls: Record<string, string> = {
                  'claude_code': 'https://docs.anthropic.com/en/docs/claude-code',
                  'codex': 'https://github.com/openai/codex',
                  'gemini_cli': 'https://github.com/google-gemini/gemini-cli',
                  'grok_cli': 'https://docs.x.ai/overview',
                  'ollama': 'https://ollama.ai',
                }
                const url = urls[runtime.runtime_id] || runtime.subscription?.login_url
                if (url) window.open(url, '_blank')
              }}
              className="px-3 py-1 rounded-lg text-xs bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 cursor-pointer"
            >
              Connect
            </button>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation()
                const urls: Record<string, string> = {
                  'claude_code': 'https://docs.anthropic.com/en/docs/claude-code',
                  'codex': 'https://github.com/openai/codex',
                  'gemini_cli': 'https://github.com/google-gemini/gemini-cli',
                  'grok_cli': 'https://docs.x.ai/overview',
                  'ollama': 'https://ollama.ai',
                }
                const url = urls[runtime.runtime_id] || runtime.subscription?.login_url
                if (url) window.open(url, '_blank')
                else toast.info(`Visit the ${runtime.display_name} website for setup instructions.`)
              }}
              className="px-3 py-1 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer flex items-center gap-1"
            >
              Setup <ExternalLink size={10} className="opacity-50" />
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
          {runtime.subscription?.is_authenticated && (
            <button
              onClick={async () => {
                const ok = await confirmDialog({
                  title: `Disconnect ${runtime.display_name}?`,
                  message: 'You can reconnect anytime.',
                  confirmLabel: 'Disconnect',
                  variant: 'warning',
                })
                if (!ok) return
                try {
                  const res = await api.post(`/runtimes/${runtime.runtime_id}/disconnect`)
                  const promoted = res.data?.data?.primary_promoted_to
                  if (promoted) {
                    toast.success(
                      `${runtime.display_name} disconnected. Primary Mind auto-promoted to ${promoted}.`,
                      8000,
                    )
                  } else {
                    toast.success(`${runtime.display_name} disconnected`)
                  }
                  onRefreshAuth?.()
                } catch {
                  toast.error('Failed to disconnect')
                }
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-accent-red bg-accent-red/10 border border-accent-red/20 hover:bg-accent-red/20 cursor-pointer"
            >
              <Unplug size={12} />
              Disconnect
            </button>
          )}
        </div>
      </ConfigPanel>
    </div>
  )
}

// ── Tab body ──

export interface ConnectionsRuntimesProps {
  runtimes: RuntimeData[]
  primaryRuntime: string
  loading: boolean
  cloudMode: boolean
  /** True while the registry is still doing its first scan (Phase 3 backend). */
  warming?: boolean
  apiProviders: {
    provider: string
    status: string
    display_name: string
    /** Optional failure surface from Phase 3 per-provider error cache. */
    last_error_at?: number
    last_error_msg?: string
  }[]
  expandedItem: string | null
  onToggleExpand: (id: string) => void
  onSetPrimary: (runtimeId: string) => void
  onTestRuntime: (runtimeId: string) => void
  onRefreshRuntimes: () => void
}

function relativeAgo(epochSeconds: number): string {
  const ms = Date.now() - epochSeconds * 1000
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s}s ago`
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  return `${h}h ago`
}

export default function ConnectionsRuntimes({
  runtimes,
  primaryRuntime,
  loading,
  cloudMode,
  warming = false,
  apiProviders,
  expandedItem,
  onToggleExpand,
  onSetPrimary,
  onTestRuntime,
  onRefreshRuntimes,
}: ConnectionsRuntimesProps) {
  // Status summary counts: Online | Warming | Failed
  // 2026-04-29 stabilization: gives the operator a one-glance view of "what's
  // up vs what's not" before scanning the per-row detail.
  const onlineCount = runtimes.filter((r) => r.status === 'online' && r.subscription?.is_authenticated).length
  const failedCount = runtimes.filter(
    (r) => r.installed && (!r.subscription?.is_authenticated || r.status !== 'online')
  ).length
  // Plus failed API providers from Phase 3 per-provider error cache
  const failedApiCount = apiProviders.filter((p) => p.status === 'degraded').length
  const totalFailed = failedCount + failedApiCount
  const notInstalledCount = runtimes.filter((r) => !r.installed).length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-display font-bold text-starlight-100">AI Runtimes</h2>
          <p className="text-xs text-starlight-400">AI models and CLI tools that power Daena's intelligence</p>
        </div>
        <button onClick={onRefreshRuntimes} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* Status summary -- one-glance view of online vs failed vs warming. */}
      <div className="grid grid-cols-4 gap-2 text-[11px]">
        <div className="rounded-lg border border-status-success/20 bg-status-success/5 px-3 py-2">
          <div className="text-status-success font-mono font-bold text-base">{onlineCount}</div>
          <div className="text-starlight-500 uppercase tracking-wider">Online</div>
        </div>
        <div className="rounded-lg border border-accent-amber/20 bg-accent-amber/5 px-3 py-2">
          <div className="text-accent-amber font-mono font-bold text-base">
            {warming ? '...' : notInstalledCount}
          </div>
          <div className="text-starlight-500 uppercase tracking-wider">
            {warming ? 'Warming' : 'Not Installed'}
          </div>
        </div>
        <div className="rounded-lg border border-status-error/20 bg-status-error/5 px-3 py-2">
          <div className="text-status-error font-mono font-bold text-base">{totalFailed}</div>
          <div className="text-starlight-500 uppercase tracking-wider">Failed</div>
        </div>
        <div className="rounded-lg border border-accent-cyan/20 bg-accent-cyan/5 px-3 py-2">
          <div className="text-accent-cyan font-mono font-bold text-base">{primaryRuntime ? '1' : '-'}</div>
          <div className="text-starlight-500 uppercase tracking-wider">Primary Mind</div>
        </div>
      </div>

      {warming && (
        <div className="rounded-lg border border-accent-cyan/20 bg-accent-cyan/5 px-4 py-2 flex items-center gap-2">
          <Loader2 size={14} className="text-accent-cyan animate-spin shrink-0" />
          <p className="text-[11px] text-accent-cyan">
            Detecting runtimes... initial registry scan in progress.
          </p>
        </div>
      )}

      {cloudMode && (
        <div className="rounded-xl border border-accent-amber/20 bg-accent-amber/5 px-4 py-3">
          <p className="text-xs text-accent-amber font-medium mb-1">Running in cloud mode</p>
          <p className="text-[11px] text-starlight-400">Local runtimes (Ollama, CLI tools) are not available. Connect API providers in Settings &gt; Models.</p>
        </div>
      )}

      {cloudMode && apiProviders.length > 0 && (
        <div>
          <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold px-4 mb-2">API Providers</p>
          <div className="rounded-xl border border-white/5 divide-y divide-white/5">
            {apiProviders.map((ap) => {
              const isDegraded = ap.status === 'degraded'
              return (
                <div key={ap.provider} className="flex items-center gap-4 px-4 py-3">
                  <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
                    <Globe size={22} className={isDegraded ? 'text-status-error' : 'text-starlight-300'} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-starlight-100">{ap.display_name}</span>
                    <p className="text-xs text-starlight-500">{ap.provider} API</p>
                    {/* Phase 3 backend now surfaces last_error_msg/at on failed providers.
                        Render inline so the user sees "Gemini timed out 14s ago" instead
                        of a misleading "Connected (0 models)" pill. */}
                    {isDegraded && ap.last_error_msg && (
                      <p className="text-[11px] text-status-error/80 mt-1 truncate">
                        {ap.last_error_msg}
                        {ap.last_error_at ? ` · ${relativeAgo(ap.last_error_at)}` : ''}
                      </p>
                    )}
                  </div>
                  <span
                    className={`flex items-center gap-1 text-[10px] ${
                      isDegraded ? 'text-status-error' : 'text-status-success'
                    }`}
                  >
                    {isDegraded ? <AlertTriangle size={10} /> : <CheckCircle2 size={10} />}
                    {isDegraded ? 'Degraded' : 'Connected'}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* CLI Bridge -- connect user's local tools to Daena cloud */}
      <CLIBridgeCard />

      <div className="rounded-xl border border-white/5 divide-y divide-white/5">
        {(cloudMode
          ? runtimes.filter((rt) => rt.runtime_id !== 'ollama')
          : runtimes
        ).map((rt) => (
          <RuntimeRow
            key={rt.runtime_id}
            runtime={rt}
            isPrimary={primaryRuntime === rt.runtime_id}
            expanded={expandedItem === rt.runtime_id}
            onToggleExpand={() => onToggleExpand(rt.runtime_id)}
            onSetPrimary={() => onSetPrimary(rt.runtime_id)}
            onTest={() => onTestRuntime(rt.runtime_id)}
            onRefreshAuth={onRefreshRuntimes}
          />
        ))}
        {runtimes.length === 0 && !loading && (
          <div className="px-4 py-8 text-center text-xs text-starlight-500">No runtimes detected. Click Refresh to scan.</div>
        )}
      </div>
    </div>
  )
}
