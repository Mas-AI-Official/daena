/**
 * PluginCardView -- Codex/Claude Desktop-style plugin card.
 *
 * PR-CONN-PLUGIN-PARITY-UX (2026-05-02): visual polish to match
 * Claude Desktop / Codex marketplace cards. Uses the existing brand
 * icon library (lucide + simple-icons via CdnIcon) and the new
 * pluginIcons.tsx registry for catalog-id -> icon resolution.
 *
 * Card content (founder spec):
 *   - icon
 *   - name
 *   - vendor
 *   - one-line description
 *   - status pill
 *   - category
 *   - included skills/capabilities (chips, top 4)
 *   - primary action
 * Backend kind labels stay in tooltip only (never primary text).
 *
 * Clicking the card body opens a detail drawer (PluginDetailDrawer)
 * with full info: capabilities, permissions, env vars (NAMES only),
 * install steps, auth status, probe status, risk, supported OS.
 *
 * Honesty:
 *   - Status pill mirrors V2 truth via PluginCard adapter
 *   - "Connected" only when callable=true
 *   - "Install" never appears -- always "Setup guide" until backend
 *     ships a safe install endpoint
 *   - "Configure" deep-links provider cards to /account/api-keys
 *   - "Connect" opens the OAuth flow drawer (skill-pack: Open the
 *     skill-pack details drawer)
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity, AlertTriangle, BookOpen, ExternalLink, Loader2, Power,
  ShieldAlert, Wrench,
} from 'lucide-react'

import {
  type PluginCard,
  type PluginAction,
  officialityLabel,
  officialityTone,
  pluginStatusTone,
} from './pluginCard'
import MCPInstallDrawer from './MCPInstallDrawer'
import OAuthConnectDrawer from './OAuthConnectDrawer'
import PluginDetailDrawer from './PluginDetailDrawer'
import { pluginIconFor, pluginIconTone } from './pluginIcons'

interface PluginCardViewProps {
  plugin: PluginCard
  /** Probe action -- pass through to V2 probe endpoint when row exists. */
  onProbe?: (rowId: string) => Promise<void>
  /** Enable action -- toggles disabled=false on existing V2 row. */
  onEnable?: (rowId: string) => Promise<void>
  /** Optional click target when action is "open" (skill pack drawer, etc). */
  onOpen?: (plugin: PluginCard) => void
  /** Spinner the action button when busy. */
  busy?: boolean
}

const ACTION_ICON: Record<PluginAction, typeof Activity> = {
  install: Wrench,
  configure: Wrench,
  connect: Power,
  test: Activity,
  open: ExternalLink,
  setup_guide: Wrench,
}

