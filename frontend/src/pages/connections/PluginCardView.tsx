/**
 * PluginCardView -- Codex-style plugin card.
 *
 * Renders one PluginCard view-model (from pluginCard.ts) with:
 *   - kind icon + name + vendor
 *   - status pill (Available / Installed / Needs auth / Connected / Failed / Not supported on this OS)
 *   - included skills/capabilities (chips)
 *   - required env var NAMES only (never values)
 *   - failure reason inline when status=failed
 *   - skill-pack caption when entry is a skill pack
 *   - one primary action button matching founder vocabulary
 *
 * Honesty:
 *   - "Connected" pill only shows when V2 truth says callable=true
 *   - "Install" never appears unless the backend can safely write
 *     install config; today every install path surfaces as "Setup guide"
 *   - "Setup guide" opens a modal with step-by-step instructions; Daena
 *     does NOT execute any commands automatically
 */

import { useState } from 'react'
import {
  Activity, AlertTriangle, BookOpen, ExternalLink, Loader2, Power,
  ShieldAlert, Wrench, X,
} from 'lucide-react'

import {
  type InstallPlan,
  fetchInstallPlan,
} from '@/hooks/useMarketplace'
import {
  type PluginCard,
  type PluginAction,
  pluginStatusTone,
} from './pluginCard'

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

export default function PluginCardView({
  plugin, onProbe, onEnable, onOpen, busy = false,
}: PluginCardViewProps) {
  const tone = pluginStatusTone(plugin.status)
  const [setupOpen, setSetupOpen] = useState(false)
  const [setupBusy, setSetupBusy] = useState(false)
  const [installPlan, setInstallPlan] = useState<InstallPlan | null>(null)
  const [setupError, setSetupError] = useState<string | null>(null)

  async function openSetup() {
    setSetupOpen(true)
    if (installPlan) return
    setSetupBusy(true)
    setSetupError(null)
    const res = await fetchInstallPlan(plugin.id)
    setSetupBusy(false)
    if (res.ok && res.plan) {
      setInstallPlan(res.plan)
    } else {
      setSetupError(res.error ?? 'Failed to load install plan')
    }
  }

  function handleAction() {
    switch (plugin.primary_action) {
      case 'install':
      case 'configure':
      case 'connect':
      case 'setup_guide':
        void openSetup()
        return
      case 'test':
        if (plugin.v2_row_id && onProbe) void onProbe(plugin.v2_row_id)
        return
      case 'open':
        if (onOpen) onOpen(plugin)
        else void openSetup()
        return
      default:
        return
    }
  }

  const ActionIcon = ACTION_ICON[plugin.primary_action]

  return (
    <>
      <article
        className={`flex h-full flex-col gap-3 rounded-xl border bg-midnight-400/40 p-4 transition-colors hover:border-white/10 ${tone.border}`}
      >
        <header className="flex items-start gap-3">
          <PluginIcon plugin={plugin} />
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

        <p className="text-xs text-starlight-300">{plugin.description}</p>

        {plugin.included_skills.length > 0 && (
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wider text-starlight-500">
              Included
            </p>
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
                  +{plugin.included_skills.length - 4} more
                </li>
              )}
            </ul>
          </div>
        )}

        <div className="mt-auto space-y-2">
          {/* Status pill + auth requirement chip */}
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${tone.border} ${tone.bg} ${tone.text}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
              {plugin.status_label}
            </span>
            {plugin.auth_type !== 'none' && (
              <span
                className="rounded-md bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-starlight-400"
                title={`Auth: ${plugin.auth_type}`}
              >
                {plugin.auth_type}
              </span>
            )}
            {plugin.install_method === 'coming-soon' && (
              <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200">
                coming soon
              </span>
            )}
          </div>

          {/* Required env names (NEVER values) */}
          {plugin.required_env_vars.length > 0 && (
            <p className="text-[10px] text-starlight-500">
              Needs: {plugin.required_env_vars.join(', ')}
            </p>
          )}

          {/* Last checked */}
          {plugin.last_checked && (
            <p className="text-[10px] text-starlight-500">
              Last checked: {new Date(plugin.last_checked).toLocaleString()}
            </p>
          )}

          {/* Failure reason inline */}
          {plugin.status === 'failed' && plugin.failure_reason && (
            <div className="flex items-start gap-1.5 rounded-md border border-rose-500/30 bg-rose-500/5 px-2 py-1 text-[11px] text-rose-200">
              <AlertTriangle size={11} className="mt-0.5 shrink-0" />
              <span>{plugin.failure_reason}</span>
            </div>
          )}

          {/* Skill-pack caption */}
          {plugin.is_skill_pack && plugin.is_skill_pack_caption && (
            <div className="flex items-start gap-1.5 rounded-md border border-violet-500/30 bg-violet-500/5 px-2 py-1 text-[11px] text-violet-200">
              <BookOpen size={11} className="mt-0.5 shrink-0" />
              <span>{plugin.is_skill_pack_caption}</span>
            </div>
          )}

          {/* Action row */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            <a
              href={plugin.official_url || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[10px] text-starlight-500 hover:text-starlight-300"
              onClick={(e) => {
                if (!plugin.official_url) e.preventDefault()
              }}
            >
              <ExternalLink size={10} />
              Source
            </a>
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

      {setupOpen && (
        <SetupDrawer
          plugin={plugin}
          plan={installPlan}
          loading={setupBusy}
          error={setupError}
          onClose={() => setSetupOpen(false)}
        />
      )}
    </>
  )
}

