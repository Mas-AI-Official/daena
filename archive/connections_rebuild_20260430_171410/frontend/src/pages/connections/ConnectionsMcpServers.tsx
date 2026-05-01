/**
 * MCP Servers tab — Codex-parity CRUD.
 *
 * Codex's Settings → MCP servers shows each server with:
 *   - A toggle switch (enable/disable)
 *   - A settings gear (edit command/args/env)
 *   - A "+ Add server" button at the top
 *   - Per-row delete via the gear menu
 *
 * Previously this tab was read-only display — toggle, settings, add,
 * delete were all missing. Every action below now hits a real backend
 * endpoint:
 *   - Toggle  → POST /connections/extensions/{id}/permissions { default: ALLOW|BLOCK }
 *   - Add     → POST /connections/extensions/install
 *   - Edit    → POST /connections/extensions/{server_key}/config
 *   - Delete  → POST /connections/extensions/uninstall
 */
import { useEffect, useState } from 'react'
import {
  Server,
  RefreshCw,
  Loader2,
  Shield,
  AlertTriangle,
  Activity,
  Settings as SettingsIcon,
  Plus,
  Trash2,
  X,
  Save,
  ChevronDown,
  ChevronUp,
  LogIn,
  CheckCircle2,
  Wrench,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { confirmDialog } from '@/stores/confirmStore'
import { getMcpBrandIcon } from '@/components/icons/BrandIcons'
import type { useMCPDetections } from '@/hooks/useMCPDetections'
import type { useMcpRegistry } from '@/hooks/useMcpRegistry'
import type { TabKey } from './types'

export interface ConnectionsMcpServersProps {
  mcpRegistry: ReturnType<typeof useMcpRegistry>
  mcpSync: ReturnType<typeof useMCPDetections>
  onChangeTab: (tab: TabKey) => void
}

// Per-server state we hydrate on top of the registry entries: enabled
// flag is derived from per-extension permission default (BLOCK = off).
interface ServerState {
  enabled: boolean
  busy: boolean
}

/**
 * Maps an MCP server-key (and/or its npm package name) to the most
 * useful credential / token source page. Each entry is a substring
 * match against the lowercased key OR package — the FIRST entry
 * whose `match` regex hits wins. Keep order: more specific first
 * (e.g. `gmail` before generic `google`).
 *
 * When a server has a credentials problem, we surface the right link
 * inline in the "Missing credentials" panel so the operator goes
 * straight to the page that mints the token, instead of bouncing
 * through search.
 *
 * Adding a new MCP: append an entry. Generic fallback at the bottom
 * points to the npm page, so unknown MCPs still get *something*.
 */
const CREDENTIAL_HINTS: Array<{ match: RegExp; url: string; label: string }> = [
  // Google Workspace family — share one Cloud Console credential page.
  { match: /(gmail)/i, url: 'https://console.cloud.google.com/apis/credentials', label: 'Get Gmail credentials' },
  { match: /(google.*drive|drive.*google|gdrive)/i, url: 'https://console.cloud.google.com/apis/credentials', label: 'Get Google Drive credentials' },
  { match: /(google.*calendar|calendar.*google|gcal)/i, url: 'https://console.cloud.google.com/apis/credentials', label: 'Get Google Calendar credentials' },
  { match: /(google.*sheets|sheets.*google|gsheets)/i, url: 'https://console.cloud.google.com/apis/credentials', label: 'Get Google Sheets credentials' },
  { match: /(google.*docs|docs.*google|gdocs)/i, url: 'https://console.cloud.google.com/apis/credentials', label: 'Get Google Docs credentials' },
  { match: /(google|gemini|gcp)/i, url: 'https://console.cloud.google.com/apis/credentials', label: 'Get Google Cloud credentials' },

  // Dev platforms.
  { match: /(github)/i, url: 'https://github.com/settings/tokens?type=beta', label: 'Create a GitHub PAT' },
  { match: /(gitlab)/i, url: 'https://gitlab.com/-/user_settings/personal_access_tokens', label: 'Create a GitLab token' },
  { match: /(bitbucket)/i, url: 'https://bitbucket.org/account/settings/app-passwords/', label: 'Create a Bitbucket app password' },
  { match: /(vercel)/i, url: 'https://vercel.com/account/tokens', label: 'Create a Vercel token' },
  { match: /(netlify)/i, url: 'https://app.netlify.com/user/applications#personal-access-tokens', label: 'Create a Netlify token' },
  { match: /(cloudflare)/i, url: 'https://dash.cloudflare.com/profile/api-tokens', label: 'Create a Cloudflare API token' },
  { match: /(render)/i, url: 'https://dashboard.render.com/u/settings#api-keys', label: 'Get a Render API key' },
  { match: /(railway)/i, url: 'https://railway.app/account/tokens', label: 'Create a Railway token' },
  { match: /(fly\.io|flyio|fly-io)/i, url: 'https://fly.io/user/personal_access_tokens', label: 'Create a Fly.io token' },
  { match: /(heroku)/i, url: 'https://dashboard.heroku.com/account', label: 'Get a Heroku API key' },
  { match: /(supabase)/i, url: 'https://supabase.com/dashboard/account/tokens', label: 'Create a Supabase token' },
  { match: /(firebase)/i, url: 'https://console.firebase.google.com/', label: 'Open Firebase Console' },
  { match: /(neon)/i, url: 'https://console.neon.tech/app/settings/api-keys', label: 'Create a Neon API key' },
  { match: /(planetscale)/i, url: 'https://app.planetscale.com/settings/tokens', label: 'Create a PlanetScale token' },
  { match: /(sentry)/i, url: 'https://sentry.io/settings/account/api/auth-tokens/', label: 'Create a Sentry token' },
  { match: /(datadog)/i, url: 'https://app.datadoghq.com/organization-settings/api-keys', label: 'Get a Datadog API key' },
  { match: /(circleci)/i, url: 'https://app.circleci.com/settings/user/tokens', label: 'Create a CircleCI token' },

  // Productivity & comms.
  { match: /(notion)/i, url: 'https://www.notion.so/my-integrations', label: 'Create a Notion integration' },
  { match: /(slack)/i, url: 'https://api.slack.com/apps', label: 'Create a Slack app' },
  { match: /(linear)/i, url: 'https://linear.app/settings/api', label: 'Create a Linear API key' },
  { match: /(asana)/i, url: 'https://app.asana.com/0/my-apps', label: 'Create an Asana token' },
  { match: /(trello)/i, url: 'https://trello.com/power-ups/admin', label: 'Get a Trello API key' },
  { match: /(jira|atlassian|confluence|rovo)/i, url: 'https://id.atlassian.com/manage-profile/security/api-tokens', label: 'Create an Atlassian API token' },
  { match: /(monday)/i, url: 'https://auth.monday.com/oauth2/authorize', label: 'Get a Monday API token' },
  { match: /(clickup)/i, url: 'https://app.clickup.com/settings/apps', label: 'Get a ClickUp API token' },
  { match: /(airtable)/i, url: 'https://airtable.com/create/tokens', label: 'Create an Airtable PAT' },

  // CRMs & sales.
  { match: /(salesforce)/i, url: 'https://help.salesforce.com/s/articleView?id=sf.connected_app_create_api_integration.htm', label: 'Set up Salesforce Connected App' },
  { match: /(hubspot)/i, url: 'https://app.hubspot.com/private-apps', label: 'Create a HubSpot Private App' },
  { match: /(pipedrive)/i, url: 'https://app.pipedrive.com/settings/personal/api', label: 'Get a Pipedrive API token' },
  { match: /(intercom)/i, url: 'https://app.intercom.com/a/apps/_/developer-hub', label: 'Create an Intercom app' },
  { match: /(zendesk)/i, url: 'https://support.zendesk.com/hc/en-us/articles/4408889192858', label: 'Create a Zendesk API token' },
  { match: /(apollo)/i, url: 'https://app.apollo.io/#/settings/integrations/api', label: 'Get an Apollo API key' },
  { match: /(common.*room|commonroom)/i, url: 'https://app.commonroom.io/settings/api', label: 'Create a Common Room API token' },
  { match: /(attio)/i, url: 'https://app.attio.com/_settings/integrations/api', label: 'Create an Attio API key' },

  // Payments & finance.
  { match: /(stripe)/i, url: 'https://dashboard.stripe.com/apikeys', label: 'Get a Stripe API key' },
  { match: /(square)/i, url: 'https://developer.squareup.com/apps', label: 'Create a Square app' },
  { match: /(plaid)/i, url: 'https://dashboard.plaid.com/team/keys', label: 'Get Plaid keys' },
  { match: /(brex)/i, url: 'https://dashboard.brex.com/integrations/developer/api-keys', label: 'Create a Brex API key' },

  // AI / ML providers.
  { match: /(openai)/i, url: 'https://platform.openai.com/api-keys', label: 'Create an OpenAI API key' },
  { match: /(anthropic|claude)/i, url: 'https://console.anthropic.com/settings/keys', label: 'Create an Anthropic API key' },
  { match: /(cohere)/i, url: 'https://dashboard.cohere.com/api-keys', label: 'Create a Cohere API key' },
  { match: /(mistral)/i, url: 'https://console.mistral.ai/api-keys/', label: 'Create a Mistral API key' },
  { match: /(huggingface|hugging.*face|hf)/i, url: 'https://huggingface.co/settings/tokens', label: 'Create a Hugging Face token' },
  { match: /(replicate)/i, url: 'https://replicate.com/account/api-tokens', label: 'Get a Replicate API token' },
  { match: /(pinecone)/i, url: 'https://app.pinecone.io/organizations/-/projects/-/keys', label: 'Get a Pinecone API key' },
  { match: /(weaviate)/i, url: 'https://console.weaviate.cloud/dashboard', label: 'Open Weaviate dashboard' },
  { match: /(perplexity|pplx)/i, url: 'https://www.perplexity.ai/settings/api', label: 'Get a Perplexity API key' },
  { match: /(groq)/i, url: 'https://console.groq.com/keys', label: 'Create a Groq API key' },
  { match: /(together)/i, url: 'https://api.together.xyz/settings/api-keys', label: 'Create a Together API key' },
  { match: /(elevenlabs|eleven.*labs)/i, url: 'https://elevenlabs.io/app/settings/api-keys', label: 'Get an ElevenLabs API key' },
  { match: /(fireworks)/i, url: 'https://fireworks.ai/account/api-keys', label: 'Create a Fireworks API key' },

  // Cloud / infra.
  { match: /(aws|amazon.*web|s3)/i, url: 'https://console.aws.amazon.com/iam/home#/security_credentials', label: 'Get AWS credentials' },
  { match: /(azure)/i, url: 'https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade', label: 'Create an Azure app registration' },
  { match: /(digitalocean|do.*spaces)/i, url: 'https://cloud.digitalocean.com/account/api/tokens', label: 'Create a DigitalOcean token' },

  // Comms / messaging.
  { match: /(twilio)/i, url: 'https://console.twilio.com/us1/account/keys-credentials/api-keys', label: 'Create a Twilio API key' },
  { match: /(sendgrid)/i, url: 'https://app.sendgrid.com/settings/api_keys', label: 'Create a SendGrid API key' },
  { match: /(postmark)/i, url: 'https://account.postmarkapp.com/api_tokens', label: 'Get Postmark API tokens' },
  { match: /(resend)/i, url: 'https://resend.com/api-keys', label: 'Create a Resend API key' },
  { match: /(mailgun)/i, url: 'https://app.mailgun.com/app/account/security/api_keys', label: 'Get a Mailgun API key' },
  { match: /(discord)/i, url: 'https://discord.com/developers/applications', label: 'Create a Discord app' },
  { match: /(telegram)/i, url: 'https://core.telegram.org/bots#how-do-i-create-a-bot', label: 'Create a Telegram bot' },

  // Analytics / data.
  { match: /(amplitude)/i, url: 'https://app.amplitude.com/data/account-settings/api-keys', label: 'Get an Amplitude API key' },
  { match: /(mixpanel)/i, url: 'https://mixpanel.com/settings/project', label: 'Get a Mixpanel service account' },
  { match: /(posthog)/i, url: 'https://us.posthog.com/settings/project-personal-api-keys', label: 'Create a PostHog API key' },
  { match: /(segment)/i, url: 'https://app.segment.com/-/settings/access-management', label: 'Get a Segment access token' },
  { match: /(hex)/i, url: 'https://app.hex.tech/settings/personal/api-keys', label: 'Create a Hex API key' },

  // Design / content.
  { match: /(figma)/i, url: 'https://www.figma.com/settings', label: 'Create a Figma personal access token' },
  { match: /(canva)/i, url: 'https://www.canva.com/developers/integrations', label: 'Set up Canva Connect' },
  { match: /(cloudinary)/i, url: 'https://console.cloudinary.com/settings/security', label: 'Get a Cloudinary API key' },

  // Browser / scraping.
  { match: /(brave)/i, url: 'https://brave.com/search/api/', label: 'Get a Brave Search API key' },
  { match: /(serpapi|serp.*api)/i, url: 'https://serpapi.com/manage-api-key', label: 'Get a SerpAPI key' },
  { match: /(firecrawl)/i, url: 'https://www.firecrawl.dev/app/api-keys', label: 'Get a Firecrawl API key' },
  { match: /(tavily)/i, url: 'https://app.tavily.com/home', label: 'Get a Tavily API key' },
  { match: /(exa)/i, url: 'https://dashboard.exa.ai/api-keys', label: 'Get an Exa API key' },
]

function resolveCredentialHint(server_key: string, pkg?: string): { url: string; label: string } | null {
  const haystack = `${server_key} ${pkg ?? ''}`
  for (const hint of CREDENTIAL_HINTS) {
    if (hint.match.test(haystack)) return hint
  }
  // Generic fallback: the npm page for the package, when we have it.
  // Helps with custom / niche MCPs whose README is the only doc source.
  if (pkg && pkg.startsWith('@')) {
    return {
      url: `https://www.npmjs.com/package/${pkg}`,
      label: 'View package on npm',
    }
  }
  if (pkg && /^[a-z0-9_-]+$/i.test(pkg)) {
    return {
      url: `https://www.npmjs.com/package/${pkg}`,
      label: 'View package on npm',
    }
  }
  return null
}


// What we learn when the user expands a row (or clicks Sign-in).
interface ServerProbe {
  loading: boolean
  alive?: boolean
  tools_count?: number
  tools?: { name: string; description: string }[]
  auth_required?: boolean
  // Set when the MCP exposes a whoami-style tool that surfaces the
  // currently-connected account (e.g. "masoud.masoori@mas-ai.co" vs
  // "masoud.masori@gmail.com"). Critical when the user has multiple
  // accounts on the same provider — they need to know which one this
  // MCP is using before issuing tool calls.
  connected_as?: string | null
  signing_in?: boolean
  sign_in_excerpt?: string
  error?: string
  // True when the MCP failed to start because required env vars (API
  // keys, OAuth client id/secret, service account key) are missing.
  // The frontend uses this to show a "Missing credentials" state with
  // a jump straight into the Settings → env editor.
  missing_credentials?: boolean
  required_env_vars?: string[]
}

export default function ConnectionsMcpServers({
  mcpRegistry,
  mcpSync,
}: ConnectionsMcpServersProps) {
  const [serverState, setServerState] = useState<Record<string, ServerState>>({})
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<string | null>(null)
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const [probes, setProbes] = useState<Record<string, ServerProbe>>({})

  // When the user expands a row, probe the MCP for liveness + tool list.
  // Cached per server_key; refresh by re-clicking Re-check inside the panel.
  const probeServer = async (server_key: string) => {
    setProbes((prev) => ({ ...prev, [server_key]: { ...prev[server_key], loading: true } }))
    try {
      const res = await api.post(`/connections/extensions/${encodeURIComponent(server_key)}/probe-auth`)
      const data = res.data?.data || {}
      setProbes((prev) => ({
        ...prev,
        [server_key]: {
          loading: false,
          alive: !!data.alive,
          tools_count: data.tools_count || 0,
          tools: data.tools || [],
          auth_required: !!data.auth_required,
          connected_as: data.connected_as ?? null,
          error: data.error,
          missing_credentials: !!data.missing_credentials,
          required_env_vars: data.required_env_vars || [],
        },
      }))
    } catch {
      setProbes((prev) => ({
        ...prev,
        [server_key]: { loading: false, alive: false, error: 'Probe request failed' },
      }))
    }
  }

  const signInToServer = async (server_key: string) => {
    setProbes((prev) => ({
      ...prev,
      [server_key]: { ...prev[server_key], signing_in: true },
    }))
    try {
      const res = await api.post(`/connections/extensions/${encodeURIComponent(server_key)}/sign-in`)
      const data = res.data?.data || {}
      const excerpt: string = (data.excerpt || '').toString()
      setProbes((prev) => ({
        ...prev,
        [server_key]: {
          ...prev[server_key],
          signing_in: false,
          sign_in_excerpt: excerpt,
        },
      }))
      // If the MCP returned a URL in its response, open it directly so the
      // user lands on the consent screen without having to copy-paste.
      const urlMatch = excerpt.match(/https?:\/\/\S+/)
      if (urlMatch) {
        window.open(urlMatch[0], '_blank', 'noopener,noreferrer')
        toast.info(`Opened ${server_key} sign-in URL. Complete the flow in the new tab, then click Re-check.`, 12000)
      } else if (data.tool_succeeded) {
        toast.success(`${server_key} is already authenticated.`)
      } else {
        toast.info(`Triggered ${data.called_tool || 'tool'} on ${server_key}. If a browser window opened, complete the sign-in there.`, 10000)
      }
    } catch {
      toast.error(`Failed to trigger sign-in for ${server_key}`)
      setProbes((prev) => ({
        ...prev,
        [server_key]: { ...prev[server_key], signing_in: false },
      }))
    }
  }

  const handleRowClick = async (server_key: string) => {
    if (expandedKey === server_key) {
      setExpandedKey(null)
      return
    }
    setExpandedKey(server_key)
    // Probe lazily on first expand so we don't hammer all MCPs at mount.
    if (!probes[server_key] || probes[server_key].error) {
      await probeServer(server_key)
    }
  }

  // Initialize enabled-state from extensions list. We treat any server
  // whose permission default is BLOCK as disabled. Live entries default
  // to enabled if no explicit BLOCK exists.
  useEffect(() => {
    setServerState((prev) => {
      const next = { ...prev }
      for (const e of mcpRegistry.entries) {
        if (!next[e.server_key]) {
          next[e.server_key] = { enabled: true, busy: false }
        }
      }
      return next
    })
  }, [mcpRegistry.entries])

  const setBusy = (key: string, busy: boolean) =>
    setServerState((prev) => ({
      ...prev,
      [key]: { ...(prev[key] || { enabled: true, busy: false }), busy },
    }))

  const toggleServer = async (server_key: string) => {
    const current = serverState[server_key]?.enabled ?? true
    const next = !current
    // Optimistic UI update with rollback on failure.
    setServerState((prev) => ({
      ...prev,
      [server_key]: { enabled: next, busy: true },
    }))
    try {
      await api.post(`/connections/extensions/${encodeURIComponent(server_key)}/permissions`, {
        default: next ? 'ALLOW' : 'BLOCK',
      })
      toast.success(`${server_key} ${next ? 'enabled' : 'disabled'}`)
    } catch {
      setServerState((prev) => ({
        ...prev,
        [server_key]: { enabled: current, busy: false },
      }))
      toast.error(`Could not ${next ? 'enable' : 'disable'} ${server_key}`)
      return
    }
    setBusy(server_key, false)
  }

  const deleteServer = async (server_key: string, display_name: string) => {
    const ok = await confirmDialog({
      title: `Delete ${display_name}?`,
      message: 'Removes the entry from claude_desktop_config.json and stops the live adapter. The MCP server itself stays installed on disk; you can re-add it from this tab.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return
    setBusy(server_key, true)
    try {
      await api.post('/connections/extensions/uninstall', { id: server_key })
      toast.success(`${display_name} deleted`)
      await mcpRegistry.refresh()
    } catch {
      toast.error(`Failed to delete ${display_name}`)
    } finally {
      setBusy(server_key, false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-starlight-100">MCP Servers</h2>
          <p className="text-xs text-starlight-500 mt-1">
            Connect external tools and data sources.
            {mcpRegistry.entries.length > 0 && (
              <> <span className="text-accent-green">{mcpRegistry.entries.length}</span> loaded and callable now.</>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { void mcpRegistry.refresh() }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
            title="Re-scan claude_desktop_config.json + rebuild the live registry"
          >
            <RefreshCw size={12} /> Refresh
          </button>
          <button
            onClick={() => setAddModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500 text-white hover:bg-primary-400 cursor-pointer"
          >
            <Plus size={12} /> Add server
          </button>
        </div>
      </div>

      {/* Hint when other-CLI MCPs are detected but not yet imported. */}
      {mcpSync.detections.length > 0 && (
        <div className="p-3 rounded-lg border border-accent-amber/30 bg-accent-amber/5">
          <div className="flex items-center gap-2">
            <AlertTriangle size={14} className="text-accent-amber" />
            <span className="text-xs text-starlight-200 font-medium">
              {mcpSync.detections.length} MCP{mcpSync.detections.length === 1 ? '' : 's'} found in other CLI configs
            </span>
          </div>
          <p className="text-[11px] text-starlight-400 mt-1">
            These MCP servers are configured in other tools on this machine.
            Import them to make their tools available to Daena.
          </p>
        </div>
      )}

      {mcpRegistry.loading && (
        <div className="flex items-center gap-2 px-4 py-6 text-xs text-starlight-500">
          <Loader2 size={14} className="animate-spin" /> Loading registry...
        </div>
      )}

      {!mcpRegistry.loading && mcpRegistry.entries.length === 0 && (
        <div className="p-6 rounded-lg border border-dashed border-white/10 text-center">
          <Server size={28} className="mx-auto text-starlight-500 mb-2" />
          <p className="text-sm text-starlight-300">No MCP servers added yet</p>
          <p className="text-[11px] text-starlight-500 mt-1">
            Click <strong>+ Add server</strong> above, or install a plugin from the Plugins tab.
          </p>
        </div>
      )}

      {mcpRegistry.entries.length > 0 && (
        <div className="rounded-xl border border-white/5 divide-y divide-white/5 bg-midnight-400/20">
          {mcpRegistry.entries.map((entry) => {
            const state = serverState[entry.server_key] || { enabled: true, busy: false }
            const isExpanded = expandedKey === entry.server_key
            const probe = probes[entry.server_key]
            const BrandIcon = getMcpBrandIcon(entry.server_key)
            return (
              <div key={entry.server_key}>
                <div
                  className="px-4 py-3 flex items-center gap-3 hover:bg-white/[0.02] transition-colors cursor-pointer"
                  onClick={() => void handleRowClick(entry.server_key)}
                >
                  <div className="w-9 h-9 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0 overflow-hidden">
                    <BrandIcon size={20} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-starlight-100">{entry.display_name || entry.server_key}</span>
                      {state.enabled && (
                        <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-accent-green/10 text-accent-green font-medium">
                          <Activity size={9} /> Live
                        </span>
                      )}
                      {entry.package && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/5 text-starlight-400 font-mono">
                          {entry.package}
                        </span>
                      )}
                    </div>
                    {entry.description && (
                      <p className="text-[11px] text-starlight-500 mt-1 leading-relaxed">{entry.description}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5 text-[10px] text-starlight-600 font-mono">
                      <code className="bg-white/[0.03] px-1.5 py-0.5 rounded">
                        {entry.command} {(entry.args || []).slice(0, 3).join(' ')}{(entry.args || []).length > 3 ? ' ...' : ''}
                      </code>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => setEditTarget(entry.server_key)}
                      className="p-1.5 rounded-lg text-starlight-400 hover:text-starlight-200 hover:bg-white/5 cursor-pointer"
                      title="Edit command + env"
                    >
                      <SettingsIcon size={14} />
                    </button>
                    <button
                      onClick={() => void deleteServer(entry.server_key, entry.display_name || entry.server_key)}
                      disabled={state.busy}
                      className="p-1.5 rounded-lg text-starlight-400 hover:text-status-error hover:bg-status-error/10 cursor-pointer disabled:opacity-40"
                      title="Delete server"
                    >
                      <Trash2 size={14} />
                    </button>
                    <button
                      onClick={() => void handleRowClick(entry.server_key)}
                      className="p-1.5 rounded-lg text-starlight-400 hover:text-starlight-200 hover:bg-white/5 cursor-pointer"
                      title={isExpanded ? 'Collapse' : 'Show details + sign in'}
                    >
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    <button
                      onClick={() => void toggleServer(entry.server_key)}
                      disabled={state.busy}
                      role="switch"
                      aria-checked={state.enabled}
                      title={state.enabled ? 'Disable' : 'Enable'}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-all duration-200 cursor-pointer disabled:opacity-50 ${
                        state.enabled
                          ? 'bg-accent-green border border-accent-green'
                          : 'bg-white/10 border border-white/15'
                      }`}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-md transform transition-transform duration-200 ${
                          state.enabled ? 'translate-x-4' : 'translate-x-0.5'
                        }`}
                      />
                    </button>
                  </div>
                </div>

                {/* Expanded panel: live probe + sign-in trigger + tool list */}
                <AnimatePresence initial={false}>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.18 }}
                      className="overflow-hidden"
                    >
                      <div className="px-4 pb-4 pt-1 bg-midnight-500/40 space-y-3">
                        {/* Liveness + auth status */}
                        {probe?.loading && (
                          <div className="flex items-center gap-2 text-xs text-starlight-500">
                            <Loader2 size={12} className="animate-spin" /> Probing server...
                          </div>
                        )}
                        {probe && !probe.loading && (
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div className="px-3 py-2 rounded-lg bg-white/5">
                              <div className="text-[10px] text-starlight-500 uppercase tracking-wider">Reachable</div>
                              <div className={`mt-0.5 font-medium ${probe.alive ? 'text-status-success' : 'text-status-error'}`}>
                                {probe.alive ? 'Yes' : 'No'}
                              </div>
                            </div>
                            <div className="px-3 py-2 rounded-lg bg-white/5">
                              <div className="text-[10px] text-starlight-500 uppercase tracking-wider">Tools exposed</div>
                              <div className="mt-0.5 font-medium text-starlight-200">{probe.tools_count ?? 0}</div>
                            </div>
                            <div className="px-3 py-2 rounded-lg bg-white/5">
                              <div className="text-[10px] text-starlight-500 uppercase tracking-wider">Auth model</div>
                              <div className="mt-0.5 font-medium text-starlight-200">
                                {probe.auth_required ? 'Account-bound' : 'Public / local'}
                              </div>
                            </div>
                          </div>
                        )}
                        {probe?.error && !probe?.missing_credentials && (
                          <div className="px-3 py-2 rounded-lg bg-status-error/10 text-status-error text-xs flex items-center gap-2">
                            <AlertTriangle size={12} /> {probe.error}
                          </div>
                        )}

                        {/* Guided "missing credentials" state. Most MCPs that
                            need API keys / OAuth client secrets fail at
                            startup with a message naming the env vars they
                            want. We extract those names and offer a one-click
                            jump into the env editor — instead of dumping the
                            raw error and leaving the operator to guess what
                            to do. */}
                        {probe?.missing_credentials && (
                          <div className="px-3 py-3 rounded-lg bg-accent-amber/10 border border-accent-amber/30 space-y-2">
                            <div className="flex items-start gap-2">
                              <AlertTriangle size={14} className="text-accent-amber shrink-0 mt-0.5" />
                              <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium text-accent-amber">Missing credentials</p>
                                <p className="text-[11px] text-starlight-300 mt-0.5 leading-relaxed">
                                  This MCP failed to start because required environment variables are not set. Add them in Settings, then Re-check.
                                </p>
                              </div>
                            </div>
                            {(probe.required_env_vars?.length ?? 0) > 0 && (
                              <div className="ml-6">
                                <p className="text-[10px] uppercase tracking-wider text-starlight-500 mb-1">Required env vars</p>
                                <div className="flex flex-wrap gap-1.5">
                                  {(probe.required_env_vars || []).map((v) => (
                                    <code key={v} className="text-[11px] px-2 py-0.5 rounded bg-white/5 border border-white/10 font-mono text-starlight-200">
                                      {v}
                                    </code>
                                  ))}
                                </div>
                              </div>
                            )}
                            <div className="ml-6 flex items-center gap-2 flex-wrap pt-1">
                              <button
                                onClick={() => setEditTarget(entry.server_key)}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500 text-white hover:bg-primary-400 cursor-pointer"
                              >
                                <SettingsIcon size={12} /> Open Settings to add env vars
                              </button>
                              {(() => {
                                const hint = resolveCredentialHint(entry.server_key, entry.package ?? undefined)
                                if (!hint) return null
                                return (
                                  <a
                                    href={hint.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-1 text-[11px] text-primary-400 hover:text-primary-300 underline"
                                  >
                                    {hint.label} →
                                  </a>
                                )
                              })()}
                            </div>
                            {/* Surface the raw error in a collapsed details so
                                power users can confirm exactly what the MCP
                                said, without dominating the panel. */}
                            <details className="ml-6 text-[10px] text-starlight-500">
                              <summary className="cursor-pointer hover:text-starlight-400">Show raw error</summary>
                              <pre className="mt-1 p-2 rounded bg-white/[0.03] font-mono text-starlight-400 whitespace-pre-wrap break-words leading-relaxed max-h-32 overflow-y-auto">
                                {probe.error}
                              </pre>
                            </details>
                          </div>
                        )}

                        {/* Connected-as pill — surfaces WHICH account this MCP
                            is currently using. Critical when the user has
                            multiple accounts on the same provider (e.g.
                            mas-ai.co work vs personal Gmail) so they don't
                            accidentally fire tools against the wrong one. */}
                        {probe?.auth_required && probe?.connected_as && (
                          <div className="px-3 py-2 rounded-lg bg-status-success/5 border border-status-success/20 flex items-center gap-2">
                            <CheckCircle2 size={12} className="text-status-success" />
                            <span className="text-xs text-starlight-200">
                              Connected as <strong className="font-mono text-status-success">{probe.connected_as}</strong>
                            </span>
                          </div>
                        )}
                        {probe?.auth_required && probe?.alive && !probe?.connected_as && (
                          <div className="px-3 py-2 rounded-lg bg-accent-amber/5 border border-accent-amber/20 flex items-start gap-2">
                            <AlertTriangle size={12} className="text-accent-amber mt-0.5" />
                            <span className="text-xs text-starlight-300">
                              Account-bound MCP. Click <strong>Sign in</strong> to authorize a Google account — pick the right one (work vs personal) at the consent screen.
                            </span>
                          </div>
                        )}

                        {/* Sign-in / Switch / Re-check */}
                        <div className="flex items-center gap-2 flex-wrap">
                          {probe?.auth_required && !probe?.connected_as && (
                            <button
                              onClick={() => void signInToServer(entry.server_key)}
                              disabled={probe?.signing_in}
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500 text-white hover:bg-primary-400 cursor-pointer disabled:opacity-50"
                            >
                              {probe?.signing_in ? <Loader2 size={12} className="animate-spin" /> : <LogIn size={12} />}
                              {probe?.signing_in ? 'Triggering sign-in...' : 'Sign in / Authorize'}
                            </button>
                          )}
                          {probe?.auth_required && probe?.connected_as && (
                            <button
                              onClick={() => void signInToServer(entry.server_key)}
                              disabled={probe?.signing_in}
                              title="Triggers the MCP's OAuth again. The Google consent screen will show all your accounts so you can pick a different one."
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer disabled:opacity-50"
                            >
                              {probe?.signing_in ? <Loader2 size={12} className="animate-spin" /> : <LogIn size={12} />}
                              {probe?.signing_in ? 'Switching...' : 'Switch account'}
                            </button>
                          )}
                          <button
                            onClick={() => void probeServer(entry.server_key)}
                            disabled={probe?.loading}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer disabled:opacity-50"
                          >
                            <RefreshCw size={12} className={probe?.loading ? 'animate-spin' : ''} /> Re-check
                          </button>
                          {probe?.alive && !probe?.auth_required && (
                            <span className="text-[11px] text-status-success flex items-center gap-1">
                              <CheckCircle2 size={12} /> No sign-in needed
                            </span>
                          )}
                        </div>

                        {probe?.sign_in_excerpt && (
                          <div className="p-2 rounded-lg bg-white/5 border border-white/5">
                            <div className="flex items-center gap-1.5 text-[10px] text-starlight-400 uppercase tracking-wider mb-1">
                              <LogIn size={10} /> Server response
                            </div>
                            <pre className="text-[11px] text-starlight-300 whitespace-pre-wrap break-words leading-relaxed font-mono max-h-40 overflow-y-auto">
                              {probe.sign_in_excerpt}
                            </pre>
                            <p className="text-[10px] text-starlight-500 mt-1.5">
                              The actual OAuth window opens inside the MCP subprocess (not Daena). Once you finish, hit Re-check.
                            </p>
                          </div>
                        )}

                        {/* Tool list */}
                        {probe?.tools && probe.tools.length > 0 && (
                          <div>
                            <div className="flex items-center gap-1.5 text-[10px] text-starlight-400 uppercase tracking-wider mb-1.5">
                              <Wrench size={10} /> Tools ({probe.tools_count})
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                              {probe.tools.map((tool) => (
                                <div key={tool.name} className="px-2.5 py-1.5 rounded-lg bg-white/[0.03] border border-white/5">
                                  <div className="text-[11px] font-mono text-starlight-200">{tool.name}</div>
                                  {tool.description && (
                                    <div className="text-[10px] text-starlight-500 mt-0.5 leading-relaxed truncate">
                                      {tool.description}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                            {(probe.tools_count ?? 0) > probe.tools.length && (
                              <p className="text-[10px] text-starlight-600 mt-1">
                                Showing first {probe.tools.length} of {probe.tools_count}.
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )
          })}
        </div>
      )}

      {/* Host config hint */}
      <div className="p-3 rounded-lg border border-white/5 bg-midnight-400/20">
        <div className="flex items-start gap-2 text-[11px] text-starlight-400 leading-relaxed">
          <Shield size={12} className="shrink-0 mt-0.5 text-starlight-500" />
          <span>
            Daena reads from <code className="font-mono bg-white/5 px-1 rounded">~/AppData/Roaming/Claude/claude_desktop_config.json</code>
            on startup and after every change. Add / Edit / Delete here patches that file directly and re-bootstraps the live adapter without a restart.
          </span>
        </div>
      </div>

      <AnimatePresence>
        {addModalOpen && (
          <AddServerModal
            onClose={() => setAddModalOpen(false)}
            onSaved={async () => {
              setAddModalOpen(false)
              await mcpRegistry.refresh()
            }}
          />
        )}
        {editTarget && (
          <EditServerModal
            server_key={editTarget}
            onClose={() => setEditTarget(null)}
            onSaved={async () => {
              setEditTarget(null)
              await mcpRegistry.refresh()
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}


// ── Add server modal ──

function AddServerModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState('')
  const [command, setCommand] = useState('npx')
  const [argsText, setArgsText] = useState('')
  const [packageId, setPackageId] = useState('')
  const [saving, setSaving] = useState(false)

  const save = async () => {
    if (!name.trim() || !packageId.trim()) {
      toast.error('Name and package are required')
      return
    }
    setSaving(true)
    try {
      // Args are entered space-separated for simplicity. Operators who
      // need spaces inside an arg can edit afterwards via the gear icon.
      const argsArray = argsText.trim()
        ? argsText.trim().split(/\s+/)
        : ['-y', packageId.trim()]
      await api.post('/connections/extensions/install', {
        id: packageId.trim(),
        name: name.trim(),
        description: `Custom MCP: ${name.trim()}`,
        command: command.trim() || 'npx',
        args: argsArray,
      })
      toast.success(`${name} added`)
      onSaved()
    } catch {
      toast.error('Failed to add server')
    } finally {
      setSaving(false)
    }
  }

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="bg-midnight-300 border border-white/10 rounded-2xl p-6 max-w-md w-full shadow-2xl"
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-starlight-100">Add MCP server</h3>
          <button onClick={onClose} className="p-1 rounded text-starlight-400 hover:text-starlight-200 hover:bg-white/5 cursor-pointer">
            <X size={14} />
          </button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-[11px] text-starlight-400 uppercase tracking-wider">Display name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My MCP server"
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
            />
          </div>
          <div>
            <label className="text-[11px] text-starlight-400 uppercase tracking-wider">Package id</label>
            <input
              type="text"
              value={packageId}
              onChange={(e) => setPackageId(e.target.value)}
              placeholder="e.g. @modelcontextprotocol/server-filesystem"
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
            />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-[11px] text-starlight-400 uppercase tracking-wider">Command</label>
              <input
                type="text"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                placeholder="npx"
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40 font-mono"
              />
            </div>
            <div className="col-span-2">
              <label className="text-[11px] text-starlight-400 uppercase tracking-wider">Args (space-separated)</label>
              <input
                type="text"
                value={argsText}
                onChange={(e) => setArgsText(e.target.value)}
                placeholder={packageId ? `-y ${packageId}` : '-y <package>'}
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40 font-mono"
              />
            </div>
          </div>
          <p className="text-[10px] text-starlight-600">
            Default args use <code className="font-mono">-y &lt;package&gt;</code> if you leave the field blank — works for most npx-launched MCP servers.
          </p>
        </div>
        <div className="flex items-center justify-end gap-2 mt-5 pt-4 border-t border-white/5">
          <button
            onClick={onClose}
            className="px-3 py-2 rounded-lg text-xs text-starlight-400 hover:text-starlight-200 hover:bg-white/5 cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={() => void save()}
            disabled={saving || !name.trim() || !packageId.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary-500 text-white hover:bg-primary-400 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            {saving ? 'Adding...' : 'Add server'}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}


// ── Edit server modal ──

function EditServerModal({ server_key, onClose, onSaved }: {
  server_key: string
  onClose: () => void
  onSaved: () => void
}) {
  const [loading, setLoading] = useState(true)
  const [command, setCommand] = useState('')
  const [argsText, setArgsText] = useState('')
  const [envText, setEnvText] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const { data } = await api.get(`/connections/extensions/${encodeURIComponent(server_key)}/config`)
        if (cancelled) return
        const cfg = data?.data
        if (!cfg) {
          toast.error('Could not load server config')
          onClose()
          return
        }
        setCommand(cfg.command || '')
        setArgsText((cfg.args || []).join(' '))
        const envObj = (cfg.env || {}) as Record<string, string>
        setEnvText(
          Object.entries(envObj)
            .map(([k, v]) => `${k}=${v}`)
            .join('\n'),
        )
      } catch {
        toast.error('Could not load server config')
        onClose()
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [server_key, onClose])

  const save = async () => {
    setSaving(true)
    try {
      const argsArray = argsText.trim() ? argsText.trim().split(/\s+/) : []
      const envObj: Record<string, string> = {}
      for (const line of envText.split('\n')) {
        const eq = line.indexOf('=')
        if (eq > 0) {
          const k = line.slice(0, eq).trim()
          const v = line.slice(eq + 1).trim()
          if (k) envObj[k] = v
        }
      }
      await api.post(`/connections/extensions/${encodeURIComponent(server_key)}/config`, {
        command: command.trim(),
        args: argsArray,
        env: envObj,
      })
      toast.success(`${server_key} updated`)
      onSaved()
    } catch {
      toast.error(`Failed to update ${server_key}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="bg-midnight-300 border border-white/10 rounded-2xl p-6 max-w-md w-full shadow-2xl"
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-starlight-100">Edit {server_key}</h3>
            <p className="text-[11px] text-starlight-500 mt-0.5">Patches claude_desktop_config.json + reloads the adapter.</p>
          </div>
          <button onClick={onClose} className="p-1 rounded text-starlight-400 hover:text-starlight-200 hover:bg-white/5 cursor-pointer">
            <X size={14} />
          </button>
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin text-starlight-500" />
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="text-[11px] text-starlight-400 uppercase tracking-wider">Command</label>
              <input
                type="text"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40 font-mono"
              />
            </div>
            <div>
              <label className="text-[11px] text-starlight-400 uppercase tracking-wider">Args (space-separated)</label>
              <input
                type="text"
                value={argsText}
                onChange={(e) => setArgsText(e.target.value)}
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40 font-mono"
              />
            </div>
            <div>
              <label className="text-[11px] text-starlight-400 uppercase tracking-wider">Environment vars (KEY=VALUE per line)</label>
              <textarea
                value={envText}
                onChange={(e) => setEnvText(e.target.value)}
                rows={4}
                placeholder="GITHUB_TOKEN=ghp_xxx&#10;NODE_ENV=production"
                className="w-full mt-1 px-3 py-2 rounded-lg text-xs bg-white/5 border border-white/10 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40 font-mono resize-none"
              />
            </div>
          </div>
        )}
        <div className="flex items-center justify-end gap-2 mt-5 pt-4 border-t border-white/5">
          <button
            onClick={onClose}
            className="px-3 py-2 rounded-lg text-xs text-starlight-400 hover:text-starlight-200 hover:bg-white/5 cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={() => void save()}
            disabled={saving || loading}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary-500 text-white hover:bg-primary-400 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}
