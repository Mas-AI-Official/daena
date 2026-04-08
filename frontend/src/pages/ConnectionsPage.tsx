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
  Unplug,
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
    login_url?: string
    setup_command?: string
    method?: string
    status?: string
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

// ── Browse catalog (Claude Desktop-style marketplace) ──

interface BrowseCatalogItem {
  id: string
  name: string
  description: string
  popularity?: string   // "Most popular", "#2 popular", etc.
  connected?: boolean
  category: string
  authUrl?: string      // URL to open for OAuth or setup
}

const BROWSE_CONNECTORS_CATALOG: BrowseCatalogItem[] = [
  // Communication
  { id: 'gmail', name: 'Gmail', description: 'Draft replies, summarize threads, and search your inbox', popularity: 'Most popular', category: 'Communication', authUrl: 'https://mail.google.com' },
  { id: 'slack', name: 'Slack', description: 'Send messages, create canvases, and fetch Slack data', popularity: '#4 popular', category: 'Communication', authUrl: 'https://slack.com' },
  { id: 'intercom', name: 'Intercom', description: 'Customer messaging, conversations, and support', category: 'Communication', authUrl: 'https://www.intercom.com' },
  { id: 'microsoft-teams', name: 'Microsoft Teams', description: 'Chat, meetings, and collaboration in Teams', category: 'Communication', authUrl: 'https://teams.microsoft.com' },
  // Productivity
  { id: 'google-calendar', name: 'Google Calendar', description: 'Manage your schedule and coordinate meetings', popularity: '#2 popular', category: 'Productivity', authUrl: 'https://calendar.google.com' },
  { id: 'google-drive', name: 'Google Drive', description: 'Access files, folders, and shared drives', popularity: '#3 popular', category: 'Productivity', authUrl: 'https://drive.google.com' },
  { id: 'notion', name: 'Notion', description: 'Connect your Notion workspace to search, update, and power workflows', popularity: '#5 popular', category: 'Productivity', authUrl: 'https://www.notion.so' },
  { id: 'monday', name: 'monday.com', description: 'Manage projects, boards, and workflows', category: 'Productivity', authUrl: 'https://monday.com' },
  { id: 'airtable', name: 'Airtable', description: 'Manage databases, tables, and automations', category: 'Productivity', authUrl: 'https://airtable.com' },
  { id: 'dropbox', name: 'Dropbox', description: 'Cloud storage, file sharing, and sync', category: 'Productivity', authUrl: 'https://www.dropbox.com' },
  { id: 'box', name: 'Box', description: 'Secure cloud content management and file sharing', category: 'Productivity', authUrl: 'https://www.box.com' },
  { id: 'wordpress', name: 'WordPress.com', description: 'Manage posts, pages, and site content', category: 'Productivity', authUrl: 'https://wordpress.com' },
  { id: 'clickup', name: 'ClickUp', description: 'Tasks, docs, goals, and project management', category: 'Productivity', authUrl: 'https://clickup.com' },
  { id: 'basecamp', name: 'Basecamp', description: 'Project management, team communication, and scheduling', category: 'Productivity', authUrl: 'https://basecamp.com' },
  // Project Management
  { id: 'asana', name: 'Asana', description: 'Track projects, manage tasks, and coordinate team work', category: 'Project Management', authUrl: 'https://asana.com' },
  { id: 'linear', name: 'Linear', description: 'Manage issues, projects, and team workflows', category: 'Project Management', authUrl: 'https://linear.app' },
  { id: 'atlassian', name: 'Atlassian Rovo', description: 'Access Jira and Confluence from Daena', category: 'Project Management', authUrl: 'https://www.atlassian.com' },
  // Design
  { id: 'canva', name: 'Canva', description: 'Search, create, autofill, and export Canva designs', popularity: '#6 popular', category: 'Design', authUrl: 'https://www.canva.com' },
  { id: 'figma', name: 'Figma', description: 'Generate diagrams and better code from Figma context', popularity: '#7 popular', category: 'Design', authUrl: 'https://www.figma.com' },
  // Development
  { id: 'github', name: 'GitHub', description: 'Repositories, issues, pull requests, and actions', popularity: '#8 popular', category: 'Development', authUrl: 'https://github.com' },
  { id: 'sentry', name: 'Sentry', description: 'Error tracking, performance monitoring, and debugging', category: 'Development', authUrl: 'https://sentry.io' },
  { id: 'cloudflare', name: 'Cloudflare', description: 'DNS, CDN, security, and Workers management', category: 'Development', authUrl: 'https://dash.cloudflare.com' },
  { id: 'vercel', name: 'Vercel', description: 'Deploy and manage web applications', category: 'Development', authUrl: 'https://vercel.com' },
  { id: 'hugging-face', name: 'Hugging Face', description: 'Models, datasets, and spaces for ML', category: 'Development', authUrl: 'https://huggingface.co' },
  // Data & Analytics
  { id: 'amplitude', name: 'Amplitude', description: 'Product analytics, user behavior, and insights', category: 'Analytics', authUrl: 'https://amplitude.com' },
  { id: 'hex', name: 'Hex', description: 'Collaborative data notebooks and analytics', category: 'Analytics', authUrl: 'https://hex.tech' },
  { id: 'snowflake', name: 'Snowflake', description: 'Cloud data warehouse queries and management', category: 'Analytics', authUrl: 'https://www.snowflake.com' },
  // Sales & CRM
  { id: 'hubspot', name: 'HubSpot', description: 'Chat with your CRM data to get personalized insights', category: 'Sales', authUrl: 'https://www.hubspot.com' },
  { id: 'salesforce', name: 'Salesforce', description: 'Access CRM records, contacts, and opportunities', category: 'Sales', authUrl: 'https://www.salesforce.com' },
  { id: 'clay', name: 'Clay', description: 'Enrich leads and automate outbound workflows', category: 'Sales', authUrl: 'https://www.clay.com' },
  // Finance
  { id: 'stripe', name: 'Stripe', description: 'View payments, subscriptions, and billing data', category: 'Finance', authUrl: 'https://dashboard.stripe.com' },
  { id: 'paypal', name: 'PayPal', description: 'Payments, invoicing, and transaction history', category: 'Finance', authUrl: 'https://www.paypal.com' },
  { id: 'square', name: 'Square', description: 'Payment processing, invoicing, and POS', category: 'Finance', authUrl: 'https://squareup.com' },
  { id: 'plaid', name: 'Plaid', description: 'Connect to bank accounts and financial data', category: 'Finance', authUrl: 'https://plaid.com' },
  // Automation
  { id: 'zapier', name: 'Zapier', description: 'Connect 5000+ apps and automate workflows', category: 'Automation', authUrl: 'https://zapier.com' },
  // Healthcare
  { id: 'apple-health', name: 'Apple Health', description: 'Access health records and lab results', category: 'Healthcare', authUrl: 'https://www.apple.com/health/' },
  { id: 'pubmed', name: 'PubMed', description: 'Search biomedical and life sciences literature', category: 'Healthcare', authUrl: 'https://pubmed.ncbi.nlm.nih.gov' },
  // Knowledge
  { id: 'gamma', name: 'Gamma', description: 'Create presentations, documents, and webpages with AI', category: 'Productivity', authUrl: 'https://gamma.app' },
  { id: 'granola', name: 'Granola', description: 'AI meeting notes and conversation summaries', category: 'Productivity', authUrl: 'https://www.granola.ai' },
]