export default function PluginCardView({
  plugin, onProbe, onEnable, onOpen, busy = false,
}: PluginCardViewProps) {
  const tone = pluginStatusTone(plugin.status)
  const navigate = useNavigate()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [installDrawerOpen, setInstallDrawerOpen] = useState(false)
  const [oauthDrawerOpen, setOauthDrawerOpen] = useState(false)

  // PR-CONN-MCP-INSTALL-INTO-CLI: MCP catalog entries with a real
  // command_template open the new install drawer instead of the
  // read-only Setup Guide. Other plugin types keep the existing flow.
  const supportsMcpInstall =
    plugin.source.catalog.kind === 'mcp_server' &&
    plugin.install_method !== 'coming-soon' &&
    plugin.source.catalog.command_template.length > 0

  // PR-CONN-OAUTH-CONNECT: oauth_app entries open the OAuth Connect
  // drawer (which gates on whether the operator has configured the
  // OAuth client_id/secret in Settings -> API Keys). Coming-soon
  // entries fall through to the read-only Setup Guide.
  const supportsOauthConnect =
    plugin.source.catalog.kind === 'oauth_app' &&
    plugin.install_method !== 'coming-soon'

  function handleAction(e: React.MouseEvent) {
    e.stopPropagation()
    switch (plugin.primary_action) {
      case 'install':
        if (supportsMcpInstall) {
          setInstallDrawerOpen(true)
          return
        }
        setDrawerOpen(true)
        return
      case 'connect':
        if (supportsOauthConnect) {
          setOauthDrawerOpen(true)
          return
        }
        setDrawerOpen(true)
        return
      case 'setup_guide':
        if (supportsMcpInstall) {
          setInstallDrawerOpen(true)
          return
        }
        if (supportsOauthConnect) {
          setOauthDrawerOpen(true)
          return
        }
        setDrawerOpen(true)
        return
      case 'configure':
        // PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT (2026-05-03): provider
        // cards (api_provider kind) deep-link to the new Provider Keys
        // section on /account, anchored so the operator lands directly
        // on the input row instead of scrolling past Profile + outbound
        // API keys. Other configures (oauth_app etc) still open the
        // Setup-guide drawer.
        if (plugin.source.catalog.kind === 'api_provider') {
          navigate('/account/api-keys#provider-keys')
          return
        }
        setDrawerOpen(true)
        return
      case 'test':
        if (plugin.v2_row_id && onProbe) void onProbe(plugin.v2_row_id)
        return
      case 'open':
        if (onOpen) onOpen(plugin)
        else setDrawerOpen(true)
        return
      default:
        return
    }
  }

  const ActionIcon = ACTION_ICON[plugin.primary_action]
  const Icon = pluginIconFor(plugin.id, plugin.source.catalog.kind, plugin.name)
  const iconBg = pluginIconTone(plugin.risk_level)

  return (
    <>
      <article
        onClick={() => setDrawerOpen(true)}
        className={`group flex h-full cursor-pointer flex-col gap-3 rounded-xl border bg-midnight-400/40 p-4 transition-all hover:-translate-y-0.5 hover:bg-midnight-400/60 hover:shadow-lg ${tone.border}`}
        title={`${plugin.backing_types.join(' / ')}`}
      >
        <header className="flex items-start gap-3">
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${iconBg}`}>
            <Icon size={22} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-semibold text-starlight-100">
                  {plugin.name}
                </h3>
                <p className="text-[11px] text-starlight-500">
                  {plugin.vendor} · {plugin.category_label}
                </p>
              </div>
              <RiskBadge risk={plugin.risk_level} />
            </div>
          </div>
        </header>

        <p className="line-clamp-2 text-xs text-starlight-300">{plugin.description}</p>

        {plugin.included_skills.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {plugin.included_skills.slice(0, 4).map((cap) => (
              <li
                key={cap}
                className="rounded bg-white/[0.04] px-2 py-0.5 text-[10px] text-starlight-300"
              >
                {cap}
              </li>
            ))}
            {plugin.included_skills.length > 4 && (
              <li className="rounded bg-white/[0.04] px-2 py-0.5 text-[10px] text-starlight-500">
                +{plugin.included_skills.length - 4}
              </li>
            )}
          </ul>
        )}

        <div className="mt-auto space-y-2">
          {/* Status + officiality pill row */}
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${tone.border} ${tone.bg} ${tone.text}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
              {plugin.status_label}
            </span>
            {/* Officiality badge: trust signal from PR-CONN-MCP-CATALOG-SKILL-BUNDLES.
                Always rendered so the operator can distinguish vendor-shipped
                from community-curated entries at a glance. */}
            {(() => {
              const oTone = officialityTone(plugin.officiality)
              const oLabel = officialityLabel(plugin.officiality)
              return (
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${oTone.border} ${oTone.bg} ${oTone.text}`}
                  title={`Source tier: ${oLabel}`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${oTone.dot}`} />
                  {oLabel}
                </span>
              )
            })()}
            {plugin.install_method === 'coming-soon' && plugin.officiality !== 'coming-soon' && (
              <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200">
                coming soon
              </span>
            )}
            {plugin.is_skill_pack && (
              <span
                className="rounded-md bg-violet-500/10 px-1.5 py-0.5 text-[10px] text-violet-200"
                title="Skill pack -- needs a runtime / MCP / app to execute"
              >
                <BookOpen size={9} className="mr-1 inline" />
                skill pack
              </span>
            )}
          </div>

          {/* Failure reason inline */}
          {plugin.status === 'failed' && plugin.failure_reason && (
            <div className="flex items-start gap-1.5 rounded-md border border-rose-500/30 bg-rose-500/5 px-2 py-1 text-[11px] text-rose-200">
              <AlertTriangle size={11} className="mt-0.5 shrink-0" />
              <span className="line-clamp-2">{plugin.failure_reason}</span>
            </div>
          )}

          {/* Action row */}
          <div className="flex items-center justify-between gap-2 pt-1">
            <button
              onClick={(e) => {
                e.stopPropagation()
                setDrawerOpen(true)
              }}
              className="text-[10px] text-starlight-500 hover:text-starlight-300"
            >
              Details
            </button>
            <button
              onClick={handleAction}
              disabled={busy || !plugin.action_enabled}
              className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-[11px] font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
            >
              {busy ? <Loader2 size={11} className="animate-spin" /> : <ActionIcon size={11} />}
              {plugin.primary_action_label}
            </button>
          </div>
        </div>
      </article>

      {drawerOpen && (
        <PluginDetailDrawer
          plugin={plugin}
          onClose={() => setDrawerOpen(false)}
          onProbe={onProbe}
          onEnable={onEnable}
          busy={busy}
        />
      )}

      {installDrawerOpen && (
        <MCPInstallDrawer
          plugin={plugin}
          onClose={() => setInstallDrawerOpen(false)}
          onComplete={() => {
            // After a successful apply, refresh the marketplace card
            // grid so the new V2 row's status pill reflects truth.
            window.dispatchEvent(new Event('daena:retry-pending'))
          }}
        />
      )}

      {oauthDrawerOpen && (
        <OAuthConnectDrawer
          plugin={plugin}
          onClose={() => setOauthDrawerOpen(false)}
          onComplete={() => {
            // Tokens received -- refresh marketplace cards so the new
            // V2 oauth_app row's authenticated state surfaces.
            window.dispatchEvent(new Event('daena:retry-pending'))
          }}
        />
      )}
    </>
  )
}

function RiskBadge({ risk }: { risk: PluginCard['risk_level'] }) {
  const tone =
    risk === 'high'
      ? { text: 'text-rose-300', bg: 'bg-rose-500/10' }
      : risk === 'medium'
        ? { text: 'text-amber-300', bg: 'bg-amber-500/10' }
        : { text: 'text-emerald-300', bg: 'bg-emerald-500/10' }
  return (
    <span
      className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${tone.text} ${tone.bg}`}
      title={`Risk: ${risk}. Asset Shield + governance still gate every call.`}
    >
      {risk === 'high' && <ShieldAlert size={10} className="mr-1 inline" />}
      {risk}
    </span>
  )
}