// ── Sub-components ──

const ACTION_ICON: Record<PluginAction, typeof Activity> = {
  install: Wrench,
  configure: Wrench,
  connect: Power,
  test: Activity,
  open: ExternalLink,
  setup_guide: Wrench,
}

function PluginIcon({ plugin }: { plugin: PluginCard }) {
  const iconBg =
    plugin.risk_level === 'high'
      ? 'bg-rose-500/15 text-rose-200'
      : plugin.risk_level === 'medium'
        ? 'bg-amber-500/10 text-amber-200'
        : 'bg-cyan-500/10 text-cyan-200'
  return (
    <div
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg font-mono text-sm ${iconBg}`}
      title={`${plugin.backing_types.join(' / ')} (risk: ${plugin.risk_level})`}
    >
      {plugin.icon}
    </div>
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

function SetupDrawer({
  plugin, plan, loading, error, onClose,
}: {
  plugin: PluginCard
  plan: InstallPlan | null
  loading: boolean
  error: string | null
  onClose: () => void
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-midnight-900/80 px-4"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-white/10 bg-midnight-400/95 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-accent-cyan">
              {plugin.is_skill_pack ? 'Skill pack details' : 'Setup guide'}
            </p>
            <h2 className="text-lg font-semibold text-starlight-100">
              {plugin.name}
            </h2>
            <p className="mt-1 text-xs text-starlight-400">{plugin.description}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md border border-white/10 bg-white/5 p-1.5 text-starlight-300 hover:bg-white/10"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </header>

        {plugin.is_skill_pack && (
          <div className="mb-3 rounded-lg border border-violet-500/30 bg-violet-500/5 p-3 text-xs text-violet-100">
            <BookOpen size={12} className="mr-1 inline" />
            <strong>This is a skill pack.</strong>{' '}
            {plugin.is_skill_pack_caption}{' '}
            Pair it with a runtime / MCP / app that exposes the
            corresponding tools to make it actionable.
          </div>
        )}

        {plugin.included_skills.length > 0 && (
          <div className="mb-3">
            <p className="mb-1 text-[10px] uppercase tracking-wider text-starlight-500">
              Included skills / capabilities
            </p>
            <ul className="flex flex-wrap gap-1.5">
              {plugin.included_skills.map((cap) => (
                <li
                  key={cap}
                  className="rounded bg-white/[0.04] px-2 py-0.5 text-[11px] text-starlight-200"
                >
                  {cap}
                </li>
              ))}
            </ul>
          </div>
        )}

        {plugin.required_env_vars.length > 0 && (
          <div className="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200">
            <strong>Required environment variables (NAMES only):</strong>
            <ul className="mt-1 list-disc pl-4">
              {plugin.required_env_vars.map((env) => (
                <li key={env}>
                  <code className="text-amber-100">{env}</code>
                </li>
              ))}
            </ul>
            <p className="mt-1 text-[10px] text-amber-200/70">
              Daena never reads or transmits the values. Set them in your
              source CLI's env or in Settings -&gt; Integrations.
            </p>
          </div>
        )}

        {loading && (
          <div className="rounded-lg border border-white/5 bg-white/[0.02] py-8 text-center text-sm text-starlight-400">
            <Loader2 size={16} className="mr-2 inline animate-spin" />
            Loading install plan...
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
            <AlertTriangle size={14} className="mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {plan && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2 rounded-md border border-white/5 bg-white/[0.03] px-3 py-2 text-[11px] text-starlight-400">
              <span>
                Vendor: <strong className="text-starlight-200">{plugin.vendor}</strong>
              </span>
              <span>·</span>
              <span>
                Auth: <strong className="text-starlight-200">{plugin.auth_type}</strong>
              </span>
              <span>·</span>
              <span>
                Install:{' '}
                <strong className="text-starlight-200">{plan.install_method}</strong>
              </span>
              <span>·</span>
              <span>
                Risk: <strong className="text-starlight-200">{plugin.risk_level}</strong>
              </span>
            </div>

            <ol className="space-y-3">
              {plan.steps.map((step, idx) => (
                <li
                  key={`${step.kind}-${idx}`}
                  className="rounded-lg border border-white/5 bg-white/[0.02] p-3"
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span className="rounded-full bg-primary-500/15 px-2 py-0.5 text-[10px] font-medium text-primary-200">
                      {step.kind}
                    </span>
                    <span className="text-[10px] text-starlight-500">
                      Step {idx + 1}
                    </span>
                  </div>
                  <p className="text-sm text-starlight-200">{step.text}</p>
                  {step.command && (
                    <pre className="mt-2 overflow-x-auto rounded-md border border-white/5 bg-midnight-900/50 p-2 text-[11px] text-emerald-200">
                      <code>{step.command}</code>
                    </pre>
                  )}
                  {step.url && (
                    <a
                      href={step.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-[11px] text-accent-cyan hover:underline"
                    >
                      <ExternalLink size={11} />
                      {step.url}
                    </a>
                  )}
                </li>
              ))}
            </ol>

            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-200">
              <strong>Daena does not execute install commands automatically.</strong>{' '}
              Copy each command into your own terminal. After install, run{' '}
              <strong>Discover installed tools</strong> in the Connections page
              header to import the new connector into Daena.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