const BROWSE_EXTENSIONS_CATALOG: BrowseCatalogItem[] = [
  // System
  { id: 'filesystem', name: 'Filesystem', description: 'Read and write files on your computer', category: 'System', authUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem' },
  { id: 'desktop-commander', name: 'Desktop Commander', description: 'Build, explore, and automate on your local machine', category: 'System', authUrl: 'https://github.com/wonderwhy-er/DesktopCommanderMCP' },
  { id: 'windows-mcp', name: 'Windows MCP', description: 'MCP server for Windows OS interaction', category: 'System', authUrl: 'https://github.com/SimonB97/win-cli-mcp-server' },
  // Design
  { id: 'figma-mcp', name: 'Figma MCP', description: 'Generate diagrams and code from Figma designs', category: 'Design', authUrl: 'https://github.com/nicholasgriffintn/figma-mcp-server' },
  // AI & Voice
  { id: 'elevenlabs', name: 'ElevenLabs', description: 'Create and manage AI voice agents', category: 'AI', authUrl: 'https://elevenlabs.io' },
  // Documents
  { id: 'pdf-tools', name: 'PDF Tools', description: 'Fill forms, analyze, and extract text from PDFs', category: 'Documents', authUrl: 'https://github.com/modelcontextprotocol/servers' },
  // Search
  { id: 'brave-search', name: 'Brave Search', description: 'Web search via Brave Search API', category: 'Search', authUrl: 'https://brave.com/search/api/' },
  // Browser
  { id: 'puppeteer', name: 'Puppeteer', description: 'Browser automation and web scraping', category: 'Browser', authUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/puppeteer' },
  { id: 'playwright', name: 'Playwright', description: 'Cross-browser testing and automation', category: 'Browser', authUrl: 'https://playwright.dev' },
  // Data
  { id: 'postgres', name: 'PostgreSQL', description: 'Query and manage PostgreSQL databases', category: 'Data', authUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/postgres' },
  { id: 'sqlite', name: 'SQLite', description: 'Query local SQLite databases', category: 'Data', authUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite' },
  { id: 'redis', name: 'Redis', description: 'In-memory data store and cache', category: 'Data', authUrl: 'https://github.com/modelcontextprotocol/servers' },
  // Monitoring
  { id: 'sentry-mcp', name: 'Sentry', description: 'Error tracking and performance monitoring', category: 'Monitoring', authUrl: 'https://sentry.io' },
  // Memory
  { id: 'memory', name: 'Memory', description: 'Persistent memory storage across conversations', category: 'AI', authUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/memory' },
  // Git
  { id: 'git', name: 'Git', description: 'Read, search, and analyze local Git repositories', category: 'Development', authUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/git' },
]

// ── Cloud-mode pre-installed extensions (mapped from BROWSE_EXTENSIONS_CATALOG) ──

const CLOUD_PREINSTALLED_EXTENSIONS: ExtensionData[] = BROWSE_EXTENSIONS_CATALOG.map((item) => ({
  id: item.id,
  name: item.name,
  description: item.description,
  enabled: true,
  permission: 'ALLOW',
}))

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
            {runtime.subscription?.is_authenticated && (
              <span className="flex items-center gap-1 text-[10px] text-status-success">
                <CheckCircle2 size={10} />
                Connected
              </span>
            )}
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
              onClick={(e) => {
                e.stopPropagation()
                toast.info(`${runtime.display_name} disconnected. Click "Connect" to reconnect.`)
                // Trigger refresh to update status
                onRefreshAuth?.()
              }}
              className="px-3 py-1 rounded-lg text-xs bg-accent-green/10 text-accent-green hover:bg-status-error/10 hover:text-status-error cursor-pointer transition-colors group/conn"
            >
              <span className="group-hover/conn:hidden">Connected</span>
              <span className="hidden group-hover/conn:inline">Disconnect</span>
            </button>
          ) : isOnline && !isAuthenticated ? (
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
                else toast.info(`Run the auth command for ${runtime.display_name} in your terminal.`)
              }}
              className="px-3 py-1 rounded-lg text-xs bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 cursor-pointer"
            >
              Connect
            </button>
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
                if (!confirm(`Disconnect ${runtime.display_name}? You can reconnect anytime.`)) return
                try {
                  await api.post(`/runtimes/${runtime.runtime_id}/disconnect`)
                  toast.success(`${runtime.display_name} disconnected`)
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

// ── Connector Row with expandable config ──

function ConnectorRow({ connector, connected, instanceId, expanded, onToggleExpand, onDisconnect, fetchInstances }: {
  connector: typeof CONNECTORS[0]
  connected: boolean
  instanceId: string | null
  expanded: boolean
  onToggleExpand: () => void
  onDisconnect: (instanceId: string) => void
  fetchInstances?: () => void
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

  const handleOAuthConnect = async () => {
    try {
      const res = await api.get(`/connectors/${connector.id}/oauth/authorize`)
      const data = res.data
      if (data?.error_type === 'oauth_not_configured') {
        toast.error(`${connector.name} OAuth not configured. ${data.help || 'Contact admin.'}`)
        return
      }
      const authUrl = data?.authorization_url
      if (!authUrl) {
        toast.error(`Failed to get authorization URL for ${connector.name}`)
        return
      }
      // Open OAuth consent in popup
      const popup = window.open(authUrl, `daena_oauth_${connector.id}`, 'width=600,height=700,popup=yes')
      if (!popup) {
        toast.error('Popup blocked. Please allow popups for this site.')
        return
      }
      // Listen for postMessage from callback page
      const handler = (event: MessageEvent) => {
        if (event.data?.type === 'oauth_success' && event.data?.connector === connector.id) {
          toast.success(`${connector.name} connected successfully`)
          window.removeEventListener('message', handler)
          // Refresh connector instances to show Connected state
          void fetchInstances?.()
        } else if (event.data?.type === 'oauth_error' && event.data?.connector === connector.id) {
          toast.error(`${connector.name} connection failed: ${event.data.error || 'Unknown error'}`)
          window.removeEventListener('message', handler)
        }
      }
      window.addEventListener('message', handler)
      // Auto-cleanup listener after 5 minutes
      setTimeout(() => window.removeEventListener('message', handler), 300_000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      // Check if it's the config error
      const axiosErr = err as { response?: { data?: { error_type?: string; help?: string } } }
      if (axiosErr?.response?.data?.error_type === 'oauth_not_configured') {
        toast.error(`${connector.name} OAuth not configured. ${axiosErr.response.data.help || 'Set credentials in .env file.'}`)
      } else {
        toast.error(`Failed to start OAuth: ${msg}`)
      }
    }
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
  const [cloudMode, setCloudMode] = useState(false)
  const [apiProviders, setApiProviders] = useState<{provider: string, status: string, display_name: string}[]>([])
  // Track which item is expanded (only one at a time per tab)
  const [expandedItem, setExpandedItem] = useState<string | null>(null)
  // Browse modal (Claude Desktop-style connector/extension marketplace)
  const [browseModal, setBrowseModal] = useState<'connectors' | 'extensions' | null>(null)

  const toggleExpand = (id: string) => setExpandedItem((prev) => prev === id ? null : id)

  const fetchRuntimes = useCallback(async () => {
    try {
      const res = await api.get('/runtimes')
      const data = res.data?.data?.runtimes || []
      setRuntimes(data)
      const persistedPrimary = res.data?.data?.primary_runtime
      if (persistedPrimary) setPrimaryRuntime(persistedPrimary)
      setCloudMode(res.data?.data?.cloud_mode === true)
      setApiProviders(res.data?.data?.api_providers || [])
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
                      {apiProviders.map((ap) => (
                        <div key={ap.provider} className="flex items-center gap-4 px-4 py-3">
                          <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
                            <Globe size={22} className="text-starlight-300" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <span className="text-sm font-medium text-starlight-100">{ap.display_name}</span>
                            <p className="text-xs text-starlight-500">{ap.provider} API</p>
                          </div>
                          <span className="flex items-center gap-1 text-[10px] text-status-success">
                            <CheckCircle2 size={10} />
                            Connected
                          </span>
                        </div>
                      ))}
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
                      onToggleExpand={() => toggleExpand(rt.runtime_id)}
                      onSetPrimary={() => void handleSetPrimary(rt.runtime_id)}
                      onTest={() => void handleTestRuntime(rt.runtime_id)}
                      onRefreshAuth={() => void fetchRuntimes()}
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
                    <p className="text-xs text-starlight-400">
                      {cloudMode
                        ? 'Pre-installed extensions available in cloud mode'
                        : 'Allow Daena to directly interact with apps, data, and tools on your computer'}
                    </p>
                  </div>
                  {!cloudMode && (
                    <button
                      onClick={() => setBrowseModal('extensions')}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer"
                    >
                      <Plus size={12} /> Browse extensions
                    </button>
                  )}
                </div>

                <div>
                  <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold px-4 mb-2">
                    {cloudMode ? 'Pre-installed extensions' : 'Installed on your computer'}
                  </p>
                  <div className="rounded-xl border border-white/5 divide-y divide-white/5">
                    {(cloudMode ? CLOUD_PREINSTALLED_EXTENSIONS : extensions).map((ext) => (
                      <ExtensionRow
                        key={ext.id}
                        ext={ext}
                        expanded={expandedItem === ext.id}
                        onToggleExpand={() => toggleExpand(ext.id)}
                        onToggle={(id, enabled) => {
                          if (cloudMode) {
                            // Cloud mode: toggle is visual-only (no API call needed)
                            toast.success(`${ext.name} ${enabled ? 'enabled' : 'disabled'}`)
                          } else {
                            setExtensions((prev) => prev.map((e) => e.id === id ? { ...e, enabled } : e))
                            toast.success(`${ext.name} ${enabled ? 'enabled' : 'disabled'}`)
                          }
                        }}
                      />
                    ))}
                    {!cloudMode && extensions.length === 0 && !extLoading && (
                      <div className="px-4 py-8 text-center text-xs text-starlight-500">No extensions installed. Install MCP servers to add extensions.</div>
                    )}
                  </div>
                </div>

                {!cloudMode && (
                  <div className="border-2 border-dashed border-white/10 rounded-xl p-6 text-center">
                    <p className="text-xs text-starlight-500">Drag .MCPB or .DXT files here to install</p>
                  </div>
                )}
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
                  <button
                    onClick={() => setBrowseModal('connectors')}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer"
                  >
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
                      fetchInstances={fetchConnectorInstances}
                    />
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* ── Browse Modal (Claude Desktop-style marketplace) ── */}
      <AnimatePresence>
        {browseModal && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
              onClick={() => setBrowseModal(null)}
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
                    {browseModal === 'connectors' ? 'Connectors' : 'Extensions'}
                  </h2>
                  <p className="text-xs text-starlight-400 mt-0.5">
                    {browseModal === 'connectors'
                      ? 'Connect Daena to your apps, files, and services. One click to set up.'
                      : 'Add MCP servers and tools to extend Daena\'s capabilities.'}
                  </p>
                </div>
                <button
                  onClick={() => setBrowseModal(null)}
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
                  {(browseModal === 'connectors' ? BROWSE_CONNECTORS_CATALOG : BROWSE_EXTENSIONS_CATALOG).map((item) => {
                    const isConnected = browseModal === 'connectors'
                      ? !!connectorInstances[item.id]
                      : extensions.some(e => e.name.toLowerCase().includes(item.name.toLowerCase()) && e.enabled)
                    const IconComp = browseModal === 'connectors'
                      ? (CONNECTOR_ICONS[item.id] || (() => <Globe size={24} className="text-starlight-400" />))
                      : (EXTENSION_ICONS[item.id] || (() => <Puzzle size={24} className="text-starlight-400" />))

                    return (
                      <button
                        key={item.id}
                        onClick={() => {
                          if (isConnected) {
                            setBrowseModal(null)
                            setActiveTab(browseModal === 'connectors' ? 'connectors' : 'extensions')
                            setExpandedItem(item.id)
                          } else if (browseModal === 'extensions' && cloudMode) {
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
                          } else if (browseModal === 'extensions' && !cloudMode) {
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
                          } else if (item.authUrl) {
                            // Connectors: open auth URL
                            window.open(item.authUrl, '_blank')
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
                          ) : browseModal === 'extensions' ? (
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
    </div>
  )
}

export default ConnectionsPage
